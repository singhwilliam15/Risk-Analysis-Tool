"""
Smoke tests for the Streamlit app itself, run with synthetic market data (see conftest.fake_fetch_stock_data).
They load the full app in each mode and drive the main widgets, checking that nothing raises.
"""

import pytest
from streamlit.testing.v1 import AppTest

TIMEOUT = 180


def run_app(mode=None, page="Market", **sidebar):
    at = AppTest.from_file("app.py", default_timeout=TIMEOUT)
    at.run()
    if page != "Overview":
        at.radio(key="page").set_value(page)
        at.run()
    if mode:
        sidebar_radio(at, "Analysis Mode").set_value(mode)
        at.run()
    selects = {w.label: w for w in at.sidebar.selectbox}
    for label, value in sidebar.items():
        selects[label].set_value(value)
    if sidebar:
        at.run()
    return at


def sidebar_radio(at, label):
    """A sidebar radio by its label (the View switch comes first)."""
    return next(r for r in at.sidebar.radio if r.label == label)


def assert_clean(at):
    assert not at.exception, [e.value for e in at.exception]
    assert not at.error, [e.value for e in at.error]


def test_single_stock_mode(fake_market):
    at = run_app()
    assert_clean(at)
    assert [t.label for t in at.tabs] == ["📊 Model Comparison", "📈 Price & Volatility", "⚡ Stress Testing", "🔬 Backtesting", "📥 Excel Report"]
    models = at.table[0].value
    assert len(models) == 8 and "GARCH(1,1)-t" in models.index


def test_market_page_shows_the_signals_with_a_tested_record(fake_market):
    """Every signal in evidence order, whether it fires now, its tested lift and badge; the official flag stated."""
    import evidence as V
    at = run_app()
    assert_clean(at)
    assert any("Signals with a tested record" in m.value for m in at.markdown)
    assert any("Official market flag: v1 (legacy rule)" in c.value for c in at.caption)
    table = next(d.value for d in at.dataframe if "Evidence" in d.value.columns)
    assert table["Signal"].tolist() == V.registry()["label"].tolist()  # evidence order
    assert table["Evidence"].iloc[0] == V.WORKS and table["Evidence"].iloc[-1] == V.UNTESTED
    assert set(table["Fires now"]) <= {"✓ fires", "–", "n.a."}
    momentum = table[table["Signal"].str.startswith("Already down 30%")].iloc[0]
    assert momentum["Tested lift (90% range)"].startswith("1.78×")
    us = run_app(**{"Quick Preset Ticker": "Apple (US)"})
    assert_clean(us)
    assert any("tested on NSE stocks only" in i.value for i in us.info)


def test_single_stock_long_history_multi_day(fake_market):
    at = run_app(**{"Historical Lookback Window": "5y", "Holding Period (Days)": 10})
    at.sidebar.select_slider[0].set_value(0.975)
    at.run()
    assert_clean(at)
    assert any("10-day check" in c.value for c in at.caption)


def test_portfolio_mode_with_what_if(fake_market):
    at = run_app("Portfolio")
    assert_clean(at)
    assert "🧩 Portfolio Risk" in [t.label for t in at.tabs]
    for basis in ("Historical VaR", "Parametric VaR"):
        at.radio(key="decomposition_basis").set_value(basis)
        at.run()
        assert_clean(at)
    at.number_input(key="what_if_weight_RELIANCE.NS").set_value(10.0)
    at.run()
    assert_clean(at)
    assert any(c.value.startswith("What-if weights") for c in at.caption)


def test_portfolio_buy_and_hold(fake_market):
    at = run_app("Portfolio")
    sidebar_radio(at, "Rebalancing").set_value("Buy-and-hold (weights drift)")
    at.run()
    assert_clean(at)


def test_short_history_flags_low_power(fake_market):
    at = run_app(**{"Historical Lookback Window": "1y"})
    assert_clean(at)
    assert any("Not enough data" in w.value for w in at.warning)


@pytest.mark.parametrize("edits, expected", [
    ({0: {"Ticker": "AAPL"}}, "different currencies"),
    ({0: {"Ticker": "BADTICKER"}}, "Could not load every holding"),
])
def test_portfolio_input_errors_are_reported(fake_market, edits, expected):
    at = AppTest.from_file("app.py", default_timeout=TIMEOUT)
    at.run()
    sidebar_radio(at, "Analysis Mode").set_value("Portfolio")
    at.session_state["holdings"] = {"edited_rows": edits, "added_rows": [], "deleted_rows": []}
    at.run()
    assert not at.exception
    assert any(expected in e.value for e in at.error)


def test_bad_single_ticker_is_reported(fake_market):
    at = AppTest.from_file("app.py", default_timeout=TIMEOUT)
    at.run()
    at.sidebar.text_input[0].set_value("BADX")
    at.run()
    assert not at.exception
    assert at.error and "BADX" in at.error[0].value


def test_overview_is_the_landing_page(fake_market):
    at = AppTest.from_file("app.py", default_timeout=TIMEOUT)
    at.run()
    assert_clean(at)
    assert at.title[0].value == "⚡ Risk Analysis Tool"
    assert at.radio(key="page").value == "Overview"
    assert not at.tabs  # the market tabs live on the Market page
    headings = [m.value for m in at.markdown]
    assert any("Positions" in h for h in headings) and any("Data quality" in h for h in headings)
    # The CRO dashboard opens the page: one row per pillar, bottom line, risks and actions
    assert any("CRO dashboard" in h for h in headings) and any(h.startswith("**Bottom line.**") for h in headings)
    dashboard = at.dataframe[0].value
    assert dashboard["Pillar"].tolist()[:3] == ["Market", "Liquidity", "Credit"]
    assert set(dashboard.columns) == {"Pillar", "Headline", "Range", "Grade", "Status"}


@pytest.mark.parametrize("mode", ["Single Stock", "Portfolio"])
def test_integrated_stress_page(fake_market, mode):
    at = run_app(mode if mode == "Portfolio" else None, page="Integrated Stress")
    assert_clean(at)
    labels = [m.label for m in at.metric]
    assert labels[1:] == ["Interaction (cross effect)", "Feedback rounds"]
    table = at.dataframe[0].value
    assert {"Market Loss", "Market", "Liquidity", "Credit", "Events", "Linked Total", "Interaction", "Rounds"} <= set(table.columns)
    assert "Siloed Sum" not in table.columns
    assert any(m.value == "#### Jump to default" for m in at.markdown)
    assert "Market -20%" in table["Scenario"].tolist()
    assert any("(reverse stress test)" in m.value for m in at.markdown)
    at.radio(key="reverse_loss").set_value(0.30)
    at.run()
    assert_clean(at)
    assert any("lose 30%" in m.value for m in at.markdown)


@pytest.mark.parametrize("mode", ["Single Stock", "Portfolio"])
def test_decisions_page(fake_market, mode):
    at = run_app(mode if mode == "Portfolio" else None, page="Decisions")
    assert_clean(at)
    limits = at.dataframe[0].value
    # Concentration limits apply to portfolios only
    assert len(limits) == (7 if mode == "Portfolio" else 5) and limits["Status"].str.contains("green|amber|red|⚪").all()
    headings = [m.value for m in at.markdown]
    for section in ("Limits", "What changed in the risk", "Best risk-reducing trades", "One-page CRO memo"):
        assert any(section in h for h in headings), section
    assert any("Exact Shapley split" in c.value for c in at.caption)
    at.selectbox(key="change_months").set_value(12)
    at.run()
    assert_clean(at)


@pytest.mark.parametrize("mode", ["Single Stock", "Portfolio"])
def test_trust_page(fake_market, mode):
    at = run_app(mode if mode == "Portfolio" else None, page="Trust")
    assert_clean(at)
    headings = [m.value for m in at.markdown]
    for section in ("How reliable each model is", "lookback sensitivity", "ghost effect", "What this metric misses"):
        assert any(section in h for h in headings), section
    assert at.metric[2].label == "Trust grade" and at.metric[2].value in ("A", "B", "C", "D")
    models = at.dataframe[0].value
    assert len(models) == 8 and set(models["Grade"]) <= {"A", "B", "C", "D"}


@pytest.mark.parametrize("mode", ["Single Stock", "Portfolio"])
def test_liquidity_page(fake_market, mode):
    at = run_app(mode if mode == "Portfolio" else None, page="Liquidity")
    assert_clean(at)
    headings = [m.value for m in at.markdown]
    for section in ("trading capacity", "SEBI/AMFI", "volume in past crises", "liquidity-adjusted VaR",
                    "circuit-lock risk", "Amihud", "What this metric misses"):
        assert any(section in h for h in headings), section
    assert [m.label for m in at.metric] == ["Days to liquidate 50% (AMFI)", "Sellable in 5 days", "Liquidity-adjusted VaR",
                                            "Circuit-lock loss"]
    assert any("grade **" in c.value for c in at.caption)
    # The assumptions are sidebar inputs, so every page (and the Excel export) sees the same values
    at.number_input(key="liq_participation").set_value(5.0)
    at.run()
    assert_clean(at)
    assert "Participation rate 5%" in at.caption[1].value or any("Participation rate 5%" in c.value for c in at.caption)


@pytest.mark.parametrize("mode", ["Single Stock", "Portfolio"])
def test_credit_page(fake_market, mode):
    at = run_app(mode if mode == "Portfolio" else None, page="Credit")
    assert_clean(at)
    # The page leads with the distance to default and the agencies' default rates; Merton's PD comes third
    labels = [m.label for m in at.metric]
    assert labels[0].startswith("Lowest distance to default")
    assert labels[1] == "Agency 1-year default rate (value-weighted)" and labels[2] == "Merton PD (risk-neutral, model-implied)"
    assert any("risk-neutral probability" in c.value for c in at.caption)
    by_holding = at.dataframe[0].value
    assert by_holding["DD"].iloc[0] != "not available"
    assert {"DD percentile", "Agency 1-yr default rate", "Merton PD (risk-neutral)"} <= set(by_holding.columns)
    if mode == "Portfolio":
        bank = by_holding.set_index("Ticker").loc["HDFCBANK.NS"]
        assert bank["DD"] == "not available" and bank["Altman"] == "not applicable"
        assert any("75% of the portfolio value is modelled" in c.value for c in at.caption)  # HDFC Bank is 25%
    at.selectbox(key="credit_vol").set_value("EWMA")
    at.run()
    assert_clean(at)


@pytest.mark.parametrize("mode", ["Single Stock", "Portfolio"])
def test_concentration_page(fake_market, mode):
    at = run_app(mode if mode == "Portfolio" else None, page="Concentration & Factors")
    assert_clean(at)
    headings = [m.value for m in at.markdown]
    assert any("(factor exposures, Fama-French 3 + momentum)" in h for h in headings)
    assert any("What this metric misses" in h for h in headings)
    assert any("Factor data:" in c.value and "IIM Ahmedabad" in c.value for c in at.caption)
    labels = [m.label for m in at.metric]
    assert "Factor share of variance" in labels
    if mode == "Portfolio":
        assert "Effective number of bets (Meucci)" in labels and "Diversification kept in a crisis" in labels
        assert any("(crisis correlation)" in h for h in headings)
    else:
        assert any("100% concentrated" in i.value for i in at.info)


@pytest.mark.parametrize("mode", ["Single Stock", "Portfolio"])
def test_events_page_without_disclosures(fake_market, mode, monkeypatch, tmp_path):
    import disclosures
    import ui.foundations
    # An empty disclosure folder (as in the repository, which ships no NSE lists)
    monkeypatch.setattr(ui.foundations, "load_disclosures", lambda: disclosures.load_disclosures(tmp_path))
    at = run_app(mode if mode == "Portfolio" else None, page="Promoter Pledge & Governance")
    assert_clean(at)
    assert any(s.value.startswith("Promoter Pledge & Governance Risk") for s in at.subheader)
    assert any(c.value.startswith("Checked ") and "Not checked" in c.value for c in at.caption)
    # Only fixable gaps warn (files the page needs, which the user can upload); auditor events are missing by design
    assert any(w.value.startswith("Not loaded:") and "upload" in w.value for w in at.warning)
    assert not any("Auditor" in w.value for w in at.warning)
    core = next(d.value for d in at.dataframe if "Pledged (% of promoter holding)" in d.value.columns)
    assert (core["Pledged (% of promoter holding)"] == "not available").all()
    tiers = next(d.value for d in at.dataframe if "Based on" in d.value.columns)
    assert tiers["Based on"].str.contains("signals").all()
    analyst = next(e for e in at.expander if e.label.startswith("Analyst details"))
    assert [m.label for m in analyst.metric][:2] == ["Event-adjusted ES (95%, 1-day)", "ES added by event risk"]


def _sample_disclosures(tmp_path):
    """Made-up disclosure files for synthetic tickers, dated relative to the synthetic price history (ends 30 Sep 2026)."""
    import json
    (tmp_path / "pledges.csv").write_text(
        "symbol,quarter_end,promoter_holding_pct,pledged_pct_of_promoter,disclosure_date\n"
        "RELIANCE,2025-06-30,50,5,2025-07-15\nRELIANCE,2026-06-30,50,60,2026-07-15\n"
        "TCS,2026-06-30,70,0,2026-07-15\nRELIANCE,2026-09-30,50,90,2026-10-15\n")  # the last row is not public yet
    (tmp_path / "ratings.csv").write_text(
        "symbol,agency,instrument,rating,outlook,action,action_date\n"
        "HDFCBANK,CRISIL,Bonds,CRISIL AA,Negative,downgraded,2026-05-01\n")
    (tmp_path / "ban.csv").write_text("Securities in Ban For Trade Date 25-SEP-2026:\n1,TCS\n")
    entries = [{"file": f, "dataset": d, "source_url": "https://example.org/test", "downloaded_on": "2026-09-30",
                "coverage_start": "2025-01-01", "coverage_end": "2026-09-30"}
               for f, d in (("pledges.csv", "pledges"), ("ratings.csv", "ratings"), ("ban.csv", "fo_ban"))]
    (tmp_path / "manifest.json").write_text(json.dumps({"files": entries}))


def test_events_page_with_sample_disclosures(fake_market, monkeypatch, tmp_path):
    import disclosures
    import ui.foundations
    _sample_disclosures(tmp_path)
    monkeypatch.setattr(ui.foundations, "load_disclosures", lambda: disclosures.load_disclosures(tmp_path))
    at = run_app("Portfolio", page="Promoter Pledge & Governance")
    assert_clean(at)
    tiers = next(d.value for d in at.dataframe if "Based on" in d.value.columns).set_index("Holding")
    assert tiers.loc["RELIANCE.NS", "Tier"] == "🔴 High"  # 60% pledged; the 90% row is disclosed after the as-of date
    core = next(d.value for d in at.dataframe if "Pledged (% of promoter holding)" in d.value.columns).set_index("Holding")
    assert core.loc["RELIANCE.NS", "Pledged (% of promoter holding)"] == "60.0%"
    assert core.loc["RELIANCE.NS", "Change over 4 quarters"] == "+55.0 pp"
    assert tiers.loc["HDFCBANK.NS", "Tier"] == "🟠 Elevated" and tiers.loc["TCS.NS", "Tier"] == "🟠 Elevated"
    flags = next(d.value for d in at.dataframe if "Red flag" in d.value.columns)
    assert set(flags["Evidence"]) <= {"Not back-tested", "Tested · weaker than momentum"}
    # Calibrated defaults: no extra jump probability, so event risk adds exactly nothing, and the cards are in the expander
    analyst = next(e for e in at.expander if e.label.startswith("Analyst details"))
    assert analyst.metric[1].value == "₹0"
    # ...until a probability is set for the High tier (RELIANCE is High): then the cards are at the top again
    at.number_input(key="ev_high_p").set_value(0.5)
    at.run()
    assert_clean(at)
    analyst = next(e for e in at.expander if e.label.startswith("Analyst details"))
    assert len(analyst.metric) == 0 and at.metric[1].value not in ("₹0", "not available")


def test_headline_numbers_carry_range_and_grade(fake_market):
    at = run_app(page="Market")
    assert_clean(at)
    cards = " ".join(m.value for m in at.markdown if "metric-card" in m.value)
    assert cards.count("90% range") == 3 and cards.count("grade ") == 3
    table = at.table[0].value
    assert "Grade" in table.columns and any("90% range" in c for c in table.columns)


def test_inputs_are_shared_across_pages(fake_market):
    at = run_app("Portfolio", page="Market")
    at.radio(key="page").set_value("Overview")
    at.run()
    assert_clean(at)
    assert sidebar_radio(at, "Analysis Mode").value == "Portfolio"  # the sidebar keeps its state when the page changes
    assert "5-stock portfolio" in at.subheader[0].value


@pytest.mark.parametrize("mode, column, amounts", [
    ("Shares", "Shares", [100.0, 150.0, 50.0, 100.0, 20.0]),
    ("Value", "Value", [300000.0, 250000.0, 200000.0, 150000.0, 100000.0]),
])
def test_portfolio_entered_as_shares_or_value(fake_market, mode, column, amounts):
    at = run_app("Portfolio", page="Overview")
    {w.label: w for w in at.sidebar.selectbox}["Holdings entered as"].set_value(mode)
    at.run()
    assert_clean(at)
    positions = next(d.value for d in at.dataframe if list(d.value.columns[:2]) == ["Ticker", "Quantity"])
    assert list(positions.columns[:2]) == ["Ticker", "Quantity"]
    assert positions["Weight"].sum() == pytest.approx(1.0)
    if mode == "Value":
        assert positions.filter(like="Value").iloc[:, 0].tolist() == pytest.approx(amounts)
    else:
        assert positions["Quantity"].tolist() == pytest.approx(amounts)
    # The Market page then runs on the total value of the holdings
    at.radio(key="page").set_value("Market")
    at.run()
    assert_clean(at)


def test_network_guard_blocks_outbound_connections():
    import socket
    with pytest.raises(RuntimeError, match="Network access is disabled"):
        socket.create_connection(("query1.finance.yahoo.com", 443), timeout=1)


def test_a_link_opens_the_page_it_names(fake_market):
    """?page=market (or the page title) opens that page directly; the URL then follows page changes."""
    from ui.pages import page_from_url
    assert page_from_url("market") == "Market" and page_from_url("Integrated Stress") == "Integrated Stress"
    assert page_from_url("event-governance") == "Promoter Pledge & Governance"  # the old link still works
    assert page_from_url("promoter-pledge-governance") == "Promoter Pledge & Governance"
    assert page_from_url("market") == "Market" and page_from_url("nonsense") is None
    at = AppTest.from_file("app.py", default_timeout=TIMEOUT)
    at.query_params["page"] = "market"
    at.run()
    assert_clean(at)
    assert at.radio(key="page").value == "Market"
    assert any("Signals with a tested record" in m.value for m in at.markdown)
    at.radio(key="page").set_value("Trust")
    at.run()
    assert at.query_params["page"] in ("trust", ["trust"])



# ---------------------------------------------------------------
# Plain-language presentation (FINAL_PLAN_V6 Phase 4)
# ---------------------------------------------------------------

STATUS_WORDS = ("Clear:", "Watch:", "Warning:")


def summary_view(at):
    at.radio(key="view").set_value("Summary")
    at.run()
    return at


@pytest.mark.parametrize("mode", ["Single Stock", "Portfolio"])
def test_every_page_opens_with_a_plain_summary(fake_market, mode):
    """Summary view: each page starts with a status word and a verdict, and keeps the full analysis behind a toggle
    that reveals it; the Full analysis view shows the same summary and then everything, without the toggle."""
    from ui.pages import GLOSSARY, PAGES
    at = summary_view(run_app(mode if mode == "Portfolio" else None, page="Overview"))
    for page in PAGES:
        at.radio(key="page").set_value(page)
        at.run()
        assert_clean(at)
        if page == GLOSSARY:
            continue
        headings = [m.value for m in at.markdown if m.value.startswith("#### ")]
        assert headings and any(w in headings[0] for w in STATUS_WORDS), page
        toggle = at.toggle[0]
        assert toggle.label == "Show the full analysis" and not toggle.value, page
        shown = len(at.markdown)
        toggle.set_value(True)
        at.run()
        assert_clean(at)
        assert len(at.markdown) > shown, page  # the toggle reveals the full page
    at.radio(key="view").set_value("Full analysis")
    at.run()
    assert_clean(at)
    assert not at.toggle or all(t.label != "Show the full analysis" for t in at.toggle)


def test_summary_text_is_short_and_names_the_technical_terms(fake_market):
    """Every page's summary, from a real run: under the word limit, and each plain term followed by its technical name."""
    from ui import plain, summaries
    from ui.pages import PAGES
    for mode in (None, "Portfolio"):
        at = run_app(mode, page="Overview")
        for page in summaries.BUILDERS:
            at.radio(key="page").set_value(page)
            at.run()
            parts = at.session_state[summaries.LAST_KEY]
            words = plain.words(summaries.text(parts))
            assert words <= plain.SUMMARY_WORD_LIMIT, (page, words)
            assert parts["status"] in (plain.CLEAR, plain.WATCH, plain.WARNING)
            for label, _, _ in parts["facts"]:
                if any(label.startswith(p) for p, *_ in plain.VOCAB.values()):
                    assert label.endswith(")") and " (" in label, (page, label)


def test_glossary_lists_every_term(fake_market):
    from ui.plain import VOCAB
    at = run_app(page="Glossary")
    assert_clean(at)
    table = at.table[0].value
    assert len(table) == len(VOCAB) and table["Technical term"].tolist() == [v[1] for v in VOCAB.values()]
    assert all(a.startswith("§") for a in table["Methodology"])


def test_how_to_read_note_can_be_dismissed(fake_market):
    at = summary_view(run_app(page="Overview"))
    assert any(m.value.startswith("**How to read this tool.**") for m in at.markdown)
    at.button(key="how_to_read_ok").click()
    at.run()
    assert not any(m.value.startswith("**How to read this tool.**") for m in at.markdown)


def test_pledge_page_without_files_says_not_checked_and_takes_an_upload(fake_market):
    """No NSE lists ship with the repository: the page says 'not checked' and offers an upload; an uploaded
    pledge filing then drives the verdict (session state stands in for the file uploader)."""
    from ui.disclosure_upload import UPLOADS_KEY
    at = summary_view(run_app(page="Promoter Pledge & Governance"))
    assert_clean(at)
    assert any("Watch: not checked: no pledge files are loaded." in m.value for m in at.markdown)
    assert any(u.label == "Disclosure files" for u in at.get("file_uploader"))
    filing = ("symbol,quarter_end,promoter_holding_pct,pledged_pct_of_promoter,pledged_pct_of_total,pledged_shares,"
              "disclosure_date\nASIANPAINT,2026-06-30,50.0,60.0,30.0,1000,2026-07-13\n").encode()
    at.session_state[UPLOADS_KEY] = [{"name": "pledges.csv", "dataset": "pledges", "as_of": "2026-09-30", "content": filing}]
    at.run()
    assert_clean(at)
    verdict = next(m.value for m in at.markdown if m.value.startswith("#### "))
    assert "not checked" not in verdict and "60.0% of the owners' shares" in " ".join(m.value for m in at.markdown)
