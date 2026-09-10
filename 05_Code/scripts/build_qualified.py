#!/usr/bin/env python3
"""
Combine ALL decision-maker sources (BlitzAPI + Apify), apply the qualifier, join
company data, and write the qualified-leads file. Re-run any time more decision-
makers are found (it just recombines everything).

QUALIFIER (per user): a company is QUALIFIED if it has ANY sales/revenue role
(VP Sales, Head of Sales, Sales Director, Sales Manager, RevOps, CRO, BD, SDR...);
"Head of Sales" counts, it does NOT require a "VP". Disqualified = no sales role.

Outputs:
  data/people/decision_makers_all.csv  - every DM (both sources), deduped, flagged
  data/people/qualified_leads.csv       - DMs at QUALIFIED companies only
"""
import re
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

BLITZ = ROOT / "data/people/decision_makers_blitz.csv"
APIFY = ROOT / "data/people/decision_makers.csv"
COMPANIES = ROOT / "data/clean/companies_with_full_info.csv"
OUT_ALL = ROOT / "data/people/decision_makers_all.csv"
OUT_QUAL = ROOT / "data/people/qualified_leads.csv"

# Any sales/revenue role qualifies the COMPANY.
SALES_RE = re.compile(r"\bsales\b|revenue|\bcro\b|chief revenue|business development|\bbdr\b|\bsdr\b", re.I)

# Per user: EXCLUDE VP-level SALES people from the contact list (VP of Sales, SVP of
# Global Sales, VP of Worldwide Sales, Regional VP of Sales...). Use an alternative
# contact (Head of Sales / Sales Director / CRO / founder-CEO) instead.
EXCLUDE_VP_SALES_RE = re.compile(r"\b(v\.?p\.?|vice president|s\.?v\.?p\.?|e\.?v\.?p\.?|"
                                 r"senior vice president|executive vice president)\b.*\bsales\b", re.I)


def is_sales(title):
    return bool(SALES_RE.search(str(title or "")))


def is_excluded_vp_sales(title):
    return bool(EXCLUDE_VP_SALES_RE.search(str(title or "")))


# Noise = not a real outreach contact (unless the person is also a founder).
NOISE_RE = re.compile(r"assistant|board member|board of advisor|\badvisor\b|\binvestor\b|"
                      r"product owner|\bcoach\b", re.I)
CEO_RE = re.compile(r"\bceo\b|chief executive|\bowner\b", re.I)


def is_contact(title, is_sales_flag, excluded_flag):
    """Keep genuine decision-makers: non-VP sales/growth roles + founders/CEOs/Presidents.
    Drop VP-of-Sales, non-sales VPs, EAs, board members, advisors, investors, etc."""
    t = str(title or "").lower()
    if excluded_flag:                       # VP of Sales - excluded per user
        return False
    has_founder = "founder" in t
    if (not has_founder) and NOISE_RE.search(t):
        return False                        # EA / board / advisor / investor / product owner
    if has_founder:
        return True                         # any founder / co-founder
    if CEO_RE.search(t):
        return True                         # CEO / chief executive / owner
    if "president" in t and "vice president" not in t:
        return True                         # real President (not "Vice President of X")
    return bool(is_sales_flag)              # non-VP sales/revenue/BD/growth/RevOps role


def seniority_rank(title):
    t = str(title or "").lower()
    if any(k in t for k in ("vp sales", "vp of sales", "head of sales", "sales director",
                            "director of sales", "chief revenue", "cro", "chief sales",
                            "head of revenue", "vp revenue", "vp of revenue")):
        return 1  # senior sales leader
    if any(k in t for k in ("revops", "revenue operations", "sales manager", "business development",
                            "account executive", "sdr", "bdr", "sales development",
                            "head of growth", "vp growth", "vp of growth")):
        return 2  # other sales/growth role
    if any(k in t for k in ("founder", "co-founder", "cofounder", "ceo", "chief executive",
                            "owner", "president")):
        return 3  # founder / CEO
    return 4


def load_sources():
    frames = []
    if BLITZ.exists():
        b = pd.read_csv(BLITZ).fillna("")
        frames.append(pd.DataFrame({
            "company_id": b["company_id"], "domain": b["domain"],
            "company_name": b.get("company_name", ""), "full_name": b["full_name"],
            "title": b["title"], "person_linkedin_url": b["linkedin_url"], "source": "blitz"}))
    if APIFY.exists():
        a = pd.read_csv(APIFY).fillna("")
        frames.append(pd.DataFrame({
            "company_id": a["company_id"], "domain": a["domain"],
            "company_name": "", "full_name": a["full_name"], "title": a["title"],
            "person_linkedin_url": a["linkedin_url"], "source": "apify"}))
    if not frames:
        sys.exit("No decision-maker sources found.")
    df = pd.concat(frames, ignore_index=True)
    df = df[df["domain"].astype(str).str.len() > 0]
    return df.drop_duplicates(subset=["domain", "full_name"])


def main():
    df = load_sources()
    df["seniority_rank"] = df["title"].map(seniority_rank)
    df["is_sales"] = df["title"].map(is_sales)
    df["excluded_vp_sales"] = df["title"].map(is_excluded_vp_sales)  # drop VP-of-Sales as a contact
    df["is_contact"] = df.apply(lambda r: is_contact(r["title"], r["is_sales"], r["excluded_vp_sales"]), axis=1)
    qual_domains = set(df.loc[df["is_sales"], "domain"])
    df["company_qualified"] = df["domain"].map(lambda d: "Yes" if d in qual_domains else "No")

    comp = pd.read_csv(COMPANIES).fillna("")
    namemap = comp.set_index("company_id")["company_name"].to_dict()
    df["company_name"] = df.apply(lambda r: r["company_name"] or namemap.get(r["company_id"], ""), axis=1)
    comp2 = comp[["company_id", "website", "company_type", "country", "headcount_bucket",
                  "founded_year", "linkedin_url"]].rename(columns={"linkedin_url": "company_linkedin_url"})
    df = df.merge(comp2, on="company_id", how="left").fillna("")

    cols = ["company_id", "company_name", "domain", "website", "company_type", "country",
            "headcount_bucket", "founded_year", "company_linkedin_url", "full_name", "title",
            "seniority_rank", "is_sales", "excluded_vp_sales", "is_contact", "person_linkedin_url",
            "source", "company_qualified"]
    df = df[[c for c in cols if c in df.columns]].sort_values(["company_qualified", "company_id", "seniority_rank"],
                                                              ascending=[False, True, True])
    OUT_ALL.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_ALL, index=False, encoding="utf-8-sig")
    # qualified_leads = real decision-maker CONTACTS at qualified companies
    # (non-VP sales/growth + founders/CEOs; no VP-of-Sales, no EA/board/non-sales-VP noise).
    qual = df[(df["company_qualified"] == "Yes") & df["is_contact"]]
    qual.to_csv(OUT_QUAL, index=False, encoding="utf-8-sig")

    searched = df["domain"].nunique()
    dropped = df[(df["company_qualified"] == "Yes") & (~df["is_contact"])]
    contact_doms = set(qual["domain"])
    lost_all = qual_domains - contact_doms          # qualified companies with NO real contact left
    print("=" * 66)
    print(f"companies searched (Blitz+Apify): {searched}")
    print(f"QUALIFIED companies (any sales/revenue role): {len(qual_domains)}")
    print(f"people dropped as VP-of-Sales/noise: {len(dropped)}")
    print(f"qualified_leads.csv (clean contacts only): {len(qual)} people across {len(contact_doms)} companies")
    print(f"  -> companies KEEPING >=1 real contact: {len(contact_doms)} of {len(qual_domains)}")
    print(f"  -> companies with NO alternative left: {len(lost_all)}")
    print(f"  tiers: {dict(qual['seniority_rank'].value_counts().sort_index())} "
          f"(1=sales leader, 2=sales/growth, 3=founder/CEO)")
    print("=" * 66)


if __name__ == "__main__":
    main()
