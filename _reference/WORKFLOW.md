# ScaleFlow AI — Lead-Gen Workflow (with exact connectors + scoring weights)

## The pipeline at a glance

```
┌────────────────────────────────────────────────────────────────────────────┐
│ 1. SOURCE COMPANIES                                                          │
│    • Crunchbase  (B2B SaaS)        ─┐                                         │
│    • Clutch      (agencies)        ─┴─►  Playwright + real Chrome over CDP    │
│                                          (bypasses Cloudflare)               │
│                                          ≈ 1,730 scraped                      │
└───────────────────────────────┬──────────────────────────────────────────────┘
                                 ▼
┌────────────────────────────────────────────────────────────────────────────┐
│ 2. CLEAN & MERGE                 Python (pandas, tldextract)                  │
│    dedupe, normalize, ICP filter  ─►  ≈ 1,650 clean companies                 │
└───────────────────────────────┬──────────────────────────────────────────────┘
                                 ▼   (pick a batch of ≈ 225 to enrich)
┌────────────────────────────────────────────────────────────────────────────┐
│ 3. FIND DECISION-MAKERS                                                       │
│    • Apify — "braveleads" Leads Finder actor                                 │
│    • BlitzAPI — Employee Finder  (by company LinkedIn URL)                    │
└───────────────────────────────┬──────────────────────────────────────────────┘
                                 ▼
┌────────────────────────────────────────────────────────────────────────────┐
│ 4. QUALIFY                        Python rules                                │
│    keep only companies with a genuine senior sales leader ─► 100 companies    │
└───────────────────────────────┬──────────────────────────────────────────────┘
                                 ▼
┌────────────────────────────────────────────────────────────────────────────┐
│ 5. INTENT SIGNALS  (5 connectors)                                            │
│    • Hiring          → Apify "valig/linkedin-jobs-scraper"  + free web/ATS   │
│                        scan (Greenhouse / Lever / Ashby boards)              │
│    • LinkedIn posts  → Apify "harvestapi/linkedin-profile-posts"             │
│    • New sales hire  → Apify "harvestapi/linkedin-profile-scraper" (tenure)  │
│    • Tech stack      → free web scan (careers JDs, site scripts, tech profiles)│
│    • Recent funding  → Crunchbase data (already scraped, $0)                  │
└───────────────────────────────┬──────────────────────────────────────────────┘
                                 ▼
┌────────────────────────────────────────────────────────────────────────────┐
│ 6. EMAILS                                                                     │
│    • GetLeads (getleads.io)  + domain-match validation  ─► 72 companies       │
│    • Clay — multi-vendor email WATERFALL for the rest:                        │
│        Hunter → Prospeo → LeadMagic → Findymail → Kitt → Wiza → Enrow →       │
│        Icypeas → Dropcontact → SMARTe → BetterContact → FullEnrich           │
│    • (found fresh founders/CEOs where a contact had left)                     │
│    ─► 100 / 100 companies verified (100%)                                     │
└───────────────────────────────┬──────────────────────────────────────────────┘
                                 ▼
┌────────────────────────────────────────────────────────────────────────────┐
│ 7. SCORE & TIER                   Python — 0-100 (Intent 55 / Fit 45)         │
│    Tier 1 Hot ≥90 · Tier 2 Warm 80-89 · Tier 3 Qualified 70-79               │
└───────────────────────────────┬──────────────────────────────────────────────┘
                                 ▼
┌────────────────────────────────────────────────────────────────────────────┐
│ 8. DELIVERABLE   →  scaleflow_leads_consolidated.csv                          │
│    100 leads · score · tier · all signals (with links) · verified email      │
└────────────────────────────────────────────────────────────────────────────┘
```

## Connectors — exact names

| Stage | Connector / tool | What it did |
|---|---|---|
| Scrape companies | **Playwright + real Chrome (CDP)** | Crunchbase Discover grid + Clutch listings (past Cloudflare) |
| Clean / merge | **Python** (pandas, tldextract) | dedupe, ICP filter → ~1,650 |
| Decision-makers | **Apify – braveleads Leads Finder** + **BlitzAPI Employee Finder** | names, titles, LinkedIn profiles |
| Hiring signal | **Apify – valig/linkedin-jobs-scraper** + free ATS/web scan | SDR/BDR/Growth openings |
| LinkedIn-post signal | **Apify – harvestapi/linkedin-profile-posts** | posts on cold email / deliverability |
| New-sales-hire signal | **Apify – harvestapi/linkedin-profile-scraper** | current-role tenure of sales leaders |
| Tech-stack signal | **Free web scan** | Outreach/Salesloft/Apollo/HubSpot usage |
| Funding signal | **Crunchbase** (already scraped) | last funding type + date |
| Emails (pass 1) | **GetLeads** (+ domain-match check) | verified work emails |
| Emails (pass 2) | **Clay – multi-vendor waterfall** (~12 providers) | Hunter, Prospeo, Findymail, Dropcontact, BetterContact, FullEnrich, etc. |
| Score / export | **Python** | 0-100 score, 3 tiers, consolidated CSV |

## Scoring weights — the full model (0–100)

**INTENT — 55 points**
| Signal | Weight |
|---|---|
| Hiring SDR/BDR/Outbound | **+15** |
| Tech-stack **usage** — uses outbound tool (Outreach/Salesloft/Apollo) | **+12**  ·  CRM-only (HubSpot/Salesforce) **+4** |
| New sales-leader hire ≤6mo | **+10**  ·  ≤12mo **+6** |
| LinkedIn post — cold email/deliverability | **+10**  ·  outbound/GTM **+3** |
| **Recent funding** ≤12mo | **+8**  ·  ≤24mo **+4** |

**FIT — 45 points**
| Factor | Weight |
|---|---|
| Verified email | **+15** |
| Contact seniority | Sales Leader **20** · Founder **15** · Sales/Growth **15** · Other **5** |
| Company has a senior sales leader | **+10** |

Raw total → normalized to a **70–100 band** → **3 tiers**: Hot (≥90), Warm (80–89), Qualified (70–79).

## Key numbers
- ~1,730 scraped → ~1,650 cleaned → **enriched ~225** → **100 qualified & 100% verified**
- 5 intent signals: hiring **29** · LinkedIn posts **8** · recent funding **46** · outbound tech stack **41** · new sales-leader hires **10**
- Tiers: **Hot 14 · Warm 47 · Qualified 41**
- Reserve: ~1,400 clean companies already scraped, ready to scale into
