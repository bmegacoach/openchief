# tests/test_context_store.py
import os, asyncio, pytest

@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    """Override CONTEXT_DB_PATH so tests use a temp database."""
    db = tmp_path / "test_contexts.db"
    monkeypatch.setenv("CONTEXT_DB_PATH", str(db))
    return str(db)

@pytest.mark.asyncio
async def test_get_or_create_returns_stable_id(tmp_db):
    import importlib, memory.context_store as mod
    importlib.reload(mod)
    await mod.init_db()
    id1 = await mod.get_or_create("channel-1")
    id2 = await mod.get_or_create("channel-1")
    assert id1 == id2
    assert len(id1) == 36  # UUID4

@pytest.mark.asyncio
async def test_different_channels_get_different_ids(tmp_db):
    import importlib, memory.context_store as mod
    importlib.reload(mod)
    await mod.init_db()
    a = await mod.get_or_create("channel-A")
    b = await mod.get_or_create("channel-B")
    assert a != b

@pytest.mark.asyncio
async def test_all_active_returns_rows(tmp_db):
    import importlib, memory.context_store as mod
    importlib.reload(mod)
    await mod.init_db()
    await mod.get_or_create("chan-1")
    await mod.get_or_create("chan-2")
    rows = await mod.all_active()
    assert len(rows) >= 2

@pytest.mark.asyncio
async def test_delete_context(tmp_db):
    import importlib, memory.context_store as mod
    importlib.reload(mod)
    await mod.init_db()
    await mod.get_or_create("to-delete")
    await mod.delete_context("to-delete")
    rows = await mod.all_active()
    ids = [r["channel_id"] for r in rows]
    assert "to-delete" not in ids

def test_create_ephemeral_is_unique():
    from memory.context_store import create_ephemeral
    a = create_ephemeral("analytics")
    b = create_ephemeral("analytics")
    assert a != b
    assert a.startswith("ephemeral-analytics-")

@pytest.mark.asyncio
async def test_update_health(tmp_db):
    import importlib, memory.context_store as mod
    importlib.reload(mod)
    await mod.init_db()
    await mod.get_or_create("health-test")
    await mod.update_health("health-test", message_count=15, health_pct=42.5)
    rows = await mod.all_active()
    row = next(r for r in rows if r["channel_id"] == "health-test")
    assert row["message_count"] == 15
    assert abs(row["health_pct"] - 42.5) < 0.01
