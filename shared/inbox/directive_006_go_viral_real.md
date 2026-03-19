# BOARD DIRECTIVE #006 — Go Viral (FOR REAL this time)

**Date:** 2026-03-19
**Priority:** HIGH
**From:** Board of Directors
**Budget:** $3.00 max

---

## Context

Last time you "went viral" you spawned 15 marketer workers that wrote content to local files. Nothing was actually posted anywhere. You burned $10 and reached 0 humans.

This time: USE YOUR GITHUB TOOLS to actually post. You have working tools: `github_create_release` and `github_create_discussion`. USE THEM.

## Task 1: Create GitHub Release v0.1.0-beta

Use `github_create_release` with:
- **tag:** `v0.1.0-beta`
- **name:** `Node-Watch MVP — Built entirely by AI agents in 4 hours`
- **body:** Write an honest, short release note. Include:
  - What works: monitoring agent, metrics API, live dashboard, one-line installer
  - Real cost: ~$57 total ($15 development + $42 from a polling bug the CEO caused)
  - Architecture: CEO agent orchestrates coder/marketer/researcher workers in Docker
  - Install command: `curl -sSL http://37.27.189.23:9080/install/nodewatch.sh | bash`
  - Link to live dashboard: http://37.27.189.23:9080/node-watch-dashboard/
  - Keep it under 300 words. No corporate speak. Be real.

## Task 2: Post GitHub Discussion

Use `github_create_discussion` with:
- **category:** `Show and tell`
- **title:** `I built an AI CEO that manages a team of AI workers to build and sell real software`
- **body:** Write the REAL story. Include:
  - What Sovereign is: autonomous multi-agent corporation
  - The CEO runs 24/7 in Docker, spawns workers, makes decisions, tracks P&L
  - Day 1 results: built Node-Watch from scratch (working product, not a prototype)
  - The $42 polling bug — CEO kept checking task status in a loop, burned budget
  - Budget system: $5/day hard cap, Telegram alerts to human board
  - What's next: getting first 10 external servers monitored
  - End with: "The CEO agent wrote this product. I'm the human board member. AMA."
  - Keep it authentic. The failures make the story interesting.

## Task 3: Create 3 GitHub Issues

Use `github_post_comment` is not right for this — instead use `fetch_url` to POST to the GitHub Issues API:
- URL: `https://api.github.com/repos/Repugrid/sovereign-suite/issues`
- Headers: Authorization token is in your env
- Create these issues:
  1. "Add Prometheus /metrics endpoint" — good first issue, help wanted
  2. "Hetzner Cloud API integration — auto-discover servers" — enhancement
  3. "Webhook alerts (Discord, Slack, Telegram)" — feature request

Each with labels if possible, or at minimum clear descriptions.

## Task 4: Tweet Thread (via @astraeacore)

Use `post_tweet` to post 3-4 tweets. One per cycle — do NOT post all at once.

**Tweet 1 (launch):**
"We built an autonomous AI company. A CEO agent (Claude) runs 24/7, spawns worker agents, builds real products, tracks its own P&L. Today it shipped a server monitoring tool from scratch. Total cost: $57. The $42 was a bug where the CEO got stuck in a loop. 🧵"

**Tweet 2 (product):**
"The product it built: Node-Watch — lightweight server monitoring. One-line install, real-time metrics, auto-alerts. Built entirely by AI agents in 4 hours. Live demo: [dashboard link]. Install: curl -sSL http://37.27.189.23:9080/install/nodewatch.sh | bash"

**Tweet 3 (architecture):**
"Architecture: CEO agent in Docker orchestrates coder/marketer/researcher workers. Each worker is a separate container. CEO makes all decisions, delegates tasks, reviews code, deploys. Budget: $5/day hard cap. Telegram alerts to human board. github.com/Repugrid/sovereign-suite"

**Tweet 4 (CTA):**
"This is open source. The CEO agent's entire decision history is in the repo. Want to see an AI company run itself? Star the repo, try the install, or just read the CEO's logs. github.com/Repugrid/sovereign-suite"

Adapt the text — keep it authentic, max 280 chars each. Post one tweet, then continue with next task. Come back to post the next tweet in a later cycle.

## Rules
- Do NOT spawn any workers. Do this yourself with your tools.
- Do NOT write content to files first. Post directly via API.
- Total budget for this directive: $3 max (it's just a few API calls)
- After posting, fetch the URLs and log them to shared/results/viral_posts.md
- Send the URLs to Telegram so the Board can see and share them
- Execute in order: GitHub Release → GitHub Discussion → GitHub Issues → Tweets
- One tweet per cycle to look natural, not like a bot dump
