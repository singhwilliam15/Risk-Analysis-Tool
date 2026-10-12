"""The research note (scripts/build_research_note.py) is generated from the results files and cannot drift from them."""

import re
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "scripts"))
import build_research_note as R  # noqa: E402


def test_committed_note_matches_a_fresh_build():
    """Rebuilding from the committed results gives exactly the committed Markdown."""
    assert R.MD.read_text(encoding="utf-8") == R.markdown(R.numbers()), \
        "docs/research_note.md is stale: run python scripts/build_research_note.py"


def test_quoted_lifts_are_the_results():
    md = R.MD.read_text(encoding="utf-8")
    b = pd.read_csv(R.RESULTS / "warnings_v2_bootstrap.csv")
    b = b[b["Universe"] == "all"].set_index("Rule")
    e = pd.read_csv(R.RESULTS / "events_bootstrap.csv")
    e = e[e["Window"].str.startswith("primary") & (e["Universe"] == "all")].set_index("Rule")
    ratio = pd.read_csv(R.RESULTS / "margin_trigger_rate_ratio.csv").iloc[0]
    assert f"**{b.loc['drawdown_30', 'Lift']:.2f} times**" in md
    assert f"lift of {b.loc['r4', 'Lift']:.2f} ({b.loc['r4', 'Lift 5%']:.2f}–{b.loc['r4', 'Lift 95%']:.2f})" in md
    assert f"{e.loc['e1', 'Lift']:.2f} times as often as average (range {e.loc['e1', 'Lift 5%']:.2f}–" in md
    assert f"{ratio['ratio']:.2f}, range {ratio['low']:.2f}–{ratio['high']:.2f}" in md
    assert "2016–2024" in md and "not supported" in md


def test_pdf_is_six_to_eight_pages():
    data = R.pdf(R.MD.read_text(encoding="utf-8"), path=None)
    pages = len(re.findall(rb"/Type\s*/Page[^s]", data))
    assert data[:4] == b"%PDF" and 6 <= pages <= 8, pages
    assert R.PDF.exists() and R.CHART.exists()


@pytest.mark.parametrize("name", ["research_note.md", "research_note.pdf"])
def test_note_is_linked(name):
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert f"docs/{name}" in readme
