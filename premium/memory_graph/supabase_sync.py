"""
Supabase Memory Graph — Premium Module
Feature flag: ENABLE_MEMORY_GRAPH=true
Persists conversation memory and entity relationships to Supabase.
"""
import os
from event_logging.event_logger import EventLogger

ENABLED = os.getenv("ENABLE_MEMORY_GRAPH", "false").lower() == "true"
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

logger = EventLogger()


class SupabaseSync:
    """Persist and retrieve memory from Supabase."""

    def __init__(self):
        self.enabled = ENABLED
        self._client = None

    def _get_client(self):
        if not self.enabled or not SUPABASE_URL or not SUPABASE_KEY:
            return None
        if self._client is None:
            try:
                from supabase import create_client  # type: ignore
                self._client = create_client(SUPABASE_URL, SUPABASE_KEY)
            except ImportError:
                logger.log_event("memory_graph_error", {"error": "supabase package not installed"})
        return self._client

    def is_configured(self) -> bool:
        return self.enabled and bool(SUPABASE_URL) and bool(SUPABASE_KEY)

    def save_memory(self, channel_id: int, role: str, content: str, metadata: dict = None) -> dict:
        client = self._get_client()
        if client is None:
            return {"status": "unconfigured"}
        try:
            row = {
                "channel_id": str(channel_id),
                "role": role,
                "content": content,
                "metadata": metadata or {},
            }
            client.table("memories").insert(row).execute()
            logger.log_event("memory_saved", {"channel_id": channel_id})
            return {"status": "ok"}
        except Exception as exc:
            logger.log_event("memory_error", {"error": str(exc)})
            return {"status": "error", "error": str(exc)}

    def recall(self, channel_id: int, limit: int = 20) -> list:
        client = self._get_client()
        if client is None:
            return []
        try:
            resp = (
                client.table("memories")
                .select("*")
                .eq("channel_id", str(channel_id))
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )
            return resp.data or []
        except Exception as exc:
            logger.log_event("memory_error", {"error": str(exc)})
            return []
