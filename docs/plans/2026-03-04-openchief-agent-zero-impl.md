# OpenChief × Agent Zero Integration — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace OpenChief's per-Chief Anthropic API calls with Agent Zero routing; add SQLite context persistence, async HealthMonitor, 17 Discord slash commands, Master Chief directive injection, Conference Room, and unify Telegram bot context with same SQLite store.

**Architecture:** `a0_client.py` is the single HTTP bridge to A0 at `localhost:50001`. `context_store.py` (SQLite via `aiosqlite`) maps `channel_id → a0_context_id`, replacing the dual in-memory context system. `health/monitor.py` runs an async background loop every 5 minutes monitoring A0 liveness, context fill, and cron health.

**Tech Stack:** Python 3.11+, discord.py 2.4+, aiosqlite 0.20.0, aiohttp 3.9.3, pytest 8.1.0 + pytest-asyncio 0.23.5; Node.js + better-sqlite3 for Telegram bot.

**Working directory:** `C:\Users\Troy\openchief` (unless noted)

---

## Pre-flight check

Before starting, verify the test suite is green:

```bash
cd C:\Users\Troy\openchief
pytest tests/test_smoke.py -v
```
Expected: all pass. If any fail, fix before proceeding.

Also verify A0 is reachable:
```bash
curl http://localhost:50001/health
```
Expected: HTTP 200. If not, start Agent Zero on Mini before continuing.

---

### Task 1: Create `agents/a0_client.py`

**Files:**
- Create: `agents/a0_client.py`
- Test: `tests/test_a0_client.py`

**Step 1: Write the failing test**

```python
# tests/test_a0_client.py
import os, asyncio, pytest
os.environ.setdefault("A0_BASE_URL", "http://localhost:50001")
os.environ.setdefault("A0_API_KEY", "")

@pytest.mark.asyncio
async def test_ping_returns_bool():
    """ping() returns True or False — never raises."""
    from agents.a0_client import ping
    result = await ping()
    assert isinstance(result, bool)

@pytest.mark.asyncio
async def test_ask_a0_offline_raises(monkeypatch):
    """ask_a0() raises an exception if A0 is unreachable (bad URL)."""
    monkeypatch.setenv("A0_BASE_URL", "http://localhost:1")
    import importlib, agents.a0_client as mod
    importlib.reload(mod)
    with pytest.raises(Exception):
        await mod.ask_a0("hello", "ctx-test")
    # reload back to good URL
    monkeypatch.setenv("A0_BASE_URL", "http://localhost:50001")
    importlib.reload(mod)

def test_a0_client_imports():
    from agents.a0_client import ask_a0, send_directive, ping
    assert callable(ask_a0) and callable(send_directive) and callable(ping)
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_a0_client.py -v
```
Expected: `ImportError: cannot import name 'ping' from 'agents.a0_client'`

**Step 3: Write `agents/a0_client.py`**

```python
"""
Single HTTP bridge to Agent Zero (localhost:50001).
All OpenChief → A0 communication flows through here.
"""
import os
import aiohttp

A0_BASE_URL = os.getenv("A0_BASE_URL", "http://localhost:50001")
A0_API_KEY  = os.getenv("A0_API_KEY", "")


def _headers() -> dict:
    if A0_API_KEY:
        return {"Authorization": f"Bearer {A0_API_KEY}"}
    return {}


async def ask_a0(prompt: str, context_id: str, system_role: str = "") -> str:
    """Send a prompt to Agent Zero and return the response text."""
    # Re-read env on every call so hot-reload works in tests
    base = os.getenv("A0_BASE_URL", A0_BASE_URL)
    payload: dict = {"message": prompt, "context_id": context_id}
    if system_role:
        payload["system"] = system_role
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{base}/agent/dispatch",
            json=payload,
            headers=_headers(),
            timeout=aiohttp.ClientTimeout(total=120),
        ) as resp:
            resp.raise_for_status()
            data = await resp.json()
            return data.get("response", "")


async def send_directive(text: str, context_ids: list) -> None:
    """Inject a Master Chief directive into every supplied A0 context."""
    wrapped = f"[MASTER CHIEF DIRECTIVE]\n{text}"
    for cid in context_ids:
        try:
            await ask_a0(wrapped, cid)
        except Exception:
            pass  # best-effort; HealthMonitor will catch A0 being down


async def ping() -> bool:
    """Return True if Agent Zero responds on /health."""
    try:
        base = os.getenv("A0_BASE_URL", A0_BASE_URL)
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{base}/health",
                timeout=aiohttp.ClientTimeout(total=5),
            ) as resp:
                return resp.status == 200
    except Exception:
        return False
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/test_a0_client.py -v
```
Expected: 3 passed (ping returns bool, bad URL raises, imports work)

**Step 5: Commit**

```bash
git add agents/a0_client.py tests/test_a0_client.py
git commit -m "feat: add a0_client.py — single HTTP bridge to Agent Zero"
```

---

### Task 2: Create `memory/context_store.py`

**Files:**
- Create: `memory/context_store.py`
- Test: `tests/test_context_store.py`

**Step 1: Write the failing test**

```python
# tests/test_context_store.py
import os, asyncio, pytest
from pathlib import Path

@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    """Override DB_PATH so tests don't touch the real database."""
    db = tmp_path / "test_contexts.db"
    monkeypatch.setenv("CONTEXT_DB_PATH", str(db))
    return str(db)

@pytest.mark.asyncio
async def test_get_or_create_returns_stable_id(tmp_db):
    import importlib, memory.context_store as mod
    importlib.reload(mod)
    await mod.init_db()
    id1 = await mod.get_or_create("channel-1")
    id2 = await mod.get_or_create("channel-1")
    assert id1 == id2
    assert len(id1) == 36  # UUID

@pytest.mark.asyncio
async def test_different_channels_get_different_ids(tmp_db):
    import importlib, memory.context_store as mod
    importlib.reload(mod)
    await mod.init_db()
    a = await mod.get_or_create("channel-A")
    b = await mod.get_or_create("channel-B")
    assert a != b

@pytest.mark.asyncio
async def test_all_active_returns_rows(tmp_db):
    import importlib, memory.context_store as mod
    importlib.reload(mod)
    await mod.init_db()
    await mod.get_or_create("chan-1")
    await mod.get_or_create("chan-2")
    rows = await mod.all_active()
    assert len(rows) >= 2

@pytest.mark.asyncio
async def test_delete_context(tmp_db):
    import importlib, memory.context_store as mod
    importlib.reload(mod)
    await mod.init_db()
    await mod.get_or_create("to-delete")
    await mod.delete_context("to-delete")
    rows = await mod.all_active()
    ids = [r["channel_id"] for r in rows]
    assert "to-delete" not in ids

def test_create_ephemeral_is_unique():
    from memory.context_store import create_ephemeral
    a = create_ephemeral("analytics")
    b = create_ephemeral("analytics")
    assert a != b
    assert a.startswith("ephemeral-analytics-")
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_context_store.py -v
```
Expected: `ModuleNotFoundError: No module named 'memory.context_store'` or similar

**Step 3: Write `memory/context_store.py`**

```python
"""
SQLite-backed context store: maps channel_id → Agent Zero context_id.
Survives restarts. Shared between openchief (Python) and chief-botsuite (Node.js).
"""
import os, uuid, aiosqlite
from datetime import datetime, timezone
from pathlib import Path

_DEFAULT_DB = Path(__file__).parent.parent / "data" / "contexts.db"


def _db_path() -> Path:
    env = os.getenv("CONTEXT_DB_PATH")
    return Path(env) if env else _DEFAULT_DB


async def init_db():
    """Create tables if they don't exist. Call once at bot startup."""
    p = _db_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(p) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS contexts (
                channel_id    TEXT PRIMARY KEY,
                a0_context_id TEXT NOT NULL,
                context_type  TEXT DEFAULT 'channel',
                created_at    TEXT NOT NULL,
                last_used     TEXT NOT NULL,
                message_count INTEGER DEFAULT 0,
                health_pct    REAL    DEFAULT 0.0
            )
        """)
        # WAL mode for concurrent Python + Node.js access
        await db.execute("PRAGMA journal_mode=WAL")
        await db.commit()


async def get_or_create(channel_id: str, context_type: str = "channel") -> str:
    """Return existing a0_context_id or create a new one for channel_id."""
    p = _db_path()
    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(p) as db:
        db.row_factory = aiosqlite.Row
        row = await (await db.execute(
            "SELECT a0_context_id FROM contexts WHERE channel_id=?", (channel_id,)
        )).fetchone()
        if row:
            await db.execute(
                "UPDATE contexts SET last_used=? WHERE channel_id=?", (now, channel_id)
            )
            await db.commit()
            return row["a0_context_id"]
        cid = str(uuid.uuid4())
        await db.execute(
            "INSERT INTO contexts VALUES (?,?,?,?,?,0,0.0)",
            (channel_id, cid, context_type, now, now),
        )
        await db.commit()
        return cid


async def update_health(channel_id: str, message_count: int, health_pct: float):
    p = _db_path()
    async with aiosqlite.connect(p) as db:
        await db.execute(
            "UPDATE contexts SET message_count=?, health_pct=? WHERE channel_id=?",
            (message_count, health_pct, channel_id),
        )
        await db.commit()


async def all_active() -> list:
    """Return context rows used in the last 7 days."""
    p = _db_path()
    async with aiosqlite.connect(p) as db:
        db.row_factory = aiosqlite.Row
        rows = await (await db.execute("""
            SELECT * FROM contexts
            WHERE last_used > datetime('now', '-7 days')
            ORDER BY last_used DESC
        """)).fetchall()
        return [dict(r) for r in rows]


async def delete_context(channel_id: str):
    """Remove context (used by /reset command)."""
    p = _db_path()
    async with aiosqlite.connect(p) as db:
        await db.execute("DELETE FROM contexts WHERE channel_id=?", (channel_id,))
        await db.commit()


def create_ephemeral(label: str) -> str:
    """Return a single-use context_id for cron jobs. Not persisted."""
    return f"ephemeral-{label}-{uuid.uuid4()}"
```

**Step 4: Run tests**

```bash
pytest tests/test_context_store.py -v
```
Expected: 5 passed

**Step 5: Commit**

```bash
git add memory/context_store.py tests/test_context_store.py
git commit -m "feat: add context_store.py — SQLite persistence for A0 context IDs"
```

---

### Task 3: Modify `agents/base_agent.py` — swap `_call_llm` to A0 routing

**Files:**
- Modify: `agents/base_agent.py`
- Test: `tests/test_base_agent.py`

**Step 1: Write the failing test**

```python
# tests/test_base_agent.py
import os, asyncio, pytest
os.environ.setdefault("DISCORD_TOKEN", "test")
os.environ.setdefault("A0_BASE_URL", "http://localhost:50001")
os.environ.setdefault("CONTEXT_DB_PATH", "/tmp/test_base_agent.db")

@pytest.mark.asyncio
async def test_call_llm_routes_to_a0(monkeypatch, tmp_path):
    """_call_llm now calls a0_client.ask_a0 instead of Anthropic SDK."""
    monkeypatch.setenv("CONTEXT_DB_PATH", str(tmp_path / "test.db"))

    # Patch ask_a0 to return a canned reply
    import agents.a0_client as a0mod
    async def fake_ask(prompt, context_id, system_role=""):
        return f"A0 says: {prompt}"
    monkeypatch.setattr(a0mod, "ask_a0", fake_ask)

    import importlib, agents.base_agent as mod
    importlib.reload(mod)

    class FakeBot:
        pass

    agent = mod.BaseAgent(FakeBot(), "TestChief", "test_channel", "You are helpful.")
    await mod.init_store()  # init sqlite

    result = await agent._call_llm("troy", "hello world")
    assert "hello world" in result

def test_base_agent_has_no_anthropic_client():
    """After refactor, BaseAgent should not instantiate an Anthropic client."""
    import importlib, agents.base_agent as mod
    importlib.reload(mod)
    import inspect
    src = inspect.getsource(mod.BaseAgent.__init__)
    assert "anthropic.Anthropic" not in src
```

**Step 2: Run to verify fails**

```bash
pytest tests/test_base_agent.py -v
```
Expected: FAIL — `AttributeError: module 'agents.base_agent' has no attribute 'init_store'`

**Step 3: Rewrite `agents/base_agent.py`**

Replace entirely:

```python
"""
Base class for all OpenChief agents.
All LLM calls now route through Agent Zero via a0_client.
"""
import asyncio
import discord
from agents import a0_client
from memory.context_store import get_or_create, init_db
from event_logging.event_logger import EventLogger

# Module-level init flag so init_db only runs once
_store_ready = False


async def init_store():
    """Call once at bot startup to ensure SQLite tables exist."""
    global _store_ready
    if not _store_ready:
        await init_db()
        _store_ready = True


class BaseAgent:
    """
    Base class for all OpenChief Chiefs.
    _call_llm routes to Agent Zero; context is stored in SQLite.
    """

    MAX_DISCORD_MSG = 1900

    def __init__(self, bot, name: str, channel_key: str, system_prompt: str):
        self.bot = bot
        self.name = name
        self.channel_key = channel_key
        self.system_prompt = system_prompt
        self.logger = EventLogger()

    def _channel_store_key(self, channel_id) -> str:
        """Stable key per Chief × channel so Chiefs don't share A0 context."""
        return f"{self.channel_key}:{channel_id}"

    async def handle_message(self, content: str, author: str) -> str:
        """
        Receive content + author string, call A0, return reply text.
        Sending is handled by bot/client.py so redaction can run first.
        """
        try:
            reply = await self._call_llm(author, content)
            self.logger.log_event("agent_response", {
                "agent": self.name,
                "channel": self.channel_key,
                "user": author,
                "reply_len": len(reply),
            })
            return reply
        except Exception as e:
            self.logger.log_event("agent_error", {"agent": self.name, "error": str(e)})
            raise

    async def _call_llm(self, author: str, content: str) -> str:
        """Route to Agent Zero with this Chief's system prompt and persisted context."""
        # Use per-Chief context key so Chiefs don't bleed into each other
        context_id = await get_or_create(self.channel_key, context_type="chief")
        prompt = f"{author}: {content}"
        return await a0_client.ask_a0(prompt, context_id, self.system_prompt)

    async def _send_chunks(self, channel: discord.abc.Messageable, text: str):
        """Send a long message in safe chunks ≤ MAX_DISCORD_MSG chars."""
        if len(text) <= self.MAX_DISCORD_MSG:
            await channel.send(text)
            return
        chunks = [text[i:i + self.MAX_DISCORD_MSG]
                  for i in range(0, len(text), self.MAX_DISCORD_MSG)]
        for chunk in chunks:
            await channel.send(chunk)
            await asyncio.sleep(0.3)

    async def post(self, channel_id: int, message: str):
        """Post a message to any channel by ID (used by cron jobs)."""
        channel = self.bot.get_channel(channel_id)
        if channel:
            await self._send_chunks(channel, message)
        else:
            self.logger.log_event("post_failed", {
                "agent": self.name,
                "channel_id": channel_id,
                "reason": "channel_not_found",
            })

    async def clear_context(self, channel_id: int):
        """Delete A0 context for this Chief × channel."""
        from memory.context_store import delete_context
        await delete_context(self._channel_store_key(channel_id))
        self.logger.log_event("context_cleared", {"agent": self.name})
```

**Step 4: Run tests**

```bash
pytest tests/test_base_agent.py -v
```
Expected: 2 passed

Also run full suite:
```bash
pytest tests/test_smoke.py -v
```
Expected: all pass (smoke tests import BaseAgent without Anthropic client)

**Step 5: Commit**

```bash
git add agents/base_agent.py tests/test_base_agent.py
git commit -m "feat: swap BaseAgent._call_llm to route through Agent Zero"
```

---

### Task 4: Create `health/monitor.py`

**Files:**
- Create: `health/__init__.py` (empty)
- Create: `health/monitor.py`
- Test: `tests/test_health_monitor.py`

**Step 1: Write the failing test**

```python
# tests/test_health_monitor.py
import os, asyncio, pytest
os.environ.setdefault("CONTEXT_DB_PATH", "/tmp/test_monitor.db")

def test_health_monitor_imports():
    from health.monitor import HealthMonitor
    assert HealthMonitor is not None

@pytest.mark.asyncio
async def test_monitor_check_a0_offline(monkeypatch, tmp_path):
    """HealthMonitor posts alert when A0 is unreachable."""
    monkeypatch.setenv("CONTEXT_DB_PATH", str(tmp_path / "test.db"))
    import agents.a0_client as a0mod
    async def fake_ping():
        return False
    monkeypatch.setattr(a0mod, "ping", fake_ping)

    from health.monitor import HealthMonitor
    alerts = []

    class FakeChannel:
        async def send(self, msg):
            alerts.append(msg)

    class FakeBot:
        def get_channel(self, cid):
            return FakeChannel()

    monitor = HealthMonitor(FakeBot(), console_channel_id=999)
    await monitor._check_a0()
    assert any("unreachable" in a.lower() or "offline" in a.lower() for a in alerts)

@pytest.mark.asyncio
async def test_monitor_check_a0_online(monkeypatch, tmp_path):
    """HealthMonitor posts nothing when A0 is reachable."""
    monkeypatch.setenv("CONTEXT_DB_PATH", str(tmp_path / "test.db"))
    import agents.a0_client as a0mod
    async def fake_ping():
        return True
    monkeypatch.setattr(a0mod, "ping", fake_ping)

    from health.monitor import HealthMonitor
    alerts = []

    class FakeChannel:
        async def send(self, msg):
            alerts.append(msg)

    class FakeBot:
        def get_channel(self, cid):
            return FakeChannel()

    monitor = HealthMonitor(FakeBot(), console_channel_id=999)
    await monitor._check_a0()
    assert alerts == []
```

**Step 2: Run to verify fails**

```bash
pytest tests/test_health_monitor.py -v
```
Expected: `ModuleNotFoundError: No module named 'health'`

**Step 3: Create `health/__init__.py` (empty) and `health/monitor.py`**

```python
# health/__init__.py
```

```python
# health/monitor.py
"""
Async background health loop — runs every 5 minutes.
Monitors: A0 liveness, context fill levels, cron watchdog.
Posts hourly status digest to #openchief-console.
"""
import asyncio
import logging
from datetime import datetime, timezone

from agents.a0_client import ask_a0, ping
from memory.context_store import all_active, update_health, init_db

log = logging.getLogger("health.monitor")

FILL_WARN  = 70    # % — silent log warning
FILL_ALERT = 90    # % — post to console channel
FILL_FULL  = 100   # % — auto-compact

CHECK_INTERVAL    = int(__import__("os").getenv("HEALTH_CHECK_INTERVAL", "300"))  # 5 min
DIGEST_INTERVAL   = 3600   # 1 hour
COMPACT_THRESHOLD = 15     # summarize oldest N messages


class HealthMonitor:
    def __init__(self, bot, console_channel_id: int):
        self.bot = bot
        self.console_channel_id = console_channel_id
        self._last_digest = datetime.now(timezone.utc)
        self._task = None

    async def start(self):
        """Initialize DB and launch background loop."""
        await init_db()
        self._task = asyncio.create_task(self._loop())
        log.info("HealthMonitor started (interval=%ds)", CHECK_INTERVAL)

    def stop(self):
        if self._task:
            self._task.cancel()

    async def _loop(self):
        while True:
            try:
                await self._check_a0()
                await self._check_contexts()
                await self._maybe_digest()
            except Exception as exc:
                log.error("HealthMonitor loop error: %s", exc)
            await asyncio.sleep(CHECK_INTERVAL)

    async def _check_a0(self):
        alive = await ping()
        if not alive:
            await self._console("🔴 **Agent Zero unreachable** — check Mini at `localhost:50001`")
            log.warning("Agent Zero unreachable")

    async def _check_contexts(self):
        for row in await all_active():
            pct = row.get("health_pct", 0)
            ch_id = row["channel_id"]
            if pct >= FILL_FULL:
                await self._compact(ch_id, row["a0_context_id"])
            elif pct >= FILL_ALERT:
                await self._console(
                    f"⚠️ Context `{ch_id}` at **{pct:.0f}%** fill — "
                    f"compaction triggers at 100%"
                )
            elif pct >= FILL_WARN:
                log.warning("Context %s at %.0f%% fill", ch_id, pct)

    async def _compact(self, channel_id: str, context_id: str):
        """Ask A0 to summarize the oldest COMPACT_THRESHOLD messages."""
        prompt = (
            f"[SYSTEM: Context compaction requested] "
            f"Summarize the oldest {COMPACT_THRESHOLD} messages in this conversation "
            f"into a single concise paragraph. Preserve all task context, "
            f"decisions, and action items. Replace those messages with the summary."
        )
        try:
            await ask_a0(prompt, context_id)
            await update_health(channel_id, 0, 50.0)  # reset fill estimate
            log.info("Compacted context %s for channel %s", context_id, channel_id)
        except Exception as exc:
            log.error("Compaction failed for %s: %s", context_id, exc)

    async def _maybe_digest(self):
        now = datetime.now(timezone.utc)
        elapsed = (now - self._last_digest).total_seconds()
        if elapsed < DIGEST_INTERVAL:
            return
        self._last_digest = now
        rows = await all_active()
        a0_alive = await ping()
        top_fill = max((r.get("health_pct", 0) for r in rows), default=0)
        msg = (
            f"**OpenChief Hourly Digest** — {now.strftime('%H:%M UTC')}\n"
            f"Agent Zero: {'🟢 online' if a0_alive else '🔴 offline'}\n"
            f"Active contexts: {len(rows)}\n"
            f"Max context fill: {top_fill:.0f}%"
        )
        await self._console(msg)

    async def _console(self, message: str):
        ch = self.bot.get_channel(self.console_channel_id)
        if ch:
            await ch.send(message)
        else:
            log.warning("Console channel %d not found", self.console_channel_id)
```

**Step 4: Run tests**

```bash
pytest tests/test_health_monitor.py -v
```
Expected: 3 passed

**Step 5: Commit**

```bash
git add health/__init__.py health/monitor.py tests/test_health_monitor.py
git commit -m "feat: add health/monitor.py — async A0 + context health loop"
```

---

### Task 5: Update `bot/channels.py`

**Files:**
- Modify: `bot/channels.py`

**Step 1: Read the file** (already read above — see Task prep)

**Step 2: Add CHANNEL_AGENTS_CONFERENCE and CHANNEL_OPENCHIEF_CONSOLE**

```python
# Add these two lines to bot/channels.py after the existing CHANNELS dict:
CHANNELS["agents_conference"] = _ch("CHANNEL_AGENTS_CONFERENCE")
CHANNELS["openchief_console"] = _ch("CHANNEL_OPENCHIEF_CONSOLE")
```

Full updated file:

```python
import os


def _ch(key: str, default: str = "0") -> int:
    val = os.getenv(key, default)
    try:
        return int(val)
    except (ValueError, TypeError):
        return 0


CHANNELS = {
    "alerts":              _ch("CHANNEL_ALERTS"),
    "trading_desk":        _ch("CHANNEL_TRADING_DESK"),
    "treasury":            _ch("CHANNEL_TREASURY"),
    "camp_marketplace":    _ch("CHANNEL_CAMP_MARKETPLACE"),
    "content_pipeline":    _ch("CHANNEL_CONTENT_PIPELINE"),
    "daily_digest":        _ch("CHANNEL_DAILY_DIGEST", "1468062917755801640"),
    "project_mgmt":        _ch("CHANNEL_PROJECT_MGMT"),
    "browser_ops":         _ch("CHANNEL_BROWSER_OPS"),
    "agents_conference":   _ch("CHANNEL_AGENTS_CONFERENCE"),   # Chiefs post summaries here
    "openchief_console":   _ch("CHANNEL_OPENCHIEF_CONSOLE"),   # HealthMonitor alerts here
}

CHANNEL_NAMES = {v: k for k, v in CHANNELS.items() if v != 0}
```

**Step 3: Add to `.env`**

```bash
# Append to C:\Users\Troy\openchief\.env:
CHANNEL_AGENTS_CONFERENCE=   # paste Discord channel ID
CHANNEL_OPENCHIEF_CONSOLE=   # paste Discord channel ID
TROY_DISCORD_ID=             # paste Troy's Discord user ID (right-click → Copy ID)
```

**Step 4: Verify smoke tests still pass**

```bash
pytest tests/test_smoke.py::test_import_channels -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add bot/channels.py
git commit -m "feat: add agents_conference and openchief_console channel IDs"
```

---

### Task 6: Rewrite `bot/client.py` — wire A0 routing + HealthMonitor

**Files:**
- Modify: `bot/client.py`

This is the largest single change. Replace the file in full.

**Step 1: Verify existing smoke test passes (baseline)**

```bash
pytest tests/test_smoke.py -v
```

**Step 2: Rewrite `bot/client.py`**

```python
"""
Main Discord bot client.
- Routes messages to correct Chief agent based on channel.
- 3-layer security on every inbound message.
- 17 native slash commands.
- Master Chief directive handler (Troy reply-to-bot).
- HealthMonitor background loop.
"""
import os
import discord
from discord import app_commands
from discord.ext import commands

from agents.project_chief import ProjectChief
from agents.finance_chief import FinanceChief
from agents.trade_chief import TradeChief
from agents.comms_chief import CommsChief
from agents.camp_chief import CampChief
from agents.base_agent import init_store
from agents.a0_client import ask_a0, send_directive
from bot.channels import CHANNELS, CHANNEL_NAMES
from security.layer1_gateway import Layer1Gateway
from security.layer2_injection import Layer2Injection
from security.layer3_data import Layer3Data
from memory.context_store import get_or_create, delete_context
from health.monitor import HealthMonitor
from cron.scheduler import setup_scheduler
from event_logging.event_logger import EventLogger

logger = EventLogger()

TROY_DISCORD_ID = int(os.getenv("TROY_DISCORD_ID", "0"))


def create_bot() -> commands.Bot:
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True

    bot = commands.Bot(command_prefix="!", intents=intents)

    gw     = Layer1Gateway()
    inj    = Layer2Injection()
    redact = Layer3Data()
    agents: dict = {}
    monitor: HealthMonitor | None = None

    def _build_agents():
        agents[CHANNELS["project_mgmt"]]     = ProjectChief(bot)
        agents[CHANNELS["treasury"]]         = FinanceChief(bot)
        agents[CHANNELS["trading_desk"]]     = TradeChief(bot)
        agents[CHANNELS["content_pipeline"]] = CommsChief(bot)
        agents[CHANNELS["camp_marketplace"]] = CampChief(bot)

    # ── Lifecycle ────────────────────────────────────────────────────────────

    @bot.event
    async def on_ready():
        nonlocal monitor
        await init_store()
        _build_agents()

        console_id = CHANNELS.get("openchief_console", 0)
        monitor = HealthMonitor(bot, console_channel_id=console_id)
        await monitor.start()

        scheduler = setup_scheduler(bot)
        scheduler.start()
        bot._scheduler = scheduler
        bot._monitor   = monitor

        # Sync slash commands with Discord
        try:
            synced = await bot.tree.sync()
            logger.log_event("slash_synced", {"count": len(synced)})
        except Exception as exc:
            logger.log_event("slash_sync_failed", {"error": str(exc)})

        logger.log_event("bot_ready", {"user": str(bot.user), "guilds": len(bot.guilds)})
        print(f"[OpenChief] Online as {bot.user} | {len(synced)} slash commands synced")

    # ── Message handler ──────────────────────────────────────────────────────

    @bot.event
    async def on_message(message: discord.Message):
        if message.author == bot.user:
            return

        channel_id = message.channel.id
        content = message.content.strip()
        if not content:
            return

        # ── Master Chief directive detection ───────────────────────────────
        if (message.reference
                and TROY_DISCORD_ID
                and message.author.id == TROY_DISCORD_ID
                and not content.startswith("/")):
            try:
                ref = await message.channel.fetch_message(message.reference.message_id)
                if ref.author == bot.user:
                    active = await __import__("memory.context_store",
                                             fromlist=["all_active"]).all_active()
                    ctx_ids = [r["a0_context_id"] for r in active]
                    await send_directive(content, ctx_ids)
                    await message.add_reaction("✅")
                    logger.log_event("master_chief_directive", {
                        "user": str(message.author),
                        "contexts": len(ctx_ids),
                    })
                    return
            except Exception as exc:
                logger.log_event("directive_error", {"error": str(exc)})

        # ── Security layers ─────────────────────────────────────────────────
        if not gw.check_channel_access(channel_id, message.author):
            logger.log_event("security_block", {
                "layer": 1, "channel": channel_id, "user": str(message.author),
            })
            return

        risk = inj.scan(content)
        if risk == "HIGH":
            logger.log_event("security_block", {
                "layer": 2, "risk": risk, "channel": channel_id, "user": str(message.author),
            })
            await message.channel.send("⛔ Message blocked: potential injection attempt.")
            return

        safe_content, was_redacted = redact.check_outbound(content)
        if was_redacted:
            logger.log_event("secret_redacted", {
                "channel": channel_id, "user": str(message.author),
            })

        # ── Route to Chief ───────────────────────────────────────────────────
        agent = agents.get(channel_id)
        if agent is None:
            await bot.process_commands(message)
            return

        channel_name = CHANNEL_NAMES.get(channel_id, str(channel_id))
        logger.log_event("message_received", {
            "channel": channel_name, "user": str(message.author),
        })

        async with message.channel.typing():
            try:
                reply = await agent.handle_message(safe_content, message.author.display_name)
                safe_reply, _ = redact.check_outbound(reply)
                await agent._send_chunks(message.channel, safe_reply)
            except Exception as exc:
                logger.log_event("agent_error", {
                    "channel": channel_name, "error": str(exc),
                })
                await message.channel.send("⚠️ An error occurred. Please try again.")

        await bot.process_commands(message)

    # ── Slash command helpers ────────────────────────────────────────────────

    async def _slash_dispatch(
        interaction: discord.Interaction,
        prompt: str,
        system_prefix: str = "",
        timeout_note: str = "",
    ):
        """Common slash command handler: route prompt to A0, reply."""
        await interaction.response.defer(thinking=True)
        channel_id = str(interaction.channel_id)
        context_id = await get_or_create(channel_id)
        full_prompt = f"{system_prefix}{prompt}" if system_prefix else prompt
        safe_prompt, _ = redact.check_outbound(full_prompt)
        try:
            reply = await ask_a0(safe_prompt, context_id)
            safe_reply, _ = redact.check_outbound(reply)
            # Discord followup max 2000 chars
            if len(safe_reply) > 1900:
                chunks = [safe_reply[i:i+1900] for i in range(0, len(safe_reply), 1900)]
                await interaction.followup.send(chunks[0])
                for chunk in chunks[1:]:
                    await interaction.channel.send(chunk)
            else:
                await interaction.followup.send(safe_reply)
        except Exception as exc:
            await interaction.followup.send(f"⚠️ Error: {exc}")

    # ── 17 Slash Commands ────────────────────────────────────────────────────

    @bot.tree.command(name="ask", description="Ask Agent Zero anything")
    @app_commands.describe(question="Your question")
    async def slash_ask(interaction: discord.Interaction, question: str):
        await _slash_dispatch(interaction, question)

    @bot.tree.command(name="plan", description="Create or view the 30–90 day strategic plan")
    @app_commands.describe(goal="Optional goal or focus area")
    async def slash_plan(interaction: discord.Interaction, goal: str = ""):
        await _slash_dispatch(
            interaction,
            goal or "What should we focus on right now?",
            "[CEO lens] Create a strategic 30–90 day plan across all active projects. "
            "Cover milestones, blockers, resource priorities. ",
        )

    @bot.tree.command(name="today", description="Today's top priorities and focus")
    @app_commands.describe(context="Optional context or constraint")
    async def slash_today(interaction: discord.Interaction, context: str = ""):
        await _slash_dispatch(
            interaction,
            context or "Consider all active projects.",
            "[Chief of Staff lens] Design my focus for today. "
            "List top 3–5 priorities with clear next actions. ",
        )

    @bot.tree.command(name="schedule", description="Show or update the weekly schedule")
    @app_commands.describe(update="Optional schedule update or query")
    async def slash_schedule(interaction: discord.Interaction, update: str = ""):
        await _slash_dispatch(
            interaction,
            update or "Show the current weekly schedule.",
            "[COO lens] Review or update the weekly schedule. "
            "Be specific about time blocks and owners. ",
        )

    @bot.tree.command(name="code", description="Send a coding task to Agent Zero")
    @app_commands.describe(task="Describe the coding task")
    async def slash_code(interaction: discord.Interaction, task: str):
        await _slash_dispatch(
            interaction, task,
            "[CODE TASK - ChiefDev] You are a senior software engineer. "
            "Use filesystem and GitHub MCP tools as needed. Task: ",
        )

    @bot.tree.command(name="review", description="Review a PR or code diff")
    @app_commands.describe(target="PR number, URL, or paste diff")
    async def slash_review(interaction: discord.Interaction, target: str):
        await _slash_dispatch(
            interaction, target,
            "[CODE REVIEW] Review the following for correctness, security, and style. "
            "List issues by severity. Target: ",
        )

    @bot.tree.command(name="deploy", description="Trigger or check a deployment pipeline")
    @app_commands.describe(target="Project or environment to deploy")
    async def slash_deploy(interaction: discord.Interaction, target: str):
        await _slash_dispatch(
            interaction, target,
            "[CTO lens] Run the deployment pipeline for: ",
        )

    @bot.tree.command(name="market", description="Crypto market summary")
    @app_commands.describe(query="Optional specific asset or question")
    async def slash_market(interaction: discord.Interaction, query: str = ""):
        await _slash_dispatch(
            interaction,
            query or "Give a current crypto market summary with key price levels.",
            "[CFO lens] Provide a concise market summary. ",
        )

    @bot.tree.command(name="portfolio", description="Portfolio status and P&L")
    @app_commands.describe(query="Optional asset or time range")
    async def slash_portfolio(interaction: discord.Interaction, query: str = ""):
        await _slash_dispatch(
            interaction,
            query or "Show current portfolio status and P&L.",
            "[CFO lens] Review portfolio status. ",
        )

    @bot.tree.command(name="trade", description="Execute or review a trade")
    @app_commands.describe(details="Trade details or review request")
    async def slash_trade(interaction: discord.Interaction, details: str):
        await _slash_dispatch(
            interaction, details,
            "[TRADE lens] Analyze or execute: ",
        )

    @bot.tree.command(name="research", description="Deep research on any topic")
    @app_commands.describe(topic="Research topic or question")
    async def slash_research(interaction: discord.Interaction, topic: str):
        await _slash_dispatch(
            interaction, topic,
            "[RESEARCH lens] Conduct thorough research on: ",
        )

    @bot.tree.command(name="summarize", description="Summarize a URL or pasted text")
    @app_commands.describe(content="URL or text to summarize")
    async def slash_summarize(interaction: discord.Interaction, content: str):
        await _slash_dispatch(
            interaction, content,
            "[CMO lens] Provide a concise summary of: ",
        )

    @bot.tree.command(name="brief", description="Morning briefing across all projects")
    async def slash_brief(interaction: discord.Interaction):
        await _slash_dispatch(
            interaction,
            "Generate a morning briefing: key priorities, blockers, wins, and risks "
            "across all active projects. Be concise and actionable.",
            "[MORNING BRIEF] ",
        )

    @bot.tree.command(name="status", description="System health: A0, contexts, crons")
    async def slash_status(interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        from agents.a0_client import ping
        a0_alive = await ping()
        rows = await __import__("memory.context_store",
                                fromlist=["all_active"]).all_active()
        top = max((r.get("health_pct", 0) for r in rows), default=0)
        lines = [
            "**OpenChief Status**",
            f"Agent Zero: {'🟢 online' if a0_alive else '🔴 offline'}",
            f"Active contexts: {len(rows)}",
            f"Max context fill: {top:.0f}%",
        ]
        await interaction.followup.send("\n".join(lines))

    @bot.tree.command(name="memory", description="Show A0 context stats for this channel")
    async def slash_memory(interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        rows = await __import__("memory.context_store",
                                fromlist=["all_active"]).all_active()
        channel_id = str(interaction.channel_id)
        match = next((r for r in rows if r["channel_id"] == channel_id), None)
        if match:
            msg = (
                f"**Context:** `{match['a0_context_id']}`\n"
                f"Messages: {match.get('message_count', '?')}\n"
                f"Fill: {match.get('health_pct', 0):.0f}%\n"
                f"Last used: {match.get('last_used', '?')}"
            )
        else:
            msg = "No context yet for this channel."
        await interaction.followup.send(msg)

    @bot.tree.command(name="compact", description="Force context compaction now")
    async def slash_compact(interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        mon = getattr(bot, "_monitor", None)
        if mon is None:
            await interaction.followup.send("⚠️ HealthMonitor not initialized.")
            return
        channel_id = str(interaction.channel_id)
        rows = await __import__("memory.context_store",
                                fromlist=["all_active"]).all_active()
        match = next((r for r in rows if r["channel_id"] == channel_id), None)
        if match:
            await mon._compact(channel_id, match["a0_context_id"])
            await interaction.followup.send("✅ Context compacted.")
        else:
            await interaction.followup.send("No context to compact for this channel.")

    @bot.tree.command(name="reset", description="Clear context for this channel")
    async def slash_reset(interaction: discord.Interaction):
        channel_id = str(interaction.channel_id)
        await delete_context(channel_id)
        await interaction.response.send_message("🔄 Context cleared. Fresh start.")

    # ── Legacy ! text commands ────────────────────────────────────────────────

    @bot.command(name="digest")
    async def cmd_digest(ctx_cmd):
        from cron.jobs.digest import job_digest
        await ctx_cmd.send("📋 Generating digest…")
        try:
            await job_digest(bot)
        except Exception as exc:
            await ctx_cmd.send(f"⚠️ Digest error: {exc}")

    @bot.command(name="jobs")
    async def cmd_jobs(ctx_cmd):
        sched = getattr(bot, "_scheduler", None)
        if sched is None:
            await ctx_cmd.send("Scheduler not attached.")
            return
        lines = ["**Scheduled Jobs:**"]
        for job in sched.get_jobs():
            nrt = str(job.next_run_time)[:19] if job.next_run_time else "paused"
            lines.append(f"- `{job.id}` next: {nrt} UTC")
        await ctx_cmd.send("\n".join(lines))

    return bot
```

**Step 3: Run smoke tests**

```bash
pytest tests/test_smoke.py -v
```
Expected: all pass. If any import fails, check that `ProjectChief(bot)` (now requires `bot` arg) matches the updated `base_agent.py`.

**Step 4: Commit**

```bash
git add bot/client.py
git commit -m "feat: rewrite bot/client.py — A0 routing, 17 slash commands, directive handler, HealthMonitor"
```

---

### Task 7: Create `tools/discord_bridge.py` + `dashboard/`

**Files:**
- Create: `tools/__init__.py` (empty)
- Create: `tools/discord_bridge.py`
- Create: `dashboard/data/.gitkeep`
- Create: `dashboard/index.html`
- Create: `dashboard/style.css`

**Step 1: Create `tools/__init__.py`**

Empty file.

**Step 2: Create `tools/discord_bridge.py`**

```python
"""
Polls #agents-conference every 60 seconds via Discord HTTP API.
Writes dashboard/data/conference_log.json for the dashboard to consume.
Run standalone: python -m tools.discord_bridge
Or import and call run() from bot/client.py on_ready.
"""
import os, asyncio, json, logging
from datetime import datetime, timezone
from pathlib import Path
import aiohttp

log = logging.getLogger("discord_bridge")

DISCORD_TOKEN        = os.getenv("DISCORD_TOKEN", "")
AGENTS_CONF_CHANNEL  = int(os.getenv("CHANNEL_AGENTS_CONFERENCE", "0"))
POLL_INTERVAL        = 60  # seconds
LOG_PATH = Path(__file__).parent.parent / "dashboard" / "data" / "conference_log.json"
MAX_LOG_ENTRIES      = 200

HEADERS = {
    "Authorization": f"Bot {DISCORD_TOKEN}",
    "Content-Type": "application/json",
}


async def fetch_recent_messages(limit: int = 20) -> list:
    url = f"https://discord.com/api/v10/channels/{AGENTS_CONF_CHANNEL}/messages?limit={limit}"
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                log.warning("Discord API returned %d", resp.status)
                return []
            data = await resp.json()
            return data


def _load_existing() -> list:
    if LOG_PATH.exists():
        try:
            return json.loads(LOG_PATH.read_text())
        except Exception:
            pass
    return []


async def poll_once():
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    messages = await fetch_recent_messages()
    if not messages:
        return
    existing = _load_existing()
    existing_ids = {m["id"] for m in existing}
    new_entries = []
    for m in messages:
        if m["id"] not in existing_ids:
            new_entries.append({
                "id":        m["id"],
                "author":    m["author"]["username"],
                "content":   m["content"][:500],
                "timestamp": m["timestamp"],
            })
    if new_entries:
        combined = new_entries + existing
        combined = combined[:MAX_LOG_ENTRIES]
        LOG_PATH.write_text(json.dumps(combined, indent=2))
        log.info("Added %d new messages to conference log", len(new_entries))


async def run():
    if not AGENTS_CONF_CHANNEL:
        log.warning("CHANNEL_AGENTS_CONFERENCE not set — bridge disabled")
        return
    log.info("Discord bridge polling #agents-conference every %ds", POLL_INTERVAL)
    while True:
        try:
            await poll_once()
        except Exception as exc:
            log.error("Bridge poll error: %s", exc)
        await asyncio.sleep(POLL_INTERVAL)
```

**Step 3: Create `dashboard/data/.gitkeep`** (empty file, ensures dir in git)

**Step 4: Create `dashboard/style.css`**

```css
/* dashboard/style.css — pixel-camp theme */
:root {
  --bg: #0a0e1a;
  --panel: #111827;
  --border: #1e2d40;
  --green: #22c55e;
  --yellow: #eab308;
  --red: #ef4444;
  --gray: #374151;
  --text: #e2e8f0;
  --muted: #64748b;
  --accent: #3b82f6;
  --pixel: "Courier New", monospace;
}

* { box-sizing: border-box; margin: 0; padding: 0; }

body {
  background: var(--bg);
  color: var(--text);
  font-family: var(--pixel);
  font-size: 13px;
  min-height: 100vh;
  padding: 16px;
}

h1 {
  font-size: 20px;
  letter-spacing: 2px;
  text-transform: uppercase;
  color: var(--accent);
  margin-bottom: 4px;
}

.subtitle { color: var(--muted); font-size: 11px; margin-bottom: 24px; }

/* Camp grid */
.camp-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 12px;
  margin-bottom: 32px;
}

.cabin {
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 16px 12px;
  text-align: center;
  transition: border-color 0.2s;
}

.cabin:hover { border-color: var(--accent); }

.cabin-icon { font-size: 32px; line-height: 1; margin-bottom: 8px; }
.cabin-name { font-size: 11px; text-transform: uppercase; letter-spacing: 1px; color: var(--muted); margin-bottom: 10px; }
.status-light { width: 10px; height: 10px; border-radius: 50%; display: inline-block; margin-bottom: 6px; }
.status-light.online  { background: var(--green);  box-shadow: 0 0 6px var(--green); }
.status-light.idle    { background: var(--yellow); box-shadow: 0 0 6px var(--yellow); }
.status-light.offline { background: var(--red);    box-shadow: 0 0 6px var(--red); }
.status-light.disabled{ background: var(--gray); }
.status-text { font-size: 10px; color: var(--muted); }

/* Conference log */
.log-panel {
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 4px;
  max-height: 420px;
  overflow-y: auto;
}

.log-header {
  padding: 10px 14px;
  border-bottom: 1px solid var(--border);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 1px;
  color: var(--accent);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.log-entry {
  padding: 10px 14px;
  border-bottom: 1px solid var(--border);
  line-height: 1.6;
}

.log-entry:last-child { border-bottom: none; }
.log-author { color: var(--accent); font-weight: bold; }
.log-time   { color: var(--muted); font-size: 10px; float: right; }
.log-content { margin-top: 4px; word-break: break-word; }
.log-empty  { padding: 24px; text-align: center; color: var(--muted); }

/* Links */
.links { display: flex; gap: 12px; margin-bottom: 24px; }
.link-btn {
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 8px 16px;
  color: var(--accent);
  text-decoration: none;
  font-size: 12px;
  transition: border-color 0.2s;
}
.link-btn:hover { border-color: var(--accent); }
```

**Step 5: Create `dashboard/index.html`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>OpenChief Control Center</title>
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <h1>⚡ OpenChief Control Center</h1>
  <p class="subtitle">Agent Zero × Chief System — Base Camp</p>

  <div class="links">
    <a class="link-btn" href="http://localhost:3000/portfolio" target="_blank">📊 Portfolio Manager</a>
    <a class="link-btn" href="#" id="a0-link" target="_blank">🤖 Agent Zero</a>
    <a class="link-btn" href="https://discord.com/channels/1468061349882892415" target="_blank">💬 Discord</a>
  </div>

  <div class="camp-grid" id="camp-grid">
    <div class="cabin">
      <div class="cabin-icon">🗂</div>
      <div class="cabin-name">ChiefPM</div>
      <div class="status-light idle" id="status-project_mgmt"></div>
      <div class="status-text" id="text-project_mgmt">idle</div>
    </div>
    <div class="cabin">
      <div class="cabin-icon">💻</div>
      <div class="cabin-name">ChiefDev</div>
      <div class="status-light idle" id="status-browser_ops"></div>
      <div class="status-text" id="text-browser_ops">idle</div>
    </div>
    <div class="cabin">
      <div class="cabin-icon">📊</div>
      <div class="cabin-name">ChiefFin</div>
      <div class="status-light idle" id="status-treasury"></div>
      <div class="status-text" id="text-treasury">idle</div>
    </div>
    <div class="cabin">
      <div class="cabin-icon">🔍</div>
      <div class="cabin-name">ChiefAnalyst</div>
      <div class="status-light idle" id="status-trading_desk"></div>
      <div class="status-text" id="text-trading_desk">idle</div>
    </div>
    <div class="cabin">
      <div class="cabin-icon">📣</div>
      <div class="cabin-name">ChiefComms</div>
      <div class="status-light idle" id="status-content_pipeline"></div>
      <div class="status-text" id="text-content_pipeline">idle</div>
    </div>
  </div>

  <div class="log-panel">
    <div class="log-header">
      <span>📡 Agents Conference</span>
      <span id="last-refresh">—</span>
    </div>
    <div id="log-entries"><div class="log-empty">Loading…</div></div>
  </div>

  <script>
    // Agent Zero URL from env (served via static file server that sets a meta tag, or hardcoded)
    const A0_URL = "http://localhost:50001";
    document.getElementById("a0-link").href = A0_URL;

    async function loadLog() {
      try {
        const res = await fetch("data/conference_log.json?t=" + Date.now());
        if (!res.ok) throw new Error(res.status);
        const entries = await res.json();
        const container = document.getElementById("log-entries");
        if (!entries.length) {
          container.innerHTML = '<div class="log-empty">No messages yet in #agents-conference</div>';
          return;
        }
        container.innerHTML = entries.map(e => {
          const time = new Date(e.timestamp).toLocaleTimeString([], {hour:"2-digit",minute:"2-digit"});
          return `<div class="log-entry">
            <span class="log-author">${e.author}</span>
            <span class="log-time">${time}</span>
            <div class="log-content">${e.content}</div>
          </div>`;
        }).join("");
        document.getElementById("last-refresh").textContent = "Updated " + new Date().toLocaleTimeString();
      } catch (err) {
        document.getElementById("log-entries").innerHTML =
          `<div class="log-empty">Could not load log: ${err.message}</div>`;
      }
    }

    loadLog();
    setInterval(loadLog, 30000); // refresh every 30s
  </script>
</body>
</html>
```

**Step 6: Verify smoke tests still pass**

```bash
pytest tests/test_smoke.py -v
```

**Step 7: Commit**

```bash
git add tools/__init__.py tools/discord_bridge.py dashboard/
git commit -m "feat: add discord_bridge.py + pixel-camp dashboard (Conference Room)"
```

---

### Task 8: Update `cron/scheduler.py` — ephemeral contexts per job

**Files:**
- Modify: `cron/scheduler.py`

**Step 1: Read one cron job to understand signature**

```bash
cat cron/jobs/analytics.py | head -20
```

**Step 2: Update `setup_scheduler` to pass ephemeral context IDs**

Add to the top of `cron/scheduler.py`:
```python
from memory.context_store import create_ephemeral
```

Update each `scheduler.add_job` to pass a fresh ephemeral context_id per run. The cleanest way is a thin wrapper:

```python
import asyncio, os, functools
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from memory.context_store import create_ephemeral

from cron.jobs.analytics   import job_analytics
from cron.jobs.monitoring  import job_monitoring
from cron.jobs.crm_sync    import job_crm_sync
from cron.jobs.treasury    import job_treasury
from cron.jobs.marketplace import job_marketplace
from cron.jobs.portfolio   import job_portfolio
from cron.jobs.research    import job_research
from cron.jobs.content     import job_content
from cron.jobs.digest      import job_digest

_DIGEST_HOURS = int(os.getenv("DIGEST_INTERVAL_HOURS", "24"))


def _with_ephemeral(job_fn, label: str):
    """Wrap a cron job to receive a fresh ephemeral context_id each run."""
    async def _wrapped(bot):
        context_id = create_ephemeral(label)
        # Pass context_id only if the job accepts it (keyword arg)
        try:
            await job_fn(bot, context_id=context_id)
        except TypeError:
            # Existing jobs that don't accept context_id yet — call without it
            await job_fn(bot)
    return _wrapped


def _digest_hour_list(interval: int) -> list:
    if interval >= 24:
        return [8]
    return list(range(0, 24, interval))


def setup_scheduler(bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="UTC")

    jobs = [
        ("analytics",   job_analytics,   CronTrigger(hour=1, minute=0)),
        ("monitoring",  job_monitoring,  CronTrigger(hour=1, minute=15)),
        ("crm_sync",    job_crm_sync,    CronTrigger(hour=2, minute=0)),
        ("treasury",    job_treasury,    CronTrigger(hour=3, minute=0)),
        ("marketplace", job_marketplace, CronTrigger(hour=4, minute=0)),
        ("portfolio",   job_portfolio,   CronTrigger(hour=5, minute=0)),
        ("research",    job_research,    CronTrigger(hour=6, minute=0)),
        ("content",     job_content,     CronTrigger(hour=7, minute=0)),
    ]

    for label, fn, trigger in jobs:
        scheduler.add_job(
            _with_ephemeral(fn, label), trigger, args=[bot], id=label
        )

    digest_hours = _digest_hour_list(_DIGEST_HOURS)
    for i, hour in enumerate(digest_hours):
        scheduler.add_job(
            _with_ephemeral(job_digest, f"digest_{i}"),
            CronTrigger(hour=hour, minute=0),
            args=[bot],
            id=f"digest_{i}",
        )

    label = f"every {_DIGEST_HOURS}h" if _DIGEST_HOURS < 24 else "daily at 08:00 UTC"
    print(f"[Scheduler] Digest: {label} → UTC hours {digest_hours}")
    return scheduler
```

**Step 3: Run smoke tests**

```bash
pytest tests/test_smoke.py -v
```
Expected: pass

**Step 4: Commit**

```bash
git add cron/scheduler.py
git commit -m "feat: cron jobs get ephemeral A0 context_id per run"
```

---

### Task 9: Update `requirements.txt` + `.gitignore` + `.env.example`

**Files:**
- Modify: `requirements.txt`
- Modify: `.gitignore` (or create if absent)

**Step 1: Update `requirements.txt`**

No new Python deps needed — `aiosqlite` and `aiohttp` already present.

Verify:
```bash
grep -E "aiosqlite|aiohttp" requirements.txt
```
Expected: both present.

**Step 2: Update `.gitignore`**

```bash
# Append to .gitignore (create if missing):
data/contexts.db
data/contexts.db-wal
data/contexts.db-shm
dashboard/data/conference_log.json
logs/
*.pyc
__pycache__/
.env
```

**Step 3: Add missing env vars to `.env`**

```bash
# Append to .env (sensitive values filled in manually):
A0_BASE_URL=http://localhost:50001
A0_API_KEY=
TROY_DISCORD_ID=
CHANNEL_AGENTS_CONFERENCE=
CHANNEL_OPENCHIEF_CONSOLE=
HEALTH_CHECK_INTERVAL=300
CONTEXT_DB_PATH=          # leave blank to use default data/contexts.db
```

**Step 4: Commit**

```bash
git add .gitignore requirements.txt
git commit -m "chore: update .gitignore and env vars for A0 integration"
```

---

### Task 10: Update `chief-botsuite/bot.js` — SQLite context + directive

**Working directory:** `C:\Users\Troy\Chief OS\chief-botsuite`

**Files:**
- Modify: `bot.js`

**Step 1: Install better-sqlite3**

```bash
cd "C:\Users\Troy\Chief OS\chief-botsuite"
npm install better-sqlite3
```

**Step 2: Add to `.env`**

```bash
# Append to chief-botsuite/.env:
CONTEXT_DB_PATH=C:\Users\Troy\openchief\data\contexts.db
TROY_TELEGRAM_ID=     # paste Troy's Telegram numeric user ID
```

**Step 3: Replace context management section in `bot.js`**

Remove the JSON file section (lines `let chatContexts`, `loadContexts`, `saveContexts`, `loadContexts()`) and replace with:

```javascript
// ─── SQLite context persistence ────────────────────────────────────────────
// Shares the same contexts.db as openchief/. Set CONTEXT_DB_PATH in .env.

const Database = require('better-sqlite3');
const DB_PATH = process.env.CONTEXT_DB_PATH ||
    path.join(__dirname, '..', 'openchief', 'data', 'contexts.db');

let db;
try {
    db = new Database(DB_PATH);
    db.pragma('journal_mode = WAL');
    db.exec(`
        CREATE TABLE IF NOT EXISTS contexts (
            channel_id    TEXT PRIMARY KEY,
            a0_context_id TEXT NOT NULL,
            context_type  TEXT DEFAULT 'telegram',
            created_at    TEXT NOT NULL,
            last_used     TEXT NOT NULL,
            message_count INTEGER DEFAULT 0,
            health_pct    REAL    DEFAULT 0.0
        )
    `);
    console.log('[contexts] SQLite connected:', DB_PATH);
} catch (e) {
    console.warn('[contexts] SQLite unavailable, falling back to memory:', e.message);
    db = null;
}

const inMemoryContexts = {};

function getContextId(chatId) {
    const key = `telegram:${chatId}`;
    if (!db) return inMemoryContexts[key] || null;
    const row = db.prepare('SELECT a0_context_id FROM contexts WHERE channel_id=?').get(key);
    if (row) {
        db.prepare('UPDATE contexts SET last_used=? WHERE channel_id=?')
          .run(new Date().toISOString(), key);
        return row.a0_context_id;
    }
    return null;
}

function setContextId(chatId, ctxId) {
    const key = `telegram:${chatId}`;
    if (!db) { inMemoryContexts[key] = ctxId; return; }
    const now = new Date().toISOString();
    db.prepare(`
        INSERT INTO contexts (channel_id, a0_context_id, context_type, created_at, last_used)
        VALUES (?, ?, 'telegram', ?, ?)
        ON CONFLICT(channel_id) DO UPDATE SET a0_context_id=excluded.a0_context_id, last_used=excluded.last_used
    `).run(key, ctxId, now, now);
}

function deleteContextId(chatId) {
    const key = `telegram:${chatId}`;
    if (!db) { delete inMemoryContexts[key]; return; }
    db.prepare('DELETE FROM contexts WHERE channel_id=?').run(key);
}

function getAllActiveContextIds() {
    if (!db) return Object.values(inMemoryContexts);
    const rows = db.prepare(
        "SELECT a0_context_id FROM contexts WHERE last_used > datetime('now', '-7 days')"
    ).all();
    return rows.map(r => r.a0_context_id);
}
```

**Step 4: Update `dispatch()` to use new functions**

Replace the `dispatch` function's context handling:
```javascript
// Old: const contextId = chatContexts[chatId];
const contextId = getContextId(chatId);

// Old: if (data.context_id && data.context_id !== contextId) {
//        chatContexts[chatId] = data.context_id;
//        saveContexts();
//      }
if (data.context_id && data.context_id !== contextId) {
    setContextId(chatId, data.context_id);
}
```

**Step 5: Update `/reset` command**

```javascript
bot.command('reset', async (ctx) => {
    deleteContextId(ctx.chat.id);   // was: delete chatContexts[ctx.chat.id]; saveContexts();
    await ctx.reply('🔄 Conversation reset. Fresh context started.');
});
```

**Step 6: Add Master Chief directive handler**

Add AFTER the `bot.on('text', ...)` handler and BEFORE `bot.on('voice', ...)`:

```javascript
// ─── Master Chief directive handler ─────────────────────────────────────────
// When Troy replies to a bot message with plain text, inject it into all A0 contexts.

const TROY_TELEGRAM_ID = parseInt(process.env.TROY_TELEGRAM_ID || '0', 10);

bot.on('message', async (ctx) => {
    const msg = ctx.message;
    if (!msg || !msg.text) return;
    if (msg.text.startsWith('/')) return;  // skip commands

    // Directive: Troy replies to a bot message
    if (TROY_TELEGRAM_ID
            && msg.from && msg.from.id === TROY_TELEGRAM_ID
            && msg.reply_to_message && msg.reply_to_message.from
            && msg.reply_to_message.from.is_bot) {

        const allContextIds = getAllActiveContextIds();
        const directive = `[MASTER CHIEF DIRECTIVE]\n${msg.text}`;
        let count = 0;
        for (const ctxId of allContextIds) {
            try {
                const res = await fetch(`${BRIDGE_URL}/agent/dispatch`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message: directive, context_id: ctxId }),
                });
                if (res.ok) count++;
            } catch { /* best-effort */ }
        }
        await ctx.reply(`✅ Directive broadcast to ${count} active context(s).`);
        return;
    }
});
```

**Step 7: Test manually**

Start the bot:
```bash
node bot.js
```
Expected: `[contexts] SQLite connected: C:\Users\Troy\openchief\data\contexts.db`

Send a Telegram message — confirm context_id saved to SQLite.

**Step 8: Commit**

```bash
cd "C:\Users\Troy\Chief OS\chief-botsuite"
git add bot.js
git commit -m "feat: bot.js uses shared SQLite context + Master Chief directive"
```

---

### Task 11: Update `tests/test_smoke.py` + add integration smoke

**Files:**
- Modify: `tests/test_smoke.py`

**Step 1: Remove stale imports, add new module tests**

Replace the `test_import_context_manager` and `test_import_base_agent` tests:

```python
# Replace old test_import_context_manager:
def test_import_context_store():
    from memory.context_store import get_or_create, init_db, create_ephemeral
    assert callable(get_or_create)

# Replace old test_import_base_agent:
def test_import_base_agent():
    from agents.base_agent import BaseAgent, init_store
    assert BaseAgent is not None and callable(init_store)

# Add new imports:
def test_import_a0_client():
    from agents.a0_client import ask_a0, send_directive, ping
    assert callable(ping)

def test_import_health_monitor():
    from health.monitor import HealthMonitor
    assert HealthMonitor is not None

def test_import_discord_bridge():
    from tools.discord_bridge import poll_once, run
    assert callable(poll_once)
```

**Step 2: Remove the test that uses `ContextManager` (old)**

Remove:
```python
def test_channel_context_add_and_retrieve(): ...
def test_channel_context_max_window(): ...
```

These are replaced by `tests/test_context_store.py`.

**Step 3: Run full test suite**

```bash
pytest tests/ -v
```
Expected: all pass (test_smoke.py + test_a0_client.py + test_context_store.py + test_base_agent.py + test_health_monitor.py)

**Step 4: Commit**

```bash
git add tests/test_smoke.py
git commit -m "test: update smoke tests for A0 integration refactor"
```

---

### Task 12: Push to GitHub + wire discord_bridge into bot/client.py on_ready

**Files:**
- Modify: `bot/client.py` (add 2 lines to on_ready)

**Step 1: Wire discord bridge as background task**

In `bot/client.py` inside `on_ready`, after `await monitor.start()`:

```python
# Start conference room bridge
from tools.discord_bridge import run as bridge_run
asyncio.create_task(bridge_run())
```

**Step 2: Final test run**

```bash
cd C:\Users\Troy\openchief
pytest tests/ -v --tb=short
```
Expected: all pass

**Step 3: Push to GitHub**

```bash
git push origin master
```

---

## Manual Steps After Implementation

1. **Fill in `.env` values:**
   - `TROY_DISCORD_ID` — right-click Troy's Discord name → Copy User ID
   - `CHANNEL_AGENTS_CONFERENCE` — right-click #agents-conference → Copy Channel ID
   - `CHANNEL_OPENCHIEF_CONSOLE` — right-click #openchief-console → Copy Channel ID

2. **Fill in `chief-botsuite/.env`:**
   - `TROY_TELEGRAM_ID` — get from @userinfobot on Telegram

3. **Restart both bots:**
   ```bash
   # Python bot
   python main.py

   # Telegram bot
   node "C:\Users\Troy\Chief OS\chief-botsuite\bot.js"
   ```

4. **Test slash command sync:**
   - In Discord, type `/ask hello` — should respond via A0
   - Check `/status` — should show A0 green

5. **Open dashboard:**
   - Serve locally: `python -m http.server 8080 --directory dashboard`
   - Open `http://localhost:8080`

6. **Agent Zero Control Center branding:**
   - In A0 settings → workspace name: "OpenChief Control Center"
   - Add bookmarks: Portfolio Manager, Conference Room

---

## Verification Checklist

```bash
# All tests pass
pytest tests/ -v

# A0 is reachable
curl http://localhost:50001/health

# SQLite context DB exists
ls "C:\Users\Troy\openchief\data\contexts.db"

# Discord bridge writes log
python -c "import asyncio; from tools.discord_bridge import poll_once; asyncio.run(poll_once())"
ls "C:\Users\Troy\openchief\dashboard\data\conference_log.json"
```
