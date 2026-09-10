#!/usr/bin/env python3
"""Build the +50 expansion people dataset (founder/CEO per new company + LinkedIn), merged
with company fields from expansion_companies.csv. Output: data/people/expansion_people.csv
(ready for GetLeads enrichment, then Clay formatting)."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import pandas as pd  # noqa
from scrapers.common import clean_domain  # noqa

# domain -> (founder, title, linkedin_url, status)   status: ok | review-left | no-linkedin
F = {
 "1kosmos.com": ("Hemen Vimadalal", "Founder & CEO", "https://www.linkedin.com/in/hemen-r-vimadalal-2561b02", "ok"),
 "1valet.com": ("Jean-Pierre Poulin", "Founder / Exec Chairman", "https://ca.linkedin.com/in/jean-pierre-poulin-04a5205a", "ok"),
 "1mind.com": ("Amanda Kahlow", "Founder & CEO", "https://www.linkedin.com/in/amandakahlow", "ok"),
 "3aminnovations.com": ("Patrick O'Connor", "President & Founder", "", "no-linkedin"),
 "3dcloud.com": ("Beck Besecker", "Founder & CEO", "https://www.linkedin.com/in/bbesecker", "ok"),
 "5x5.ai": ("Anne Zink", "Founder & CEO", "https://www.linkedin.com/in/annemzink", "ok"),
 "911inform.com": ("Ivo Allen", "Founder & CEO", "https://www.linkedin.com/in/ivoallen", "ok"),
 "arwall.co": ("Rene Amador", "Co-Founder & CEO", "https://www.linkedin.com/in/rlamador", "ok"),
 "aampe.com": ("Paul Meinshausen", "Co-Founder & CEO", "https://www.linkedin.com/in/paulmeinshausen", "ok"),
 "abacum.io": ("Julio Martínez", "Co-Founder & CEO", "https://www.linkedin.com/in/thejuliomartinez", "ok"),
 "acalvio.com": ("Raj Gopalakrishna", "Co-founder & Chief Architect", "https://www.linkedin.com/in/rajgopalakrishna", "ok"),
 "acelabusa.com": ("Vardhan Mehta", "Co-Founder & CEO", "https://www.linkedin.com/in/vardhan-acelab", "ok"),
 "adept.ai": ("David Luan", "Co-Founder (departed)", "https://www.linkedin.com/in/jluan", "review-left"),
 "aerospike.com": ("Srini V. Srinivasan", "Founder & CTO", "https://www.linkedin.com/in/drvsrini", "ok"),
 "aigen.io": ("Kenny Lee", "Co-Founder & CEO", "https://www.linkedin.com/in/kennyklee", "ok"),
 "airspace-intelligence.com": ("Phillip Buckendorf", "Co-Founder & CEO", "https://www.linkedin.com/in/phillipbuckendorf", "ok"),
 "airgarage.com": ("Jonathon Barkl", "Co-Founder & CEO", "https://www.linkedin.com/in/jonathonbarkl", "ok"),
 "airia.com": ("John Marshall", "Co-Founder & Chairman", "https://www.linkedin.com/in/john-marshall-2b6b3013", "ok"),
 "albertinvent.com": ("Nick Talken", "Co-Founder & CEO", "https://www.linkedin.com/in/nick-talken-b720ba42", "ok"),
 "alignedup.com": ("Gal Aga", "Co-Founder & CEO", "https://il.linkedin.com/in/galaga", "ok"),
 "alivecor.com": ("David Albert", "Co-Founder & CMO", "https://www.linkedin.com/in/drdavealbert", "ok"),
 "allhere.com": ("Joanna Smith-Griffin", "Founder (departed)", "", "review-left"),
 "alluxio.io": ("Haoyuan Li", "Founder & CEO", "https://www.linkedin.com/in/haoyuanli", "ok"),
 "alvys.com": ("Nick Darman", "Founder & CEO", "https://www.linkedin.com/in/ndarman", "ok"),
 "amalgamrx.com": ("Ryan Sysko", "Co-Founder & CEO", "https://www.linkedin.com/in/ryansysko", "ok"),
 "amaze.co": ("Steve Newcomb", "Founder (not at domain)", "", "review-left"),
 "ambientscientific.ai": ("Gajendra Prasad Singh", "Founder & CEO", "https://www.linkedin.com/in/gp-singh-340732", "ok"),
 "ambition.com": ("Travis Truett", "Co-Founder & CEO", "https://www.linkedin.com/in/travistruett", "ok"),
 "sayanchor.com": ("Rom Lakritz", "Co-Founder & CEO", "https://il.linkedin.com/in/romlakritz", "ok"),
 "anecdotes.ai": ("Yair Kuznitsov", "Co-Founder & CEO", "https://il.linkedin.com/in/yair-kuznitsov", "ok"),
 "anrok.com": ("Michelle Valentine", "Co-Founder & CEO", "https://www.linkedin.com/in/michellevalentinehk", "ok"),
 "getanswersnow.com": ("Jeff Beck", "Co-Founder & CEO", "https://www.linkedin.com/in/jeffbeck11", "ok"),
 "antaris.space": ("Tom Barton", "Co-Founder & CEO", "https://www.linkedin.com/in/tkbarton", "ok"),
 "apex.ai": ("Jan Becker", "Co-Founder, President & CEO", "https://www.linkedin.com/in/janbecker23", "ok"),
 "apiiro.com": ("Idan Plotnik", "Co-Founder & CEO", "https://www.linkedin.com/in/idanplotnik", "ok"),
 "apono.io": ("Rom Carmel", "Co-Founder & CEO", "https://www.linkedin.com/in/romcarmel", "ok"),
 "archera.ai": ("Aran Khanna", "Co-Founder & CEO", "https://www.linkedin.com/in/aran-khanna-3b338055", "ok"),
 "architect.co": ("Brett Harrison", "Founder & CEO", "https://www.linkedin.com/in/brettaharrison", "ok"),
 "arintra.com": ("Nitesh Shroff", "Co-Founder & CEO", "https://www.linkedin.com/in/nitesh-shroff-08855148", "ok"),
 "aristamd.com": ("Rebecca Cofinas", "Founder (departed)", "", "review-left"),
 "arize.com": ("Jason Lopatecki", "Co-Founder & CEO", "https://www.linkedin.com/in/jason-lopatecki-9509941", "ok"),
 "arkestro.com": ("Edmund Zagorin", "Founder & CSO", "https://www.linkedin.com/in/edmund-zagorin-41291b13", "ok"),
 "arketa.com": ("Rachel Lea Fishman", "Co-Founder & CEO", "https://www.linkedin.com/in/rachelleafishman", "ok"),
 "fordefi.com": ("Josh Schwartz", "Co-Founder & CEO", "https://www.linkedin.com/in/josh-schwartz-9339654", "ok"),
 "arthur.ai": ("Adam Wenchel", "Co-Founder & CEO", "https://www.linkedin.com/in/apwenchel", "ok"),
 "artie.com": ("Jacqueline Cheong", "Co-Founder & CEO", "https://www.linkedin.com/in/jacqueline-cheong", "ok"),
 "useascend.com": ("Andrew Wynn", "Co-Founder & Co-CEO", "https://www.linkedin.com/in/wynnandrewj", "ok"),
 "ashbyhq.com": ("Benjamin Encz", "Co-Founder & CEO", "https://www.linkedin.com/in/benjaminencz", "ok"),
 "assembled.com": ("Ryan Wang", "Co-Founder & CEO", "https://www.linkedin.com/in/ryanywang", "ok"),
 "ataraxis.ai": ("Jan Witowski", "Founder & CEO", "https://www.linkedin.com/in/jan-witowski", "ok"),
}


def main():
    comp = pd.read_csv(ROOT / "data/people/expansion_companies.csv").fillna("")
    comp["dom"] = comp["domain"].map(lambda x: clean_domain(str(x)))
    rows = []
    for _, r in comp.iterrows():
        dom = r["dom"]
        fn, title, li, status = F.get(dom, ("", "", "", "no-match"))
        rows.append({
            "company_name": r["company_name"], "domain": dom, "website": r["website"],
            "country": r["country"], "headcount": r["headcount_bucket"], "founded_year": r["founded_year"],
            "last_funding_type": r["last_funding_type"], "last_funding_amount": r["last_funding_amount"],
            "full_name": fn, "title": title, "person_linkedin_url": li, "contact_status": status,
            "email": "", "email_status": "",
        })
    out = pd.DataFrame(rows)
    out.to_csv(ROOT / "data/people/expansion_people.csv", index=False, encoding="utf-8")
    print(f"expansion_people.csv: {len(out)} companies | ok={ (out['contact_status']=='ok').sum() } | "
          f"review-left={ (out['contact_status']=='review-left').sum() } | no-linkedin={ (out['contact_status']=='no-linkedin').sum() }")


if __name__ == "__main__":
    main()
