"""
Base class for all OpenChief agents.
All LLM calls now route through Agent Zero via a0_client.
Context is stored in SQLite via context_store (survives restarts).
"""
import asyncio
import discord
from agents import a0_client
from memory.context_store import get_or_create, init_db, delete_context, _db_path
from event_logging.event_logger import EventLogger

_initialized_path = None


async def init_store():
    """Call once at bot startup to ensure SQLite tables exist."""
    global _initialized_path
    current_path = str(_db_path())
    if _initialized_path != current_path:
        await init_db()
        _initialized_path = current_path


class BaseAgent:
    """
    Base class for all OpenChief Chiefs.
    _call_llm routes to Agent Zero; context persists in SQLite.
    """

    MAX_DISCORD_MSG = 1900

    def __init__(self, bot, name: str, channel_key: str, system_prompt: str):
        self.bot = bot
        self.name = name
        self.channel_key = channel_key
        self.system_prompt = system_prompt
        self.logger = EventLogger()

    async def handle_message(self, content: str, author: str) -> str:
        """
        Receive content + author string, route to A0, return reply.
        Sending/redaction is handled by bot/client.py.
        """
        try:
            reply = await self._call_llm(author, content)
            self.logger.log_event("agent_response", {
                "agent": self.name,
                "channel": self.channel_key,
                "user": author,
                "reply_len": len(reply),
            })
            return reply
        except Exception as e:
            self.logger.log_event("agent_error", {"agent": self.name, "error": str(e)})
            raise

    async def _call_llm(self, author: str, content: str) -> str:
        """Route to Agent Zero with this Chief's system prompt and persisted context."""
        context_id = await get_or_create(self.channel_key, context_type="chief")
        prompt = f"{author}: {content}"
        return await a0_client.ask_a0(prompt, context_id, self.system_prompt)

    async def _send_chunks(self, channel: discord.abc.Messageable, text: str):
        """Send a long message in safe chunks <= MAX_DISCORD_MSG chars."""
        if len(text) <= self.MAX_DISCORD_MSG:
            await channel.send(text)
            return
        chunks = [text[i:i + self.MAX_DISCORD_MSG]
                  for i in range(0, len(text), self.MAX_DISCORD_MSG)]
        for chunk in chunks:
            await channel.send(chunk)
            await asyncio.sleep(0.3)

    async def post(self, channel_id: int, message: str):
        """Post a message to any channel by ID (used by cron jobs)."""
        channel = self.bot.get_channel(channel_id)
        if channel:
            await self._send_chunks(channel, message)
        else:
            self.logger.log_event("post_failed", {
                "agent": self.name,
                "channel_id": channel_id,
                "reason": "channel_not_found",
            })

    async def clear_context(self, channel_id: int = 0):
        """Delete A0 context for this Chief (keyed by channel_key)."""
        await delete_context(self.channel_key)
        self.logger.log_event("context_cleared", {"agent": self.name})
