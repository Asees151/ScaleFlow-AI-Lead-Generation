#!/usr/bin/env python3
"""
Separate Clay file for the companies with NO verified email yet (best contact each) —
ready to run Clay's email-finding waterfall (name + company domain).

Built from scaleflow_clay_upload.csv (same clean structure). A company qualifies if NONE of
its contacts has an email; we then export its primary (best) contact.

Output: data/people/scaleflow_clay_no_email.csv
Usage:  python scripts/export_no_email.py
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

SRC = ROOT / "data/people/scaleflow_clay_upload.csv"
OUT = ROOT / "data/people/scaleflow_clay_no_email.csv"


def main():
    d = pd.read_csv(SRC).fillna("")
    has_email = d["email"].astype(str).str.len() > 0
    emailed_cos = set(d.loc[has_email, "company_name"])
    no_email = d[~d["company_name"].isin(emailed_cos)].copy()

    # best contact per no-email company (primary flag, else top priority)
    prim = no_email[no_email["is_primary_contact"] == "Yes"]
    missing = set(no_email["company_name"]) - set(prim["company_name"])
    if missing:
        extra = no_email[no_email["company_name"].isin(missing)].sort_values("priority_score", ascending=False)
        prim = pd.concat([prim, extra.drop_duplicates("company_name")])

    prim = prim.sort_values("priority_score", ascending=False).reset_index(drop=True)
    prim.to_csv(OUT, index=False, encoding="utf-8")   # plain UTF-8 for Clay

    print(f"NO-EMAIL Clay file -> {OUT.name}: {len(prim)} companies")
    print(f"  tiers: A+ {(prim['lead_score_tier']=='A+').sum()} · A {(prim['lead_score_tier']=='A').sum()} · "
          f"B {(prim['lead_score_tier']=='B').sum()} · C {(prim['lead_score_tier']=='C').sum()}")
    print(prim[["priority_score", "company_name", "domain", "contact_name", "contact_title"]].to_string(index=False))


if __name__ == "__main__":
    main()
