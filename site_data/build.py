"""
Website data (FINAL_PLAN_V6 Phase 5): run the app for each preset, read what every page shows, and write JSON for the
static site in web/. The site does no calculations, and this script does none either: it drives app.py with
Streamlit's AppTest (as scripts/build_snapshot.py does) and records the page summary, sections, tables, metrics and
Plotly figures exactly as the app rendered them.

    python site_data/build.py                  # every preset (the demo snapshot makes the defaults fast, offline)
    python site_data/build.py --out DIR --presets asianpaint

No NSE lists are used or written (NSE's terms reserve redistribution; docs/data_sources.md). If a preset fails,
its last good JSON is kept and marked stale.
"""

import argparse
import json
import math
import os
import shutil
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("RISK_TOOL_DEFAULT_VIEW", "full")  # every section rendered
os.environ["RISK_TOOL_DISCLOSURE_DIR"] = str(ROOT / "test_data" / "no_disclosures")  # never local NSE files

import pandas as pd  # noqa: E402

from site_data.schema import validate  # noqa: E402

OUT = ROOT / "web" / "public" / "data"
APP_URL = "https://risk-analysis-tool.streamlit.app/"
# site slug: (app page, title)
PAGES = {
    "overview": ("Overview", "Overview"),
    "market": ("Market", "Market"),
    "liquidity": ("Liquidity", "Liquidity"),
    "credit": ("Credit", "Credit"),
    "concentration-factors": ("Concentration & Factors", "Concentration & Factors"),
    "promoter-pledge-governance": ("Promoter Pledge & Governance", "Promoter Pledge & Governance"),
    "integrated-stress": ("Integrated Stress", "Integrated Stress"),
    "decisions": ("Decisions", "Decisions"),
    "trust": ("Trust", "Trust"),
}
# preset slug: (label, kind, ticker or None, investment or None)
PRESETS = {
    "portfolio": ("5-stock NSE portfolio, ₹10 lakh", "portfolio", None, None),
    "portfolio-50cr": ("5-stock NSE portfolio, ₹50 crore", "portfolio", None, 500_000_000.0),
    "reliance": ("Reliance Industries (NSE)", "stock", "RELIANCE.NS", None),
    "hdfcbank": ("HDFC Bank (NSE)", "stock", "HDFCBANK.NS", None),
    "tcs": ("TCS (NSE)", "stock", "TCS.NS", None),
    "asianpaint": ("Asian Paints (NSE)", "stock", "ASIANPAINT.NS", None),
    "britannia": ("Britannia (NSE)", "stock", "BRITANNIA.NS", None),
    "aapl": ("Apple (US)", "stock", "AAPL", None),
}
MAX_CHARTS, MAX_CHART_BYTES, MAX_ROWS = 4, 150_000, 60
SKIP_SECTIONS = ("Download", "Validate against", "Upload", "Excel Report")


def _clean(v):
    """JSON-safe scalar: NaN/inf → None, numpy → Python, floats to 6 significant figures."""
    if v is None:
        return None
    if hasattr(v, "item"):
        v = v.item()
    if isinstance(v, float):
        return None if not math.isfinite(v) else float(f"{v:.6g}")
    if isinstance(v, (pd.Timestamp, date)):
        return v.isoformat()[:10]
    return v if isinstance(v, (int, str, bool)) else str(v)


def table_json(df: pd.DataFrame) -> dict:
    if not isinstance(df.index, pd.RangeIndex):
        df = df.reset_index()
    df = df.head(MAX_ROWS)
    return {"columns": [str(c) for c in df.columns], "rows": [[_clean(v) for v in row] for row in df.itertuples(index=False)],
            "truncated": False}


def _text(node) -> str:
    return str(getattr(node, "value", "") or "")


def sections(at) -> list:
    """The full-analysis part of the page (after the summary), as [{title, items}] in reading order."""
    out, current, after_summary, charts = [], None, False, 0

    def section(title):
        nonlocal current
        current = {"title": title, "items": []}
        out.append(current)

    def walk(node, skip=False):
        nonlocal after_summary, charts
        for k in sorted(getattr(node, "children", {}) or {}):
            c = node.children[k]
            t = c.type
            if t == "markdown" and _text(c).strip() == "---":
                after_summary = True
                continue
            if not after_summary:
                continue
            label = getattr(c, "label", "") or ""
            if t in ("expander", "tab"):
                if any(s in label for s in SKIP_SECTIONS):
                    continue
                section(label.lstrip("📊🧩📈⚡🔬📥✅ ").strip())
                walk(c)
                continue
            if t == "subheader" or (t == "markdown" and _text(c).startswith("#")):
                section(_text(c).lstrip("#").strip())
                continue
            if current is None:
                section("")
            if t == "dataframe" or t == "table":
                try:
                    current["items"].append({"type": "table", **table_json(c.value)})
                except Exception:  # noqa: BLE001 — a table that cannot be read is left out, not invented
                    pass
            elif t == "plotly_chart" and charts < MAX_CHARTS and len(c.proto.spec) <= MAX_CHART_BYTES:
                spec = json.loads(c.proto.spec)
                spec.get("layout", {}).pop("template", None)  # the site applies its own light/dark styling
                current["items"].append({"type": "chart", "figure": spec})
                charts += 1
            elif t == "metric":
                current["items"].append({"type": "metric", "label": label, "value": str(c.value)})
            elif t == "caption" and _text(c):
                current["items"].append({"type": "note", "text": _text(c)})
            elif t == "markdown" and _text(c) and not _text(c).startswith("<style"):
                current["items"].append({"type": "text", "text": _text(c)})
            else:
                walk(c)
    walk(at.main)
    return [s for s in out if s["items"]]


def summary_json(parts: dict) -> dict:
    import evidence as V
    chips = []
    for sid in parts.get("chips", []):
        r = V.record(sid)
        chips.append({"id": sid, "signal": V.SIGNALS[sid], "badge": r["badge"], "lift": V.lift_text(r),
                      "window": V.SHORT.get(r["test"], r["test"]), "beyond_momentum": V.incremental_text(r)})
    grades = [{"label": label, "name": m.name, "grade": m.grade, "reasons": list(m.reasons)}
              for label, m in parts.get("grades", [])]
    return {"question": parts["question"], "status": parts["status"], "verdict": parts["verdict"],
            "facts": [{"label": a, "value": b, "so_what": c} for a, b, c in parts["facts"]],
            "grades": grades, "action": parts["action"], "methods": list(parts["methods"]), "chips": chips}


def data_note() -> str:
    """Where the numbers come from, for the website (the app's own caption talks about its sidebar)."""
    from ui import snapshot
    meta = snapshot.meta()
    if not meta:
        return "Prices from Yahoo Finance (adjusted closes), computed when the site was built."
    return (f"Prices from Yahoo Finance (adjusted closes) to {pd.Timestamp(meta['prices_as_of']):%d %b %Y}, from the app's "
            f"demo snapshot built {pd.Timestamp(meta['built']):%d %b %Y}.")


def run_preset(slug: str, pages=None) -> dict:
    """{page slug: page JSON} for one preset."""
    from streamlit.testing.v1 import AppTest

    from ui import summaries
    from ui.pages import PAGE_KEY, SLUGS
    label, kind, ticker, investment = PRESETS[slug]
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=1800)
    at.run()
    if kind == "portfolio":
        next(r for r in at.sidebar.radio if r.label == "Analysis Mode").set_value("Portfolio")
    else:
        at.sidebar.text_input[0].set_value(ticker)
    at.run()
    if investment:
        next(n for n in at.sidebar.number_input if "Investment Amount" in n.label).set_value(investment)
        at.run()
    out = {}
    for page_slug in pages or PAGES:
        app_page, title = PAGES[page_slug]
        at.radio(key=PAGE_KEY).set_value(app_page)
        at.run()
        problems = [e.value for e in list(at.exception) + list(at.error)]
        if problems:
            raise RuntimeError(f"{slug} / {app_page}: {problems[0]}")
        out[page_slug] = {"preset": slug, "preset_label": label, "page": page_slug, "title": title,
                          "app_link": f"{APP_URL}?page={SLUGS[app_page]}", "summary": summary_json(at.session_state[summaries.LAST_KEY]),
                          "sections": sections(at), "data_note": data_note(),
                          "built": date.today().isoformat(), "stale": False}
    return out


def evidence_json() -> dict:
    import evidence as V
    reg = V.registry()
    results = ROOT / "case_studies" / "results"
    ratio = pd.read_csv(results / "margin_trigger_rate_ratio.csv")
    bins = pd.read_csv(results / "margin_trigger_bins.csv")
    tally = pd.read_csv(results / "tally.csv")
    return {
        "signals": [{"id": r["id"], "signal": r["label"], "badge": r["badge"], "lift": V.lift_text(r),
                     "beyond_momentum": V.incremental_text(r), "window": V.SHORT.get(r["test"], r["test"] or "—"),
                     "note": r["note"]} for r in reg.to_dict("records")],
        "margin_trigger": {"ratio": table_json(ratio), "bins": table_json(bins[bins["Sample"].str.startswith("primary")])},
        "case_tally": table_json(tally),
        "decisions": {name: json.loads((results / f"{name}_decision.json").read_text(encoding="utf-8"))
                      for name in ("events", "margin_trigger")},
    }


def glossary_json() -> list:
    from ui.plain import VOCAB
    return [{"plain": p, "technical": t, "definition": d, "section": a} for p, t, d, a in VOCAB.values()]


def split_figures(payload: dict, folder: Path) -> dict:
    """Move each Plotly figure to its own file (fetched by the site only when the chart scrolls into view)."""
    n = 0
    for s in payload["sections"]:
        for i, item in enumerate(s["items"]):
            if item["type"] == "chart":
                name = f"{payload['page']}-{n}.json"
                folder.mkdir(parents=True, exist_ok=True)
                (folder / name).write_text(json.dumps(item["figure"], ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
                s["items"][i] = {"type": "chart", "src": f"{payload['preset']}/figures/{name}"}
                n += 1
    return payload


def write(path: Path, payload, kind: str) -> None:
    validate(payload, kind)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def mark_stale(out: Path, slug: str, reason: str) -> int:
    """Keep the last good JSON of a failed preset, marked stale; returns how many files were kept."""
    kept = 0
    for f in sorted((out / slug).glob("*.json")):
        data = json.loads(f.read_text(encoding="utf-8"))
        data.update(stale=True, stale_reason=reason)
        f.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        kept += 1
    return kept


def build(out: Path = OUT, presets=None, pages=None) -> dict:
    out = Path(out)
    status = {}
    for slug in presets or PRESETS:
        started = time.time()
        try:
            for page_slug, payload in run_preset(slug, pages).items():
                write(out / slug / f"{page_slug}.json", split_figures(payload, out / slug / "figures"), "page")
            status[slug] = "ok"
        except Exception as exc:  # noqa: BLE001 — keep the last good data, say so
            kept = mark_stale(out, slug, str(exc)[:300])
            status[slug] = f"stale ({kept} files kept): {exc}"
        print(f"{slug}: {status[slug][:120]} ({time.time() - started:.0f}s)", flush=True)
    write(out / "presets.json", [{"slug": s, "label": PRESETS[s][0], "kind": PRESETS[s][1],
                                  "stale": not status.get(s, "ok").startswith("ok")}
                                 for s in PRESETS if (out / s).exists()], "presets")
    write(out / "evidence.json", evidence_json(), "evidence")
    write(out / "glossary.json", glossary_json(), "glossary")
    docs = out / "docs"
    docs.mkdir(parents=True, exist_ok=True)
    for name in ("methodology.md", "case_studies.md"):
        shutil.copyfile(ROOT / "docs" / name, docs / name)
    return status


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(OUT))
    parser.add_argument("--presets", nargs="*")
    args = parser.parse_args()
    status = build(Path(args.out), args.presets)
    return 0 if all(v == "ok" for v in status.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
