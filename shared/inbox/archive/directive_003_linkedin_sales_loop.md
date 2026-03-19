# BOARD DIRECTIVE #003 — LinkedIn Human-in-the-Loop Sales

**Date:** 2026-03-19
**Priority:** HIGH (execute alongside Directive #002)
**From:** Board of Directors

---

## Context

The Board will manually copy LinkedIn comments/names of people who commented "SOVEREIGN" (or showed interest) under our posts. These will be dropped into:

**`shared/inbox/linkedin_leads.md`**

Format:
```
## Lead: [Name]
- Company: [if visible]
- Comment: [what they said]
- LinkedIn URL: [if available]
```

## Your Mission: Research + Ghostwrite

When you find new entries in `shared/inbox/linkedin_leads.md`:

### Step 1: Researcher Agent
For each lead, delegate to a researcher:
- Find their company website
- What does the company do?
- How many servers might they run?
- What's their tech stack? (check GitHub, job postings, website)
- Pain points related to server monitoring
- Any public info about infrastructure challenges

Save to `shared/results/lead_research_{name}.md`

### Step 2: CEO Ghostwriting
Based on research, write TWO response options per lead:

**Option A: Public Comment Reply** (max 3 sentences)
- Acknowledge their interest naturally
- One specific detail about their use case
- Soft CTA: "Happy to set up a demo for your [specific setup]"

**Option B: LinkedIn DM Draft** (personalized)
- Open with something specific about their company
- Connect their pain point to Node-Watch
- Include the install command
- Professional but human tone
- Max 5 sentences

Save both to `shared/results/linkedin_responses_{name}.md`

### Step 3: Notify Board
After writing responses, update `shared/results/linkedin_queue.md` with:
```
## Ready for Review
- [Name] — [Company] — Response ready at linkedin_responses_{name}.md
```

The Board will then copy-paste and send manually.

## Rules
- NEVER send LinkedIn messages directly (we don't have API access)
- NEVER fabricate company details — if research finds nothing, say so
- Keep responses authentic — no corporate-speak, no "revolutionizing" language
- Max $3 budget per lead research
- Researcher must cite sources
