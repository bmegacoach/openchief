import os


def _ch(key: str, default: str = "0") -> int:
    """Safely read a channel ID from env."""
    val = os.getenv(key, default)
    try:
        return int(val)
    except (ValueError, TypeError):
        return 0


# Channel ID map — sourced entirely from .env
CHANNELS = {
    "alerts":           _ch("CHANNEL_ALERTS"),
    "trading_desk":     _ch("CHANNEL_TRADING_DESK"),
    "treasury":         _ch("CHANNEL_TREASURY"),
    "camp_marketplace": _ch("CHANNEL_CAMP_MARKETPLACE"),
    "content_pipeline": _ch("CHANNEL_CONTENT_PIPELINE"),
    "daily_digest":     _ch("CHANNEL_DAILY_DIGEST", "1468062917755801640"),
    "project_mgmt":     _ch("CHANNEL_PROJECT_MGMT"),
    "browser_ops":      _ch("CHANNEL_BROWSER_OPS"),
    "agents_conference":   _ch("CHANNEL_AGENTS_CONFERENCE"),   # Chiefs post summaries here
    "openchief_console":   _ch("CHANNEL_OPENCHIEF_CONSOLE"),   # HealthMonitor alerts here
}

# Reverse map: channel_id -> name (for logging)
CHANNEL_NAMES = {v: k for k, v in CHANNELS.items() if v != 0}
