import os
import asyncio
import discord
import anthropic
from event_logging.event_logger import EventLogger


class BaseAgent:
    """
    Base class for all OpenChief agents.
    Handles: LLM calls, message routing, context management, Discord posting.
    """

    MAX_CONTEXT = 20
    MAX_DISCORD_MSG = 1900

    def __init__(self, bot, name: str, channel_key: str, system_prompt: str):
        self.bot = bot
        self.name = name
        self.channel_key = channel_key
        self.system_prompt = system_prompt
        self.logger = EventLogger()
        self.context: list = []

        api_key = os.getenv("ANTHROPIC_API_KEY", "")
        self.llm = anthropic.Anthropic(api_key=api_key) if api_key else None
        self.model = os.getenv("LLM_MODEL", "claude-opus-4-5")

    async def handle_message(self, message: discord.Message, clean_content: str):
        """Entry point: receive a Discord message, respond via LLM."""
        async with message.channel.typing():
            try:
                reply = await self._call_llm(message.author.display_name, clean_content)
                await self._send_chunks(message.channel, reply)
                self.logger.log_event("agent_response", {
                    "agent": self.name,
                    "channel": self.channel_key,
                    "user": str(message.author),
                    "reply_len": len(reply),
                })
            except Exception as e:
                err_msg = f"⚠️ **{self.name}** encountered an error: `{str(e)[:120]}`"
                await message.channel.send(err_msg)
                self.logger.log_event("agent_error", {"agent": self.name, "error": str(e)})

    async def _call_llm(self, author: str, content: str) -> str:
        """Call Claude API with sliding context window."""
        if not self.llm:
            return (
                f"🤖 **{self.name}** is online but `ANTHROPIC_API_KEY` is not set. "
                "Add your key to `.env` to enable AI responses."
            )

        self.context.append({"role": "user", "content": f"{author}: {content}"})
        if len(self.context) > self.MAX_CONTEXT:
            self.context = self.context[-self.MAX_CONTEXT:]

        response = self.llm.messages.create(
            model=self.model,
            max_tokens=1024,
            system=self.system_prompt,
            messages=self.context,
        )
        reply = response.content[0].text
        self.context.append({"role": "assistant", "content": reply})
        return reply

    async def _send_chunks(self, channel: discord.abc.Messageable, text: str):
        """Send a long message in safe chunks."""
        if len(text) <= self.MAX_DISCORD_MSG:
            await channel.send(text)
            return
        chunks = [text[i:i+self.MAX_DISCORD_MSG] for i in range(0, len(text), self.MAX_DISCORD_MSG)]
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

    def clear_context(self):
        self.context = []
        self.logger.log_event("context_cleared", {"agent": self.name})
