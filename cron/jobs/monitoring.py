"""1:15 AM — X/Twitter competitor monitoring."""
from datetime import datetime, timezone
from bot.channels import CHANNELS
from event_logging.event_logger import EventLogger

logger = EventLogger()


async def job_monitoring(bot):
    channel_id = CHANNELS["alerts"] or CHANNELS["daily_digest"]
    channel = bot.get_channel(channel_id)
    if not channel:
        logger.log_event("cron_skip", {"job": "monitoring", "reason": "channel_not_found"})
        return

    logger.log_event("cron_start", {"job": "monitoring"})
    report = (
        f"🐦 **X/Twitter Competitor Monitor** — {datetime.now(timezone.utc).strftime('%Y-%m-%d 01:15 UTC')}\n"
        "_Add `X_API_BEARER_TOKEN` to `.env` to enable live monitoring (Phase 3)._"
    )
    await channel.send(report)
    logger.log_event("cron_complete", {"job": "monitoring"})
