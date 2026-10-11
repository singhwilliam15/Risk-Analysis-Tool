# FINAL_PLAN_V6, Phase 1: manual checklist

Phase 1 stopped on 11 Oct 2026, because the official sources' terms forbid automated collection or couldn't be
checked (see [docs/data_sources.md](../data_sources.md)). Every item below can be done in one of two ways:
- **with permission:** once NSE grants written permission (draft request:
  [nse_permission_request.md](../permissions/nse_permission_request.md)), the ready scripts can be run;
- **by hand:** download the pages yourself for personal, educational use, which NSE's copyright page allows, and
  keep them out of the public repository unless redistribution is allowed.

| # | Dataset | Source | Ready script (only with permission) | Size of the job |
| --- | --- | --- | --- | --- |
| 1 | Shareholding / pledges, 2025 → latest quarter | NSE shareholding-pattern XBRL | `scripts/fetch_shareholding_history.py` (extend the quarters) | ~12,000 filings |
| 2 | Pledges before 2021 (cases and controls) | BSE shareholding pages | none (BSE refuses scripts) | 226 pages by hand (Phase G list) |
| 3 | Auditor events, 2014 → today | NSE announcements: "Change in Auditors", "Statement on Impact of Audit Qualifications" | `scripts/fetch_announcements.py` | ~650 listings and a few thousand PDFs |
| 4 | Rating actions, 2014 → today | NSE announcements: "Credit Rating"; agency rationale pages | `scripts/fetch_announcements.py` | ~25,000 PDFs |
| 5 | F&O ban list, 2016 → today | NSE archive `fo_secban_DDMMYYYY.csv` | `scripts/fetch_archives.py` | ~2,700 small files |
| 6 | Price-band history, 2016 → today | NSE archive `eq_band_changes_DDMMYYYY.csv` | `scripts/fetch_archives.py` | ~2,700 small files |
| 7 | Surveillance (ASM/GSM) history | NSE publishes current lists only | none: start a daily record (Phase 2 ledger) once permitted | daily |
| 8 | Group links | promoter names in shareholding XBRL (item 1) | to be written after item 1 | — |
| 9 | Bank capital ratios for every bank | RBI bank-wise statistics; Pillar 3 disclosures on bank websites | none (terms not verified) | ~40 banks |
| 10 | Prices to the latest trading day (needed for the 2025 holdout) | NSE bhavcopies | `scripts/fetch_bhavcopy.py --end <today>` | ~180 files |

**Local leftovers:** the stopped runs left 125 F&O ban files and 58 weeks of announcement listings in `data/raw/`.
They are git-ignored, unused, about 0.5 MB, and kept until you decide.
