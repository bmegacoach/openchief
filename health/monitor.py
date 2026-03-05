"""
Async background health loop — runs every CHECK_INTERVAL seconds (default 5 min).
Monitors: A0 liveness, context fill levels, cron health.
Posts hourly status digest to #openchief-console.
"""
import asyncio
import logging
import os
from datetime import datetime, timezone

import agents.a0_client as a0_client
from memory.context_store import all_active, update_health, init_db

log = logging.getLogger(__name__)

FILL_WARN  = 70    # % — silent log warning
FILL_ALERT = 90    # % — post to console channel
FILL_FULL  = 100   # % — auto-compact

CHECK_INTERVAL  = int(os.getenv("HEALTH_CHECK_INTERVAL", "300"))  # 5 min
DIGEST_INTERVAL = 3600   # 1 hour
COMPACT_THRESHOLD = 15   # summarize oldest N messages


class HealthMonitor:
    def __init__(self, bot, console_channel_id: int):
        self.bot = bot
        self.console_channel_id = console_channel_id
        self._last_digest = datetime.now(timezone.utc)
        self._task: asyncio.Task | None = None

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
        alive = await a0_client.ping()
        if not alive:
            await self._console(
                "🔴 **Agent Zero unreachable** — check Mini at `localhost:50001`"
            )
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
            await a0_client.ask_a0(prompt, context_id)
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
        a0_alive = await a0_client.ping()
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
