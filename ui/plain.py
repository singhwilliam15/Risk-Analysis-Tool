"""
Plain-language presentation (FINAL_PLAN_V6 Phase 4): one vocabulary and a few helpers every page uses.

Every term is shown in plain words WITH its technical name in brackets ("Bad-day loss (95% 1-day VaR)"); nothing is
renamed away. Status words are Clear / Watch / Warning, always written out (colour is a second signal, never the only
one). Presentation only: the helpers read numbers the pages already computed and change none.
"""

import os

import streamlit as st

SUMMARY, FULL = "Summary", "Full analysis"
VIEW_KEY = "view"
DEFAULT_VIEW_ENV = "RISK_TOOL_DEFAULT_VIEW"  # "full" for tests and build scripts, which must render every section
CLEAR, WATCH, WARNING = "Clear", "Watch", "Warning"
STATUS_ICON = {CLEAR: "🟢", WATCH: "🟠", WARNING: "🔴"}
SUMMARY_WORD_LIMIT = 140

# key: (plain phrase, technical term, one-line definition, methodology anchor)
VOCAB = {
    "var": ("Bad-day loss", "95% 1-day VaR", "The loss you should not exceed on 95 days out of 100.", "§1"),
    "es": ("Average loss on the worst days", "Expected Shortfall, 95%, 1-day",
           "The average loss on the 5 worst days in 100: what a bad day costs once it happens.", "§1"),
    "backtest": ("Checked against what happened", "out-of-sample backtest: Kupiec, Christoffersen, McNeil–Frey",
                 "Each model's past forecasts compared with the losses that followed.", "§3"),
    "tick_loss": ("Forecast error score", "tick loss", "How far a model's VaR forecasts were from the losses, "
                  "penalising misses in the tail; lower is better.", "§3.7"),
    "garch": ("Model that reacts when markets get nervous", "GARCH(1,1) with Student-t errors",
              "Volatility rises after large moves and fades slowly; fat tails allowed.", "§1.7"),
    "grade": ("How reliable this number is", "trust grade A–D",
              "A letter from written rules: width of the 90% range, model disagreement, backtest, data quality, "
              "sample length and the share of assumptions.", "§8.3"),
    "range90": ("Likely range", "90% range", "Where the number would fall in 9 of 10 resamples of the data.", "§8.1"),
    "days_liquidate": ("Days to sell it all", "days to liquidate at 20% participation",
                       "Days to sell without trading more than a fifth of a day's volume.", "§9.1"),
    "lvar": ("Bad-day loss including the cost of selling", "liquidity-adjusted VaR, LVaR",
             "VaR plus the bid-ask spread and the price impact of your own selling.", "§9.4"),
    "circuit": ("Locked at the daily limit", "lower circuit, price band",
                "NSE halts trading below a stock's daily band; a locked stock cannot be sold.", "§9.6"),
    "amfi": ("Fund-style selling test", "SEBI/AMFI liquidity stress test",
             "Days to sell 25% and 50% of the holdings pro rata, as mutual funds must report.", "§9.2"),
    "dd": ("Distance from default", "Merton distance to default",
           "How many standard deviations the firm's assets are above its debt.", "§10.1"),
    "pd": ("Default probability implied by the market", "risk-neutral Merton PD",
           "A model-implied probability, not a real-world default rate.", "§10.1"),
    "altman": ("Accounts-based distress score", "Altman Z / Z''",
               "A score from five balance-sheet and income ratios; below a cut-off means distress.", "§10.2"),
    "pca": ("RBI's intervention levels", "Prompt Corrective Action thresholds",
            "Capital, asset-quality and leverage levels at which RBI restricts a bank.", "§10.6"),
    "enb": ("Number of truly independent bets", "effective number of bets, Meucci",
            "How many uncorrelated positions the portfolio behaves like.", "§11.4"),
    "factor_share": ("Share of risk from the whole market and style factors", "factor share of variance",
                     "The part of the variance explained by market, size, value and momentum.", "§11.3"),
    "crisis_corr": ("Diversification left in a crisis", "crisis correlation",
                    "How much of the diversification benefit survived in past crisis windows.", "§11.5"),
    "pledge": ("Owners' shares pledged for loans", "promoter pledge / encumbrance",
               "Promoter shares given as collateral; lenders can sell them if the price falls.", "§12.1"),
    "margin_call": ("Price at which lenders can sell", "pledge margin-call trigger",
                    "The price after the fall that takes the loan's collateral cover from 2× to 1.5× (assumptions).", "§12.3"),
    "surveillance": ("On NSE's watch-list", "ASM / GSM surveillance",
                     "NSE's additional or graded surveillance measures on unusual trading or weak fundamentals.", "§12.1"),
    "tier": ("Warning level", "event tier Low / Elevated / High", "Written rules over the disclosure signals.", "§12.2"),
    "jump": ("Sudden-drop add-on", "jump overlay on ES", "An assumed chance of a one-day crash added to ES; off by "
             "default after testing.", "§12.4"),
    "lift": ("Crash-rate multiple", "lift", "How many times more often flagged stocks fell 50% within a year than "
             "the average stock.", "§15.2"),
    "linked": ("Loss when everything goes wrong together", "linked stress (multi-pillar)",
               "A crash run through market, liquidity, credit and pledge effects at once, with price feedback.", "§13.1"),
    "interaction": ("Extra loss when risks hit together", "interaction effect, Shapley split",
                    "The part of the linked loss that appears only when the pillars act together.", "§13.1"),
    "reverse": ("What move would cost you this much", "reverse stress test",
                "The most plausible market move that produces a chosen loss.", "§13.2"),
    "limits": ("Risk limits", "limit utilisation, traffic lights", "Each risk measured against its limit: green "
               "below 80%, amber 80–100%, red above.", "§14.3"),
    "shapley_change": ("Why the risk changed", "Shapley attribution of the change in ES",
                       "The change split exactly between positions, volatility, correlation, data window and model.",
                       "§14.1"),
    "momentum": ("Already down 30% in 6 months", "momentum baseline",
                 "The simple rule every warning signal is compared against.", "§15.1"),
    "ghost": ("Jump when an old crash leaves the data", "ghost effect in historical VaR",
              "A sudden change in VaR when an old extreme day drops out of the window.", "§8.2"),
}


def term(key: str) -> str:
    """'plain phrase (technical term)'."""
    plain, technical, _, _ = VOCAB[key]
    return f"{plain} ({technical})"


def default_view() -> str:
    return FULL if os.environ.get(DEFAULT_VIEW_ENV, "").lower() == "full" else SUMMARY


def view() -> str:
    return st.session_state.get(VIEW_KEY, default_view())


def view_switch() -> None:
    """The sidebar switch between Summary and Full analysis."""
    st.sidebar.radio("View", (SUMMARY, FULL), key=VIEW_KEY, horizontal=True, index=(SUMMARY, FULL).index(default_view()),
                     help="Summary: the verdict, the key facts and what to do, with the method behind each number. "
                          "Full analysis: every table and chart. Nothing is hidden for good; the summary links to it.")


def status_from_light(light: str) -> str:
    """CRO-dashboard limit status → status word: green → Clear, amber → Watch, red → Warning."""
    return {"green": CLEAR, "amber": WATCH, "red": WARNING}.get(str(light).lower(), CLEAR)


def worst(*statuses) -> str:
    order = [CLEAR, WATCH, WARNING]
    return max(statuses, key=order.index) if statuses else CLEAR


def verdict(question: str, status: str, sentence: str) -> None:
    """The page's opening: the question it answers, a status word (with its icon) and a one-line verdict."""
    st.markdown(f"**{question}**")
    st.markdown(f"#### {STATUS_ICON[status]} {status}: {sentence}")


def fact(label: str, value: str, so_what: str = "", method: str = "") -> None:
    st.markdown(f"- **{label}:** {value}" + (f" — {so_what}" if so_what else ""))
    if method:
        st.caption(f"  Method: {method}")


def action(text: str) -> None:
    st.markdown(f"**What to do:** {text}")


def method_line(text: str) -> None:
    st.caption(f"Method: {text}")


def evidence_chip(sid: str) -> None:
    """Short form of evidence.chip: the signal, its badge and its tested crash-rate multiple (lift)."""
    import evidence as V
    r = V.record(sid)
    name = V.SIGNALS[sid].split(" (")[0]
    if r["badge"] == V.UNTESTED:
        st.caption(f"Evidence for '{name}': {V.UNTESTED}.")
        return
    st.caption(f"Evidence for '{name}': {r['badge']}. Flagged stocks crashed {V.lift_text(r)} as often as the average "
               f"stock ({V.SHORT.get(r['test'], r['test'])}).")


def grade_badge(metric, label: str = None) -> None:
    """The trust grade as a short badge whose popover names the metric and lists the reasons for the grade."""
    reasons = "; ".join(metric.reasons) or "no deductions"
    with st.popover(f"{label or metric.name}: grade {metric.grade}"):
        st.markdown(f"**{metric.name}: grade {metric.grade}**")
        st.markdown(reasons)


def full_analysis(page: str) -> bool:
    """Whether to show the full page: always in Full analysis, behind a toggle in Summary."""
    if view() == FULL:
        st.markdown("---")
        return True
    return st.toggle("Show the full analysis", key=f"full_{page}",
                     help="Every table and chart behind the summary. The sidebar's View switch shows them on every page.")


def words(text: str) -> int:
    return len(text.split())
