"""4-hour portfolio heartbeat cron job."""
import logging
from tools.portfolio_heartbeat import post_heartbeat

log = logging.getLogger(__name__)


async def job_heartbeat(bot, context_id: str = None):
    """Post portfolio SWOT/WBS report to #openchief-console every 4 hours."""
    log.info("[cron] portfolio heartbeat firing")
    await post_heartbeat(bot)
