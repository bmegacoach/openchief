import os
import time
from datetime import datetime, timezone


class Layer1Gateway:
    """
    Layer 1 Security: Network Gateway.
    Controls which agents can respond in which channels.
    Implements heartbeat verification and channel ACL.
    """

    def __init__(self):
        self.security_token = os.getenv("SECURITY_TOKEN", "")
        self.last_heartbeat = time.time()
        self.heartbeat_interval = 7 * 24 * 3600  # weekly

        # channel_id -> list of required role names (empty = open)
        self.channel_acl: dict = {}

        # Sensitive channels: DM-only mode
        self.dm_only_channels: set = set()

        # Agent -> allowed channel IDs mapping
        self.agent_channel_map: dict = {
            "ProjectChief":  [int(os.getenv("CHANNEL_PROJECT_MGMT", "0"))],
            "FinanceChief":  [int(os.getenv("CHANNEL_TREASURY", "0"))],
            "TradeChief":    [int(os.getenv("CHANNEL_TRADING_DESK", "0"))],
            "CommsChief":    [int(os.getenv("CHANNEL_CONTENT_PIPELINE", "0"))],
            "CampChief":     [int(os.getenv("CHANNEL_CAMP_MARKETPLACE", "0"))],
        }

    def check_channel_access(self, channel_id: int, user) -> bool:
        """Returns True if the user is allowed to interact in this channel."""
        required_roles = self.channel_acl.get(channel_id, [])
        if not required_roles:
            return True
        user_role_names = [r.name for r in getattr(user, "roles", [])]
        return any(role in user_role_names for role in required_roles)

    def can_agent_post(self, agent_name: str, channel_id: int) -> bool:
        """Check if a named agent is allowed to post in channel_id."""
        allowed = self.agent_channel_map.get(agent_name, [])
        if not allowed or 0 in allowed:
            return True
        return channel_id in allowed

    def verify_token(self, token: str) -> bool:
        """Validate a security token for HTTP endpoint access."""
        return token == self.security_token and bool(self.security_token)

    def heartbeat(self) -> dict:
        """Record a heartbeat ping. Returns status."""
        self.last_heartbeat = time.time()
        return {
            "status": "alive",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "last_heartbeat": self.last_heartbeat,
        }

    def check_heartbeat_health(self) -> bool:
        """Returns False if heartbeat is overdue (>1 week)."""
        return (time.time() - self.last_heartbeat) < self.heartbeat_interval
