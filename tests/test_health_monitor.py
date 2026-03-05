# tests/test_health_monitor.py
import os, asyncio, pytest
os.environ.setdefault("CONTEXT_DB_PATH", "/tmp/test_monitor.db")

def test_health_monitor_imports():
    from health.monitor import HealthMonitor
    assert HealthMonitor is not None

@pytest.mark.asyncio
async def test_monitor_check_a0_offline(monkeypatch, tmp_path):
    """HealthMonitor posts alert when A0 is unreachable."""
    monkeypatch.setenv("CONTEXT_DB_PATH", str(tmp_path / "test.db"))
    import agents.a0_client as a0mod
    async def fake_ping():
        return False
    monkeypatch.setattr(a0mod, "ping", fake_ping)

    from health.monitor import HealthMonitor
    alerts = []

    class FakeChannel:
        async def send(self, msg):
            alerts.append(msg)

    class FakeBot:
        def get_channel(self, cid):
            return FakeChannel()

    monitor = HealthMonitor(FakeBot(), console_channel_id=999)
    await monitor._check_a0()
    assert any("unreachable" in a.lower() or "offline" in a.lower() for a in alerts)

@pytest.mark.asyncio
async def test_monitor_check_a0_online(monkeypatch, tmp_path):
    """HealthMonitor posts nothing when A0 is reachable."""
    monkeypatch.setenv("CONTEXT_DB_PATH", str(tmp_path / "test.db"))
    import agents.a0_client as a0mod
    async def fake_ping():
        return True
    monkeypatch.setattr(a0mod, "ping", fake_ping)

    from health.monitor import HealthMonitor
    alerts = []

    class FakeChannel:
        async def send(self, msg):
            alerts.append(msg)

    class FakeBot:
        def get_channel(self, cid):
            return FakeChannel()

    monitor = HealthMonitor(FakeBot(), console_channel_id=999)
    await monitor._check_a0()
    assert alerts == []

@pytest.mark.asyncio
async def test_monitor_digest(monkeypatch, tmp_path):
    """_maybe_digest posts a message when DIGEST_INTERVAL has elapsed."""
    monkeypatch.setenv("CONTEXT_DB_PATH", str(tmp_path / "test.db"))
    import agents.a0_client as a0mod
    async def fake_ping():
        return True
    monkeypatch.setattr(a0mod, "ping", fake_ping)

    from health.monitor import HealthMonitor
    from memory.context_store import init_db
    await init_db()

    messages = []

    class FakeChannel:
        async def send(self, msg):
            messages.append(msg)

    class FakeBot:
        def get_channel(self, cid):
            return FakeChannel()

    monitor = HealthMonitor(FakeBot(), console_channel_id=999)
    # Force _last_digest to far in the past so digest fires immediately
    from datetime import datetime, timezone, timedelta
    monitor._last_digest = datetime.now(timezone.utc) - timedelta(hours=2)
    await monitor._maybe_digest()
    assert any("digest" in m.lower() or "openchief" in m.lower() for m in messages)
