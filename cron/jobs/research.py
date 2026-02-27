"""6:00 AM — AI research digest compilation."""
from datetime import datetime, timezone
from bot.channels import CHANNELS
from event_logging.event_logger import EventLogger

logger = EventLogger()


async def job_research(bot):
    channel_id = CHANNELS["content_pipeline"] or CHANNELS["daily_digest"]
    channel = bot.get_channel(channel_id)
    if not channel:
        logger.log_event("cron_skip", {"job": "research", "reason": "channel_not_found"})
        return

    logger.log_event("cron_start", {"job": "research"})
    report = (
        f"🔬 **Research Digest** — {datetime.now(timezone.utc).strftime('%Y-%m-%d 06:00 UTC')}\n"
        "```\n"
        "Top Stories       : --\n"
        "Trending Topics   : --\n"
        "Sentiment Score   : --\n"
        "Action Items      : --\n"
        "```\n"
        "_Enable `ENABLE_BROWSER_OPS=true` and set `PERPLEXITY_API_KEY` for live research (Phase 2)._"
    )
    await channel.send(report)
    logger.log_event("cron_complete", {"job": "research"})
