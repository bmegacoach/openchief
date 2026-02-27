"""8:00 AM — Daily digest summary across all channels."""
from datetime import datetime, timezone
from bot.channels import CHANNELS
from event_logging.event_logger import EventLogger

logger = EventLogger()


async def job_digest(bot):
    channel_id = CHANNELS["daily_digest"]
    channel = bot.get_channel(channel_id)
    if not channel:
        logger.log_event("cron_skip", {"job": "digest", "reason": "channel_not_found"})
        return

    logger.log_event("cron_start", {"job": "digest"})
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    report = (
        f"📋 **Daily Digest** — {now_str}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "**🔴 Alerts:** None\n"
        "**📈 Markets:** Snapshot pending (Phase 2)\n"
        "**🏦 Treasury:** GBB supply sync pending (Phase 2)\n"
        "**🏪 Marketplace:** CAMP listings pending (Phase 2)\n"
        "**📊 Portfolio:** Wallet connect pending (Phase 2)\n"
        "**✍️ Content:** Pipeline sync pending (Phase 2)\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "_Good morning. OpenChief V2 is online. Configure `.env` to unlock live data._"
    )
    await channel.send(report)
    logger.log_event("cron_complete", {"job": "digest"})
