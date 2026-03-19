# PRIORITY DIRECTIVE — Suite Finalization & Market Launch Prep

**Date:** 2026-03-19
**Priority:** HIGH
**From:** Board of Directors

## Mission: Deploy Sovereign Suite & Prepare Acquire.com Package

All Vault deliverables are COMPLETE. Now finalize everything for market launch.

## Task 1: Vault Landing Page HTML (delegate to `coder`)

Convert the Vault marketing copy into a production HTML landing page.

Instruction for coder:
"Read `shared/results/landing_page_vault.md` and create a production-ready HTML landing page.

Requirements:
- Single HTML file, Tailwind CSS via CDN (`<script src='https://cdn.tailwindcss.com'></script>`)
- Design MUST match Node-Watch style for brand consistency:
  - Dark hero: Deep blue (#1e3a5f) to darker (#0f172a) gradient
  - Accent: Green (#10b981) instead of blue (to differentiate from Node-Watch)
  - White content sections, same card-hover and fade-in animations
- Hero: headline, subheadline, CTA
- 3 feature blocks with emoji icons
- Pricing section with 3 tiers
- Cross-sell banner: 'Part of the Sovereign Suite — Bundle with Node-Watch and save 30%'
- Footer: '2026 Sovereign Suite | Node-Watch | Vault'
- Link to /node-watch/ in navigation
- Meta tags for SEO
- Save to `shared/results/landing_page_vault.html`"

## Task 2: Sovereign Suite Hub Page (delegate to `coder`)

Create the root index page that ties everything together.

Instruction for coder:
"Create a professional hub page for the Sovereign Suite brand.

Requirements:
- Single HTML file, Tailwind CSS via CDN
- Dark theme throughout (matches the product pages)
- Color: Deep blue (#1e3a5f) primary, white text
- Header: 'Sovereign Suite' logo text + tagline 'AI-Powered Infrastructure Management'
- Two product cards side by side:
  - Node-Watch card: monitoring icon, 3-line description, 'From €9/mo', link to /node-watch/
  - Vault card: backup icon, 3-line description, 'From €12/mo', link to /vault/
- Bundle pricing banner: 'Get both for €16/mo (save 30%)'
- Bottom section: 'Built by AI. Trusted by Engineers.' + brief trust copy
- Footer with links to /data-room/ (for investors)
- Save to `shared/results/sovereign_suite_index.html`"

## Task 3: Deploy All (CEO — do NOT delegate)

After coder delivers both HTML files:
1. Read `shared/results/landing_page_vault.html`
2. Use `deploy_static_site` with project_name `vault`
3. Read `shared/results/sovereign_suite_index.html`
4. Write it to the deployments root: use `write_file` to save to `../../deployments/index.html` — OR use `deploy_static_site` with project_name `.` (if supported)

Actually, simpler approach: Write the suite index HTML directly using `write_file` with path `../../deployments/index.html`. This puts it at the Nginx root.

NOTE: Since write_file saves to shared/, you cannot write to deployments/ directly. Instead, after reading the HTML, use the `deploy_static_site` tool:
- For vault: `deploy_static_site(project_name="vault", html_content=<vault html>)`
- For suite hub: Write the content to `shared/results/suite_index.html`, then I will manually copy it to deployments/index.html.

## Task 4: Update Master Log (CEO — do NOT delegate)

Append entry:
```
## [2026-03-19 XX:XX] — Sovereign Suite LIVE
**Decision:** Deployed complete Sovereign Suite with both products live.
**Result:** Node-Watch + Vault + Suite Hub all accessible. Portfolio doubled.
**URLs:** / (Suite Hub), /node-watch/ (Monitoring), /vault/ (Backup), /data-room/ (Protected)
**Cost:** Total project spend ~$12
**Status:** MARKET-READY — prepared for Acquire.com listing
---
```

## Constraints
- Budget: $3 max
- Parallelize both coder tasks (Task 1 + Task 2 are independent)
- Design consistency is critical — both pages must look like they belong together
