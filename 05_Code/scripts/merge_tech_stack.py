#!/usr/bin/env python3
"""
Competitor / tech-stack intent signal (from the free web scan — 8 subagents, WebSearch/WebFetch).

Detects whether each company USES a cold-email / sales-engagement / outbound tool. Verified by
domain (job postings, website tracking scripts, tech-stack profiles). Tier:
  HIGH = uses a real outbound sequencer (Outreach / Salesloft / Apollo / Smartlead / Instantly /
         Lemlist) -> already doing cold outbound = prime ScaleFlow fit.
  MED  = CRM / conversation-intel only (HubSpot / Salesforce / Gong / Clay).
Writes tech_stack_signal / tech_stack_tools / tech_stack_tier into clay_ready_leads.csv.

Usage: python scripts/merge_tech_stack.py
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

# company_name -> (tools, tier)  ; HIGH = uses an outbound sequencer
TECH = {
    "Blacksmith": ("Outreach, Apollo", "HIGH"),
    "Twelve Labs": ("Salesloft, Apollo, HubSpot, Clay", "HIGH"),
    "Unframe": ("Outreach, Salesforce", "HIGH"),
    "Trunk Tools": ("HubSpot", "MED"),
    "Revv": ("Salesforce", "MED"),
    "Agentio": ("HubSpot, Gong, Sales Navigator", "MED"),
    "Warp": ("Apollo, Outreach, HubSpot", "HIGH"),
    "Kumo.AI": ("Salesforce", "MED"),
    "Mutiny": ("Outreach, Salesloft, Salesforce, Gong", "HIGH"),
    "Momentum": ("Salesloft, Outreach, Salesforce, Gong", "HIGH"),
    "Takt": ("HubSpot, Salesforce", "MED"),
    "Cloverleaf AI": ("HubSpot", "MED"),
    "Konko AI": ("HubSpot", "MED"),
    "Vertical Insure": ("HubSpot", "MED"),
    "Auditoria.AI": ("Outreach, Salesforce", "HIGH"),
    "Numa": ("HubSpot, Salesforce", "MED"),
    "ketteQ": ("Salesforce", "MED"),
    "Richtech Robotics": ("Salesforce/HubSpot", "MED"),
    "Cortex": ("Outreach, Salesforce", "HIGH"),
    "VESSL AI": ("HubSpot", "MED"),
    "Buzz Solutions": ("HubSpot", "MED"),
    "OpenMind": ("Salesforce, HubSpot", "MED"),
    "Vendelux": ("Salesloft, Salesforce, HubSpot", "HIGH"),
    "David Energy": ("Salesforce, HubSpot", "MED"),
    "Comet": ("Outreach, Salesforce", "HIGH"),
    "Codoxo": ("Salesforce", "MED"),
    "Wildfire Systems": ("HubSpot", "MED"),
    "11x AI": ("Salesforce", "MED"),
    "Lakera": ("HubSpot, Salesforce", "MED"),
    "Archy": ("Salesforce, HubSpot", "MED"),
    "Optery": ("HubSpot", "MED"),
    "Raspberry AI": ("HubSpot", "MED"),
    "Voly": ("HubSpot", "MED"),
    "SGNL": ("HubSpot", "MED"),
    "Onward": ("HubSpot", "MED"),
    "Threater": ("Apollo", "HIGH"),
    "Spoiler Alert": ("Apollo, HubSpot", "HIGH"),
    "ModelOp": ("HubSpot", "MED"),
    "Cypris": ("HubSpot", "MED"),
    "Instrumentl": ("HubSpot, Gong", "MED"),
    "BriefCatch": ("HubSpot", "MED"),
}


def main():
    d = pd.read_csv(LEADS).fillna("")
    for c in ("tech_stack_signal", "tech_stack_tools", "tech_stack_tier"):
        if c not in d.columns:
            d[c] = ""
    d["tech_stack_signal"] = "No"
    miss = []
    for co, (tools, tier) in TECH.items():
        m = d["company_name"] == co
        if not m.any():
            miss.append(co)
            continue
        d.loc[m, "tech_stack_signal"] = "Yes"
        d.loc[m, "tech_stack_tools"] = tools
        d.loc[m, "tech_stack_tier"] = tier
    d.to_csv(LEADS, index=False, encoding="utf-8")
    if miss:
        print("WARN not found:", miss)
    c = d.drop_duplicates("company_name")
    y = c[c["tech_stack_signal"] == "Yes"]
    print(f"tech_stack: {len(y)} companies (HIGH outbound-tool={ (y['tech_stack_tier']=='HIGH').sum() }, "
          f"MED crm-only={ (y['tech_stack_tier']=='MED').sum() })")
    print("HIGH (uses Outreach/Salesloft/Apollo):")
    print(y[y["tech_stack_tier"] == "HIGH"][["company_name", "tech_stack_tools"]].to_string(index=False))


if __name__ == "__main__":
    main()
