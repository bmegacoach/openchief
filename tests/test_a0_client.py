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
    """ask_a0() raises when A0_BASE_URL points to a non-listening port."""
    # Set env var to bad URL — a0_client reads it fresh on each call
    monkeypatch.setenv("A0_BASE_URL", "http://localhost:1")
    from agents.a0_client import ask_a0
    with pytest.raises(Exception):
        await ask_a0("hello", "ctx-test")
    # Restore
    monkeypatch.setenv("A0_BASE_URL", "http://localhost:50001")


@pytest.mark.asyncio
async def test_ask_a0_reads_env_per_call(monkeypatch):
    """ask_a0 must read A0_BASE_URL from os.getenv on each call, not at module load."""
    from agents.a0_client import ask_a0
    # Change URL after import — should take effect without reload
    monkeypatch.setenv("A0_BASE_URL", "http://localhost:1")
    with pytest.raises(Exception):
        await ask_a0("test", "ctx-123")
    # Restore
    monkeypatch.setenv("A0_BASE_URL", "http://localhost:50001")

def test_a0_client_imports():
    from agents.a0_client import ask_a0, send_directive, ping
    assert callable(ask_a0) and callable(send_directive) and callable(ping)
