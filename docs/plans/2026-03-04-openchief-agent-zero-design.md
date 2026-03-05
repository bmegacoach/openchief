# OpenChief × Agent Zero Integration Design
**Date:** 2026-03-04
**Status:** Approved — ready for implementation
**Scope:** openchief/ + chief-botsuite/

---

## Overview

Replace OpenChief's per-Chief Anthropic API calls with a single Agent Zero routing layer. All intelligence flows through Agent Zero (running at `localhost:50001` on Mini). OpenChief retains its 5-Chief structure and Discord/Telegram surfaces; it becomes a sophisticated *command surface* for A0 rather than a standalone LLM system.

---

## Section 1 — Module Map

### openchief/ changes

| Path | Action | Reason |
|------|--------|--------|
| `agents/a0_client.py` | **NEW** | HTTP bridge to A0 |
| `agents/base_agent.py` | **MODIFY** | swap `_call_llm()` → `a0_client.ask_a0()` |
| `memory/context_store.py` | **NEW** | SQLite persistence of channel→context_id |
| `memory/channel_ctx.py` | **REMOVE** | replaced by context_store + A0 |
| `health/monitor.py` | **NEW** | async background health loop |
| `bot/client.py` | **MODIFY** | 17 slash commands + directive handler |
| `bot/channels.py` | **MODIFY** | add CHANNEL_AGENTS_CONFERENCE |
| `tools/discord_bridge.py` | **NEW** | polls #agents-conference → dashboard JSON |
| `dashboard/index.html` | **NEW** | pixel-camp visual (5 Chief cabins) |
| `dashboard/style.css` | **NEW** | pixel-art theming |
| `cron/scheduler.py` | **MODIFY** | ephemeral context_id per cron job |

### chief-botsuite/ changes

| Path | Action | Reason |
|------|--------|--------|
| `bot.js` | **MODIFY** | migrate context store to same SQLite; add directive detection |

---

## Section 2 — a0_client.py

Single module, three methods. All A0 communication flows here.

```python
# agents/a0_client.py
import os
import httpx

A0_BASE = os.getenv("A0_BASE_URL", "http://localhost:50001")
A0_API_KEY = os.getenv("A0_API_KEY", "")

async def ask_a0(prompt: str, context_id: str, system_role: str = "") -> str:
    """Send prompt to Agent Zero, return response text."""
    payload = {
        "message": prompt,
        "context_id": context_id,
    }
    if system_role:
        payload["system"] = system_role
    headers = {"Authorization": f"Bearer {A0_API_KEY}"} if A0_API_KEY else {}
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(f"{A0_BASE}/agent/dispatch", json=payload, headers=headers)
        resp.raise_for_status()
        return resp.json().get("response", "")

async def send_directive(text: str, context_ids: list[str]) -> None:
    """Inject Master Chief directive into every active A0 context."""
    wrapped = f"[MASTER CHIEF DIRECTIVE]\n{text}"
    for cid in context_ids:
        await ask_a0(wrapped, cid)

async def ping() -> bool:
    """Return True if Agent Zero is reachable."""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{A0_BASE}/health")
            return resp.status_code == 200
    except Exception:
        return False
```

**Environment variables required:**
- `A0_BASE_URL` — default `http://localhost:50001`
- `A0_API_KEY` — empty string disables auth header (Cloudflare tunnel token)

---

## Section 3 — context_store.py

SQLite table: `contexts(channel_id, a0_context_id, context_type, created_at, last_used, message_count, health_pct)`

```python
# memory/context_store.py
import sqlite3, uuid
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "contexts.db"

def _conn():
    DB_PATH.parent.mkdir(exist_ok=True)
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    with _conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS contexts (
                channel_id    TEXT PRIMARY KEY,
                a0_context_id TEXT NOT NULL,
                context_type  TEXT DEFAULT 'channel',
                created_at    TEXT,
                last_used     TEXT,
                message_count INTEGER DEFAULT 0,
                health_pct    REAL    DEFAULT 0.0
            )
        """)

def get_or_create(channel_id: str, context_type: str = "channel") -> str:
    with _conn() as c:
        row = c.execute("SELECT a0_context_id FROM contexts WHERE channel_id=?", (channel_id,)).fetchone()
        if row:
            now = datetime.now(timezone.utc).isoformat()
            c.execute("UPDATE contexts SET last_used=? WHERE channel_id=?", (now, channel_id))
            return row["a0_context_id"]
        cid = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        c.execute("INSERT INTO contexts VALUES (?,?,?,?,?,0,0.0)", (channel_id, cid, context_type, now, now))
        return cid

def update_health(channel_id: str, message_count: int, health_pct: float):
    with _conn() as c:
        c.execute("UPDATE contexts SET message_count=?, health_pct=? WHERE channel_id=?",
                  (message_count, health_pct, channel_id))

def all_active() -> list[sqlite3.Row]:
    """Return all context rows used in the last 7 days."""
    with _conn() as c:
        return c.execute("""
            SELECT * FROM contexts
            WHERE last_used > datetime('now', '-7 days')
        """).fetchall()

def create_ephemeral(label: str) -> str:
    """Create a single-use context_id (cron jobs). Not persisted."""
    return f"ephemeral-{label}-{uuid.uuid4()}"
```

**Replaces:** `BaseAgent.context` list (20 msgs) + `ChannelContext` deque (50 msgs)
**Survives:** bot restarts, crashes, Mini reboots
**Used by:** openchief `base_agent.py`, `health/monitor.py`, `cron/scheduler.py`, and `chief-botsuite/bot.js` (same SQLite file via shared path)

---

## Section 4 — health/monitor.py

Async background loop, runs every 5 minutes. Replaces the heartbeat stub in `Layer1Gateway`.

```python
# health/monitor.py
import asyncio, logging
from datetime import datetime, timezone
from memory.context_store import all_active, update_health, init_db
from agents.a0_client import ask_a0, ping

FILL_WARN  = 70   # % — post warning to #openchief-console
FILL_ALERT = 90   # % — post alert + suggest compaction
FILL_FULL  = 100  # % — trigger compaction automatically

CHECK_INTERVAL = 300        # 5 minutes
DIGEST_INTERVAL = 3600      # 1 hour
COMPACT_THRESHOLD = 15      # summarize oldest N messages when full

log = logging.getLogger("health.monitor")

class HealthMonitor:
    def __init__(self, bot, console_channel_id: int):
        self.bot = bot
        self.console = console_channel_id
        self._last_digest = datetime.now(timezone.utc)

    async def start(self):
        init_db()
        asyncio.create_task(self._loop())

    async def _loop(self):
        while True:
            await self._check_a0()
            await self._check_contexts()
            await self._check_crons()
            await self._maybe_digest()
            await asyncio.sleep(CHECK_INTERVAL)

    async def _check_a0(self):
        alive = await ping()
        if not alive:
            ch = self.bot.get_channel(self.console)
            if ch:
                await ch.send("🔴 **Agent Zero unreachable** — check Mini at `localhost:50001`")

    async def _check_contexts(self):
        for row in all_active():
            # A0 context fill heuristic: query A0 for message_count
            # (A0 exposes this via GET /context/{id}/stats — implement if available,
            #  otherwise estimate from context_store.message_count)
            pct = row["health_pct"]
            ch_id = row["channel_id"]

            if pct >= FILL_FULL:
                await self._compact(ch_id, row["a0_context_id"])
            elif pct >= FILL_ALERT:
                ch = self.bot.get_channel(int(ch_id)) if ch_id.isdigit() else None
                if ch:
                    await ch.send(f"⚠️ Context at {pct:.0f}% — compaction will trigger at 100%")
            elif pct >= FILL_WARN:
                log.warning(f"Context {ch_id} at {pct:.0f}% fill")

    async def _compact(self, channel_id: str, context_id: str):
        """Summarize oldest 15 messages → 1 summary message via A0."""
        prompt = (
            f"[SYSTEM: Context compaction requested]\n"
            f"Summarize the oldest {COMPACT_THRESHOLD} messages in this conversation "
            f"into a single concise summary paragraph. Replace those messages with the summary. "
            f"Preserve all task context, decisions, and action items."
        )
        try:
            await ask_a0(prompt, context_id)
            log.info(f"Compacted context {context_id} for channel {channel_id}")
        except Exception as e:
            log.error(f"Compaction failed for {context_id}: {e}")

    async def _check_crons(self):
        """Verify cron scheduler is alive (heartbeat from scheduler sets flag)."""
        # scheduler.py sets health.monitor.CRON_LAST_BEAT = datetime.now() each cycle
        # Check if it's more than 15 min stale
        pass  # TODO: wire scheduler → monitor heartbeat flag

    async def _maybe_digest(self):
        now = datetime.now(timezone.utc)
        elapsed = (now - self._last_digest).total_seconds()
        if elapsed >= DIGEST_INTERVAL:
            self._last_digest = now
            ch = self.bot.get_channel(self.console)
            if ch:
                rows = all_active()
                lines = [f"**OpenChief Hourly Digest** — {now.strftime('%H:%M UTC')}"]
                a0_alive = await ping()
                lines.append(f"Agent Zero: {'🟢 online' if a0_alive else '🔴 offline'}")
                lines.append(f"Active contexts: {len(rows)}")
                top_fill = max((r['health_pct'] for r in rows), default=0)
                lines.append(f"Max context fill: {top_fill:.0f}%")
                await ch.send("\n".join(lines))
```

**Thresholds:**
| Fill % | Action |
|--------|--------|
| 70% | `log.warning` — silent |
| 90% | Post alert to #openchief-console |
| 100% | Auto-compact: A0 summarizes oldest 15 → 1 |

**Triggered by:** `client.py` on `on_ready` event: `asyncio.create_task(monitor.start())`

---

## Section 5 — Command Registry (17 Commands)

All commands available in both Discord (native slash via `@bot.tree.command`) and Telegram (existing `/cmd` prefix in `bot.js`).

| Command | Description | Routes to |
|---------|-------------|-----------|
| `/ask` | Free-text query to Agent Zero | A0 |
| `/plan` | Create or show today's plan | A0 (ChiefPM) |
| `/today` | Summary of today's schedule/tasks | A0 (ChiefPM) |
| `/schedule` | Show or update weekly schedule | A0 (ChiefPM) |
| `/code` | Code task / PR review | A0 (ChiefDev) |
| `/review` | Review PR or code diff | A0 (ChiefDev) |
| `/deploy` | Trigger deployment pipeline | A0 (ChiefDev) |
| `/market` | Crypto market summary | A0 (ChiefFin) |
| `/portfolio` | Portfolio status + P&L | A0 (ChiefFin) |
| `/trade` | Execute or review trade | A0 (ChiefFin) |
| `/research` | Deep research query | A0 (ChiefAnalyst) |
| `/summarize` | Summarize a URL or pasted text | A0 (ChiefAnalyst) |
| `/brief` | Morning briefing | A0 (all Chiefs) |
| `/status` | System health status | HealthMonitor |
| `/memory` | Show A0 context stats | context_store |
| `/compact` | Force context compaction now | HealthMonitor |
| `/reset` | Clear context for this channel | context_store |

**Discord implementation:** `@bot.tree.command(name="cmd", description="...")` in `bot/client.py`
**Telegram implementation:** Already present in `chief-botsuite/bot.js` — verify all 17 are wired

---

## Section 6 — Master Chief Directive Handler

**Trigger:** Troy replies to any bot message in Discord or Telegram.

**Discord detection (bot/client.py):**
```python
@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return
    # Master Chief detection: Troy replies to a bot message
    if (message.reference
            and message.author.id == TROY_DISCORD_ID
            and not message.content.startswith("/")):
        ref_msg = await message.channel.fetch_message(message.reference.message_id)
        if ref_msg.author == bot.user:
            active = [r["a0_context_id"] for r in all_active()]
            await send_directive(message.content, active)
            await message.add_reaction("✅")
            return
    await bot.process_commands(message)
```

**Telegram detection (bot.js):**
```javascript
bot.on('message', async (ctx) => {
  const msg = ctx.message;
  // Directive: reply from Troy to bot message
  if (msg.reply_to_message?.from?.is_bot && msg.from.id === TROY_TELEGRAM_ID) {
    const activeContexts = await getActiveContextIds();
    for (const ctxId of activeContexts) {
      await sendToA0(`[MASTER CHIEF DIRECTIVE]\n${msg.text}`, ctxId);
    }
    await ctx.reply("✅ Directive broadcast to all active contexts.");
    return;
  }
  // ... normal routing
});
```

**What A0 does with it:** The `[MASTER CHIEF DIRECTIVE]` prefix causes A0 to treat the message as a high-priority correction/override. All subsequent responses in those contexts acknowledge and incorporate the directive.

---

## Section 7 — Conference Room

### Discord: #agents-conference

- Channel constant added to `bot/channels.py`:
  `CHANNEL_AGENTS_CONFERENCE = int(os.getenv("CHANNEL_AGENTS_CONFERENCE", "0"))`
- Chiefs post summaries here after significant task completions (not every message)
- Format: `**[ChiefDev]** Completed PR #42 review — 3 issues flagged, 1 blocker.`

### Dashboard: dashboard/index.html

Pixel-camp visual. 5 Chief cabins (ChiefPM, ChiefDev, ChiefFin, ChiefAnalyst, ChiefOps), status light per cabin (🟢 active last 5 min / 🟡 idle / 🔴 offline / ⚫ disabled), scrollable conference log fed from `dashboard/data/conference_log.json`.

`tools/discord_bridge.py` polls #agents-conference every 60s via Discord HTTP API and writes the JSON file. No additional deps — pure `httpx` + `asyncio`.

**Links embedded in A0 Control Center:**
- Portfolio Manager: `http://localhost:PORT/portfolio` (Moltworker)
- Conference Room: `http://localhost:PORT/dashboard` (local static server)

---

## Section 8 — OpenChief Control Center (A0 UI)

Manual configuration in Agent Zero settings after bot is running:

| Setting | Value |
|---------|-------|
| Workspace name | OpenChief Control Center |
| System prompt prefix | "You are Agent Zero, the AI core of the OpenChief system. Troy Joyner (Master Chief) is the operator. Chiefs (PM, Dev, Fin, Analyst, Ops) route tasks to you. Respond with precision." |
| Quick links | Portfolio Manager, Conference Room |
| HTTP/MCP API | Enabled, Cloudflare tunnel URL |

---

## Section 9 — Zeroclaw Compatibility

All integration points are environment-variable driven and interface-based for future wrapping:

| Module | Swap point |
|--------|-----------|
| `a0_client.py` | `A0_BASE_URL` env var — change to any LLM backend |
| `context_store.py` | `DB_PATH` env var — swap to Postgres/Redis adapter |
| `health/monitor.py` | `CHECK_INTERVAL`, `COMPACT_THRESHOLD` env vars |
| `bot/client.py` | `DISCORD_TOKEN` env var — swap to any Discord-compatible bot |
| `bot.js` | `TELEGRAM_TOKEN` env var — swap to any messaging surface |

Zeroclaw wrapper will set all env vars via its own `.env` injection and expose `openchief/` as a drop-in module.

---

## Implementation Order

1. `agents/a0_client.py` — foundation, everything depends on this
2. `memory/context_store.py` — persistence layer
3. `agents/base_agent.py` — swap `_call_llm()` (removes `memory/channel_ctx.py`)
4. `health/monitor.py` — background health loop
5. `bot/client.py` — 17 slash commands + directive handler
6. `bot/channels.py` — add CHANNEL_AGENTS_CONFERENCE
7. `tools/discord_bridge.py` + `dashboard/index.html` — conference room
8. `cron/scheduler.py` — ephemeral context per job
9. `chief-botsuite/bot.js` — unify to same SQLite store + directive detection
10. Integration test: verify all 17 commands round-trip through A0, verify health digest fires

---

## Security Notes

- A0 API key in `.env` — never commit; add `data/contexts.db` to `.gitignore`
- Master Chief TROY_DISCORD_ID and TROY_TELEGRAM_ID hardcoded env vars — no spoofing
- Directive injection only fires on Troy's user ID reply-to-bot; no other trigger
- Cloudflare tunnel provides HTTPS + auth header to A0 (no open port on Mini)
