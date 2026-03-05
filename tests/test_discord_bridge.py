# tests/test_discord_bridge.py
import pytest

def test_discord_bridge_imports():
    from tools.discord_bridge import poll_once, run, fetch_recent_messages
    assert callable(poll_once) and callable(run) and callable(fetch_recent_messages)

@pytest.mark.asyncio
async def test_poll_once_no_channel(monkeypatch, tmp_path):
    """poll_once returns 0 when no channel is configured."""
    monkeypatch.setenv("CHANNEL_AGENTS_CONFERENCE", "0")
    import importlib, tools.discord_bridge as mod
    importlib.reload(mod)
    # Override LOG_PATH to temp dir
    mod.LOG_PATH = tmp_path / "dashboard" / "data" / "conference_log.json"
    result = await mod.poll_once()
    assert result == 0
