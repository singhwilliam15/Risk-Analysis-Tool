"""
Margin-trigger distance (FINAL_PLAN_V6 Phase 2, as pre-registered in docs/preregistration_margin_trigger.md).

For a stock whose promoters have encumbered shares, the tool's margin-call model sizes the loan at the price on the
filing's broadcast date P0 with collateral cover `initial` (2×); lenders can sell once cover falls to `trigger` (1.5×),
i.e. once the price falls to P0 × trigger / initial. At a later date with price Pt the distance to the trigger is

    d = 1 − (trigger / initial) × P0 / Pt

the further fall needed before lenders could sell (d ≤ 0: at or past the trigger). Pure: no Streamlit, no I/O.
"""

import numpy as np
import pandas as pd

INITIAL, TRIGGER = 2.0, 1.5                  # primary cover assumptions (the app's defaults)
SENSITIVITY = (1.75, 1.25)                  # pre-registered sensitivity
MIN_ENC = 20.0                              # sample: encumbered ≥ 20% of promoter holding
CLOSE = 0.10                                # "close to the trigger": d < 10%
BINS = (-np.inf, 0.10, 0.25, np.inf)        # d < 10%, 10–25%, > 25%
BIN_LABELS = ("< 10% (incl. past the trigger)", "10–25%", "> 25%")


def distance(p0, pt, initial: float = INITIAL, trigger: float = TRIGGER):
    """Further fall needed before lenders could sell; NaN where a price is missing or not positive."""
    p0, pt = np.asarray(p0, dtype=float), np.asarray(pt, dtype=float)
    ok = (p0 > 0) & (pt > 0)
    return np.where(ok, 1.0 - (trigger / initial) * np.divide(p0, pt, out=np.ones_like(p0), where=ok), np.nan)


def price_index(panel: pd.DataFrame) -> pd.DataFrame:
    """
    Per symbol, a cumulative adjusted-return index by date (from the panel's adjusted daily return `ret`), so price
    ratios across bonuses and splits are right. Columns: symbol, date, level.
    """
    p = panel[["symbol", "date", "ret"]].dropna(subset=["date"]).sort_values(["symbol", "date"]).copy()
    p["level"] = np.exp(np.log1p(p["ret"].fillna(0.0).clip(lower=-0.99)).groupby(p["symbol"]).cumsum())
    return p[["symbol", "date", "level"]]


def level_on_or_before(index: pd.DataFrame, symbols, dates) -> np.ndarray:
    """The index level on the last trading day on or before each (symbol, date); NaN if none."""
    left = pd.DataFrame({"symbol": list(symbols), "date": pd.to_datetime(list(dates)).astype("datetime64[ns]"),
                         "_row": np.arange(len(symbols))})
    right = index.assign(date=pd.to_datetime(index["date"]).astype("datetime64[ns]")).sort_values("date")
    out = pd.merge_asof(left.dropna(subset=["date"]).sort_values("date"), right, on="date", by="symbol",
                        direction="backward")
    levels = np.full(len(symbols), np.nan)
    levels[out["_row"].to_numpy()] = out["level"].to_numpy()
    return levels


def add_distance(rows: pd.DataFrame, index: pd.DataFrame, initial: float = INITIAL, trigger: float = TRIGGER,
                 suffix: str = "") -> pd.DataFrame:
    """
    rows: stock-dates with symbol, as_of, enc_pct and enc_disclosed (the point-in-time filing's broadcast date).
    Adds trigger_dist{suffix}, flag_m1{suffix} (encumbered ≥ 20% and d < 10%; NaN without a filing) and the bin.
    """
    df = rows.copy()
    p0 = level_on_or_before(index, df["symbol"], df["enc_disclosed"])
    pt = level_on_or_before(index, df["symbol"], df["as_of"])
    d = distance(p0, pt, initial, trigger)
    df[f"trigger_dist{suffix}"] = d
    has = df["enc_pct"].notna() & np.isfinite(d)
    df[f"flag_m1{suffix}"] = np.where(has, ((df["enc_pct"] >= MIN_ENC) & (d < CLOSE)).astype(float), np.nan)
    df[f"trigger_bin{suffix}"] = pd.cut(pd.Series(d, index=df.index), BINS, labels=BIN_LABELS, right=False)
    return df


def rate_ratio_bootstrap(df: pd.DataFrame, flag: str, outcome: str = "event_observed", block: int = 12,
                         n_boot: int = 2000, seed: int = 11) -> dict:
    """
    Within df (the pre-registered sample), the crash rate of flag == 1 over flag == 0, with a 90% interval from a
    circular block bootstrap of whole as-of dates (blocks of `block` consecutive month-ends), as in warnings_v2.
    """
    data = df.dropna(subset=[flag, outcome]).sort_values("as_of")
    y, f = data[outcome].astype(bool), data[flag].astype(bool)
    g = data.groupby("as_of")
    n1, e1 = f.groupby(data["as_of"]).sum().to_numpy(float), (f & y).groupby(data["as_of"]).sum().to_numpy(float)
    n0, e0 = (~f).groupby(data["as_of"]).sum().to_numpy(float), (~f & y).groupby(data["as_of"]).sum().to_numpy(float)

    def ratio(i):
        a, b = n1[i].sum(), n0[i].sum()
        return (e1[i].sum() / a) / (e0[i].sum() / b) if a and b and e0[i].sum() else np.nan

    T = len(g.size())
    point = ratio(np.arange(T))
    rng = np.random.default_rng(seed)
    draws = np.empty(n_boot)
    for k in range(n_boot):
        starts = rng.integers(0, T, int(np.ceil(T / block)))
        draws[k] = ratio((starts[:, None] + np.arange(block)[None, :]).ravel()[:T] % T)
    return {"ratio": float(point), "low": float(np.nanpercentile(draws, 5)), "high": float(np.nanpercentile(draws, 95)),
            "n_close": int(n1.sum()), "events_close": int(e1.sum()), "n_far": int(n0.sum()), "events_far": int(e0.sum()),
            "dates": int(T)}


def bin_table(df: pd.DataFrame, bin_col: str = "trigger_bin", outcome: str = "event_observed") -> pd.DataFrame:
    """Stock-dates, crashes and crash rate per distance bin (within the sample)."""
    data = df.dropna(subset=[outcome])
    t = data.groupby(bin_col, observed=False)[outcome].agg(["size", "sum"]).rename(columns={"size": "Stock-dates", "sum": "Crashes"})
    t["Crash rate"] = t["Crashes"] / t["Stock-dates"].replace(0, np.nan)
    return t.reset_index().rename(columns={bin_col: "Fall to trigger"})
