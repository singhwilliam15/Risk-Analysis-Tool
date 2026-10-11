"""
"Signals with a tested record" (FINAL_PLAN_V6 Phase 3), on the Market page: every warning signal the tool shows, whether
it fires now for each NSE holding, its tested record and an evidence badge (evidence.py).

The official market flag was fixed by the pre-registered test (docs/preregistration_warnings_v2.md): v1 stays in use
because the challenger did not beat momentum. Nothing here chooses or re-tunes a rule.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

import events as E
import evidence as V
import warnings_v2 as W
from case_studies import engine as K
from events import load_rules
from stress import price_series
from ui.cache import cached_fetch

RESULTS = Path(__file__).resolve().parent.parent / "case_studies" / "results"
PRICE_RULES = ("drawdown_30", "r4", "r2", "market", "tool", "below_200dma", "liquidity", "stress", "r1", "r3",
               "vol_top_decile")


@st.cache_data(show_spinner=False)
def load_record() -> dict:
    """The frozen R4 model, the pre-registered decision and the NSE cross-section R2/R4 compare against."""
    try:
        return {"model": json.loads((RESULTS / "warnings_v2_model.json").read_text()),
                "decision": json.loads((RESULTS / "warnings_v2_decision.json").read_text()),
                "reference": json.loads((RESULTS / "warnings_v2_reference.json").read_text())}
    except FileNotFoundError:
        return {}


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


def _mark(value) -> str:
    if value is None or (isinstance(value, float) and not np.isfinite(value)):
        return "n.a."
    return "✓ fires" if bool(value) else "–"


def event_flags(signals: dict, rules: dict) -> dict:
    """The pledge rules as tested (E1, E2, E3 on pledges and circuits, E3p on pledges) and each untested red flag."""
    pledge = signals.get("pledge")
    out = {"e1": None if pledge is None else pledge["pledged_pct_of_promoter"] >= rules["high"]["pledged_pct_of_promoter_min"],
           "e2": None if pledge is None or not np.isfinite(pledge["change_4q_pp"])
           else pledge["change_4q_pp"] >= rules["elevated"]["pledge_increase_4q_pp_min"],
           "e3": E.classify({"pledge": pledge, "circuit": signals.get("circuit")}, rules)["tier"] != E.LOW
           if pledge is not None or signals.get("circuit") is not None else None,
           "e3p": None if pledge is None else E.classify({"pledge": pledge}, rules)["tier"] != E.LOW}
    for sid in V.UNTESTED_IDS:
        s = signals.get(sid)
        out[sid] = None if s is None else E.classify({sid: s}, rules)["tier"] != E.LOW
    return out


def holding_flags(ctx, ticker: str, data: dict, market) -> dict:
    flags = {}
    res = cached_fetch(ticker, period="max")
    if res["success"] and market is not None:
        a = assess_holding(_frame(res), market, data["model"], data["reference"])
        if a.get("available"):
            flags.update({sid: a.get(f"flag_{sid}") for sid in PRICE_RULES})
    flags.update(event_flags(ctx.event_signals.get(ticker, {}), load_rules()))
    return flags


def panel_table(registry: pd.DataFrame, flags_by_holding: dict) -> pd.DataFrame:
    """One row per signal in evidence order: fires now per holding, tested lift, window, beyond momentum, badge."""
    rows = []
    for r in registry.to_dict("records"):
        row = {"Signal": r["label"]}
        for t, flags in flags_by_holding.items():
            row[t.replace(".NS", "").replace(".BO", "") if len(flags_by_holding) > 1 else "Fires now"] = _mark(flags.get(r["id"]))
        row.update({"Evidence": r["badge"], "Tested lift (90% range)": V.lift_text(r),
                    "Among stocks not down 30%": V.incremental_text(r), "Test window (NSE month-ends)": V.SHORT.get(r["test"], "—")})
        rows.append(row)
    return pd.DataFrame(rows)


def render(ctx) -> None:
    data = load_record()
    registry = V.registry()
    if not data or registry.empty:
        return
    st.markdown("#### Signals with a tested record (a fall of 50% or more within 12 months)")
    decision = data["decision"]
    st.caption("**Official market flag: v1 (legacy rule).** The pre-registered challenger, R4, scored higher but did "
               "not beat the momentum rule by a margin the test could confirm, so v1 stays "
               "(docs/preregistration_warnings_v2.md)." if not decision.get("wins") else
               f"**Official market flag: {decision['challenger'].upper()}** (won the pre-registered test); v1 is the legacy rule.")
    indian = [t for t in ctx.price_frames if t.upper().endswith((".NS", ".BO"))]
    if not indian:
        st.info("These signals were tested on NSE stocks only, so they are not shown for this ticker.")
        return
    market_res = cached_fetch(ctx.benchmark_symbol, period="max")
    market = None
    if market_res["success"]:
        market = price_series(market_res["df"]).pct_change().dropna()
        market.index = pd.to_datetime(market.index).tz_localize(None).normalize()
    flags = {t: holding_flags(ctx, t, data, market) for t in indian}
    st.dataframe(panel_table(registry, flags), hide_index=True, width="stretch")
    st.caption("**Lift** = how many times more often a flagged stock fell 50% or more within 12 months than the average "
               "NSE stock in the test. Evidence badges: *works* = beats the momentum rule; *weaker than momentum* = warns "
               "(range above 1) but does not beat it; *no effect* = range includes 1; *not back-tested* = no history to "
               "test. Price rules were tested on month-ends 2020–24, pledge rules on Oct 2022 – Dec 2024, so compare "
               "lifts within a window. Pledge rules were tested on shares 'pledged or otherwise encumbered' (filings to "
               "mid-2025); the app's current file reports pledges only. Peer comparison uses the NSE cross-section of "
               f"{pd.Timestamp(data['reference']['as_of']):%d %b %Y}. A flag is a statistical warning, not a forecast.")
