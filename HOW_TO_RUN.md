# How to Run / Reproduce

The whole pipeline is Python scripts (in `05_Code/`), run in order. Each writes its output into
`data/…`, which the next step reads. Below is the exact order.

## Setup
1. **Python 3.12**, then install deps:
   ```
   pip install -r 05_Code/requirements.txt
   python -m playwright install chromium
   ```
2. **Secrets** — copy `05_Code/.env.example` to `.env` and fill in the keys:
   `APIFY_TOKEN`, `APIFY_JOBS_KEY`, `BLITZ_KEY_1/2`, `GETLEADS_KEY`.
3. **For scraping only** — launch your real Chrome in debug mode, then the scrapers connect to it:
   ```
   "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="C:\chrome-scrape-profile"
   ```

## Run order
| # | Command | What it does |
|---|---|---|
| 1 | `python scrapers/crunchbase_scraper.py --cdp` | scrape Crunchbase (B2B SaaS) |
| 2 | `python scrapers/clutch_scraper.py --open-tabs --enrich` | scrape Clutch (agencies) |
| 3 | `python clean/clean_and_merge.py` | clean, dedupe, merge → company pool |
| 4 | `python scripts/find_people_blitz.py` + `python scripts/find_people.py` | find decision-makers (BlitzAPI + Apify) |
| 5 | `python scripts/build_qualified.py` | qualify (drop VP-of-Sales as contact) → 100 companies |
| 6 | `python scripts/find_emails_getleads.py` | emails via GetLeads (domain-checked) |
| 7 | `python scripts/find_hiring_signal.py` → `merge_hiring_signals.py` | **hiring** intent signal |
| 8 | `python scripts/find_post_signal.py` | **LinkedIn-post** intent signal |
| 9 | `python scripts/find_new_sales_hire.py` | **new sales-leader hire** signal |
| 10 | `python scripts/merge_tech_stack.py` | **tech-stack** signal |
| 11 | `python scripts/add_funding_signal.py` | **recent-funding** signal |
| 12 | `python scripts/score_leads.py` | weighted 0–100 score + tiers |
| 13 | `python scripts/export_consolidated.py` | ⭐ final consolidated file |
| 14 | `python scripts/export_clay_full.py` | full Clay upload file |
| 15 | `python scripts/render_html.py` | render the workflow diagram (PNG + PDF) |

## Gap-closing helpers (used to reach 100% email coverage)
- `export_no_email.py` / `export_gap_alternates.py` → Clay files for companies missing an email
- `build_expansion.py` → pulls fresh companies from the reserve pool
- `merge_waterfall.py` / `merge_waterfall_round2.py` → fold Clay-waterfall emails back in (domain-checked)

## Notes
- Emails are **always domain-checked** — an address at the wrong company (person changed jobs) is rejected.
- Scripts are **resumable** — they skip rows already done, so re-running is safe.
- Full stage-by-stage history + gotchas: `_reference/PROJECT_STATE.md`.
