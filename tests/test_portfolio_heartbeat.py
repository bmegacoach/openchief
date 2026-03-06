import pytest
from unittest.mock import patch, MagicMock
from tools.portfolio_heartbeat import (
    parse_queue_stats,
    format_heartbeat_report,
)

SAMPLE_QUEUE = """
## 🔴 P1 — task-one | ProjectA
> Agent: 🔒 a0
> Lane: backend
> Status: claimed

Working on API.

---

## 🟡 P2 — task-two | ProjectB
> Agent: unassigned
> Lane: frontend
> Status: todo

Build dashboard.

---

## 🟢 P3 — task-three | ProjectC
> Agent: unassigned
> Lane: any
> Status: ⏸ REVIEW

Awaiting review.

---

## 🔴 P1 — task-four | ProjectD
> Agent: unassigned
> Lane: strategy
> Status: todo

Architecture review.
"""

def test_parse_queue_stats_counts_correctly():
    stats = parse_queue_stats(SAMPLE_QUEUE)
    assert stats["p1_total"] == 2
    assert stats["p2_total"] == 1
    assert stats["p3_total"] == 1
    assert stats["claimed"] == 1
    assert stats["review"] == 1
    assert stats["todo"] == 2

def test_format_heartbeat_report_contains_required_sections():
    stats = parse_queue_stats(SAMPLE_QUEUE)
    report = format_heartbeat_report(stats, queue_content=SAMPLE_QUEUE)
    assert "PORTFOLIO HEARTBEAT" in report
    assert "MASTER WORK BREAKDOWN" in report
    assert "SWOT" in report
    assert "DEPENDENCIES" in report
    assert "SUGGESTED NEXT MOVES" in report
    assert "PENDING CLEARANCE" in report

def test_format_heartbeat_report_shows_review_tasks():
    stats = parse_queue_stats(SAMPLE_QUEUE)
    report = format_heartbeat_report(stats, queue_content=SAMPLE_QUEUE)
    assert "task-three" in report
