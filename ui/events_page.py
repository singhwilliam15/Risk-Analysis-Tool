"""
Promoter Pledge & Governance Risk page (Pillar 5; FINAL_PLAN_V6 Phase 3).

Order: the question → coverage line → the pledge core (level, 4-quarter change, margin-call trigger, forced selling)
with its tested evidence → other red flags with evidence badges → tiers → analyst details (the jump overlay, off by
default) → what this misses. The calculations are unchanged (ui/events_layer.py, events.py).
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import events as E
import evidence as V
from disclosures import as_of_stamp
from ui.coverage import coverage_line

METHODOLOGY = "docs/methodology.md, section 12"
TIER_ICONS = {E.LOW: "🟢 Low", E.ELEVATED: "🟠 Elevated", E.HIGH: "🔴 High"}
SIGNAL_LABELS = {"pledge": "Promoter pledge", "surveillance": "ASM / GSM", "fo_ban": "F&O ban", "rating": "Rating actions",
                 "auditor": "Auditor events", "merton": "Credit (Merton DD trend; RBI PCA for banks)", "circuit": "Circuit history", "group": "Group tag"}
RED_FLAGS = {  # signal: (plain words with the technical term, evidence id)
    "surveillance": ("On NSE's watch-list (ASM / GSM surveillance)", "surveillance"),
    "rating": ("Credit rating cut or on negative watch (rating actions)", "rating"),
    "auditor": ("Auditor resigned or qualified the accounts (auditor events)", "auditor"),
    "fo_ban": ("In the F&O ban period (market-wide position limit)", "fo_ban"),
    "group": ("Several holdings from one business group (group links)", "group"),
    "circuit": ("Repeated lower circuits (lower-circuit days)", "liquidity"),
    "merton": ("Close to default on market values (Merton DD; RBI PCA for banks)", "merton"),
}
EXPECTED = ("pledges", "surveillance", "fo_ban", "ratings")  # files the repository normally loads
BY_DESIGN = {"auditor": "no permitted source, see docs/data_sources.md", "group": "no group tags entered",
             "merton": "no statements, or not modelled"}


def _signal_text(name, s):
    if s is None:
        return "not available"
    if name == "pledge":
        change = f", {s['change_4q_pp']:+.1f} pp in 4 quarters" if np.isfinite(s["change_4q_pp"]) else ""
        return f"{s['pledged_pct_of_promoter']:.1f}% of promoter holding ({s['quarter_end']:%b %Y}){change}"
    if name == "surveillance":
        return f"{s['measure']} {s['stage_text']} since {s['since']:%d %b %Y}" if s["measure"] else "not under surveillance"
    if name == "fo_ban":
        return f"banned on {s['last_ban']:%d %b %Y}" if s["last_ban"] is not None else "no ban in window"
    if name == "rating":
        parts = [f"{s['downgrades']} downgrade(s) in 12 months"] + (["negative watch"] if s["negative_watch"] else [])
        return f"{s['latest'] or 'no rating on file'}; " + ", ".join(parts)
    if name == "auditor":
        return ", ".join(s["events"]) if s["events"] else "no events in 24 months"
    if name == "merton" and "pca_band" in s:
        return f"RBI PCA band {s['pca_band']}" + (f" ({s['pca_detail']})" if s["pca_detail"] else "") + (
            f"; {len(s['warnings'])} early warning(s)" if s["warnings"] else "")
    if name == "merton":
        trend = f" (6 months ago {s['dd_6m_ago']:.2f})" if np.isfinite(s["dd_6m_ago"]) else ""
        return f"DD {s['dd']:.2f}{trend}"
    if name == "circuit":
        return f"{s['lower_circuit_days']} lower-circuit days, longest run {s['longest_run']}"
    if name == "group":
        return f"{s['group']} ({s['same_group_holdings']} holding(s))"
    return str(s)


def coverage(ctx) -> tuple:
    """(checked items, {not checked: reason}, fixable dataset titles) over every holding."""
    data = ctx.disclosures["data"]
    checked, not_checked = [], {}
    for name in E.SIGNALS:
        values = [s.get(name) for s in ctx.event_signals.values()]
        if values and all(v is not None for v in values):
            checked.append(SIGNAL_LABELS[name])
        else:
            not_checked[SIGNAL_LABELS[name]] = BY_DESIGN.get(name, "no data for some holdings" if any(
                v is not None for v in values) else "file not loaded or not applicable")
    from disclosures import DATASETS
    fixable = [DATASETS[d].title for d in EXPECTED if data[d].empty]
    return checked, not_checked, fixable


def render(ctx):
    curr = ctx.curr_sym

    def money(v):
        return f"{curr}{v:,.0f}" if v is not None and np.isfinite(v) else "not available"

    st.subheader(f"Promoter Pledge & Governance Risk: {ctx.company_name}")
    st.caption("The question: could the owners' borrowing against their shares (promoter pledges), or a governance red "
               "flag, set off a sudden fall? Official NSE files, point in time; see Overview → Disclosure data.")
    checked, not_checked, fixable = coverage(ctx)
    coverage_line(checked, not_checked, as_of_stamp(ctx.disclosures["files"]).replace("Data as of: ", ""), fixable)

    jump_on = any(p > 0 for p, _ in ctx.event_jumps.values())
    if jump_on:
        _cards(ctx, money)
    _pledge_core(ctx, money)
    _red_flags(ctx)
    _tiers(ctx)
    with st.expander("Analyst details: jump overlay (off by default, 0; see methodology §12.4)", expanded=False):
        if not jump_on:
            st.caption("The overlay adds no risk while every jump probability is 0, the calibrated default, so its "
                       "cards sit here rather than at the top.")
            _cards(ctx, money)
        _overlay(ctx, money)

    st.markdown("### What this page misses")
    st.markdown("""
- **Fraud or misstatement not yet in any disclosure.** The signals only see what has been filed or rated.
- **Regulatory action without warning** (SEBI orders, sector bans, tax demands) and litigation.
- **Promoter debt outside pledges**: non-disposal undertakings and loans at holding companies are only partly in the pledge data.
- **Jump probabilities and sizes are assumptions** (off by default after the 2016–24 and 2021–24 tests, methodology §12.4).
- **Rules are coarse.** A tier is a flag for attention, not a probability; two holdings in the same tier can differ a lot.
""")
    st.caption(f"Methodology: {METHODOLOGY}.")


def _cards(ctx, money):
    m = ctx.event_metrics
    cols = st.columns(4)
    cards = [(m["event_es"], money), (m["gap"], money), (m["flagged"], lambda v: f"{v:.0%}"), (m["high"], lambda v: f"{v:.0f}")]
    for col, (metric, fmt) in zip(cols, cards):
        col.metric(metric.name, fmt(metric.value))
        col.caption(f"{metric.range_text(fmt)} · grade **{metric.grade}**")
        col.caption("; ".join(metric.reasons) or "no deductions")


def _pledge_core(ctx, money):
    st.markdown("### Owners' shares pledged for loans (promoter pledge / encumbrance)")
    rows = []
    for t, signals in ctx.event_signals.items():
        p, mc = signals.get("pledge"), ctx.event_margin.get(t, {})
        row = {"Holding": t,
               "Pledged (% of promoter holding)": f"{p['pledged_pct_of_promoter']:.1f}%" if p else "not available",
               "Change over 4 quarters": f"{p['change_4q_pp']:+.1f} pp" if p and np.isfinite(p["change_4q_pp"]) else "—",
               "Quarter": f"{p['quarter_end']:%b %Y}" if p else "—"}
        if mc:
            row.update({"Margin-call trigger price": f"{ctx.curr_sym}{mc['trigger_price']:,.2f}",
                        "Fall to trigger (distance)": f"{mc['trigger_fall']:.0%}",
                        "Forced selling (all pledged)": f"{mc['days_all']:,.1f} days of volume" if np.isfinite(mc["days_all"]) else "—",
                        "Selling to restore cover": f"{mc['days_restore']:,.1f} days of volume" if np.isfinite(mc["days_restore"]) else "—"})
        rows.append(row)
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    st.caption(f"Margin call (assumption): the loan was sized at today's price at {ctx.initial_cover:g}× cover, and lenders "
               f"can sell when cover falls to {ctx.trigger_cover:g}×, i.e. after a {1 - ctx.trigger_cover / ctx.initial_cover:.0%} "
               "fall. Forced selling is in days of 60-day average volume.")
    st.markdown(f"- **E1, half or more pledged:** {V.chip('e1')}\n- **E2, pledging up 10 points in a year:** {V.chip('e2')}")
    st.caption("Tested on shares 'pledged or otherwise encumbered' (the only measure filed before mid-2025); the current "
               "file reports pledges only. Lift = how many times more often a flagged stock fell 50% or more within 12 months.")


def _red_flags(ctx):
    st.markdown("### Other red flags")
    rows = []
    for name, (label, sid) in RED_FLAGS.items():
        row = {"Red flag": label}
        for t, signals in ctx.event_signals.items():
            row[t] = _signal_text(name, signals.get(name))
        row["Evidence"] = V.record(sid)["badge"]
        rows.append(row)
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    st.caption("Evidence badges come from the tests in docs/case_studies.md; 'Not back-tested' means no history exists to "
               "test the signal (docs/data_sources.md). Rules and thresholds: config/event_rules.json (assumptions).")


def _tiers(ctx):
    st.markdown("### Warning tier per holding (event tier, all loaded signals)")
    rows = [{"Holding": t, "Tier": TIER_ICONS[tier["tier"]], "Based on": tier["basis"],
             "What fired": "; ".join(f"{level}: {text}" for level, text in tier["fired"]) or "nothing"}
            for t, tier in ctx.event_tiers.items()]
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    st.caption(f"As of {ctx.prices_as_of:%d %b %Y}: only disclosures public by then are used. The tested version of this "
               f"tier (pledges and circuits only) is E3: {V.chip('e3')}.")


def _overlay(ctx, money):
    st.markdown("#### Jump overlay on Expected Shortfall")
    o, inv = ctx.event_overlay, ctx.investment_amount
    fig = go.Figure(go.Bar(x=["Standard ES", "Event-adjusted ES"], y=[o["es"] * inv, o["event_es"] * inv],
                           marker_color=["#63B3ED", "#FC8181"], text=[money(o["es"] * inv), money(o["event_es"] * inv)],
                           textposition="outside"))
    fig.update_layout(template="plotly_dark", height=300, margin=dict(t=30), yaxis_title=f"1-day ES ({ctx.curr_sym})")
    st.plotly_chart(fig, width="stretch")
    rows = [{"Ticker": t, "Tier": ctx.event_tiers[t]["tier"], "Jump probability (a day)": f"{p:.2%}",
             "Chance of a jump in a year": f"{E.annual_probability(p):.0%}", "Jump size": f"{j:.0%}",
             "Share of the ES gap": money(o["by_holding"].get(t, 0.0) * inv)} for t, (p, j) in ctx.event_jumps.items()]
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    st.caption(f"Base: the {ctx.event_base['model']} one-day distribution of the {'portfolio' if ctx.is_portfolio else 'stock'} "
               "return. Each holding can jump by its tier's J with its tier's probability; every combination of jumps is "
               "included exactly (closed-form Student-t tail, no simulation). 1-day figures at the selected confidence level.")
    _sensitivity(ctx, money)


def _sensitivity(ctx, money):
    sens = ctx.event_sensitivity
    table = sens["table"]
    shown = pd.DataFrame({f"J = {j:.0%}": [money(v) for v in table[j]] for j in table.columns})
    shown.insert(0, "p a day (a year)", [f"{p:.2%} ({E.annual_probability(p):.0%})" for p in table.index])
    who = ", ".join(sens["targets"])
    st.markdown("**How much the jump assumptions matter**: event-adjusted ES if "
                + (f"{who} (no holding is Elevated or High, so this is hypothetical: the largest holding)" if sens["hypothetical"]
                   else f"the Elevated/High holding(s) {who}") + " had jump probability p and size J")
    st.dataframe(shown, hide_index=True, width="stretch")
    st.caption("Every other holding has no jump. A daily p compounds: 0.5% a day is a 72% chance of at least one jump "
               "in a year. The defaults and how they were calibrated: docs/methodology.md §12.4.")
