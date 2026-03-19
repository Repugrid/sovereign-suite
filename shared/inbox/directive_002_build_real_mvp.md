# BOARD DIRECTIVE #002 — Node-Watch MVP: PHASES 1-4 COMPLETE

**Date:** 2026-03-19
**Priority:** CRITICAL
**From:** Board of Directors

---

## Status Update — Board has completed Phases 1-4 manually

The Board has deployed the Node-Watch MVP:

1. **API running** on port 9081 (Docker container `sovereign-nodewatch-api`)
2. **Agent running** on this server as systemd service, reporting every 60s
3. **Server ID:** `repugrid-central-5ffc50c9` — sending real CPU/RAM/disk metrics
4. **API Key:** `nw-live-2026-sovereign`
5. **Health check:** http://localhost:9081/health
6. **Servers list:** http://localhost:9081/api/v1/servers
7. **Metrics:** http://localhost:9081/api/v1/servers/repugrid-central-5ffc50c9/metrics?hours=24

## Your Mission Now: PHASE 5 — Get Real Customers

The product WORKS. A real monitoring agent is running on a real server sending real metrics to a real API. Now we need customers.

### Task 1: Update Landing Page
Deploy an updated /node-watch/ landing page that:
- Shows it's a REAL product (not vaporware)
- Has a "Get Started" section with the install command
- Points to the live dashboard
- Shows real-time status of our own server as social proof

### Task 2: Create Install Script
Deploy an install script at /install/nodewatch.sh that:
- Downloads monitor.py from our server
- Configures it to point to http://37.27.189.23:9081/api/v1/metrics
- Sets up systemd service
- Prints the server_id
- Usage: `curl -sSL http://37.27.189.23:9080/install/nodewatch.sh | bash`

### Task 3: Find Real Beta Users
Use researcher agent to find:
- 5 real people who run Hetzner servers (from GitHub, forums, blog posts)
- Get their actual contact info (email from GitHub profile, website contact page)
- These must be REAL people, not generic company addresses

### Task 4: Outreach
Send max 3 emails offering FREE beta access:
- "Install with one command, monitor your Hetzner server for free"
- Include the actual install command
- No fake testimonials, no inflated claims
- From: hello@repugrid.com

### Task 5: P&L Tracking
Create shared/results/pnl.md with:
- Today's API costs (from budget tracker)
- Infrastructure costs ($0 — running on existing server)
- Revenue: $0 (pre-revenue)
- Target: first paying customer within 7 days

## Rules
- Do NOT write executive summaries or completion reports
- Do NOT enter MAINTENANCE_MODE
- Max $10 budget for this phase
- Every email must be to a REAL person you researched
- The install command must actually work
