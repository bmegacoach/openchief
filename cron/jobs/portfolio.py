"""5:00 AM — Portfolio performance snapshot."""
from datetime import datetime, timezone
from bot.channels import CHANNELS
from event_logging.event_logger import EventLogger

logger = EventLogger()


async def job_portfolio(bot):
    channel_id = CHANNELS["trading_desk"] or CHANNELS["daily_digest"]
    channel = bot.get_channel(channel_id)
    if not channel:
        logger.log_event("cron_skip", {"job": "portfolio", "reason": "channel_not_found"})
        return

    logger.log_event("cron_start", {"job": "portfolio"})
    report = (
        f"📊 **Portfolio Snapshot** — {datetime.now(timezone.utc).strftime('%Y-%m-%d 05:00 UTC')}\n"
        "```\n"
        "Total Value       : --\n"
        "SOL Holdings      : --\n"
        "GBB Holdings      : --\n"
        "CAMP Holdings     : --\n"
        "24h PnL           : --\n"
        "```\n"
        "_Connect wallet address via `WALLET_ADDRESS` in `.env` for live data (Phase 2)._"
    )
    await channel.send(report)
    logger.log_event("cron_complete", {"job": "portfolio"})
