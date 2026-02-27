# OpenChief V2 — AI Business Operating System

A multi-agent AI Business Operating System deployed through Discord. Five specialized Chief agents manage your business operations 24/7.

## Architecture

### 8-Channel Discord Layout
| Channel | Agent | Purpose |
|---------|-------|---------|
| `#alerts` | System | Urgent notifications |
| `#trading-desk` | TradeChief | Market analysis & DEX ops |
| `#treasury` | FinanceChief | GoldBackBond & treasury |
| `#camp-marketplace` | CampChief | CAMP NFT marketplace |
| `#content-pipeline` | CommsChief | Content & social strategy |
| `#daily-digest` | System | 8AM automated summary |
| `#project-mgmt` | ProjectChief | Tasks & coordination |
| `#browser-ops` | System | Browser automation (Phase 2) |

### 5 Chief Agents
- **ProjectChief** — Task tracking, sprint planning, coordination
- **FinanceChief** — Treasury, GoldBackBond, financial analysis
- **TradeChief** — Market data, Jupiter DEX, trade signals
- **CommsChief** — Content strategy, social media, campaigns
- **CampChief** — CAMP marketplace, NFT listings, bids

### 3-Layer Security
- **Layer 1** — Channel ACL + bot heartbeat monitoring
- **Layer 2** — Prompt injection scanner (HIGH/MEDIUM/LOW risk)
- **Layer 3** — Outbound secret redaction (API keys, tokens)

### 9 Scheduled Cron Jobs (UTC)
| Time | Job |
|------|-----|
| 1:00 AM | Social analytics |
| 1:15 AM | X/Twitter monitoring |
| 2:00 AM | CRM sync |
| 3:00 AM | GoldBackBond treasury check |
| 4:00 AM | CAMP marketplace scan |
| 5:00 AM | Portfolio snapshot |
| 6:00 AM | Research digest |
| 7:00 AM | Content pipeline |
| 8:00 AM | Daily digest (all channels) |

---

## Quick Start

### 1. Prerequisites
- Python 3.11+ (recommended; 3.14 has `supabase` wheel issues — non-blocking)
- Discord bot token with **Message Content Intent** enabled
- Anthropic API key

### 2. Clone & Install
```bash
git clone https://github.com/bmegacoach/openchief.git
cd openchief
pip install -r requirements.txt
```

### 3. Configure Environment
```bash
cp .env.example .env
# Edit .env with your values
```

Required:
```env
DISCORD_TOKEN=your_discord_bot_token
ANTHROPIC_API_KEY=your_anthropic_key
DISCORD_GUILD_ID=your_server_id
```

### 4. Add Discord Channel IDs
Enable **Developer Mode** in Discord (Settings → Advanced → Developer Mode).
Right-click each channel → **Copy Channel ID** → paste into `.env`.

### 5. Run
```bash
python main.py
```

---

## Environment Variables

### Required
| Variable | Description |
|----------|-------------|
| `DISCORD_TOKEN` | Discord bot token |
| `ANTHROPIC_API_KEY` | Claude API key |
| `DISCORD_GUILD_ID` | Your Discord server ID |

### Channel IDs (Required for agent routing)
| Variable | Channel |
|----------|---------|
| `CHANNEL_ALERTS` | #alerts |
| `CHANNEL_TRADING_DESK` | #trading-desk |
| `CHANNEL_TREASURY` | #treasury |
| `CHANNEL_CAMP_MARKETPLACE` | #camp-marketplace |
| `CHANNEL_CONTENT_PIPELINE` | #content-pipeline |
| `CHANNEL_DAILY_DIGEST` | #daily-digest |
| `CHANNEL_PROJECT_MGMT` | #project-mgmt |
| `CHANNEL_BROWSER_OPS` | #browser-ops |

### Premium Modules (Optional, default off)
| Variable | Default | Description |
|----------|---------|-------------|
| `ENABLE_CLICKUP` | `false` | ClickUp task sync |
| `CLICKUP_API_KEY` | — | ClickUp API key |
| `ENABLE_MEMORY_GRAPH` | `false` | Supabase + Pinecone memory |
| `SUPABASE_URL` | — | Supabase project URL |
| `SUPABASE_KEY` | — | Supabase anon key |
| `PINECONE_API_KEY` | — | Pinecone API key |
| `ENABLE_PENTHOUSE_PAPI` | `false` | Content engine |
| `ENABLE_BROWSER_OPS` | `false` | Playwright automation |

---

## Testing
```bash
pytest tests/test_smoke.py -v
```

---

## Project Structure
```
openchief/
├── main.py                    # Entry point
├── requirements.txt
├── .env.example
├── agents/
│   ├── base_agent.py          # BaseAgent (LLM + sliding context + chunking)
│   ├── project_chief.py
│   ├── finance_chief.py
│   ├── trade_chief.py
│   ├── comms_chief.py
│   └── camp_chief.py
├── bot/
│   ├── channels.py            # Channel ID constants from env
│   └── client.py              # Discord bot + 3-layer security routing
├── connectors/
│   ├── goldbackbond.py        # GoldBackBond RWA connector
│   ├── camp.py                # CAMP marketplace connector
│   ├── layerzero.py           # LayerZero bridge connector
│   └── jupiter.py             # Jupiter DEX connector (live quote API)
├── cron/
│   ├── scheduler.py           # APScheduler AsyncIOScheduler setup
│   └── jobs/                  # 9 scheduled jobs (1AM–8AM UTC)
├── logging/
│   └── event_logger.py        # SQLite + JSONL dual-write logger
├── memory/
│   └── channel_ctx.py         # Per-channel sliding context window
├── premium/
│   ├── clickup/sync.py        # ClickUp task sync
│   ├── memory_graph/          # Supabase persist + Pinecone vectors
│   ├── penthouse_papi/        # AI content engine
│   └── browser_ops/           # Playwright + temp site provisioner
├── security/
│   ├── layer1_gateway.py      # Channel ACL + heartbeat
│   ├── layer2_injection.py    # Prompt injection scanner
│   └── layer3_data.py         # Secret redaction
└── tests/
    └── test_smoke.py
```

---

## Phase Roadmap
| Phase | Status | Scope |
|-------|--------|-------|
| **Phase 1** | ✅ Current | Discord bot, 5 agents, 3-layer security, 9 cron jobs, premium stubs |
| **Phase 2** | Planned | Live Web3 data (GBB mint, Jupiter swaps, CAMP bids), memory graph, browser ops |
| **Phase 3** | Planned | ClickUp sync, Penthouse Papi content engine, multi-guild support |

---

## Security Notes
- **Never commit `.env`** — it's in `.gitignore`
- Rotate your Discord bot token if it was ever shared or exposed
- Layer 3 redacts secrets before they reach the LLM
- Layer 2 blocks prompt injection attempts rated HIGH risk
- Layer 1 enforces per-channel access control lists

---

*Built with Python 3.11 + discord.py 2.3 + Anthropic Claude*
