"""
The NSE cross-section the app needs for R2 and R4 (docs/preregistration_warnings_v2.md): on the panel's latest
month-end, every stock's ES95 and log median 60-day traded value, summarised as liquidity-tercile edges and ES
percentiles per tercile. Written to case_studies/results/warnings_v2_reference.json (small; committed).

    python scripts/build_warning_reference.py      # needs data/cache/panel.parquet (scripts/fetch_bhavcopy.py)
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import universe as U  # noqa: E402
import warnings_v2 as W  # noqa: E402

OUT = ROOT / "case_studies" / "results" / "warnings_v2_reference.json"


def main() -> int:
    panel = pd.read_parquet(U.PANEL_PATH, columns=["date", "symbol", "close", "value"])
    days = pd.Series(sorted(panel["date"].unique()))
    as_of = days.groupby(days.dt.to_period("M")).max().iloc[-1]
    recent = set(days[days <= as_of].tail(U.ACTIVE_WITHIN_DAYS))
    rows = []
    for symbol, g in panel[panel["date"] <= as_of].groupby("symbol", sort=False):
        g = g.sort_values("date")
        if len(g) < W.ES_MIN_ROWS or g["date"].iloc[-1] not in recent:
            continue
        returns = g["close"].pct_change().to_numpy()
        es = W.daily_es_series(returns)[-1]
        value = g["value"].tail(60).median()
        rows.append({"symbol": symbol, "es_today": es, "log_value60": np.log(value) if value > 0 else np.nan})
    reference = W.reference_from(pd.DataFrame(rows), as_of)
    OUT.write_text(json.dumps(reference, indent=1))
    print(f"{reference['stocks']} stocks on {reference['as_of']}; tercile edges (₹, median 60-day value): "
          + ", ".join(f"{np.exp(e):,.0f}" for e in reference["edges"])
          + "; ES95 90th percentile by tercile: " + ", ".join(f"{t['es_p90']:.2%}" for t in reference["tiers"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
