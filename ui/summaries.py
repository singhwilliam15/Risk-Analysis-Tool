"""
Page summaries (FINAL_PLAN_V6 Phase 4): the question each page answers, a status word, a one-line verdict, three or
four facts with what they mean, what to do, and the method behind the numbers.

Presentation only. Every number is one the pages already computed (ctx); the status words come from rules that already
exist: a pillar's CRO-dashboard limit light (green → Clear, amber → Watch, red → Warning), the headline trust grade
(A/B → Clear, C → Watch, D → Warning) and the pledge tiers (Low → Clear, Elevated → Watch, High → Warning).
`build(page, ctx)` returns the parts (tested for length and wording); `render(page, ctx)` draws them.
"""

import numpy as np
import streamlit as st

from ui import pages as P
from ui import plain
from ui.plain import CLEAR, WARNING, WATCH, term

TIER_STATUS = {"Low": CLEAR, "Elevated": WATCH, "High": WARNING}
GRADE_STATUS = {"A": CLEAR, "B": CLEAR, "C": WATCH, "D": WARNING}


def _ok(v) -> bool:
    return v is not None and np.isfinite(v)


def _money(ctx, v) -> str:
    return f"{ctx.curr_sym}{v:,.0f}" if _ok(v) else "not available"


def _row(ctx, pillar) -> dict:
    return next((r for r in ctx.dashboard if r["Pillar"] == pillar), {})


def _status(ctx, pillar) -> str:
    return plain.status_from_light(_row(ctx, pillar).get("Status", "-"))


def _limits_status(ctx) -> str:
    return plain.worst(*[plain.status_from_light(s) for s in ctx.limits_table["Status"]]) if len(ctx.limits_table) else CLEAR


def _first_action(ctx, fallback) -> str:
    return ctx.top_actions[0] if ctx.top_actions else fallback


def _risk_terms(ctx):
    cl, h = ctx.confidence_level, ctx.holding_period
    return (f"{plain.VOCAB['var'][0]} ({cl:.0%} {h}-day VaR)", f"{plain.VOCAB['es'][0]} (Expected Shortfall, {cl:.0%}, {h}-day)")


def _market(ctx) -> dict:
    var, es = ctx.trusted[ctx.headline_model]["VaR"], ctx.trusted[ctx.headline_model]["ES"]
    inv, money = ctx.investment_amount, lambda v: _money(ctx, v)
    var_label, es_label = _risk_terms(ctx)
    status = _status(ctx, "Market")
    tested = {"recommended": "passed every test", "var_only": "passed the VaR tests but not the ES test",
              "none_pass": "failed at least one test (treat with caution)"}.get(ctx.recommendation["status"],
                                                                                "too few days to test")
    return {
        "question": "How much could this lose on a bad day?",
        "status": status,
        "verdict": f"on a bad day you could lose about {money(var.value)} ({var.value / inv:.1%} of {money(inv)}).",
        "facts": [(var_label, f"{money(var.value)}, {var.range_text(money)}", "exceeded on about 1 day in 20"),
                  (es_label, money(es.value), "what a bad day costs once it happens"),
                  (term("backtest"), f"{ctx.headline_model} model {tested}", "")],
        "grades": [("Bad-day loss", var), ("Worst-days loss", es)],
        "action": _first_action(ctx, "Nothing to do now") if status != CLEAR else
        "Nothing to do now: the average worst-day loss is within your limit.",
        "methods": [f"{ctx.headline_model} model, chosen out of sample by the lowest {plain.VOCAB['tick_loss'][1]} among the "
                    f"models that pass; methodology {plain.VOCAB['var'][3]}, {plain.VOCAB['backtest'][3]}."],
        "chips": [],
    }


def _liquidity(ctx) -> dict:
    lm, money = ctx.liquidity_metrics, lambda v: _money(ctx, v)
    status = _status(ctx, "Liquidity")
    days, sell5 = lm["amfi50"].value, lm["sell5"].value
    days_text = f"{days:,.2f} days" if days < 1 else f"{days:,.1f} days"
    return {
        "question": "Could you sell this quickly without moving the price?",
        "status": status,
        "verdict": (f"half of it could be sold within a day ({days_text}) without trading more than a fifth of daily "
                    "volume." if days < 1 else f"half of it would take {days_text} to sell without trading more than a "
                    "fifth of daily volume."),
        "facts": [(f"Days to sell half ({plain.VOCAB['amfi'][1]})", days_text, "the mutual-fund reporting test"),
                  ("Share sellable in 5 days", f"{sell5:.0%}" if _ok(sell5) else "not available", ""),
                  (term("lvar"), money(lm["lvar"].value), "the bad-day loss plus the cost of selling"),
                  (f"Loss if locked at the daily limit ({plain.VOCAB['circuit'][1]})", money(lm["circuit"].value),
                   "a locked stock cannot be sold")],
        "grades": [("Days to sell half", lm["amfi50"]), ("Loss incl. selling", lm["lvar"])],
        "action": _first_action(ctx, "Nothing to do now") if status != CLEAR else
        "Nothing to do now: the holdings can be sold within your limit.",
        "methods": [f"{plain.VOCAB['days_liquidate'][1]}, 3-month average volume; SEBI/AMFI pro-rata method; "
                    f"methodology {plain.VOCAB['days_liquidate'][3]}–{plain.VOCAB['circuit'][3]}."],
        "chips": [],
    }


def _credit(ctx) -> dict:
    cm = ctx.credit_metrics
    status = _status(ctx, "Credit")
    pd_text = _row(ctx, "Credit").get("Headline", "").replace("weighted PD ", "") or "not available"
    dd = cm["weakest_dd"]
    facts = [(term("pd"), pd_text + " (value-weighted)", "a model-implied probability, not a real-world default rate"),
             (f"{plain.VOCAB['dd'][0]}, weakest holding ({plain.VOCAB['dd'][1]})",
              f"{dd.value:.2f} standard deviations" if _ok(dd.value) else "not available",
              dd.name.replace("Lowest distance to default", "").strip(" ()") or "")]
    if "weakest_altman" in cm:
        facts.append((term("altman"), cm["weakest_altman"].name.replace("Lowest Altman ", ""), "lowest score held"))
    return {
        "question": "Could a company you hold fail?",
        "status": status,
        "verdict": "credit risk is within your limit." if status == CLEAR else
        "credit risk is close to or above your limit.",
        "facts": facts,
        "grades": [("Default probability", cm["weighted_pd"])],
        "action": _first_action(ctx, "Nothing to do now") if status != CLEAR else
        "Nothing to do now; watch any holding whose distance to default keeps falling.",
        "methods": [f"Merton model on market values and published debt; Altman Z from the accounts; RBI PCA levels for "
                    f"banks; methodology {plain.VOCAB['dd'][3]}–{plain.VOCAB['pca'][3]}."],
        "chips": ["merton"],
    }


def _concentration(ctx) -> dict:
    cmx = ctx.conc_metrics
    status = _status(ctx, "Concentration")
    largest = float(ctx.positions["Weight"].max())
    facts, grades = [], []
    if "enb" in cmx:
        facts.append((term("enb"), f"{cmx['enb'].value:.2f} of {len(ctx.positions)} holdings",
                      "how many separate bets the portfolio really is"))
        grades.append(("Independent bets", cmx["enb"]))
    if "factor_share" in cmx:
        facts.append((term("factor_share"), f"{cmx['factor_share'].value:.0%}", "risk that diversifying stocks will not remove"))
        grades.append(("Factor share", cmx["factor_share"]))
    if "kept" in cmx and _ok(cmx["kept"].value):
        facts.append((term("crisis_corr"), f"{cmx['kept'].value:.0%}", "how much of the diversification survived past crises"))
    facts.append(("Largest holding", f"{largest:.0%}", ""))
    verdict = (f"the portfolio behaves like {cmx['enb'].value:.1f} independent bets." if "enb" in cmx else
               f"{cmx['factor_share'].value:.0%} of this stock's risk comes from the market and style factors."
               if "factor_share" in cmx else "not enough data to measure concentration.")
    return {
        "question": "Is the risk spread out, or does it all depend on one thing?",
        "status": status, "verdict": verdict, "facts": facts[:4], "grades": grades,
        "action": _first_action(ctx, "Nothing to do now") if status != CLEAR else
        "Nothing to do now: no holding is above your limit.",
        "methods": [f"Principal components and a market, size, value and momentum factor model; methodology "
                    f"{plain.VOCAB['factor_share'][3]}–{plain.VOCAB['crisis_corr'][3]}."],
        "chips": [],
    }


def _events(ctx) -> dict:
    if ctx.disclosures["data"]["pledges"].empty:
        return {
            "question": "Could the owners' borrowing, or a governance red flag, set off a sudden fall?",
            "status": WATCH, "verdict": "not checked: no pledge files are loaded.",
            "facts": [(term("pledge"), "not loaded", "NSE's terms do not allow this project to republish them")],
            "grades": [],
            "action": "Download the shareholding pattern (or the template) and upload it on this page or on Overview.",
            "methods": [f"Official filings you load, point in time; methodology {plain.VOCAB['pledge'][3]}."],
            "chips": ["e1", "e2"],
        }
    tiers = {t: r["tier"] for t, r in ctx.event_tiers.items()}
    status = plain.worst(*[TIER_STATUS.get(v, CLEAR) for v in tiers.values()])
    flagged = [t for t, v in tiers.items() if v != "Low"]
    pledged = {t: s["pledge"]["pledged_pct_of_promoter"] for t, s in ctx.event_signals.items() if s.get("pledge")}
    tier_label = f"{plain.VOCAB['tier'][0]} ({plain.VOCAB['tier'][1]})"
    if len(tiers) == 1:
        tier_value = next(iter(tiers.values()), "not available")
    else:
        counts = {lvl: sum(v == lvl for v in tiers.values()) for lvl in ("High", "Elevated", "Low")}
        if flagged:
            tier_value = (", ".join(f"{n} {lvl}" for lvl, n in counts.items() if n)
                          + f" ({', '.join(f'{t}: {tiers[t]}' for t in flagged)})")
        else:
            tier_value = f"all {len(tiers)} Low"
    facts = [(tier_label, tier_value, "")]
    if pledged:
        top = max(pledged, key=pledged.get)
        facts.append((term("pledge"), f"{pledged[top]:.1f}% of the owners' shares" + (f" ({top})" if len(tiers) > 1 else ""),
                      "lenders can sell these shares"))
        mc = ctx.event_margin.get(top) or {}
        if mc and _ok(mc.get("trigger_price")) and pledged[top] > 0:
            days = mc.get("days_all")
            facts.append((f"{plain.VOCAB['margin_call'][0]} ({plain.VOCAB['margin_call'][1]})",
                          f"{ctx.curr_sym}{mc['trigger_price']:,.2f}, {mc['trigger_fall']:.0%} below today",
                          f"a forced sale would be {days:,.1f} days of volume" if _ok(days) else ""))
    else:
        facts.append((term("pledge"), "none reported", ""))
    if not flagged:
        verdict = "no pledge or governance warning." if len(tiers) == 1 else "no holding has a pledge or governance warning."
    elif len(tiers) == 1:
        verdict = f"this stock carries a {tiers[flagged[0]]} pledge or governance warning."
    else:
        verdict = f"{len(flagged)} of {len(tiers)} holdings carry a pledge or governance warning."
    return {
        "question": "Could the owners' borrowing, or a governance red flag, set off a sudden fall?",
        "status": status, "verdict": verdict, "facts": facts, "grades": [],
        "action": "Nothing to do now; the pledge data updates each quarter." if status == CLEAR else
        "Check the trigger price against today's price, and size the position so a forced sale would not hurt.",
        "methods": [f"NSE shareholding filings, point in time; tiers from written rules; trigger assumes the loan "
                    f"starts at 2× cover and lenders sell at 1.5×; methodology "
                    f"{plain.VOCAB['pledge'][3]}–{plain.VOCAB['margin_call'][3]}."],
        "chips": ["e1", "e2"],
    }


def _integrated(ctx) -> dict:
    w, inv = ctx.worst_scenario, ctx.investment_amount
    status = _limits_status(ctx)
    if not w:
        return {"question": "What if everything goes wrong at once?", "status": status,
                "verdict": "no linked stress scenario could be run on this data.", "facts": [], "grades": [],
                "action": "Use a longer lookback.", "methods": [f"Methodology {plain.VOCAB['linked'][3]}."], "chips": []}
    return {
        "question": "What if everything goes wrong at once?",
        "status": status,
        "verdict": f"in the worst scenario ({w['name']}) you would lose about {_money(ctx, w['loss_pct'] * inv)} "
                   f"({w['loss_pct']:.1%}).",
        "facts": [(term("linked"), f"{w['loss_pct']:.1%}", "market, liquidity, credit and pledge effects together"),
                  (term("interaction"), f"{w['interaction_pct']:+.1%}", "loss that appears only when the risks combine")],
        "grades": [],
        "action": _first_action(ctx, "Nothing to do now.") if status != CLEAR else
        "Nothing to do now: every limit is within range.",
        "methods": [f"Historical crash shocks run through every pillar with price feedback; status is your worst limit; "
                    f"methodology {plain.VOCAB['linked'][3]}–{plain.VOCAB['reverse'][3]}."],
        "chips": [],
    }


def _decisions(ctx) -> dict:
    counts = ctx.limits_table["Status"].value_counts()
    status = _limits_status(ctx)
    breaches = ctx.limits_table[ctx.limits_table["Status"] != "green"]["Limit"].tolist()
    return {
        "question": "What should you do about it?",
        "status": status,
        "verdict": "every limit is within range." if not breaches else
        f"{len(breaches)} limit(s) need attention: {', '.join(breaches[:3])}.",
        "facts": [(term("limits"), f"{counts.get('green', 0)} green, {counts.get('amber', 0)} amber, "
                   f"{counts.get('red', 0)} red", ""),
                  ("Top risk", ctx.top_risks[0] if ctx.top_risks else "none", "")],
        "grades": [],
        "action": _first_action(ctx, "Nothing to do now."),
        "methods": [f"Trades ranked by the cut in Expected Shortfall; change explained by {plain.VOCAB['shapley_change'][1]}; "
                    f"methodology {plain.VOCAB['shapley_change'][3]}–{plain.VOCAB['limits'][3]}."],
        "chips": [],
    }


def _trust(ctx) -> dict:
    es = ctx.trusted[ctx.headline_model]["ES"]
    status = GRADE_STATUS.get(es.grade, WATCH)
    reasons = es.reasons[:2]
    return {
        "question": "How far can you rely on these numbers?",
        "status": status,
        "verdict": f"the headline Expected Shortfall earns grade {es.grade}.",
        "facts": [(term("grade"), es.grade, "; ".join(reasons) if reasons else "no deductions"),
                  (term("range90"), es.range_text(lambda v: _money(ctx, v)), "a wider range means a less certain number")],
        "grades": [("Expected Shortfall", es)],
        "action": "Rely on the headline numbers within their ranges." if status == CLEAR else
        "Read the ranges, not just the point values, and load the missing data listed below.",
        "methods": [f"Grades from written rules: range width, model disagreement, backtest, data quality, sample length "
                    f"and assumptions; methodology {plain.VOCAB['range90'][3]}–{plain.VOCAB['grade'][3]}."],
        "chips": [],
    }


OVERVIEW_PILLARS = ((P.MARKET, "Market"), (P.LIQUIDITY, "Liquidity"), (P.CREDIT, "Credit"),
                    (P.CONCENTRATION, "Concentration"), (P.EVENTS, "Pledges and governance"),
                    (P.INTEGRATED, "Everything at once"))


def _overview(ctx) -> dict:
    pillars = [(name, BUILDERS[page](ctx)) for page, name in OVERVIEW_PILLARS]
    status = _limits_status(ctx)
    reds = ctx.limits_table[ctx.limits_table["Status"] == "red"]["Limit"].tolist()
    ambers = ctx.limits_table[ctx.limits_table["Status"] == "amber"]["Limit"].tolist()
    verdict = (f"{len(reds)} limit(s) breached: {', '.join(reds)}." if reds else
               f"within your limits, but {len(ambers)} close: {', '.join(ambers)}." if ambers else
               "every limit is within range.")
    return {
        "question": "Is this portfolio's risk within your limits?" if ctx.is_portfolio else
        "Is this stock's risk within your limits?",
        "status": status, "verdict": verdict,
        "facts": [(name, f"{parts['status']}, {parts['verdict']}", "") for name, parts in pillars],
        "grades": [],
        "action": _first_action(ctx, "Nothing to do now."),
        "methods": ["Each pillar against its limit; the pages give the detail."],
        "chips": [],
    }


BUILDERS = {P.OVERVIEW: _overview, P.MARKET: _market, P.LIQUIDITY: _liquidity, P.CREDIT: _credit,
            P.CONCENTRATION: _concentration, P.EVENTS: _events, P.INTEGRATED: _integrated, P.DECISIONS: _decisions,
            P.TRUST: _trust}


def build(page: str, ctx) -> dict:
    return BUILDERS[page](ctx)


def text(parts: dict) -> str:
    """Everything the summary shows above the toggle, as plain text (for the word limit)."""
    lines = [parts["question"], f"{parts['status']}: {parts['verdict']}"]
    lines += [f"{label}: {value} {so}" for label, value, so in parts["facts"]]
    return " ".join(lines + [f"What to do: {parts['action']}"] + parts["methods"])


LAST_KEY = "summary_parts"  # the last summary shown, kept for the tests and the memo's plain paragraph


def render(page: str, ctx) -> dict:
    parts = build(page, ctx)
    st.session_state[LAST_KEY] = parts
    plain.verdict(parts["question"], parts["status"], parts["verdict"])
    for label, value, so in parts["facts"]:
        plain.fact(label, value, so)
    if parts["grades"]:
        cols = st.columns(len(parts["grades"]) + 2)
        for col, (label, metric) in zip(cols, parts["grades"]):
            with col:
                plain.grade_badge(metric, label)
    plain.action(parts["action"])
    for chip in parts["chips"]:
        plain.evidence_chip(chip)
    for m in parts["methods"]:
        plain.method_line(m)
    if page == P.EVENTS and ctx.disclosures["data"]["pledges"].empty:
        # The repository ships no NSE lists, so the upload sits in the summary, visible in both views
        from ui import disclosure_upload
        with st.expander("Upload disclosure files (pledges, surveillance, F&O ban, ratings)", expanded=True):
            disclosure_upload.render("pledge_upload")
    return parts
