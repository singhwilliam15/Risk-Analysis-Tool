"""
Margin-trigger distance on every NSE stock, Oct 2022 - Dec 2024, as pre-registered in
docs/preregistration_margin_trigger.md. Reads only data already held locally (the wider test's stock-dates, the
bhavcopy panel and the 2021-2024 shareholding history, all git-ignored); writes summary statistics only.

    python scripts/run_margin_test.py   # writes case_studies/results/margin_trigger_*.csv and margin_trigger_decision.json
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
import event_universe as EU  # noqa: E402
import margin_trigger as M  # noqa: E402
import universe as U  # noqa: E402
import warnings_v2 as W  # noqa: E402
from run_event_test import joined  # noqa: E402

RESULTS = ROOT / "case_studies" / "results"
W.LABELS["m1"] = "M1 encumbered ≥ 20% and within 10% of the margin-call trigger"
W.LABELS["m1_s"] = "M1 with 1.75×/1.25× cover"


def registry_readings(df: pd.DataFrame, rules) -> tuple:
    """Lift with 90% ranges (vs momentum on the same resamples), and among stocks not already down 30%."""
    _, n, ev, counts = W.per_date_counts(df, rules)
    boot = W.block_bootstrap(n, ev, counts)
    rest = df[~df["flag_drawdown_30"].fillna(False).astype(bool)]
    _, n2, ev2, counts2 = W.per_date_counts(rest, [r for r in rules if r != "drawdown_30"] + ["tool"])
    inc = W.block_bootstrap(n2, ev2, counts2, reference="tool")
    return W.table(df, rules), boot, inc[inc["Rule"] != "tool"]


def main() -> int:
    df, _ = joined()
    df = df[W.in_period(df["as_of"], EU.PRIMARY)].copy()
    panel = pd.read_parquet(U.PANEL_PATH, columns=["symbol", "date", "ret"])
    index = M.price_index(panel)
    df = M.add_distance(df, index)
    df = M.add_distance(df, index, *M.SENSITIVITY, suffix="_s")
    observed = df.dropna(subset=["worst_12m"])

    tables = {}
    for subset, part in (("all", observed), ("liquid", observed[observed["liquid"]])):
        t, b, inc = registry_readings(part, ["m1", "m1_s", "e1", "drawdown_30"])
        for name, frame in (("test", t), ("bootstrap", b), ("incremental_bootstrap", inc)):
            tables.setdefault(name, []).append(frame.assign(Universe=subset))
    for name, frames in tables.items():
        pd.concat(frames, ignore_index=True).to_csv(RESULTS / f"margin_trigger_{name}.csv", index=False)

    # Conditional question: within encumbered stocks, does being close to the trigger add to the encumbrance level?
    sample = observed[(observed["enc_pct"] >= M.MIN_ENC) & observed["trigger_dist"].notna()]
    ratios, bins = [], []
    for label, part, flag, bin_col in (
            ("primary: encumbered ≥ 20%", sample, "flag_m1", "trigger_bin"),
            ("encumbered ≥ 50%", sample[sample["enc_pct"] >= 50], "flag_m1", "trigger_bin"),
            ("liquid, encumbered ≥ 20%", sample[sample["liquid"]], "flag_m1", "trigger_bin"),
            ("sensitivity 1.75×/1.25×", observed[(observed["enc_pct"] >= M.MIN_ENC) & observed["trigger_dist_s"].notna()],
             "flag_m1_s", "trigger_bin_s")):
        ratios.append({"Sample": label, **M.rate_ratio_bootstrap(part, flag)})
        bins.append(M.bin_table(part, bin_col).assign(Sample=label))
    ratios = pd.DataFrame(ratios)
    ratios.to_csv(RESULTS / "margin_trigger_rate_ratio.csv", index=False)
    pd.concat(bins, ignore_index=True).to_csv(RESULTS / "margin_trigger_bins.csv", index=False)

    b = tables["bootstrap"][0].set_index("Rule")
    inc = tables["incremental_bootstrap"][0].set_index("Rule")
    primary = ratios.iloc[0]
    decision = {
        "close_adds_beyond_encumbrance": bool(primary["low"] > 1),
        "m1": {"warns": bool(b.loc["m1", "Lift 5%"] > 1),
               "beats momentum": bool(b.loc["m1", "Difference 5%"] > 0),
               "adds information beyond momentum": bool(inc.loc["m1", "Lift 5%"] > 1)},
        "coverage": {"stock_dates": int(len(observed)), "dates": int(observed["as_of"].nunique()),
                     "encumbered_20_with_distance": int(len(sample)),
                     "close_to_trigger": int(sample["flag_m1"].sum())},
    }
    (RESULTS / "margin_trigger_decision.json").write_text(json.dumps(decision, indent=2))
    pd.set_option("display.width", 220)
    for name, frames in tables.items():
        print(pd.concat(frames).to_string(index=False, float_format=lambda v: f"{v:.3f}"))
    print(ratios.to_string(index=False, float_format=lambda v: f"{v:.3f}"))
    print(pd.concat(bins).to_string(index=False, float_format=lambda v: f"{v:.4f}"))
    print(json.dumps(decision, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
