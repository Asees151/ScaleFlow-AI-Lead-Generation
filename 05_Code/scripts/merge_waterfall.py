#!/usr/bin/env python3
"""
Merge Clay email-waterfall results (30 no-email companies) back into clay_ready_leads.csv,
with the same domain-match rule we use everywhere (reject an email whose domain != company
domain -> that person moved employers / wrong company). Then report coverage + gaps + alternates.

Usage: python scripts/merge_waterfall.py
"""
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
from scrapers.common import clean_domain  # noqa: E402

LEADS = ROOT / "data/people/clay_ready_leads.csv"

# company_name -> email returned by Clay waterfall for its PRIMARY contact (raw, pre-validation)
WATERFALL = {
    "Unframe": "ryan.roberts@unframe.ai", "Raspberry AI": "marc@aiuc.com", "Blee": "lylle@blee.com",
    "Trunk Tools": "ryan.franco@trunk.tools", "Proxy Foods": "orsalia.michailidi@proxyfoods.ai",
    "Canvas Envision": "matt@canvasenvision.com", "Richtech Robotics": "aaron.m@richtechrobotics.com",
    "DataPelago": "dan@datapelago.net", "Maxima AI": "tracy@maxima.ai", "InsightFinder AI": "dan@insightfinder.com",
    "CREWASIS": "", "Threater": "", "Roam": "", "Mos": "", "Voly": "nicole@voly.co.uk", "Warp": "",
    "RAD Intel": "", "Pasito": "pauline@pasito.ai", "Malama Health": "marin@heymalama.com",
    "ZBD": "andre@zbd.gg", "VESSL AI": "", "OpenMind": "clara@openmind.org", "SGNL": "nikita@sgnl.ai",
    "Pulley": "", "DataHub": "swaroop.jagadish@datahub.com", "Opsera": "kumar@opsera.ai",
    "FriendliAI": "bgchun@friendli.ai", "Simon AI": "alexis.bennett@apollographql.com",
    "Noah": "jameson.lobb@noah.com", "aixplain": "",
}
# known legit alternate corporate domains (same company, different email domain)
ALT_OK = {"voly.co.uk": "volygroup.com", "datapelago.net": "datapelago.io"}


def main():
    d = pd.read_csv(LEADS).fillna("")
    added, rejected, notfound = [], [], []
    for co, em in WATERFALL.items():
        if not em:
            notfound.append(co)
            continue
        m = (d["company_name"] == co) & (d["is_primary_contact"] == "Yes")
        if not m.any():
            continue
        codom = clean_domain(str(d.loc[m, "domain"].iloc[0]))
        emdom = clean_domain(em)
        ok = (emdom == codom) or (emdom in ALT_OK and ALT_OK[emdom] == codom)
        if ok:
            d.loc[m, "email"] = em
            d.loc[m, "email_status"] = "VALID (clay-waterfall)"
            d.loc[m, "email_source"] = "clay-waterfall"
            added.append((co, em))
        else:
            rejected.append((co, em, f"{emdom} != {codom}"))
    d.to_csv(LEADS, index=False, encoding="utf-8")

    emailed = d[d["email"].astype(str).str.len() > 0]["company_name"].nunique()
    print(f"ADDED {len(added)} valid emails:")
    for co, em in added:
        print(f"   + {co}: {em}")
    print(f"\nREJECTED (wrong-company domain — person moved): {len(rejected)}")
    for co, em, why in rejected:
        print(f"   x {co}: {em}  ({why})")
    print(f"\nWATERFALL found nothing for: {len(notfound)} -> {notfound}")

    gaps = sorted(set([c for c, *_ in rejected] + notfound))
    print(f"\n=== COVERAGE NOW: {emailed}/102 companies have a verified email | {102-emailed} gaps ===")
    print("GAP companies:", gaps)
    print("\nAlternate contacts available at gap companies:")
    for co in gaps:
        others = d[(d["company_name"] == co) & (d["is_primary_contact"] != "Yes")]
        alts = [f"{r['contact_name']} ({r['contact_title']})" for _, r in others.iterrows()]
        print(f"   {co}: {len(alts)} alt(s) -> {alts if alts else 'NONE (only 1 contact)'}")


if __name__ == "__main__":
    main()
