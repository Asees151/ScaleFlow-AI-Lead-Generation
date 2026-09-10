#!/usr/bin/env python3
"""
Email enrichment via GetLeads (getleads.io) for our decision-makers.

For each person in the leads file it looks up an email - primarily by the exact
`linkedin_url` (precise, our person), falling back to first+last name + company
`domains`. Writes `email` + `email_status` back into the same file. 1 credit per
MATCH; no-match costs 0. Resumable (skips rows that already have an email).

Setup: .env with GETLEADS_KEY.
Usage:
  python scripts/find_emails_getleads.py --limit 10      # small test
  python scripts/find_emails_getleads.py                  # full run (resumes)
  python scripts/find_emails_getleads.py --input data/people/decision_makers_all.csv
"""
import argparse
import json
import os
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

from scrapers.common import clean_domain  # noqa: E402

BASE = "https://app.getleads.io/api/v1"
DEFAULT_FILE = ROOT / "data/people/final_qualified_leads.csv"
COLUMNS = ["first_name", "last_name", "job_title", "email_address", "email_status",
           "person_linkedin_url", "org_domain"]


def load_key():
    load_dotenv(ROOT / ".env")
    k = os.environ.get("GETLEADS_KEY")
    if not k:
        sys.exit("ERROR: GETLEADS_KEY not in .env")
    return k


def post(key, ep, body, retries=3):
    hdr = {"Authorization": "Bearer " + key, "Content-Type": "application/json"}
    for attempt in range(retries):
        try:
            req = urllib.request.Request(BASE + ep, data=json.dumps(body).encode(),
                                         headers=hdr, method="POST")
            return json.loads(urllib.request.urlopen(req, timeout=45).read())
        except urllib.error.HTTPError as exc:
            return {"ERR": exc.code, "msg": exc.read().decode()[:200]}
        except Exception as exc:                       # timeout / transient
            if attempt < retries - 1:
                time.sleep(2 * (attempt + 1))
                continue
            return {"ERR": "conn", "msg": str(exc)}
    return {"ERR": "retries", "msg": ""}


def lookup(key, linkedin, first, last, domain):
    """Return (contact_dict_or_None, credits_remaining_or_None)."""
    cred = None
    if linkedin and "linkedin.com/in" in linkedin:
        r = post(key, "/contacts/search",
                 {"linkedin_url": linkedin, "require_email": True, "columns": COLUMNS, "limit": 1})
        if isinstance(r, dict) and "ERR" not in r:
            cred = r.get("creditsRemaining", cred)
            if r.get("contacts"):
                return r["contacts"][0], cred
    if first and last and domain:
        r = post(key, "/contacts/search",
                 {"first_name": first, "last_name": last, "domains": [domain],
                  "require_email": True, "columns": COLUMNS, "limit": 1})
        if isinstance(r, dict) and "ERR" not in r:
            cred = r.get("creditsRemaining", cred)
            if r.get("contacts"):
                return r["contacts"][0], cred
    return None, cred


def main():
    ap = argparse.ArgumentParser(description="GetLeads email enrichment")
    ap.add_argument("--input", default=str(DEFAULT_FILE))
    ap.add_argument("--limit", type=int, default=None, help="enrich only N people (test)")
    args = ap.parse_args()
    key = load_key()

    path = Path(args.input)
    df = pd.read_csv(path).fillna("")
    for c in ("email", "email_status"):
        if c not in df.columns:
            df[c] = ""

    todo = [i for i in df.index if not str(df.at[i, "email"]).strip()]
    if args.limit:
        todo = todo[:args.limit]
    print(f"Enriching {len(todo)} of {len(df)} people via GetLeads...")

    matched = done = 0
    credits = None
    for i in todo:
        name = str(df.at[i, "full_name"]).split()
        first = name[0] if name else ""
        last = name[-1] if len(name) > 1 else ""
        contact, cred = lookup(key, str(df.at[i, "person_linkedin_url"]),
                               first, last, str(df.at[i, "domain"]))
        if cred is not None:
            credits = cred
        if contact:
            em = contact.get("email_address", "")
            em_dom, co_dom = clean_domain(em), clean_domain(str(df.at[i, "domain"]))
            if em_dom and co_dom and em_dom == co_dom:
                df.at[i, "email"] = em
                df.at[i, "email_status"] = contact.get("email_status", "VALID")
                matched += 1
            else:  # person found, but email is at a different company (moved / mismatch)
                df.at[i, "email_status"] = f"other_domain:{em_dom}"
        else:
            df.at[i, "email_status"] = "not_found"
        done += 1
        if done % 20 == 0:
            df.to_csv(path, index=False, encoding="utf-8-sig")
            print(f"  {done}/{len(todo)} | matched {matched} | credits {credits}")
        time.sleep(0.25)

    df.to_csv(path, index=False, encoding="utf-8-sig")
    have = (df["email"].astype(str).str.len() > 0).sum()
    valid = (df["email_status"] == "VALID").sum()
    print("=" * 60)
    print(f"DONE. matched {matched}/{len(todo)} this run | credits remaining {credits}")
    print(f"total with email: {have}/{len(df)} | VALID: {valid}")
    print("=" * 60)


if __name__ == "__main__":
    main()
