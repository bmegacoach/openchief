"""
Polls Discord #agents-conference every POLL_INTERVAL seconds.
Writes dashboard/data/conference_log.json for the dashboard to consume.
Requires: DISCORD_TOKEN and CHANNEL_AGENTS_CONFERENCE env vars.
"""
import os
import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import aiohttp

log = logging.getLogger(__name__)

DISCORD_TOKEN       = os.getenv("DISCORD_TOKEN", "")
_AGENTS_CONF_ENV    = os.getenv("CHANNEL_AGENTS_CONFERENCE", "0")
AGENTS_CONF_CHANNEL = int(_AGENTS_CONF_ENV) if _AGENTS_CONF_ENV.isdigit() else 0
POLL_INTERVAL       = int(os.getenv("BRIDGE_POLL_INTERVAL", "60"))
MAX_LOG_ENTRIES     = 200
LOG_PATH = Path(__file__).parent.parent / "dashboard" / "data" / "conference_log.json"


def _discord_headers() -> dict:
    return {
        "Authorization": f"Bot {os.getenv('DISCORD_TOKEN', DISCORD_TOKEN)}",
        "Content-Type": "application/json",
    }


async def fetch_recent_messages(limit: int = 20) -> list:
    """Fetch the most recent messages from #agents-conference via Discord REST."""
    if not AGENTS_CONF_CHANNEL:
        log.warning("CHANNEL_AGENTS_CONFERENCE not set — skipping fetch")
        return []
    url = (
        f"https://discord.com/api/v10/channels/{AGENTS_CONF_CHANNEL}"
        f"/messages?limit={limit}"
    )
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                headers=_discord_headers(),
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status != 200:
                    log.warning("Discord API returned %d for channel %d",
                                resp.status, AGENTS_CONF_CHANNEL)
                    return []
                return await resp.json()
    except Exception as exc:
        log.error("fetch_recent_messages error: %s", exc)
        return []


def _load_existing() -> list:
    if LOG_PATH.exists():
        try:
            return json.loads(LOG_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


async def poll_once() -> int:
    """Fetch new messages and append to conference_log.json. Returns count added."""
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    messages = await fetch_recent_messages()
    if not messages:
        return 0
    existing = _load_existing()
    existing_ids = {m["id"] for m in existing}
    new_entries = [
        {
            "id":        m["id"],
            "author":    m["author"]["username"],
            "content":   m["content"][:500],
            "timestamp": m["timestamp"],
        }
        for m in messages
        if m["id"] not in existing_ids
    ]
    if new_entries:
        combined = (new_entries + existing)[:MAX_LOG_ENTRIES]
        LOG_PATH.write_text(
            json.dumps(combined, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        log.info("Added %d new messages to conference log", len(new_entries))
    return len(new_entries)


async def run():
    """Background loop: poll #agents-conference every POLL_INTERVAL seconds."""
    if not AGENTS_CONF_CHANNEL:
        log.warning("CHANNEL_AGENTS_CONFERENCE not set — discord bridge disabled")
        return
    log.info(
        "Discord bridge polling channel %d every %ds",
        AGENTS_CONF_CHANNEL, POLL_INTERVAL,
    )
    while True:
        try:
            await poll_once()
        except Exception as exc:
            log.error("Bridge poll error: %s", exc)
        await asyncio.sleep(POLL_INTERVAL)
