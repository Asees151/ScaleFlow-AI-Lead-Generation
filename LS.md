# Loom Script — Lead Generation Flow (ScaleFlow AI)  ·  ~2 min, read as-is
*Leads with intent, names every tool. Headers are just for you — don't read them.*

---

**Open**

"Hey! Quick walkthrough of the 100 verified, high-intent lead list I built for ScaleFlow AI — an AI sales-engagement platform, a competitor to Smartlead and Instantly."

**Intent first (the value)**

"The whole list is built around intent — not just companies that fit, but ones that need this *right now*. Every company is scored on five buying signals:
one — they're actively hiring SDRs or BDRs;
two — their founders are posting on LinkedIn about cold email or deliverability;
three — they raised funding recently, so they have budget;
four — they're already using outbound tools like Outreach, Instantly, or Apollo, or a CRM like HubSpot — which means they're doing outreach and feel the exact pain ScaleFlow fixes;
and five — they just hired a new sales leader, so they're building their go-to-market motion.
Each lead is scored out of 100 — intent weighted 55, fit 45, with hiring and outbound-tools the heaviest — then sorted into three tiers: Hot, Warm, and Qualified."

**How I built it — Python + scraping**

"Now how I built it — the brain behind the whole thing is Claude Code. It wrote the Python scripts, ran every scraper and API, did the web research, and scored the leads — I orchestrated it end to end. For sourcing, it used Playwright driving a real Chrome browser — not the default Chromium, because Cloudflare blocks that — to scrape Crunchbase for SaaS and Clutch for agencies. That gave about 1,650 clean companies after de-duping."

**Decision-makers + qualifying**

"Then I picked a batch of around 225 and enriched them. I used the Apify Leads Finder and BlitzAPI's Employee Finder endpoint to pull the decision-makers and their LinkedIn profiles. Then I qualified — I kept the decision-makers but disqualified the VP-of-Sales titles as the contact and used another decision-maker at the company instead. That gave me 100 qualified companies."

**The signals — the scrapers**

"For the intent signals I used a few Apify scrapers — the LinkedIn Jobs scraper for hiring, and on top of that I read the companies' own hiring boards directly, the ATS platforms like Greenhouse, Lever, and Ashby, because a lot of roles never hit LinkedIn. I used the Apify LinkedIn Posts scraper for what founders are posting, and a profile scraper to spot newly-hired sales leaders. I did a web scan for their tech stack, and pulled recent funding straight from Crunchbase."

**Emails — GetLeads then Clay waterfall**

"For emails, I subscribed to GetLeads' free plan for the credits, and since I already had the LinkedIn URLs, I used its contact-search endpoint — that got me about 70% of the emails, all domain-checked so nothing at the wrong company slipped through. For the remaining 30%, I built a multi-vendor email waterfall in Clay — stacking around ten providers like Hunter, Prospeo, and Findymail on free credits, so it was basically zero cost. Where a contact had left, I found fresh founders and ran them through too. End result — all 100 companies verified, 100%."

**Close — deliverable**

"The final deliverable is one clean file: 100 leads, one per company — each with its score, its tier, every intent signal with a source link, and the verified email at the end. So you can sort by tier and start reaching out. And the rest of the scraped pool, around 1,400 companies, is a ready reserve, so this scales past 100 anytime. Thanks for watching!"

---

### Cheat-sheet (if asked)
- **Brain / orchestrator:** Claude Code — wrote the scripts, ran every scraper & API, web research, scoring
- **Python** everywhere: scraping (Playwright + real Chrome, beats Cloudflare), cleaning, enrichment, scoring
- **ATS** = Applicant Tracking System (Greenhouse / Lever / Ashby) — I read job boards directly, incl. their public APIs
- **Scrapers:** Apify Leads Finder + BlitzAPI Employee Finder (people) · Apify LinkedIn Jobs (hiring) · Apify LinkedIn Profile-Posts (posts) · Apify LinkedIn Profile scraper (new sales hire) · web scan (tech stack) · Crunchbase (funding)
- **Emails:** GetLeads contact-search endpoint (~70%, domain-checked) → Clay ~10-vendor waterfall (~30%) = 100%
- **Score weights (of 100):** hiring +15 · outbound-tool +12/4 · new-sales-hire +10/6 · LinkedIn post +10/3 · funding +8/4 · verified email +15 · seniority up to +20 · has-sales-leader +10
- **3 tiers:** Hot ≥90 (14) · Warm 80–89 (47) · Qualified 70–79 (41)
