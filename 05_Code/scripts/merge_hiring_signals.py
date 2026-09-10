#!/usr/bin/env python3
"""
Merge the hiring/intent signals from ALL sources into clay_ready_leads.csv:
  - LinkedIn jobs (Apify valig/linkedin-jobs-scraper, URL-matched)  -> earlier pass
  - Indeed + company careers/ATS pages (free web scan via Claude subagents, WebSearch/WebFetch)

Web-scan results (careers/ATS/Indeed) are the dict below; verified by DOMAIN so no
same-name false positives. LinkedIn-only companies (Blee, Agentio, BriefCatch) are kept.
Sets hiring_signal / hiring_job_title / hiring_job_url / hiring_source (and keeps hiring_date
from the LinkedIn pass where we have it).

Usage: python scripts/merge_hiring_signals.py
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

# company_name (exact as in CSV) -> (role, url, source)
WEB = {
    "Unframe": ("Business Development Representative (Remote)", "https://job-boards.greenhouse.io/unframe/jobs/4847893101", "careers"),
    "Trunk Tools": ("Business Development Representative (Austin)", "https://jobs.ashbyhq.com/Trunk%20Tools/11da904b-71cd-4258-9cdf-95281a96a6b1", "careers"),
    "Revv": ("Business Development Representative", "https://ats.rippling.com/revv/jobs/8d59ebd8-d8d9-4d3b-ba12-c58021f4d096", "careers+indeed"),
    "Lindy": ("Growth Marketing Lead / Growth PM", "https://jobs.ashbyhq.com/lindy/ef2ea3db-4bb9-4885-91ef-c52266e354bf", "careers"),
    "Trust & Will": ("Business Development Representative (Remote)", "https://ats.rippling.com/trustandwill/jobs/95393433-bb3b-42b2-9567-faf86b3d2d6e", "careers+indeed"),
    "Mutiny": ("Head of GTM (Path to COO)", "https://jobs.ashbyhq.com/mutiny", "careers"),
    "Hex Technologies": ("Sales Development Representative (SF) + SDR Manager", "https://hex.tech/careers/sales-development-representative/", "careers"),
    "Orb": ("Sales Development Representative", "https://jobs.ashbyhq.com/orb/f3e023ea-6a91-4f43-a168-a09b187ee417", "careers"),
    "Numa": ("Sales Development Representative", "https://job-boards.greenhouse.io/numa", "careers"),
    "Cortex": ("Business Development Representative (+ BDR Manager)", "https://job-boards.greenhouse.io/cortex/jobs/5413866008", "careers+linkedin"),
    "Dropzone AI": ("Sales Development Representative / SDR Lead", "https://builtin.com/job/sales-development-representative-lead/8004118", "careers"),
    "Maxima AI": ("BDR / GTM Engineer / Founding SDR", "https://jobs.ashbyhq.com/Maxima/c88461f4-6d46-4e90-819a-9fcc49777c10", "careers"),
    "Buzz Solutions": ("Business Development Representative", "https://job-boards.greenhouse.io/buzzsolutions", "careers"),
    "Vendelux": ("Field Sales Development Representative / SDR", "https://jobs.ashbyhq.com/vendelux", "careers+linkedin"),
    "David Energy": ("Sales Development Representative", "https://jobs.ashbyhq.com/davidenergy/71ad4582-c73f-45a8-b0d7-8230733ba9e6", "careers"),
    "runZero, Inc": ("Business Development Representative (East)", "https://builtin.com/job/business-development-representative-east/9228241", "careers+indeed"),
    "11x AI": ("Growth Lead", "https://jobs.a16z.com/jobs/11x.ai", "careers"),
    "Pulley": ("Sales Development Representative", "https://jobs.ashbyhq.com/withpulley/f5c9f1d5-5e78-4dab-95db-81b3ee4e8a13", "careers"),
    "Lakera": ("Business Development Representative (founding)", "https://jobs.ashbyhq.com/lakera.ai", "careers"),
    "Raspberry AI": ("GTM Associate", "https://www.raspberry.ai/careers", "careers"),
    "Gravity": ("Business Development Representative (BDR)", "https://jobs.ashbyhq.com/GravityClimate", "careers"),
    "Cypris": ("Business Development Representative", "https://www.builtinnyc.com/job/business-development-representative/6484236", "careers+indeed"),
    "Stable": ("Sales Development Representative", "https://usestable.com/careers", "careers"),
    "Instrumentl": ("Inbound & Outbound Sales Development Representative", "https://instrumentl.com/careers", "careers"),
    "Nuvocargo": ("Sales Development Representative", "https://www.nuvocargo.com/careers/jobs/join-our-team-sales-development-representative/", "careers"),
    "Archy": ("Sales Development Representative", "https://jobs.ashbyhq.com/archy/1f3fa29a-c12d-4aa6-abdf-2aa98528f51f", "careers"),  # re-verified: fresh 2026-09-01
}
# Yes on LinkedIn only (web scan could not verify a current target role) — keep as signal
LINKEDIN_ONLY = {"Blee", "Agentio", "BriefCatch"}


def main():
    d = pd.read_csv(LEADS).fillna("")
    if "hiring_source" not in d.columns:
        d["hiring_source"] = ""
    for c in ("hiring_signal", "hiring_job_title", "hiring_job_url", "hiring_date", "hiring_source"):
        if c not in d.columns:
            d[c] = ""

    # reset to No, then apply
    d["hiring_signal"] = "No"
    d["hiring_source"] = ""
    for co, (role, url, src) in WEB.items():
        m = d["company_name"] == co
        if not m.any():
            print(f"WARN: '{co}' not found in leads")
            continue
        d.loc[m, "hiring_signal"] = "Yes"
        d.loc[m, "hiring_job_title"] = role
        d.loc[m, "hiring_job_url"] = url
        d.loc[m, "hiring_source"] = src
    for co in LINKEDIN_ONLY:
        m = d["company_name"] == co
        if m.any():
            d.loc[m, "hiring_signal"] = "Yes"
            d.loc[m, "hiring_source"] = "linkedin"
            # hiring_job_title / hiring_date already set from the LinkedIn pass

    d.to_csv(LEADS, index=False, encoding="utf-8")
    yes = d[d["hiring_signal"] == "Yes"]
    print(f"hiring_signal=Yes: {len(yes)} contact rows across {yes['company_name'].nunique()} companies")
    print(yes[["company_name", "hiring_job_title", "hiring_source"]].drop_duplicates("company_name").to_string(index=False))


if __name__ == "__main__":
    main()
