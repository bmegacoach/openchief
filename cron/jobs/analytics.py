"""1:00 AM — Instagram/Facebook analytics collection."""
from datetime import datetime, timezone
from bot.channels import CHANNELS
from event_logging.event_logger import EventLogger

logger = EventLogger()


async def job_analytics(bot):
    channel_id = CHANNELS["daily_digest"]
    channel = bot.get_channel(channel_id)
    if not channel:
        logger.log_event("cron_skip", {"job": "analytics", "reason": "channel_not_found"})
        return

    logger.log_event("cron_start", {"job": "analytics"})
    report = (
        f"📊 **Social Analytics Report** — {datetime.now(timezone.utc).strftime('%Y-%m-%d 01:00 UTC')}\n"
        "```\n"
        "Platform     | Reach    | Engagement | Followers Δ\n"
        "-------------|----------|------------|------------\n"
        "Instagram    | --       | --         | --\n"
        "Facebook     | --       | --         | --\n"
        "```\n"
        "_Add `INSTAGRAM_API_KEY` to `.env` to enable live data (Phase 3)._"
    )
    await channel.send(report)
    logger.log_event("cron_complete", {"job": "analytics"})
