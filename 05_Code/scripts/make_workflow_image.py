#!/usr/bin/env python3
"""Render the lead-gen workflow HORIZONTALLY as a polished PNG + PDF.
Two-tone cards (colored header + light body), horizontal flow, intent band, weights panel.
Output: data/people/scaleflow_workflow.png / .pdf"""
import sys
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

ROOT = Path(__file__).resolve().parent.parent
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# (title, [detail lines], body color, accent color)
STAGES = [
    ("SOURCE", ["~1,730 companies", "Crunchbase + Clutch", "Playwright + Chrome +", "Python (no Cloudflare)"], "#EAF2FE", "#2E6FDB"),
    ("CLEAN & MERGE", ["~1,650 companies", "Python (pandas)", "capture LinkedIn,", "site, size, funding"], "#EAF2FE", "#2E6FDB"),
    ("DECISION MAKERS", ["batch of ~225", "Apify Leads Finder", "+ BlitzAPI Employee", "Finder API endpoint"], "#EAF7EE", "#2E9E4F"),
    ("QUALIFY", ["100 companies", "kept decision-makers,", "disqualified VP-of-", "Sales as the contact"], "#EAF7EE", "#2E9E4F"),
    ("INTENT SIGNALS", ["5 signals,", "scored & weighted", "", "see below  ↓"], "#FFF6E3", "#E0A008"),
    ("EMAILS", ["100% verified", "GetLeads ~70%", "+ Clay multi-vendor", "waterfall ~30%"], "#FDECEC", "#D2453F"),
    ("SCORE & TIER", ["weighted signals", "→ 0-100 score", "3 tiers", ""], "#F1EBFB", "#7B4FCB"),
    ("DELIVERABLE", ["100 leads", "consolidated CSV", "score · tier ·", "signals · email"], "#F1EBFB", "#7B4FCB"),
]
SIGNALS = [
    ("HIRING", ["Apify LinkedIn Jobs actor", "+ ATS boards read direct:", "Greenhouse · Lever · Ashby", "(public job APIs)"]),
    ("LINKEDIN POSTS", ["Apify Profile-Posts actor", "founders posting on", "cold email /", "deliverability"]),
    ("NEW SALES HIRE", ["Apify Profile scraper", "recently hired a", "Head of Sales / CRO", "(building GTM)"]),
    ("TECH STACK", ["web scan — do they use", "Instantly / Outreach /", "Apollo, or a CRM", "(HubSpot) = fit"]),
    ("RECENT FUNDING", ["Crunchbase data", "raised recently =", "budget to buy &", "try new tools"]),
]
WLEFT = ["INTENT — 55 pts", "Hiring SDR/BDR/Outbound  .............  +15",
         "Uses outbound tool (Outreach/Salesloft/Apollo)  +12   (CRM-only +4)",
         "New sales-leader hire ≤ 6mo  ......  +10   (≤ 12mo +6)",
         "LinkedIn post: cold email/deliverability  +10   (outbound/GTM +3)",
         "Recent funding ≤ 12mo  ...............  +8   (≤ 24mo +4)"]
WRIGHT = ["FIT — 45 pts", "Verified email  ....................  +15",
          "Seniority: Sales Leader 20 · Founder 15 ·", "               Sales/Growth 15 · Other 5",
          "Company has a senior sales leader  ...  +10", ""]


def card(ax, x, y, w, h, num, title, lines, body, accent, hh=3.4, tfs=8.4, lfs=7.4):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.15,rounding_size=0.9",
                                linewidth=0, facecolor=accent, zorder=1))
    ax.add_patch(FancyBboxPatch((x + 0.35, y + 0.35), w - 0.7, h - hh - 0.35,
                                boxstyle="round,pad=0.1,rounding_size=0.6",
                                linewidth=0, facecolor=body, zorder=2))
    label = f"{num} · {title}" if num else title
    ax.text(x + w / 2, y + h - hh / 2, label, ha="center", va="center", fontsize=tfs,
            fontweight="bold", color="white", zorder=3)
    for i, ln in enumerate(lines):
        ax.text(x + w / 2, y + h - hh - 1.7 - i * 1.95, ln, ha="center", va="top",
                fontsize=lfs, color="#222", zorder=3)


def main():
    fig, ax = plt.subplots(figsize=(24, 12))
    ax.set_xlim(0, 100); ax.set_ylim(0, 100); ax.axis("off")
    fig.patch.set_facecolor("white")
    ax.add_patch(FancyBboxPatch((1, 91), 98, 8, boxstyle="round,pad=0.2,rounding_size=1.0",
                                linewidth=0, facecolor="#101828"))
    ax.text(50, 96.4, "Lead Generation Flow", ha="center", va="center", fontsize=23,
            fontweight="bold", color="white")
    ax.text(50, 92.7, "ScaleFlow AI  ·  intent-driven, 100% verified lead list  ·  connectors at every step",
            ha="center", va="center", fontsize=11.5, color="#B8C2D9", style="italic")

    # main pipeline row
    n = len(STAGES); mx = 1.5; gap = 1.4
    bw = (100 - 2 * mx - (n - 1) * gap) / n
    bh = 14; by = 74
    xs = []
    for i, (t, lines, body, accent) in enumerate(STAGES):
        x = mx + i * (bw + gap); xs.append(x)
        card(ax, x, by, bw, bh, i + 1, t, lines, body, accent)
        if i < n - 1:
            ax.add_patch(FancyArrowPatch((x + bw + 0.1, by + bh / 2), (x + bw + gap - 0.1, by + bh / 2),
                         arrowstyle="-|>", mutation_scale=16, linewidth=2, color="#98A2B3"))
    sx = xs[4] + bw / 2
    ax.add_patch(FancyArrowPatch((sx, by), (sx, 69), arrowstyle="-|>", mutation_scale=18, linewidth=2, color="#E0A008"))

    # intent band
    ax.text(50, 70, "INTENT SIGNALS  (5)  —  scored & weighted", ha="center", va="top",
            fontsize=13.5, fontweight="bold", color="#9A6B00")
    ns = len(SIGNALS); smx = 2.5; sgap = 1.6
    sbw = (100 - 2 * smx - (ns - 1) * sgap) / ns
    sbh = 15.5; sby = 48
    for i, (t, lines) in enumerate(SIGNALS):
        x = smx + i * (sbw + sgap)
        card(ax, x, sby, sbw, sbh, "", t, lines, "#FFFBF0", "#E0A008", hh=3.2, tfs=8.6)

    # weights panel
    ax.add_patch(FancyBboxPatch((2.5, 3.5), 95, 40, boxstyle="round,pad=0.3,rounding_size=1.2",
                                linewidth=1.5, edgecolor="#D0D5DD", facecolor="#F8F9FB"))
    ax.text(50, 41.5, "SCORING WEIGHTS  (0–100)", ha="center", va="top", fontsize=13.5,
            fontweight="bold", color="#101828")
    ax.plot([50, 50], [7.5, 38], color="#E4E7EC", linewidth=1.2)
    for i, ln in enumerate(WLEFT):
        b = ln.endswith("pts")
        ax.text(6, 36 - i * 4.5, ln, ha="left", va="top", fontsize=11 if b else 9.6,
                fontweight="bold" if b else "normal", color="#1D2939" if b else "#344054")
    for i, ln in enumerate(WRIGHT):
        b = ln.endswith("pts")
        ax.text(53, 36 - i * 4.5, ln, ha="left", va="top", fontsize=11 if b else 9.6,
                fontweight="bold" if b else "normal", color="#1D2939" if b else "#344054")
    ax.text(50, 6.2, "Score  →  Tier 1 Hot ≥ 90    ·    Tier 2 Warm 80–89    ·    Tier 3 Qualified 70–79",
            ha="center", va="top", fontsize=10.8, fontweight="bold", color="#475467")

    for ext in ("png", "pdf"):
        p = ROOT / f"data/people/scaleflow_workflow.{ext}"
        fig.savefig(p, dpi=180 if ext == "png" else None, bbox_inches="tight", facecolor="white")
    print("wrote scaleflow_workflow.png and .pdf")


if __name__ == "__main__":
    main()
