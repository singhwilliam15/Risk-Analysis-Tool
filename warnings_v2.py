"""
Early-warning rules v2 (NEXT_STEPS_V5 Phase F), tested out of sample on every NSE stock under a pre-registration
(docs/preregistration_warnings_v2.md). Pure functions: the wider test (universe.py, scripts/run_universe.py) supplies
the rows; nothing here reads files.

Candidate rules, from prices up to the as-of date only:
- R1 own-history ES: today's historical ES95 ≥ the 90th percentile of the stock's own daily ES95 over the previous
  756 trading days (at least 500 values);
- R2 peer-relative ES: ES95 ≥ the 90th percentile of its liquidity tercile on that date;
- R3 volatility shock with trend: EWMA volatility ≥ 1.5 × one-year volatility AND close below its 200-day average;
- R4 combined score: a logistic regression fitted on design-period rows only, flagging scores at or above the
  design-period 90th percentile.
"""

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view

ES_WINDOW, ES_MIN_ROWS = 500, 250      # as v1 (case_studies.engine.LOOKBACK_DAYS; the wider test needs 250 rows)
ALPHA = 0.05
R1_HISTORY, R1_MIN = 756, 500          # previous 3 years of daily ES values, at least 500 of them
PCT = 0.90
R3_RATIO = 1.5
DESIGN = ("2016-01-01", "2018-12-31")
EMBARGO = ("2019-01-01", "2019-12-31")
TEST = ("2020-01-01", "2024-12-31")
R4_FEATURES = ("r1_pct", "r2_pct", "ret_6m", "dist_200dma", "circuit_60", "stress_loss", "log_value60")
CANDIDATES = ("r1", "r2", "r3", "r4")
LABELS = {"r1": "R1 own-history ES (top decile of own 3 years)", "r2": "R2 peer-relative ES (top decile of liquidity tercile)",
          "r3": "R3 volatility shock with trend", "r4": "R4 combined logistic score",
          "tool": "v1 any price flag", "market": "v1 market flag", "drawdown_30": "(a) down ≥ 30% in 6 months",
          "vol_top_decile": "(b) volatility in own top decile", "below_200dma": "(c) below 200-day average"}
FLAG_RATE_BAND = (0.05, 0.25)          # the challenger's design flag rate must lie in this band
BLOCK_MONTHS, N_BOOT = 12, 2000


# ---------------------------------------------------------------
# Per-stock features (time series)
# ---------------------------------------------------------------

def _es(sample: np.ndarray) -> float:
    """var_calculator._empirical_var_es's ES: mean loss at or beyond the empirical 5% quantile (linear interpolation)."""
    cutoff = np.percentile(sample, ALPHA * 100)
    tail = sample[sample <= cutoff]
    return float(-tail.mean()) if len(tail) else float(-cutoff)


def daily_es_series(returns) -> np.ndarray:
    """
    Historical ES95 on each row: the returns of the last min(500, i+1) rows up to and including row i, NaNs dropped,
    as case_studies.engine.price_flags computes it on its 500-row window. NaN before 250 rows.
    """
    r = np.asarray(returns, dtype=float)
    n = len(r)
    out = np.full(n, np.nan)
    if n >= ES_WINDOW:
        windows = sliding_window_view(r, ES_WINDOW)  # row j covers rows j .. j+499, i.e. ends at row j+499
        clean = ~np.isnan(windows).any(axis=1)
        if clean.any():
            w = windows[clean]
            cutoff = np.percentile(w, ALPHA * 100, axis=1)
            mask = w <= cutoff[:, None]
            out[np.flatnonzero(clean) + ES_WINDOW - 1] = -(np.where(mask, w, 0).sum(axis=1) / mask.sum(axis=1))
        todo = [j + ES_WINDOW - 1 for j in np.flatnonzero(~clean)]
    else:
        todo = []
    todo = list(range(ES_MIN_ROWS - 1, min(n, ES_WINDOW - 1))) + todo
    for i in todo:
        sample = r[max(0, i - ES_WINDOW + 1):i + 1]
        sample = sample[~np.isnan(sample)]
        if len(sample):
            out[i] = _es(sample)
    return out


def r1_at(es: np.ndarray, i: int) -> tuple:
    """(percentile rank of today's ES among the previous 756 values, R1 flag); (NaN, NaN) without 500 prior values."""
    today = es[i] if 0 <= i < len(es) else np.nan
    prior = es[max(0, i - R1_HISTORY):max(0, i)]
    prior = prior[~np.isnan(prior)]
    if not np.isfinite(today) or len(prior) < R1_MIN:
        return np.nan, np.nan
    rank = float((prior < today).mean() + 0.5 * (prior == today).mean())
    return rank, float(today >= np.percentile(prior, PCT * 100))


def stock_features(frame: pd.DataFrame, i: int, es: np.ndarray, band) -> dict:
    """Features of one stock on row i of its (adjusted) frame, from rows 0..i only. `band` is the circuit band (or NaN)."""
    close = frame["Close"].to_numpy(dtype=float)
    r1_pct, r1 = r1_at(es, i)
    ma200 = close[i - 199:i + 1].mean() if i >= 199 else np.nan
    value = frame["value"].to_numpy(dtype=float)[max(0, i - 59):i + 1]
    circuit_60 = np.nan
    if band is not None and np.isfinite(band):
        from liquidity import lower_circuit_days
        circuit_60 = float(lower_circuit_days(frame.iloc[max(0, i - 59):i + 1], band).sum())
    elif band is not None:
        circuit_60 = 0.0  # no fixed band found: no circuit days (as liquidity.circuit_lock reports)
    med = np.nanmedian(value) if np.isfinite(value).any() else np.nan
    return {"es_today": es[i], "r1_pct": r1_pct, "flag_r1": r1,
            "ret_6m": close[i] / close[i - 126] - 1 if i >= 126 else np.nan,
            "dist_200dma": close[i] / ma200 - 1 if np.isfinite(ma200) else np.nan,
            "circuit_60": circuit_60, "log_value60": float(np.log(med)) if np.isfinite(med) and med > 0 else np.nan}


# ---------------------------------------------------------------
# Cross-sectional rules
# ---------------------------------------------------------------

def add_cross_sectional(df: pd.DataFrame) -> pd.DataFrame:
    """
    Per as-of date: liquidity tercile (of log median 60-day traded value, across all stocks with a value that day),
    r2_pct = percentile rank of es_today within the tercile, flag_r2 = es_today ≥ the tercile's 90th percentile.
    """
    df = df.copy()
    df["liq_bucket"], df["r2_pct"], df["flag_r2"] = np.nan, np.nan, np.nan
    for _, idx in df.groupby("as_of").groups.items():
        part = df.loc[idx]
        ok = part["log_value60"].notna() & part["es_today"].notna()
        if ok.sum() < 3:
            continue
        buckets = pd.qcut(part.loc[ok, "log_value60"].rank(method="first"), 3, labels=False)
        df.loc[buckets.index, "liq_bucket"] = buckets
        for b in range(3):
            members = buckets.index[buckets == b]
            es = df.loc[members, "es_today"]
            df.loc[members, "r2_pct"] = es.rank(pct=True, method="average")
            df.loc[members, "flag_r2"] = (es >= np.percentile(es, PCT * 100)).astype(float)
    return df


def add_r3(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    ok = df["ewma_vol_ratio"].notna() & df["dist_200dma"].notna()
    df["flag_r3"] = np.where(ok, ((df["ewma_vol_ratio"] >= R3_RATIO) & (df["dist_200dma"] < 0)).astype(float), np.nan)
    return df


# ---------------------------------------------------------------
# R4: logistic regression fitted on design rows only
# ---------------------------------------------------------------

def in_period(dates, period) -> np.ndarray:
    d = pd.to_datetime(pd.Series(dates))
    return ((d >= pd.Timestamp(period[0])) & (d <= pd.Timestamp(period[1]))).to_numpy()


def fit_logistic(X: np.ndarray, y: np.ndarray, ridge: float = 1e-6, iters: int = 50) -> np.ndarray:
    """Newton–Raphson (IRLS) for P(y=1) = 1/(1+exp(−[1, X]·β)); a tiny ridge keeps the Hessian invertible."""
    A = np.column_stack([np.ones(len(X)), X])
    beta = np.zeros(A.shape[1])
    for _ in range(iters):
        p = 1 / (1 + np.exp(-np.clip(A @ beta, -35, 35)))
        grad = A.T @ (y - p) - ridge * beta
        hess = (A * (p * (1 - p))[:, None]).T @ A + ridge * np.eye(A.shape[1])
        step = np.linalg.solve(hess, grad)
        beta += step
        if np.abs(step).max() < 1e-10:
            break
    return beta


def fit_r4(design: pd.DataFrame, outcome: str = "event_observed") -> dict:
    """The frozen R4 model: standardisation moments, coefficients and the threshold, from design-period rows only."""
    if not in_period(design["as_of"], DESIGN).all():
        raise ValueError("R4 must be fitted on design-period rows only (2016-01-01 to 2018-12-31)")
    rows = design.dropna(subset=list(R4_FEATURES) + ["worst_12m"])
    X = rows[list(R4_FEATURES)].to_numpy(dtype=float)
    mean, sd = X.mean(axis=0), X.std(axis=0, ddof=0)
    sd[sd == 0] = 1.0
    beta = fit_logistic((X - mean) / sd, rows[outcome].to_numpy(dtype=float))
    model = {"features": list(R4_FEATURES), "mean": mean.tolist(), "sd": sd.tolist(), "beta": beta.tolist(),
             "rows": int(len(rows)), "first_date": str(rows["as_of"].min().date()), "last_date": str(rows["as_of"].max().date())}
    model["threshold"] = float(np.percentile(score(rows, model), PCT * 100))
    return model


def score(df: pd.DataFrame, model: dict) -> np.ndarray:
    """Logistic score (probability); NaN where any feature is missing."""
    X = df[model["features"]].to_numpy(dtype=float)
    z = (X - np.array(model["mean"])) / np.array(model["sd"])
    p = 1 / (1 + np.exp(-np.clip(model["beta"][0] + z @ np.array(model["beta"][1:]), -35, 35)))
    p[np.isnan(X).any(axis=1)] = np.nan
    return p


def add_r4(df: pd.DataFrame, model: dict) -> pd.DataFrame:
    df = df.copy()
    df["r4_score"] = score(df, model)
    df["flag_r4"] = np.where(df["r4_score"].notna(), (df["r4_score"] >= model["threshold"]).astype(float), np.nan)
    return df


# ---------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------

def metrics(df: pd.DataFrame, rule: str, outcome: str = "event_observed") -> dict:
    """Precision, recall, lift, flag rate, availability and mean lead time (as-of to trough, true positives)."""
    data = df.dropna(subset=["worst_12m"]) if outcome == "event_observed" else df
    y = data[outcome].astype(bool)
    raw = data[f"flag_{rule}"]
    flag = raw.fillna(0).astype(bool)  # unavailable counts as not flagged
    tp = int((flag & y).sum())
    n_flag, n_ev = int(flag.sum()), int(y.sum())
    base = n_ev / len(data) if len(data) else np.nan
    precision = tp / n_flag if n_flag else np.nan
    lead = data.loc[flag & y, "trough_days"] if "trough_days" in data else pd.Series(dtype=float)
    return {"Rule": rule, "Label": LABELS.get(rule, rule), "Stock-dates": len(data),
            "Available": float(raw.notna().mean()) if len(data) else np.nan, "Flagged": n_flag,
            "Flag rate": n_flag / len(data) if len(data) else np.nan, "Events": n_ev, "Base rate": base,
            "Precision": precision, "Recall": tp / n_ev if n_ev else np.nan,
            "Lift": precision / base if base and n_flag else np.nan,
            "Mean lead time to trough (trading days)": float(lead.mean()) if len(lead) else np.nan}


def table(df: pd.DataFrame, rules, outcome: str = "event_observed") -> pd.DataFrame:
    return pd.DataFrame([metrics(df, r, outcome) for r in rules])


def incremental(df: pd.DataFrame, rules, outcome: str = "event_observed") -> pd.DataFrame:
    """Each rule's metrics among stock-dates NOT flagged by baseline (a): what it adds beyond 'it has already fallen'."""
    rest = df[~df["flag_drawdown_30"].fillna(False).astype(bool)]
    return table(rest, rules, outcome)


def choose_challenger(design_table: pd.DataFrame) -> str:
    """The R1–R4 rule with the highest design lift among those whose design flag rate lies in FLAG_RATE_BAND."""
    t = design_table[design_table["Rule"].isin(CANDIDATES)]
    t = t[(t["Flag rate"] >= FLAG_RATE_BAND[0]) & (t["Flag rate"] <= FLAG_RATE_BAND[1]) & t["Lift"].notna()]
    if t.empty:
        return None
    return str(t.sort_values("Lift", ascending=False)["Rule"].iloc[0])


# ---------------------------------------------------------------
# Block bootstrap over consecutive month-ends (paired across rules)
# ---------------------------------------------------------------

def per_date_counts(df: pd.DataFrame, rules, outcome: str = "event_observed") -> tuple:
    """(dates, n, events, {rule: (flagged, true positives)}) summed per as-of date, in date order."""
    data = df.dropna(subset=["worst_12m"]) if outcome == "event_observed" else df
    data = data.sort_values("as_of")
    g = data.groupby("as_of")
    y = data[outcome].astype(bool)
    n = g.size().to_numpy(dtype=float)
    ev = y.groupby(data["as_of"]).sum().to_numpy(dtype=float)
    counts = {}
    for r in rules:
        f = data[f"flag_{r}"].fillna(0).astype(bool)
        counts[r] = (f.groupby(data["as_of"]).sum().to_numpy(dtype=float),
                     (f & y).groupby(data["as_of"]).sum().to_numpy(dtype=float))
    return g.size().index, n, ev, counts


def block_indices(n_dates: int, block: int, rng) -> np.ndarray:
    """Circular moving blocks of `block` consecutive dates, concatenated to n_dates."""
    starts = rng.integers(0, n_dates, int(np.ceil(n_dates / block)))
    return (starts[:, None] + np.arange(block)[None, :]).ravel()[:n_dates] % n_dates


def block_bootstrap(n, ev, counts: dict, reference: str = "drawdown_30", block: int = BLOCK_MONTHS,
                    n_boot: int = N_BOOT, seed: int = 11) -> pd.DataFrame:
    """90% percentile intervals for each rule's lift and for lift − lift(reference), on the same resamples."""
    rng = np.random.default_rng(seed)
    T = len(n)
    lifts = {r: np.empty(n_boot) for r in counts}
    for b in range(n_boot):
        idx = block_indices(T, block, rng)
        N, E = n[idx].sum(), ev[idx].sum()
        for r, (fl, tp) in counts.items():
            F = fl[idx].sum()
            lifts[r][b] = (tp[idx].sum() / F) / (E / N) if F and E else np.nan
    rows = []
    for r in counts:
        F, TP = counts[r][0].sum(), counts[r][1].sum()
        point = (TP / F) / (ev.sum() / n.sum()) if F and ev.sum() else np.nan
        ref_point = (counts[reference][1].sum() / counts[reference][0].sum()) / (ev.sum() / n.sum())
        diff = lifts[r] - lifts[reference]
        rows.append({"Rule": r, "Label": LABELS.get(r, r), "Lift": point,
                     "Lift 5%": float(np.nanpercentile(lifts[r], 5)), "Lift 95%": float(np.nanpercentile(lifts[r], 95)),
                     f"Lift − lift({reference})": point - ref_point,
                     "Difference 5%": float(np.nanpercentile(diff, 5)), "Difference 95%": float(np.nanpercentile(diff, 95))})
    return pd.DataFrame(rows)


def decide(test_table: pd.DataFrame, boot: pd.DataFrame, challenger: str) -> dict:
    """
    The pre-registered decision: the challenger replaces v1 only if its test lift beats v1 (any price flag and the
    market flag) and baseline (a), and the 90% interval of lift − lift(a) lies above zero.
    """
    lift = test_table.set_index("Rule")["Lift"]
    b = boot.set_index("Rule")
    if challenger is None:
        return {"challenger": None, "wins": False, "reason": "no rule met the design flag-rate band"}
    checks = {"beats v1 any price flag": bool(lift[challenger] > lift["tool"]),
              "beats v1 market flag": bool(lift[challenger] > lift["market"]),
              "beats (a) down ≥ 30%": bool(lift[challenger] > lift["drawdown_30"]),
              "90% CI of lift − lift(a) above zero": bool(b.loc[challenger, "Difference 5%"] > 0)}
    return {"challenger": challenger, "wins": all(checks.values()), "checks": checks}
