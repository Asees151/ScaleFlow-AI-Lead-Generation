#!/usr/bin/env python3
"""
LinkedIn-post intent signal via Apify actor harvestapi/linkedin-profile-posts.

Scrapes recent posts (last ~3 months) of each company's PRIMARY contact and flags whoever
is posting about the pains ScaleFlow AI sells into: cold email / deliverability / email
warmup / outbound / scaling sales. Writes linkedin_post_signal / _url / _date / _topic /
_snippet into data/people/clay_ready_leads.csv. All matched posts -> post_signal_hits.csv.

Cost: $0.002/post + tiny start (~$2 for 102 contacts at maxPosts=10). Key = APIFY_JOBS_KEY.
Batched (20 profiles/run), retry-hardened polling, resumable-safe.

Usage:
  python scripts/find_post_signal.py --limit 6      # cheap test
  python scripts/find_post_signal.py                # full (102 primary contacts)
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
import pandas as pd  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

ACTOR = "harvestapi~linkedin-profile-posts"
LEADS = ROOT / "data/people/clay_ready_leads.csv"
HITS = ROOT / "data/people/post_signal_hits.csv"

# HIGH = direct ScaleFlow pain; MED = adjacent outbound/GTM intent
HIGH_RE = re.compile(r"cold email|cold outreach|deliverabilit|email warm|inbox placement|spam folder|"
                     r"sender reputation|domain reputation|bounce rate|open rate|reply rate|"
                     r"email sequenc|cold call|email warmup|land in the inbox|primary inbox", re.I)
MED_RE = re.compile(r"\boutbound\b|prospect|\bsdr\b|\bbdr\b|pipeline generation|sales engagement|"
                    r"scaling (sales|outbound)|book(ing)? (more )?meetings|sales development|"
                    r"go[- ]to[- ]market|\bgtm\b|lead generation|sales cadence|outreach sequence", re.I)


def slug_in(url):
    m = re.search(r"/in/([^/?#]+)", str(url or ""))
    return m.group(1).lower() if m else ""


def _get(url, timeout=30, retries=5, data=None, method="GET"):
    hdr = {"Content-Type": "application/json"} if data is not None else {}
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, data=data, headers=hdr, method=method)
            return json.loads(urllib.request.urlopen(req, timeout=timeout).read())
        except Exception as exc:  # noqa: BLE001
            if attempt < retries - 1:
                time.sleep(4 * (attempt + 1))
                continue
            raise exc


def run_actor(key, urls):
    inp = {"targetUrls": urls, "maxPosts": 10, "postedLimit": "3months",
           "includeReposts": True, "includeQuotePosts": True,
           "scrapeReactions": False, "scrapeComments": False}
    run = _get(f"https://api.apify.com/v2/acts/{ACTOR}/runs?token={key}",
               timeout=60, data=json.dumps(inp).encode(), method="POST")["data"]
    rid, ds = run["id"], run["defaultDatasetId"]
    print(f"  run {rid} ({len(urls)} profiles); polling...")
    waited = 0
    while True:
        time.sleep(6)
        waited += 6
        st = _get(f"https://api.apify.com/v2/actor-runs/{rid}?token={key}", timeout=30)["data"]
        if st["status"] in ("SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"):
            print("   status:", st["status"], "| USD:", st.get("usageTotalUsd"))
            break
        if waited > 420:
            print("   poll cap hit; moving on")
            break
    return _get(f"https://api.apify.com/v2/datasets/{ds}/items?token={key}&clean=true", timeout=90)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--key", default=None)
    args = ap.parse_args()
    load_dotenv(ROOT / ".env")
    key = args.key or os.environ.get("APIFY_JOBS_KEY") or os.environ.get("APIFY_TOKEN")
    if not key:
        sys.exit("no APIFY key")

    d = pd.read_csv(LEADS).fillna("")
    prim = d[d["is_primary_contact"] == "Yes"].copy()
    prim = prim[prim["contact_linkedin_url"].str.contains("linkedin.com/in", case=False, na=False)]
    if args.limit:
        prim = prim.head(args.limit)
    url_to_co = {slug_in(r["contact_linkedin_url"]): (r["company_name"], r["contact_name"])
                 for _, r in prim.iterrows()}
    urls = prim["contact_linkedin_url"].tolist()
    print(f"scanning posts for {len(urls)} primary contacts...")

    items = []
    B = 20
    for i in range(0, len(urls), B):
        try:
            items.extend(run_actor(key, urls[i:i + B]))
        except Exception as exc:  # noqa: BLE001
            print(f"  batch {i//B+1} FAILED ({exc}); skipping")
    print(f"got {len(items)} posts total")

    # attribute each post to the queried profile, keyword-match content
    hits = {}
    rows = []
    for it in items:
        q = it.get("query") or {}
        turl = q.get("targetUrl", "") if isinstance(q, dict) else ""
        qslug = slug_in(turl)
        if not qslug or qslug not in url_to_co:
            # can't attribute safely -> skip
            continue
        co, person = url_to_co[qslug]
        content = str(it.get("content") or "")
        tier = "HIGH" if HIGH_RE.search(content) else ("MED" if MED_RE.search(content) else "")
        if not tier:
            continue
        date = (it.get("postedAt") or {}).get("date", "") if isinstance(it.get("postedAt"), dict) else ""
        purl = it.get("linkedinUrl") or it.get("shareLinkedinUrl") or ""
        rows.append({"company_name": co, "contact_name": person, "tier": tier,
                     "date": date[:10], "url": purl, "snippet": content[:200].replace("\n", " ")})
        # keep best hit per company: HIGH beats MED, then most recent
        cur = hits.get(co)
        rank = 2 if tier == "HIGH" else 1
        if not cur or rank > cur["rank"] or (rank == cur["rank"] and date > cur["date"]):
            hits[co] = {"rank": rank, "tier": tier, "date": date[:10], "url": purl,
                        "topic": tier, "snippet": content[:160].replace("\n", " ")}

    for c in ("linkedin_post_signal", "linkedin_post_url", "linkedin_post_date",
              "linkedin_post_topic", "linkedin_post_snippet"):
        if c not in d.columns:
            d[c] = ""
    d["linkedin_post_signal"] = "No"
    for co, h in hits.items():
        m = d["company_name"] == co
        d.loc[m, "linkedin_post_signal"] = "Yes"
        d.loc[m, "linkedin_post_url"] = h["url"]
        d.loc[m, "linkedin_post_date"] = h["date"]
        d.loc[m, "linkedin_post_topic"] = h["tier"]
        d.loc[m, "linkedin_post_snippet"] = h["snippet"]
    d.to_csv(LEADS, index=False, encoding="utf-8")
    if rows:
        pd.DataFrame(rows).to_csv(HITS, index=False, encoding="utf-8")

    print("=" * 60)
    print(f"post signal: {len(hits)} companies (HIGH={sum(1 for h in hits.values() if h['tier']=='HIGH')}, "
          f"MED={sum(1 for h in hits.values() if h['tier']=='MED')})")
    for co, h in sorted(hits.items(), key=lambda x: -x[1]["rank"]):
        print(f"   [{h['tier']}] {co} ({h['date']}): {h['snippet'][:80]}")
    print("=" * 60)


if __name__ == "__main__":
    main()
