"""7:00 AM — Content pipeline generation."""
from datetime import datetime, timezone
from bot.channels import CHANNELS
from event_logging.event_logger import EventLogger

logger = EventLogger()


async def job_content(bot):
    channel_id = CHANNELS["content_pipeline"] or CHANNELS["daily_digest"]
    channel = bot.get_channel(channel_id)
    if not channel:
        logger.log_event("cron_skip", {"job": "content", "reason": "channel_not_found"})
        return

    logger.log_event("cron_start", {"job": "content"})
    report = (
        f"✍️ **Content Pipeline** — {datetime.now(timezone.utc).strftime('%Y-%m-%d 07:00 UTC')}\n"
        "```\n"
        "Posts Queued      : --\n"
        "Drafts Ready      : --\n"
        "Scheduled Today   : --\n"
        "Engagement Target : --\n"
        "```\n"
        "_Enable `ENABLE_PENTHOUSE_PAPI=true` for Penthouse Papi content engine (Phase 2)._"
    )
    await channel.send(report)
    logger.log_event("cron_complete", {"job": "content"})
