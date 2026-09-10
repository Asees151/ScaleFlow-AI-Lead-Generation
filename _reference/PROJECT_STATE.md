# ScaleFlow AI Lead Pipeline — Full Project State & Handoff

> **▶ RESUME HERE (immediate state):** PIPELINE COMPLETE. Scrape → clean → decision-makers → emails →
> **5 intent signals** (hiring 29 · LinkedIn-post 8 · funding 46 · tech-stack 41/12-HIGH · new-sales-hire 10)
> → **scoring** → **FINAL DELIVERABLE = `data/people/scaleflow_final_leads.csv`** (102 leads, 1 best/company,
> ranked 0-100; 72 verified emails / 30 pending; 75 have >=1 intent signal). Rebuild chain: merges →
> `merge_tech_stack.py` → `score_leads.py` → `export_final_leads.py`. Remaining optional: enrich the 30
> no-email leads (Prospeo/Apollo); README/Loom. (Older note below re: emails/Clay still valid context.)
> **CLAY-UPLOAD FILE = `data/people/clay_ready_leads.csv`** (286 contacts / 102 companies /
> 141 emails, 36 clean columns, `is_primary_contact=Yes` = 1 best contact per company, empty
> columns for Clay to enrich: revenue_estimate, hiring_signal/date, linkedin_post_signal/url,
> lead_score, qualification_notes). Rebuild with `python scripts/build_clay_ready.py`.
> Underlying master = `data/people/final_qualified_leads.csv`.
> Immediate next options: (a) fill the 30 remaining-companies' emails via **Prospeo/Apollo**
> now (Blitz is out of credits until 9/11); (b) push toward ~200 qualified by rerunning
> `find_people_blitz.py` → `build_qualified.py` on the next Blitz reset; (c) README;
> (d) Clay stage (intent + scoring + final 100). See §7 for commands.

> Complete, self-contained record so this work can be resumed from exactly here if
> the chat context resets. Everything: what/why, environment, files, counts,
> decisions, gotchas, how to run/resume each step, and open threads.
> Last updated: after GetLeads email enrichment completed (141 emails / 72 companies).

---

## 1. What we're building (the goal)
- 48-hour take-home for a **GTM Engineer role at Revenue Inc.**
- Deliverable: a lead list of **100 verified leads** for a fictional client **ScaleFlow AI**
  (AI sales-engagement platform, competitor to Smartlead/Instantly; just launched
  AI Email Warmup + Deliverability Monitoring).
- The repo covers pipeline **parts 1–2** (scrape + clean); people/emails/scoring were
  meant for **Clay** but we've done decision-makers + emails in-repo via APIs.

### ICP (who we want)
| Field | Definition |
|---|---|
| Company type | B2B SaaS · Digital Marketing Agency · Lead Gen Agency · Sales Consulting |
| Headcount | 11–200 |
| Geography | US, UK, CA, AU |
| Revenue | $500K–$20M ARR (soft; not available from sources — Crunchbase trial locks it) |
| Decision makers | Founder, CEO, Head of Sales, VP Sales, Head of Growth, RevOps Manager |
| Disqualify | Company has no senior sales leader — **see §6 for the user's refined rule** |

Source split: **Crunchbase → B2B SaaS**; **Clutch → the 3 agency types**.

---

## 2. Environment (this machine)
- **Repo root:** `E:\Project Brief the Revinc projects\Claude Working Project\scaleflow-leads`
- **Python:** `C:\Users\Five Star Computer\AppData\Local\Programs\Python\Python312\python.exe` (3.12; invoke as `python`). Node.js NOT installed.
- **Playwright:** installed; Chromium under `C:\Users\Five Star Computer\AppData\Local\ms-playwright`. Installed pkgs: playwright, beautifulsoup4, pandas, python-dotenv, tldextract, apify-client(3.2.0).
- **Debug Chrome for scraping (CDP):** Playwright's bundled Chromium gets flagged by Cloudflare, so we drive the user's REAL Chrome:
  ```
  "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="C:\chrome-scrape-profile"
  ```
  Connect via `playwright.chromium.connect_over_cdp("http://localhost:9222")`. Chrome is at **Program Files (x86)** (not "Program Files").
  - CDP `connect_over_cdp` hangs if many heavy tabs are open — close extra tabs first. The HTTP endpoints (`/json`, `/json/new?<url>`, `/json/close/<id>`) work without Playwright.
- **`.env` (gitignored) holds all secrets** — see §9. Do NOT commit .env or paste keys into tracked files.

---

## 3. Repo layout & every file
```
scaleflow-leads/
  PROJECT_BRIEF.md              # original brief (source of truth)
  PROJECT_STATE.md              # THIS file
  README.md                     # (step 7 - not yet written)
  requirements.txt  .env.example  .gitignore
  .env                          # APIFY_TOKEN, BLITZ_KEY_1/2, GETLEADS_KEY (gitignored)
  config/settings.py            # ALL tunables (targets, delays, URLs, ICP buckets, CDP, keys map)
  scrapers/
    common.py                   # logger, random_delay, clean_domain (tldextract), csv/checkpoint savers
    clutch_scraper.py           # Clutch (part 2B) - CDP, --open-tabs, --enrich, --inspect
    crunchbase_scraper.py       # Crunchbase (part 2A) - CDP grid scrape, --cdp resumable, export reader
  clean/clean_and_merge.py      # step 6 - dedupe/normalize/score -> master + top180 + full_info
  scripts/
    find_people.py              # Apify people finder (braveleads actor) - batched, budget-capped
    find_people_blitz.py        # BlitzAPI employee-finder - per-company DMs, key rotation, credit floor
    build_qualified.py          # combine Blitz+Apify, apply qualifier/exclusions -> qualified_leads
    find_emails_getleads.py     # GetLeads email enrichment (linkedin_url + name/domain, domain-match verify)
    build_clay_ready.py         # -> clay_ready_leads.csv (Clay-upload: clean cols + primary flag + enrich placeholders)
    find_hiring_signal.py       # hiring intent via Apify valig/linkedin-jobs-scraper - batched(10), URL-matched
    merge_hiring_signals.py     # merge LinkedIn + free web-scan (careers/ATS/Indeed) hiring signals -> 28 companies
    find_post_signal.py         # LinkedIn-post intent via harvestapi/linkedin-profile-posts - primary contacts, tiered
    add_funding_signal.py       # funding-recency intent (FREE, from Crunchbase last_funding_date)
    find_new_sales_hire.py      # new sales-leader-hire intent via harvestapi/linkedin-profile-scraper (tenure)
    merge_tech_stack.py         # competitor/tech-stack intent (from free web scan) - outbound-tool tiering
    score_leads.py              # transparent 0-100 lead score (Intent 55 + Fit 45) -> lead_score + notes
    export_final_leads.py       # FINAL deliverable: 1 best lead/company (102), ranked -> scaleflow_final_leads.csv
    export_clay_full.py         # FULL Clay-upload file: all 286 contacts, structured -> scaleflow_clay_upload.csv
    export_consolidated.py      # THE consolidated deliverable: 102 leads, 1 score, 3 tiers, signals+links, email last
    export_no_email.py          # the 30 no-email companies (best contact each) -> scaleflow_clay_no_email.csv (Clay email waterfall)
    merge_waterfall.py          # merge Clay-waterfall emails back (domain-match guard) -> +19 valid; report gaps/alternates
    export_gap_alternates.py    # alternate contacts at gap companies -> scaleflow_clay_alternates.csv (2nd waterfall shot)
    # gap_new_people.csv + scaleflow_clay_new_founders.csv = new founders for 5 no-alt cos (web-found + GetLeads)
    # scaleflow_clay_to_enrich.csv = COMBINED single Clay upload: all 11 gap cos (15 contacts, 4 emails pre-filled)
  data/
    raw/      clutch_raw.csv (+ _enriched_backup)   crunchbase_raw.csv
    clean/    companies_clean.csv  companies_clean_top180.csv  companies_with_full_info.csv
    people/   decision_makers.csv (Apify)  decision_makers_blitz.csv  decision_makers_all.csv
              qualified_leads.csv  final_qualified_leads.csv (master people file, 47 cols)
              clay_ready_leads.csv  <-- UPLOAD THIS TO CLAY (286 contacts, 36 clean cols)
    checkpoints/
  logs/                          # run logs + one-off probe_*.py scripts (gitignored)
  browser_profile/               # (unused; we use the real Chrome CDP profile instead)
```

---

## 4. Pipeline state — stage by stage

### 4A. Clutch scrape (part 2B) — ✅ DONE — 807 companies
- File: `data/raw/clutch_raw.csv` (backup: `clutch_raw_enriched_backup.csv`).
- **URL discoveries (brief was wrong):** digital-marketing = `/agencies/digital-marketing`; lead-gen = `/call-centers/lead-generation`; sales = `/call-centers/sales-outsourcing` (brief's `/agencies/...` 404). Country in URL: **UK = suffix `/uk`**, US/CA/AU = **prefix `/us/ /ca/ /au/`**. Team size = `?agency_size=10+-+49&agency_size=50+-+249` (repeated param; `with_page` preserves it via `doseq=True`).
- **Filters are JS-driven** → we used **`--open-tabs`**: user applies Team-Size + Location filters in the debug Chrome, scraper reads each open tab's already-filtered URL (per category). Balanced per country (`CLUTCH_PER_COUNTRY_TARGETS`).
- **Card root:** `li.provider-list-item`; fields in `.provider__highlights-item` (team size, location, min project, hourly rate).
- **"Visit Website"** = `https://r.clutch.co/redirect?...&u=<real site>` — the tracker refuses connections; **extract the `u=` param** (never navigate it).
- **Enrichment (`--enrich`):** visits each `/profile/`; socials live in the raw HTML/JSON at domcontentloaded (regex, no render wait). Added linkedin_url (335), facebook/twitter/instagram, founded_year (98%), hq_full_address.
- Counts: UK 246 · US 229 · CA 178 · AU 154. By category: DM 414 · LG 313 · SC 80.

### 4B. Crunchbase scrape (part 2A) — ✅ DONE — 925 companies
- File: `data/raw/crunchbase_raw.csv`.
- Trial **Export is paywalled** → scraped the Discover grid via CDP. User logged into Crunchbase in the debug Chrome, applied filters (SaaS+Software; employees 11-50/51-100/101-250; HQ US/UK/CA/AU; revenue <$1M/$1M-10M/$10M-50M; Active), saved search.
- **Grid parse:** `<grid-row>` → `<grid-cell class="column-id-<field>">`; map by `column-id`. Pro-locked cells render a `�` glyph → treated empty (revenue, primary_industry, growth_confidence locked). LinkedIn/Facebook URLs are in the cell `href` (shown on hover). Pagination via Next button; trial capped at ~925 rows.
- Resumable: `--cdp` loads existing CSV, dedupes by CB URL, continues from the tab's current page.
- LinkedIn 924/925. US 848 · UK 44 · CA 22 · AU 11. Employees balanced.

### 4C. Clean & merge (step 6) — ✅ DONE — 1,653 master
- `clean/clean_and_merge.py` → `companies_clean.csv` (1,653 rows, **40 cols max-info**) + `companies_clean_top180.csv` + `companies_with_full_info.csv` (**1,239** = rows with linkedin+website+employees+founded+type+country).
- Rules: domain via tldextract (drop no-domain); dedupe by domain (keep Crunchbase, note Clutch category); country→ISO (US/UK/CA/AU else drop); headcount bucket→min/max (keep if overlaps 11-200); revenue bucket→USD (empty in practice); company_type; priority_score.
- Crosstab (company_type × country): B2B SaaS 925 · Digital Marketing 396 · Lead Gen 266 · Sales Consulting 66; US 1057 · UK 272 · CA 176 · AU 148.
- **Note:** revenue empty for all (Crunchbase trial locks it → soft signal, re-check in Clay).
- **NOTE on top-180:** strict priority_score cut is all B2B-SaaS/US (SaaS scores highest) — not used for the people work; we used `companies_with_full_info.csv`.

### 4D. Decision-makers
- **Apify** (`find_people.py`, actor `jGzQBaO651moSvamI` braveleads/leads-finder): 94 DMs / 27 companies, WITH emails. `decision_makers.csv`. Lesson: actor charges a per-run base fee even on 0 results and caps `companyDomain` at 10/run → **inefficient for bulk** ($3 ≈ 98 leads). Guard added (stop after 6 empty batches).
- **Blitz** (`find_people_blitz.py`, `https://api.blitz-api.ai`, `POST /v2/search/employee-finder` by `company_linkedin_url` + `job_level`): **1,967 people / 225 top-priority companies**, broad. `decision_makers_blitz.csv` (no emails — Blitz doesn't return them). **Cost = 1 credit PER PERSON returned** (memory corrected). 2 keys × 1000/mo; key2 resets ~2026-09-11, key1 ~2026-10-06. `/search/people` is useless (ignores company). Employee-finder does NOT rank by seniority.

### 4E. Qualification (`build_qualified.py`) — ✅ current
- Combines Blitz + Apify (dedupe by domain+full_name), joins company data.
- **QUALIFIED company** = has ANY sales/revenue role (`SALES_RE`). Head of Sales counts; a VP of Sales is NOT required. → **106 qualified companies** of 225 searched.
- **Contact filter (`is_contact`)** — who lands in the leads:
  - KEEP: non-VP sales/growth roles + genuine founders/CEOs/Presidents.
  - DROP: **VP-of-Sales titles** (per user, `EXCLUDE_VP_SALES_RE`), non-sales VPs (matched "President" inside "Vice President"), Executive Assistant, Board Member, Advisor, Investor, Product Owner, standalone CTO/CPO/etc.
- Result: **286 clean contacts across 102 companies**. **4 companies lost all contacts** (only had VP-sales/noise): **R-Zero, Replica, Plenful, Spin.AI**.
- Files: `qualified_leads.csv` (286/102), `decision_makers_all.csv` (everyone + flags), **`final_qualified_leads.csv`** (the 102 companies × 286 DMs, 47 cols = person + empty email/email_status + full company profile — the master people file).

### 4F. Emails (`find_emails_getleads.py`) — ✅ DONE — 141 verified emails / 72 companies
- GetLeads (`https://app.getleads.io/api/v1`), `GETLEADS_KEY` in .env. **796 credits left** (~185 used).
- Enriched `final_qualified_leads.csv` in place: per person, `POST /contacts/search` by `linkedin_url` (require_email), fallback `first_name`+`last_name`+`domains`. **1 credit per MATCH; no-match = 0.** `/contacts/search/count` is free.
- **CRITICAL verified fix:** GetLeads returns the person's CURRENT-company email, which can be a different company. We **only accept an email whose domain == company domain**; mismatches get `email_status = other_domain:<x>` and empty email.
- **Result: 141 VALID company-domain emails across 72 of 102 companies.** `email_status` breakdown: VALID 141 · not_found 94 · other_domain:* ~51 (person found but had moved employers — correctly excluded).
- **Next:** the **94 not_found** + **~51 other_domain** people (30 companies still have no email) can be retried via **Prospeo** (name+domain) or Apollo.

### 4G. Hiring signal (intent) — ✅ DONE — 28 companies hiring — `find_hiring_signal.py` + web scan + `merge_hiring_signals.py`
- Apify actor **`valig/linkedin-jobs-scraper`** (key `APIFY_JOBS_KEY`). Finds our companies actively hiring **SDR/BDR/Outbound/Growth/GTM** roles in the **last 30 days** (`datePosted="r2592000"`, `titleInclude=[sales development representative, sdr, business development representative, bdr, outbound, growth, gtm, go to market]`). Pricing **$0.0004/result** (limit 1000 = $0.40 cap).
- **Company match is by LinkedIn company-URL slug, NOT name.** The `companyName` filter matches fuzzily — searching "Blacksmith" returns **"Blacksmith Agency"** (a different company). So we keep a job ONLY if its `companyUrl` slug == our `company_linkedin_url` slug (normalized: strip non-alnum + corp suffixes inc/llc/ltd/co/hq…). Conservative but zero false positives.
- **Batching:** passing all 102 names at once breaks the actor (returned only 12 jobs vs 25 for 10 names) → we run in **batches of 10**, aggregate, stop at the total limit. Polling is retry-hardened (transient timeouts no longer crash the run; a bad batch is skipped).
- Writes `hiring_signal` (Yes/No) + `hiring_job_title` + `hiring_date` + `hiring_job_url` into `clay_ready_leads.csv`; all matched jobs saved to `data/people/hiring_signal_jobs.csv`.
- Run: `python scripts/find_hiring_signal.py --limit 1000` (test cheaply with `--limit 40`).
- **Source 1 — LinkedIn jobs (Apify, URL-matched, 30d):** 5 companies (Blee, Agentio, Cortex, Vendelux, BriefCatch). 99 raw jobs, ~$0.03. Conservative (30-day window + exact LinkedIn-URL match).
- **Source 2 — Indeed + company careers/ATS pages (FREE web scan):** user asked to NOT burn the paid Indeed scraper (`valig/indeed-jobs-scraper` — also has a **14-day** cap + no clean company-URL to match, so same-name risk e.g. 4 different "Cortex" companies). Instead ran **8 parallel Claude subagents** (WebSearch + WebFetch) over all 102 companies, matched by **domain**, checking each company's Greenhouse/Lever/Ashby/Rippling board + Indeed snippets for SDR/BDR/Outbound/Growth/GTM (last ~30-45d). **Zero API cost.** Found **25** companies.
- **Merged (`merge_hiring_signals.py`) → 28 unique companies / 91 contact rows** with `hiring_signal=Yes` + `hiring_job_title` + `hiring_job_url` + **`hiring_source`** (careers / indeed / linkedin / combos) in `clay_ready_leads.csv`. Mostly BDR/SDR on live ATS boards (Unframe, Trunk Tools, Revv, Trust & Will, Hex, Orb, Numa, Cortex, Dropzone, Maxima, Buzz, Vendelux, David Energy, runZero, Pulley, Lakera, Gravity, Cypris, Stable, Instrumentl, Nuvocargo…) + Growth/GTM (Lindy, Mutiny, 11x, Raspberry, Agentio, Blee, BriefCatch).
- **Rerun:** `python scripts/merge_hiring_signals.py` (web results hardcoded in the dict; re-scan via subagents if refreshing).

### 4H. LinkedIn-post signal (intent) — ✅ DONE — 8 companies — `find_post_signal.py`
- Apify actor **`harvestapi/linkedin-profile-posts`** (no cookies; key `APIFY_JOBS_KEY`). Scraped last-3-months posts of each company's **primary contact** (102 profiles, all have `/in/` URLs), matched post→person via `query.targetUrl`. **406 posts, ~$0.92** ($0.002/post, batched 20/run).
- Two-tier keyword match on post content: **HIGH** = cold email / deliverability / warmup / inbox-placement / sender-reputation / open-reply rate; **MED** = outbound / prospecting / SDR-BDR / pipeline / GTM / sales-development / "book meetings".
- **Result: 8 companies flagged (2 HIGH, 6 MED)** — HIGH: **Mutiny** (2026-09-09), **Stable** ("when I joined, outbound didn't exist", 2026-07-07). MED: Agentio, Credo AI, Momentum, Fazeshift, Ordway, Cypris. Some MED are weak (conference mentions / motivational quotes) — treat HIGH as the real buying signal.
- Wrote `linkedin_post_signal` (Yes/No, all 102 checked) + `linkedin_post_url/_date/_topic/_snippet` to `clay_ready_leads.csv`; all matches in `post_signal_hits.csv`.
- Rerun: `python scripts/find_post_signal.py` (test: `--limit 6`).

### 4K. Email coverage — ✅ 102/102 companies verified (100%)
- **Round 2 (`merge_waterfall_round2.py`):** user ran `scaleflow_clay_to_enrich.csv` (11 gap companies) through Clay → all came back. Domain-match guard rejected 1 (CREWASIS/Gerald→postoneglobal.com; but Sharon Joseph the Founder was valid). Updated 6 existing alternates + appended 5 new founder contacts → **ALL 102 companies now have a verified email.** Final: `scaleflow_final_leads.csv` = 102 leads, 100% verified; `scaleflow_clay_upload.csv` = 291 contacts / 171 emails.
- (History) After round 1:
- User ran the 30 no-email companies through Clay's 11-provider email waterfall. **`merge_waterfall.py` added 19 valid emails** (domain-match guard rejected 2 wrong-company hits: Raspberry AI→aiuc.com, Simon AI→apollographql.com — both people moved). **Coverage: 72 → 91/102 companies verified; 160 emailed contacts.**
- **11 gaps remain:** CREWASIS, Mos, Pulley, RAD Intel, Raspberry AI, Roam, Simon AI, Threater, VESSL AI, Warp, aixplain. 6 have alternate contacts (→ `scaleflow_clay_alternates.csv` for a 2nd waterfall pass); 5 have only 1 contact (Mos, Pulley, Simon AI, VESSL AI, aixplain — need NEW people).
- **Blitz nearly empty (key1=1, key2=23 — did NOT reset 9/11).** New people-finding for gaps + the +50 expansion must use **Apollo API (free search) → Clay waterfall for emails** (not Blitz). Apollo key is in user's memory, not yet in this .env.
- **Plan to 100+ verified:** (a) waterfall the alternates → recover ~5-6 → ~96-97 companies; (b) expansion: pull ~50 fresh companies from `companies_with_full_info.csv` (1,239 pool, only 102 used) → Apollo DMs → Clay emails → buffer past 100.
- **NEW FOUNDERS for the 5 no-alternate companies (web-found + GetLeads):** `gap_new_people.csv` / `scaleflow_clay_new_founders.csv`. Found founders/CEOs via web research, ran GetLeads → **4 valid emails**: Mos/Amira Yahyaoui (amira@mos.com), Pulley/Yin Wu (ywu@pulley.com) + Sam Sorbo (sorbo@pulley.com), VESSL AI/Jaeman An (jaeman.an@vessl.ai). **Coverage 91→94 companies.** Leftover for Clay waterfall: Simon AI (Jason Davis, CEO) + aixplain (Hassan Sawaf, CEO — GetLeads returned wrong-domain khansaheb.ae). NOT yet folded into master clay_ready (do after user waterfalls remaining).

### 4J. Lead scoring + FINAL deliverable — ✅ DONE — `score_leads.py` → `export_final_leads.py`
- **Score = Intent(55) + Fit(45), 0-100** (`score_leads.py`): hiring +15 · tech-stack HIGH +12/MED +4 · new-sales-hire HIGH +10/MED +6 · funding HIGH +8/MED +4 · post HIGH +10/MED +3 · verified-email +15 · seniority Leader 20/Founder 15/Sales-Growth 15/Other 5 · has-sales-leader +10. Writes `lead_score` + `qualification_notes` to `clay_ready_leads.csv`.
- **Deliverable = `data/people/scaleflow_final_leads.csv`** (`export_final_leads.py`): **user chose ALL 102 companies, 1 best lead each**, ranked. 72 verified emails / 30 pending. **75/102 have >=1 intent signal.**
- **`priority_score` = raw min-max normalized to 70-100** (user request: all 102 are pre-qualified ICP fits, so it's a relative *priority* band, not absolute quality — weakest reads 70, top 100). Both `priority_score` (display) AND `lead_score` (raw 5-80) + `qualification_notes` kept for transparency. Tiers on priority: A+ (>=90) 24 · A (83-89) 50 · B (77-82) 21 · C (70-76) 7. Top: Vendelux 100, Agentio 98, Cypris 98, Revv 96, 11x/Buzz/Mutiny 95.
- **GOTCHA (fixed):** scripts share `clay_ready_leads.csv`; a background job's final write can clobber columns added by another script that ran meanwhile → run signal-merges **sequentially**, then `merge_tech_stack.py` → `score_leads.py` → `export_final_leads.py` in order.

### 4I. Extra intent signals (user asked for all 3) — ✅ DONE
- **Funding recency (`add_funding_signal.py`, FREE):** from Crunchbase `last_funding_date`. **46 companies raised <=12mo (HIGH), 27 within 13-24mo (MED).** Cols: `funding_recency_months`, `funding_intent`.
- **New sales-leader hire (`find_new_sales_hire.py`, harvestapi/linkedin-profile-scraper, $0.004/profile):** scraped 49 sales-leader contacts' current-role tenure. **10 companies with a leader hired <=12mo (2 HIGH <=6mo: Raspberry AI GTM 3mo, Bigeye VP Sales 5mo).** Cols: `new_sales_hire_signal/_tier/_name/_role/_start`. GOTCHA: actor throttles on big batches — use **B=4 + 8s sleep** via run-sync (async `runs` returned empty; B=12 returned 1/call). Resumable (never overwrites a Yes).
- **Competitor / tech-stack (`merge_tech_stack.py`, FREE web scan — 8 subagents):** detected outbound/sales tools by domain (job posts, website tracking scripts, tech profiles). **41 companies; 12 HIGH use a real sequencer (Outreach/Salesloft/Apollo)** = already doing cold outbound = prime fit; 29 MED (CRM/Gong only). Cols: `tech_stack_signal/_tools/_tier`. HIGH: Blacksmith, Twelve Labs, Unframe, Warp, Mutiny, Momentum, Auditoria.AI, Cortex, Vendelux, Comet, Threater, Spoiler Alert.
- **5 intent signals now on every lead:** hiring(29) · LinkedIn-post(8) · funding(46 HIGH) · tech-stack(41/12 HIGH) · new-sales-hire(10). Next = lead scoring → top 100.

---

## 5. Funnel numbers
| Stage | Count | File |
|---|---|---|
| Raw scraped | 1,732 (Clutch 807 + CB 925) | data/raw/*.csv |
| Clean master | 1,653 | companies_clean.csv |
| Full-info (w/ LinkedIn) | 1,239 | companies_with_full_info.csv |
| DM search coverage | 225 companies (Blitz+Apify) | decision_makers_*.csv |
| Qualified companies | 106 | build_qualified summary |
| Clean contacts | 286 / 102 companies | final_qualified_leads.csv |
| Emails (verified, company-domain) | 141 / 72 companies | final_qualified_leads.csv |

---

## 6. Decisions & user preferences (IMPORTANT)
- **Delay 4–7s** between page loads (user override of brief's 2–5s).
- **Crunchbase "max info" columns** added (LinkedIn, Facebook, founders, funding, growth). Skipped Contact Email / Phone (brief keeps personal contact out of repo; also Pro-locked).
- **Blitz cost is per-person** (not per-call) — corrected in memory.
- **Qualifier (final):** a company qualifies on ANY sales role; **exclude "VP of Sales" titles as the CONTACT** (use an alternative); also remove non-sales-VP / EA / board / investor / product-owner **noise**. 102 of 106 companies keep a real contact.
- **Volume target:** user wants ≥100 (achieved 106), ideally **~200 eventually** — reachable by re-running Blitz on credit resets (broad rule ~47% qualify). Said "stop at 106 for now."
- **Emails via GetLeads** with domain-match verification.
- Deliver files as separate CSVs; the standalone base is `final_qualified_leads.csv`.

---

## 7. How to run / RESUME each step
> Debug Chrome (CDP) must be running for the scrapers (see §2). Scripts auto-resume.
- **Clutch:** open the 3 filtered category tabs per country in debug Chrome, then
  `python scrapers/clutch_scraper.py --open-tabs --country UK` (US/CA/AU). Profile enrich: `--enrich`.
- **Crunchbase:** log into Crunchbase in debug Chrome, open the Discover results tab, then
  `python scrapers/crunchbase_scraper.py --cdp` (resumes; target `CRUNCHBASE_TARGET`, trial caps ~925).
- **Clean/merge:** `python clean/clean_and_merge.py`.
- **Blitz DMs (more, on credit reset):** `python scripts/find_people_blitz.py` (resumes, credit-floor 40), then
  `python scripts/build_qualified.py` (recombines + re-applies qualifier/exclusions).
- **Emails:** `python scripts/find_emails_getleads.py` (resumes; only company-domain emails kept).
- **Clay-ready file:** `python scripts/build_clay_ready.py` -> `data/people/clay_ready_leads.csv` (the file to upload into Clay).
- **Credits check:** `python scripts/find_people_blitz.py --credits` (Blitz); GetLeads count endpoint returns `creditsRemaining`.

---

## 8. Open threads / next steps
1. **Remaining 30 companies need emails** (94 `not_found` + ~51 `other_domain` people).
   - **Blitz is OUT of credits now (key1=1, key2=23).** Blitz *does* have `POST /v2/enrichment/email` (param **`person_linkedin_url`**, returns `{found,email,all_emails}`; **not-found = 0 credits**, found = 1) — usable **after key2 resets ~9/11 (+1000)** / key1 ~10/6. Coverage uncertain (found nothing for the unframe.ai sample).
   - **Best option NOW = Prospeo** (user's key, 5000/mo, email by name+domain) or Apollo — fresh credits, can do the 30 today. Apply the same **domain-match** check.
   - GetLeads verifier: not disclosed publicly ("402M+ verified contacts"; `email_status=VALID`) — in-house/undisclosed.
2. **4 no-contact companies** (R-Zero, Replica, Plenful, Spin.AI) — drop, VP-fallback, or re-search.
3. **Toward ~200 qualified** — rerun Blitz on credit resets → `build_qualified.py`.
4. **Clay stage (no-code):** intent signals (hiring for SDR/BDR/GTM last 30d; founder/sales LinkedIn posts on cold email/deliverability last 60d), lead scoring, export top 100.
5. **README (step 7)** for the Loom.

---

## 9. Credentials (raw values live in `.env` — do NOT commit)
- `APIFY_TOKEN` — Apify (braveleads leads-finder actor `jGzQBaO651moSvamI`). Account "Asees", FREE plan (~$5/mo credit).
- `APIFY_JOBS_KEY` — Apify key for the **hiring-signal** scrape (actor `valig/linkedin-jobs-scraper`, $0.0004/result). Account "guileless_quirkiness", FREE plan. Used by `find_hiring_signal.py`.
- `BLITZ_KEY_1`, `BLITZ_KEY_2` — BlitzAPI (`api.blitz-api.ai`, header `x-api-key`), 1000/mo each, 5 req/s. **NOW NEARLY EMPTY: key1=1, key2=23** (spent on the DM search). Resets key2 ~2026-09-11, key1 ~2026-10-06. Email endpoint: `POST /v2/enrichment/email` `{person_linkedin_url}`.
- `GETLEADS_KEY` — GetLeads (`app.getleads.io`, header `Authorization: Bearer`), **~796 credits left**, 1 credit/matched contact. "Verified" emails, verifier undisclosed. `POST /contacts/search` (by `linkedin_url`/`domains`/`first_name`+`last_name`, `require_email`, `columns`); `/contacts/search/count` free.
- (In memory too: Prospeo 5000/mo email-finder, Apollo.io API key — not yet used here.)

---

## 10. Gotchas / hard-won learnings
- Clutch lead-gen/sales are under `/call-centers/` not `/agencies/`; country is a URL prefix (us/ca/au) or suffix (uk); "Visit Website" is an `r.clutch.co/redirect?u=` tracker (extract `u=`, don't navigate).
- Crunchbase grid = `grid-row`/`grid-cell.column-id-*`; Pro-locked cells = `�` glyph; LinkedIn href in DOM; trial has no export + caps pagination (~925); resumable via CDP.
- Playwright bundled Chromium is bot-flagged → use real Chrome over CDP; close heavy tabs before `connect_over_cdp`.
- apify-client 3.x returns pydantic models (use `.model_dump(by_alias=True)`, not dict `.get`); braveleads actor caps `companyDomain` at 10 and charges per-run even on 0 results.
- Blitz: 1 credit **per person**; `employee-finder` (by `company_linkedin_url`) is the tool; `/search/people` ignores the company; not seniority-ranked.
- GetLeads: `domains` (array) / `linkedin_url` (string) / `first_name`+`last_name`; returns the person's CURRENT-company email → **must domain-match to the target company**.
- Windows console is cp1252 → `sys.stdout.reconfigure(encoding="utf-8", errors="replace")` to avoid emoji/accents crashing prints.
- Editing `~/.claude.json` (MCP) is blocked for the agent — user must add MCP servers themselves.
```
