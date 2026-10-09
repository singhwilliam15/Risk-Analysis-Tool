# Pre-registration: early-warning rules v2 (out-of-sample test)

Written and committed on 10 Oct 2026, **before** any result was computed on the design or the test period
(NEXT_STEPS_V5.md, Phase F). The code that implements it (`warnings_v2.py`, `universe.py`,
`scripts/run_universe.py`) and its tests (`test_warnings_v2.py`) are in the same commit. Nothing below will change
after test results are seen. If a bug is found later, it will be fixed in a separate commit and the report will
show the results before and after the fix.

## Why

In the wider test (every NSE stock, month-ends 2016–2024), the tool's v1 market flag fires on 72.7% of
stock-dates, with a lift of 1.14. The momentum baseline "down ≥ 30% in 6 months" has a lift of 2.25. Both
figures are in `case_studies/results/universe_metrics.csv` as of commit b90a3a7. The question tested here is
whether a better-calibrated rule beats momentum on data it was not designed on.

## Data and universe

- **Prices:** NSE daily bhavcopies, series EQ, BE and BZ, company ISINs only, including stocks that were later
  delisted. They are back-adjusted for bonuses and splits, and renamed symbols are chained (`universe.py`).
- **Panel extension:** the panel is extended to **1 Jan 2011 – 31 Jan 2026**, from 2014–2025 before. Amendment 1
  moves the start to 22 Jun 2011.
  - The earlier start gives R1 three years of daily ES history in the design period.
  - The later end completes the 12-month outcome window of the last test dates.
  - v1 and the baselines are re-run on the same extended panel.
- **Stock-dates:** the last market trading day of each month. A stock is included on a date if it has at least
  250 rows to that date, traded in the last 5 market days, and its outcome window is complete. These are
  unchanged from the wider test.
- **Market calendar:** Nifty 50 trading days from Yahoo Finance.

## Periods

| Period | As-of month-ends | Use |
| --- | --- | --- |
| Design | Jan 2016 – Dec 2018 | Fit R4, set its threshold, choose the challenger |
| Embargo | Jan 2019 – Dec 2019 | Not used: their 12-month outcomes overlap the test period |
| Test | Jan 2020 – Dec 2024 | Evaluated once, with everything frozen |

## Outcome

- **Primary outcome:** the lowest close in the next 252 market trading days is ≥ 50% below the as-of close
  (`event_observed`). Stock-dates without future prices are dropped.
- **Secondary outcome:** a stock that stops trading inside the window also counts as an event
  (`event_upper`).

## Rules

ES95 is the tool's historical Expected Shortfall at 95%: the mean daily return at or below the empirical 5%
quantile (linear interpolation), as a positive loss. It is computed on the returns of the last 500 rows up to the
date (at least 250 rows), exactly as the v1 flag computes it.

**Candidate rules:**
- **R1. Own-history ES.** ES95 on the date ≥ the 90th percentile of the stock's own daily ES95 values over the
  previous 756 trading rows. At least 500 such values are needed.
- **R2. Peer-relative ES.** ES95 ≥ the 90th percentile of ES95 within the stock's liquidity bucket on that date.
  The buckets are terciles of log median 60-day traded value, across all stocks with a value on that date.
- **R3. Volatility shock with trend.** EWMA volatility (λ = 0.94) ≥ 1.5 × one-year volatility (252 days), and the
  close below its 200-day average.
- **R4. Combined score.**
  - The model is a logistic regression of the primary outcome on 7 features:
    - R1's percentile rank of today's ES within the previous 756 values;
    - R2's percentile rank within the bucket;
    - the 126-day return;
    - the distance from the 200-day average (close / average − 1);
    - lower-circuit days in the last 60 rows (band inferred from the 500-row window, as in the liquidity pillar;
      0 when no band is found);
    - the integrated-stress loss from a −20% market move (the v1 stress flag's figure);
    - the log median 60-day traded value.
  - Features are standardised with design-period means and standard deviations.
  - It is fitted by Newton–Raphson with a 10⁻⁶ ridge, on design-period rows that have every feature and an
    observed outcome. The code refuses any row dated outside 2016–2018.
  - It flags when the score is ≥ the 90th percentile of design-period scores.

**Comparisons**, all unchanged:
- **v1 any price flag (`tool`):** market, liquidity or stress.
- **v1 market flag:** EWMA / 1-year volatility ≥ 1.5, or ES95 ≥ 5%.
- **Baseline (a):** down ≥ 30% over 126 days.
- **Baseline (b):** 60-day volatility in its own 5-year top decile.
- **Baseline (c):** below the 200-day average.

**Missing values:** a rule that cannot be computed on a stock-date, for lack of history or a missing feature,
counts as **not flagged**, as in the published wider test. The share of stock-dates where each rule is available
is reported.

## Choosing the one rule that is tested

- The **challenger** is the R1–R4 rule with the highest **design-period** lift among the rules whose design flag
  rate is between 5% and 25%.
- Only the challenger is subject to the decision rule.
- All four rules are reported on the test period as descriptive results. This avoids picking a winner after
  seeing four test results, and stops a rule that flags very few stock-dates from winning on lift alone.

## Metrics

Metrics are computed on the test period, for all stocks and for the liquid subset (median 60-day traded value
≥ ₹1 crore):
- precision, recall, lift (precision / base rate) and the share of stock-dates flagged;
- availability;
- mean lead time on true positives (trading days from the as-of date to the lowest close in the window);
- lift year by year;
- **incremental value over momentum:** the same metrics among stock-dates *not* flagged by baseline (a).

## Uncertainty

- **Method:** a circular moving-block bootstrap of **12 consecutive month-ends** over the 60 test dates,
  2,000 resamples, seed 11.
  - Stock-dates on one date are correlated, and neighbouring month-ends share 11 of their 12 outcome months.
  - Each resample sums the per-date counts.
- **Pairing:** every rule's lift, and lift − lift(a), are computed on the same resamples.
- **Intervals:** 90% intervals (5th and 95th percentiles), for all stocks and for the liquid subset.

## Decision rule

The decision is made on all stocks, primary outcome, test period. The challenger **replaces the v1 market flag**
only if all of these hold:
- its lift is above v1's any-price-flag lift;
- its lift is above v1's market-flag lift;
- its lift is above baseline (a)'s lift;
- the lower end (5th percentile) of its lift − lift(a) interval is above zero.

**If it wins:**
- `case_studies/engine.price_flags` uses it as the market flag, with v1 kept and shown as "previous rule";
- the 220 case-study dates are re-run.

**If it does not win:**
- the app keeps v1;
- the Market page shows v1 and the challenger side by side, with their tested lifts;
- the README says the new rules did not beat momentum.

Either way, the app's Market page states which rule is in use and its tested lift with the 90% interval.

R2 and R4 need every NSE stock on the same date. If one of them is used in the app, it applies the
cross-sectional thresholds of the latest month-end in the panel, labelled with that date.

## Process

1. This document, the code and the tests are committed together.
2. `python scripts/run_universe.py --stage design` evaluates every month-end once.
   - It writes only design-period results: `warnings_v2_design.csv`, and `warnings_v2_model.json` with the
     coefficients, threshold and challenger.
   - These are committed. No test-period metric is computed before that commit.
3. `python scripts/run_universe.py --stage test --reuse` checks that the frozen model is committed (it refuses
   otherwise), then computes the test results and the decision. After that, the published full-period tables are
   rebuilt.

## Deviations from NEXT_STEPS_V5.md (agreed before the run)

- **Panel extended back to 2011.** With prices from 2014, R1 had no three-year history in the design period.
- **One challenger chosen on the design period**, instead of applying the decision rule to four rules on the test
  period.
- **Blocks of 12 consecutive month-ends** in the bootstrap, instead of single dates, because neighbouring dates'
  outcome windows overlap.
- **v1 compared on both its any-price-flag and its market-flag forms.**

## Amendment 1 (10 Oct 2026, before any result was computed)

The panel starts on **22 Jun 2011**, not 1 Jan 2011.
- **Cause:** NSE's 117 bhavcopies from 3 Jan to 21 Jun 2011 have no ISIN column. The ISIN is how the panel
  keeps out ETFs and fund units, which also trade in series EQ.
- **Handling:** those days are left out rather than guessed (`universe.normalise_bhavcopy`).
- **Effect on R1:** none. R1 needs about three years of rows before a date (250 rows for the first ES value,
  then 500 ES values), so its first design date, Jan 2016, needs prices from about Jan 2013.
- **Other rules:** unaffected.
