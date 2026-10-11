# Pre-registration: margin-trigger distance, every NSE stock, Oct 2022 – Dec 2024

Written and committed on 12 Oct 2026, **before** any result of this test was computed. This is FINAL_PLAN_V6 Phase 2,
item 2, as adjusted for working without new NSE data ([v6 adjustments](plans/v6_adjustments.md)). The code
(`margin_trigger.py`, `scripts/run_margin_test.py`) and its tests are in the same commit. No outcome of this test
has been looked at. Nothing below changes after results are seen. Any bug fix goes in a separate commit, with the
results shown before and after.

## Question

Among stocks whose promoters have encumbered their shares, does being **close to the pledge margin-call trigger**
warn of a ≥ 50% fall within 12 months **better than the encumbrance level alone**?

## Data (already held locally; nothing new is downloaded)

- **Stock-dates and outcome:** the wider test's rows (`data/cache/universe_results.parquet`), as in the event test
  ([pre-registration](preregistration_events.md)). The outcome is `event_observed`: the lowest close in the next
  252 trading days is ≥ 50% below. Rows whose 12 months are not observed are dropped.
- **Encumbrance, point in time:** exactly as in the event test (`event_universe.point_in_time`): the latest original
  filing broadcast on or before the as-of date, measured as "pledged or otherwise encumbered" % of promoter holding.
- **Prices:** the bhavcopy panel's adjusted daily returns (bonuses and splits), compounded per stock.
- **Window:** month-ends **Oct 2022 – Dec 2024** (27 dates), the event test's primary window.
- Only summary statistics are committed (`case_studies/results/margin_trigger_*`); the inputs stay git-ignored
  ([data sources](data_sources.md)).

## Definition

The tool's margin-call model (methodology §12.3), with the loan sized at the price on the filing's **broadcast date**
P0 (the first date the market could know the filing):
- initial cover 2×, lenders can sell at 1.5×, so the trigger price is 0.75 × P0;
- distance to the trigger at the as-of date: **d = 1 − 0.75 × P0 / Pt**, the further fall needed (d ≤ 0: at or past
  the trigger);
- **sensitivity:** 1.75× initial and 1.25× trigger.

## Rules and samples

- **M1:** encumbered ≥ 20% of promoter holding **and** d < 10% (including at or past the trigger).
- **Bins:** d < 10% (including past), 10–25%, > 25%.
- **Sample for the main question:** stock-dates with encumbrance ≥ 20% and a computable d.

## Tests

1. **Main (conditional):** within the sample, the crash rate of M1 stock-dates divided by the crash rate of the other
   sample stock-dates (**rate ratio**). The 90% interval comes from a circular block bootstrap of whole month-ends in
   blocks of 12, with 2,000 resamples and seed 11.
   - **Supported** ("being close adds to the encumbrance level") if the interval's lower end is **above 1**.
   - Also reported, without a decision: the same ratio within encumbrance ≥ 50%, in the liquid subset, and under
     the 1.75×/1.25× covers; and the crash rate per bin.
2. **Registry reading (as every signal, methodology §15.5):** M1's lift over all stock-dates. It is reported with
   its 90% interval and the interval of lift − lift(momentum, down ≥ 30% in 6 months) on the same resamples. It is
   also reported among stocks not already down 30%, with E1 alongside. The evidence badge follows §15.5 unchanged.

## Limits stated in advance

- **Overlap with momentum.** M1 needs a price fall since the filing (Pt below 0.83 × P0 at 2× / 1.5×), so it
  overlaps the momentum rule. The incremental reading is the guard against that overlap.
- **Assumed loan size.** The real loan size and cover are not disclosed; d is a model quantity.
- **Upper bound on pledges.** Before mid-2025 the encumbrance measure includes non-disposal undertakings, so it is an
  upper bound on pledges.
- **Limited power.** There are 27 month-ends from one market regime, overlapping 12-month outcomes, and few
  encumbered stocks.
