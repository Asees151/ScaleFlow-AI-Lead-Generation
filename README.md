# ScaleFlow AI — 100 Verified, Intent-Scored Leads

**GTM Engineer take-home · built & orchestrated end-to-end with Claude Code**

A list of **100 B2B SaaS companies**, each with a **verified decision-maker email** and a
**0–100 intent score**, ranked into 3 tiers — so ScaleFlow AI (a cold-email / sales-engagement
platform) can work the hottest, most-likely-to-buy accounts first.

---

## What's the headline
| | |
|---|---|
| **Leads** | **100** (1 best contact per company) |
| **Email coverage** | **100% verified** (domain-checked) |
| **Intent signals** | **5** per company (hiring · LinkedIn posts · funding · tech stack · new sales hire) |
| **Scoring** | 0–100 (Intent 55 / Fit 45) → **Tier 1 Hot 14 · Tier 2 Warm 47 · Tier 3 Qualified 41** |
| **Reserve** | ~1,400 more companies already scraped, ready to enrich |

**👉 The deliverable is [`00_Final_Deliverable/scaleflow_leads_consolidated.csv`](00_Final_Deliverable/scaleflow_leads_consolidated.csv)** —
one row per company: score, tier, all company + contact info, every intent signal *with its source link*, and the verified email.

---

## What we did, end to end
1. **Source** — scraped Crunchbase (SaaS) + Clutch (agencies) with Python + Playwright driving a real Chrome browser (beats Cloudflare) → ~1,730 companies.
2. **Clean & merge** — Python/pandas de-dupe, normalize, ICP-filter → ~1,650 clean companies.
3. **Decision-makers** — enriched a batch of ~225 via Apify Leads Finder + BlitzAPI Employee Finder → names, titles, LinkedIn profiles.
4. **Qualify** — kept companies with a real decision-maker; disqualified VP-of-Sales titles as the contact (used another DM) → **100 companies**.
5. **Intent signals (5)** — hiring (Apify LinkedIn Jobs + ATS boards: Greenhouse/Lever/Ashby), LinkedIn posts (Apify), new sales-leader hire (Apify profile scraper), tech stack (web scan), recent funding (Crunchbase). *(see `03_Intent_Signals/README.md`)*
6. **Emails** — GetLeads contact-search (~70%, domain-checked) → Clay multi-vendor waterfall (~30%) → **100% verified**.
7. **Score & tier** — weighted 0–100 → Hot / Warm / Qualified.
8. **Deliver** — one consolidated, Clay-ready file.

See the full picture in **[`Lead_Generation_Flow.png`](Lead_Generation_Flow.png)** (and `.pdf`).

---

## Folder guide
```
00_Final_Deliverable/        ⭐ the 100 leads (consolidated) + full Clay upload
01_Source_and_Clean/         raw scrapes + cleaned/merged company pool
02_Decision_Makers_and_Qualify/  decision-makers + qualified set
03_Intent_Signals/           hiring + LinkedIn-post signal data (+ README on all 5)
04_Emails/                   new founders found + Clay waterfall inputs
05_Code/                     all Python scripts + supporting modules (see HOW_TO_RUN.md)
_reference/                  PROJECT_STATE.md (full history) + WORKFLOW.md
Lead_Generation_Flow.png/pdf workflow diagram
Loom_Script.md               narration script for the walkthrough video
workflow.html                editable source for the diagram
HOW_TO_RUN.md                setup + exact run order to reproduce
```

---

## Scoring weights (0–100)
**Intent (55):** hiring +15 · uses outbound tool (Outreach/Salesloft/Apollo) +12 (CRM-only +4) ·
new sales-leader hire ≤6mo +10 (≤12mo +6) · LinkedIn post cold-email/deliverability +10 (outbound/GTM +3) ·
recent funding ≤12mo +8 (≤24mo +4)
**Fit (45):** verified email +15 · seniority up to +20 (Sales Leader 20 / Founder 15 / Sales-Growth 15 / Other 5) ·
company has a senior sales leader +10

*Built by Muhammad Asees Abid · orchestrated with Claude Code.*
