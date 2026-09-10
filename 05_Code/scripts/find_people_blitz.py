#!/usr/bin/env python3
"""
scripts/find_people_blitz.py - decision-maker finder via BlitzAPI (per-lead, no
per-run fee - far cheaper than the Apify actor for bulk).

For each company (from data/clean/, using its LinkedIn company URL) it calls
/v2/search/employee-finder (1 credit, up to 10 people) filtered to job levels
C-Team/VP/Director/Manager, extracts the decision-makers, ranks seniority, and
writes data/people/decision_makers_blitz.csv. Emails are a separate step
(/v2/enrichment/email) added later once we confirm coverage/cost.

Setup: .env with BLITZ_KEY_1 / BLITZ_KEY_2 (each ~1000 credits/mo, 5 req/sec).

Usage:
  python scripts/find_people_blitz.py --credits          # show remaining credits, no spend
  python scripts/find_people_blitz.py --limit 20         # test on 20 companies
  python scripts/find_people_blitz.py                    # full run (resumes; skips done)
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

BASE = "https://api.blitz-api.ai"
JOB_LEVELS = ["C-Team", "VP", "Director", "Manager"]
FALLBACK_FILE = ROOT / "data/clean/companies_with_full_info.csv"
DM_OUT = ROOT / "data/people/decision_makers_blitz.csv"
DM_COLUMNS = ["company_id", "domain", "company_name", "full_name", "title",
              "linkedin_url", "email", "location", "seniority_rank",
              "has_vp_of_sales", "company_qualified"]
RATE_SLEEP = 0.25       # ~4 req/sec, under the 5/sec limit
CREDIT_FLOOR = 40       # stop the run when total remaining credits drops below this
CREDIT_CHECK_EVERY = 3  # how often (companies) to re-check total credits


class Blitz:
    def __init__(self, keys):
        self.keys = keys
        self.i = 0

    def _hdr(self):
        return {"x-api-key": self.keys[self.i], "Content-Type": "application/json"}

    def credits(self):
        try:
            req = urllib.request.Request(BASE + "/v2/account/key-info", headers=self._hdr())
            return json.loads(urllib.request.urlopen(req, timeout=20).read()).get("records_remaining")
        except Exception:
            return None

    def total_credits(self):
        total, save = 0, self.i
        for j in range(len(self.keys)):
            self.i = j
            c = self.credits()
            total += c if isinstance(c, int) else 0
        self.i = save
        return total

    def post(self, endpoint, body):
        for _ in range(len(self.keys)):
            req = urllib.request.Request(BASE + endpoint, data=json.dumps(body).encode(),
                                         headers=self._hdr(), method="POST")
            try:
                return json.loads(urllib.request.urlopen(req, timeout=45).read())
            except urllib.error.HTTPError as exc:
                msg = exc.read().decode()[:200]
                if exc.code in (402, 429) or "credit" in msg.lower() or "quota" in msg.lower() or "limit" in msg.lower():
                    if self.i < len(self.keys) - 1:
                        print(f"  key{self.i + 1} limited ({exc.code}); rotating to key{self.i + 2}")
                        self.i += 1
                        continue
                    raise RuntimeError(f"all keys exhausted: {msg}")
                raise RuntimeError(f"HTTP {exc.code}: {msg}")
        raise RuntimeError("no keys left")


def load_keys():
    load_dotenv(ROOT / ".env")
    keys = [os.environ.get("BLITZ_KEY_1"), os.environ.get("BLITZ_KEY_2")]
    keys = [k for k in keys if k]
    if not keys:
        sys.exit("ERROR: no BLITZ_KEY_1/BLITZ_KEY_2 in .env")
    return keys


def seniority_rank(title):
    t = str(title or "").lower()
    if any(k in t for k in ("vp sales", "vp of sales", "head of sales", "sales director",
                            "director of sales", "chief revenue", "cro")):
        return 1
    if any(k in t for k in ("head of growth", "vp growth", "vp of growth", "growth",
                            "revops", "revenue operations", "revenue ops")):
        return 2
    if any(k in t for k in ("founder", "co-founder", "cofounder", "ceo", "chief executive", "owner")):
        return 3
    return 4


def person_title(p, company_li):
    """Best title for this person at the searched company."""
    for e in (p.get("experiences") or []):
        if e.get("company_linkedin_url") == company_li and e.get("job_title"):
            return e["job_title"]
    exps = p.get("experiences") or []
    if exps and exps[0].get("job_title"):
        return exps[0]["job_title"]
    return p.get("headline", "")


def save_rows(rows):
    """Recompute has_vp_of_sales + company_qualified per company, save, return df."""
    df = pd.DataFrame(rows)
    if not df.empty:
        df["seniority_rank"] = pd.to_numeric(df["seniority_rank"], errors="coerce").fillna(4).astype(int)
        vp = set(df.loc[df["seniority_rank"] == 1, "domain"])  # rank 1 = VP/Head/Dir of Sales
        df["has_vp_of_sales"] = df["domain"].map(lambda d: "Yes" if d in vp else "No")
        df["company_qualified"] = df["has_vp_of_sales"]  # ICP disqualifier: needs a senior sales leader
        for c in DM_COLUMNS:
            if c not in df.columns:
                df[c] = ""
        df = df[DM_COLUMNS]
    DM_OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(DM_OUT, index=False, encoding="utf-8-sig")
    return df


def summary(df):
    print("=" * 66)
    if df is None or df.empty:
        print("no people found")
        print("=" * 66)
        return
    comp = df["domain"].nunique()
    icp = df[df["seniority_rank"] <= 3]           # the 6 ICP roles (rank 1-3)
    qualified = df.loc[df["company_qualified"] == "Yes", "domain"].nunique()
    print(f"decision_makers_blitz.csv: {len(df)} people across {comp} companies")
    print(f"ICP decision-makers (Founder/CEO, VP/Head Sales, RevOps...): {len(icp)}")
    print(f"companies QUALIFIED (have a VP/Head of Sales): {qualified}")
    print(f"companies DISQUALIFIED (no senior sales leader): {comp - qualified}")
    print(f"with LinkedIn: {(df['linkedin_url'].astype(str).str.len() > 0).sum()}")
    print(f"seniority_rank counts: {df['seniority_rank'].value_counts().sort_index().to_dict()}")
    print("=" * 66)


def main():
    ap = argparse.ArgumentParser(description="BlitzAPI decision-maker finder")
    ap.add_argument("--limit", type=int, default=None, help="process only N companies (test)")
    ap.add_argument("--max-companies", dest="max_companies", type=int, default=None,
                    help="hard cap on companies this run (else runs to the credit floor)")
    ap.add_argument("--input", default=None, help="company CSV (default: companies_with_full_info.csv)")
    ap.add_argument("--credits", action="store_true", help="print remaining credits per key; no spend")
    args = ap.parse_args()

    blitz = Blitz(load_keys())
    if args.credits:
        for i in range(len(blitz.keys)):
            blitz.i = i
            print(f"key{i + 1} credits remaining: {blitz.credits()}")
        return

    companies = pd.read_csv(Path(args.input) if args.input else FALLBACK_FILE).fillna("")
    companies = companies[companies["linkedin_url"].astype(str).str.contains("linkedin.com/company", case=False)]

    rows, done = [], set()
    if DM_OUT.exists():
        prev = pd.read_csv(DM_OUT).fillna("")
        rows = prev.to_dict("records")
        done = set(prev["company_id"].astype(str))
        print(f"Resuming: {len(rows)} people from {len(done)} companies already done.")

    todo = [r for _, r in companies.iterrows() if str(r["company_id"]) not in done]
    if args.limit:
        todo = todo[:args.limit]
    if args.max_companies:
        todo = todo[:args.max_companies]
    total = blitz.total_credits()
    print(f"Companies to process: {len(todo)} | total credits: {total} | floor: {CREDIT_FLOOR}")

    processed = 0
    for row in todo:
        if processed % CREDIT_CHECK_EVERY == 0:
            total = blitz.total_credits()
            if total < CREDIT_FLOOR:
                print(f"Credit floor reached ({total} < {CREDIT_FLOOR}); stopping after {processed} companies.")
                break
        li = str(row["linkedin_url"]).strip()
        try:
            resp = blitz.post("/v2/search/employee-finder",
                              {"company_linkedin_url": li, "job_level": JOB_LEVELS})
        except Exception as exc:
            print(f"  STOP at {row['company_name']}: {exc}")
            break
        for p in (resp.get("results") or []):
            title = person_title(p, li)
            loc = p.get("location") or {}
            rows.append({
                "company_id": row["company_id"], "domain": row["domain"],
                "company_name": row["company_name"],
                "full_name": p.get("full_name") or f"{p.get('first_name', '')} {p.get('last_name', '')}".strip(),
                "title": title, "linkedin_url": p.get("linkedin_url", ""), "email": "",
                "location": ", ".join(x for x in (loc.get("city"), loc.get("country_code")) if x),
                "seniority_rank": seniority_rank(title), "has_vp_of_sales": "",
            })
        processed += 1
        if processed % 10 == 0:
            print(f"  {processed}/{len(todo)} companies | {len(rows)} people | total credits {total}")
            save_rows(rows)
        time.sleep(RATE_SLEEP)

    df = save_rows(rows)
    summary(df)


if __name__ == "__main__":
    main()
