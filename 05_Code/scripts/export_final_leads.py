#!/usr/bin/env python3
"""
Final deliverable: ONE best lead per company (all 102 companies), scored & ranked.

Uses is_primary_contact (best contact per company: prefers verified email, then seniority),
sorts by lead_score desc, writes a clean, presentation-ready CSV.

Output: data/people/scaleflow_final_leads.csv
Usage:  python scripts/export_final_leads.py
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
OUT = ROOT / "data/people/scaleflow_final_leads.csv"

COLS = ["rank", "priority_score", "lead_score", "company_name", "domain", "website", "company_type", "country",
        "headcount", "founded_year", "last_funding_type", "last_funding_amount", "last_funding_date",
        "company_linkedin_url", "contact_name", "contact_title", "contact_seniority",
        "contact_linkedin_url", "email", "email_status",
        "hiring_signal", "hiring_job_title", "hiring_source",
        "tech_stack_tier", "tech_stack_tools", "funding_intent",
        "new_sales_hire_tier", "new_sales_hire_role",
        "linkedin_post_topic", "linkedin_post_url", "lead_score_tier", "qualification_notes"]


def main():
    d = pd.read_csv(SRC).fillna("")
    # one best lead per company
    lead = d[d["is_primary_contact"] == "Yes"].copy()
    # (safety) if any company somehow lacks a primary flag, take its top-scored row
    missing = set(d["company_name"]) - set(lead["company_name"])
    if missing:
        extra = d[d["company_name"].isin(missing)].sort_values("lead_score", ascending=False)
        lead = pd.concat([lead, extra.drop_duplicates("company_name")])

    # normalize raw score -> Priority Score 70-100 (relative rank among the qualified 102;
    # all passed ICP qualification, so nothing reads as a "fail")
    rmin, rmax = lead["lead_score"].min(), lead["lead_score"].max()
    span = (rmax - rmin) or 1
    lead["priority_score"] = (70 + (lead["lead_score"] - rmin) / span * 30).round().astype(int)

    lead = lead.sort_values("priority_score", ascending=False).reset_index(drop=True)
    lead["rank"] = lead.index + 1
    lead["lead_score_tier"] = pd.cut(lead["priority_score"], [-1, 76, 82, 90, 200],
                                     labels=["C", "B", "A", "A+"]).astype(str)
    out = lead.reindex(columns=COLS)
    out.to_csv(OUT, index=False, encoding="utf-8-sig")

    has_email = out["email"].astype(str).str.len() > 0
    print(f"FINAL DELIVERABLE: {len(out)} leads (1 per company) -> {OUT.name}")
    print(f"  priority_score range: {out['priority_score'].min()}-{out['priority_score'].max()} (raw {out['lead_score'].min()}-{out['lead_score'].max()})")
    print(f"  verified email: {has_email.sum()} | no email yet: {(~has_email).sum()}")
    print(f"  tiers: A+ (>=90): {(out['lead_score_tier']=='A+').sum()} | A (83-89): {(out['lead_score_tier']=='A').sum()} | "
          f"B (77-82): {(out['lead_score_tier']=='B').sum()} | C (70-76): {(out['lead_score_tier']=='C').sum()}")
    print(f"  with >=1 intent signal: "
          f"{((out['hiring_signal']=='Yes')|(out['linkedin_post_topic']!='')|(out['funding_intent']=='HIGH')|(out['tech_stack_tier']=='HIGH')|(out['new_sales_hire_tier']!='')).sum()}")
    print("\nTOP 20:")
    print(out.head(20)[["rank", "priority_score", "lead_score", "company_name", "contact_name", "contact_title", "email"]].to_string(index=False))


if __name__ == "__main__":
    main()
