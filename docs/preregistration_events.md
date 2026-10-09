# Pre-registration: the event pillar on every NSE stock, 2021–2024

Written and committed on 10 Oct 2026, **before** any result of this test was computed (NEXT_STEPS_V5.md, Phase G,
step 4). The code (`event_universe.py`, `scripts/run_event_test.py`) and its tests are in the same commit. The
shareholding data were still downloading at the time, so no outcome had been looked at. Nothing below changes
after results are seen. Any bug fix goes in a separate commit, with the results shown before and after.

## Question

Do the event pillar's pledge signals warn of a ≥ 50% fall within 12 months? Do they add anything beyond the
momentum rule "down ≥ 30% in 6 months"? And do the tiers justify a non-zero jump overlay?

## Data

- **Shareholding:** NSE's quarterly shareholding-pattern XBRL for every company, quarters Sep 2021 – Dec 2024
  (`scripts/fetch_shareholding_history.py`, `data/disclosures/history/shareholding_2021_2024.csv`).
  - **Point in time:** each quarter's *original* filing, public from its broadcast date. Later revisions are not
    used.
  - **Unreadable filings** are listed, not filled.
  - **Broadcast versus submission:** the broadcast date is used, which can only be later than the company's
    submission, never earlier. It matches the submission date for the median filing in every quarter except
    Sep 2021, whose XBRL files NSE broadcast about 84 days late (median). Those filings therefore count from
    January 2022.
- **The measure is "pledged or otherwise encumbered" % of promoter holding.** Until mid-2025 the filings report
  pledges and non-disposal undertakings together, so the measure is an **upper bound on pledges**. For example,
  Jaiprakash Power is 94.63% encumbered in Sep 2022 against 72.99% pledged in 2025, and TCS is 0.48% encumbered
  with no pledges. The rules below use the pledge thresholds on this measure, because it is the only one filed.
- **Stock-dates:** the wider test's rows (`data/cache/universe_results.parquet`): every NSE company in the
  bhavcopies on each month-end, with the same filters and the same outcome (`event_observed`: the lowest close in
  the next 252 trading days is ≥ 50% below; secondary outcome `event_upper`).
- **Joining filings to stocks:** by symbol, followed through NSE's symbol-change file to the panel's later symbol.
  Where that fails, by ISIN. ISIN alone is not reliable: NSE's listing gives Zee a partly-paid ISIN.

## Windows

- **Primary:** month-ends **Oct 2022 – Dec 2024** (27 dates). Oct 2022 is the first month-end at which a
  4-quarter change can be computed from Sep 2021 data.
- **Secondary:** month-ends **Oct 2021 – Dec 2024** (39 dates), for E1 and E3, which need no change.

## Rules

On each stock-date, the latest filing broadcast on or before the date gives E%, the encumbered % of promoter
holding. The change is E% minus the E% of the latest quarter ending ≥ 360 days before that filing's quarter, as
`events.pledge_signal` computes it.

- **E1 (High pledge rule):** E% ≥ 50.
- **E2 (rising pledges):** the change ≥ 10 percentage points.
- **E3 (event tier):** `events.classify` gives Elevated or High from the signals that have point-in-time history
  for every company:
  - the pledge signal, using E% and the change;
  - the circuit signal: lower-circuit days in the 500-row window, the tool's Elevated rule of 3 or more, as in
    the app.

  Surveillance, F&O ban, rating and auditor signals have no history for 2021–2024 (NSE's rating feed returns
  nothing for those years, and ASM/GSM lists are current only), so they are not part of the tier. They are
  stated as unavailable.
- **E3p (secondary):** the same tier from the pledge signal alone.

E1, E2 and E3p count as **not flagged** where a company has no filing yet. Each rule's availability is reported.

## Comparisons

All are on the same stock-dates:
- baseline (a): down ≥ 30% in 6 months;
- baseline (b): volatility in its own top decile;
- baseline (c): below its 200-day average;
- v1 any price flag;
- R2 from Phase F (peer-relative ES), exploratory.

## Metrics

- **For every rule, on all stocks and on the liquid subset:** precision, recall, lift, flag rate, availability,
  mean lead time to the trough on correct warnings, and lift by year.
- **Incremental:** the same measures among stock-dates *not* flagged by (a).
- **Uncertainty:** a paired circular block bootstrap over runs of **12 consecutive month-ends**, 2,000 resamples,
  seed 11, with 90% percentile intervals. Intervals are given for each lift, for lift − lift(a), and for the
  incremental lift. With 27 month-ends there are only a few independent blocks, so the intervals will be wide;
  that is the honest consequence of NSE's data starting in 2021.

## Reading the results (fixed now)

- **"Warns":** a rule's lift interval lies above 1.
- **"Beats momentum":** lift > lift(a) and the 90% interval of lift − lift(a) lies above zero.
- **"Adds information beyond momentum":** the 90% interval of the incremental lift lies above 1.
- No rule replaces anything in the app because of this test. The README and the case studies report the
  outcome either way.

## Jump overlay (methodology §12.4)

- **Groups,** over all month-ends in the secondary window:
  - **High:** E1;
  - **Elevated:** E3 is Elevated or High, but not E1.
- **For each group:** the forward daily rate of stock-specific one-day falls (≥ 20% for High, ≥ 10% for
  Elevated, on days the Nifty fell less than 5%) over the next 63 trading days, minus the stock's own trailing
  rate. The 90% range comes from a cluster bootstrap over stocks, as `universe.jump_base_rates` computes it.
- **Default p:** the excess, if its 5th percentile is above 0. Otherwise it stays **0**. J is the mean fall in
  that group.
- If a default changes, `events.DEFAULT_JUMPS` changes with the interval cited. If not, it stays 0, and the docs
  say so.

## What this cannot test

- **Pre-2021 collapses** (Zee, Jet Airways, Future Retail, DHFL, Yes Bank): NSE serves no shareholding XBRL for
  them by script, BSE refuses scripts, and the user chose not to collect the pages by hand.
- **Pledges as distinct from other encumbrances,** before mid-2025.
- **The disclosure signals other than pledges** (see Rules).
