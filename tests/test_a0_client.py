# tests/test_a0_client.py
import os, asyncio, pytest
os.environ.setdefault("A0_BASE_URL", "http://localhost:50001")
os.environ.setdefault("A0_API_KEY", "")

@pytest.mark.asyncio
async def test_ping_returns_bool():
    """ping() returns True or False — never raises."""
    from agents.a0_client import ping
    result = await ping()
    assert isinstance(result, bool)

@pytest.mark.asyncio
async def test_ask_a0_offline_raises(monkeypatch):
    """ask_a0() raises an exception if A0 is unreachable (bad URL)."""
    monkeypatch.setenv("A0_BASE_URL", "http://localhost:1")
    import importlib, agents.a0_client as mod
    importlib.reload(mod)
    with pytest.raises(Exception):
        await mod.ask_a0("hello", "ctx-test")
    # reload back to good URL
    monkeypatch.setenv("A0_BASE_URL", "http://localhost:50001")
    importlib.reload(mod)

def test_a0_client_imports():
    from agents.a0_client import ask_a0, send_directive, ping
    assert callable(ask_a0) and callable(send_directive) and callable(ping)
