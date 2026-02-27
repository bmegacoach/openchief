"""2:00 AM — CRM sync and contact enrichment."""
from datetime import datetime, timezone
from bot.channels import CHANNELS
from event_logging.event_logger import EventLogger

logger = EventLogger()


async def job_crm_sync(bot):
    channel_id = CHANNELS["project_mgmt"] or CHANNELS["daily_digest"]
    channel = bot.get_channel(channel_id)
    if not channel:
        logger.log_event("cron_skip", {"job": "crm_sync", "reason": "channel_not_found"})
        return

    logger.log_event("cron_start", {"job": "crm_sync"})
    report = (
        f"👥 **CRM Sync** — {datetime.now(timezone.utc).strftime('%Y-%m-%d 02:00 UTC')}\n"
        "_Add `CRM_API_KEY` to `.env` to enable live sync (Phase 3)._"
    )
    await channel.send(report)
    logger.log_event("cron_complete", {"job": "crm_sync"})
