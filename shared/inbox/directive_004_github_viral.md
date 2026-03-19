# BOARD DIRECTIVE #004 — GitHub Viral Push

**Date:** 2026-03-19
**Priority:** HIGH
**From:** Board of Directors

---

## Context

The sovereign-suite repo is now PUBLIC at github.com/Repugrid/sovereign-suite.
README is done. Topics are set. Now we need activity and visibility.

## Your Mission: Make the Repo Active and Interesting

### Task 1: Create v0.1.0 Release
Use `github_create_release` to create the first release:
- Tag: `v0.1.0-beta`
- Name: "Node-Watch MVP — Built by AI Agents"
- Body: Short changelog of what was built today. Include:
  - Monitoring agent (psutil, systemd, offline buffer)
  - FastAPI metrics API (SQLite, CORS, health checks)
  - Live dashboard (Chart.js, auto-refresh)
  - One-line installer
  - CEO orchestrator with anti-polling protection
  - Telegram chat integration
  - Total cost: ~$15 in API credits

### Task 2: Enable Discussions & Post First Thread
Use `github_create_discussion` to post:

**Title:** "How an AI CEO built this product in 4 hours (with honest cost breakdown)"
**Category:** "Show and tell" (or "Announcements" or "General" — check what's available)
**Body:**
Write an honest, engaging post about how Sovereign works. Include:
- The architecture (CEO → workers in Docker)
- What went right (parallel task execution, code review by CEO)
- What went wrong ($42 burned in polling loop, format mismatches)
- Real cost breakdown per phase
- An invitation for people to try the install script
- Ask: "What should the AI CEO build next?"

Keep it authentic. No corporate speak. The honesty about failures is what makes it interesting.

### Task 3: Create "Good First Issue" Issues
The CEO doesn't have a create_issue tool yet, so instead write 3 good first issues as a discussion post:
- "Add Prometheus export endpoint to the API"
- "Support for Hetzner Cloud API integration (auto-discover servers)"
- "Alert notifications via webhook (Discord, Slack)"

This gives contributors something to work on.

## Rules
- Do NOT create fake stars or engagement
- Be honest about what works and what doesn't
- Budget: max $2 for this directive
- The $42 polling bug story is GOOD — include it, it makes us real
