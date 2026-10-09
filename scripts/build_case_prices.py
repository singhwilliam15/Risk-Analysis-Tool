"""
Price files for case studies that Yahoo no longer serves (delisted stocks), from the NSE bhavcopy panel.

    python scripts/build_case_prices.py DHFL      # writes case_studies/data/prices/DHFL.csv

The panel (data/cache/panel.parquet, scripts/fetch_bhavcopy.py) is NSE's own daily file, back-adjusted for bonuses
and splits exactly as in the wider test (universe.adjust); series EQ, BE and BZ, as the stock traded.
"""

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import universe as U  # noqa: E402

OUT = ROOT / "case_studies" / "data" / "prices"


def case_prices(panel: pd.DataFrame, symbol: str) -> pd.DataFrame:
    rows = panel[panel["symbol"] == symbol].sort_values("date")
    if rows.empty:
        raise ValueError(f"{symbol} is not in the bhavcopy panel")
    out = rows.rename(columns={"date": "Date", "open": "Open", "high": "High", "low": "Low", "close": "Close",
                               "volume": "Volume"})[["Date", "Open", "High", "Low", "Close", "Volume"]]
    return out.reset_index(drop=True)


def main(symbols) -> int:
    panel = pd.read_parquet(U.PANEL_PATH, columns=["date", "symbol", "open", "high", "low", "close", "volume"])
    OUT.mkdir(parents=True, exist_ok=True)
    for symbol in symbols:
        prices = case_prices(panel, symbol)
        prices.to_csv(OUT / f"{symbol}.csv", index=False, date_format="%Y-%m-%d")
        print(f"{symbol}: {len(prices)} days, {prices['Date'].min():%d %b %Y} to {prices['Date'].max():%d %b %Y}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or ["DHFL"]))
