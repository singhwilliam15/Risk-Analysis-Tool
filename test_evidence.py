"""
Evidence registry and coverage line (FINAL_PLAN_V6 Phase 3): badges at their boundaries, the registry reproducing the
committed test results, every untested signal listed, and the coverage-line format.
"""

import numpy as np
import pandas as pd
import pytest

import evidence as V
from ui.coverage import coverage_text


def test_badges_at_their_boundaries():
    assert V.badge(2.0, low=1.2, diff_low=0.01) == V.WORKS             # beats momentum
    assert V.badge(2.0, low=1.2, diff_low=0.0) == V.WEAKER             # interval of the difference touches 0
    assert V.badge(1.5, low=1.0001, diff_low=-0.5) == V.WEAKER         # warns, does not beat momentum
    assert V.badge(1.5, low=1.0, diff_low=-0.5) == V.NO_EFFECT         # interval includes 1
    assert V.badge(1.3) == V.WEAKER and V.badge(0.9) == V.NO_EFFECT   # no interval: the point lift decides
    assert V.badge(1.8, low=1.1, benchmark=True) == V.WORKS
    assert V.badge(1.8, low=0.9, benchmark=True) == V.NO_EFFECT
    assert V.badge(np.nan) == V.UNTESTED and V.badge(None) == V.UNTESTED


def test_registry_reproduces_the_committed_results():
    reg = V.registry().set_index("id")
    t = pd.read_csv(V.RESULTS / "warnings_v2_test.csv")
    t = t[(t["Universe"] == "all") & (t["Outcome"] == "observed path")].set_index("Rule")
    e = pd.read_csv(V.RESULTS / "events_bootstrap.csv")
    e = e[e["Window"].str.startswith("primary") & (e["Universe"] == "all")].set_index("Rule")
    for sid in ("r2", "r4", "market", "drawdown_30"):
        assert reg.loc[sid, "lift"] == pytest.approx(t.loc[sid, "Lift"])
    for sid in ("e1", "e2", "e3", "e3p"):
        assert reg.loc[sid, "lift"] == pytest.approx(e.loc[sid, "Lift"])
        assert reg.loc[sid, "low"] == pytest.approx(e.loc[sid, "Lift 5%"])
    assert reg.loc["drawdown_30", "badge"] == V.WORKS
    assert reg.loc["r1", "badge"] == V.NO_EFFECT and reg.loc["e1", "badge"] == V.WEAKER


def test_registry_order_and_untested_signals():
    reg = V.registry()
    order = reg["badge"].map(V.BADGE_ORDER).tolist()
    assert order == sorted(order)                                        # evidence strength first
    assert set(V.UNTESTED_IDS) <= set(reg.loc[reg["badge"] == V.UNTESTED, "id"])
    assert reg["label"].str.contains(r"\(").all()                       # every label carries its technical term


def test_chip_and_texts():
    assert V.chip("e1").startswith(V.WEAKER) and "among stocks not already down 30%" in V.chip("e1")
    assert V.chip("auditor").startswith(V.UNTESTED)
    assert V.lift_text(V.record("liquidity")).endswith("(no range)")


def test_coverage_line_format():
    text = coverage_text(["Promoter pledge", "ASM / GSM"], {"Auditor events": "no permitted source"}, "Pledges 02 Oct 2026")
    assert text == "Checked 2 of 3 items · Not checked: Auditor events (no permitted source) · Data as of Pledges 02 Oct 2026"
    assert coverage_text(["a"], {}) == "Checked 1 of 1 items"
