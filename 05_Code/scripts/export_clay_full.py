#!/usr/bin/env python3
"""
FULL Clay-upload file — ALL 286 contacts, cleanly structured for direct import to Clay.

Column order: Score/Priority -> Company -> Contact -> Intent signals.
- priority_score = raw lead_score normalized to 70-100 across all 286 (relative priority band).
- keeps raw lead_score + lead_score_tier + qualification_notes for transparency.
- plain UTF-8 (no BOM) so Clay parses headers cleanly.

Output: data/people/scaleflow_clay_upload.csv
Usage:  python scripts/export_clay_full.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
import pandas as pd  # noqa: E402

SRC = ROOT / "data/people/clay_ready_leads.csv"
OUT = ROOT / "data/people/scaleflow_clay_upload.csv"

ORDER = [
    # --- score / priority ---
    "priority_score", "lead_score", "lead_score_tier", "qualification_notes",
    # --- company ---
    "company_name", "domain", "website", "company_type", "country", "hq_city", "hq_region",
    "headcount", "headcount_min", "headcount_max", "revenue_estimate", "founded_year",
    "industries", "company_linkedin_url", "last_funding_type", "last_funding_amount",
    "last_funding_date", "has_sales_leader",
    # --- contact ---
    "contact_name", "contact_title", "contact_seniority", "contact_linkedin_url",
    "email", "email_status", "email_source", "is_primary_contact", "dm_source",
    # --- intent signals ---
    "hiring_signal", "hiring_job_title", "hiring_source", "hiring_job_url",
    "tech_stack_signal", "tech_stack_tier", "tech_stack_tools",
    "funding_intent", "funding_recency_months",
    "new_sales_hire_signal", "new_sales_hire_tier", "new_sales_hire_role", "new_sales_hire_start",
    "linkedin_post_signal", "linkedin_post_topic", "linkedin_post_date", "linkedin_post_url",
    "linkedin_post_snippet",
]


def main():
    d = pd.read_csv(SRC).fillna("")
    d = d.drop(columns=["priority_score"], errors="ignore")   # stale company-priority (name clash)

    raw = pd.to_numeric(d["lead_score"], errors="coerce").fillna(0)
    lo, hi = raw.min(), raw.max()
    span = (hi - lo) or 1
    d["priority_score"] = (70 + (raw - lo) / span * 30).round().astype(int)
    d["lead_score_tier"] = pd.cut(d["priority_score"], [-1, 76, 82, 90, 200],
                                  labels=["C", "B", "A", "A+"]).astype(str)

    d = d.sort_values(["priority_score", "is_primary_contact"], ascending=[False, True])
    out = d.reindex(columns=[c for c in ORDER if c in d.columns])
    out.to_csv(OUT, index=False, encoding="utf-8")   # plain UTF-8, no BOM

    he = out["email"].astype(str).str.len() > 0
    print(f"CLAY UPLOAD FILE -> {OUT.name}: {len(out)} contacts / {out['company_name'].nunique()} companies / {out.shape[1]} columns")
    print(f"  priority range {out['priority_score'].min()}-{out['priority_score'].max()} | verified emails {he.sum()} | primary contacts {(out['is_primary_contact']=='Yes').sum()}")
    print(f"  tiers: A+ {(out['lead_score_tier']=='A+').sum()} · A {(out['lead_score_tier']=='A').sum()} · B {(out['lead_score_tier']=='B').sum()} · C {(out['lead_score_tier']=='C').sum()}")
    print("  columns:", out.columns.tolist())


if __name__ == "__main__":
    main()
