#!/usr/bin/env python3
"""
Funding-recency intent signal (FREE — uses last_funding_date already scraped from Crunchbase).

A recent raise = fresh budget + GTM scaling = strong timing signal for ScaleFlow.
Adds: funding_recency_months, funding_intent (HIGH <=12mo, MED 13-24mo, else '').
Writes into data/people/clay_ready_leads.csv.  Run: python scripts/add_funding_signal.py
"""
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
import pandas as pd  # noqa: E402

LEADS = ROOT / "data/people/clay_ready_leads.csv"
TODAY = datetime(2026, 9, 11)


def months_since(s):
    s = str(s).strip()
    for fmt in ("%b %d, %Y", "%B %d, %Y", "%Y-%m-%d", "%b %Y", "%Y"):
        try:
            dt = datetime.strptime(s, fmt)
            return (TODAY.year - dt.year) * 12 + (TODAY.month - dt.month)
        except ValueError:
            continue
    return None


def main():
    d = pd.read_csv(LEADS).fillna("")
    d["funding_recency_months"] = d["last_funding_date"].map(months_since)
    def intent(m):
        if m is None:
            return ""
        return "HIGH" if m <= 12 else ("MED" if m <= 24 else "")
    d["funding_intent"] = d["funding_recency_months"].map(intent)
    d.to_csv(LEADS, index=False, encoding="utf-8")

    c = d.drop_duplicates("company_name")
    print(f"funding_intent: HIGH(<=12mo)={ (c['funding_intent']=='HIGH').sum() } | "
          f"MED(13-24mo)={ (c['funding_intent']=='MED').sum() } | "
          f"older/none={ (c['funding_intent']=='').sum() }  (of {len(c)} companies)")
    hi = c[c["funding_intent"] == "HIGH"][["company_name", "last_funding_type", "last_funding_date"]]
    print("recent raisers (<=12mo):", len(hi))
    print(hi.head(15).to_string(index=False))


if __name__ == "__main__":
    main()
