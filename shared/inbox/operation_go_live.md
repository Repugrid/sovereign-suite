# PRIORITY DIRECTIVE — Operation Go-Live

**Date:** 2026-03-19
**Priority:** HIGHEST
**From:** Board of Directors

## Mission: Make Sovereign-Node-Watch LIVE on the Internet

You now have a new tool: `deploy_static_site`. This deploys HTML to a live Nginx web server accessible at `http://37.27.189.23:9080/<project_name>/`.

## Phase 1: Build the Landing Page (delegate to `coder`)

Delegate to a `coder` worker with this instruction:

"Convert the marketing copy into a production-ready, single-file HTML landing page.

**Source:** Read `shared/results/DATA_ROOM/03_MARKETING_ASSETS.md` for the copy.

**Requirements:**
- Single HTML file with ALL CSS inline (no external files except CDN)
- Use Tailwind CSS via CDN: `<script src='https://cdn.tailwindcss.com'></script>`
- Modern, professional SaaS design (dark hero section, white content sections)
- Color scheme: Deep blue (#1e3a5f) primary, Electric blue (#3b82f6) accent, White backgrounds
- Responsive (mobile-first)
- Include ALL content from the English version of the marketing copy
- Hero section with headline, subheadline, CTA button
- 3 feature blocks with icons (use emoji or Unicode symbols)
- Pricing section with 3 tier cards
- Social proof / testimonials section
- Footer with copyright '2026 Sovereign-Node-Watch'
- CTA buttons should link to `#signup` (placeholder)
- Add subtle animations (fade-in on scroll using vanilla JS)
- Meta tags for SEO (title, description, og:image placeholder)
- Favicon using emoji via data URL

Save the complete HTML to `shared/results/landing_page_node_watch.html`"

## Phase 2: Deploy (CEO Task — do NOT delegate)

After the coder delivers the HTML file:
1. Read `shared/results/landing_page_node_watch.html`
2. Use `deploy_static_site` with project_name `node-watch` and the HTML content
3. Verify deployment by noting the live URL

## Phase 3: Update Assets (CEO Task)

After deployment:
1. Update `shared/results/DATA_ROOM/07_TEASER_LISTING.md` — add the live URL
2. Update `shared/results/DATA_ROOM/00_EXECUTIVE_SUMMARY.md` — add "Live Demo" link
3. Update `shared/results/master_log.md` with deployment entry

## Constraints
- Budget: $3 max for this operation
- The HTML must be a SINGLE FILE (no external CSS/JS files except CDN links)
- Quality matters — this is what investors see first
