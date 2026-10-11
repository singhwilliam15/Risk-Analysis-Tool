"""
The event pillar on every NSE stock, 2021-2024 (NEXT_STEPS_V5 Phase G; docs/preregistration_events.md). Pure
functions: scripts/run_event_test.py supplies the wider test's stock-dates and the shareholding history.

- Filings are matched to the panel's symbols (renames followed; ISIN as a fallback), then joined point in time:
  the latest filing broadcast on or before each date, and the quarter at least 360 days before it.
- E1 = encumbered % of promoter holding ≥ 50; E2 = up ≥ 10 pp in four quarters; E3 = events.classify tier
  Elevated or High from the pledge and circuit signals (the signals with history for every company); E3p = the
  pledge signal alone.
"""

import numpy as np
import pandas as pd

import events as E

PRIMARY = ("2022-10-01", "2024-12-31")
SECONDARY = ("2021-10-01", "2024-12-31")
CHANGE_DAYS = 360
LABELS = {"e1": "E1 encumbered ≥ 50% of promoter holding", "e2": "E2 encumbrance up ≥ 10 pp in 4 quarters",
          "e3": "E3 event tier Elevated/High (pledge + circuits)", "e3p": "E3p event tier from pledges alone"}


def chain(symbol: str, changes: list, after) -> str:
    """The symbol a listing used on `after`, followed through every later rename (changes in date order)."""
    for old, new, when in changes:
        if symbol == old and pd.Timestamp(when) > pd.Timestamp(after):
            symbol = new
    return symbol


def map_symbols(filings: pd.DataFrame, universe_symbols: set, isin_to_symbol: dict, changes: list) -> pd.Series:
    """
    The panel symbol of each filing: its own symbol carried through later renames if the panel knows it, otherwise
    the panel symbol of its ISIN, otherwise NaN (reported as unmatched).
    """
    out = []
    for sym, isin, filed in filings[["symbol", "isin", "disclosure_date"]].itertuples(index=False):
        chained = chain(sym, changes, filed)
        if chained in universe_symbols:
            out.append(chained)
        elif sym in universe_symbols:
            out.append(sym)
        else:
            out.append(isin_to_symbol.get(isin, np.nan))
    return pd.Series(out, index=filings.index)


def point_in_time(rows: pd.DataFrame, filings: pd.DataFrame) -> pd.DataFrame:
    """
    For each stock-date (symbol, as_of): the latest filing broadcast on or before as_of (its quarter, E% and
    disclosure date), and the change from the latest quarter ending ≥ 360 days before that quarter, among filings
    also public by as_of.
    """
    f = filings.dropna(subset=["panel_symbol"]).copy()
    f["disclosure_date"] = pd.to_datetime(f["disclosure_date"]).astype("datetime64[ns]")  # one resolution on both sides
    f["quarter_end"] = pd.to_datetime(f["quarter_end"]).astype("datetime64[ns]")
    f = f.sort_values("disclosure_date")
    left = rows[["symbol", "as_of"]].copy()
    left["as_of"] = pd.to_datetime(left["as_of"]).astype("datetime64[ns]")
    left["_row"] = np.arange(len(left))
    latest = pd.merge_asof(left.sort_values("as_of"), f.rename(columns={"panel_symbol": "symbol_f"})
                           [["symbol_f", "disclosure_date", "quarter_end", "encumbered_pct_of_promoter", "measure"]],
                           left_on="as_of", right_on="disclosure_date", left_by="symbol", right_by="symbol_f",
                           direction="backward")
    latest = latest.sort_values("_row").reset_index(drop=True)
    change = np.full(len(latest), np.nan)
    by_symbol = {s: g for s, g in f.groupby("panel_symbol")}
    for i, r in enumerate(latest.itertuples(index=False)):
        if pd.isna(r.quarter_end):
            continue
        g = by_symbol[r.symbol]
        earlier = g[(g["quarter_end"] <= r.quarter_end - pd.Timedelta(days=CHANGE_DAYS)) & (g["disclosure_date"] <= r.as_of)]
        if len(earlier):
            back = earlier.sort_values("quarter_end").iloc[-1]
            change[i] = r.encumbered_pct_of_promoter - back["encumbered_pct_of_promoter"]
    return pd.DataFrame({"enc_pct": latest["encumbered_pct_of_promoter"].to_numpy(), "enc_change_4q": change,
                         "enc_quarter": latest["quarter_end"].to_numpy(), "enc_disclosed": latest["disclosure_date"].to_numpy(),
                         "enc_measure": latest["measure"].to_numpy()}, index=rows.index)


def add_rules(df: pd.DataFrame, rules: dict) -> pd.DataFrame:
    """E1, E2, E3, E3p (1/0, NaN where the rule cannot be computed) and the tier, from the joined columns."""
    df = df.copy()
    has = df["enc_pct"].notna()
    df["flag_e1"] = np.where(has, (df["enc_pct"] >= rules["high"]["pledged_pct_of_promoter_min"]).astype(float), np.nan)
    ok2 = df["enc_change_4q"].notna()
    df["flag_e2"] = np.where(ok2, (df["enc_change_4q"] >= rules["elevated"]["pledge_increase_4q_pp_min"]).astype(float), np.nan)
    tiers, tiers_p = [], []
    for r in df[["enc_pct", "enc_change_4q", "lower_circuit_days"]].itertuples(index=False):
        pledge = None if pd.isna(r.enc_pct) else {"pledged_pct_of_promoter": float(r.enc_pct), "change_4q_pp": float(r.enc_change_4q)
                                                   if pd.notna(r.enc_change_4q) else np.nan}
        circuit = {"lower_circuit_days": int(r.lower_circuit_days), "longest_run": 0}
        tiers.append(E.classify({"pledge": pledge, "circuit": circuit}, rules)["tier"])
        tiers_p.append(E.classify({"pledge": pledge}, rules)["tier"] if pledge is not None else None)
    df["tier"], df["tier_pledge"] = tiers, tiers_p
    df["flag_e3"] = (df["tier"] != E.LOW).astype(float)
    df["flag_e3p"] = np.where(has, (pd.Series(tiers_p, index=df.index) != E.LOW).astype(float), np.nan)
    return df


def jump_default(row: pd.Series) -> float:
    """The pre-registered default: the excess daily jump rate if its 5th percentile is above zero, else 0."""
    return float(row["Excess p a day"]) if row["p low (5%)"] > 0 else 0.0
