#!/usr/bin/env python3
"""
Hiring-signal enrichment via Apify actor valig/linkedin-jobs-scraper.

Finds which of our companies are actively hiring SDR/BDR/Outbound/Growth/GTM roles
on LinkedIn in the last 30 days, and writes hiring_signal / hiring_job_title /
hiring_date / linkedin_post_url... no -> the Clay columns hiring_signal,
hiring_job_title, hiring_date into data/people/clay_ready_leads.csv.

Matching: jobs are tied to our companies by **LinkedIn company URL slug** (the job's
`companyUrl` vs our `company_linkedin_url`), lightly normalized (strip corp suffixes),
so we DON'T get false positives from same-named companies (e.g. "Blacksmith Agency").

Cost: $0.0004/result. `--limit 1000` = $0.40 max. Key via APIFY_JOBS_KEY in .env or --key.

Usage:
  python scripts/find_hiring_signal.py --limit 40      # cheap test
  python scripts/find_hiring_signal.py --limit 1000    # full ($0.40)
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import pandas as pd  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

ACTOR = "valig~linkedin-jobs-scraper"
LEADS = ROOT / "data/people/clay_ready_leads.csv"
JOBS_OUT = ROOT / "data/people/hiring_signal_jobs.csv"
TITLE_INCLUDE = ["sales development representative", "sdr", "business development representative",
                 "bdr", "outbound", "growth", "gtm", "go to market"]
CORE_SALES = ("sdr", "bdr", "sales development", "business development representative", "outbound")
_SUFFIX = re.compile(r"(inc|llc|ltd|limited|co|corp|company|group|hq|the)$")


def norm_slug(url):
    m = re.search(r"/company/([^/?#]+)", str(url or ""))
    if not m:
        return ""
    s = re.sub(r"[^a-z0-9]", "", m.group(1).lower())
    prev = None
    while s != prev:                       # strip repeated corp suffixes
        prev = s
        s = _SUFFIX.sub("", s)
    return s


def get_key(args):
    if args.key:
        return args.key
    load_dotenv(ROOT / ".env")
    return os.environ.get("APIFY_JOBS_KEY") or os.environ.get("APIFY_TOKEN")


def _get(url, timeout=30, retries=5, data=None, method="GET"):
    """HTTP GET/POST that retries on transient timeouts instead of crashing."""
    hdr = {"Content-Type": "application/json"} if data is not None else {}
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, data=data, headers=hdr, method=method)
            return json.loads(urllib.request.urlopen(req, timeout=timeout).read())
        except Exception as exc:                       # noqa: BLE001 - timeout / transient net
            if attempt < retries - 1:
                time.sleep(4 * (attempt + 1))
                continue
            raise exc


def run_actor(key, company_names, limit):
    inp = {"companyName": company_names, "titleInclude": TITLE_INCLUDE,
           "datePosted": "r2592000", "limit": limit}
    start = f"https://api.apify.com/v2/acts/{ACTOR}/runs?token={key}"
    run = _get(start, timeout=60, data=json.dumps(inp).encode(), method="POST")["data"]
    run_id, ds = run["id"], run["defaultDatasetId"]
    print(f"run {run_id} started (limit {limit}); polling...")
    waited = 0
    while True:
        time.sleep(6)
        waited += 6
        st = _get(f"https://api.apify.com/v2/actor-runs/{run_id}?token={key}", timeout=30)["data"]
        if st["status"] in ("SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"):
            print("  run status:", st["status"], "| cost USD:", st.get("usageTotalUsd"))
            break
        if waited > 420:                               # 7-min safety cap per batch
            print("  poll timeout (>7min); moving on")
            break
    return _get(f"https://api.apify.com/v2/datasets/{ds}/items?token={key}&clean=true", timeout=90)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=1000)
    ap.add_argument("--key", default=None)
    args = ap.parse_args()
    key = get_key(args)
    if not key:
        sys.exit("ERROR: no Apify key (pass --key or set APIFY_JOBS_KEY in .env)")

    df = pd.read_csv(LEADS).fillna("")
    companies = df.drop_duplicates("company_name")[["company_name", "company_linkedin_url", "domain"]].copy()
    companies["nslug"] = companies["company_linkedin_url"].map(norm_slug)
    slug_to_name = {r["nslug"]: r["company_name"] for _, r in companies.iterrows() if r["nslug"]}

    # Passing all names at once breaks the actor -> batch in groups of 10 (the size
    # that reliably returns per-company jobs), aggregate, stop at the total limit.
    names = companies["company_name"].tolist()
    BATCH = 10
    items = []
    nbatches = (len(names) + BATCH - 1) // BATCH
    for i in range(0, len(names), BATCH):
        batch = names[i:i + BATCH]
        try:
            it = run_actor(key, batch, min(200, args.limit))
        except Exception as exc:                       # noqa: BLE001 - skip a bad batch
            print(f"  batch {i // BATCH + 1}/{nbatches} FAILED ({exc}); skipping")
            continue
        items.extend(it)
        print(f"  batch {i // BATCH + 1}/{nbatches}: +{len(it)} jobs (total {len(items)})")
        if len(items) >= args.limit:
            break
    print(f"returned {len(items)} jobs total")

    # match jobs -> our companies by normalized company URL slug
    per_co = {}
    for it in items:
        js = norm_slug(it.get("companyUrl"))
        if js and js in slug_to_name:
            per_co.setdefault(slug_to_name[js], []).append({
                "title": it.get("title", ""), "date": str(it.get("postedDate", ""))[:10],
                "url": it.get("url", "")})

    def best(jobs):                        # prefer a core-sales role, then most recent
        core = [j for j in jobs if any(k in j["title"].lower() for k in CORE_SALES)]
        pick = sorted(core or jobs, key=lambda j: j["date"], reverse=True)[0]
        return pick

    # write signal into the leads (per company; applies to all that company's contacts)
    df["hiring_signal"] = "No"
    df["hiring_job_title"] = ""
    df["hiring_date"] = ""
    df["hiring_job_url"] = ""
    for co, jobs in per_co.items():
        b = best(jobs)
        m = df["company_name"] == co
        df.loc[m, "hiring_signal"] = "Yes"
        df.loc[m, "hiring_job_title"] = b["title"]
        df.loc[m, "hiring_date"] = b["date"]
        df.loc[m, "hiring_job_url"] = b["url"]
    df.to_csv(LEADS, index=False, encoding="utf-8")

    # save all matched jobs for reference
    rows = [{"company_name": co, **j} for co, js in per_co.items() for j in js]
    if rows:
        pd.DataFrame(rows).to_csv(JOBS_OUT, index=False, encoding="utf-8")
    print("=" * 60)
    print(f"OUR companies hiring (SDR/BDR/Outbound/Growth/GTM, 30d): {len(per_co)} of {companies['nslug'].ne('').sum()} (with LinkedIn URL)")
    for co, js in list(per_co.items())[:20]:
        print(f"   {co}: {len(js)} job(s) - e.g. {best(js)['title']} ({best(js)['date']})")
    print("=" * 60)


if __name__ == "__main__":
    main()
