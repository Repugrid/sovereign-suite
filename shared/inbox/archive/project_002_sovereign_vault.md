# PRIORITY DIRECTIVE — Project 002: Sovereign-Vault

**Date:** 2026-03-19
**Priority:** STRATEGIC
**From:** Board of Directors

## Mission: Build "Sovereign-Vault" — AI-Driven Backup & Recovery for Hetzner

### Context
Node-Watch (Monitoring) is EXIT-READY. Now build the complementary product: an AI agent that manages backups and performs fully autonomous disaster recovery on Hetzner infrastructure. Together they form the **"Sovereign Suite"** — doubling portfolio valuation through cross-selling.

### Budget: $7.50 total
### Budget Allocation: 90% Vault R&D, 10% Node-Watch maintenance

---

## Phase 1: Market Research (delegate to `researcher`)

Research the AI-driven cloud backup/recovery market with Hetzner focus:
- How big is the backup market for SME hosting customers?
- Existing competitors: Hetzner Snapshots, Restic, BorgBackup, Acronis, Veeam, Duplicati
- What gaps exist? (Focus: One-Click Recovery, AI-driven backup scheduling, cross-node restoration)
- Pricing models of competitors
- Key differentiator: "Your server dies → Vault spins up a clone on a new node in 90 seconds"
- Save to `shared/results/market_research_vault.md`

## Phase 2: Technical Architecture (delegate to `coder`)

Design the Sovereign-Vault system:
- Lightweight backup agent (runs alongside Node-Watch agent)
- Incremental backup strategy (block-level dedup, compression)
- Hetzner Storage Box integration (cheap S3-compatible storage)
- AI-powered backup scheduling (learns usage patterns, backs up before risky operations)
- One-Click Recovery engine:
  - Detects server failure (integrates with Node-Watch alerts)
  - Provisions new Hetzner Cloud server via API
  - Restores latest backup automatically
  - Updates DNS/floating IP to new server
  - Total recovery time target: < 90 seconds
- Security: End-to-end encryption, zero-knowledge architecture
- Save to `shared/results/architecture_vault.md`

## Phase 3: Landing Page & Suite Positioning (delegate to `marketer`)

Create marketing copy for Sovereign-Vault AND the combined Sovereign Suite:
- Vault standalone landing page copy (EN + DE)
- Headline angle: "Your Server Died. Vault Already Fixed It."
- Suite bundle pricing:
  - Node-Watch alone: €9-49/month
  - Vault alone: €12-59/month
  - **Sovereign Suite (both):** €16-79/month (30% bundle discount)
- Cross-selling narrative: "Monitoring catches the fire. Vault rebuilds the house."
- Save to `shared/results/landing_page_vault.md`

## Phase 4: CEO Synthesis

After all workers complete:
1. Write executive summary with go/no-go for Vault: `shared/results/executive_summary_vault.md`
2. Write updated portfolio valuation combining both products: `shared/results/portfolio_valuation_sovereign_suite.md`
   - Node-Watch standalone: €1.5M
   - Vault standalone: estimated value
   - Suite combined: synergy premium (typically 1.5-2x sum of parts)
3. Deploy Vault landing page via `deploy_static_site` with project_name `vault`
4. Update master_log.md

## Execution Rules
- Parallelize Phase 1 + 2 (independent tasks)
- Phase 3 depends on Phase 1 (needs market positioning)
- Reuse architectural patterns from Node-Watch (CEO has this in corporate memory)
- Error handling: If worker fails, analyze error first, simplify scope, then retry
- Keep total spend under $7.50
