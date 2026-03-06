"""
Generates the 4-hour portfolio heartbeat report.
Reads QUEUE.md from the Chief OS monorepo and posts SWOT/WBS to Discord.
"""
import os
import re
import logging
import subprocess
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)

CHIEF_OS_PATH = Path(os.getenv(
    "CHIEF_OS_PATH",
    str(Path(__file__).parent.parent.parent / "Chief OS")
))
QUEUE_PATH = CHIEF_OS_PATH / "QUEUE.md"


def _pull_queue_repo() -> None:
    """git pull on the chief-system repo so heartbeat always reads live QUEUE.md."""
    try:
        result = subprocess.run(
            ["git", "pull", "--ff-only", "origin", "main"],
            cwd=CHIEF_OS_PATH,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            log.info("[heartbeat] git pull OK: %s", result.stdout.strip().splitlines()[-1])
        else:
            log.warning("[heartbeat] git pull failed: %s", result.stderr.strip())
    except Exception as exc:
        log.warning("[heartbeat] git pull error: %s", exc)


def _read_queue() -> str:
    _pull_queue_repo()
    if not QUEUE_PATH.exists():
        log.warning("QUEUE.md not found at %s", QUEUE_PATH)
        return ""
    return QUEUE_PATH.read_text(encoding="utf-8")


def parse_queue_stats(content: str) -> dict:
    """Count tasks by priority and status."""
    stats = {
        "p1_total": 0, "p2_total": 0, "p3_total": 0,
        "claimed": 0, "review": 0, "todo": 0, "done": 0,
        "p1_tasks": [], "p2_tasks": [], "p3_tasks": [],
        "review_tasks": [],
    }
    blocks = re.split(r"\n---\n", content)
    for block in blocks:
        header = re.search(r"##\s+([🔴🟡🟢])\s+(P\d)\s+—\s+([\w-]+)\s+\|\s+(.+)", block)
        if not header:
            continue
        emoji, priority, slug, project = header.groups()
        status_m = re.search(r">\s+Status:\s+(.+)", block)
        status = status_m.group(1).strip().lower() if status_m else "todo"

        p_key = {"P1": "p1", "P2": "p2", "P3": "p3"}.get(priority, "p3")
        stats[f"{p_key}_total"] += 1
        stats[f"{p_key}_tasks"].append(f"`{slug}` ({project.strip()})")

        if "claimed" in status:
            stats["claimed"] += 1
        elif "review" in status:
            stats["review"] += 1
            stats["review_tasks"].append(slug)
        elif "done" in status:
            stats["done"] += 1
        else:
            stats["todo"] += 1

    return stats


def format_heartbeat_report(stats: dict, queue_content: str = "") -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    p1_list = " • ".join(stats["p1_tasks"]) or "none"
    p2_list = " • ".join(stats["p2_tasks"]) or "none"
    p3_list = f"{len(stats['p3_tasks'])} queued" if stats["p3_tasks"] else "none"
    review_list = "\n".join(f"  - `{t}`" for t in stats["review_tasks"]) or "  none"
    pending_count = len(stats["review_tasks"])

    report = f"""📊 **PORTFOLIO HEARTBEAT** — {now}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**MASTER WORK BREAKDOWN**
🔴 P1 ({stats['p1_total']} total): {p1_list}
🟡 P2 ({stats['p2_total']} total): {p2_list}
🟢 P3: {p3_list}
📊 Active: {stats['claimed']} claimed | {stats['todo']} todo | {stats['review']} awaiting review

**SWOT ANALYSIS**
💪 Strengths:     Multi-agent fleet active, shared queue operational
⚠️  Weaknesses:   Review tasks blocking P1 progress
🚀 Opportunities: {stats['todo']} unstarted tasks ready for pickup
🔴 Threats:       Context drift if review tasks age >24h

**DEPENDENCIES & RISKS**
🔗 Dependencies:  Review tasks block downstream work
⚡ Risks:         {pending_count} task(s) awaiting clearance

**SUGGESTED NEXT MOVES**
1. Clear pending review tasks (reply ✅ below)
2. Assign unstarted P1 tasks to available agents
3. Check if any P2 tasks have unblocked dependencies

⏸ **PENDING CLEARANCE** ({pending_count} tasks)
{review_list}
Reply ✅ to resume all | specify task slugs to selectively clear"""
    return report


async def post_heartbeat(bot) -> None:
    """Read queue, generate report, post to #openchief-console."""
    from bot.channels import CHANNELS
    from bot.client import send_to_channel

    content = _read_queue()
    if not content:
        log.warning("[heartbeat] QUEUE.md empty or missing — skipping")
        return

    stats = parse_queue_stats(content)
    report = format_heartbeat_report(stats, queue_content=content)

    channel_id = CHANNELS.get("openchief_console")
    if channel_id:
        await send_to_channel(bot, channel_id, report)
        log.info("[heartbeat] Portfolio report posted to #openchief-console")
    else:
        log.warning("[heartbeat] openchief_console channel not configured")
