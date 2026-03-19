# BOARD DIRECTIVE #005 — REVENUE ONLY MODE

**Date:** 2026-03-19
**Priority:** CRITICAL
**From:** Board of Directors

---

## Context

You have burned through $15+ in API credits today with ZERO revenue. You spawned 15+ workers producing HackerNews posts, Reddit viral content, Dev.to articles, Discord/Slack posts, newsletter pitches — none of which generated a single Euro.

**This stops now.**

## New Rules (effective immediately)

### 1. NO MORE MARKETING WORKERS
Do NOT spawn marketer or researcher workers. Zero. Every Euro you spend on content is wasted until we have paying customers who came through direct sales.

### 2. ONLY SPEND MONEY ON THINGS THAT DIRECTLY LEAD TO PAYMENT
The only acceptable use of your budget:
- Fix bugs in the Node-Watch product that block a sale
- Build a missing feature that a specific lead requested
- Send a targeted outreach email to a real person (max 3/day)

### 3. OUTREACH = DIRECT SALES ONLY
- Find 3 real Hetzner users (small agencies, SaaS founders, freelance devops)
- Use the researcher to find their REAL email (not info@)
- Write a SHORT personal email (5 lines max) offering Node-Watch for free in exchange for feedback
- Send via Postmark
- That's it. No blog posts. No viral campaigns. No "content marketing".

### 4. MAKE THE PRODUCT ACTUALLY WORK FIRST
Before ANY outreach, verify:
- [ ] Install script works: `curl -sSL http://37.27.189.23:9080/install/nodewatch.sh | bash`
- [ ] Agent reports to API after install
- [ ] Dashboard shows real data at /node-watch-dashboard/
- [ ] Alert emails fire when CPU > 90%

If any of these are broken, fix them FIRST. That is your only job.

### 5. BUDGET DISCIPLINE
- Daily budget: $5.00 (hard cap, persisted to disk)
- Target: spend < $2/day
- Every cycle, state your remaining budget before doing anything
- If budget > 80% spent, STOP and wait for tomorrow

### 6. SUCCESS METRIC
The ONLY metric that matters: **number of servers reporting to our API**.
Currently: 1 (our own). Target: 3 by end of week.

## What NOT To Do
- NO HackerNews posts
- NO Reddit posts
- NO Dev.to articles
- NO Discord/Slack outreach
- NO newsletter pitches
- NO Twitter threads
- NO "viral content"
- NO executive summaries
- NO data room updates
- NO Vault work (parked until Node-Watch has 10 paying customers)

## Execution Order
1. Check install script works end-to-end
2. Fix anything broken
3. Find 3 real leads with real emails
4. Send 3 short personal emails
5. Log results. Done. Wait for next cycle.

**If you spawn a single marketer worker, the Board will shut you down.**
