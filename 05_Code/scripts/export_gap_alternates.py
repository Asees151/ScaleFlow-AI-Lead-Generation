#!/usr/bin/env python3
"""
Clay file of ALTERNATE contacts at the gap companies (those still with no verified email),
so they can be run through the Clay email-waterfall as a second shot per account.

Output: data/people/scaleflow_clay_alternates.csv
Usage:  python scripts/export_gap_alternates.py
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
OUT = ROOT / "data/people/scaleflow_clay_alternates.csv"
COLS = ["company_name", "domain", "website", "country", "contact_name", "contact_title",
        "contact_seniority", "contact_linkedin_url", "is_primary_contact",
        "hiring_signal", "tech_stack_tier", "funding_intent", "qualification_notes"]


def main():
    d = pd.read_csv(SRC).fillna("")
    # gap companies = no verified email on ANY contact
    emailed = set(d[d["email"].astype(str).str.len() > 0]["company_name"])
    gaps = sorted(set(d["company_name"]) - emailed)
    # FRESH alternates only = non-primary contacts (the primary already failed the waterfall).
    alt = d[(d["company_name"].isin(gaps)) & (d["is_primary_contact"] != "Yes")].copy()
    alt = alt.sort_values(["company_name"])
    out = alt.reindex(columns=COLS)
    out.to_csv(OUT, index=False, encoding="utf-8")

    have_alt = sorted(set(out["company_name"]))
    no_alt = [c for c in gaps if c not in have_alt]
    print(f"GAP alternates (FRESH, non-primary) -> {OUT.name}: {len(out)} contacts across {len(have_alt)} companies")
    print("\nHAVE a fresh alternate to waterfall:")
    print(out[["company_name", "contact_name", "contact_title"]].to_string(index=False))
    print(f"\nNO fresh alternate ({len(no_alt)}) — only the already-failed contact, need NEW people (Apollo/expansion):")
    print("  ", no_alt)


if __name__ == "__main__":
    main()
