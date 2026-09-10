# Intent Signals (5)

Each company is checked for five buying signals. The two files here hold the raw hits for the two
scraped signals; the other three, plus the final Yes/No per company, live as columns in
`00_Final_Deliverable/scaleflow_leads_consolidated.csv`.

| # | Signal | How it's found | Weight | Data |
|---|---|---|---|---|
| 1 | **Hiring** (SDR/BDR/Outbound) | Apify LinkedIn Jobs actor **+ ATS boards read direct** (Greenhouse, Lever, Ashby — public APIs) | **+15** | `hiring_signal_jobs.csv` |
| 2 | **LinkedIn posts** | Apify Profile-Posts actor — founders posting on cold email / deliverability | **+10** (HIGH) / +3 (MED) | `post_signal_hits.csv` |
| 3 | **New sales-leader hire** | Apify Profile scraper — a Head of Sales / CRO hired recently (tenure) | **+10** (≤6mo) / +6 (≤12mo) | column in consolidated |
| 4 | **Tech stack** | Web scan — already using Instantly / Outreach / Apollo, or a CRM (HubSpot) | **+12** (outbound tool) / +4 (CRM) | column in consolidated |
| 5 | **Recent funding** | Crunchbase — raised recently = budget to buy & try new tools | **+8** (≤12mo) / +4 (≤24mo) | column in consolidated |

**Why these:** ScaleFlow is a cold-email / sales-engagement tool, so the strongest tells are a company
*scaling outbound now* (hiring SDRs, just hired a sales leader), *already doing outbound* (using an
outbound tool), *voicing the pain* (posting about deliverability), and *able to buy* (recent funding).

Counts: hiring **29** · LinkedIn posts **8** · recent funding **46** · outbound tech stack **41** · new sales-leader hires **10**.
