"""
Warnings v2 (Phase F, warnings_v2.py): each rule on synthetic data with known answers, no look-ahead, the logistic
model fitted on design rows only, and the block bootstrap's coverage of a known lift.
"""

import numpy as np
import pandas as pd
import pytest

import warnings_v2 as W
from var_calculator import calculate_historical_var


def returns_series(n=900, seed=1, vol=0.01):
    r = np.random.default_rng(seed).standard_t(4, n) * vol
    r[0] = np.nan  # the first row has no return, as in the price frames
    return r


def test_daily_es_matches_the_tools_historical_es_on_each_window():
    r = returns_series()
    es = W.daily_es_series(r)
    assert np.isnan(es[:249]).all()  # fewer than 250 rows
    for i in (249, 250, 400, 498, 499, 500, 650, 899):
        window = pd.Series(r[max(0, i - 499):i + 1]).dropna()
        assert es[i] == pytest.approx(calculate_historical_var(window, 1.0, 0.95, 1)["cvar_daily_pct"], rel=1e-12)


def test_daily_es_handles_a_gap_inside_a_window():
    r = returns_series(700, seed=2)
    r[600] = np.nan
    es = W.daily_es_series(r)
    window = pd.Series(r[650 - 499:651]).dropna()
    assert es[650] == pytest.approx(calculate_historical_var(window, 1.0, 0.95, 1)["cvar_daily_pct"], rel=1e-12)


def test_r1_against_hand_built_histories():
    es = np.concatenate([np.linspace(0.02, 0.03, 700), [0.05]])
    rank, flag = W.r1_at(es, 700)
    assert flag == 1.0 and rank == 1.0
    es[-1] = 0.021
    rank, flag = W.r1_at(es, 700)
    assert flag == 0.0 and rank == pytest.approx(0.10)  # 70 of the 700 prior values lie below 0.021
    assert np.isnan(W.r1_at(np.full(400, 0.02), 399)[1])  # fewer than 500 prior values
    # only the previous 756 values count: an old spike beyond them is ignored
    es = np.concatenate([[0.5] * 100, np.full(756, 0.02), [0.03]])
    assert W.r1_at(es, len(es) - 1)[1] == 1.0


def test_r1_fires_after_a_planted_volatility_burst():
    r = returns_series(2000, seed=3, vol=0.01)
    r[-60:] = np.random.default_rng(4).standard_t(4, 60) * 0.05
    es = W.daily_es_series(r)
    assert W.r1_at(es, len(r) - 1)[1] == 1.0


def frame(n=1200, seed=5):
    rng = np.random.default_rng(seed)
    close = 100 * np.cumprod(1 + rng.normal(0, 0.01, n))
    df = pd.DataFrame({"Date": pd.bdate_range("2015-01-01", periods=n), "Close": close, "Low": close * 0.99,
                       "High": close * 1.01, "value": rng.lognormal(16, 0.3, n)})
    df["Returns"] = df["Close"].pct_change()
    return df


def test_features_use_no_data_after_the_as_of_row():
    df = frame()
    i = 900
    es = W.daily_es_series(df["Returns"])
    before = W.stock_features(df, i, es, 0.05)
    later = df.copy()
    later.loc[i + 1:, ["Close", "Low", "High", "value"]] *= 3.0  # rewrite the future
    later["Returns"] = later["Close"].pct_change()
    after = W.stock_features(later, i, W.daily_es_series(later["Returns"]), 0.05)
    for k, v in before.items():
        assert (np.isnan(v) and np.isnan(after[k])) or v == pytest.approx(after[k]), k


def test_simple_features_by_hand():
    df = frame()
    i = 700
    f = W.stock_features(df, i, W.daily_es_series(df["Returns"]), np.nan)
    c = df["Close"].to_numpy()
    assert f["ret_6m"] == pytest.approx(c[i] / c[i - 126] - 1)
    assert f["dist_200dma"] == pytest.approx(c[i] / c[i - 199:i + 1].mean() - 1)
    assert f["log_value60"] == pytest.approx(np.log(np.median(df["value"].to_numpy()[i - 59:i + 1])))
    assert f["circuit_60"] == 0.0  # no band found: no circuit days


def test_circuit_60_counts_planted_lower_circuits_in_the_last_60_days():
    df = frame()
    for j in (650, 680, 695):  # three 5% lower circuits closing at the low
        df.loc[j, "Close"] = df.loc[j - 1, "Close"] * 0.95
        df.loc[j, "Low"] = df.loc[j, "Close"]
    df.loc[500, "Close"] = df.loc[499, "Close"] * 0.95  # one more, outside the 60-day window
    df.loc[500, "Low"] = df.loc[500, "Close"]
    df["Returns"] = df["Close"].pct_change()
    assert W.stock_features(df, 700, W.daily_es_series(df["Returns"]), 0.05)["circuit_60"] == 3.0


def test_r2_buckets_and_percentiles_by_hand():
    df = pd.DataFrame({"as_of": pd.Timestamp("2020-01-31"), "log_value60": [1, 2, 3, 4, 5, 6],
                       "es_today": [0.05, 0.02, 0.01, 0.03, 0.04, 0.04]})
    out = W.add_cross_sectional(df)
    assert out["liq_bucket"].tolist() == [0, 0, 1, 1, 2, 2]
    # within each pair the 90th percentile is close to the larger value: only the larger (or a tie) is flagged
    assert out["flag_r2"].tolist() == [1, 0, 0, 1, 1, 1]
    assert out["r2_pct"].tolist() == [1.0, 0.5, 0.5, 1.0, 0.75, 0.75]


def test_r3_needs_both_the_volatility_shock_and_the_downtrend():
    df = pd.DataFrame({"ewma_vol_ratio": [1.6, 1.6, 1.2, 1.2, np.nan], "dist_200dma": [-0.1, 0.1, -0.1, 0.1, -0.1]})
    assert W.add_r3(df)["flag_r3"].tolist()[:4] == [1, 0, 0, 0]
    assert np.isnan(W.add_r3(df)["flag_r3"].iloc[4])


def test_logistic_recovers_known_coefficients():
    rng = np.random.default_rng(6)
    X = rng.normal(size=(40000, 2))
    true = np.array([-2.0, 1.0, -0.5])
    p = 1 / (1 + np.exp(-(true[0] + X @ true[1:])))
    beta = W.fit_logistic(X, (rng.random(40000) < p).astype(float))
    assert np.allclose(beta, true, atol=0.06)


def design_rows(n=3000, seed=7, start="2016-01-31"):
    rng = np.random.default_rng(seed)
    dates = pd.date_range(start, periods=36, freq="ME")
    df = pd.DataFrame({f: rng.normal(size=n) for f in W.R4_FEATURES})
    df["as_of"] = dates[rng.integers(0, len(dates), n)]
    z = -2 + 1.2 * df["ret_6m"] * -1
    df["event_observed"] = rng.random(n) < 1 / (1 + np.exp(-z))
    df["worst_12m"] = -0.1
    return df


def test_r4_is_fitted_on_design_rows_only_and_flags_a_tenth():
    df = design_rows()
    model = W.fit_r4(df)
    assert model["first_date"] >= "2016-01-01" and model["last_date"] <= "2018-12-31"
    flagged = W.add_r4(df, model)["flag_r4"]
    assert flagged.mean() == pytest.approx(0.10, abs=0.005)
    assert model["beta"][1 + W.R4_FEATURES.index("ret_6m")] < -0.5  # the planted signal
    with pytest.raises(ValueError, match="design-period rows only"):
        W.fit_r4(pd.concat([df, design_rows(10, start="2020-01-31")]))


def test_r4_is_missing_when_a_feature_is_missing():
    df = design_rows()
    model = W.fit_r4(df)
    df.loc[0, "r1_pct"] = np.nan
    assert np.isnan(W.add_r4(df, model)["flag_r4"].iloc[0])


def test_metrics_incremental_and_unavailable_by_hand():
    df = pd.DataFrame({"worst_12m": -0.1, "event_observed": [1, 1, 0, 0, 0, 0, 1, 0],
                       "flag_x": [1, 0, 1, np.nan, 0, 0, 1, 0], "flag_drawdown_30": [1, 0, 0, 0, 0, 0, 0, 0],
                       "trough_days": [10, 20, 30, 40, 50, 60, 70, 80]}).astype({"event_observed": bool})
    m = W.metrics(df, "x")
    assert m["Flagged"] == 3 and m["Precision"] == pytest.approx(2 / 3) and m["Recall"] == pytest.approx(2 / 3)
    assert m["Lift"] == pytest.approx((2 / 3) / (3 / 8)) and m["Available"] == pytest.approx(7 / 8)
    assert m["Mean lead time to trough (trading days)"] == pytest.approx(40)  # true positives at 10 and 70
    inc = W.incremental(df, ["x"]).iloc[0]  # drop row 0 (flagged by (a)): 7 rows, 2 events, flags at rows 2 and 6
    assert inc["Stock-dates"] == 7 and inc["Precision"] == pytest.approx(0.5) and inc["Lift"] == pytest.approx(0.5 / (2 / 7))


def test_challenger_is_the_best_design_lift_inside_the_flag_rate_band():
    t = pd.DataFrame({"Rule": ["r1", "r2", "r3", "r4", "drawdown_30"], "Flag rate": [0.10, 0.02, 0.12, 0.30, 0.1],
                      "Lift": [1.5, 5.0, 1.8, 3.0, 9.0]})
    assert W.choose_challenger(t) == "r3"
    assert W.choose_challenger(t.assign(**{"Flag rate": 0.5})) is None


def test_decision_rule():
    t = pd.DataFrame({"Rule": ["r1", "tool", "market", "drawdown_30"], "Lift": [2.5, 1.1, 1.1, 2.2]})
    b = pd.DataFrame({"Rule": ["r1"], "Difference 5%": [0.05]})
    assert W.decide(t, b, "r1")["wins"]
    assert not W.decide(t, b.assign(**{"Difference 5%": -0.01}), "r1")["wins"]
    assert not W.decide(t.assign(Lift=[2.0, 1.1, 1.1, 2.2]), b, "r1")["wins"]
    assert not W.decide(t, b, None)["wins"]


def test_block_indices_are_consecutive_and_wrap():
    idx = W.block_indices(60, 12, np.random.default_rng(0))
    assert len(idx) == 60 and idx.max() < 60
    for block in idx.reshape(5, 12):
        assert ((np.diff(block) % 60) == 1).all()


def test_block_bootstrap_covers_a_known_lift():
    """Flags independent of the date; P(event | flag) = 2 × P(event | no flag) on every date, so the true lift is
    2 / (0.1·2 + 0.9) = 1.818 whatever the date's base rate. Base rates follow a persistent AR(1) across dates."""
    true = 2 / 1.1
    rng = np.random.default_rng(8)
    covered, sims = 0, 200
    for _ in range(sims):
        T, N = 60, 150
        logit = np.empty(T)
        logit[0] = rng.normal(-2.5, 0.6)
        for t in range(1, T):
            logit[t] = -2.5 + 0.9 * (logit[t - 1] + 2.5) + rng.normal(0, 0.26)
        b = 1 / (1 + np.exp(-logit))
        flags = rng.random((T, N)) < 0.10
        events = rng.random((T, N)) < np.where(flags, 2 * b[:, None], b[:, None])
        n, ev = np.full(T, float(N)), events.sum(axis=1).astype(float)
        counts = {"x": (flags.sum(axis=1).astype(float), (flags & events).sum(axis=1).astype(float)),
                  "drawdown_30": (np.full(T, float(N)), ev)}  # a reference that flags everything (lift 1)
        out = W.block_bootstrap(n, ev, counts, n_boot=300, seed=int(rng.integers(1e9))).set_index("Rule")
        covered += out.loc["x", "Lift 5%"] <= true <= out.loc["x", "Lift 95%"]
    assert 0.80 <= covered / sims <= 0.97
