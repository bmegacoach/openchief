"""
Main Discord bot client.
Routes messages to the correct Chief agent based on channel.
Applies 3-layer security on every inbound message.
"""
import discord
from discord.ext import commands

from agents.project_chief import ProjectChief
from agents.finance_chief import FinanceChief
from agents.trade_chief import TradeChief
from agents.comms_chief import CommsChief
from agents.camp_chief import CampChief
from bot.channels import CHANNELS, CHANNEL_NAMES
from security.layer1_gateway import Layer1Gateway
from security.layer2_injection import Layer2Injection
from security.layer3_data import Layer3Data
from memory.channel_ctx import ContextManager
from cron.scheduler import setup_scheduler
from event_logging.event_logger import EventLogger

logger = EventLogger()


def create_bot() -> commands.Bot:
    """Build and return the configured Discord bot."""
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True

    bot = commands.Bot(command_prefix="!", intents=intents)

    # Security layers
    gw = Layer1Gateway()
    inj = Layer2Injection()
    redact = Layer3Data()

    # Context manager
    ctx_mgr = ContextManager()

    # Chief agents keyed by channel_id
    agents: dict = {}

    def _build_agents():
        agents[CHANNELS["project_mgmt"]]     = ProjectChief()
        agents[CHANNELS["treasury"]]         = FinanceChief()
        agents[CHANNELS["trading_desk"]]     = TradeChief()
        agents[CHANNELS["content_pipeline"]] = CommsChief()
        agents[CHANNELS["camp_marketplace"]] = CampChief()

    @bot.event
    async def on_ready():
        _build_agents()
        scheduler = setup_scheduler(bot)
        scheduler.start()
        bot._scheduler = scheduler  # expose for !jobs command
        logger.log_event("bot_ready", {"user": str(bot.user), "guilds": len(bot.guilds)})
        print(f"[OpenChief] Online as {bot.user}")

    @bot.event
    async def on_message(message: discord.Message):
        # Ignore self
        if message.author == bot.user:
            return

        channel_id = message.channel.id
        content = message.content.strip()

        if not content:
            return

        # Layer 1: Channel ACL
        if not gw.check_channel_access(channel_id, message.author):
            logger.log_event("security_block", {
                "layer": 1, "channel": channel_id,
                "user": str(message.author),
            })
            return

        # Layer 2: Prompt injection scan
        risk = inj.scan(content)
        if risk == "HIGH":
            logger.log_event("security_block", {
                "layer": 2, "risk": risk,
                "channel": channel_id, "user": str(message.author),
            })
            await message.channel.send(
                "⛔ Message blocked: potential injection attempt detected."
            )
            return

        # Layer 3: Redact secrets before they reach the LLM
        safe_content, was_redacted = redact.check_outbound(content)
        if was_redacted:
            logger.log_event("secret_redacted", {
                "channel": channel_id, "user": str(message.author),
            })

        # Store in context window
        channel_name = CHANNEL_NAMES.get(channel_id, str(channel_id))
        ctx = ctx_mgr.get_or_create(channel_id, channel_name)
        ctx.add_message("user", safe_content, author=str(message.author))

        # Route to correct agent
        agent = agents.get(channel_id)
        if agent is None:
            # Unknown channel — no agent assigned, silently ignore
            return

        logger.log_event("message_received", {
            "channel": channel_name, "user": str(message.author),
        })

        try:
            reply = await agent.handle_message(safe_content, str(message.author))
            # Redact agent reply before sending
            safe_reply, _ = redact.check_outbound(reply)
            await agent._send_chunks(message.channel, safe_reply)
            ctx.add_message("assistant", safe_reply)
        except Exception as exc:
            logger.log_event("agent_error", {
                "channel": channel_name, "error": str(exc),
            })
            await message.channel.send("⚠️ An error occurred. Please try again.")

        # Allow built-in commands (e.g. !help) to also fire
        await bot.process_commands(message)

    # ── Built-in slash-style text commands ──────────────────────────────────

    @bot.command(name="status")
    async def cmd_status(ctx_cmd):
        """Return bot health status."""
        hb = gw.check_heartbeat_health()
        mem = ctx_mgr.status_all()
        lines = [f"**OpenChief V2 Status** — {'✅ Healthy' if hb else '⚠️ Heartbeat overdue'}"]
        for ch in mem:
            lines.append(
                f"• #{ch['channel_name']}: {ch['messages_stored']}/{ch['max_messages']} msgs"
            )
        await ctx_cmd.send("\n".join(lines))

    @bot.command(name="clear")
    async def cmd_clear(ctx_cmd):
        """Clear this channel's context window."""
        ch_ctx = ctx_mgr.get_or_create(ctx_cmd.channel.id)
        ch_ctx.clear()
        await ctx_cmd.send("🗑️ Context cleared for this channel.")

    @bot.command(name="digest")
    async def cmd_digest(ctx_cmd):
        """Trigger an on-demand digest report immediately."""
        from cron.jobs.digest import job_digest
        await ctx_cmd.send("📋 Generating digest...")
        try:
            await job_digest(bot)
        except Exception as exc:
            await ctx_cmd.send(f"⚠️ Digest error: {exc}")

    @bot.command(name="jobs")
    async def cmd_jobs(ctx_cmd):
        """List all scheduled cron jobs and their next run times."""
        sched = getattr(bot, "_scheduler", None)
        if sched is None:
            await ctx_cmd.send("Scheduler not attached to bot instance.")
            return
        lines = ["**Scheduled Jobs:**"]
        for job in sched.get_jobs():
            next_run = str(job.next_run_time)[:19] if job.next_run_time else "paused"
            job_line = "- `" + job.id + "` next: " + next_run + " UTC"
            lines.append(job_line)
        await ctx_cmd.send("
".join(lines))

    return bot
