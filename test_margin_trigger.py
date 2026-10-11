"""Margin-trigger distance (margin_trigger.py): the formula, point-in-time prices and the rate-ratio bootstrap."""

import numpy as np
import pandas as pd
import pytest

import margin_trigger as M


def test_distance_formula():
    # Loan sized at 100 with 2× cover; lenders can sell at 75. At 100 the price must fall 25%; at 75, 0%; at 60, past it
    assert M.distance([100, 100, 100], [100, 75, 60]) == pytest.approx([0.25, 0.0, -0.25])
    assert M.distance(100, 100, 1.75, 1.25) == pytest.approx(1 - 1.25 / 1.75)
    assert np.isnan(M.distance(np.nan, 100)) and np.isnan(M.distance(100, 0))


def test_price_index_follows_adjusted_returns_and_dates_are_point_in_time():
    dates = pd.bdate_range("2024-01-01", periods=5)
    panel = pd.DataFrame({"symbol": "A", "date": dates, "ret": [0.0, 0.10, -0.50, 0.0, 0.20]})
    index = M.price_index(panel)
    assert index["level"].tolist() == pytest.approx([1.0, 1.1, 0.55, 0.55, 0.66])
    # a Saturday takes Friday's level; a date before the first trading day has none
    levels = M.level_on_or_before(index, ["A", "A", "A"], ["2024-01-06", "2023-12-29", "2024-01-03"])
    assert np.isnan(levels[1]) and levels[0] == pytest.approx(0.66) and levels[2] == pytest.approx(0.55)


def test_add_distance_flags_only_encumbered_stocks_close_to_the_trigger():
    dates = pd.bdate_range("2024-01-01", periods=60)
    rets = np.zeros(60)
    rets[30] = -0.20  # a 20% fall after the filing
    panel = pd.concat([pd.DataFrame({"symbol": s, "date": dates, "ret": rets}) for s in ("A", "B", "C")])
    rows = pd.DataFrame({"symbol": ["A", "B", "C"], "as_of": dates[-1], "enc_pct": [60.0, 10.0, np.nan],
                         "enc_disclosed": dates[5]})
    out = M.add_distance(rows, M.price_index(panel))
    # P0 = 1, Pt = 0.8: d = 1 − 0.75 / 0.8 = 6.25% → close to the trigger
    assert out["trigger_dist"].tolist()[:2] == pytest.approx([0.0625, 0.0625])
    assert out["flag_m1"].tolist()[:2] == [1.0, 0.0] and np.isnan(out["flag_m1"].iloc[2])
    assert out["trigger_bin"].iloc[0] == M.BIN_LABELS[0]


def test_rate_ratio_bootstrap_recovers_a_known_ratio():
    rng = np.random.default_rng(0)
    months = pd.date_range("2022-10-31", periods=27, freq="ME")
    rows = []
    for d in months:
        close = rng.random(400) < 0.25
        crash = rng.random(400) < np.where(close, 0.20, 0.05)  # true ratio 4
        rows.append(pd.DataFrame({"as_of": d, "flag_m1": close.astype(float), "event_observed": crash}))
    r = M.rate_ratio_bootstrap(pd.concat(rows), "flag_m1", n_boot=300)
    assert 3.0 < r["ratio"] < 5.5 and r["low"] < r["ratio"] < r["high"] and r["low"] > 1
    assert r["dates"] == 27 and r["n_close"] + r["n_far"] == 27 * 400
