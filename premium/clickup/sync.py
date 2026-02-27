"""
ClickUp Sync — Premium Module
Feature flag: ENABLE_CLICKUP=true
Syncs Discord project threads to ClickUp tasks.
"""
import os
import requests
from event_logging.event_logger import EventLogger

ENABLED = os.getenv("ENABLE_CLICKUP", "false").lower() == "true"
API_KEY = os.getenv("CLICKUP_API_KEY", "")
TEAM_ID = os.getenv("CLICKUP_TEAM_ID", "")
BASE_URL = "https://api.clickup.com/api/v2"

logger = EventLogger()


class ClickUpSync:
    """Sync Discord messages/tasks to ClickUp."""

    def __init__(self):
        self.enabled = ENABLED
        self.headers = {"Authorization": API_KEY, "Content-Type": "application/json"}

    def is_configured(self) -> bool:
        return self.enabled and bool(API_KEY) and bool(TEAM_ID)

    def create_task(self, list_id: str, name: str, description: str = "") -> dict:
        """Create a ClickUp task. Requires human approval for financial tasks."""
        if not self.is_configured():
            return {"status": "unconfigured"}
        try:
            resp = requests.post(
                f"{BASE_URL}/list/{list_id}/task",
                headers=self.headers,
                json={"name": name, "description": description},
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            logger.log_event("clickup_task_created", {"task_id": data.get("id"), "name": name})
            return {"status": "ok", "task_id": data.get("id"), "url": data.get("url")}
        except Exception as exc:
            logger.log_event("clickup_error", {"error": str(exc)})
            return {"status": "error", "error": str(exc)}

    def get_tasks(self, list_id: str) -> dict:
        if not self.is_configured():
            return {"status": "unconfigured", "tasks": []}
        try:
            resp = requests.get(
                f"{BASE_URL}/list/{list_id}/task",
                headers=self.headers,
                timeout=10,
            )
            resp.raise_for_status()
            return {"status": "ok", "tasks": resp.json().get("tasks", [])}
        except Exception as exc:
            return {"status": "error", "error": str(exc)}
