#!/usr/bin/env python3
"""
scripts/find_people.py - find decision-makers per company via the Apify actor
braveleads/leads-finder-linkedin-apollo-leads-generator (id jGzQBaO651moSvamI).

Reads company domains from data/clean/, runs the actor (cost-capped at
MAX_CHARGE_USD), saves raw people to data/people/apify_people_raw.csv, then builds
data/people/decision_makers.csv (person rows, seniority-ranked, per-company
has_vp_of_sales).

Setup: pip install apify-client python-dotenv pandas
       .env at repo root must contain:  APIFY_TOKEN=<your token>

Usage:
  python scripts/find_people.py --schema-only   # fetch + confirm input schema; NO run, NO cost
  python scripts/find_people.py                 # run the actor (charges Apify, capped) + build
  python scripts/find_people.py --build-only     # just rebuild decision_makers.csv from saved raw
  python scripts/find_people.py --input data/clean/companies_with_full_info.csv
"""
import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402
from dotenv import load_dotenv  # noqa: E402
from apify_client import ApifyClient  # noqa: E402

# Windows consoles default to cp1252; force UTF-8 so emoji/accents in lead data
# don't crash prints.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ACTOR_ID = "jGzQBaO651moSvamI"
MAX_CHARGE_USD = 3.0          # GLOBAL budget across all batches
MAX_RESULTS = 1000
BATCH_SIZE = 10               # actor limit: companyDomain must have <= 10 items
MAX_RESULTS_PER_RUN = 100     # cap per batch of 10 companies (decision-makers only)
EMPTY_STREAK_STOP = 6         # stop after N consecutive batches with no NEW leads
                              # (the actor charges a base fee per run even on 0 results)

PERSON_TITLES = [
    "founder", "co-founder", "ceo", "head of sales", "vp sales", "vp of sales",
    "sales director", "head of growth", "vp growth", "revops manager",
    "revenue operations manager",
]
SENIORITY = ["owner", "founder", "c_suite", "vp", "head", "director", "manager"]

# Input company files, in priority order (batch files if present, else full-info).
BATCH_FILES = [ROOT / "data/clean/companies_clean_batch1.csv",
               ROOT / "data/clean/companies_clean_batch2.csv"]
FALLBACK_FILE = ROOT / "data/clean/companies_with_full_info.csv"

RAW_OUT = ROOT / "data/people/apify_people_raw.csv"
DM_OUT = ROOT / "data/people/decision_makers.csv"


# ---------------------------------------------------------------------------
# Client + schema
# ---------------------------------------------------------------------------
def load_client():
    load_dotenv(ROOT / ".env")
    token = os.environ.get("APIFY_TOKEN")
    if not token:
        sys.exit("ERROR: APIFY_TOKEN not found. Create a .env at the repo root with "
                 "APIFY_TOKEN=<your token>.")
    return ApifyClient(token)


def to_dict(obj):
    """apify-client 3.x returns pydantic models; normalize to a plain dict (API camelCase)."""
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "model_dump"):
        try:
            return obj.model_dump(by_alias=True)
        except Exception:
            return obj.model_dump()
    return dict(getattr(obj, "__dict__", {}) or {})


def fetch_input_schema(token):
    """Fetch the actor's input-schema properties via the HTTP API (returns plain dicts)."""
    import urllib.request
    base = "https://api.apify.com/v2/acts/" + ACTOR_ID
    hdr = {"Authorization": "Bearer " + token}
    actor = json.loads(urllib.request.urlopen(urllib.request.Request(base, headers=hdr), timeout=25).read())["data"]
    bid = (actor.get("taggedBuilds") or {}).get("latest", {}).get("buildId")
    if not bid:
        return {}
    b = json.loads(urllib.request.urlopen(urllib.request.Request(base + "/builds/" + bid, headers=hdr), timeout=25).read())["data"]
    schema = b.get("inputSchema")
    if isinstance(schema, str):
        schema = json.loads(schema)
    return (schema or {}).get("properties", {})


def resolve_fields(props):
    """Map our intended fields to the actor's real field names + report types."""
    names = list(props.keys())
    print("Actor input fields:")
    for n in names:
        p = props[n]
        print(f"   - {n}  (type={p.get('type')}, editor={p.get('editor')})")
    wanted = {
        "maxResults": ["maxResults", "max_results", "maxItems", "limit", "maxLeads", "totalRecords", "count"],
        "personTitle": ["personTitles", "personTitle", "titles", "jobTitles", "jobTitle", "title"],
        "seniority": ["seniorities", "seniority", "seniorityLevel", "managementLevel", "seniorityLevels"],
        "companyDomain": ["companyDomains", "companyDomain", "domains", "organizationDomains", "domain", "companyDomainList"],
    }
    resolved = {}
    print("Field mapping:")
    for key, cands in wanted.items():
        found = next((c for c in cands if c in props), None)
        if not found:
            found = next((n for n in names if key.lower().rstrip("s") in n.lower()), None)
        resolved[key] = found
        print(f"   {key:13} -> {found or 'NOT FOUND (check schema above!)'}")
    return resolved


# ---------------------------------------------------------------------------
# Domains
# ---------------------------------------------------------------------------
def load_companies(input_path):
    if input_path:
        files = [Path(input_path)]
    elif all(p.exists() for p in BATCH_FILES):
        files = BATCH_FILES
    elif FALLBACK_FILE.exists():
        files = [FALLBACK_FILE]
    else:
        sys.exit("ERROR: no input company file found in data/clean/.")
    frames = [pd.read_csv(f).fillna("") for f in files]
    companies = pd.concat(frames).drop_duplicates("domain")
    domains = [d.strip() for d in companies["domain"].astype(str) if d.strip()]
    print(f"Companies from {[str(f.name) for f in files]}: {len(companies)} rows, {len(domains)} domains")
    return companies, domains


# ---------------------------------------------------------------------------
# Run the actor
# ---------------------------------------------------------------------------
def run_batches(client, resolved, domains, max_batches=None):
    """
    Run the actor in batches of <=10 domains (its companyDomain limit), tracking
    cumulative spend and stopping at the GLOBAL MAX_CHARGE_USD budget. Each run is
    itself capped at the remaining budget, so we can never exceed it. Saves the raw
    people after every batch (so a mid-run stop still keeps progress).
    max_batches: optional cap on number of batches (for a cheap test run).
    """
    dom_f = resolved["companyDomain"] or "companyDomain"
    max_f = resolved["maxResults"] or "maxResults"
    title_f = resolved["personTitle"] or "personTitle"
    sen_f = resolved["seniority"] or "seniority"

    all_items, seen, spent, covered = [], set(), 0.0, set()
    empty_streak = 0
    RAW_OUT.parent.mkdir(parents=True, exist_ok=True)
    # Resume: seed from any existing raw so re-runs skip already-fetched batches.
    if RAW_OUT.exists():
        try:
            prev = pd.read_csv(RAW_OUT).fillna("")
            wcol = pick_col(prev, ["organizationWebsite", "organization_domain", "domain", "website"])
            for _, r in prev.iterrows():
                d = r.to_dict()
                all_items.append(d)
                k = d.get("linkedinUrl") or d.get("email")
                if k:
                    seen.add(k)
                if wcol and d.get(wcol):
                    covered.add(root_domain(d.get(wcol)))
            print(f"Resume: loaded {len(all_items)} existing leads covering {len(covered)} domains.")
        except Exception as exc:
            print(f"(could not seed from existing raw: {exc})")

    n_batches = (len(domains) + BATCH_SIZE - 1) // BATCH_SIZE
    print(f"Batching {len(domains)} domains -> {n_batches} runs of <={BATCH_SIZE}, budget ${MAX_CHARGE_USD}")

    for bi in range(n_batches):
        if max_batches is not None and bi >= max_batches:
            print(f"Reached --max-batches {max_batches}; stopping (test mode).")
            break
        remaining = MAX_CHARGE_USD - spent
        if remaining <= 0.02:
            print(f"Budget ${MAX_CHARGE_USD} reached (spent ${spent:.3f}); stopping after {bi} batches.")
            break
        batch = domains[bi * BATCH_SIZE:(bi + 1) * BATCH_SIZE]
        if batch and all(d in covered for d in batch):
            continue  # every domain in this batch already fetched by a previous run
        run_input = {"onlycompany": False, dom_f: batch, max_f: MAX_RESULTS_PER_RUN,
                     title_f: PERSON_TITLES, sen_f: SENIORITY}
        try:
            run = client.actor(ACTOR_ID).call(run_input=run_input,
                                              max_total_charge_usd=round(remaining, 3))
        except Exception as exc:
            print(f"  batch {bi + 1}/{n_batches} FAILED: {exc}")
            continue
        rd = to_dict(run)
        try:
            cost = float(rd.get("usageTotalUsd") or 0)
        except (TypeError, ValueError):
            cost = 0.0
        spent += cost
        items = to_dict(client.dataset(rd.get("defaultDatasetId")).list_items()).get("items", [])
        new = 0
        for it in items:
            key = it.get("linkedinUrl") or it.get("email") or json.dumps(it, sort_keys=True)[:150]
            if key in seen:
                continue
            seen.add(key)
            all_items.append(it)
            new += 1
            wcol = it.get("organizationWebsite") or ""
            if wcol:
                covered.add(root_domain(wcol))
        print(f"  batch {bi + 1}/{n_batches} ({len(batch)} dom): +{new} leads | "
              f"cost ${cost:.3f} | cumulative ${spent:.3f} | total {len(all_items)}")
        pd.DataFrame(all_items).to_csv(RAW_OUT, index=False, encoding="utf-8-sig")
        empty_streak = empty_streak + 1 if new == 0 else 0
        if empty_streak >= EMPTY_STREAK_STOP:
            print(f"{EMPTY_STREAK_STOP} consecutive batches with no new leads - stopping to save budget "
                  f"(spent ${spent:.3f}).")
            break

    raw = pd.DataFrame(all_items)
    raw.to_csv(RAW_OUT, index=False, encoding="utf-8-sig")
    print("=" * 70)
    print(f"ACTOR DONE. {len(raw)} leads total, spent ${spent:.3f} of ${MAX_CHARGE_USD}")
    if not raw.empty:
        print("columns:", raw.columns.tolist())
    return raw


# ---------------------------------------------------------------------------
# Build decision_makers.csv
# ---------------------------------------------------------------------------
def pick_col(df, candidates):
    lower = {c.lower(): c for c in df.columns}
    for cand in candidates:
        if cand.lower() in lower:
            return lower[cand.lower()]
    for cand in candidates:  # loose contains
        for c in df.columns:
            if cand.lower() in c.lower():
                return c
    return None


def root_domain(value):
    from scrapers.common import clean_domain
    v = str(value or "").strip()
    return clean_domain(v) if v else ""


def seniority_rank(title):
    t = str(title or "").lower()
    if any(k in t for k in ("vp sales", "vp of sales", "head of sales", "sales director",
                            "director of sales", "chief revenue", "cro")):
        return 1
    if any(k in t for k in ("head of growth", "vp growth", "vp of growth", "growth",
                            "revops", "revenue operations", "revenue ops")):
        return 2
    if any(k in t for k in ("founder", "co-founder", "cofounder", "ceo",
                            "chief executive", "owner")):
        return 3
    return 4


def build_decision_makers(companies, logger_print=print):
    if not RAW_OUT.exists():
        sys.exit(f"ERROR: {RAW_OUT} not found - run the actor first.")
    raw = pd.read_csv(RAW_OUT).fillna("")
    if raw.empty:
        logger_print("No people returned.")
        return

    name_col = pick_col(raw, ["full_name", "fullName", "name"])
    first_col = pick_col(raw, ["first_name", "firstName"])
    last_col = pick_col(raw, ["last_name", "lastName"])
    title_col = pick_col(raw, ["title", "headline", "job_title", "jobTitle"])
    li_col = pick_col(raw, ["linkedin_url", "linkedinUrl", "linkedin", "person_linkedin_url"])
    email_col = pick_col(raw, ["email", "apify_email", "work_email", "emailAddress"])
    sen_col = pick_col(raw, ["seniority", "seniority_level"])
    dom_col = pick_col(raw, ["organization_domain", "company_domain", "companyDomain",
                             "domain", "organization_website_url", "website_url", "website"])

    dm = pd.DataFrame()
    if name_col:
        dm["full_name"] = raw[name_col]
    elif first_col or last_col:
        dm["full_name"] = (raw.get(first_col, "").astype(str) + " " + raw.get(last_col, "").astype(str)).str.strip()
    else:
        dm["full_name"] = ""
    dm["title"] = raw[title_col] if title_col else ""
    dm["linkedin_url"] = raw[li_col] if li_col else ""
    dm["apify_email"] = raw[email_col] if email_col else ""
    dm["seniority"] = raw[sen_col] if sen_col else ""
    dm["domain"] = raw[dom_col].map(root_domain) if dom_col else ""

    dm["seniority_rank"] = dm["title"].map(seniority_rank)

    # join company_id on domain
    cmap = companies.drop_duplicates("domain").set_index("domain")["company_id"].to_dict()
    dm["company_id"] = dm["domain"].map(cmap).fillna("")

    # per-company has_vp_of_sales (Yes if any person at that domain is rank 1)
    vp_domains = set(dm.loc[dm["seniority_rank"] == 1, "domain"])
    dm["has_vp_of_sales"] = dm["domain"].map(lambda d: "Yes" if d in vp_domains else "No")

    # Keep only real people mapped to one of OUR companies. This drops the actor's
    # promo/support row (empty domain) and any people whose domain didn't match.
    before = len(dm)
    dm = dm[(dm["domain"].astype(str).str.len() > 0)
            & (dm["company_id"].astype(str).str.len() > 0)].copy()
    dropped = before - len(dm)

    cols = ["company_id", "domain", "full_name", "title", "linkedin_url",
            "apify_email", "seniority_rank", "has_vp_of_sales"]
    dm = dm[[c for c in cols if c in dm.columns]]
    DM_OUT.parent.mkdir(parents=True, exist_ok=True)
    dm.to_csv(DM_OUT, index=False, encoding="utf-8-sig")

    companies_with_person = dm["domain"].nunique()
    companies_with_vp = dm.loc[dm["has_vp_of_sales"] == "Yes", "domain"].nunique()
    logger_print("=" * 70)
    logger_print(f"decision_makers.csv: {len(dm)} people across {companies_with_person} companies"
                 f"  (dropped {dropped} promo/unmatched rows)")
    logger_print(f"companies with >=1 person:   {companies_with_person}")
    logger_print(f"companies with has_vp_of_sales=Yes: {companies_with_vp}")
    logger_print(f"with LinkedIn: {(dm['linkedin_url'].astype(str).str.len() > 0).sum()} | "
                 f"with email: {(dm['apify_email'].astype(str).str.len() > 0).sum()}")
    logger_print(f"seniority_rank counts: {dm['seniority_rank'].value_counts().sort_index().to_dict()}")
    logger_print("=" * 70)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="Apify people finder (part of the pipeline)")
    ap.add_argument("--schema-only", action="store_true", help="fetch + print input schema; no run, no cost")
    ap.add_argument("--build-only", action="store_true", help="rebuild decision_makers.csv from saved raw; no run")
    ap.add_argument("--input", default=None, help="company CSV to read domains from")
    ap.add_argument("--max-batches", dest="max_batches", type=int, default=None,
                    help="cap number of 10-domain batches (cheap test run)")
    args = ap.parse_args()

    if args.build_only:
        companies, _ = load_companies(args.input)
        build_decision_makers(companies)
        return

    client = load_client()
    try:
        props = fetch_input_schema(os.environ["APIFY_TOKEN"])
    except Exception as exc:
        print(f"WARN: schema fetch failed ({exc}); using documented field names.")
        props = {}
    if not props:
        print("WARN: could not read input schema; will use the documented field names.")
        resolved = {"maxResults": "maxResults", "personTitle": "personTitle",
                    "seniority": "seniority", "companyDomain": "companyDomain"}
    else:
        resolved = resolve_fields(props)

    if args.schema_only:
        print("\n--schema-only: stopping before the (paid) run.")
        return

    companies, domains = load_companies(args.input)
    run_batches(client, resolved, domains, max_batches=args.max_batches)
    build_decision_makers(companies)


if __name__ == "__main__":
    main()
