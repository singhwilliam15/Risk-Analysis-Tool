"""
Research note (FINAL_PLAN_V6 Phase 6): "What predicts 50% crashes in Indian stocks? Evidence from every NSE stock,
2016–2024". Every number is read from the committed results (case_studies/results/*, evidence.registry()), so the
note cannot drift from the data; test_research_note.py rebuilds it and compares.

    python scripts/build_research_note.py   # docs/research_note.md, docs/research_note.pdf, docs/images/research_lifts.png
"""

import io
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import evidence as V  # noqa: E402

RESULTS = ROOT / "case_studies" / "results"
MD = ROOT / "docs" / "research_note.md"
PDF = ROOT / "docs" / "research_note.pdf"
CHART = ROOT / "docs" / "images" / "research_lifts.png"
TITLE = "What predicts 50% crashes in Indian stocks? Evidence from every NSE stock, 2016–2024"


def _csv(name):
    return pd.read_csv(RESULTS / name)


def _json(name):
    return json.loads((RESULTS / name).read_text(encoding="utf-8"))


def pct(v, d=1):
    return f"{v * 100:.{d}f}%"


def numbers() -> dict:
    """Every figure the note quotes, from the results files."""
    n = {}
    meta = _json("universe_meta.json")
    n.update(stocks=f"{meta['symbols_evaluated']:,}", stock_dates=f"{meta['stock_dates']:,}", months=meta["month_ends"],
             delisted=f"{meta['symbols_that_disappeared']:,}", crashes=f"{meta['events_observed']:,}")
    m = _csv("universe_metrics.csv")
    m = m[(m["Universe"] == "all") & (m["Outcome"] == "observed path")].set_index("Rule")
    n.update(base_wide=pct(m.loc["tool", "Base rate"]), v1_lift_wide=f"{m.loc['tool', 'Lift']:.2f}",
             market_flag_rate=pct(m.loc["market", "Flag rate"], 0), mom_lift_wide=f"{m.loc['drawdown_30', 'Lift']:.2f}",
             ma_lift_wide=f"{m.loc['below_200dma', 'Lift']:.2f}")
    b = _csv("warnings_v2_bootstrap.csv")
    b = b[b["Universe"] == "all"].set_index("Rule")
    t = _csv("warnings_v2_test.csv")
    t = t[(t["Universe"] == "all") & (t["Outcome"] == "observed path")].set_index("Rule")
    rng = lambda r: f"{b.loc[r, 'Lift 5%']:.2f}–{b.loc[r, 'Lift 95%']:.2f}"  # noqa: E731
    n.update(test_dates=f"{int(t.loc['r4', 'Stock-dates']):,}", base_test=pct(t.loc["r4", "Base rate"]),
             mom=f"{b.loc['drawdown_30', 'Lift']:.2f}", mom_rng=rng("drawdown_30"),
             r4=f"{b.loc['r4', 'Lift']:.2f}", r4_rng=rng("r4"),
             r4_diff=f"{b.loc['r4', 'Difference 5%']:+.2f} to {b.loc['r4', 'Difference 95%']:+.2f}".replace("-", "−"),
             r2=f"{b.loc['r2', 'Lift']:.2f}", r2_rng=rng("r2"), v1=f"{b.loc['tool', 'Lift']:.2f}", v1_rng=rng("tool"),
             r1=f"{b.loc['r1', 'Lift']:.2f}", r1_rng=rng("r1"), r4_flag=pct(t.loc["r4", "Flag rate"]))
    y = _csv("warnings_v2_yearly.csv").set_index(["Year", "Rule"])["Lift"]
    n.update(r2_min=f"{min(y.loc[(yr, 'r2')] for yr in range(2020, 2025)):.2f}",
             r2_max=f"{max(y.loc[(yr, 'r2')] for yr in range(2020, 2025)):.2f}",
             mom_2020=f"{y.loc[(2020, 'drawdown_30')]:.2f}")
    e = _csv("events_bootstrap.csv")
    e = e[e["Window"].str.startswith("primary") & (e["Universe"] == "all")].set_index("Rule")
    ib = _csv("events_incremental_bootstrap.csv")
    ib = ib[ib["Window"].str.startswith("primary") & (ib["Universe"] == "all")].set_index("Rule")
    ed = _json("events_decision.json")
    n.update(filings=f"{ed['coverage']['filings']:,}", companies=f"{ed['coverage']['companies']:,}",
             e1=f"{e.loc['e1', 'Lift']:.2f}", e1_rng=f"{e.loc['e1', 'Lift 5%']:.2f}–{e.loc['e1', 'Lift 95%']:.2f}",
             e2=f"{e.loc['e2', 'Lift']:.2f}", e2_rng=f"{e.loc['e2', 'Lift 5%']:.2f}–{e.loc['e2', 'Lift 95%']:.2f}",
             e_mom=f"{e.loc['drawdown_30', 'Lift']:.2f}",
             e1_inc=f"{ib.loc['e1', 'Lift']:.2f}", e1_inc_rng=f"{ib.loc['e1', 'Lift 5%']:.2f}–{ib.loc['e1', 'Lift 95%']:.2f}",
             e2_inc=f"{ib.loc['e2', 'Lift']:.2f}")
    mt = _csv("margin_trigger_rate_ratio.csv").set_index("Sample")
    p = mt.iloc[0]
    mb = _csv("margin_trigger_bootstrap.csv")
    mb = mb[mb["Universe"] == "all"].set_index("Rule")
    mi = _csv("margin_trigger_incremental_bootstrap.csv")
    mi = mi[mi["Universe"] == "all"].set_index("Rule")
    md = _json("margin_trigger_decision.json")
    n.update(mt_ratio=f"{p['ratio']:.2f}", mt_rng=f"{p['low']:.2f}–{p['high']:.2f}",
             mt_close=f"{int(p['n_close']):,}", mt_close_rate=pct(p["events_close"] / p["n_close"]),
             mt_far_rate=pct(p["events_far"] / p["n_far"]), mt_sample=f"{int(p['n_close'] + p['n_far']):,}",
             m1=f"{mb.loc['m1', 'Lift']:.2f}", m1_rng=f"{mb.loc['m1', 'Lift 5%']:.2f}–{mb.loc['m1', 'Lift 95%']:.2f}",
             m1_inc=f"{mi.loc['m1', 'Lift']:.2f}", m1_inc_rng=f"{mi.loc['m1', 'Lift 5%']:.2f}–{mi.loc['m1', 'Lift 95%']:.2f}",
             mt_dates=md["coverage"]["dates"], mt_stock_dates=f"{md['coverage']['stock_dates']:,}")
    j = _csv("events_jumps.csv").set_index(["Group", "Fall"])
    hj = j.loc[("High: E1", "≥ 20%")]
    n.update(jump_excess=f"{hj['Excess p a day'] * 100:+.3f}%".replace("-", "−"),
             jump_rng=f"{hj['p low (5%)'] * 100:+.3f}% to {hj['p high (95%)'] * 100:+.3f}%".replace("-", "−"))
    tally = _csv("tally.csv").set_index("Pillar")
    n.update(case_dates=int(tally.loc["any", "Case dates"]), case_hits=int(tally.loc["any", "Hits"]),
             case_fp=pct(tally.loc["any", "False-positive rate"]), controls=int(tally.loc["any", "Control dates"]),
             ma_hits=int(tally.loc["below_200dma", "Hits"]), ma_fp=pct(tally.loc["below_200dma", "False-positive rate"], 0),
             mom_hits=int(tally.loc["drawdown_30", "Hits"]))
    return n


def signal_rows() -> list:
    reg = V.registry()
    rows = []
    for r in reg.to_dict("records"):
        rows.append([r["label"], V.lift_text(r), V.incremental_text(r), V.SHORT.get(r["test"], "—") if r["test"] else "—",
                     r["badge"]])
    return rows


def bins_rows() -> list:
    b = _csv("margin_trigger_bins.csv")
    b = b[b["Sample"].str.startswith("primary")]
    return [[r["Fall to trigger"], f"{int(r['Stock-dates']):,}", f"{int(r['Crashes']):,}", pct(r["Crash rate"])]
            for r in b.to_dict("records")]


def chart(path: Path = CHART) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    reg = V.registry()
    reg = reg[reg["lift"].notna()].iloc[::-1]
    labels = [s.split(" (")[0] for s in reg["label"]]
    lift = reg["lift"].to_numpy(float)
    low = reg["low"].astype(float).to_numpy()
    high = reg["high"].astype(float).to_numpy()
    colors = {V.WORKS: "#2563eb", V.WEAKER: "#64748b", V.NO_EFFECT: "#cbd5e1"}
    fig, ax = plt.subplots(figsize=(7.2, 4.6), dpi=160)
    y = np.arange(len(reg))
    ax.barh(y, lift, color=[colors[b] for b in reg["badge"]], height=0.6)
    has = np.isfinite(low)
    ax.errorbar(lift[has], y[has], xerr=[lift[has] - low[has], high[has] - lift[has]], fmt="none", ecolor="#0f172a",
                elinewidth=0.8, capsize=2)
    ax.axvline(1, color="#0f172a", linewidth=0.8, linestyle="--")
    ax.set_yticks(y, labels, fontsize=7)
    ax.set_xlabel("Lift: crash rate of flagged stocks ÷ average crash rate (90% range)", fontsize=8)
    ax.tick_params(axis="x", labelsize=7)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(color=c, label=b) for b, c in colors.items()], fontsize=7, frameon=False, loc="lower right")
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, metadata={"Software": None})
    plt.close(fig)


def table_md(header, rows) -> str:
    out = ["| " + " | ".join(header) + " |", "| " + " | ".join("---" for _ in header) + " |"]
    return "\n".join(out + ["| " + " | ".join(str(c) for c in r) + " |" for r in rows])


SIGNAL_HEADER = ["Signal", "Lift (90% range)", "Among stocks not down 30%", "Test window", "Evidence"]
BINS_HEADER = ["Fall to the trigger", "Stock-dates", "Crashes", "Crash rate"]
YEAR_RULES = {"drawdown_30": "Momentum (down 30% in 6 months)", "r4": "R4 combined score", "r2": "R2 peer-relative tail risk",
              "tool": "v1 any price flag", "below_200dma": "Below 200-day average"}


def yearly_rows() -> tuple:
    y = _csv("warnings_v2_yearly.csv")
    years = sorted(y["Year"].unique())
    lift = y.set_index(["Year", "Rule"])["Lift"]
    base = y.groupby("Year")["Base rate"].first()
    rows = [[label] + [f"{lift.loc[(yr, r)]:.2f}" for yr in years] for r, label in YEAR_RULES.items()]
    rows.append(["Base crash rate"] + [pct(base.loc[yr]) for yr in years])
    return ["Rule"] + [str(yr) for yr in years], rows


def markdown(n: dict) -> str:
    return f"""# {TITLE}

*A research note from the Risk Analysis Tool project. Every number below is generated from the committed results
files (`scripts/build_research_note.py`). Methods: [methodology](methodology.md); pre-registrations:
[price rules](preregistration_warnings_v2.md), [pledges](preregistration_events.md),
[margin trigger](preregistration_margin_trigger.md).*

## Summary

Which public signals warn that an Indian stock will lose half its value within a year? I tested the warning rules of
an open-source risk tool on **every NSE stock from 2016 to 2024**: {n['stocks']} stocks, {n['delisted']} of which
later disappeared, at {n['months']} month-ends ({n['stock_dates']} stock-dates). The rules were fixed and committed
before each test was run.

- **The simplest rule is the one to beat.** "Down 30% in six months" (momentum) flags stocks that crash
  **{n['mom']} times** as often as average out of sample, 2020–24 (90% range {n['mom_rng']}).
- **More elaborate price rules do not beat it by a margin the test can confirm.** The best, a combined logistic
  score (R4), reached a lift of {n['r4']} ({n['r4_rng']}). The 90% range of its difference from momentum,
  {n['r4_diff']}, includes zero.
- **Promoter pledges warn, and add what momentum misses.** Owners who pledged half or more of their shares flag
  stocks that crash {n['e1']} times as often as average (range {n['e1_rng']}), 2022–24. Among stocks not already down
  30%, the lift stays {n['e1_inc']} ({n['e1_inc_rng']}).
- **Being close to the lenders' selling price adds little beyond the pledge level.** The crash-rate ratio is
  {n['mt_ratio']}, range {n['mt_rng']}; this was pre-registered and is not supported.
- **One assumption failed and was removed.** Pledge-heavy stocks show no excess sudden crashes beyond their own
  history, so the tool's jump overlay defaults to zero.

## 1. Question

Indian equity collapses — Yes Bank, DHFL, Zee, Jet Airways, Future Retail, Adani Enterprises in 2023 — combine market,
liquidity, credit and governance stress. A risk tool can show many warning lights. The question is which of them
carry information: does a flagged stock fall **50% or more within 12 months** more often than an unflagged one, and
does the signal add anything to the simplest rule a portfolio manager already uses, a large recent fall?

## 2. Data

- **Prices:** NSE's daily bhavcopies, which keep stocks that later delisted or were suspended, so the sample has no
  survivorship bias. Prices are back-adjusted for bonuses and splits with NSE's corporate-action list.
- **Universe:** every NSE equity at each month-end from January 2016 to December 2024: {n['stocks']} stocks,
  {n['stock_dates']} stock-dates, {n['crashes']} of which were followed by a 50% fall (a base rate of {n['base_wide']}).
- **Outcome:** the lowest close in the next 252 trading days is at least 50% below the as-of close. A stock that
  stopped trading counts as observed only to its last close.
- **Pledges:** NSE's quarterly shareholding-pattern filings ({n['filings']} filings, {n['companies']} companies,
  September 2021 – December 2024). Each filing counts only from its broadcast date, and later revisions are ignored.
  Until mid-2025 the filings report pledges together with other encumbrances, so the measure is an upper bound on
  pledges.
- **Access:** the data were downloaded from NSE's public archives before NSE's terms of use, which forbid automated
  collection and redistribution without permission, were found. Collection then stopped. The raw files are not
  redistributed; only derived statistics are published ([data sources](data_sources.md)).

## 3. Method

- **Lift** = crash rate among flagged stock-dates ÷ crash rate among all stock-dates. A lift of 2 means flagged stocks
  crashed twice as often as average.
- **Pre-registration.** Before each test the rules, thresholds, windows, metrics and decision rule were written down
  and committed to the public repository, so the git history proves the order. Results were computed once.
- **Design, embargo, test.** The new price rules were designed on 2016–18, 2019 was left out (its 12-month outcomes
  overlap the test), and they were tested once on 2020–24. The pledge rules use the tool's existing thresholds,
  tested on October 2022 – December 2024, the first window in which a 4-quarter change exists.
- **Uncertainty.** 90% ranges come from a circular block bootstrap of whole month-ends in blocks of 12, 2,000 resamples.
  Resampling dates rather than stocks keeps the cross-sectional correlation of crashes, and the blocks keep the
  overlap of 12-month outcomes. Differences from momentum use the same resamples.
- **Incremental lift.** The same lift computed only among stocks **not** already down 30% in six months, the test of
  whether a signal sees something momentum does not.
- **Evidence badges.** Fixed in advance: *works* if the range of lift − lift(momentum) is above 0; *weaker than
  momentum* if the lift range is above 1 but the difference range is not; *no effect* if the lift range includes 1.

## 4. Results

### 4.1 Every signal

![Lift with 90% ranges for every tested signal](images/research_lifts.png)

{table_md(SIGNAL_HEADER, signal_rows())}

Lifts from different windows are best compared within a window: price rules 2020–24, pledge rules October 2022 –
December 2024, and the v1 liquidity and stress flags 2016–24 without a range.

### 4.2 Momentum is the benchmark to beat

On the full 2016–24 sample "down 30% in six months" has a lift of {n['mom_lift_wide']}. In the out-of-sample test
window it is {n['mom']} ({n['mom_rng']}). Its weakness is 2020, when the COVID crash flagged everything: its lift that
year was {n['mom_2020']}.

### 4.3 The tool's original price flags barely beat chance

The tool's v1 market flag (5% daily Expected Shortfall, or volatility 1.5 times its one-year level) fires on
**{n['market_flag_rate']} of all NSE stock-dates**, because its threshold was set with large caps in mind. On
2016–24 any v1 price flag has a lift of {n['v1_lift_wide']}; out of sample, {n['v1']} ({n['v1_rng']}). The threshold
was not re-tuned after this was seen. Instead, four new rules were pre-registered and tested.

### 4.4 Better price rules, but not confirmably better than momentum

- **R4, a combined logistic score** of tail risk, volatility, trend and liquidity, flags {n['r4_flag']} of stock-dates
  with a lift of {n['r4']} ({n['r4_rng']}). It beats both v1 flags and momentum's point estimate, but the 90% range of
  the difference from momentum is {n['r4_diff']}. By the pre-registered rule the challenger does not replace v1; the
  app shows both and says why.
- **R2, peer-relative tail risk** (top decile of Expected Shortfall within the stock's liquidity tercile), has a lift of
  {n['r2']} ({n['r2_rng']}). It stayed between {n['r2_min']} and {n['r2_max']} in every test year, including 2020.
  This is reported as exploratory.
- **R1, tail risk against the stock's own history**, does not warn: lift {n['r1']} ({n['r1_rng']}).

### 4.5 Promoter pledges

| Rule | Lift (90% range) | Among stocks not down 30% |
| --- | --- | --- |
| E1: pledged or encumbered ≥ 50% of promoter holding | {n['e1']} ({n['e1_rng']}) | {n['e1_inc']} ({n['e1_inc_rng']}) |
| E2: encumbrance up ≥ 10 points in 4 quarters | {n['e2']} ({n['e2_rng']}) | {n['e2_inc']} |
| Momentum, same window | {n['e_mom']} | — |

Pledges warn, and the warning survives among stocks that have not yet fallen, which is where a risk manager needs
it. They do not beat momentum outright in this window.

### 4.6 Distance to the margin-call trigger (pre-registered October 2026)

A pledge becomes dangerous when the price falls far enough for lenders to sell. Using the tool's margin-call model —
the loan sized at the filing date with 2× cover, lenders selling at 1.5× — I asked whether stocks **within 10% of the
trigger** crash more often than other pledged stocks ({n['mt_sample']} stock-dates with encumbrance ≥ 20%,
{n['mt_dates']} month-ends).

{table_md(BINS_HEADER, bins_rows())}

The crash rate rises as the trigger gets closer ({n['mt_close_rate']} against {n['mt_far_rate']}), but the rate ratio of
{n['mt_ratio']} has a 90% range of {n['mt_rng']}, which includes 1. **The pre-registered hypothesis is not supported.**
As a stand-alone signal the rule (M1) warns, with a lift of {n['m1']} ({n['m1_rng']}), and among stocks not down 30% of
{n['m1_inc']} ({n['m1_inc_rng']}). That is mostly the pledge level and the price fall it requires.

### 4.7 Sudden crashes: an assumption that failed

The tool once assumed a High-tier stock had a 0.5% daily chance of a sudden 20% crash, about 72% a year. On NSE-wide
data, stocks with half or more of promoter shares encumbered show an excess daily rate of {n['jump_excess']} over
their own trailing rate (90% range {n['jump_rng']}). The base model already carries their history of falls, so the
overlay's default is now zero, with a grid showing what any assumed jump would add.

### 4.8 Case studies

Before six collapses (Yes Bank, DHFL, Zee, Jet Airways, Future Retail and Adani Enterprises in 2023), using only data
public at each date, the tool warned on {n['case_hits']} of {n['case_dates']} case dates, with false alarms on
{n['case_fp']} of {n['controls']} control dates. "Price below its 200-day average" warned on {n['ma_hits']}, with
{n['ma_fp']} false alarms, and momentum on {n['mom_hits']}. On these dates the tool's edge is precision, not
catching more.

## 5. What failed

- The v1 tail-risk threshold, which fires on most small stocks.
- R1 (own-history tail risk) and R3 (a volatility shock in a downtrend), with no effect.
- The challenger R4, which did not beat momentum by a confirmable margin.
- The margin-trigger hypothesis.
- The jump-overlay assumption.

Each is reported in the tool and the repository rather than re-tuned.

## 6. Limitations

- **One market, two regimes.** 2016–24 includes one crash (2020) and a long bull market. The pledge and margin-trigger
  tests cover 27 month-ends, with overlapping 12-month outcomes, so their power is limited.
- **No 2025 holdout and no forward ledger.** Both need new NSE data, which this project stopped collecting after
  reading NSE's terms. A request for permission has been drafted.
- **Pledges are an upper bound** before mid-2025 (encumbrance includes non-disposal undertakings), and pledge history
  starts in 2021, so DHFL, Zee and Jet Airways cannot be tested on this pillar.
- **The outcome is a large fall, not default or fraud.** Some falls recover; some frauds never show in prices first.
- **Untested signals** (surveillance lists, F&O bans, rating actions, auditor events, group links, Merton distance to
  default) have no history in the data and carry a "not back-tested" badge.

## 7. How the tool uses this

Every signal in the app and on the website shows its badge and its tested lift. The official market flag stays v1
because the challenger did not win its pre-registered test. The pledge page leads with the pledge level, the trigger
price and their evidence, and the jump overlay is off by default. Website:
<https://singhwilliam15.github.io/Risk-Analysis-Tool/evidence/>.

## Appendix: lift by test year

{table_md(*yearly_rows())}

Lift of each price rule in each year of the 2020–24 test, with the base rate of 50% falls among all NSE stock-dates
that year. Momentum's 2020 weakness and R2's stability are visible here.

## References

- Christoffersen, P. (1998). Evaluating interval forecasts. *International Economic Review*, 39(4), 841–862.
- Harvey, C. R., Liu, Y., & Zhu, H. (2016). … and the cross-section of expected returns. *Review of Financial
  Studies*, 29(1), 5–68.
- Jegadeesh, N., & Titman, S. (1993). Returns to buying winners and selling losers. *Journal of Finance*, 48(1), 65–91.
- Künsch, H. R. (1989). The jackknife and the bootstrap for general stationary observations. *Annals of Statistics*,
  17(3), 1217–1241.
- Merton, R. C. (1974). On the pricing of corporate debt. *Journal of Finance*, 29(2), 449–470.
- Nosek, B. A., Ebersole, C. R., DeHaven, A. C., & Mellor, D. T. (2018). The preregistration revolution. *PNAS*,
  115(11), 2600–2606.
- Politis, D. N., & Romano, J. P. (1992). A circular block-resampling procedure for stationary data. In *Exploring the
  Limits of Bootstrap*, 263–270. Wiley.
"""


# ---------------------------------------------------------------
# PDF from the same Markdown (headings, paragraphs, bullets, tables, the chart)
# ---------------------------------------------------------------

def _inline(text: str) -> str:
    text = text.replace("&", "&amp;").replace("<https://", "https://").replace(">", "&gt;").replace("<", "&lt;")
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<i>\1</i>", text)
    return re.sub(r"`([^`]+)`", r"<font face='Courier'>\1</font>", text)


def pdf(md: str, path: Path = PDF) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    base = getSampleStyleSheet()
    body = ParagraphStyle("b", parent=base["BodyText"], fontName="Helvetica", fontSize=10.5, leading=15, spaceAfter=5)
    bullet = ParagraphStyle("li", parent=body, leftIndent=10, bulletIndent=2, spaceAfter=2)
    styles = {1: ParagraphStyle("h1", parent=base["Title"], fontSize=17, leading=22, spaceAfter=8),
              2: ParagraphStyle("h2", parent=base["Heading2"], fontSize=13, spaceBefore=12, spaceAfter=5),
              3: ParagraphStyle("h3", parent=base["Heading3"], fontSize=11.5, spaceBefore=8, spaceAfter=4)}
    cell = ParagraphStyle("c", parent=body, fontSize=8, leading=10, spaceAfter=0)
    story, para, i = [], [], 0
    lines = md.splitlines()

    def flush():
        if para:
            story.append(Paragraph(_inline(" ".join(para)), body))
            para.clear()

    while i < len(lines):
        line = lines[i].rstrip()
        if not line:
            flush()
        elif line.startswith("#"):
            flush()
            level = len(line) - len(line.lstrip("#"))
            story.append(Paragraph(_inline(line.lstrip("# ").strip()), styles[min(level, 3)]))
        elif line.startswith("!["):
            flush()
            story.append(Image(str(CHART), width=165 * mm, height=165 * mm * 4.6 / 7.2))
        elif line.startswith("|"):
            flush()
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(set(c) <= {"-", " "} for c in cells):
                    rows.append([Paragraph(_inline(c), cell) for c in cells])
                i += 1
            widths = None
            if len(rows[0]) == 5:
                widths = [66 * mm, 28 * mm, 28 * mm, 20 * mm, 28 * mm]
            t = Table(rows, colWidths=widths, repeatRows=1)
            t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#cbd5e1")),
                                   ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
                                   ("VALIGN", (0, 0), (-1, -1), "TOP")]))
            story += [t, Spacer(1, 4)]
            continue
        elif line.lstrip().startswith("- "):
            flush()
            item = [line.lstrip()[2:]]
            while i + 1 < len(lines) and lines[i + 1].startswith("  ") and not lines[i + 1].lstrip().startswith("- "):
                i += 1
                item.append(lines[i].strip())
            story.append(Paragraph(_inline(" ".join(item)), bullet, bulletText="•"))
        else:
            para.append(line.strip())
        i += 1
    flush()

    def footer(canvas, doc):
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(colors.HexColor("#64748b"))
        canvas.drawString(18 * mm, 10 * mm, "Risk Analysis Tool · research note · github.com/singhwilliam15/Risk-Analysis-Tool")
        canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"{doc.page}")

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=18 * mm,
                            bottomMargin=18 * mm, title=TITLE, author="Risk Analysis Tool", invariant=1)
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    data = buf.getvalue()
    if path is not None:
        path.write_bytes(data)
    return data


def main() -> int:
    chart()
    md = markdown(numbers())
    MD.write_text(md, encoding="utf-8")
    data = pdf(md)
    pages = len(re.findall(rb"/Type\s*/Page[^s]", data))
    print(f"{MD} ({len(md.split()):,} words), {PDF} ({pages} pages), {CHART}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
