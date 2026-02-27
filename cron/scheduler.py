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


def setup_scheduler(bot) -> AsyncIOScheduler:
    """Configure and return the APScheduler instance. All times UTC."""
    scheduler = AsyncIOScheduler(timezone="UTC")

    scheduler.add_job(job_analytics,  CronTrigger(hour=1,  minute=0),  args=[bot], id="analytics")
    scheduler.add_job(job_monitoring, CronTrigger(hour=1,  minute=15), args=[bot], id="monitoring")
    scheduler.add_job(job_crm_sync,   CronTrigger(hour=2,  minute=0),  args=[bot], id="crm_sync")
    scheduler.add_job(job_treasury,   CronTrigger(hour=3,  minute=0),  args=[bot], id="treasury")
    scheduler.add_job(job_marketplace,CronTrigger(hour=4,  minute=0),  args=[bot], id="marketplace")
    scheduler.add_job(job_portfolio,  CronTrigger(hour=5,  minute=0),  args=[bot], id="portfolio")
    scheduler.add_job(job_research,   CronTrigger(hour=6,  minute=0),  args=[bot], id="research")
    scheduler.add_job(job_content,    CronTrigger(hour=7,  minute=0),  args=[bot], id="content")
    scheduler.add_job(job_digest,     CronTrigger(hour=8,  minute=0),  args=[bot], id="digest")

    return scheduler
