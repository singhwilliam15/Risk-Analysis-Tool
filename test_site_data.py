"""Website data (site_data/build.py): JSON as the app renders it, valid, chart files split out, no NSE lists, stale kept."""

import json

import pytest

from site_data import build as B
from site_data.schema import errors

PAGES = ["market", "promoter-pledge-governance"]


@pytest.fixture
def built(fake_market, tmp_path):
    status = B.build(tmp_path, presets=["aapl"], pages=PAGES)
    return tmp_path, status


def test_pages_are_valid_and_carry_the_app_summary(built):
    out, status = built
    assert status == {"aapl": "ok"}
    for page in PAGES:
        d = json.loads((out / "aapl" / f"{page}.json").read_text(encoding="utf-8"))
        assert errors(d, "page") == []
        assert d["summary"]["status"] in ("Clear", "Watch", "Warning") and d["summary"]["verdict"]
        assert d["app_link"].endswith(f"?page={page}")
    market = json.loads((out / "aapl" / "market.json").read_text(encoding="utf-8"))
    assert market["summary"]["question"] == "How much could this lose on a bad day?"
    assert any(i["type"] == "table" for s in market["sections"] for i in s["items"])
    for kind in ("presets", "evidence", "glossary"):
        assert errors(json.loads((out / f"{kind}.json").read_text(encoding="utf-8")), kind) == []
    assert (out / "docs" / "methodology.md").exists()


def test_charts_are_split_into_their_own_files(built):
    out, _ = built
    market = json.loads((out / "aapl" / "market.json").read_text(encoding="utf-8"))
    charts = [i for s in market["sections"] for i in s["items"] if i["type"] == "chart"]
    assert charts and all(set(c) == {"type", "src"} for c in charts)
    for c in charts:
        fig = json.loads((out / c["src"]).read_text(encoding="utf-8"))
        assert "data" in fig and "layout" in fig and "template" not in fig["layout"]


def test_no_nse_lists_are_written(built):
    out, _ = built
    text = " ".join(f.read_text(encoding="utf-8") for f in out.rglob("*.json"))
    assert "nsearchives" not in text and "pledged_pct_of_promoter" not in text
    pledge = json.loads((out / "aapl" / "promoter-pledge-governance.json").read_text(encoding="utf-8"))
    assert pledge["summary"]["verdict"] == "not checked: no pledge files are loaded."


def test_a_failed_preset_keeps_its_last_good_data(built, monkeypatch):
    out, _ = built

    def fail(slug, pages=None):
        raise RuntimeError("Yahoo Finance did not answer")
    monkeypatch.setattr(B, "run_preset", fail)
    status = B.build(out, presets=["aapl"], pages=PAGES)
    assert status["aapl"].startswith("stale (2 files kept)")
    d = json.loads((out / "aapl" / "market.json").read_text(encoding="utf-8"))
    assert d["stale"] is True and "Yahoo" in d["stale_reason"]
    assert json.loads((out / "presets.json").read_text(encoding="utf-8"))[0]["stale"] is True


def test_schema_rejects_bad_pages():
    assert errors({"preset": "x"}, "page")
    page = {"preset": "a", "preset_label": "A", "page": "p", "title": "T", "app_link": "u", "data_note": "", "built": "d",
            "stale": False, "sections": [{"title": "", "items": [{"type": "video"}]}],
            "summary": {"question": "q", "status": "Fine", "verdict": "v", "facts": [], "grades": [], "action": "a",
                        "methods": [], "chips": []}}
    assert errors(page, "page") == ["page.summary.status: not a status word", "page.sections: unknown item type video"]
    page["summary"]["status"] = "Clear"
    assert errors(page, "page") == ["page.sections: unknown item type video"]
