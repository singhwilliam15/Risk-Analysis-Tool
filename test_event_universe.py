"""
The event pillar's wider test (Phase G, event_universe.py): symbol matching, the point-in-time join, the rules at
their thresholds, the jump-default rule, and the original-filing selection of the download script.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import event_universe as EU
from events import ELEVATED, HIGH, LOW, load_rules

sys.path.insert(0, str(Path(__file__).parent / "scripts"))
import fetch_shareholding_history as FH  # noqa: E402

CHANGES = [("OLDCO", "NEWCO", pd.Timestamp("2023-06-01"))]


def test_chain_follows_only_later_renames():
    assert EU.chain("OLDCO", CHANGES, "2022-10-20") == "NEWCO"   # filed before the rename: the panel calls it NEWCO
    assert EU.chain("OLDCO", CHANGES, "2023-07-20") == "OLDCO"   # a later, unrelated use of the old symbol


def test_map_symbols_by_symbol_rename_then_isin():
    filings = pd.DataFrame({"symbol": ["ZEEL", "OLDCO", "ODD", "GONE"],
                            "isin": ["IN9256A01042", "INE000X", "INE111Y", "INE999Z"],  # Zee: a partly-paid ISIN
                            "disclosure_date": ["2022-10-20"] * 4})
    out = EU.map_symbols(filings, {"ZEEL", "NEWCO", "PANELSYM"}, {"INE111Y": "PANELSYM"}, CHANGES)
    assert out.iloc[:3].tolist() == ["ZEEL", "NEWCO", "PANELSYM"] and pd.isna(out.iloc[3])


def filings_frame():
    return pd.DataFrame({
        "panel_symbol": ["A"] * 5,
        "quarter_end": ["2021-09-30", "2021-12-31", "2022-09-30", "2022-12-31", "2023-03-31"],
        "disclosure_date": ["2021-10-20", "2022-01-19", "2022-10-18", "2023-01-20", "2023-04-15"],
        "encumbered_pct_of_promoter": [10.0, 12.0, 30.0, 55.0, 55.0],
        "measure": "pledged or otherwise encumbered"})


def test_point_in_time_never_uses_a_filing_before_its_broadcast():
    rows = pd.DataFrame({"symbol": ["A", "A", "A", "A", "B"],
                         "as_of": pd.to_datetime(["2021-09-30", "2022-10-17", "2022-10-31", "2023-01-31", "2023-01-31"])})
    pit = EU.point_in_time(rows, filings_frame())
    assert np.isnan(pit["enc_pct"].iloc[0])                   # nothing broadcast yet
    assert pit["enc_pct"].iloc[1] == 12.0                     # Sep 2022 quarter broadcast a day later
    assert pit["enc_pct"].iloc[2] == 30.0 and pit["enc_change_4q"].iloc[2] == pytest.approx(20.0)  # vs Sep 2021
    assert pit["enc_pct"].iloc[3] == 55.0 and pit["enc_change_4q"].iloc[3] == pytest.approx(43.0)  # vs Dec 2021
    assert np.isnan(pit["enc_pct"].iloc[4])                   # a stock with no filings
    assert np.isnan(pit["enc_change_4q"].iloc[1])             # Dec 2021 is < 360 days before Dec 2021's... none earlier


def test_rules_at_their_thresholds():
    rules = load_rules()
    df = pd.DataFrame({"enc_pct": [50.0, 49.99, 20.0, 5.0, np.nan, np.nan],
                       "enc_change_4q": [np.nan, 0.0, 10.0, 9.99, np.nan, np.nan],
                       "lower_circuit_days": [0, 0, 0, 0, 3, 2]})
    out = EU.add_rules(df, rules)
    assert out["flag_e1"].tolist()[:4] == [1, 0, 0, 0] and np.isnan(out["flag_e1"].iloc[4])
    assert np.isnan(out["flag_e2"].iloc[0]) and out["flag_e2"].tolist()[1:4] == [0, 1, 0]
    assert out["tier"].tolist() == [HIGH, ELEVATED, ELEVATED, LOW, ELEVATED, LOW]  # 49.99% ≥ 20%: Elevated
    assert out["flag_e3"].tolist() == [1, 1, 1, 0, 1, 0]                            # circuits fire without a filing
    assert out["flag_e3p"].tolist()[:4] == [1, 1, 1, 0] and np.isnan(out["flag_e3p"].iloc[4])


def test_jump_default_needs_an_excess_above_zero():
    assert EU.jump_default(pd.Series({"Excess p a day": 0.0012, "p low (5%)": 0.0003})) == pytest.approx(0.0012)
    assert EU.jump_default(pd.Series({"Excess p a day": 0.0012, "p low (5%)": -0.0001})) == 0.0


def test_download_keeps_the_original_filing_of_each_quarter():
    listing = pd.DataFrame([
        {"symbol": "A", "isin": "X1", "date": "30-SEP-2021", "broadcastDate": "20-OCT-2021 10:00:00", "xbrl": "u1.xml"},
        {"symbol": "A", "isin": "X1", "date": "30-SEP-2021", "broadcastDate": "05-JAN-2022 10:00:00", "xbrl": "u2.xml"},  # revision
        {"symbol": "B", "isin": "X2", "date": "13-JAN-2022", "broadcastDate": "14-JAN-2022 10:00:00", "xbrl": "u3.xml"},  # not a quarter
        {"symbol": "B", "isin": "X2", "date": "30-JUN-2021", "broadcastDate": "14-JUL-2021 10:00:00", "xbrl": "u4.xml"},  # out of range
        {"symbol": "C", "isin": "X3", "date": "31-DEC-2024", "broadcastDate": "21-JAN-2025 10:00:00", "xbrl": "u5.pdf"}])  # no XBRL
    out = FH.original_filings(listing)
    assert out["xbrl"].tolist() == ["u1.xml"]


def test_download_keeps_companies_whose_isin_is_blank_apart():
    """NSE's listing leaves the ISIN blank for some companies (Reliance among them): each keeps its own filing."""
    listing = pd.DataFrame([
        {"symbol": "RELIANCE", "isin": None, "date": "30-SEP-2022", "broadcastDate": "23-OCT-2022 07:10:02", "xbrl": "r.xml"},
        {"symbol": "OTHER", "isin": None, "date": "30-SEP-2022", "broadcastDate": "20-OCT-2022 10:00:00", "xbrl": "o.xml"},
        {"symbol": "RELIANCE", "isin": None, "date": "30-SEP-2022", "broadcastDate": "05-JAN-2023 10:00:00", "xbrl": "r2.xml"}])
    assert sorted(FH.original_filings(listing)["xbrl"]) == ["o.xml", "r.xml"]
