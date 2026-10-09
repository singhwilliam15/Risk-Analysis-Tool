"""
Early-warning box on the Market page (NEXT_STEPS_V5 Phase F): the rule in use for a 12-month crash warning, its
out-of-sample record on every NSE stock (2020-2024), and whether it fires for each holding today.

The decision between v1 and the v2 challenger was fixed in advance (docs/preregistration_warnings_v2.md) and is
read from case_studies/results/warnings_v2_decision.json; nothing here chooses a rule.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

import warnings_v2 as W
from case_studies import engine as K
from events import load_rules
from stress import price_series
from ui.cache import cached_fetch

RESULTS = Path(__file__).resolve().parent.parent / "case_studies" / "results"


@st.cache_data(show_spinner=False)
def load_record() -> dict:
    """The frozen model, the decision, the test-period lifts with their 90% intervals, and the NSE cross-section."""
    try:
        model = json.loads((RESULTS / "warnings_v2_model.json").read_text())
        decision = json.loads((RESULTS / "warnings_v2_decision.json").read_text())
        reference = json.loads((RESULTS / "warnings_v2_reference.json").read_text())
        test = pd.read_csv(RESULTS / "warnings_v2_test.csv")
        boot = pd.read_csv(RESULTS / "warnings_v2_bootstrap.csv")
    except FileNotFoundError:
        return {}
    test = test[(test["Universe"] == "all") & (test["Outcome"] == "observed path")].set_index("Rule")
    boot = boot[boot["Universe"] == "all"].set_index("Rule")
    record = {r: {"lift": test.loc[r, "Lift"], "low": boot.loc[r, "Lift 5%"], "high": boot.loc[r, "Lift 95%"],
                  "flag_rate": test.loc[r, "Flag rate"], "recall": test.loc[r, "Recall"], "label": W.LABELS[r]}
              for r in test.index if r in boot.index}
    return {"model": model, "decision": decision, "reference": reference, "record": record,
            "base_rate": float(test["Base rate"].iloc[0])}


@st.cache_data(show_spinner=False)
def assess_holding(frame: pd.DataFrame, market: pd.Series, model: dict, reference: dict) -> dict:
    return W.assess(frame, market, model, reference, K.load_cases()["flag_rules"], load_rules())


def _frame(res: dict) -> pd.DataFrame:
    """A Yahoo download → the columns the wider test uses; traded value = close × volume (₹)."""
    df = res["df"].copy()
    df["Date"] = pd.to_datetime(df["Date"]).dt.tz_localize(None).dt.normalize()
    df["value"] = df["Close"] * df["Volume"]
    df["series"] = "EQ"
    return df[["Date", "Open", "High", "Low", "Close", "Volume", "Returns", "value", "series"]]


def _lift_text(rec: dict) -> str:
    return f"lift {rec['lift']:.2f} (90% range {rec['low']:.2f}–{rec['high']:.2f}), flags {rec['flag_rate']:.0%} of stock-dates"


def render(ctx) -> None:
    data = load_record()
    if not data:
        return
    tickers = list(ctx.price_frames)
    indian = [t for t in tickers if t.upper().endswith((".NS", ".BO"))]
    rec, decision = data["record"], data["decision"]
    challenger = decision["challenger"]
    in_use = challenger if decision["wins"] else "market"
    st.markdown("#### 🚦 Early warning: a fall of 50% or more within 12 months")
    verdict = (f"**In use: {rec[in_use]['label']}**, {_lift_text(rec[in_use])}. "
               if decision["wins"] else
               f"**In use: the v1 market flag** ({_lift_text(rec['market'])}). The pre-registered challenger, "
               f"**{rec[challenger]['label']}**, scored higher ({_lift_text(rec[challenger])}) but did not beat "
               f"the naive momentum rule *{rec['drawdown_30']['label']}* ({_lift_text(rec['drawdown_30'])}) by a "
               "margin the test could confirm, so it is shown alongside, not used. ")
    st.caption(verdict + f"Tested out of sample on every NSE stock, month-ends 2020–2024 (base rate "
               f"{data['base_rate']:.1%}); lift = how many times more often a flagged stock crashed than the average "
               "stock. Pre-registration: docs/preregistration_warnings_v2.md.")
    if not indian:
        st.info("These rules were tested on NSE stocks only, so they are not shown for this ticker.")
        return
    market_res = cached_fetch(ctx.benchmark_symbol, period="max")
    if not market_res["success"]:
        return
    market = price_series(market_res["df"]).pct_change().dropna()
    market.index = pd.to_datetime(market.index).tz_localize(None).normalize()
    rows = []
    for t in indian:
        res = cached_fetch(t, period="max")
        if not res["success"]:
            continue
        a = assess_holding(_frame(res), market, data["model"], data["reference"])
        if not a.get("available"):
            rows.append({"Holding": t, "v1 market flag": a.get("note", "not available")})
            continue
        score = a.get("r4_score", np.nan)
        rows.append({"Holding": t, "As of": f"{a['as_of']:%d %b %Y}",
                     "v1 market flag": "⚠ fires" if a["flag_market"] else "–",
                     f"{challenger.upper()} (challenger)": ("⚠ fires" if a[f"flag_{challenger}"] == 1 else "–")
                     if np.isfinite(a.get(f"flag_{challenger}", np.nan)) else "needs ~3 years of prices",
                     "R4 score": f"{score:.0%}" if np.isfinite(score) else "–",
                     "(a) down ≥ 30% in 6 months": "⚠ fires" if a["flag_drawdown_30"] else "–"})
    if rows:
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        st.caption(f"Peer comparison (R2, and R4's peer feature) uses the NSE cross-section of "
                   f"{pd.Timestamp(data['reference']['as_of']):%d %b %Y} ({data['reference']['stocks']:,} stocks), the "
                   "latest in the bhavcopy panel. Traded value here is close × Yahoo volume, which can include BSE volume. "
                   "A flag is a statistical warning, not a forecast: even the best rule's flagged stocks mostly did not crash.")
