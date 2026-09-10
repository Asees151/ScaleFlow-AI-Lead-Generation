#!/usr/bin/env python3
"""
New sales-leader-hire intent signal via Apify harvestapi/linkedin-profile-scraper.

Scrapes the profiles of our sales-leader contacts (Head of Sales / VP Sales / CRO /
Director of Sales / Head of Growth-Revenue-BizDev) and reads their CURRENT-role start
date. A leader who joined recently => the company is actively building GTM => strong
intent for ScaleFlow. Cost $0.004/profile (~$0.20 for 49). Key = APIFY_JOBS_KEY.

Writes company-level: new_sales_hire_signal (Yes/No), new_sales_hire_tier (HIGH<=6mo / MED<=12mo),
new_sales_hire_name, new_sales_hire_role, new_sales_hire_start into clay_ready_leads.csv.

Usage: python scripts/find_new_sales_hire.py [--limit N] [--months 12]
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
import pandas as pd  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

ACTOR = "harvestapi~linkedin-profile-scraper"
LEADS = ROOT / "data/people/clay_ready_leads.csv"
TODAY = datetime(2026, 9, 11)
LEADER = re.compile(r"head of sales|vp.*sales|vice president.*sales|chief revenue|\bcro\b|"
                    r"director.*sales|head of growth|head of revenue|head of business development|"
                    r"vp.*growth|chief commercial", re.I)
MONTHS = {m[:3]: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august",
     "september", "october", "november", "december"], 1)}


def slug_in(u):
    m = re.search(r"/in/([^/?#]+)", str(u or ""))
    return m.group(1).lower() if m else ""


def tenure_from(cand):
    """months in current role — use LinkedIn's `duration` ("1 yr 2 mos") first, then startDate."""
    dur = str(cand.get("duration") or "")
    if dur:
        yr = re.search(r"(\d+)\s*yr", dur)
        mo = re.search(r"(\d+)\s*mo", dur)
        if yr or mo:
            return (int(yr.group(1)) if yr else 0) * 12 + (int(mo.group(1)) if mo else 0)
    sd = cand.get("startDate")
    if not isinstance(sd, dict):
        return None
    y, mo = sd.get("year"), sd.get("month")
    if isinstance(mo, str):
        mo = MONTHS.get(mo.strip().lower()[:3]) or (int(mo) if mo.isdigit() else 1)
    if not y:
        t = str(sd.get("text", "")).strip()
        for fmt in ("%b %Y", "%B %Y", "%Y"):
            try:
                dt = datetime.strptime(t, fmt)
                return (TODAY.year - dt.year) * 12 + (TODAY.month - dt.month)
            except ValueError:
                continue
        return None
    return (TODAY.year - int(y)) * 12 + (TODAY.month - int(mo or 1))


def _get(url, timeout=30, retries=5, data=None, method="GET"):
    hdr = {"Content-Type": "application/json"} if data is not None else {}
    for a in range(retries):
        try:
            return json.loads(urllib.request.urlopen(
                urllib.request.Request(url, data=data, headers=hdr, method=method), timeout=timeout).read())
        except Exception as exc:  # noqa: BLE001
            if a < retries - 1:
                time.sleep(4 * (a + 1))
                continue
            raise exc


def run_actor(key, urls):
    # run-sync is reliable for this actor (async 'runs' returned empty datasets); wait for items.
    inp = {"queries": urls, "profileScraperMode": "Profile details no email ($4 per 1k)"}
    url = f"https://api.apify.com/v2/acts/{ACTOR}/run-sync-get-dataset-items?token={key}"
    print(f"  run-sync ({len(urls)} profiles)...")
    items = _get(url, timeout=300, data=json.dumps(inp).encode(), method="POST")
    print(f"   got {len(items)} profiles")
    return items


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--months", type=int, default=12)
    ap.add_argument("--key", default=None)
    args = ap.parse_args()
    load_dotenv(ROOT / ".env")
    key = args.key or os.environ.get("APIFY_JOBS_KEY") or os.environ.get("APIFY_TOKEN")
    if not key:
        sys.exit("no APIFY key")

    d = pd.read_csv(LEADS).fillna("")
    sl = d[d["contact_title"].apply(lambda t: bool(LEADER.search(str(t))))]
    sl = sl[sl["contact_linkedin_url"].str.contains("linkedin.com/in", case=False, na=False)]
    sl = sl.drop_duplicates("contact_linkedin_url")
    if args.limit:
        sl = sl.head(args.limit)
    url_map = {slug_in(r["contact_linkedin_url"]): (r["company_name"], r["contact_name"], r["contact_title"])
               for _, r in sl.iterrows()}
    urls = sl["contact_linkedin_url"].tolist()
    print(f"scraping {len(urls)} sales-leader profiles for current-role tenure...")

    items = []
    B = 4
    for i in range(0, len(urls), B):
        try:
            items.extend(run_actor(key, urls[i:i + B]))
        except Exception as exc:  # noqa: BLE001
            print(f"  batch {i//B+1} FAILED ({exc})")
        time.sleep(8)  # be gentle — actor throttles under rapid no-cookie scraping
    print(f"got {len(items)} profiles")

    # best (freshest) recent sales-leader per company
    best = {}
    for it in items:
        oq = it.get("originalQuery") or {}
        qs = slug_in(oq.get("url") or oq.get("publicIdentifier") or it.get("linkedinUrl"))
        if qs not in url_map:
            continue
        co, name, title = url_map[qs]
        cps = it.get("currentPosition") or []
        # prefer the current position whose title looks like a sales-leader role
        cand = None
        for cp in cps:
            if LEADER.search(str(cp.get("position", ""))):
                cand = cp
                break
        cand = cand or (cps[0] if cps else None)
        if not cand:
            continue
        m = tenure_from(cand)
        if m is None or m > args.months:
            continue
        tier = "HIGH" if m <= 6 else "MED"
        rank = 2 if tier == "HIGH" else 1
        cur = best.get(co)
        if not cur or rank > cur["rank"] or (rank == cur["rank"] and m < cur["m"]):
            best[co] = {"rank": rank, "tier": tier, "m": m, "name": name,
                        "role": cand.get("position", title), "start": (cand.get("startDate") or {}).get("text", "")}

    for c in ("new_sales_hire_signal", "new_sales_hire_tier", "new_sales_hire_name",
              "new_sales_hire_role", "new_sales_hire_start"):
        if c not in d.columns:
            d[c] = ""
    # accumulate across runs: default blanks to No, but never overwrite an existing Yes
    d.loc[d["new_sales_hire_signal"] == "", "new_sales_hire_signal"] = "No"
    for co, h in best.items():
        m = d["company_name"] == co
        d.loc[m, "new_sales_hire_signal"] = "Yes"
        d.loc[m, "new_sales_hire_tier"] = h["tier"]
        d.loc[m, "new_sales_hire_name"] = h["name"]
        d.loc[m, "new_sales_hire_role"] = h["role"]
        d.loc[m, "new_sales_hire_start"] = h["start"]
    d.to_csv(LEADS, index=False, encoding="utf-8")

    print("=" * 60)
    print(f"new sales-leader hire (<= {args.months}mo): {len(best)} companies "
          f"(HIGH<=6mo={sum(1 for h in best.values() if h['tier']=='HIGH')})")
    for co, h in sorted(best.items(), key=lambda x: x[1]["m"]):
        print(f"   [{h['tier']}] {co}: {h['name']} - {h['role']} (started {h['start']}, {h['m']}mo)")
    print("=" * 60)


if __name__ == "__main__":
    main()
