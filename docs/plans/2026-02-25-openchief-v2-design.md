# OpenChief V2 — Design Document
**Date:** 2026-02-25
**Status:** Approved
**Location:** `C:\Users\Troy\openchief\`

---

## 1. Overview

OpenChief is an AI-powered Business Operating System deployed through Discord channels. Five chief AI agents (ProjectChief, FinanceChief, TradeChief, CommsChief, CampChief) handle autonomous operations across business functions. Web3 connectors (GoldBackBond, CAMP, LayerZero) bridge on-chain activity. Premium upgrade modules add ClickUp, memory graph, content engine, and browser automation.

---

## 2. Stack

| Layer | Technology |
|-------|-----------|
| Discord Bot | Python 3.11 + discord.py 2.x |
| Cron Scheduler | APScheduler 3.x |
| Event Logging | SQLite (JSONL sidecar) |
| Browser Ops | Playwright |
| Memory Graph | Supabase + Pinecone |
| Secrets | python-dotenv (.env only) |
| Web3 Connectors | Rust binaries (called via subprocess) |

---

## 3. Discord Configuration

- **Server ID:** `1468061349882892415`
- **Bot Token:** stored in `.env` as `DISCORD_BOT_TOKEN`
- **Client ID:** `1468068014107656455`

### Channel Architecture

| Channel | Purpose | Agent |
|---------|---------|-------|
| `#alerts` | Trending signals, market movements | All agents |
| `#trading-desk` | Trade execution, P&L | TradeChief |
| `#treasury` | GoldBackBond RWA ops | FinanceChief |
| `#camp-marketplace` | Inscription listings, IDL | CampChief |
| `#content-pipeline` | Research → Scripts workflow | CommsChief |
| `#daily-digest` | Morning + 4hr rolling reports | All agents |
| `#project-mgmt` | WBS, sprints, coordination | ProjectChief |
| `#browser-ops` | Agent browser sessions, logs | BrowserAgent |

---

## 4. Project Structure

```
openchief/
├── .env                          # All secrets — never committed
├── .env.example                  # Key names only
├── .gitignore
├── requirements.txt
├── main.py                       # Entry: starts bot + scheduler
│
├── bot/
│   ├── client.py                 # Discord client, intents, on_ready
│   └── channels.py               # Channel ID constants
│
├── agents/
│   ├── base_agent.py             # Shared: LLM call, memory, security hooks
│   ├── project_chief.py          # #project-mgmt
│   ├── finance_chief.py          # #treasury
│   ├── trade_chief.py            # #trading-desk
│   ├── comms_chief.py            # #content-pipeline
│   └── camp_chief.py             # #camp-marketplace
│
├── security/
│   ├── layer1_gateway.py         # Token auth, heartbeat, channel ACL
│   ├── layer2_injection.py       # Prompt injection sanitizer + risk scoring
│   └── layer3_data.py            # Outbound secret redaction
│
├── cron/
│   ├── scheduler.py              # APScheduler bootstrap
│   └── jobs/
│       ├── analytics.py          # 1:00 AM — social analytics
│       ├── monitoring.py         # 1:15 AM — X/Twitter competitor
│       ├── crm_sync.py           # 2:00 AM — CRM sync
│       ├── treasury.py           # 3:00 AM — GoldBackBond rewards
│       ├── marketplace.py        # 4:00 AM — CAMP sweep
│       ├── portfolio.py          # 5:00 AM — portfolio rebalance
│       ├── research.py           # 6:00 AM — stock/crypto report
│       ├── content.py            # 7:00 AM — competitor content
│       └── digest.py             # 8:00 AM — daily digest compile
│
├── connectors/
│   ├── goldbackbond.py           # Wraps Rust binary
│   ├── camp.py                   # Wraps Rust binary
│   ├── layerzero.py              # Wraps Rust binary
│   └── jupiter.py                # DEX trading stubs
│
├── premium/
│   ├── clickup/
│   │   └── sync.py               # Bi-directional ClickUp task sync
│   ├── memory_graph/
│   │   ├── supabase_sync.py      # Notes → Supabase
│   │   └── pinecone_embed.py     # Vectorize → Pinecone
│   ├── penthouse_papi/
│   │   └── content_engine.py     # Ideation→Research→Script workflow
│   └── browser_ops/
│       ├── playwright_agent.py   # Headless browser automation
│       └── temp_sites.py         # Temp site spin-up/teardown
│
├── memory/
│   └── channel_ctx.py            # Per-channel context buffer + pruning
│
├── logging/
│   └── event_logger.py           # JSONL + SQLite structured logging
│
└── docs/
    └── plans/
        └── 2026-02-25-openchief-v2-design.md
```

---

## 5. Security Architecture (Three Layers)

### Layer 1 — Network Gateway (`security/layer1_gateway.py`)
- Token-based auth on all HTTP endpoints
- Channel ACL: maps each channel to permitted agents
- DM-only mode for sensitive operations
- Weekly heartbeat verification

### Layer 2 — Prompt Injection Defense (`security/layer2_injection.py`)
- Deterministic regex sanitizer scans all incoming messages
- Risk scoring: `LOW` / `MEDIUM` / `HIGH`
- HIGH-risk actions pause and request explicit human approval via Discord reaction
- Injection pattern library (prompt override, role confusion, jailbreak markers)

### Layer 3 — Data Protection (`security/layer3_data.py`)
- Regex-based outbound redaction: strips API keys, tokens, passwords before LLM sees content
- Pre-commit hook config included
- Nightly security council cron scans logs for anomalies

---

## 6. Cron Schedule

| Time | Job | Channel |
|------|-----|---------|
| 1:00 AM | Instagram/Facebook analytics | #daily-digest |
| 1:15 AM | X/Twitter competitor monitoring | #alerts |
| 2:00 AM | CRM sync + contact enrichment | #project-mgmt |
| 3:00 AM | GoldBackBond rewards calculation | #treasury |
| 4:00 AM | CAMP inscription sweep | #camp-marketplace |
| 5:00 AM | Portfolio rebalancing analysis | #trading-desk |
| 6:00 AM | Stock/crypto research report | #trading-desk |
| 7:00 AM | Competitor content analysis | #content-pipeline |
| 8:00 AM | Daily digest compilation | #daily-digest |

---

## 7. Agent Definitions

| Agent | Channel | Primary Model | Functions |
|-------|---------|--------------|-----------|
| ProjectChief | #project-mgmt | Claude / GPT-4 | WBS, milestones, task routing |
| FinanceChief | #treasury | Claude / GPT-4 | RWA ops, yield, rewards |
| TradeChief | #trading-desk | Claude / GPT-4 | DEX trading, risk, P&L |
| CommsChief | #content-pipeline | Gemini Flash | Scripts, research, content |
| CampChief | #camp-marketplace | Kimi / Minimax | Marketplace, IDL distributions |

All agents respond to `@ChiefOS` mentions in their channel. Each has a channel-scoped system prompt.

---

## 8. Premium Modules (Feature Flags)

All premium modules are scaffolded but disabled by default. Enable via `.env`:

```env
ENABLE_CLICKUP=false
ENABLE_MEMORY_GRAPH=false
ENABLE_PENTHOUSE_PAPI=false
ENABLE_BROWSER_OPS=false
```

---

## 9. Environment Variables

```env
# Discord
DISCORD_BOT_TOKEN=
DISCORD_SERVER_ID=1468061349882892415
DISCORD_DAILY_REPORTS_CHANNEL=1468062917755801640

# LLM Providers
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
GOOGLE_API_KEY=

# Web3
SOLANA_RPC_URL=
GOLDBACKBOND_PROGRAM_ID=
CAMP_IDL_PROGRAM_ID=
LAYERZERO_ENDPOINT=

# Premium: ClickUp
ENABLE_CLICKUP=false
CLICKUP_API_KEY=

# Premium: Memory Graph
ENABLE_MEMORY_GRAPH=false
SUPABASE_URL=
SUPABASE_KEY=
PINECONE_API_KEY=
PINECONE_INDEX=

# Premium: Browser Ops
ENABLE_BROWSER_OPS=false

# Security
SECURITY_TOKEN=
LOG_DB_PATH=./logs/openchief.db
```

---

## 10. How to Run

```bash
cd C:\Users\Troy\openchief
pip install -r requirements.txt
cp .env.example .env   # fill in keys
python main.py
```

---

## 11. Phase Mapping

| Phase | Scope | Timeline |
|-------|-------|---------|
| Phase 1 (this build) | Discord bot, 5 agents, security, cron, premium stubs | Week 1 |
| Phase 2 | GoldBackBond + CAMP + LayerZero + Jupiter live | Weeks 2–3 |
| Phase 3 | Autonomy, content pipeline, memory pruning, self-healing | Week 4 |
| Phase 4 | Premium modules live, cost tracking, advanced security | Weeks 5+ |
