import os
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from memory.context_store import create_ephemeral
from cron.jobs.analytics import job_analytics
from cron.jobs.monitoring import job_monitoring
from cron.jobs.crm_sync import job_crm_sync
from cron.jobs.treasury import job_treasury
from cron.jobs.marketplace import job_marketplace
from cron.jobs.portfolio import job_portfolio
from cron.jobs.research import job_research
from cron.jobs.content import job_content
from cron.jobs.digest import job_digest
from cron.jobs.heartbeat import job_heartbeat

# How often to post the digest (hours). Set via .env DIGEST_INTERVAL_HOURS.
# 24 = once daily at 8AM UTC
# 4  = every 4 hours  (0, 4, 8, 12, 16, 20)
# 6  = every 6 hours  (0, 6, 12, 18)
_DIGEST_HOURS = int(os.getenv("DIGEST_INTERVAL_HOURS", "24"))


def _with_ephemeral(job_fn, label: str):
    """Wrap a cron job to receive a fresh ephemeral context_id each run."""
    async def _wrapped(bot):
        context_id = create_ephemeral(label)
        try:
            await job_fn(bot, context_id=context_id)
        except TypeError:
            # Existing jobs that don't accept context_id yet — call without it
            await job_fn(bot)
    return _wrapped


def _digest_hour_list(interval: int) -> list:
    """Return list of UTC hours at which to fire the digest job."""
    if interval >= 24:
        return [8]  # classic single daily digest at 8AM UTC
    return list(range(0, 24, interval))


def setup_scheduler(bot) -> AsyncIOScheduler:
    """Configure and return the APScheduler instance. All times UTC."""
    scheduler = AsyncIOScheduler(timezone="UTC")

    # Fixed intel-gathering jobs (1AM-7AM UTC)
    scheduler.add_job(
        _with_ephemeral(job_analytics, "analytics"),
        CronTrigger(hour=1, minute=0),
        args=[bot],
        id="analytics",
    )
    scheduler.add_job(
        _with_ephemeral(job_monitoring, "monitoring"),
        CronTrigger(hour=1, minute=15),
        args=[bot],
        id="monitoring",
    )
    scheduler.add_job(
        _with_ephemeral(job_crm_sync, "crm_sync"),
        CronTrigger(hour=2, minute=0),
        args=[bot],
        id="crm_sync",
    )
    scheduler.add_job(
        _with_ephemeral(job_treasury, "treasury"),
        CronTrigger(hour=3, minute=0),
        args=[bot],
        id="treasury",
    )
    scheduler.add_job(
        _with_ephemeral(job_marketplace, "marketplace"),
        CronTrigger(hour=4, minute=0),
        args=[bot],
        id="marketplace",
    )
    scheduler.add_job(
        _with_ephemeral(job_portfolio, "portfolio"),
        CronTrigger(hour=5, minute=0),
        args=[bot],
        id="portfolio",
    )
    scheduler.add_job(
        _with_ephemeral(job_research, "research"),
        CronTrigger(hour=6, minute=0),
        args=[bot],
        id="research",
    )
    scheduler.add_job(
        _with_ephemeral(job_content, "content"),
        CronTrigger(hour=7, minute=0),
        args=[bot],
        id="content",
    )

    # 4-hour portfolio heartbeat fires at :30 past each 4-hour mark (0, 4, 8, 12, 16, 20 UTC)
    for _hb_hour in range(0, 24, 4):
        scheduler.add_job(
            _with_ephemeral(job_heartbeat, f"heartbeat_{_hb_hour}"),
            CronTrigger(hour=_hb_hour, minute=30),
            args=[bot],
            id=f"heartbeat_{_hb_hour}",
        )
    print("[Scheduler] Portfolio heartbeat: every 4h at :30 UTC")

    # Configurable digest - controlled by DIGEST_INTERVAL_HOURS
    digest_hours = _digest_hour_list(_DIGEST_HOURS)
    for i, hour in enumerate(digest_hours):
        scheduler.add_job(
            _with_ephemeral(job_digest, f"digest_{i}"),
            CronTrigger(hour=hour, minute=0),
            args=[bot],
            id=f"digest_{i}",
        )

    interval_label = f"every {_DIGEST_HOURS}h" if _DIGEST_HOURS < 24 else "daily at 08:00 UTC"
    print(f"[Scheduler] Digest: {interval_label} -> UTC hours {digest_hours}")

    return scheduler
