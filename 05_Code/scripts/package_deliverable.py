#!/usr/bin/env python3
"""Assemble the final structured deliverable folder (copies curated assets by pipeline stage)."""
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PKG = ROOT.parent / "ScaleFlow AI - 100 Verified Leads"

# stage folder -> list of (source path relative to ROOT)
LAYOUT = {
    "00_Final_Deliverable": [
        "data/people/scaleflow_leads_consolidated.csv",
        "data/people/scaleflow_clay_upload.csv",
        "data/people/scaleflow_final_leads.csv",
    ],
    "01_Source_and_Clean": [
        "data/raw/crunchbase_raw.csv",
        "data/raw/clutch_raw.csv",
        "data/clean/companies_clean.csv",
        "data/clean/companies_with_full_info.csv",
    ],
    "02_Decision_Makers_and_Qualify": [
        "data/people/decision_makers_all.csv",
        "data/people/qualified_leads.csv",
        "data/people/final_qualified_leads.csv",
    ],
    "03_Intent_Signals": [
        "data/people/hiring_signal_jobs.csv",
        "data/people/post_signal_hits.csv",
    ],
    "04_Emails": [
        "data/people/gap_new_people.csv",
        "data/people/scaleflow_clay_to_enrich.csv",
        "data/people/scaleflow_clay_no_email.csv",
    ],
}
ROOT_FILES = [
    ("data/people/scaleflow_workflow.png", "Lead_Generation_Flow.png"),
    ("data/people/scaleflow_workflow.pdf", "Lead_Generation_Flow.pdf"),
    ("LOOM_SCRIPT.md", "Loom_Script.md"),
    ("workflow.html", "workflow.html"),
]
REFERENCE = ["PROJECT_STATE.md", "WORKFLOW.md"]
CODE_DIRS = ["scripts", "scrapers", "config", "clean"]
CODE_FILES = ["requirements.txt", ".env.example"]


def main():
    if PKG.exists():
        shutil.rmtree(PKG)
    PKG.mkdir(parents=True)

    for folder, files in LAYOUT.items():
        d = PKG / folder
        d.mkdir(parents=True, exist_ok=True)
        for f in files:
            src = ROOT / f
            if src.exists():
                shutil.copy2(src, d / src.name)
            else:
                print("  MISSING:", f)

    for src_rel, dst_name in ROOT_FILES:
        src = ROOT / src_rel
        if src.exists():
            shutil.copy2(src, PKG / dst_name)

    ref = PKG / "_reference"
    ref.mkdir(exist_ok=True)
    for f in REFERENCE:
        if (ROOT / f).exists():
            shutil.copy2(ROOT / f, ref / f)

    code = PKG / "05_Code"
    code.mkdir(exist_ok=True)
    for dname in CODE_DIRS:
        s = ROOT / dname
        if s.exists():
            shutil.copytree(s, code / dname, dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".env"))
    for f in CODE_FILES:
        if (ROOT / f).exists():
            shutil.copy2(ROOT / f, code / f)

    # count
    n = sum(1 for _ in PKG.rglob("*") if _.is_file())
    print(f"PACKAGE built -> {PKG}")
    print(f"  {n} files across:", ", ".join(sorted([p.name for p in PKG.iterdir() if p.is_dir()])))


if __name__ == "__main__":
    main()
