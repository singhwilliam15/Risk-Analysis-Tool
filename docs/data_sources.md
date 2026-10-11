# Data sources, their terms, and what this project may do with them

Checked on 11 Oct 2026 (FINAL_PLAN_V6, Phase 1, step 10). This is a record of what each source's published terms say
and the decisions taken from them. It is not legal advice.

## The rule this project follows

Data are downloaded automatically only where the source's terms allow automated collection, and redistributed only
where the terms allow it. Where the terms forbid it, or could not be checked, the dataset goes on a manual
checklist, or waits for written permission.

## NSE (nseindia.com, nsearchives.nseindia.com)

**What the terms say:**
- [Terms of Use](https://www.nseindia.com/static/nse-terms-of-use): "User is prohibited to conduct any systematic or
  automated data collection activities (including scraping, data mining, data extraction and data harvesting)".
  They also say content "shall not be copied, modified, … reproduced, uploaded, transmitted, posted, stored …,
  distributed, displayed, … published … in any form, without prior written permission of NSE."
- [Copyright](https://www.nseindia.com/static/nse-copyright): "Users may view, print copies and download the Content
  for personal, non-commercial or educational purpose … and provide full acknowledgement that the Content originated
  from this Website".
- [Disclaimer](https://www.nseindia.com/static/nse-disclaimer): "Research-oriented data (not including any data for
  commercial, speculative or investigative purposes), can be downloaded/accessed/made available without cost,
  provided it does not exceed in aggregate the volume threshold of 2GB set by SEBI via SEBI Circular dated December
  20th, 2024."
- robots.txt allows every path except `/market-data-test`.

**Access:** NSE silently drops requests that identify themselves as scripts (tested on 11 Oct 2026). Scripts in this
repository used a browser User-Agent.

**What the project has already done** (October 2026, before these terms were read):
- automated downloads of daily bhavcopies (about 3,700 files), quarterly shareholding XBRL (27,033 filings),
  disclosure lists, bank results XBRL, and a partial run of the v6 archive and announcement downloaders (stopped);
- committed NSE-derived files, listed below.

**Decision (11 Oct 2026):**
- no new automated NSE collection;
- a request for written permission, for non-commercial research use and for redistributing derived results, is
  drafted in [docs/permissions/nse_permission_request.md](permissions/nse_permission_request.md);
- the v6 downloaders (`scripts/fetch_archives.py`, `scripts/fetch_announcements.py`, `scripts/nse_client.py`) are
  kept but not run, until permission is granted.

**NSE-derived files: what was done (11 Oct 2026, branch `final-v6`)**

The bulk NSE datasets that only the research scripts read are **no longer tracked in git**:
- the shareholding history 2021–2024;
- the raw ASM, GSM and rating JSON and the pledge scan;
- the case-study pledge file;
- DHFL's bhavcopy prices.

They stay on the owner's computer (git-ignored), so every script and re-run still works locally. Earlier commits in
git history still contain them; rewriting history is a separate decision.

The small current lists the app read (price bands, F&O bans, pledges, ratings and surveillance of 2 Oct 2026)
were **untracked on 12 Oct 2026** as well, by the owner's decision to continue without NSE data. The repository
now ships no NSE lists. Users download the lists from NSE themselves (NSE allows personal use) and upload them in
the app (Overview → Disclosure data, or the Promoter Pledge & Governance page). Uploads last for the session. Run
locally, the app also reads files saved in `data/disclosures/` with a manifest; these are git-ignored. With no files,
the pledge page says "not checked" instead of showing a clear status. The table shows each file's status:

| Kind | Files |
| --- | --- |
| NSE lists and filings, close to raw | **Untracked, kept locally:** `data/disclosures/raw/`, `data/disclosures/history/shareholding_2021_2024*.csv`, `case_studies/data/disclosures/pledges_nse_history_2021_2024.csv`, `case_studies/data/prices/DHFL.csv`. `data/disclosures/` current lists (sec_list, fo_secban, pledges, ratings, surveillance) and their manifest (untracked 12 Oct 2026) |
| Values taken from company filings on NSE | `data/banks/*.csv` (results XBRL and annual reports); `case_studies/data/fundamentals/*.csv` (annual reports) |
| Small test excerpts | `test_data/nse/*` |
| Derived statistics only | `case_studies/results/*` (lifts, counts, rates); `case_studies/results/warnings_v2_reference.json` (ES percentiles) |

## BSE (bseindia.com)

Its API answers HTTP 403 to scripts, and its pages refuse an honest User-Agent (HTTP 406). The terms could not be
read by script. **Decision:** no automated access. BSE items go on the manual checklist.

## Rating agencies

| Agency | What was found | Decision |
| --- | --- | --- |
| ICRA | [Disclaimer](https://www.icra.in/Home/Disclaimer): users "may not … copy, distribute, … reproduce, publish, … 'scrape', data mine, or otherwise use any information or material obtained from or through this Site" beyond occasional personal, non-commercial printing and downloading | No automation |
| CRISIL Ratings | The terms-of-use page is rendered by JavaScript, so its text could not be checked; robots.txt blocks named crawlers | Not verified, so no automation |
| CARE Ratings | robots.txt allows all; no terms page found at the usual address | Not verified, so no automation |
| India Ratings | robots.txt allows public paths; terms pages are rendered by JavaScript | Not verified, so no automation |
| Acuité | No robots.txt; the disclaimer covers the use of ratings, not access | Not verified, so no automation |

The default-rate tables in `data/credit/rating_default_rates.csv` are figures cited from published default studies
(CRISIL FY2025, ICRA FY2025), with page references. Short factual citations are kept.

## Regulators

- **SEBI:** the terms pages were not found at the usual addresses.
- **RBI:** the copyright page is rendered by JavaScript, so its wording could not be checked by script.

**Decision:** nothing automated from either until the terms are read by hand. RBI's bank-wise statistics would
answer the "capital ratios for every bank" item, and are on the manual checklist.

## Other sources the project uses (not part of Phase 1)

- Yahoo Finance prices, through `yfinance`, in the app and the daily snapshot.
- IIM Ahmedabad and Kenneth French factor files (`data/factors/`).

Their terms have not been reviewed here. They should be checked the same way before the project is distributed
further.
