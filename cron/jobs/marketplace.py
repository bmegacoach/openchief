"""4:00 AM — CAMP inscription marketplace sweep."""
from datetime import datetime, timezone
from bot.channels import CHANNELS
from event_logging.event_logger import EventLogger

logger = EventLogger()


async def job_marketplace(bot):
    channel_id = CHANNELS["camp_marketplace"] or CHANNELS["daily_digest"]
    channel = bot.get_channel(channel_id)
    if not channel:
        logger.log_event("cron_skip", {"job": "marketplace", "reason": "channel_not_found"})
        return

    logger.log_event("cron_start", {"job": "marketplace"})
    report = (
        f"🏪 **CAMP Marketplace Sweep** — {datetime.now(timezone.utc).strftime('%Y-%m-%d 04:00 UTC')}\n"
        "```\n"
        "Active Listings   : --\n"
        "Floor Price       : --\n"
        "24h Volume        : --\n"
        "Pending Bids      : --\n"
        "```\n"
        "_Add `CAMP_IDL_PROGRAM_ID` to `.env` to enable live data (Phase 2)._"
    )
    await channel.send(report)
    logger.log_event("cron_complete", {"job": "marketplace"})
