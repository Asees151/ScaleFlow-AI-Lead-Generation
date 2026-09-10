#!/usr/bin/env python3
"""
Merge the round-2 Clay waterfall results (new founders + alternates for the 11 gap companies)
into clay_ready_leads.csv. Domain-match guard (reject wrong-company emails). Per gap company,
pick the best valid contact (Founder/CEO > Sales Leader > other), update it if it already exists
or append it as a new contact, and make it that company's primary contact.

Usage: python scripts/merge_waterfall_round2.py
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import pandas as pd  # noqa
from scrapers.common import clean_domain  # noqa

LEADS = ROOT / "data/people/clay_ready_leads.csv"
R2 = ROOT / "data/people/clay_waterfall_round2.csv"
ALT_OK = {"voly.co.uk": "volygroup.com", "datapelago.net": "datapelago.io"}
CONTACT_COLS = ["contact_name", "contact_title", "contact_seniority", "contact_linkedin_url",
                "email", "email_status", "email_source", "is_primary_contact", "dm_source"]


def seniority(title):
    t = title.lower()
    if re.search(r"founder|ceo|chief executive|president", t):
        return "Founder/CEO"
    if re.search(r"chief revenue|\bcro\b|vp|vice president|head of (sales|revenue|growth|business)|director of sales", t):
        return "Sales Leader"
    if re.search(r"sales|growth|business development|\bbdr\b|\bsdr\b|revenue", t):
        return "Sales/Growth"
    return "Other"


RANK = {"Founder/CEO": 3, "Sales Leader": 2, "Sales/Growth": 1, "Other": 0}


def main():
    d = pd.read_csv(LEADS).fillna("")
    r2 = pd.read_csv(R2).fillna("")

    # 1) validate + collect valid contacts per company
    valid = {}
    for _, row in r2.iterrows():
        co = row["company_name"]
        em = str(row["Work Email"]).strip()
        if not em:
            continue
        emdom, codom = clean_domain(em), clean_domain(str(row["domain"]))
        if not (emdom == codom or (emdom in ALT_OK and ALT_OK[emdom] == codom)):
            print(f"  reject {co}: {em} ({emdom} != {codom})")
            continue
        sen = seniority(str(row["contact_title"]))
        cand = {"name": row["contact_name"], "title": row["contact_title"], "sen": sen,
                "li": row["contact_linkedin_url"], "email": em}
        cur = valid.get(co)
        if not cur or RANK[sen] > RANK[cur["sen"]]:
            valid[co] = cand

    # 2) apply: update existing contact by linkedin, else append new row (copy company fields)
    added_new, updated = 0, 0
    for co, c in valid.items():
        comp_rows = d[d["company_name"] == co]
        if comp_rows.empty:
            continue
        # match existing contact by linkedin slug
        def slug(u):
            m = re.search(r"/in/([^/?#]+)", str(u)); return m.group(1).lower() if m else ""
        cli = slug(c["li"])
        match = comp_rows[comp_rows["contact_linkedin_url"].map(slug) == cli] if cli else comp_rows.iloc[0:0]
        # clear primary for the company first
        d.loc[d["company_name"] == co, "is_primary_contact"] = "No"
        if not match.empty:
            i = match.index[0]
            d.at[i, "email"] = c["email"]
            d.at[i, "email_status"] = "VALID (clay-waterfall)"
            d.at[i, "email_source"] = "clay-waterfall"
            d.at[i, "is_primary_contact"] = "Yes"
            updated += 1
        else:
            base = comp_rows.iloc[0].copy()          # company-level fields
            base["contact_name"] = c["name"]
            base["contact_title"] = c["title"]
            base["contact_seniority"] = c["sen"]
            base["contact_linkedin_url"] = c["li"]
            base["email"] = c["email"]
            base["email_status"] = "VALID (clay-waterfall)"
            base["email_source"] = "clay-waterfall"
            base["is_primary_contact"] = "Yes"
            base["dm_source"] = "web+clay"
            d = pd.concat([d, pd.DataFrame([base])], ignore_index=True)
            added_new += 1

    d.to_csv(LEADS, index=False, encoding="utf-8")
    emailed = d[d["email"].astype(str).str.len() > 0]["company_name"].nunique()
    print(f"\nupdated {updated} existing contacts, appended {added_new} new founder contacts")
    print(f"=== COVERAGE: {emailed}/{d['company_name'].nunique()} companies verified ===")
    still = sorted(set(d["company_name"]) - set(d[d["email"].astype(str).str.len() > 0]["company_name"]))
    print("remaining gaps:", still if still else "NONE — all companies verified!")


if __name__ == "__main__":
    main()
