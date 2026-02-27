import os
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from cron.jobs.analytics import job_analytics
from cron.jobs.monitoring import job_monitoring
from cron.jobs.crm_sync import job_crm_sync
from cron.jobs.treasury import job_treasury
from cron.jobs.marketplace import job_marketplace
from cron.jobs.portfolio import job_portfolio
from cron.jobs.research import job_research
from cron.jobs.content import job_content
from cron.jobs.digest import job_digest

# How often to post the digest (hours). Set via .env DIGEST_INTERVAL_HOURS.
# 24 = once daily at 8AM UTC
# 4  = every 4 hours  (0, 4, 8, 12, 16, 20)
# 6  = every 6 hours  (0, 6, 12, 18)
_DIGEST_HOURS = int(os.getenv("DIGEST_INTERVAL_HOURS", "24"))


def _digest_hour_list(interval: int) -> list:
    """Return list of UTC hours at which to fire the digest job."""
    if interval >= 24:
        return [8]  # classic single daily digest at 8AM UTC
    return list(range(0, 24, interval))


def setup_scheduler(bot) -> AsyncIOScheduler:
    """Configure and return the APScheduler instance. All times UTC."""
    scheduler = AsyncIOScheduler(timezone="UTC")

    # Fixed intel-gathering jobs (1AM-7AM UTC)
    scheduler.add_job(job_analytics,   CronTrigger(hour=1, minute=0),  args=[bot], id="analytics")
    scheduler.add_job(job_monitoring,  CronTrigger(hour=1, minute=15), args=[bot], id="monitoring")
    scheduler.add_job(job_crm_sync,    CronTrigger(hour=2, minute=0),  args=[bot], id="crm_sync")
    scheduler.add_job(job_treasury,    CronTrigger(hour=3, minute=0),  args=[bot], id="treasury")
    scheduler.add_job(job_marketplace, CronTrigger(hour=4, minute=0),  args=[bot], id="marketplace")
    scheduler.add_job(job_portfolio,   CronTrigger(hour=5, minute=0),  args=[bot], id="portfolio")
    scheduler.add_job(job_research,    CronTrigger(hour=6, minute=0),  args=[bot], id="research")
    scheduler.add_job(job_content,     CronTrigger(hour=7, minute=0),  args=[bot], id="content")

    # Configurable digest - controlled by DIGEST_INTERVAL_HOURS
    digest_hours = _digest_hour_list(_DIGEST_HOURS)
    for i, hour in enumerate(digest_hours):
        scheduler.add_job(
            job_digest,
            CronTrigger(hour=hour, minute=0),
            args=[bot],
            id=f"digest_{i}",
        )

    interval_label = f"every {_DIGEST_HOURS}h" if _DIGEST_HOURS < 24 else "daily at 08:00 UTC"
    print(f"[Scheduler] Digest: {interval_label} -> UTC hours {digest_hours}")

    return scheduler
