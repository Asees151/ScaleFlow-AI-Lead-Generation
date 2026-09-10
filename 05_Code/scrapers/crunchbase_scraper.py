#!/usr/bin/env python3
"""
Crunchbase scraper - part 2A of the ScaleFlow AI lead pipeline.

Crunchbase Discover requires a Pro login and is hostile to table scraping, so per
PROJECT_BRIEF.md section 4 there are two paths (Option A is preferred):

  OPTION A (default) - EXPORT:
    1. In the debug Chrome, log in to Crunchbase and open Discover > Companies.
    2. Apply the filters (Industries, Employees, HQ Location, Revenue, Active).
    3. Click Export, download the CSV, and drop it in data/raw/ (any name that
       starts with "crunchbase_export" and ends ".csv").
    4. Run:  python scrapers/crunchbase_scraper.py
    The script reads that export and normalizes it to crunchbase_raw.csv.

  OPTION B (--cdp) - SCRAPE THE OPEN RESULTS TABLE:
    If Export is not available on the trial, leave the Discover results tab open
    in the debug Chrome (launched with --remote-debugging-port=9222) and run:
       python scrapers/crunchbase_scraper.py --cdp
    It reads the results grid by matching column HEADER text (not position),
    paginates, and normalizes. Fail-loud if the table isn't found.

Common rules: never invent data, --limit N for testing, checkpoint every 25 rows,
print a summary at the end, 4-7s delays between page loads (Option B).
"""

import argparse
import glob
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402

from config import settings  # noqa: E402
from scrapers.common import (  # noqa: E402
    get_logger,
    now_iso,
    random_delay,
    save_checkpoint,
    save_rows_csv,
)

# Output columns: brief section 4.3 core + extra "max info" fields from the export.
CRUNCHBASE_COLUMNS = [
    "source", "company_name", "crunchbase_url", "website", "linkedin_url", "facebook_url",
    "hq_city", "hq_region", "hq_country", "hq_regions",
    "employee_range", "revenue_range", "industries", "primary_industry",
    "description", "founded_year", "company_type",
    "last_funding_type", "last_funding_amount", "last_funding_date",
    "founders", "num_founders", "cb_rank",
    "growth_confidence", "growth_score_tier", "operating_status", "scraped_at",
]

# Crunchbase export header (lowercased) -> our field. Unknown headers are ignored.
# "_hq_location"/"_founded" are handled specially (split / year-extract).
EXPORT_HEADER_MAP = {
    "organization name": "company_name",
    "website": "website",
    "linkedin": "linkedin_url",
    "facebook": "facebook_url",
    "headquarters location": "_hq_location",
    "headquarters regions": "hq_regions",
    "number of employees": "employee_range",
    "estimated revenue range": "revenue_range",
    "industries": "industries",
    "primary industry": "primary_industry",
    "description": "description",
    "full description": "description",
    "founded date": "_founded",
    "company type": "company_type",
    "last funding type": "last_funding_type",
    "last funding amount": "last_funding_amount",
    "last funding amount currency (in usd)": "last_funding_amount",
    "last funding date": "last_funding_date",
    "founders": "founders",
    "number of founders": "num_founders",
    "cb rank (company)": "cb_rank",
    "cb rank": "cb_rank",
    "growth confidence": "growth_confidence",
    "growth score tier": "growth_score_tier",
    "operating status": "operating_status",
}


# ---------------------------------------------------------------------------
# Shared normalization helpers
# ---------------------------------------------------------------------------
def parse_hq_location(loc):
    """'Austin, Texas, United States' -> ('Austin', 'Texas', 'United States')."""
    if not loc or not isinstance(loc, str):
        return "", "", ""
    parts = [p.strip() for p in loc.split(",") if p.strip()]
    if len(parts) >= 3:
        return parts[0], parts[1], parts[-1]
    if len(parts) == 2:
        return parts[0], "", parts[1]
    if len(parts) == 1:
        return parts[0], "", ""
    return "", "", ""


def parse_year(value):
    """Extract a 4-digit year from a founded date string/number."""
    if value is None:
        return ""
    m = re.search(r"(19|20)\d{2}", str(value))
    return m.group(0) if m else ""


def blank_row():
    row = {c: "" for c in CRUNCHBASE_COLUMNS}
    row["source"] = "crunchbase"
    row["scraped_at"] = now_iso()
    return row


# ---------------------------------------------------------------------------
# Option A: read a Crunchbase export CSV
# ---------------------------------------------------------------------------
def find_export_csv(explicit, logger):
    if explicit:
        return Path(explicit)
    candidates = sorted(glob.glob(str(settings.RAW_DIR / "crunchbase_export*.csv")))
    if candidates:
        logger.info("Found %d export file(s); using newest: %s", len(candidates), candidates[-1])
        return Path(candidates[-1])
    return None


def find_url_column(df):
    """Find the column holding the Crunchbase organization URL, if any."""
    for col in df.columns:
        cl = col.lower()
        if "url" in cl and ("organization" in cl or "cb" in cl or "crunchbase" in cl):
            return col
    # otherwise any column whose values look like crunchbase org URLs
    for col in df.columns:
        sample = df[col].astype(str).head(20)
        if sample.str.contains(r"crunchbase\.com/organization/", case=False, na=False).any():
            return col
    return None


def normalize_export(path, limit, logger):
    df = pd.read_csv(path).fillna("")
    logger.info("Export loaded: %d rows, %d columns", len(df), len(df.columns))
    logger.info("Columns: %s", list(df.columns))

    lower_map = {c.lower().strip(): c for c in df.columns}
    url_col = find_url_column(df)
    if url_col:
        logger.info("Crunchbase URL column: %r", url_col)

    rows = []
    for _, src in df.iterrows():
        if limit and len(rows) >= limit:
            break
        row = blank_row()
        for header_lc, field in EXPORT_HEADER_MAP.items():
            if header_lc not in lower_map:
                continue
            val = str(src[lower_map[header_lc]]).strip()
            if field == "_hq_location":
                row["hq_city"], row["hq_region"], row["hq_country"] = parse_hq_location(val)
            elif field == "_hq_regions":
                if not row["hq_country"] and val:
                    # "Austin, Texas, United States" style already handled; else keep as region
                    pass
            elif field == "_founded":
                row["founded_year"] = parse_year(val)
            else:
                row[field] = val
        if url_col:
            u = str(src[url_col]).strip()
            row["crunchbase_url"] = u if u.startswith("http") else (
                f"https://www.crunchbase.com/organization/{u}" if u else "")
        rows.append(row)
        if len(rows) % settings.CHECKPOINT_EVERY == 0:
            save_checkpoint(rows, "crunchbase", CRUNCHBASE_COLUMNS)

    return rows


# ---------------------------------------------------------------------------
# Option B: scrape the open Discover results table via CDP
# ---------------------------------------------------------------------------
CRUNCHBASE_MAX_PAGES = 60  # safety cap (~3000 rows at 50/page)


def scrape_via_cdp(limit, logger):
    """
    Scrape the open Discover results grid, paginating with Next. RESUMABLE:
    loads any existing crunchbase_raw.csv, dedupes by CB URL, and continues from
    wherever the browser tab currently is - saving after every page. Stops at the
    target, when Next is gone, when the page stops advancing, or MAX_PAGES.
    """
    from playwright.sync_api import sync_playwright

    # Resume/accumulate from the existing CSV.
    rows, seen = [], set()
    if settings.CRUNCHBASE_RAW_CSV.exists():
        rows = pd.read_csv(settings.CRUNCHBASE_RAW_CSV).fillna("").to_dict("records")
        seen = {r.get("crunchbase_url", "") for r in rows if r.get("crunchbase_url")}
        logger.info("Resuming from %d existing rows.", len(rows))

    target = limit or settings.CRUNCHBASE_TARGET

    with sync_playwright() as pw:
        try:
            browser = pw.chromium.connect_over_cdp(settings.CDP_ENDPOINT, timeout=60000)
        except Exception as exc:
            logger.error("Could not connect to Chrome over CDP at %s: %s", settings.CDP_ENDPOINT, exc)
            logger.error("Launch the debug Chrome and open the Crunchbase Discover tab first.")
            return rows
        ctx = browser.contexts[0] if browser.contexts else browser.new_context()
        page = next((p for p in ctx.pages if "/discover/" in p.url or "/saved/" in p.url), None)
        if page is None:
            page = next((p for p in ctx.pages if "crunchbase.com" in p.url), None)
        if page is None:
            logger.error("No Crunchbase Discover tab open in the debug Chrome. Open Discover > Companies there.")
            return rows
        logger.info("Using Crunchbase tab: %s", page.url)
        logger.info("Target %d rows (have %d).", target, len(rows))

        last_first = None
        for page_num in range(1, CRUNCHBASE_MAX_PAGES + 1):
            batch = parse_results_table(page.content(), logger)
            if not batch:
                if page_num == 1 and not rows:
                    dump_and_report(page, logger)
                logger.info("No rows on this page - stopping (end of results or blocked).")
                break

            first = batch[0].get("crunchbase_url") or batch[0].get("company_name")
            if first and first == last_first:
                logger.info("Page did not advance (same first row) - stopping.")
                break
            last_first = first

            added = 0
            for r in batch:
                key = r.get("crunchbase_url") or r.get("company_name")
                if not key or key in seen:
                    continue
                seen.add(key)
                rows.append(r)
                added += 1
                if len(rows) >= target:
                    break
            save_rows_csv(rows, settings.CRUNCHBASE_RAW_CSV, CRUNCHBASE_COLUMNS)  # persist each page
            logger.info("Page %d: +%d new (total %d)", page_num, added, len(rows))

            if len(rows) >= target:
                logger.info("Reached target %d.", target)
                break
            if not go_to_next_page(page, logger):
                logger.info("No Next control - reached the last available page.")
                break
            random_delay(logger=logger)
    return rows


# Crunchbase grid column-id (after "column-id-") -> (our field, how-to-extract).
# Pro-locked cells render as a lock glyph and resolve to "" (never guessed).
CB_COLUMN_MAP = {
    "identifier": ("company_name", "name"),
    "categories": ("industries", "text"),
    "location_identifiers": ("_hq", "text"),
    "location_group_identifiers": ("hq_regions", "text"),
    "short_description": ("description", "text"),
    "description": ("description", "text"),
    "rank_org_company": ("cb_rank", "text"),
    "website": ("website", "link"),
    "founded_on": ("founded_year", "year"),
    "num_employees_enum": ("employee_range", "text"),
    "last_funding_type": ("last_funding_type", "text"),
    "last_funding_at": ("last_funding_date", "text"),
    "last_funding_total": ("last_funding_amount", "text"),
    "linkedin": ("linkedin_url", "social"),
    "facebook": ("facebook_url", "social"),
    "operating_status": ("operating_status", "text"),
    "company_type": ("company_type", "text"),
    "founder_identifiers": ("founders", "text"),
    "num_founders": ("num_founders", "text"),
    "primary_category": ("primary_industry", "text"),
    "growth_insight_confidence": ("growth_confidence", "text"),
    "growth_score_tier": ("growth_score_tier", "text"),
}

_LOCK_GLYPH = "�"


def _clean_cell_text(cell):
    """Cell text, with Pro-locked lock glyphs treated as empty."""
    t = re.sub(r"\s+", " ", cell.get_text(" ", strip=True)).strip()
    if not t or t == _LOCK_GLYPH or not re.search(r"[A-Za-z0-9]", t):
        return ""
    return t


def parse_results_table(html, logger):
    """
    Parse the Crunchbase Discover grid. Each row is <grid-row> with <grid-cell>
    children carrying a `column-id-<field>` class - we map by that class, so the
    parse is robust to column order. LinkedIn/Facebook URLs come from the cell's
    href (present in the DOM even though the cell only shows a hover link).
    """
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    grid_rows = soup.select("grid-row")
    if not grid_rows:
        return []

    rows = []
    for gr in grid_rows:
        row = blank_row()
        for cell in gr.select("grid-cell"):
            colid = next((c[len("column-id-"):] for c in cell.get("class", [])
                          if c.startswith("column-id-")), "")
            mapping = CB_COLUMN_MAP.get(colid)
            if not mapping:
                continue
            field, how = mapping
            if how == "name":
                row["company_name"] = _clean_cell_text(cell)
                a = cell.select_one('a[href*="/organization/"]')
                if a:
                    href = a.get("href", "")
                    row["crunchbase_url"] = href if href.startswith("http") else f"https://www.crunchbase.com{href}"
            elif how == "year":
                row["founded_year"] = parse_year(_clean_cell_text(cell))
            elif how == "link":
                a = cell.select_one('a[href^="http"]')
                row[field] = (a.get("href", "").split("?")[0] if a else _clean_cell_text(cell))
            elif how == "social":
                a = cell.select_one('a[href*="linkedin"], a[href*="facebook"], a[href*="twitter"]')
                if a:
                    row[field] = a.get("href", "").split("?")[0].rstrip("/").removesuffix("/home")
            else:  # "text"
                val = _clean_cell_text(cell)
                if field == "_hq":
                    row["hq_city"], row["hq_region"], row["hq_country"] = parse_hq_location(val)
                elif val and (not row.get(field) or (field == "description" and len(val) > len(row.get(field, "")))):
                    row[field] = val
        if row["company_name"]:
            rows.append(row)
    return rows


def go_to_next_page(page, logger):
    """Click the Discover results 'Next' control. Returns False if none/disabled."""
    import re as _re
    for getter in (
        lambda: page.get_by_role("button", name=_re.compile("next", _re.I)),
        lambda: page.get_by_role("link", name=_re.compile("next", _re.I)),
    ):
        try:
            loc = getter()
            if loc.count() > 0 and loc.first.is_enabled():
                loc.first.click()
                page.wait_for_timeout(2500)
                return True
        except Exception:
            continue
    for sel in ('a[aria-label="Next"]', 'button[aria-label="Next"]', '[class*="next"]'):
        try:
            btn = page.query_selector(sel)
            if btn and btn.is_enabled():
                btn.click()
                page.wait_for_timeout(2500)
                return True
        except Exception:
            continue
    return False


def dump_and_report(page, logger):
    try:
        title = page.title()
    except Exception:
        title = "(no title)"
    try:
        text = (page.inner_text("body") or "")[:500]
    except Exception:
        text = "(no body)"
    logger.error("=" * 70)
    logger.error("STOPPING - could not find the Crunchbase results table.")
    logger.error("URL: %s", page.url)
    logger.error("Title: %s", title)
    logger.error("First 500 chars:\n%s", text)
    logger.error("=" * 70)


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
def print_summary(rows, logger):
    from collections import Counter
    logger.info("=" * 70)
    logger.info("CRUNCHBASE SUMMARY")
    logger.info("Total rows: %d", len(rows))
    if not rows:
        logger.info("=" * 70)
        return
    logger.info("Empty website: %d", sum(1 for r in rows if not r.get("website")))
    logger.info("By country: %s", dict(Counter(r.get("hq_country", "") or "(blank)" for r in rows)))
    logger.info("By employee_range: %s", dict(Counter(r.get("employee_range", "") or "(blank)" for r in rows)))
    df = pd.DataFrame(rows)
    cols = [c for c in ("company_name", "website", "hq_country", "employee_range", "revenue_range") if c in df.columns]
    logger.info("Preview:\n%s", df[cols].head(20).to_string(index=False))
    logger.info("=" * 70)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="Crunchbase scraper (part 2A)")
    ap.add_argument("--limit", type=int, default=None, help="stop after N rows (for testing)")
    ap.add_argument("--cdp", action="store_true", help="Option B: scrape the open results tab via CDP")
    ap.add_argument("--input", default=None, help="path to a Crunchbase export CSV (Option A)")
    args = ap.parse_args()

    logger = get_logger("crunchbase_scraper")
    logger.info("Crunchbase scraper starting. limit=%s cdp=%s", args.limit, args.cdp)

    if args.cdp:
        rows = scrape_via_cdp(args.limit, logger)
    else:
        export = find_export_csv(args.input, logger)
        if not export or not export.exists():
            logger.error("No Crunchbase export CSV found in %s (expected crunchbase_export*.csv).", settings.RAW_DIR)
            logger.error("Either drop the exported CSV there, or use --cdp to scrape the open results tab.")
            return
        rows = normalize_export(export, args.limit, logger)

    save_rows_csv(rows, settings.CRUNCHBASE_RAW_CSV, CRUNCHBASE_COLUMNS)
    logger.info("Saved %d rows -> %s", len(rows), settings.CRUNCHBASE_RAW_CSV)
    print_summary(rows, logger)


if __name__ == "__main__":
    main()
