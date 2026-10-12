"""
Evidence registry (FINAL_PLAN_V6 Phase 3): every warning signal the tool shows, with its tested record read from the
committed results files, and an evidence badge from rules fixed in advance (docs/methodology.md §15.5):

- "Tested · works": the 90% interval of lift − lift(momentum) lies above 0, or the signal is the momentum benchmark
  itself and its lift interval lies above 1;
- "Tested · weaker than momentum": the lift interval lies above 1 but the signal does not beat momentum;
- "Tested · no effect": the lift interval includes 1 (or, without an interval, the lift is at most 1);
- "Not back-tested": no historical test exists.

Lift = how many times more often a flagged stock fell 50% or more within 12 months than the average stock.
Pure: no Streamlit; the results files are read once.
"""

from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

RESULTS = Path(__file__).resolve().parent / "case_studies" / "results"
WORKS, WEAKER, NO_EFFECT, UNTESTED = ("Tested · works", "Tested · weaker than momentum", "Tested · no effect",
                                      "Not back-tested")
BADGE_ORDER = {WORKS: 0, WEAKER: 1, NO_EFFECT: 2, UNTESTED: 3}
BENCHMARK = "drawdown_30"

# id: (plain words with the technical term, source, legacy?)
SIGNALS = {
    "drawdown_30": "Already down 30% in 6 months (momentum baseline)",
    "r4": "Combined crash score (R4, logistic model on price features)",
    "r2": "Large tail losses for its liquidity group (R2, peer-relative Expected Shortfall)",
    "e1": "Owners pledged half or more of their shares (E1, promoter encumbrance ≥ 50%)",
    "e2": "Owners' pledging jumped (E2, encumbrance up ≥ 10 pp in 4 quarters)",
    "e3": "Pledge or circuit warning (E3, event tier Elevated/High)",
    "e3p": "Pledge warning (E3p, event tier from pledges alone)",
    "market": "Tail-risk or volatility alarm (v1 market flag: ES95 ≥ 5% or EWMA ≥ 1.5× one-year volatility)",
    "tool": "Any v1 price flag (market, circuit or stress)",
    "below_200dma": "Below its 200-day average (baseline c)",
    "liquidity": "Repeated lower circuits (v1 liquidity flag, ≥ 3 lower-circuit days)",
    "stress": "Large loss in a −20% market move (v1 integrated-stress flag)",
    "r1": "Tail losses high versus its own past (R1, own-history Expected Shortfall)",
    "r3": "Volatility shock in a downtrend (R3, EWMA ≥ 1.5× one-year volatility and below the 200-day average)",
    "vol_top_decile": "Volatility in its own top 10% (baseline b)",
    "surveillance": "On NSE's watch-list (ASM / GSM surveillance)",
    "fo_ban": "In the F&O ban period (market-wide position limit)",
    "rating": "Credit rating cut or on negative watch (rating actions)",
    "auditor": "Auditor resigned or qualified the accounts (auditor events)",
    "group": "Several holdings from one business group (group links)",
    "merton": "Close to default on market values (Merton distance to default; RBI PCA for banks)",
    "m1": "Close to the lenders' selling price (M1, encumbered ≥ 20% and within 10% of the pledge margin-call trigger)",
}
UNTESTED_IDS = ("surveillance", "fo_ban", "rating", "auditor", "group", "merton")
PHASE_F = "NSE, month-ends 2020–24, out of sample (pre-registered)"
PHASE_G = "NSE, month-ends Oct 2022 – Dec 2024 (pre-registered)"
WIDER = "NSE, month-ends 2016–24"
SHORT = {PHASE_F: "2020–24", PHASE_G: "Oct 2022 – Dec 2024", WIDER: "2016–24"}  # window labels for tables


def badge(lift, low=None, diff_low=None, benchmark=False) -> str:
    """The evidence badge from a lift, its 90% interval's lower end and the lower end of lift − lift(momentum)."""
    if lift is None or not np.isfinite(lift):
        return UNTESTED
    if benchmark:
        return WORKS if (low if low is not None else lift) > 1 else NO_EFFECT
    if diff_low is not None and np.isfinite(diff_low) and diff_low > 0:
        return WORKS
    bound = low if low is not None and np.isfinite(low) else lift
    return WEAKER if bound > 1 else NO_EFFECT


def _row(sid, test, lift, low, high, diff_low, inc=None, inc_low=None, inc_high=None, source="", note=""):
    return {"id": sid, "label": SIGNALS[sid], "test": test, "lift": lift, "low": low, "high": high,
            "diff_low": diff_low, "incremental": inc, "inc_low": inc_low, "inc_high": inc_high,
            "badge": badge(lift, low, diff_low, sid == BENCHMARK), "source": source, "note": note}


@lru_cache(maxsize=1)
def registry() -> pd.DataFrame:
    """Every signal with its tested record and badge, ordered by evidence strength (badge, then lift)."""
    rows = []
    try:
        t = pd.read_csv(RESULTS / "warnings_v2_test.csv")
        t = t[(t["Universe"] == "all") & (t["Outcome"] == "observed path")].set_index("Rule")
        b = pd.read_csv(RESULTS / "warnings_v2_bootstrap.csv")
        b = b[b["Universe"] == "all"].set_index("Rule")
        inc = pd.read_csv(RESULTS / "warnings_v2_incremental.csv")
        inc = inc[inc["Universe"] == "all"].set_index("Rule")
        for sid in ("drawdown_30", "r4", "r2", "market", "tool", "below_200dma", "r1", "r3", "vol_top_decile"):
            rows.append(_row(sid, PHASE_F, t.loc[sid, "Lift"], b.loc[sid, "Lift 5%"], b.loc[sid, "Lift 95%"],
                             None if sid == BENCHMARK else b.loc[sid, "Difference 5%"],
                             None if sid == BENCHMARK else inc.loc[sid, "Lift"],
                             source="case_studies/results/warnings_v2_*.csv",
                             note="" if sid == BENCHMARK else "incremental lift without a range (Phase F)"))
    except (FileNotFoundError, KeyError):
        pass
    try:
        e = pd.read_csv(RESULTS / "events_bootstrap.csv")
        e = e[e["Window"].str.startswith("primary") & (e["Universe"] == "all")].set_index("Rule")
        ib = pd.read_csv(RESULTS / "events_incremental_bootstrap.csv")
        ib = ib[ib["Window"].str.startswith("primary") & (ib["Universe"] == "all")].set_index("Rule")
        for sid in ("e1", "e2", "e3", "e3p"):
            rows.append(_row(sid, PHASE_G, e.loc[sid, "Lift"], e.loc[sid, "Lift 5%"], e.loc[sid, "Lift 95%"],
                             e.loc[sid, "Difference 5%"], ib.loc[sid, "Lift"], ib.loc[sid, "Lift 5%"],
                             ib.loc[sid, "Lift 95%"], "case_studies/results/events_*.csv",
                             "tested on 'pledged or otherwise encumbered' (filings to mid-2025)"))
    except (FileNotFoundError, KeyError):
        pass
    try:
        mb = pd.read_csv(RESULTS / "margin_trigger_bootstrap.csv")
        mb = mb[mb["Universe"] == "all"].set_index("Rule")
        mi = pd.read_csv(RESULTS / "margin_trigger_incremental_bootstrap.csv")
        mi = mi[mi["Universe"] == "all"].set_index("Rule")
        rows.append(_row("m1", PHASE_G, mb.loc["m1", "Lift"], mb.loc["m1", "Lift 5%"], mb.loc["m1", "Lift 95%"],
                         mb.loc["m1", "Difference 5%"], mi.loc["m1", "Lift"], mi.loc["m1", "Lift 5%"],
                         mi.loc["m1", "Lift 95%"], "case_studies/results/margin_trigger_*.csv",
                         "pre-registered Oct 2026 (docs/preregistration_margin_trigger.md); loan sized at the filing date"))
    except (FileNotFoundError, KeyError):
        pass
    try:
        m = pd.read_csv(RESULTS / "universe_metrics.csv")
        m = m[(m["Universe"] == "all") & (m["Outcome"] == "observed path")].set_index("Rule")
        for sid in ("liquidity", "stress"):
            rows.append(_row(sid, WIDER, m.loc[sid, "Lift"], None, None, None,
                             source="case_studies/results/universe_metrics.csv", note="no range computed"))
    except (FileNotFoundError, KeyError):
        pass
    for sid in UNTESTED_IDS:
        rows.append(_row(sid, "", np.nan, None, None, None, note="no historical data to test it"))
    out = pd.DataFrame(rows)
    out["order"] = out["badge"].map(BADGE_ORDER)
    out = out.sort_values(["order", "lift"], ascending=[True, False], na_position="last").drop(columns="order")
    return out.reset_index(drop=True)


def record(sid: str) -> dict:
    """One signal's row, or an untested placeholder."""
    reg = registry()
    hit = reg[reg["id"] == sid]
    return hit.iloc[0].to_dict() if len(hit) else _row(sid, "", np.nan, None, None, None)


def lift_text(r: dict) -> str:
    if r["lift"] is None or not np.isfinite(r["lift"]):
        return "—"
    rng = f" ({r['low']:.2f}–{r['high']:.2f})" if r["low"] is not None and np.isfinite(r["low"]) else " (no range)"
    return f"{r['lift']:.2f}×{rng}"


def incremental_text(r: dict) -> str:
    v = r.get("incremental")
    if v is None or not np.isfinite(v):
        return "—"
    lo = r.get("inc_low")
    return f"{v:.2f}×" + (f" ({lo:.2f}–{r['inc_high']:.2f})" if lo is not None and np.isfinite(lo) else "")


def chip(sid: str) -> str:
    """One-line evidence chip, e.g. 'Tested on NSE, … : 1.89× crash rate (1.60–2.24) · beyond momentum 1.86× · Tested · weaker than momentum'."""
    r = record(sid)
    if r["badge"] == UNTESTED:
        return f"{UNTESTED}: {r['note']}"
    beyond = f" · among stocks not already down 30%: {incremental_text(r)}" if incremental_text(r) != "—" else ""
    return f"{r['badge']} · {r['test']}: {lift_text(r)} the average crash rate{beyond}"
