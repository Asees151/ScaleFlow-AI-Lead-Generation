"""
Central config for the ScaleFlow AI lead pipeline (parts 1 and 2).

Everything tunable lives here: search URLs, target row counts, delays, paths,
and the ICP filter buckets. Nothing else in the repo should hardcode these.

HOW TO FILL THE PLACEHOLDERS
----------------------------
1. Set the Crunchbase filters manually in your logged-in browser, then copy the
   resulting results-page URL into CRUNCHBASE_SEARCH_URL below.
2. Apply Team Size + Location filters on each Clutch category page in the browser,
   then paste each resulting URL into CLUTCH_URLS below (one per category/country).

Do NOT try to build filters through the UI with code — the URL carries the state.
"""

from pathlib import Path

# ---------------------------------------------------------------------------
# Paths (absolute, derived from this file's location)
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
CLEAN_DIR = DATA_DIR / "clean"
CHECKPOINT_DIR = DATA_DIR / "checkpoints"
LOGS_DIR = BASE_DIR / "logs"
BROWSER_PROFILE_DIR = BASE_DIR / "browser_profile"

CRUNCHBASE_RAW_CSV = RAW_DIR / "crunchbase_raw.csv"
CLUTCH_RAW_CSV = RAW_DIR / "clutch_raw.csv"
COMPANIES_CLEAN_CSV = CLEAN_DIR / "companies_clean.csv"
COMPANIES_CLEAN_TOP_CSV = CLEAN_DIR / "companies_clean_top180.csv"

# ---------------------------------------------------------------------------
# Scrape targets (row counts). Scrapers stop at these.
# ---------------------------------------------------------------------------
CRUNCHBASE_TARGET = 2000  # user: scrape up to 2000; --cdp resumes from existing CSV
CLUTCH_TARGET = 4000  # user: up to 1000/country x 4; take max available if fewer

# Per-category ceilings across all countries (2:2:1 ratio, 400/400/200 per country x 4).
CLUTCH_CATEGORY_TARGETS = {
    "digital-marketing": 1600,
    "lead-generation": 1600,
    "sales-consulting": 800,
}

# Final Clay-bound cut size.
CLAY_TOP_N = 180

# ---------------------------------------------------------------------------
# Politeness / anti-block
# ---------------------------------------------------------------------------
DELAY_MIN_SECONDS = 4.0        # user override: 4-7s between page loads (brief said 2-5)
DELAY_MAX_SECONDS = 7.0
COMPANY_PAGE_DELAY_MIN = 3.0   # slower when opening individual company pages
COMPANY_PAGE_DELAY_MAX = 5.0
CHECKPOINT_EVERY = 25          # save a partial CSV every N rows
CLOUDFLARE_WAIT_SECONDS = 20   # max wait for Clutch "checking your browser"

# ---------------------------------------------------------------------------
# Crunchbase (part 2A)
# ---------------------------------------------------------------------------
# PLACEHOLDER — paste your saved Discover > Companies search URL here after
# setting Industries / Employees / Location / Revenue / Active filters manually.
CRUNCHBASE_SEARCH_URL = ""

# ---------------------------------------------------------------------------
# Clutch (part 2B)
# ---------------------------------------------------------------------------
# Base category pages, VERIFIED live on 2026-09-10 via CDP (card counts in comments).
# NOTE: the brief's /agencies/lead-generation and /agencies/sales-outsourcing both
# 404; Clutch actually files these under /call-centers/. Corrected below.
CLUTCH_CATEGORY_PAGES = {
    "digital-marketing": "https://clutch.co/agencies/digital-marketing",      # 72 cards
    "lead-generation": "https://clutch.co/call-centers/lead-generation",      # 64 cards
    "sales-consulting": "https://clutch.co/call-centers/sales-outsourcing",   # 58 cards
}

# PLACEHOLDER — after applying Team Size + Location filters in the browser,
# paste each filtered results URL here. Up to ~12 entries (category x country).
# Each entry: {"url": "...", "category": "digital-marketing", "country": "US"}
CLUTCH_URLS = [
    # {"url": "", "category": "digital-marketing", "country": "US"},
]

# "Rotate the location filter" workflow (--open-tabs): you set the country filter
# in the browser, the scraper reads each open tab's already-filtered URL. Clutch
# puts the country in the URL PATH (e.g. /agencies/digital-marketing/uk) and team
# size in ?agency_size=. Per-country caps ~= CLUTCH_CATEGORY_TARGETS / 4 countries.
CLUTCH_PER_COUNTRY_TARGETS = {
    "digital-marketing": 400,
    "lead-generation": 400,
    "sales-consulting": 200,
}

# Clutch location path-slug -> ISO code we store.
CLUTCH_COUNTRY_SLUG_TO_ISO = {
    "us": "US", "united-states": "US",
    "uk": "UK", "united-kingdom": "UK", "gb": "UK",
    "canada": "CA", "ca": "CA",
    "australia": "AU", "au": "AU",
}

# ---------------------------------------------------------------------------
# ICP filter buckets (used by the cleaning step)
# ---------------------------------------------------------------------------
HEADCOUNT_TARGET_MIN = 11
HEADCOUNT_TARGET_MAX = 200

REVENUE_TARGET_MIN = 500_000
REVENUE_TARGET_MAX = 20_000_000

# Accepted geographies -> ISO code used in the clean file.
ALLOWED_COUNTRIES = {"US", "UK", "CA", "AU"}

# Crunchbase revenue bucket text -> (min_usd, max_usd)
REVENUE_BUCKET_MAP = {
    "Less than $1M": (0, 1_000_000),
    "$1M to $10M": (1_000_000, 10_000_000),
    "$10M to $50M": (10_000_000, 50_000_000),
    "$50M to $100M": (50_000_000, 100_000_000),
}

# Company type labels.
COMPANY_TYPE_SAAS = "B2B SaaS"
CLUTCH_CATEGORY_TO_TYPE = {
    "digital-marketing": "Digital Marketing Agency",
    "lead-generation": "Lead Generation Agency",
    "sales-consulting": "Sales Consulting",
}

# ---------------------------------------------------------------------------
# Browser
# ---------------------------------------------------------------------------
HEADLESS = False  # brief requires headed mode for both sites
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)

# ---------------------------------------------------------------------------
# CDP mode (--cdp): connect to your REAL Chrome instead of Playwright Chromium.
# Cloudflare fingerprints the bundled Chromium, so use a genuine Chrome you drive.
# Launch Chrome first (all windows closed) with:
#   "C:\Program Files\Google\Chrome\Application\chrome.exe" \
#       --remote-debugging-port=9222 --user-data-dir="C:\chrome-scrape-profile"
# ---------------------------------------------------------------------------
CDP_ENDPOINT = "http://localhost:9222"
# NOTE: on this machine Chrome is under "Program Files (x86)", not "Program Files".
CHROME_EXE = r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
CHROME_DEBUG_PROFILE = r"C:\chrome-scrape-profile"
CHROME_DEBUG_PORT = 9222
