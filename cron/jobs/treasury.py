"""3:00 AM — GoldBackBond rewards calculation and distribution."""
from datetime import datetime, timezone
from bot.channels import CHANNELS
from event_logging.event_logger import EventLogger

logger = EventLogger()


async def job_treasury(bot):
    channel_id = CHANNELS["treasury"] or CHANNELS["daily_digest"]
    channel = bot.get_channel(channel_id)
    if not channel:
        logger.log_event("cron_skip", {"job": "treasury", "reason": "channel_not_found"})
        return

    logger.log_event("cron_start", {"job": "treasury"})
    report = (
        f"🏦 **Treasury Report** — {datetime.now(timezone.utc).strftime('%Y-%m-%d 03:00 UTC')}\n"
        "```\n"
        "USDGB Circulating Supply : --\n"
        "RWA Backing Value        : --\n"
        "Bonus Vault Balance      : --\n"
        "Pending Distributions    : --\n"
        "```\n"
        "_Add `GOLDBACKBOND_PROGRAM_ID` to `.env` to enable live data (Phase 2)._"
    )
    await channel.send(report)
    logger.log_event("cron_complete", {"job": "treasury"})
