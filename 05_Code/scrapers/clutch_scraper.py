#!/usr/bin/env python3
"""
Clutch scraper - part 2B of the ScaleFlow AI lead pipeline.

Scrapes agency/consulting provider cards from Clutch category listing pages into
data/raw/clutch_raw.csv. Clutch is public but sits behind Cloudflare, so this uses
a headed Playwright browser with a persistent profile and polite 2-5s delays.

Design rules (from PROJECT_BRIEF.md):
  * Never invent data. If a field is not on the card, leave it empty.
  * Read filter state from the URL (settings.CLUTCH_URLS). Do NOT click dropdowns.
  * If the page layout does not match what we expect, print the title + first 500
    chars of visible text, dump the HTML, and STOP. Do not guess selectors blindly.
  * Checkpoint every 25 rows. --limit N for testing. --resume to continue.

Usage:
  python scrapers/clutch_scraper.py --limit 20          # test run, ~20 rows
  python scrapers/clutch_scraper.py --inspect           # verify page 1 only, no scrape
  python scrapers/clutch_scraper.py                     # full run to CLUTCH_TARGET
  python scrapers/clutch_scraper.py --resume            # append to existing checkpoint
  python scrapers/clutch_scraper.py --cdp --limit 20    # use your real Chrome via CDP

CDP mode (recommended when Cloudflare loops on the bundled Chromium):
  1) Close ALL Chrome windows.
  2) Launch Chrome with remote debugging:
     "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" \\
         --remote-debugging-port=9222 --user-data-dir="C:\\chrome-scrape-profile"
  3) In that Chrome, open clutch.co once and clear any Cloudflare check.
  4) Run:  python scrapers/clutch_scraper.py --cdp --limit 20
"""

import argparse
import re
import sys
import time
from collections import Counter
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlencode, urljoin, urlparse, urlunparse

# Repo root on sys.path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402
from bs4 import BeautifulSoup  # noqa: E402
from playwright.sync_api import TimeoutError as PWTimeout  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

from config import settings  # noqa: E402
from scrapers.common import (  # noqa: E402
    clean_domain,
    get_logger,
    now_iso,
    random_delay,
    save_checkpoint,
    save_rows_csv,
)

# Extra fields pulled from each company's Clutch PROFILE page (--enrich).
# Company-level only (LinkedIn company page, socials, founded year) - no personal data.
CLUTCH_ENRICH_COLUMNS = [
    "linkedin_url", "facebook_url", "twitter_url", "instagram_url",
    "founded_year", "hq_full_address",
]

# Exact output columns (brief section 5.3) + enrichment columns appended.
CLUTCH_COLUMNS = [
    "source", "company_name", "clutch_url", "website", "category",
    "hq_city", "hq_region", "hq_country", "team_size", "min_project_size",
    "hourly_rate", "rating", "review_count", "tagline", "scraped_at",
] + CLUTCH_ENRICH_COLUMNS

# Clutch self-reported team-size buckets.
TEAM_SIZE_BUCKETS = ["Freelancer", "2 - 9", "10 - 49", "50 - 249", "250 - 999", "1,000+"]

# US state abbreviations -> so we can infer country from "City, ST" location text.
US_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID", "IL",
    "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT",
    "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI",
    "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "DC",
}

MAX_PAGES_PER_URL = 25  # safety cap on pagination


# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------
def get_target_urls(logger):
    """Return list of {url, category, country}. Fall back to base pages if empty."""
    if settings.CLUTCH_URLS:
        return list(settings.CLUTCH_URLS)
    logger.warning(
        "CLUTCH_URLS is empty in settings.py -> falling back to base category "
        "pages (UNFILTERED). For the real run, apply Team Size + Location filters "
        "in the browser and paste each URL into settings.CLUTCH_URLS."
    )
    return [
        {"url": url, "category": cat, "country": ""}
        for cat, url in settings.CLUTCH_CATEGORY_PAGES.items()
    ]


def with_page(url, page_num):
    """
    Return url with the ?page= param set (page 0 = base URL, no param).
    Preserves repeated params like ?agency_size=10+-+49&agency_size=50+-+249.
    """
    parts = urlparse(url)
    query = parse_qs(parts.query, keep_blank_values=True)
    if page_num > 0:
        query["page"] = [str(page_num)]
    else:
        query.pop("page", None)
    return urlunparse(parts._replace(query=urlencode(query, doseq=True)))


# ---------------------------------------------------------------------------
# Cloudflare handling
# ---------------------------------------------------------------------------
def looks_like_cloudflare(page):
    try:
        title = (page.title() or "").lower()
    except Exception:
        title = ""
    if any(k in title for k in ("just a moment", "attention required", "checking your browser")):
        return True
    try:
        body = (page.inner_text("body") or "")[:600].lower()
    except Exception:
        body = ""
    return any(
        k in body
        for k in ("checking your browser", "verify you are human", "needs to review the security")
    )


def wait_for_cloudflare(page, logger):
    """Wait up to CLOUDFLARE_WAIT_SECONDS; if still blocked, ask the user to solve it."""
    if not looks_like_cloudflare(page):
        return
    logger.info("Cloudflare challenge detected - waiting up to %ss...", settings.CLOUDFLARE_WAIT_SECONDS)
    for _ in range(settings.CLOUDFLARE_WAIT_SECONDS):
        time.sleep(1)
        if not looks_like_cloudflare(page):
            logger.info("Cloudflare cleared automatically.")
            return
    logger.warning("Cloudflare still present - likely a captcha.")
    try:
        input(">>> Solve the Cloudflare/captcha in the browser window, then press Enter here... ")
    except EOFError:
        logger.warning("No interactive stdin; continuing without manual solve.")
    time.sleep(2)


def dump_and_report(page, logger, reason):
    """Print title + first 500 chars of visible text, save full HTML, per the brief."""
    try:
        title = page.title()
    except Exception:
        title = "(no title)"
    try:
        text = (page.inner_text("body") or "")[:500]
    except Exception:
        text = "(could not read body text)"
    logger.error("=" * 70)
    logger.error("STOPPING - %s", reason)
    logger.error("URL:   %s", page.url)
    logger.error("Title: %s", title)
    logger.error("First 500 chars of visible text:\n%s", text)
    try:
        from datetime import datetime
        dump = settings.LOGS_DIR / f"clutch_pagedump_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        dump.write_text(page.content(), encoding="utf-8")
        logger.error("Full HTML saved for inspection: %s", dump)
    except Exception as exc:
        logger.error("Could not save HTML dump: %s", exc)
    logger.error("=" * 70)


# ---------------------------------------------------------------------------
# Card parsing
# ---------------------------------------------------------------------------
def _card_container(anchor):
    """Climb from a /profile/ anchor to the enclosing card container (best effort)."""
    node = anchor
    for _ in range(6):
        if node.parent is None:
            break
        node = node.parent
        text = node.get_text(" ", strip=True)
        if len(text) > 60 and any(
            k in text for k in ("Visit Website", "reviews", "/ hr", "Min. project", "Min project")
        ):
            return node
    return anchor.parent if anchor.parent is not None else anchor


def _extract_location(text):
    """
    Split a location string into (city, region, country). Handles US 'San Diego, CA',
    UK 'London, England', and 'City, Country' forms. Country inferred from the last
    segment when possible; empty if unknown (caller can fall back to the URL country).
    """
    text = re.sub(r"\s+", " ", text or "").strip().strip(",").strip()
    if not text:
        return "", "", ""
    parts = [p.strip() for p in text.split(",") if p.strip()]
    city = parts[0] if parts else ""
    region = parts[1] if len(parts) > 1 else ""
    last = parts[-1].lower() if parts else ""
    country = ""
    if parts[-1] in US_STATES:
        country = "US"
    elif last in ("england", "scotland", "wales", "northern ireland"):
        country = "UK"
    else:
        cmap = {"united states": "US", "usa": "US", "united kingdom": "UK",
                "uk": "UK", "canada": "CA", "australia": "AU"}
        country = cmap.get(last, "")
    return city, region, country


def _classify_highlight(raw):
    """Map one provider__highlights-item's text to (field, value). ('', '') if unknown."""
    t = re.sub(r"\s+", " ", raw).strip()
    if not t:
        return "", ""
    low = t.lower()
    if re.search(r"/\s*hr\b", low):                       # "$100 - $149 / hr", "< $25 / hr"
        return "hourly_rate", t
    compact = t.replace(" ", "")
    if re.fullmatch(r"\$[\d,]+\+?", compact):             # "$1,000+"
        return "min_project_size", compact
    if (t in TEAM_SIZE_BUCKETS or t == "1,000+" or low == "freelancer"
            or re.fullmatch(r"[\d,]+\s*-\s*[\d,]+", t)):  # "10 - 49", "250 - 999"
        return "team_size", t
    if "," in t:                                          # "San Diego, CA", "London, United Kingdom"
        return "location", t
    return "", ""


def extract_card_fields(li, name, slug, entry):
    """Pull the brief's fields from one card <li>, mainly from its highlights items."""
    row = {c: "" for c in CLUTCH_COLUMNS}
    row["source"] = "clutch"
    row["company_name"] = name
    row["clutch_url"] = f"https://clutch.co/profile/{slug}"
    row["category"] = entry.get("category", "")
    row["scraped_at"] = now_iso()

    header = li.get_text(" ", strip=True)
    # rating + review count appear together: "4.8 175 reviews"
    m = re.search(r"([0-5](?:\.\d)?)\s+(\d+)\s+reviews?\b", header, re.I)
    if m:
        row["rating"], row["review_count"] = m.group(1), m.group(2)
    else:
        m = re.search(r"(\d+)\s+reviews?\b", header, re.I)
        if m:
            row["review_count"] = m.group(1)

    # structured highlights: min project size, hourly rate, team size, location
    location_text = ""
    for hi in li.select(".provider__highlights-item"):
        field, value = _classify_highlight(hi.get_text(" ", strip=True))
        if field == "location":
            location_text = location_text or value
        elif field and not row.get(field):
            row[field] = value

    # tagline / short description (best effort; empty if the element is not present)
    tag = li.select_one(".provider__description-text, .provider__description, .provider-description")
    if tag:
        row["tagline"] = re.sub(r"\s+", " ", tag.get_text(" ", strip=True))[:300]

    # location text -> city / region / country (prefer country from the source URL)
    city, region, country = _extract_location(location_text) if location_text else ("", "", "")
    row["hq_city"], row["hq_region"] = city, region
    row["hq_country"] = entry.get("country", "") or country

    return row


def _find_visit_href(container):
    """Return the href of the card's Visit Website / Clutch redirect link, or ''."""
    for a2 in container.select("a[href]"):
        if "visit website" in a2.get_text(" ", strip=True).lower():
            return a2.get("href", "")
    for a2 in container.select("a[href]"):  # safety net: any redirect tracker link
        h = a2.get("href", "")
        if "r.clutch.co/redirect" in h or "provider_website=" in h:
            return h
    return ""


def parse_cards(html, entry, logger):
    """
    Return (rows, visit_hrefs). Prefer the stable li.provider-list-item card root;
    fall back to climbing from each /profile/ link if that class is not present.
    """
    soup = BeautifulSoup(html, "html.parser")
    rows, visit_hrefs, seen = [], [], set()

    cards = soup.select("li.provider-list-item")
    if cards:
        for li in cards:
            anchor = li.select_one('a[href*="/profile/"]')
            if not anchor:
                continue
            m = re.search(r"/profile/([^/?#]+)", anchor.get("href", ""))
            if not m:
                continue
            slug = m.group(1).strip()
            if not slug or slug in seen:
                continue
            name_el = li.select_one(".provider__title") or anchor
            name = name_el.get_text(" ", strip=True)
            if not name:
                continue
            seen.add(slug)
            rows.append(extract_card_fields(li, name, slug, entry))
            visit_hrefs.append(_find_visit_href(li))
        return rows, visit_hrefs

    # Fallback: unknown card root -> climb from each profile link (degraded fields).
    logger.warning("No li.provider-list-item found; using profile-link fallback heuristic.")
    for anchor in soup.select('a[href*="/profile/"]'):
        m = re.search(r"/profile/([^/?#]+)", anchor.get("href", ""))
        if not m:
            continue
        slug = m.group(1).strip()
        name = anchor.get_text(" ", strip=True)
        if not slug or slug in seen or not name:
            continue
        seen.add(slug)
        container = _card_container(anchor)
        rows.append(extract_card_fields(container, name, slug, entry))
        visit_hrefs.append(_find_visit_href(container))
    return rows, visit_hrefs


# ---------------------------------------------------------------------------
# Website resolution
# ---------------------------------------------------------------------------
def _extract_dest_from_redirect(href):
    """
    Clutch's Visit Website link is https://r.clutch.co/redirect?...&u=<real site>
    (and also carries provider_website=<domain>). Pull the destination straight
    from the query params - no navigation, no tabs. Return '' if none.
    """
    if not href:
        return ""
    try:
        q = parse_qs(urlparse(href).query)
    except Exception:
        return ""
    for key in ("u", "url", "provider_website"):
        vals = q.get(key)
        if not vals or not vals[0]:
            continue
        val = unquote(vals[0]).strip()
        if not val.startswith("http"):
            val = "https://" + val
        try:
            netloc = urlparse(val).netloc
        except Exception:
            continue
        if val.startswith("http") and netloc and "clutch.co" not in netloc:
            return val
    return ""


def resolve_website(context, visit_href, clutch_url, logger, allow_profile_fallback=True):
    """
    Resolve the real website WITHOUT opening tabs where possible:
      1) read the destination embedded in the redirect link (?u=/provider_website),
      2) if the href is already a direct non-clutch URL, use it,
      3) fallback: open the profile page once and read its redirect link's ?u=.
    Return '' if nothing usable (never guess).
    """
    dest = _extract_dest_from_redirect(visit_href)
    if dest:
        return dest

    if visit_href:
        full = urljoin("https://clutch.co", visit_href)
        netloc = urlparse(full).netloc
        if full.startswith("http") and netloc and "clutch.co" not in netloc:
            return full

    if allow_profile_fallback:
        try:
            p = context.new_page()
            p.goto(clutch_url, wait_until="domcontentloaded", timeout=25000)
            html = p.content()
            p.close()
            soup = BeautifulSoup(html, "html.parser")
            for a2 in soup.select("a[href]"):
                if "visit website" in a2.get_text(" ", strip=True).lower():
                    dest = _extract_dest_from_redirect(a2.get("href", ""))
                    if dest:
                        return dest
        except Exception as exc:
            logger.info("  profile fallback failed for %s: %s", clutch_url, exc)
    return ""


# ---------------------------------------------------------------------------
# Scrape one category URL
# ---------------------------------------------------------------------------
def compute_entry_caps(entries):
    """
    Distribute each category's target across its URLs so no single country
    dominates. e.g. digital-marketing target 100 over 4 country URLs -> 25 each;
    sales-consulting 50 over 4 -> 13,13,12,12. Returns {id(entry): cap}.
    """
    from collections import defaultdict
    by_cat = defaultdict(list)
    for e in entries:
        by_cat[e.get("category", "?")].append(e)

    caps = {}
    for cat, group in by_cat.items():
        target = settings.CLUTCH_CATEGORY_TARGETS.get(cat)
        if target is None:
            target = settings.CLUTCH_TARGET // max(len(by_cat), 1)
        n = len(group)
        base, rem = divmod(target, n)
        for i, e in enumerate(group):
            caps[id(e)] = base + (1 if i < rem else 0)
    return caps


def scrape_url(context, page, entry, rows, limit, logger, entry_cap=None, seen_urls=None):
    """Scrape pages of one URL, appending to rows. Stops at entry_cap for this URL.
    seen_urls dedupes by clutch_url across pages, categories and country batches."""
    base = entry["url"]
    cat = entry.get("category", "?")
    if seen_urls is None:
        seen_urls = set()
    start_count = len(rows)
    logger.info("-" * 70)
    logger.info("Category '%s' | country '%s' | cap %s", cat, entry.get("country", ""), entry_cap)
    logger.info("Base URL: %s", base)

    for page_num in range(MAX_PAGES_PER_URL):
        url = with_page(base, page_num)
        logger.info("Opening page %d: %s", page_num, url)
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=45000)
        except PWTimeout:
            logger.warning("Timeout loading %s - skipping.", url)
            break
        wait_for_cloudflare(page, logger)
        random_delay(logger=logger)

        # let lazy content settle
        try:
            page.wait_for_load_state("networkidle", timeout=8000)
        except PWTimeout:
            pass

        page_rows, visit_hrefs = parse_cards(page.content(), entry, logger)

        if not page_rows:
            if page_num == 0:
                dump_and_report(page, logger, "no provider cards found on first page")
                raise SystemExit(2)
            logger.info("No cards on page %d - end of this category.", page_num)
            break

        new_on_page = sum(1 for r in page_rows if r["clutch_url"] not in seen_urls)
        logger.info("Found %d cards on page %d (%d new). Resolving websites...",
                    len(page_rows), page_num, new_on_page)
        if new_on_page == 0 and page_num > 0:
            logger.info("All cards already seen - end of this URL.")
            break
        for row, visit in zip(page_rows, visit_hrefs):
            if row["clutch_url"] in seen_urls:
                continue
            seen_urls.add(row["clutch_url"])
            row["website"] = resolve_website(context, visit, row["clutch_url"], logger)
            rows.append(row)
            if len(rows) % settings.CHECKPOINT_EVERY == 0:
                save_checkpoint(rows, "clutch", CLUTCH_COLUMNS)
                logger.info("  checkpoint saved (%d rows)", len(rows))
            if limit and len(rows) >= limit:
                logger.info("Reached --limit %d.", limit)
                return
            if entry_cap and (len(rows) - start_count) >= entry_cap:
                logger.info("Reached cap %d for %s/%s.", entry_cap, cat, entry.get("country", ""))
                return
            if len(rows) >= settings.CLUTCH_TARGET:
                logger.info("Reached CLUTCH_TARGET %d.", settings.CLUTCH_TARGET)
                return
        random_delay(logger=logger)


# ---------------------------------------------------------------------------
# Open-tabs mode: scrape whatever the user has filtered in the debug Chrome
# ---------------------------------------------------------------------------
def category_from_url(url):
    """Map a Clutch listing URL to our category key (or '' if not a listing)."""
    if "/profile/" in url:
        return ""
    if "digital-marketing" in url:
        return "digital-marketing"
    if "lead-generation" in url:
        return "lead-generation"
    if "sales-outsourcing" in url:
        return "sales-consulting"  # keep the brief's label for company-type mapping
    return ""


def country_from_url(url):
    """Read the country from any path slug. Clutch is inconsistent: UK is a suffix
    (/agencies/digital-marketing/uk) while CA is a prefix (/ca/agencies/...)."""
    path = urlparse(url).path.lower().strip("/")
    for seg in path.split("/"):
        iso = settings.CLUTCH_COUNTRY_SLUG_TO_ISO.get(seg)
        if iso:
            return iso
    return ""


def find_category_tabs(context, logger, prefer_country=None):
    """Pick the best open tab per category (most-filtered, matching prefer_country)."""
    best = {}
    for pg in context.pages:
        try:
            url = pg.url
        except Exception:
            continue
        cat = category_from_url(url)
        if not cat:
            continue
        country = country_from_url(url)
        score = (3 if (prefer_country and country == prefer_country) else 0)
        score += (1 if country else 0) + (1 if "agency_size" in url else 0)
        if cat not in best or score > best[cat]["score"]:
            best[cat] = {"page": pg, "url": url, "category": cat, "country": country, "score": score}
    tabs = list(best.values())
    logger.info("Open category tabs found: %s",
                {t["category"]: (t["country"] or "?") for t in tabs})
    return tabs


def run_open_tabs(context, rows, seen_urls, args, logger):
    """Scrape the currently-open, already-filtered category tabs for one country."""
    tabs = find_category_tabs(context, logger, prefer_country=args.country)
    if not tabs:
        logger.error("No open Clutch category tabs found. In the debug Chrome, open the "
                     "filtered category pages first, then re-run with --open-tabs.")
        return
    existing_by_cat = Counter(r.get("category", "") for r in rows)
    for tab in tabs:
        cat = tab["category"]
        iso = args.country or tab["country"]
        if not iso:
            logger.warning("No country for %s (url=%s). Pass --country. Skipping.", cat, tab["url"])
            continue
        cat_target = settings.CLUTCH_CATEGORY_TARGETS.get(cat, 0)
        remaining = cat_target - existing_by_cat.get(cat, 0)
        if remaining <= 0:
            logger.info("Category '%s' already at target %d; skipping.", cat, cat_target)
            continue
        per_country = settings.CLUTCH_PER_COUNTRY_TARGETS.get(cat, cat_target)
        cap = min(per_country, remaining)
        entry = {"url": tab["url"], "category": cat, "country": iso}
        logger.info("OPEN-TAB scrape: %s / %s | cap=%d", cat, iso, cap)
        scrape_url(context, tab["page"], entry, rows, args.limit, logger,
                   entry_cap=cap, seen_urls=seen_urls)


# ---------------------------------------------------------------------------
# Profile enrichment: LinkedIn + socials + founded + address (--enrich)
# ---------------------------------------------------------------------------
# Social handles live in the raw HTML/JSON at domcontentloaded (the <a> tags render
# later via JS), so we regex the raw HTML - no render wait needed.
_SOCIAL_RES = {
    "linkedin_url": re.compile(r"linkedin\.com/company/[A-Za-z0-9_\-%.]+"),
    "facebook_url": re.compile(r"facebook\.com/[A-Za-z0-9_\-%.]+"),
    "twitter_url": re.compile(r"(?:twitter\.com|x\.com)/[A-Za-z0-9_]+"),
    "instagram_url": re.compile(r"instagram\.com/[A-Za-z0-9_\-%.]+"),
}


def _pick_social(html, rx):
    """First social handle matched in the raw HTML, excluding Clutch's own."""
    for m in rx.findall(html):
        if "clutch" in m.lower():
            continue
        return "https://www." + m.lstrip("/")
    return ""


def enrich_profile(page, clutch_url, logger):
    """
    Visit a company's Clutch profile; return LinkedIn/socials/founded/address.
    Socials are read by regex from the raw HTML/JSON at domcontentloaded (fast,
    accurate); founded/address come from the rendered text in that same HTML.
    """
    out = {c: "" for c in CLUTCH_ENRICH_COLUMNS}
    try:
        page.goto(clutch_url, wait_until="domcontentloaded", timeout=45000)
    except Exception as exc:
        logger.info("  enrich load failed %s: %s", clutch_url, exc)
        return out
    wait_for_cloudflare(page, logger)
    html = page.content()

    for col, rx in _SOCIAL_RES.items():
        out[col] = _pick_social(html, rx)

    txt = re.sub(r"\s+", " ", BeautifulSoup(html, "html.parser").get_text(" ", strip=True))
    m = re.search(r"Founded ((?:19|20)\d{2})", txt)
    if m:
        out["founded_year"] = m.group(1)
    m = re.search(r"Headquarters\s+(.+?)(?:\s+\d+\s*-\s*\d+\b|\s+Year founded\b|\s+Founded\b|"
                  r"\s+Languages\b|\s+Locations\b|\s+Timezones\b)", txt)
    if m:
        addr = m.group(1).strip(" ,")
        if 8 <= len(addr) <= 120 and "," in addr:
            out["hq_full_address"] = addr
    return out


def run_enrich(context, logger, force=False):
    """Read clutch_raw.csv, visit each profile, add LinkedIn/socials/founded/address."""
    if not settings.CLUTCH_RAW_CSV.exists():
        logger.error("No %s to enrich - scrape first.", settings.CLUTCH_RAW_CSV)
        return
    df = pd.read_csv(settings.CLUTCH_RAW_CSV).fillna("")
    for col in CLUTCH_ENRICH_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    rows = df.to_dict("records")
    page = context.pages[0] if context.pages else context.new_page()

    def needs(r):
        # Resume: skip rows already enriched (ANY enrich field filled). This also
        # retries rows that came back completely empty (e.g. a Cloudflare-blocked
        # load) on a later run, so nothing is silently missed.
        if not r.get("clutch_url"):
            return False
        if force:
            return True
        return not any(str(r.get(c, "")).strip() for c in CLUTCH_ENRICH_COLUMNS)

    todo = [r for r in rows if needs(r)]
    logger.info("Enriching %d / %d profiles (force=%s)...", len(todo), len(rows), force)
    done = 0
    for r in rows:
        if not needs(r):
            continue
        r.update(enrich_profile(page, r["clutch_url"], logger))
        done += 1
        if done % 10 == 0:
            logger.info("  progress %d/%d (last: %.24s | linkedin=%s)", done, len(todo),
                        r.get("company_name", ""), "y" if r.get("linkedin_url") else "n")
        if done % settings.CHECKPOINT_EVERY == 0:
            save_rows_csv(rows, settings.CLUTCH_RAW_CSV, CLUTCH_COLUMNS)
            logger.info("  enrich checkpoint saved (%d done)", done)
        random_delay(1.0, 2.0, logger=logger)  # sped up (Cloudflare still handled per-profile)

    save_rows_csv(rows, settings.CLUTCH_RAW_CSV, CLUTCH_COLUMNS)
    have_li = sum(1 for r in rows if str(r.get("linkedin_url", "")).strip())
    logger.info("=" * 70)
    logger.info("ENRICH DONE. Enriched %d this run. LinkedIn present: %d/%d (%.0f%%). Saved -> %s",
                done, have_li, len(rows), 100.0 * have_li / max(len(rows), 1), settings.CLUTCH_RAW_CSV)
    logger.info("=" * 70)


# ---------------------------------------------------------------------------
# Inspect mode
# ---------------------------------------------------------------------------
def inspect(context, page, entry, logger):
    """Open page 1 of a URL, clear Cloudflare, report title + card count. No scrape."""
    url = with_page(entry["url"], 0)
    logger.info("INSPECT: %s", url)
    page.goto(url, wait_until="domcontentloaded", timeout=45000)
    wait_for_cloudflare(page, logger)
    random_delay(logger=logger)
    try:
        title = page.title()
    except Exception:
        title = "(no title)"
    logger.info("Title: %s", title)
    rows, _ = parse_cards(page.content(), entry, logger)
    logger.info("Provider cards detected: %d", len(rows))
    if rows:
        logger.info("First card parsed: %s", {k: rows[0][k] for k in ("company_name", "clutch_url", "team_size", "hq_country", "review_count")})
    else:
        dump_and_report(page, logger, "inspect found 0 cards")


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
def print_summary(rows, logger):
    logger.info("=" * 70)
    logger.info("CLUTCH SCRAPE SUMMARY")
    logger.info("Total rows scraped: %d", len(rows))
    if not rows:
        logger.info("=" * 70)
        return
    empty_web = sum(1 for r in rows if not r.get("website"))
    logger.info("Rows with empty website: %d", empty_web)
    logger.info("By category: %s", dict(Counter(r.get("category", "") or "(blank)" for r in rows)))
    logger.info("By country:  %s", dict(Counter(r.get("hq_country", "") or "(blank)" for r in rows)))
    logger.info("By team_size: %s", dict(Counter(r.get("team_size", "") or "(blank)" for r in rows)))

    df = pd.DataFrame(rows)
    # category x country crosstab so the spread is easy to eyeball
    try:
        cat = df.get("category", pd.Series(dtype=str)).fillna("").replace("", "(blank)")
        cty = df.get("hq_country", pd.Series(dtype=str)).fillna("").replace("", "(blank)")
        logger.info("category x country:\n%s", pd.crosstab(cat, cty, margins=True, margins_name="Total").to_string())
    except Exception as exc:
        logger.info("crosstab skipped: %s", exc)

    preview_cols = [c for c in ("company_name", "website", "team_size", "hq_country", "review_count") if c in df.columns]
    logger.info("Preview (first 20 rows):\n%s", df[preview_cols].head(20).to_string(index=False))
    logger.info("=" * 70)


# ---------------------------------------------------------------------------
# CDP mode
# ---------------------------------------------------------------------------
def print_cdp_instructions(logger):
    """Tell the user how to launch their real Chrome with remote debugging."""
    logger.info("=" * 70)
    logger.info("CDP MODE: connecting to your REAL Chrome (not Playwright Chromium).")
    logger.info("If the connection fails, do this first, then re-run with --cdp:")
    logger.info("  1) Close ALL Chrome windows completely.")
    logger.info("  2) Launch Chrome with remote debugging (copy/paste this):")
    logger.info('     "%s" --remote-debugging-port=%d --user-data-dir="%s"',
                settings.CHROME_EXE, settings.CHROME_DEBUG_PORT, settings.CHROME_DEBUG_PROFILE)
    logger.info("  3) In that Chrome window, open clutch.co once and clear any Cloudflare check.")
    logger.info("  4) Leave Chrome open and run this script again with --cdp.")
    logger.info("Connecting to %s ...", settings.CDP_ENDPOINT)
    logger.info("=" * 70)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="Clutch scraper (part 2B)")
    ap.add_argument("--limit", type=int, default=None, help="stop after N rows (for testing)")
    ap.add_argument("--resume", action="store_true", help="continue from existing checkpoint")
    ap.add_argument("--inspect", action="store_true", help="open page 1 of each URL and report; no scrape")
    ap.add_argument("--headless", action="store_true", help="override: run headless (default headed)")
    ap.add_argument("--cdp", action="store_true", help="connect to your real Chrome over CDP instead of launching Chromium")
    ap.add_argument("--open-tabs", dest="open_tabs", action="store_true",
                    help="scrape the already-filtered category tabs open in the debug Chrome (implies --cdp)")
    ap.add_argument("--country", default=None, help="ISO country (US/UK/CA/AU) for this --open-tabs batch")
    ap.add_argument("--enrich", action="store_true",
                    help="visit each company's profile to add LinkedIn/socials/founded (implies --cdp)")
    ap.add_argument("--enrich-force", dest="enrich_force", action="store_true",
                    help="re-enrich rows that already have a LinkedIn URL")
    args = ap.parse_args()
    if args.open_tabs or args.enrich or args.enrich_force:
        args.cdp = True  # these modes only make sense against the real Chrome
    if args.enrich_force:
        args.enrich = True

    logger = get_logger("clutch_scraper")
    logger.info("Clutch scraper starting. limit=%s resume=%s inspect=%s cdp=%s open_tabs=%s country=%s enrich=%s",
                args.limit, args.resume, args.inspect, args.cdp, args.open_tabs, args.country, args.enrich)

    # In open-tabs/enrich modes the URLs come from tabs / the CSV, not settings.
    entries = [] if (args.open_tabs or args.enrich) else get_target_urls(logger)
    if not entries and not args.open_tabs and not args.enrich:
        logger.error("No URLs to scrape. Populate settings.CLUTCH_URLS or CLUTCH_CATEGORY_PAGES.")
        return

    # Accumulate across runs for --resume and --open-tabs (country batches).
    rows, seen_urls = [], set()
    if (args.resume or args.open_tabs) and settings.CLUTCH_RAW_CSV.exists():
        rows = pd.read_csv(settings.CLUTCH_RAW_CSV).fillna("").to_dict("records")
        seen_urls = {r.get("clutch_url", "") for r in rows if r.get("clutch_url")}
        logger.info("Loaded %d existing rows to accumulate/dedupe.", len(rows))

    settings.BROWSER_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        if args.cdp:
            # Connect to the user's real Chrome (launched with --remote-debugging-port).
            print_cdp_instructions(logger)
            try:
                browser = pw.chromium.connect_over_cdp(settings.CDP_ENDPOINT)
            except Exception as exc:
                logger.error("Could not connect to Chrome over CDP at %s: %s", settings.CDP_ENDPOINT, exc)
                logger.error("Launch Chrome with --remote-debugging-port=%d first (see instructions above), then re-run with --cdp.",
                             settings.CHROME_DEBUG_PORT)
                return
            context = browser.contexts[0] if browser.contexts else browser.new_context()
            page = context.pages[0] if context.pages else context.new_page()
            logger.info("Connected over CDP. Using existing context with %d page(s).", len(context.pages))
        else:
            # Brief default: launch headed Playwright Chromium with a persistent profile.
            context = pw.chromium.launch_persistent_context(
                user_data_dir=str(settings.BROWSER_PROFILE_DIR),
                headless=args.headless,
                user_agent=settings.USER_AGENT,
                viewport={"width": 1400, "height": 900},
            )
            page = context.pages[0] if context.pages else context.new_page()

        try:
            if args.inspect:
                for entry in entries:
                    inspect(context, page, entry, logger)
                    random_delay(logger=logger)
                return

            if args.enrich:
                run_enrich(context, logger, force=args.enrich_force)
            elif args.open_tabs:
                run_open_tabs(context, rows, seen_urls, args, logger)
            else:
                caps = compute_entry_caps(entries)
                logger.info("Per-URL caps: %s", {f"{e.get('category')}/{e.get('country')}": caps.get(id(e)) for e in entries})
                for entry in entries:
                    scrape_url(context, page, entry, rows, args.limit, logger,
                               entry_cap=caps.get(id(entry)), seen_urls=seen_urls)
                    if args.limit and len(rows) >= args.limit:
                        break
                    if len(rows) >= settings.CLUTCH_TARGET:
                        break
        finally:
            if not args.inspect and not args.enrich:
                save_rows_csv(rows, settings.CLUTCH_RAW_CSV, CLUTCH_COLUMNS)
                logger.info("Saved %d rows -> %s", len(rows), settings.CLUTCH_RAW_CSV)
                print_summary(rows, logger)
            # In CDP mode leave the user's real Chrome open; only close what we launched.
            if args.cdp:
                logger.info("Leaving your Chrome open (CDP). Disconnecting.")
            else:
                context.close()


if __name__ == "__main__":
    main()
