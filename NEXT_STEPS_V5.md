# Risk Analysis Tool — Next Steps (v5)

Review of `singhwilliam15/Risk-Analysis-Tool` at commit b90a3a7 (588 tests pass). Review fixes A–E
are done. Three gaps remain:

1. **The early-warning flags do not beat a naive rule on the whole market.** On every NSE stock
   from 2016 to 2024, "any price flag" has a lift of 1.13, while "down 30% in 6 months" has 2.25.
   The cause is the fixed rule "daily ES95 ≥ 5%", which fires on about 72% of stock-dates.
2. **The event pillar has never been validated.** The case-study disclosure files are empty and
   NSE's pledge history starts in 2021, so Zee, Jet Airways, Future Retail and DHFL cannot be tested.
3. **Housekeeping and one security point.** The demo snapshot is a pickle whose sha256 sits on
   the same branch it is loaded from.

## Master prompt (paste into Claude Code)

```
Read NEXT_STEPS_V5.md. Work through Phases F, G and H in order, ONE phase at a time:
plan mode → my approval → implement → pytest → run the app briefly → commit → summary with
real numbers → STOP. Branch: `next-steps-v5`. Never push.

Keep every existing rule of this project: point-in-time data only, never invent data, label
assumptions, offline tests against independent references, and update the README, the
methodology and the case studies after each phase.

Research discipline for Phase F (most important):
- Write the pre-registration (rules, periods, metrics, decision rule) and commit it BEFORE
  computing any result on the test period. Do not change it after seeing test results; if you
  find a bug, fix it, say so in the report, and show results before and after the fix.
- Report the outcome honestly, including if no new rule beats the momentum baseline.

If you disagree with anything in this file after reading the code, tell me with evidence
before changing anything.

Start with Phase F.
```

---

## Phase F — Early-warning flags that work across the market (true out-of-sample test)

```
Phase F of NEXT_STEPS_V5.md. Work in universe.py, case_studies/engine.py (price_flags) and
scripts/run_universe.py, and add a new module warnings_v2.py.

1. PERIODS (avoid leakage through the 12-month outcome window)
   - Design period: month-end dates Jan 2016 – Dec 2018 (outcomes end by Dec 2019).
   - Embargo: 2019 dates are not used, because their 12-month outcomes overlap the test period.
   - Test period: month-end dates Jan 2020 – Dec 2024 (outcomes need prices through Dec 2025;
     check the bhavcopies cover this and say so if they do not).
   - Outcome as now: a fall of ≥ 50% from the date's close within the next 12 months.

2. PRE-REGISTRATION: write docs/preregistration_warnings_v2.md and commit it before step 4.
   It must fix exactly these candidate rules, their parameters, the metrics and the decision rule:
   R1. Own-history ES: today's ES95 at or above the 90th percentile of the stock's own daily
       ES95 over the previous 3 years (needs at least 500 prior values).
   R2. Peer-relative ES: ES95 at or above the 90th percentile of its liquidity bucket on that date
       (terciles of median 60-day traded value across all stocks on that date).
   R3. Volatility shock with trend: EWMA volatility ≥ 1.5 × one-year volatility AND close below
       its 200-day average.
   R4. A combined score: a logistic regression fitted on the DESIGN period only, with a small
       fixed feature set: R1 percentile, R2 percentile, 6-month return, distance from the
       200-day average, lower-circuit days (60-day count), integrated-stress loss, log traded
       value. Its threshold is set in the design period to flag about 10% of stock-dates.
   Baselines unchanged: (a) down ≥ 30% in 6 months, (b) volatility in own top decile,
   (c) below 200-day average. Keep v1 ("any price flag") for comparison.
   Decision rule (fixed in advance): a new rule replaces the v1 market flag in the app only if,
   on the TEST period, its lift beats both v1 and baseline (a), with the 90% confidence interval
   of the lift difference vs (a) above zero. Otherwise the app keeps v1, shows the best rule
   alongside it, and the README says the new rules did not beat momentum.

3. METRICS (all stocks and the liquid subset, on the test period):
   precision, recall, lift, share of stock-dates flagged, mean lead time before the trough,
   and year-by-year lift. Confidence intervals by block bootstrap over DATES (stock-dates on
   the same date are correlated), 2,000 resamples.
   Also the INCREMENTAL value over momentum: among stock-dates NOT flagged by (a), the lift of
   each rule. This answers "does the tool add anything beyond 'it has already fallen'?".

4. RUN on the test period once. Write case_studies/results/warnings_v2_*.csv and a section
   "Warnings v2: out-of-sample test" in docs/case_studies.md with the tables and a plain-English
   verdict.

5. APPLY the decision rule. If a rule wins, wire it into the market flag (keeping v1 visible as
   "previous rule") and re-run the 220-date case studies with it. Either way, show on the app's
   Market page which rule is in use and its tested lift.

6. TESTS: R1–R4 on synthetic data with known answers; no feature uses data after its date;
   the logistic model is fitted only on design-period rows (assert on the dates); the bootstrap
   CI covers a known lift in simulation.
```

---

## Phase G — Validate the event pillar with historical pledge data

```
Phase G of NEXT_STEPS_V5.md.

1. DHFL NOW: the NSE bhavcopies already downloaded for the wider test include DHFL. Build
   case_studies/data/prices/DHFL.csv from them (adjusted the same way as in universe.py) and
   add DHFL to the case studies, which were missing it because Yahoo returns 404.

2. HISTORICAL PLEDGES (pre-2021): find official sources of quarterly promoter holding and
   pledged/encumbered shares for:
   Zee Entertainment (Dec 2016 – Dec 2018), Jet Airways (Mar 2017 – Mar 2019), Future Retail
   (Sep 2018 – Jun 2020), DHFL (Mar 2017 – Jun 2019), Yes Bank (Mar 2018 – Dec 2019),
   Adani Enterprises (Dec 2020 – Dec 2022) and the 10 control stocks for the same quarters.
   - Check BSE's quarterly shareholding-pattern filings first, then NSE's older shareholding
     filings and SAST Regulation 31 (encumbrance) disclosures.
   - If a site allows scripted download, add it to scripts/fetch_disclosures.py with the source
     URL per row. If it blocks scripts, STOP and give me a precise checklist (company, quarter,
     page, what to save, file name) and the CSV template, then wait while I collect them.
   - Point in time: use the actual filing date. If it is unknown, use quarter end + 21 days
     (the filing deadline) and label it "deadline, not actual date".
   - Never fill a quarter from memory or estimates; a missing quarter stays missing.

3. CASE STUDIES: re-run with the event pillar on. For each case and date, record the event tier,
   which signals fired, and the lead time versus the price flags and the baselines. Add the
   events row to the hits/misses/false-positives table, with the control group's false
   positives from the same data.

4. WIDER EVENT TEST (2021–2024, NSE pledge data that already exists): for every NSE company with
   shareholding filings, test whether (i) pledged % of promoter holding ≥ 50%, (ii) a rise of
   ≥ 10 percentage points in pledged % over 4 quarters, and (iii) the full event tier
   (Elevated/High) predict a ≥ 50% fall within 12 months. Same metrics as Phase F, including the
   incremental lift over baseline (a). Pre-register these rules before running, as in Phase F.

5. JUMP OVERLAY: revisit the jump default (currently 0) ONLY with the event-tier evidence from
   steps 3–4. If the High tier shows stock-specific crash rates above the stock's own history,
   set the default from those base rates with a confidence interval; otherwise keep 0 and say so.

6. Update the README's findings, docs/case_studies.md, methodology §12 and the interview story.
```

---

## Phase H — Housekeeping and security

```
Phase H of NEXT_STEPS_V5.md.

1. SNAPSHOT INTEGRITY: stop loading a pickle from the network. Store the snapshot as Parquet
   (tables) plus JSON (metadata and scalars), and have the app verify a sha256 that is committed
   on main (written by the workflow as a PR or a small commit to a file on main), not one that
   sits on the same branch as the data. Keep the local bundled fallback. Tests: a tampered file is
   rejected; the app still starts offline.
2. README: make the test count come from a check (test_docs.py) so it can never go stale again
   (it says 584; there are 588 or more now). Re-check every number in the README against the
   current results files.
3. Move REVIEW_FIXES_V4.md, RISK_TOOL_PLAN_V3.md and this file into docs/plans/ and fix any
   links.
4. List the manual steps for me: delete the merged branches (review-fixes-v4, next-steps-v5
   after merge); archive the old VaR-Tool repo and decide between Trading-System and Trading_Tool;
   check that the live app at risk-analysis-tool.streamlit.app loads the new snapshot.
```

---

## After this

Build the website from WEBSITE_PLAN.md. Its Case Studies page should lead with the
out-of-sample results from Phases F and G.
