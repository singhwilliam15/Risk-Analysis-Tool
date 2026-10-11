"""
The event pillar on every NSE stock, 2021-2024, as pre-registered in docs/preregistration_events.md.

    python scripts/fetch_shareholding_history.py   # the quarterly shareholding history (hours; once)
    python scripts/run_universe.py --stage ...      # the wider test's stock-dates (data/cache/universe_results.parquet)
    python scripts/run_event_test.py                # writes case_studies/results/events_*.csv and events_decision.json
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import event_universe as EU  # noqa: E402
import universe as U  # noqa: E402
import warnings_v2 as W  # noqa: E402
from events import load_rules  # noqa: E402

RESULTS = ROOT / "case_studies" / "results"
HISTORY = ROOT / "data" / "disclosures" / "history" / "shareholding_2021_2024.csv"
RULES = ("e1", "e2", "e3", "e3p", "drawdown_30", "vol_top_decile", "below_200dma", "tool", "r2")
for key, label in EU.LABELS.items():
    W.LABELS[key] = label


def joined() -> pd.DataFrame:
    results = pd.read_parquet(U.CACHE / "universe_results.parquet")
    results = results[W.in_period(results["as_of"], EU.SECONDARY)].copy()
    results = W.add_cross_sectional(results)  # R2 on the full cross-section of each date
    filings = pd.read_csv(HISTORY)
    panel = pd.read_parquet(U.PANEL_PATH, columns=["symbol", "isin"]).drop_duplicates()
    isin_to_symbol = dict(zip(panel["isin"], panel["symbol"]))
    raw = pd.read_csv(U.CACHE / "bhavcopy" / "symbolchange.csv", header=None, dtype=str, encoding="latin-1")
    filings["panel_symbol"] = EU.map_symbols(filings, set(results["symbol"]), isin_to_symbol, U.parse_symbol_changes(raw))
    unmatched = filings["panel_symbol"].isna()
    print(f"{len(filings):,} filings, {filings['isin'].nunique():,} companies; {int(unmatched.sum()):,} filings "
          f"({filings.loc[unmatched, 'isin'].nunique()} companies) match no panel stock", flush=True)
    pit = EU.point_in_time(results, filings)
    return EU.add_rules(pd.concat([results, pit], axis=1), load_rules()), filings


def summary(df: pd.DataFrame, rules) -> dict:
    out = {}
    for subset, part in (("all", df), ("liquid", df[df["liquid"]])):
        t = W.table(part, rules)
        _, n, ev, counts = W.per_date_counts(part, rules)
        b = W.block_bootstrap(n, ev, counts)
        rest = part[~part["flag_drawdown_30"].fillna(False).astype(bool)]
        inc = W.table(rest, rules)
        _, n2, ev2, counts2 = W.per_date_counts(rest, [r for r in rules if r != "drawdown_30"] + ["tool"])
        bi = W.block_bootstrap(n2, ev2, counts2, reference="tool")  # (a) flags nothing here: differences vs v1
        bi = bi.rename(columns=lambda c: c.replace("lift(tool)", "lift(v1 any price flag)"))
        out[subset] = (t, b, inc, bi[bi["Rule"] != "drawdown_30"])
    return out


def main() -> int:
    df, filings = joined()
    rules = load_rules()
    tables = {}
    for window, period, rule_set in (("primary Oct 2022 - Dec 2024", EU.PRIMARY, RULES),
                                     ("secondary Oct 2021 - Dec 2024", EU.SECONDARY, ("e1", "e3", "e3p", "drawdown_30", "tool", "r2"))):
        part = df[W.in_period(df["as_of"], period)]
        for subset, (t, b, inc, bi) in summary(part, rule_set).items():
            for name, frame in (("test", t), ("bootstrap", b), ("incremental", inc), ("incremental_bootstrap", bi)):
                frame = frame.copy()
                frame.insert(0, "Universe", subset)
                frame.insert(0, "Window", window)
                tables.setdefault(name, []).append(frame)
    for name, frames in tables.items():
        pd.concat(frames, ignore_index=True).to_csv(RESULTS / f"events_{name}.csv", index=False)
    primary = df[W.in_period(df["as_of"], EU.PRIMARY)]
    yearly = []
    for year, part in primary.groupby(primary["as_of"].dt.year):
        t = W.table(part, RULES)
        t.insert(0, "Year", year)
        yearly.append(t)
    pd.concat(yearly, ignore_index=True).to_csv(RESULTS / "events_yearly.csv", index=False)

    # Jump overlay (pre-registered groups, secondary window)
    high = df["flag_e1"].fillna(0).astype(bool)
    elevated = df["flag_e3"].fillna(0).astype(bool) & ~high
    jumps = U.jump_base_rates(df, groups={"All stocks": pd.Series(True, index=df.index), "High: E1": high,
                                          "Elevated: E3 not E1": elevated})
    jumps.to_csv(RESULTS / "events_jumps.csv", index=False)
    j = jumps.set_index(["Group", "Fall"])
    decision = {"jump_default": {
        "High": {"p": EU.jump_default(j.loc[("High: E1", "≥ 20%")]), "J": float(j.loc[("High: E1", "≥ 20%"), "Mean fall J"])},
        "Elevated": {"p": EU.jump_default(j.loc[("Elevated: E3 not E1", "≥ 10%")]),
                     "J": float(j.loc[("Elevated: E3 not E1", "≥ 10%"), "Mean fall J"])}}}
    b = pd.concat(tables["bootstrap"])
    b = b[(b["Window"].str.startswith("primary")) & (b["Universe"] == "all")].set_index("Rule")
    bi = pd.concat(tables["incremental_bootstrap"])
    bi = bi[(bi["Window"].str.startswith("primary")) & (bi["Universe"] == "all")].set_index("Rule")
    decision["readings"] = {r: {"warns": bool(b.loc[r, "Lift 5%"] > 1),
                                "beats momentum": bool(b.loc[r, "Lift − lift(drawdown_30)"] > 0 and b.loc[r, "Difference 5%"] > 0),
                                "adds information beyond momentum": bool(bi.loc[r, "Lift 5%"] > 1)}
                            for r in ("e1", "e2", "e3", "e3p")}
    decision["coverage"] = {"filings": int(len(filings)), "companies": int(filings["isin"].nunique()),
                            "unmatched_filings": int(filings["panel_symbol"].isna().sum()),
                            "stock_dates_primary": int(len(primary)),
                            "with_a_filing_primary": float(primary["enc_pct"].notna().mean())}
    (RESULTS / "events_decision.json").write_text(json.dumps(decision, indent=2))
    pd.set_option("display.width", 220)
    fmt = lambda v: f"{v:.4f}" if abs(v) < 0.01 else f"{v:.3f}"  # noqa: E731
    for name in ("test", "bootstrap", "incremental", "incremental_bootstrap"):
        t = pd.concat(tables[name])
        print(t[t["Universe"] == "all"].to_string(index=False, float_format=fmt))
    print(jumps.to_string(index=False, float_format=lambda v: f"{v:.5f}"))
    print(json.dumps(decision, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
