"""
Per-channel context buffer and memory management.
Each Discord channel gets its own context window and metadata.
"""
from datetime import datetime, timezone


class ChannelContext:
    """Manages context and memory for a single Discord channel."""

    def __init__(self, channel_id: int, channel_name: str = "", max_messages: int = 50):
        self.channel_id = channel_id
        self.channel_name = channel_name
        self.max_messages = max_messages
        self.messages: list = []
        self.pinned_docs: list = []
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.last_pruned = None

    def add_message(self, role: str, content: str, author: str = ""):
        self.messages.append({
            "role": role,
            "content": content,
            "author": author,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        self._auto_prune()

    def _auto_prune(self) -> int:
        if len(self.messages) > self.max_messages:
            removed = len(self.messages) - self.max_messages
            self.messages = self.messages[-self.max_messages:]
            self.last_pruned = datetime.now(timezone.utc).isoformat()
            return removed
        return 0

    def get_recent(self, n: int = 10) -> list:
        return self.messages[-n:]

    def get_utilization(self) -> dict:
        return {
            "channel_id": self.channel_id,
            "channel_name": self.channel_name,
            "messages_stored": len(self.messages),
            "max_messages": self.max_messages,
            "utilization_pct": round(len(self.messages) / self.max_messages * 100, 1),
            "last_pruned": self.last_pruned,
        }

    def pin_doc(self, doc: str):
        if doc not in self.pinned_docs:
            self.pinned_docs.append(doc)

    def clear(self):
        self.messages = []
        self.last_pruned = datetime.now(timezone.utc).isoformat()


class ContextManager:
    """Manages context buffers for all channels."""

    def __init__(self):
        self._channels: dict = {}

    def get_or_create(self, channel_id: int, channel_name: str = "") -> ChannelContext:
        if channel_id not in self._channels:
            self._channels[channel_id] = ChannelContext(channel_id, channel_name)
        return self._channels[channel_id]

    def status_all(self) -> list:
        return [ctx.get_utilization() for ctx in self._channels.values()]

    def prune_all(self) -> dict:
        total_pruned = 0
        for ctx in self._channels.values():
            total_pruned += ctx._auto_prune()
        return {"pruned_messages": total_pruned, "channels": len(self._channels)}
