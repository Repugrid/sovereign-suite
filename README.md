# Sovereign Suite

**An AI CEO that autonomously builds, deploys, and sells SaaS products.**

No human wrote the code. No human sent the emails. No human deployed the servers.
A Claude-powered CEO agent delegated everything to worker agents — and shipped a real product in 4 hours.

> *"MiroFish raised $4.1M to simulate markets. We spent $10 to build a real business."*

---

## What This Is

Sovereign is an **Autonomous Multi-Agent Corporation (AMAC)** — a CEO agent that:

1. Reads strategic directives from an inbox
2. Delegates tasks to specialized workers (coder, marketer, researcher)
3. Reviews their output and iterates
4. Deploys real products to real servers
5. Sends real outreach emails to real companies
6. Manages its own P&L and budget

**The result:** A working server monitoring product ([Node-Watch](https://repugrid.com/node-watch/)) that collects real metrics from real servers — built entirely by AI agents.

## Live Demo

Node-Watch is running **right now**. Real servers. Real data. Real API.

```bash
# See live servers being monitored
curl https://repugrid.com/api/v1/servers | jq

# Install the agent on your own server (free beta)
curl -sSL https://repugrid.com/install/nodewatch.sh | bash
```

**Live dashboard:** [repugrid.com/node-watch](https://repugrid.com/node-watch/)

## Architecture

```
Board of Directors (you)
        |
   [ CEO Agent ]  ← Claude Sonnet in Docker, 2-min cycles
        |
   ┌────┼────┐
   v    v    v
Coder  Marketer  Researcher   ← Ephemeral Docker containers
   |    |    |
   v    v    v
 Code  Copy  Data   ← Written to shared/results/
        |
   [ Deployment ]  ← CEO deploys via tools
        |
   Live Product    ← Node-Watch API + Dashboard
```

### The Swarm

| Agent | Capabilities | Example Output |
|-------|-------------|----------------|
| **CEO** | Orchestration, delegation, deployment, email | Strategic decisions, budget management |
| **Coder** | File read/write, no internet | FastAPI backend, monitoring agent, dashboards |
| **Marketer** | File read/write, no internet | Landing pages, email templates, ad copy |
| **Researcher** | File read/write + HTTP | Market analysis, lead generation, competitor data |

### What Got Built (by AI, autonomously)

| Component | Lines | Description |
|-----------|-------|-------------|
| `services/nodewatch-api/` | 560 | FastAPI + SQLite metrics API |
| `deployments/install/monitor.py` | 336 | Server monitoring agent (psutil) |
| `deployments/install/nodewatch.sh` | 70 | One-line install script |
| `deployments/node-watch/index.html` | 310 | Live dashboard (Chart.js) |
| `scripts/orchestrator.py` | 620 | CEO agent loop with tool handling |
| `scripts/spawner.py` | 210 | Docker container worker spawner |
| `services/telegram-chat/bot.py` | 280 | Telegram chat bot (Claude backend) |

## How It Works

### 1. CEO Boots Up
```python
# orchestrator.py — the CEO's brain
while True:
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        system=ceo_system_prompt,
        tools=tools,  # read, write, delegate, deploy, email
        messages=messages,
    )
    # CEO decides, acts, delegates, deploys
    handle_tool_calls(response)
    time.sleep(120)  # 2-min cycles
```

### 2. CEO Reads Directive & Delegates
```
DECISION: Build Node-Watch MVP
ACTION: Spawn coder for API + coder for agent in parallel
COST_ESTIMATE: $8
```

### 3. Workers Execute in Isolation
Each worker runs in its own Docker container with:
- A JSON task file describing what to do
- Read/write access to `shared/results/`
- No access to the internet (except researcher)
- Auto-cleanup when done

### 4. CEO Reviews & Deploys
CEO reads worker output, catches bugs (like format mismatches), fixes them, and deploys.

### 5. CEO Sends Outreach
```
Email sent: "Partnership: AI Server Monitoring"
To: info@netcup.de (1/10 today)
```

## Cost Breakdown

| Phase | Cost | Output |
|-------|------|--------|
| Market research | $1.86 | Competitive analysis, pricing data |
| Technical architecture | $2.35 | System design, API spec |
| Landing pages | $1.50 | Marketing copy, HTML |
| MVP code (API + agent) | $4.29 | Working monitoring product |
| Sales outreach | $3.60 | 10 emails, 25 qualified prospects |
| **Total** | **~$15** | **Complete SaaS product, live** |

## Run It Yourself

```bash
git clone https://github.com/Repugrid/sovereign-suite.git
cd sovereign-suite
cp .env.example .env  # Add your ANTHROPIC_API_KEY
docker compose up -d
```

The CEO will boot, read directives from `shared/inbox/`, and start working.

### Write Your Own Directive

```markdown
# shared/inbox/my_directive.md
Build a URL shortener SaaS.
- API: FastAPI, store in SQLite
- Landing page: Tailwind CSS
- Deploy at /shortener/
- Budget: $5 max
```

The CEO will delegate to coders and marketers, review output, and deploy.

## Safety & Budget Controls

- **Hard budget limit** per day (default $5)
- **Anti-polling protection** — max 3 checks per task, then move on
- **Email limit** — max 10 emails/day with mandatory unsubscribe
- **Worker isolation** — containers with 1GB memory limit, no docker socket
- **Telegram notifications** — startup, budget warnings, new customers, emails sent

## What Makes This Different

| | Traditional SaaS | AI-Assisted Dev | **Sovereign (AMAC)** |
|---|---|---|---|
| Who decides? | Human CEO | Human + Copilot | **AI CEO** |
| Who codes? | Human devs | Human + AI | **AI workers** |
| Who deploys? | DevOps team | Human | **AI CEO** |
| Who sells? | Sales team | Human + templates | **AI CEO + workers** |
| Time to ship | Weeks-months | Days | **4 hours** |
| Cost | $10K+ | $1K+ | **$15** |

## License

MIT

## Contact

- **Email:** hello@repugrid.com
- **Live product:** [repugrid.com/node-watch](https://repugrid.com/node-watch/)
- **Telegram:** Talk to the CEO bot directly

---

*Built by AI agents. Deployed by AI agents. This README is the only thing a human wrote.*
