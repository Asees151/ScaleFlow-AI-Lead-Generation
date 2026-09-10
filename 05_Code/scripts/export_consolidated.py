#!/usr/bin/env python3
"""
Single CONSOLIDATED deliverable — 1 best lead per company (102), everything in one clean file:
one score (0-100 band), 3 tiers, all company info, all intent signals WITH their links, and
the verified email at the END.

Tiers (3): Tier 1 (Hot) >=90 · Tier 2 (Warm) 80-89 · Tier 3 (Qualified) <=79.

Output: data/people/scaleflow_leads_consolidated.csv
Usage:  python scripts/export_consolidated.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import pandas as pd  # noqa

SRC = ROOT / "data/people/clay_ready_leads.csv"
OUT = ROOT / "data/people/scaleflow_leads_consolidated.csv"

# clean, logical order — score/tier first, company, contact, signals(+links), notes, EMAIL last
COLS = [
    "rank", "lead_score", "tier",
    # company
    "company_name", "domain", "website", "company_type", "country", "hq_city", "hq_region",
    "headcount", "founded_year", "last_funding_type", "last_funding_amount", "last_funding_date",
    "company_linkedin_url",
    # contact
    "contact_name", "contact_title", "contact_seniority", "contact_linkedin_url",
    # intent signals (with links)
    "hiring_signal", "hiring_job_title", "hiring_source", "hiring_job_url",
    "tech_stack_signal", "tech_stack_tier", "tech_stack_tools",
    "funding_intent",
    "new_sales_hire_signal", "new_sales_hire_tier", "new_sales_hire_role",
    "linkedin_post_signal", "linkedin_post_topic", "linkedin_post_date", "linkedin_post_url",
    "qualification_notes",
    # email LAST
    "email", "email_status",
]


def main():
    d = pd.read_csv(SRC).fillna("")
    lead = d[d["is_primary_contact"] == "Yes"].copy()

    # single score: raw lead_score normalized to 70-100
    raw = pd.to_numeric(lead["lead_score"], errors="coerce").fillna(0)
    lo, hi = raw.min(), raw.max()
    span = (hi - lo) or 1
    lead["lead_score"] = (70 + (raw - lo) / span * 30).round().astype(int)

    # 3 tiers
    def tier(s):
        return "Tier 1 (Hot)" if s >= 90 else ("Tier 2 (Warm)" if s >= 80 else "Tier 3 (Qualified)")
    lead["tier"] = lead["lead_score"].map(tier)

    lead = lead.sort_values("lead_score", ascending=False).reset_index(drop=True)
    lead["rank"] = lead.index + 1
    out = lead.reindex(columns=COLS)
    out.to_csv(OUT, index=False, encoding="utf-8-sig")   # BOM so Excel opens clean

    print(f"CONSOLIDATED -> {OUT.name}: {len(out)} leads (1/company), {out.shape[1]} columns")
    print(f"  verified email: {(out['email'].astype(str).str.len()>0).sum()}/{len(out)}")
    vc = out["tier"].value_counts()
    for t in ["Tier 1 (Hot)", "Tier 2 (Warm)", "Tier 3 (Qualified)"]:
        print(f"  {t}: {vc.get(t,0)}")
    print("\nTOP 12:")
    print(out.head(12)[["rank", "lead_score", "tier", "company_name", "contact_name", "contact_title", "email"]].to_string(index=False))


if __name__ == "__main__":
    main()
