# tests/test_base_agent.py
import os, asyncio, pytest
os.environ.setdefault("DISCORD_TOKEN", "test")
os.environ.setdefault("A0_BASE_URL", "http://localhost:50001")

@pytest.fixture
def patched_store(tmp_path, monkeypatch):
    monkeypatch.setenv("CONTEXT_DB_PATH", str(tmp_path / "test.db"))

@pytest.mark.asyncio
async def test_call_llm_routes_to_a0(patched_store, monkeypatch):
    """_call_llm now calls a0_client.ask_a0, not Anthropic SDK."""
    import agents.a0_client as a0mod
    async def fake_ask(prompt, context_id, system_role=""):
        return f"A0 says: {prompt}"
    monkeypatch.setattr(a0mod, "ask_a0", fake_ask)

    from agents.base_agent import BaseAgent, init_store
    await init_store()

    class FakeBot:
        pass

    agent = BaseAgent(FakeBot(), "TestChief", "test_channel", "You are helpful.")
    result = await agent._call_llm("troy", "hello world")
    assert "hello world" in result

@pytest.mark.asyncio
async def test_handle_message_returns_string(patched_store, monkeypatch):
    """handle_message(content, author) returns a string reply."""
    import agents.a0_client as a0mod
    async def fake_ask(prompt, context_id, system_role=""):
        return "This is the reply"
    monkeypatch.setattr(a0mod, "ask_a0", fake_ask)

    from agents.base_agent import BaseAgent, init_store
    await init_store()

    class FakeBot:
        pass

    agent = BaseAgent(FakeBot(), "TestChief", "test_channel", "You are helpful.")
    result = await agent.handle_message("what is 2+2?", "troy")
    assert result == "This is the reply"

def test_base_agent_has_no_anthropic_client():
    """After refactor, BaseAgent.__init__ must not create an Anthropic client."""
    import inspect
    from agents.base_agent import BaseAgent
    src = inspect.getsource(BaseAgent.__init__)
    assert "anthropic.Anthropic" not in src
    assert "Anthropic(" not in src

@pytest.mark.asyncio
async def test_clear_context_removes_from_store(patched_store, monkeypatch):
    """clear_context deletes the context_id from SQLite."""
    import agents.a0_client as a0mod
    async def fake_ask(p, c, system_role=""):
        return "ok"
    monkeypatch.setattr(a0mod, "ask_a0", fake_ask)

    from agents.base_agent import BaseAgent, init_store
    from memory.context_store import all_active
    await init_store()

    class FakeBot:
        pass

    agent = BaseAgent(FakeBot(), "TestChief", "test_channel", "You are helpful.")
    # Create a context by calling _call_llm
    await agent._call_llm("troy", "create context")
    rows_before = await all_active()
    assert any(r["channel_id"] == "test_channel" for r in rows_before)

    await agent.clear_context(0)  # channel_id arg is ignored — uses self.channel_key
    rows_after = await all_active()
    assert not any(r["channel_id"] == "test_channel" for r in rows_after)
