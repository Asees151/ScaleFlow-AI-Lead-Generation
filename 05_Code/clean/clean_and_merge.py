#!/usr/bin/env python3
"""
Step 6 - Clean & Merge (PROJECT_BRIEF.md section 6).

Reads data/raw/crunchbase_raw.csv + data/raw/clutch_raw.csv and produces:
  data/clean/companies_clean.csv          (all clean rows)
  data/clean/companies_clean_top180.csv   (top CLAY_TOP_N by priority_score -> Clay)

Rules: normalize domain (drop rows with none), dedupe by domain (keep Crunchbase,
note the Clutch category), normalize country to ISO (drop others), parse headcount
buckets to min/max ints and keep only rows overlapping 11-200, parse Crunchbase
revenue buckets, tag company_type, compute a priority_score, and print a summary
with a company_type x country crosstab. LinkedIn/socials/founders are carried
through (the "max info" captured during scraping). Never invents data.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402

from config import settings  # noqa: E402
from scrapers.common import clean_domain, get_logger  # noqa: E402

# Master schema = union of both sources, carrying ALL the max-info fields.
# Source-specific fields are simply blank for the other source.
CLEAN_COLUMNS = [
    # identity
    "company_id", "company_name", "domain", "website", "company_type", "source", "source_url",
    # location
    "country", "hq_city", "hq_region", "hq_regions", "hq_full_address",
    # size / revenue
    "headcount_bucket", "headcount_min", "headcount_max",
    "revenue_bucket", "revenue_min", "revenue_max",
    # classification
    "industries_or_category", "primary_industry", "description", "founded_year",
    # contacts / social (max info)
    "linkedin_url", "facebook_url", "twitter_url", "instagram_url",
    # crunchbase-specific
    "last_funding_type", "last_funding_amount", "last_funding_date",
    "founders", "num_founders", "cb_rank", "growth_score_tier", "operating_status",
    # clutch-specific
    "min_project_size", "hourly_rate", "rating", "review_count",
    # scoring
    "priority_score", "notes",
]

US_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID", "IL",
    "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT",
    "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI",
    "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "DC",
}
CA_PROV = {"AB", "BC", "MB", "NB", "NL", "NS", "NT", "NU", "ON", "PE", "QC", "SK", "YT"}


# ---------------------------------------------------------------------------
# Field helpers
# ---------------------------------------------------------------------------
def normalize_country(raw_country):
    """Map a country string (full name, ISO, UK nation, or CA/US region) -> ISO or ''."""
    c = str(raw_country or "").strip()
    cl = c.lower()
    if cl in ("united states", "usa", "us", "u.s.", "u.s.a.", "america"):
        return "US"
    if cl in ("united kingdom", "uk", "u.k.", "great britain", "britain",
              "england", "scotland", "wales", "northern ireland"):
        return "UK"
    if cl in ("canada", "ca"):
        return "CA"
    if cl in ("australia", "au", "aus"):
        return "AU"
    if c in US_STATES:
        return "US"
    if c in CA_PROV:
        return "CA"
    return ""


def parse_headcount_bucket(bucket):
    """'10 - 49'/'101-250'/'1,000+' -> (min, max) ints, or (None, None)."""
    if bucket is None:
        return None, None
    b = str(bucket).replace(",", "").strip()
    if not b:
        return None, None
    if b.endswith("+"):
        m = re.search(r"(\d+)", b)
        return (int(m.group(1)), 999999) if m else (None, None)
    nums = re.findall(r"\d+", b)
    if len(nums) >= 2:
        return int(nums[0]), int(nums[1])
    if len(nums) == 1:
        return int(nums[0]), int(nums[0])
    return None, None


def parse_revenue_bucket(bucket):
    """Crunchbase revenue bucket text -> (min, max) USD ints, or (None, None)."""
    b = str(bucket or "").strip()
    if not b:
        return None, None
    if b in settings.REVENUE_BUCKET_MAP:
        return settings.REVENUE_BUCKET_MAP[b]
    return None, None


def year_only(value):
    m = re.search(r"(19|20)\d{2}", str(value or ""))
    return m.group(0) if m else ""


def to_int(value):
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Row builders (raw -> unified clean row)
# ---------------------------------------------------------------------------
def base_row():
    return {c: "" for c in CLEAN_COLUMNS}


def build_from_crunchbase(r):
    row = base_row()
    row["company_name"] = str(r.get("company_name", "")).strip()
    row["website"] = str(r.get("website", "")).strip()
    row["linkedin_url"] = str(r.get("linkedin_url", "")).strip()
    row["facebook_url"] = str(r.get("facebook_url", "")).strip()
    row["company_type"] = settings.COMPANY_TYPE_SAAS
    row["source"] = "crunchbase"
    row["source_url"] = str(r.get("crunchbase_url", "")).strip()
    row["hq_city"] = str(r.get("hq_city", "")).strip()
    row["hq_region"] = str(r.get("hq_region", "")).strip()
    row["_raw_country"] = str(r.get("hq_country", "")).strip()
    row["hq_regions"] = str(r.get("hq_regions", "")).strip()
    row["headcount_bucket"] = str(r.get("employee_range", "")).strip()
    row["revenue_bucket"] = str(r.get("revenue_range", "")).strip()
    row["industries_or_category"] = str(r.get("industries", "")).strip()
    row["primary_industry"] = str(r.get("primary_industry", "")).strip()
    row["description"] = str(r.get("description", "")).strip()
    row["founded_year"] = year_only(r.get("founded_year", ""))
    row["last_funding_type"] = str(r.get("last_funding_type", "")).strip()
    row["last_funding_amount"] = str(r.get("last_funding_amount", "")).strip()
    row["last_funding_date"] = str(r.get("last_funding_date", "")).strip()
    row["founders"] = str(r.get("founders", "")).strip()
    row["num_founders"] = str(r.get("num_founders", "")).strip()
    row["cb_rank"] = str(r.get("cb_rank", "")).strip()
    row["growth_score_tier"] = str(r.get("growth_score_tier", "")).strip()
    row["operating_status"] = str(r.get("operating_status", "")).strip()
    return row


def build_from_clutch(r):
    row = base_row()
    row["company_name"] = str(r.get("company_name", "")).strip()
    row["website"] = str(r.get("website", "")).strip()
    row["linkedin_url"] = str(r.get("linkedin_url", "")).strip()
    row["facebook_url"] = str(r.get("facebook_url", "")).strip()
    row["twitter_url"] = str(r.get("twitter_url", "")).strip()
    row["instagram_url"] = str(r.get("instagram_url", "")).strip()
    category = str(r.get("category", "")).strip()
    row["company_type"] = settings.CLUTCH_CATEGORY_TO_TYPE.get(category, "")
    row["source"] = "clutch"
    row["source_url"] = str(r.get("clutch_url", "")).strip()
    row["hq_city"] = str(r.get("hq_city", "")).strip()
    row["hq_region"] = str(r.get("hq_region", "")).strip()
    row["hq_full_address"] = str(r.get("hq_full_address", "")).strip()
    row["_raw_country"] = str(r.get("hq_country", "")).strip()
    row["headcount_bucket"] = str(r.get("team_size", "")).strip()
    row["industries_or_category"] = category
    row["description"] = str(r.get("tagline", "")).strip()
    row["founded_year"] = year_only(r.get("founded_year", ""))
    row["min_project_size"] = str(r.get("min_project_size", "")).strip()
    row["hourly_rate"] = str(r.get("hourly_rate", "")).strip()
    row["rating"] = str(r.get("rating", "")).strip()
    row["review_count"] = str(r.get("review_count", "")).strip()
    return row


def priority_score(row):
    score = 0
    hmin, hmax = row["headcount_min"], row["headcount_max"]
    if hmin is not None and hmax is not None:
        if hmin >= settings.HEADCOUNT_TARGET_MIN and hmax <= settings.HEADCOUNT_TARGET_MAX:
            score += 2
        elif hmax >= settings.HEADCOUNT_TARGET_MIN and hmin <= settings.HEADCOUNT_TARGET_MAX:
            score += 1
    rmin, rmax = row["revenue_min"], row["revenue_max"]
    if rmin is not None and rmax is not None:
        if rmin >= settings.REVENUE_TARGET_MIN and rmax <= settings.REVENUE_TARGET_MAX:
            score += 1
    if row["source"] == "crunchbase" and row["last_funding_type"]:
        score += 1
    if row["source"] == "clutch":
        rc = to_int(row["review_count"])
        if rc is not None and rc >= 5:
            score += 1
    return score


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    logger = get_logger("clean_and_merge")
    drops = {"no_domain": {"crunchbase": 0, "clutch": 0},
             "country": {"crunchbase": 0, "clutch": 0},
             "headcount": {"crunchbase": 0, "clutch": 0},
             "duplicate": {"crunchbase": 0, "clutch": 0}}
    rows_in = {"crunchbase": 0, "clutch": 0}

    unified = []
    for path, builder, src in (
        (settings.CRUNCHBASE_RAW_CSV, build_from_crunchbase, "crunchbase"),
        (settings.CLUTCH_RAW_CSV, build_from_clutch, "clutch"),
    ):
        if not path.exists():
            logger.warning("Missing %s - skipping %s.", path, src)
            continue
        df = pd.read_csv(path).fillna("")
        rows_in[src] = len(df)
        logger.info("Loaded %d rows from %s", len(df), src)
        for _, r in df.iterrows():
            unified.append(builder(r))

    # 1) domain + drop no-domain
    kept = []
    for row in unified:
        row["domain"] = clean_domain(row["website"])
        if not row["domain"]:
            drops["no_domain"][row["source"]] += 1
            continue
        kept.append(row)

    # 2) country normalize + drop others
    kept2 = []
    for row in kept:
        row["country"] = normalize_country(row.pop("_raw_country", ""))
        if row["country"] not in settings.ALLOWED_COUNTRIES:
            drops["country"][row["source"]] += 1
            continue
        kept2.append(row)

    # 3) headcount parse + keep only overlapping 11-200
    kept3 = []
    for row in kept2:
        hmin, hmax = parse_headcount_bucket(row["headcount_bucket"])
        row["headcount_min"], row["headcount_max"] = hmin, hmax
        overlaps = (hmin is not None and hmax is not None
                    and hmax >= settings.HEADCOUNT_TARGET_MIN
                    and hmin <= settings.HEADCOUNT_TARGET_MAX)
        if not overlaps:
            drops["headcount"][row["source"]] += 1
            continue
        rmin, rmax = parse_revenue_bucket(row["revenue_bucket"])
        row["revenue_min"], row["revenue_max"] = rmin, rmax
        kept3.append(row)

    # 4) dedupe by domain (keep crunchbase; fold clutch category into notes)
    by_domain = {}
    order = []
    for row in kept3:
        d = row["domain"]
        if d not in by_domain:
            by_domain[d] = row
            order.append(d)
            continue
        existing = by_domain[d]
        keep, drop = (existing, row)
        if existing["source"] == "clutch" and row["source"] == "crunchbase":
            keep, drop = row, existing  # prefer crunchbase
            by_domain[d] = keep
        note = f"dup:{drop['source']}"
        if drop["source"] == "clutch" and drop["industries_or_category"]:
            note += f"({drop['industries_or_category']})"
        keep["notes"] = (keep["notes"] + "; " + note).strip("; ")
        drops["duplicate"][drop["source"]] += 1
    deduped = [by_domain[d] for d in order]

    # 5) priority score + sort
    for row in deduped:
        row["priority_score"] = priority_score(row)
    deduped.sort(key=lambda r: (r["priority_score"],
                                to_int(r["review_count"]) or 0), reverse=True)

    # 6) company_id + finalize
    for i, row in enumerate(deduped, 1):
        row["company_id"] = f"c{i:04d}"

    df_out = pd.DataFrame(deduped)
    for c in CLEAN_COLUMNS:
        if c not in df_out.columns:
            df_out[c] = ""
    df_out = df_out[CLEAN_COLUMNS]
    settings.CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    df_out.to_csv(settings.COMPANIES_CLEAN_CSV, index=False, encoding="utf-8-sig")
    top = df_out.head(settings.CLAY_TOP_N)
    top.to_csv(settings.COMPANIES_CLEAN_TOP_CSV, index=False, encoding="utf-8-sig")

    print_summary(rows_in, drops, deduped, df_out, top, logger)


def print_summary(rows_in, drops, deduped, df_out, top, logger):
    logger.info("=" * 70)
    logger.info("CLEAN & MERGE SUMMARY")
    for src in ("crunchbase", "clutch"):
        out = sum(1 for r in deduped if r["source"] == src)
        logger.info("  %-11s rows in: %4d -> out: %4d", src, rows_in[src], out)
    logger.info("  dropped no-domain:      %s", dict(drops["no_domain"]))
    logger.info("  dropped country-not-in: %s", dict(drops["country"]))
    logger.info("  dropped headcount-oob:  %s", dict(drops["headcount"]))
    logger.info("  dropped duplicate:      %s", dict(drops["duplicate"]))
    logger.info("  TOTAL clean rows: %d  (top %d -> %s)",
                len(df_out), len(top), settings.COMPANIES_CLEAN_TOP_CSV.name)
    logger.info("  LinkedIn present: %d / %d",
                (df_out["linkedin_url"].astype(str).str.len() > 0).sum(), len(df_out))

    logger.info("company_type x country:\n%s",
                pd.crosstab(df_out["company_type"], df_out["country"],
                            margins=True, margins_name="Total").to_string())
    logger.info("priority_score distribution: %s",
                dict(df_out["priority_score"].value_counts().sort_index(ascending=False)))
    logger.info("Top 10 preview:\n%s",
                df_out.head(10)[["company_id", "company_name", "domain", "company_type",
                                 "country", "headcount_bucket", "priority_score"]].to_string(index=False))
    logger.info("=" * 70)


if __name__ == "__main__":
    main()
