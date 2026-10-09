"""
The wider test (docs/case_studies.md, "Wider test"): every NSE equity in the bhavcopies on every month-end from
Jan 2016 to Dec 2024, the tool's price-based flags and the naive baselines against a ≥ 50% drawdown over the next
12 months, plus the jump base rates for the event overlay; and the out-of-sample test of the v2 warning rules.

    python scripts/fetch_bhavcopy.py                 # once: downloads and builds data/cache/panel.parquet
    python scripts/run_universe.py --stage design    # evaluates every month-end; writes the design-period results
                                                     # and the frozen warnings-v2 model only (commit them next)
    python scripts/run_universe.py --stage test      # the out-of-sample test (2020-2024), then the full-period tables

The benchmark is the Nifty 50 index from Yahoo Finance (an index has no survivorship problem). The design was fixed
before the run: thresholds, outcome, universe filters and proxy groups are in universe.py. Warnings v2 (Phase F)
follow docs/preregistration_warnings_v2.md: the design stage never computes a test-period metric, and the test stage
refuses to run until the frozen model (case_studies/results/warnings_v2_model.json) is committed.
"""

import argparse
import json
import subprocess
import sys
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import data_fetcher  # noqa: E402
import universe as U  # noqa: E402
import warnings_v2 as W  # noqa: E402
from case_studies import engine as K  # noqa: E402
from events import load_rules  # noqa: E402
from stress import price_series  # noqa: E402

RESULTS = K.ROOT / "results"
START, END = "2016-01-01", "2024-12-31"
UNEXPLAINED_MOVE = 0.40  # a day beyond ±40% that no bonus/split explains (NSE bands are at most 20%)
MODEL_PATH = RESULTS / "warnings_v2_model.json"
CACHE_PATH = U.CACHE / "universe_results.parquet"
TABLE_RULES = W.CANDIDATES + ("tool", "market", "drawdown_30", "vol_top_decile", "below_200dma")


def evaluate_all(started) -> tuple:
    """Every stock on every month-end (flags, features and outcomes), cached in data/cache/universe_results.parquet."""
    panel = pd.read_parquet(U.PANEL_PATH)
    nifty = data_fetcher.fetch_stock_data("^NSEI", "max")
    market = price_series(nifty["df"]).pct_change().dropna()
    market = market[market.index >= panel["date"].min()]
    as_of_dates = U.month_ends(market.index, START, END)
    config = K.load_cases()
    rules = load_rules()
    panel_end = panel["date"].max()

    odd = panel.loc[panel["ret"].abs() > UNEXPLAINED_MOVE, ["symbol", "date", "ret"]]
    tasks = []
    for symbol, rows in panel.groupby("symbol", sort=True):
        if len(rows) >= 250:
            tasks.append((symbol, U.stock_frame(rows), market, as_of_dates, config["flag_rules"], rules, panel_end))
    print(f"{len(tasks):,} symbols with 250+ days; {len(as_of_dates)} month-ends; "
          f"{len(odd):,} unexplained moves beyond ±40% in {odd['symbol'].nunique()} symbols", flush=True)

    rows, errors = [], []
    with Pool(7) as pool:
        for i, out in enumerate(pool.imap_unordered(U.worker, tasks, chunksize=4), 1):
            for r in out:
                (errors if "error" in r else rows).append(r)
            if i % 200 == 0:
                print(f"  {i:,}/{len(tasks):,} symbols, {len(rows):,} rows ({time.time() - started:.0f}s)", flush=True)
    results = pd.DataFrame(rows)
    results.to_parquet(CACHE_PATH, index=False)
    meta = {"as_of_start": str(as_of_dates[0].date()), "as_of_end": str(as_of_dates[-1].date()),
            "month_ends": len(as_of_dates), "symbols_evaluated": int(results["symbol"].nunique()),
            "stock_dates": len(results), "liquid_stock_dates": int(results["liquid"].sum()),
            "events_observed": int(results["event_observed"].sum()),
            "dates_without_future_prices": int(results["worst_12m"].isna().sum()),
            "disappeared_stock_dates": int(results["disappeared"].sum()),
            "symbols_that_disappeared": int(results.loc[results["disappeared"], "symbol"].nunique()),
            "unexplained_moves": len(odd), "symbols_with_unexplained_moves": int(odd["symbol"].nunique()),
            "unexplained_symbols": sorted(set(odd["symbol"])),
            "errors": len(errors), "error_examples": errors[:5], "panel_start": str(panel["date"].min().date()),
            "panel_end": str(panel_end.date()), "panel_symbols": int(panel["symbol"].nunique()),
            "runtime_s": round(time.time() - started)}
    (U.CACHE / "universe_run_meta.json").write_text(json.dumps(meta, indent=2))
    return results, meta


def design_stage(results: pd.DataFrame) -> int:
    """Fit R4 and pick the challenger from design-period rows (2016-2018) only; write the frozen model."""
    design = results[W.in_period(results["as_of"], W.DESIGN)].copy()
    design = W.add_r3(W.add_cross_sectional(design))
    model = W.fit_r4(design)
    design = W.add_r4(design, model)
    table = W.table(design, TABLE_RULES)
    table.insert(0, "Period", "design 2016-2018")
    model["challenger"] = W.choose_challenger(table)
    model["design_table"] = table.to_dict("records")
    table.to_csv(RESULTS / "warnings_v2_design.csv", index=False)
    MODEL_PATH.write_text(json.dumps(model, indent=2, default=float))
    pd.set_option("display.width", 220)
    print(table.to_string(index=False, float_format=lambda v: f"{v:.3f}"))
    print(f"challenger: {model['challenger']}; R4 fitted on {model['rows']:,} rows "
          f"({model['first_date']} to {model['last_date']}), threshold {model['threshold']:.4f}")
    print(f"Now commit {MODEL_PATH.relative_to(ROOT)} and warnings_v2_design.csv, then run --stage test --reuse.")
    return 0


def committed(path: Path) -> bool:
    """Whether `path` is tracked by git and has no uncommitted change."""
    rel = str(path.relative_to(ROOT))
    tracked = subprocess.run(["git", "ls-files", "--error-unmatch", rel], cwd=ROOT, capture_output=True).returncode == 0
    dirty = subprocess.run(["git", "status", "--porcelain", rel], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    return tracked and not dirty


def test_stage(results: pd.DataFrame) -> int:
    """The out-of-sample test on 2020-2024 with the frozen model, and the pre-registered decision."""
    if not committed(MODEL_PATH):
        print(f"Refusing to run the test: {MODEL_PATH.name} is missing or not committed.")
        return 1
    model = json.loads(MODEL_PATH.read_text())
    test = results[W.in_period(results["as_of"], W.TEST)].copy()
    test = W.add_r4(W.add_r3(W.add_cross_sectional(test)), model)
    tables, boots, incs = [], [], []
    for subset, part in (("all", test), ("liquid", test[test["liquid"]])):
        for outcome in ("event_observed", "event_upper"):
            t = W.table(part, TABLE_RULES, outcome)
            t.insert(0, "Outcome", {"event_observed": "observed path", "event_upper": "disappearance counted as event"}[outcome])
            t.insert(0, "Universe", subset)
            tables.append(t)
        _, n, ev, counts = W.per_date_counts(part, TABLE_RULES)
        b = W.block_bootstrap(n, ev, counts)
        b.insert(0, "Universe", subset)
        boots.append(b)
        inc = W.incremental(part, TABLE_RULES)
        inc.insert(0, "Universe", subset)
        incs.append(inc)
    test_table, boot = pd.concat(tables, ignore_index=True), pd.concat(boots, ignore_index=True)
    yearly = []
    for year, part in test.groupby(test["as_of"].dt.year):
        t = W.table(part, TABLE_RULES)
        t.insert(0, "Year", year)
        yearly.append(t)
    primary = test_table[(test_table["Universe"] == "all") & (test_table["Outcome"] == "observed path")]
    decision = W.decide(primary, boot[boot["Universe"] == "all"], model["challenger"])
    test_table.to_csv(RESULTS / "warnings_v2_test.csv", index=False)
    boot.to_csv(RESULTS / "warnings_v2_bootstrap.csv", index=False)
    pd.concat(incs, ignore_index=True).to_csv(RESULTS / "warnings_v2_incremental.csv", index=False)
    pd.concat(yearly, ignore_index=True).to_csv(RESULTS / "warnings_v2_yearly.csv", index=False)
    (RESULTS / "warnings_v2_decision.json").write_text(json.dumps(decision, indent=2))
    pd.set_option("display.width", 220)
    fmt = lambda v: f"{v:.3f}"  # noqa: E731
    print(test_table.to_string(index=False, float_format=fmt))
    print(boot.to_string(index=False, float_format=fmt))
    print(pd.concat(incs).to_string(index=False, float_format=fmt))
    print(json.dumps(decision, indent=2))
    return 0


def full_period_tables(results: pd.DataFrame) -> None:
    """The published wider-test tables over every month-end 2016-2024 (v1 flags and baselines), as before."""
    run_meta = json.loads((U.CACHE / "universe_run_meta.json").read_text())
    odd_symbols = set(run_meta.pop("unexplained_symbols"))
    tables = []
    clean = ~results["symbol"].isin(odd_symbols)
    for subset, mask in (("all", pd.Series(True, index=results.index)), ("liquid", results["liquid"]),
                         ("all, excluding unexplained ±40% moves", clean)):
        for outcome in ("event_observed", "event_upper"):
            m = U.rule_metrics(results[mask], outcome)
            m.insert(0, "Outcome", {"event_observed": "observed path", "event_upper": "disappearance counted as event"}[outcome])
            m.insert(0, "Universe", subset)
            tables.append(m)
    metrics = pd.concat(tables, ignore_index=True)
    metrics.to_csv(RESULTS / "universe_metrics.csv", index=False)
    U.yearly_metrics(results).to_csv(RESULTS / "universe_yearly.csv", index=False)
    jumps = U.jump_base_rates(results)
    jumps.to_csv(RESULTS / "universe_jumps.csv", index=False)
    (RESULTS / "universe_meta.json").write_text(json.dumps(run_meta, indent=2))
    pd.set_option("display.width", 200)
    print(metrics.to_string(index=False, float_format=lambda v: f"{v:.3f}"))
    print(jumps.to_string(index=False, float_format=lambda v: f"{v:.5f}"))
    print(json.dumps(run_meta, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=["design", "test"], required=True)
    parser.add_argument("--reuse", action="store_true", help="reuse data/cache/universe_results.parquet")
    args = parser.parse_args()
    started = time.time()
    results = pd.read_parquet(CACHE_PATH) if args.reuse else evaluate_all(started)[0]
    if args.stage == "design":
        return design_stage(results)
    code = test_stage(results)
    if code == 0:
        full_period_tables(results)
    return code


if __name__ == "__main__":
    sys.exit(main())
