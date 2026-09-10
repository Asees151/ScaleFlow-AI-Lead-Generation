#!/usr/bin/env python3
"""
Structure the final leads into a Clay-ready CSV for direct upload.

- One row per contact (286), clean snake_case headers.
- `is_primary_contact` = the best contact per company (prefers one WITH an email,
  then most-senior). Filter to Yes in Clay for a one-per-company list.
- Empty columns Clay will enrich/compute: revenue_estimate, hiring_signal(+job/date),
  linkedin_post_signal(+url), lead_score, qualification_notes.

Re-run after more emails/DMs land:  python scripts/build_clay_ready.py
"""
import sys
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

SRC = ROOT / "data/people/final_qualified_leads.csv"
OUT = ROOT / "data/people/clay_ready_leads.csv"
TIER = {1: "Sales Leader", 2: "Sales/Growth", 3: "Founder/CEO", 4: "Other"}


def main():
    d = pd.read_csv(SRC).fillna("")
    d["seniority_rank"] = pd.to_numeric(d["seniority_rank"], errors="coerce").fillna(4).astype(int)
    leader_co = set(d.loc[d["seniority_rank"] == 1, "company_id"])

    # primary contact per company: prefer has-email, then best seniority
    d["_has_email"] = (d["email"].astype(str).str.len() > 0).astype(int)
    d = d.sort_values(["company_id", "_has_email", "seniority_rank"], ascending=[True, False, True])
    primary_idx = d.groupby("company_id").head(1).index
    d["is_primary_contact"] = "No"
    d.loc[primary_idx, "is_primary_contact"] = "Yes"

    has_email = d["email"].astype(str).str.len() > 0
    out = pd.DataFrame()
    # --- company ---
    out["company_name"] = d["company_name"]
    out["domain"] = d["domain"]
    out["website"] = d["website"]
    out["company_type"] = d["company_type"]
    out["country"] = d["country"]
    out["hq_city"] = d["hq_city"]
    out["hq_region"] = d["hq_region"]
    out["headcount"] = d["headcount_bucket"]
    out["headcount_min"] = d["headcount_min"]
    out["headcount_max"] = d["headcount_max"]
    out["revenue_estimate"] = d["revenue_bucket"]           # empty -> Clay fills
    out["founded_year"] = d["founded_year"]
    out["industries"] = d["industries_or_category"]
    out["company_linkedin_url"] = d["linkedin_url"]
    out["last_funding_type"] = d["last_funding_type"]
    out["last_funding_amount"] = d["last_funding_amount"]
    out["last_funding_date"] = d["last_funding_date"]
    out["cb_rank"] = d["cb_rank"]
    out["priority_score"] = d["priority_score"]
    out["has_sales_leader"] = d["company_id"].map(lambda c: "Yes" if c in leader_co else "No")
    # --- contact ---
    out["contact_name"] = d["full_name"]
    out["contact_title"] = d["title"]
    out["contact_seniority"] = d["seniority_rank"].map(TIER)
    out["contact_linkedin_url"] = d["person_linkedin_url"]
    out["email"] = d["email"]
    out["email_status"] = d["email_status"].where(has_email, "")   # blank if no real email
    out["email_source"] = has_email.map({True: "getleads", False: ""})
    out["dm_source"] = d["dm_source"]
    out["is_primary_contact"] = d["is_primary_contact"]
    # --- Clay will fill these ---
    for c in ("hiring_signal", "hiring_job_title", "hiring_date",
              "linkedin_post_signal", "linkedin_post_url", "lead_score", "qualification_notes"):
        out[c] = ""

    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT, index=False, encoding="utf-8")           # plain UTF-8 (no BOM) for Clay
    print(f"clay_ready_leads.csv: {len(out)} contacts | {out.shape[1]} columns | {out['domain'].nunique()} companies")
    print(f"  with email: {(out['email'].astype(str).str.len() > 0).sum()} | primary contacts: {(out['is_primary_contact'] == 'Yes').sum()}")
    print(f"  columns: {out.columns.tolist()}")


if __name__ == "__main__":
    main()
