"""
Main Discord bot client.
- Routes messages to the correct Chief agent based on channel.
- 3-layer security on every inbound message.
- 17 native slash commands.
- Master Chief directive handler (Troy reply-to-bot).
- HealthMonitor background loop.
"""
import os
import asyncio
import discord
from discord import app_commands
from discord.ext import commands

from agents.project_chief import ProjectChief
from agents.finance_chief import FinanceChief
from agents.trade_chief import TradeChief
from agents.comms_chief import CommsChief
from agents.camp_chief import CampChief
from agents.base_agent import init_store
from agents.a0_client import ask_a0, send_directive
from bot.channels import CHANNELS, CHANNEL_NAMES
from security.layer1_gateway import Layer1Gateway
from security.layer2_injection import Layer2Injection
from security.layer3_data import Layer3Data
from memory.context_store import get_or_create, delete_context, all_active
from health.monitor import HealthMonitor
from cron.scheduler import setup_scheduler
from event_logging.event_logger import EventLogger

logger = EventLogger()

TROY_DISCORD_ID = int(os.getenv("TROY_DISCORD_ID", "0"))


def create_bot() -> commands.Bot:
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True

    bot = commands.Bot(command_prefix="!", intents=intents)

    gw     = Layer1Gateway()
    inj    = Layer2Injection()
    redact = Layer3Data()
    agents: dict = {}

    def _build_agents():
        agents[CHANNELS["project_mgmt"]]     = ProjectChief(bot)
        agents[CHANNELS["treasury"]]         = FinanceChief(bot)
        agents[CHANNELS["trading_desk"]]     = TradeChief(bot)
        agents[CHANNELS["content_pipeline"]] = CommsChief(bot)
        agents[CHANNELS["camp_marketplace"]] = CampChief(bot)

    # ── Lifecycle ────────────────────────────────────────────────────────────

    @bot.event
    async def on_ready():
        await init_store()
        _build_agents()

        console_id = CHANNELS.get("openchief_console", 0)
        monitor = HealthMonitor(bot, console_channel_id=console_id)
        await monitor.start()
        bot._monitor = monitor

        scheduler = setup_scheduler(bot)
        scheduler.start()
        bot._scheduler = scheduler

        try:
            synced = await bot.tree.sync()
            logger.log_event("slash_synced", {"count": len(synced)})
            print(f"[OpenChief] Online as {bot.user} | {len(synced)} slash commands synced")
        except Exception as exc:
            logger.log_event("slash_sync_failed", {"error": str(exc)})
            print(f"[OpenChief] Online as {bot.user} (slash sync failed: {exc})")

        logger.log_event("bot_ready", {"user": str(bot.user), "guilds": len(bot.guilds)})

    # ── Message handler ──────────────────────────────────────────────────────

    @bot.event
    async def on_message(message: discord.Message):
        if message.author == bot.user:
            return

        channel_id = message.channel.id
        content = message.content.strip()
        if not content:
            return

        # ── Master Chief directive detection ───────────────────────────────
        if (message.reference
                and TROY_DISCORD_ID
                and message.author.id == TROY_DISCORD_ID
                and not content.startswith("/")):
            try:
                ref = await message.channel.fetch_message(message.reference.message_id)
                if ref.author == bot.user:
                    rows = await all_active()
                    ctx_ids = [r["a0_context_id"] for r in rows]
                    await send_directive(content, ctx_ids)
                    await message.add_reaction("✅")
                    logger.log_event("master_chief_directive", {
                        "user": str(message.author),
                        "contexts": len(ctx_ids),
                    })
                    return
            except Exception as exc:
                logger.log_event("directive_error", {"error": str(exc)})

        # ── Security layers ─────────────────────────────────────────────────
        if not gw.check_channel_access(channel_id, message.author):
            logger.log_event("security_block", {
                "layer": 1, "channel": channel_id, "user": str(message.author),
            })
            return

        risk = inj.scan(content)
        if risk == "HIGH":
            logger.log_event("security_block", {
                "layer": 2, "risk": risk, "channel": channel_id,
                "user": str(message.author),
            })
            await message.channel.send("⛔ Message blocked: potential injection attempt.")
            return

        safe_content, was_redacted = redact.check_outbound(content)
        if was_redacted:
            logger.log_event("secret_redacted", {
                "channel": channel_id, "user": str(message.author),
            })

        # ── Route to Chief ───────────────────────────────────────────────────
        agent = agents.get(channel_id)
        if agent is None:
            await bot.process_commands(message)
            return

        channel_name = CHANNEL_NAMES.get(channel_id, str(channel_id))
        logger.log_event("message_received", {
            "channel": channel_name, "user": str(message.author),
        })

        async with message.channel.typing():
            try:
                reply = await agent.handle_message(
                    safe_content, message.author.display_name
                )
                safe_reply, _ = redact.check_outbound(reply)
                await agent._send_chunks(message.channel, safe_reply)
            except Exception as exc:
                logger.log_event("agent_error", {
                    "channel": channel_name, "error": str(exc),
                })
                await message.channel.send("⚠️ An error occurred. Please try again.")

        await bot.process_commands(message)

    # ── Slash command helper ─────────────────────────────────────────────────

    async def _slash_dispatch(
        interaction: discord.Interaction,
        prompt: str,
        system_prefix: str = "",
    ):
        """Route a slash command prompt to A0 via the channel's context_id."""
        await interaction.response.defer(thinking=True)
        channel_id = str(interaction.channel_id)
        context_id = await get_or_create(channel_id)
        full_prompt = f"{system_prefix}{prompt}" if system_prefix else prompt
        safe_prompt, _ = redact.check_outbound(full_prompt)
        try:
            reply = await ask_a0(safe_prompt, context_id)
            safe_reply, _ = redact.check_outbound(reply)
            MAX = 1900
            if len(safe_reply) > MAX:
                chunks = [safe_reply[i:i+MAX] for i in range(0, len(safe_reply), MAX)]
                await interaction.followup.send(chunks[0])
                for chunk in chunks[1:]:
                    await interaction.channel.send(chunk)
            else:
                await interaction.followup.send(safe_reply or "(no response)")
        except Exception as exc:
            await interaction.followup.send(f"⚠️ Error: {exc}")

    # ── 17 Slash Commands ────────────────────────────────────────────────────

    @bot.tree.command(name="ask", description="Ask Agent Zero anything")
    @app_commands.describe(question="Your question")
    async def slash_ask(interaction: discord.Interaction, question: str):
        await _slash_dispatch(interaction, question)

    @bot.tree.command(name="plan", description="Create or view the 30–90 day strategic plan")
    @app_commands.describe(goal="Optional goal or focus area")
    async def slash_plan(interaction: discord.Interaction, goal: str = ""):
        await _slash_dispatch(
            interaction,
            goal or "What should we focus on right now?",
            "[CEO lens] Create a strategic 30–90 day plan across all active projects. "
            "Cover milestones, blockers, and resource priorities. ",
        )

    @bot.tree.command(name="today", description="Today's top priorities and focus")
    @app_commands.describe(context="Optional context or constraint")
    async def slash_today(interaction: discord.Interaction, context: str = ""):
        await _slash_dispatch(
            interaction,
            context or "Consider all active projects.",
            "[Chief of Staff lens] Design my focus for today. "
            "List top 3–5 priorities with clear next actions. ",
        )

    @bot.tree.command(name="schedule", description="Show or update the weekly schedule")
    @app_commands.describe(update="Optional schedule update or query")
    async def slash_schedule(interaction: discord.Interaction, update: str = ""):
        await _slash_dispatch(
            interaction,
            update or "Show the current weekly schedule.",
            "[COO lens] Review or update the weekly schedule. "
            "Be specific about time blocks and owners. ",
        )

    @bot.tree.command(name="code", description="Send a coding task to Agent Zero")
    @app_commands.describe(task="Describe the coding task")
    async def slash_code(interaction: discord.Interaction, task: str):
        await _slash_dispatch(
            interaction, task,
            "[CODE TASK - ChiefDev] You are a senior software engineer. "
            "Use filesystem and GitHub MCP tools as needed. Task: ",
        )

    @bot.tree.command(name="review", description="Review a PR or code diff")
    @app_commands.describe(target="PR number, URL, or paste diff")
    async def slash_review(interaction: discord.Interaction, target: str):
        await _slash_dispatch(
            interaction, target,
            "[CODE REVIEW] Review for correctness, security, and style. "
            "List issues by severity. Target: ",
        )

    @bot.tree.command(name="deploy", description="Trigger or check a deployment pipeline")
    @app_commands.describe(target="Project or environment to deploy")
    async def slash_deploy(interaction: discord.Interaction, target: str):
        await _slash_dispatch(
            interaction, target,
            "[CTO lens] Run the deployment pipeline for: ",
        )

    @bot.tree.command(name="market", description="Crypto market summary")
    @app_commands.describe(query="Optional specific asset or question")
    async def slash_market(interaction: discord.Interaction, query: str = ""):
        await _slash_dispatch(
            interaction,
            query or "Give a current crypto market summary with key price levels.",
            "[CFO lens] Provide a concise market summary. ",
        )

    @bot.tree.command(name="portfolio", description="Portfolio status and P&L")
    @app_commands.describe(query="Optional asset or time range")
    async def slash_portfolio(interaction: discord.Interaction, query: str = ""):
        await _slash_dispatch(
            interaction,
            query or "Show current portfolio status and P&L.",
            "[CFO lens] Review portfolio status. ",
        )

    @bot.tree.command(name="trade", description="Execute or review a trade")
    @app_commands.describe(details="Trade details or review request")
    async def slash_trade(interaction: discord.Interaction, details: str):
        await _slash_dispatch(
            interaction, details,
            "[TRADE lens] Analyze or execute: ",
        )

    @bot.tree.command(name="research", description="Deep research on any topic")
    @app_commands.describe(topic="Research topic or question")
    async def slash_research(interaction: discord.Interaction, topic: str):
        await _slash_dispatch(
            interaction, topic,
            "[RESEARCH lens] Conduct thorough research on: ",
        )

    @bot.tree.command(name="summarize", description="Summarize a URL or pasted text")
    @app_commands.describe(content="URL or text to summarize")
    async def slash_summarize(interaction: discord.Interaction, content: str):
        await _slash_dispatch(
            interaction, content,
            "[CMO lens] Provide a concise summary of: ",
        )

    @bot.tree.command(name="brief", description="Morning briefing across all projects")
    async def slash_brief(interaction: discord.Interaction):
        await _slash_dispatch(
            interaction,
            "Generate a morning briefing: key priorities, blockers, wins, and risks "
            "across all active projects. Be concise and actionable.",
            "[MORNING BRIEF] ",
        )

    @bot.tree.command(name="status", description="System health: A0, contexts, crons")
    async def slash_status(interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        from agents.a0_client import ping
        a0_alive = await ping()
        rows = await all_active()
        top = max((r.get("health_pct", 0) for r in rows), default=0)
        lines = [
            "**OpenChief Status**",
            f"Agent Zero: {'🟢 online' if a0_alive else '🔴 offline'}",
            f"Active contexts: {len(rows)}",
            f"Max context fill: {top:.0f}%",
        ]
        await interaction.followup.send("\n".join(lines))

    @bot.tree.command(name="memory", description="Show A0 context stats for this channel")
    async def slash_memory(interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        channel_id = str(interaction.channel_id)
        rows = await all_active()
        match = next((r for r in rows if r["channel_id"] == channel_id), None)
        if match:
            msg = (
                f"**Context:** `{match['a0_context_id']}`\n"
                f"Messages: {match.get('message_count', '?')}\n"
                f"Fill: {match.get('health_pct', 0):.0f}%\n"
                f"Last used: {match.get('last_used', '?')}"
            )
        else:
            msg = "No context yet for this channel."
        await interaction.followup.send(msg)

    @bot.tree.command(name="compact", description="Force context compaction now")
    async def slash_compact(interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        mon = getattr(bot, "_monitor", None)
        if mon is None:
            await interaction.followup.send("⚠️ HealthMonitor not initialized.")
            return
        channel_id = str(interaction.channel_id)
        rows = await all_active()
        match = next((r for r in rows if r["channel_id"] == channel_id), None)
        if match:
            await mon._compact(channel_id, match["a0_context_id"])
            await interaction.followup.send("✅ Context compacted.")
        else:
            await interaction.followup.send("No context to compact for this channel.")

    @bot.tree.command(name="reset", description="Clear context for this channel")
    async def slash_reset(interaction: discord.Interaction):
        channel_id = str(interaction.channel_id)
        await delete_context(channel_id)
        await interaction.response.send_message("🔄 Context cleared. Fresh start.")

    # ── Legacy ! text commands ────────────────────────────────────────────────

    @bot.command(name="digest")
    async def cmd_digest(ctx_cmd):
        from cron.jobs.digest import job_digest
        await ctx_cmd.send("📋 Generating digest…")
        try:
            await job_digest(bot)
        except Exception as exc:
            await ctx_cmd.send(f"⚠️ Digest error: {exc}")

    @bot.command(name="jobs")
    async def cmd_jobs(ctx_cmd):
        sched = getattr(bot, "_scheduler", None)
        if sched is None:
            await ctx_cmd.send("Scheduler not attached.")
            return
        lines = ["**Scheduled Jobs:**"]
        for job in sched.get_jobs():
            nrt = str(job.next_run_time)[:19] if job.next_run_time else "paused"
            lines.append(f"- `{job.id}` next: {nrt} UTC")
        await ctx_cmd.send("\n".join(lines))

    return bot
