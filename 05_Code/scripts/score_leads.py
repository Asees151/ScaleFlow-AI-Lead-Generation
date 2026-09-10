#!/usr/bin/env python3
"""
Lead scoring for ScaleFlow AI — transparent 0-100 score = Intent (55) + Fit (45).

INTENT (max 55): hiring +15 | tech-stack HIGH +12/MED +4 | new-sales-hire HIGH +10/MED +6 |
                 funding HIGH +8/MED +4 | LinkedIn-post HIGH +10/MED +3
FIT (max 45):    verified email +15 | seniority Leader 20/Founder 15/Sales-Growth 15/Other 5 |
                 has_sales_leader +10

Writes lead_score + qualification_notes into clay_ready_leads.csv, sorts, and prints the
distribution. Deliverable selection (top-100) is a separate step once we confirm the rule.

Usage: python scripts/score_leads.py
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

LEADS = ROOT / "data/people/clay_ready_leads.csv"
SEN = {"Sales Leader": 20, "Founder/CEO": 15, "Sales/Growth": 15, "Other": 5}


def score_row(r):
    s = 0
    notes = []
    # ---- INTENT (55) ----
    if r["hiring_signal"] == "Yes":
        s += 15
        notes.append(f"Hiring:{r.get('hiring_job_title','')[:40]}")
    tt = r.get("tech_stack_tier", "")
    if tt == "HIGH":
        s += 12; notes.append(f"Uses outbound tool:{r.get('tech_stack_tools','')}")
    elif tt == "MED":
        s += 4; notes.append(f"CRM:{r.get('tech_stack_tools','')}")
    nh = r.get("new_sales_hire_tier", "")
    if nh == "HIGH":
        s += 10; notes.append(f"New sales leader<=6mo:{r.get('new_sales_hire_role','')}")
    elif nh == "MED":
        s += 6; notes.append(f"New sales leader<=12mo:{r.get('new_sales_hire_role','')}")
    fi = r.get("funding_intent", "")
    if fi == "HIGH":
        s += 8; notes.append(f"Funded<=12mo:{r.get('last_funding_type','')}")
    elif fi == "MED":
        s += 4; notes.append("Funded<=24mo")
    pt = r.get("linkedin_post_topic", "")
    if pt == "HIGH":
        s += 10; notes.append("Posts on cold-email/deliverability(HIGH)")
    elif pt == "MED":
        s += 3; notes.append("Posts on outbound/GTM(MED)")
    # ---- FIT (45) ----
    has_email = len(str(r.get("email", "")).strip()) > 0
    if has_email:
        s += 15; notes.append("Verified email")
    s += SEN.get(str(r.get("contact_seniority", "")), 5)
    if r.get("has_sales_leader", "") == "Yes":
        s += 10
    return min(100, s), " | ".join(notes)


def main():
    d = pd.read_csv(LEADS).fillna("")
    res = d.apply(score_row, axis=1)
    d["lead_score"] = [x[0] for x in res]
    d["qualification_notes"] = [x[1] for x in res]
    d = d.sort_values(["lead_score", "is_primary_contact"], ascending=[False, True]).reset_index(drop=True)
    d.to_csv(LEADS, index=False, encoding="utf-8")

    has_email = d["email"].astype(str).str.len() > 0
    print(f"scored {len(d)} contacts / {d['company_name'].nunique()} companies")
    print(f"  score >=70: {(d['lead_score']>=70).sum()} | >=50: {(d['lead_score']>=50).sum()} | >=30: {(d['lead_score']>=30).sum()}")
    print(f"  with verified email: {has_email.sum()} | emailed & score>=50: {(has_email & (d['lead_score']>=50)).sum()}")
    print("\nTOP 15 leads:")
    print(d.head(15)[["lead_score", "company_name", "contact_name", "contact_title", "email"]].to_string(index=False))
    print("\nTOP 15 companies by best-contact score:")
    top_co = d.sort_values("lead_score", ascending=False).drop_duplicates("company_name").head(15)
    print(top_co[["lead_score", "company_name", "hiring_signal", "tech_stack_tier", "funding_intent", "new_sales_hire_tier", "linkedin_post_topic"]].to_string(index=False))


if __name__ == "__main__":
    main()
