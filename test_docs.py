"""
The README and docs (review P2): no stale status lines, and every local link and image they use exists.
"""

import os
import re

import pytest

ROOT = os.path.dirname(os.path.abspath(__file__))
DOCS = ["README.md", "docs/features.md", "docs/case_studies.md", "docs/methodology.md", "docs/deploy.md",
        "docs/interview_story.md", "docs/preregistration_warnings_v2.md", "docs/preregistration_events.md",
        "docs/data_sources.md", "docs/plans/v6_phase1_manual_checklist.md", "docs/research_note.md",
        "docs/preregistration_margin_trigger.md", "docs/plans/README.md", "docs/plans/v6_adjustments.md",
        "docs/plans/v6_final_checklist.md", "docs/images/README.md"]
STALE = ["is being extended", "Market risk** is complete", "Market risk is complete", "Coming next (Phase 6)",
         "434 tests", "434 offline tests", "measures those links", "until the Phase 7 case studies",
         "banks are not modelled beyond the manual panel",
         "cannot be calibrated on disclosure data"]


def _read(path):
    with open(os.path.join(ROOT, path), encoding="utf-8") as f:
        return f.read()


@pytest.mark.parametrize("path", DOCS)
def test_no_stale_lines(path):
    text = _read(path)
    found = [phrase for phrase in STALE if phrase in text]
    assert not found, f"{path}: {found}"


@pytest.mark.parametrize("path", DOCS)
def test_local_links_and_images_exist(path):
    base = os.path.dirname(os.path.join(ROOT, path))
    for target in re.findall(r"\]\(([^)\s]+)\)", _read(path)):
        if target.startswith(("http://", "https://", "#", "mailto:")):
            continue
        local = target.split("#")[0]
        assert os.path.exists(os.path.normpath(os.path.join(base, local))), f"{path}: broken link {target}"


def test_readme_is_one_screen_plus_a_little():
    assert len(_read("README.md").splitlines()) < 150


# ---------------------------------------------------------------
# Numbers that must not go stale (Phase H)
# ---------------------------------------------------------------

def collected_tests() -> int:
    """How many tests pytest collects in this repository, from a separate collection run."""
    import subprocess
    import sys
    out = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider"],
                         cwd=ROOT, capture_output=True, text=True, timeout=600).stdout
    return int(re.search(r"(\d+) tests? collected", out).group(1))


def test_stated_test_count_is_the_real_one():
    n = collected_tests()
    assert f"There are {n} tests" in _read("README.md"), f"README should say 'There are {n} tests'"
    assert f"with {n} offline tests" in _read("docs/interview_story.md"), f"interview story should say {n}"


def _results(name):
    import pandas as pd
    return pd.read_csv(os.path.join(ROOT, "case_studies", "results", name))


def test_readme_findings_match_the_results_files():
    import json
    readme = " ".join(_read("README.md").split())  # line wrapping does not matter
    expected = []
    tally = _results("tally.csv").set_index("Pillar")
    any_, ma = tally.loc["any"], tally.loc["below_200dma"]
    expected += [f"warned on {int(any_['Hits'])} of {int(any_['Case dates'])} dates",
                 f"false alarms on {any_['False-positive rate']:.1%} of {int(any_['Control dates'])} control dates",
                 f"also warned on {int(ma['Hits'])}", f"{ma['False-positive rate']:.0%} false alarms"]
    meta = json.loads(_read("case_studies/results/universe_meta.json"))
    m = _results("universe_metrics.csv")
    m = m[(m["Universe"] == "all") & (m["Outcome"] == "observed path")].set_index("Rule")
    expected += [f"On {meta['symbols_evaluated']:,} stocks", f"their lift is {m.loc['tool', 'Lift']:.2f}",
                 f"does twice as well ({m.loc['drawdown_30', 'Lift']:.2f})", f"fires on {m.loc['market', 'Flag rate']:.0%} of all NSE"]
    t = _results("warnings_v2_test.csv")
    t = t[(t["Universe"] == "all") & (t["Outcome"] == "observed path")].set_index("Rule")
    b = _results("warnings_v2_bootstrap.csv")
    b = b[b["Universe"] == "all"].set_index("Rule")
    expected += [f"lift of {t.loc['r4', 'Lift']:.2f} against momentum's {t.loc['drawdown_30', 'Lift']:.2f}",
                 f"({b.loc['r4', 'Difference 5%']:.2f} to +{b.loc['r4', 'Difference 95%']:.2f})".replace("-", "−"),
                 f"crashed {b.loc['drawdown_30', 'Lift']:.2f} times as often as average out of sample, 2020–24 "
                 f"(90% range {b.loc['drawdown_30', 'Lift 5%']:.2f}–{b.loc['drawdown_30', 'Lift 95%']:.2f})"]
    decision = json.loads(_read("case_studies/results/events_decision.json"))
    e = _results("events_bootstrap.csv")
    e = e[e["Window"].str.startswith("primary") & (e["Universe"] == "all")].set_index("Rule")
    inc = _results("events_incremental_bootstrap.csv")
    inc = inc[inc["Window"].str.startswith("primary") & (inc["Universe"] == "all")].set_index("Rule")
    expected += [f"{decision['coverage']['filings']:,} NSE shareholding filings",
                 f"{e.loc['e1', 'Lift']:.1f} times as often as average (90% range {e.loc['e1', 'Lift 5%']:.1f}–{e.loc['e1', 'Lift 95%']:.1f})",
                 f"which had a lift of {e.loc['drawdown_30', 'Lift']:.1f}", f"the lift stays at {inc.loc['e1', 'Lift']:.1f}"]
    ratio = _results("margin_trigger_rate_ratio.csv").iloc[0]
    expected += [f"crash-rate ratio {ratio['ratio']:.2f} (90% range {ratio['low']:.2f}–{ratio['high']:.2f})"]
    missing = [x for x in expected if x not in readme]
    assert not missing, missing


def test_interview_story_numbers_match_the_results():
    import json
    story = " ".join(_read("docs/interview_story.md").split())
    b = _results("warnings_v2_bootstrap.csv")
    b = b[b["Universe"] == "all"].set_index("Rule")
    e = _results("events_bootstrap.csv")
    e = e[e["Window"].str.startswith("primary") & (e["Universe"] == "all")].set_index("Rule")
    filings = json.loads(_read("case_studies/results/events_decision.json"))["coverage"]["filings"]
    margin = json.loads(_read("case_studies/results/margin_trigger_decision.json"))
    expected = [f"crashed {b.loc['drawdown_30', 'Lift']:.2f} times as often as average",
                f"The best scored {b.loc['r4', 'Lift']:.2f}", f"tested on {filings:,} shareholding filings",
                f"warn at {e.loc['e1', 'Lift']:.1f} times average"]
    missing = [x for x in expected if x not in story]
    assert not missing, missing
    assert not margin["close_adds_beyond_encumbrance"] and "was not supported" in story
