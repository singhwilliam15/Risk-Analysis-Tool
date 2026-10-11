"""
NOT RUN: NSE's Terms of Use forbid automated data collection without written permission (docs/data_sources.md).
Kept ready for when permission is granted; see docs/permissions/nse_permission_request.md.

NSE daily archive files, 2016 to today (FINAL_PLAN_V6 Phase 1, steps 3 and 4):

    python scripts/fetch_archives.py            # resumable; about 1 request a second
    python scripts/fetch_archives.py --build    # only rebuild the outputs from what is downloaded

- F&O ban: archives/fo/sec_ban/fo_secban_DDMMYYYY.csv, one per trade date → data/disclosures/history/fo_ban_history.csv
- Price bands: content/equities/eq_band_changes_DDMMYYYY.csv (each day's band changes, from → to) plus today's
  sec_list.csv → data/disclosures/history/band_history.csv: every symbol's band from the first change file on,
  rebuilt backwards from today's list ("official (rebuilt from NSE band-change files)"). Dates before the first file
  are not covered, and the app infers bands from prices there, as before.

Raw files are kept in data/raw/nse/ (git-ignored; see docs/data_sources.md). A date with no file in either format is
a market holiday or a day NSE did not publish one, and is remembered.
"""

import argparse
import io
import json
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
import disclosures as D  # noqa: E402
from nse_client import ARCHIVES, Checkpoint, Client  # noqa: E402

RAW = ROOT / "data" / "raw" / "nse"
OUT = ROOT / "data" / "disclosures" / "history"
START = date(2016, 1, 1)
KINDS = {
    "fo_ban": ("fo_secban_{d:%d%m%Y}.csv", ARCHIVES + "/archives/fo/sec_ban/fo_secban_{d:%d%m%Y}.csv"),
    "band_changes": ("eq_band_changes_{d:%d%m%Y}.csv", ARCHIVES + "/content/equities/eq_band_changes_{d:%d%m%Y}.csv"),
}
REBUILT = "official (rebuilt from NSE band-change files)"


def download(client, end: date) -> None:
    for kind, (name, url) in KINDS.items():
        folder = RAW / kind
        folder.mkdir(parents=True, exist_ok=True)
        missing = Checkpoint(RAW / f"{kind}_missing.jsonl")
        d, got = START, 0
        while d <= end:
            target = folder / name.format(d=d)
            if d.weekday() < 5 and not target.exists() and d.isoformat() not in missing:
                r = client.get(url.format(d=d))
                if r.status_code == 200 and not r.content.lstrip().startswith(b"<"):
                    target.write_bytes(r.content)
                    got += 1
                else:
                    missing.add(d.isoformat())
                if got and got % 200 == 0:
                    print(f"  {kind} {d}: {got} files", flush=True)
            d += timedelta(days=1)
        print(f"{kind}: {got} new files", flush=True)
    r = client.get(ARCHIVES + "/content/equities/sec_list.csv")
    if r.status_code == 200:
        (RAW / f"sec_list_{date.today():%d%m%Y}.csv").write_bytes(r.content)


def file_date(path: Path) -> pd.Timestamp:
    return pd.to_datetime(path.stem.rsplit("_", 1)[-1], format="%d%m%Y")


def fo_ban_history() -> pd.DataFrame:
    rows = []
    for path in sorted((RAW / "fo_ban").glob("*.csv")):
        frame = D._parse_fo_ban_official(path.read_text(encoding="utf-8", errors="replace"))
        if frame is None:
            continue
        frame["source"] = KINDS["fo_ban"][1].format(d=file_date(path))
        rows.append(frame)
    out = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(columns=["trade_date", "symbol", "source"])
    return out.sort_values(["trade_date", "symbol"]).reset_index(drop=True)


def band_changes() -> pd.DataFrame:
    """Every band change: date, symbol, series, from, to (bands as numbers; 'No Band' kept as text)."""
    rows = []
    for path in sorted((RAW / "band_changes").glob("*.csv")):
        try:
            frame = pd.read_csv(io.StringIO(path.read_text(encoding="utf-8", errors="replace")), dtype=str)
        except (pd.errors.EmptyDataError, pd.errors.ParserError):
            continue
        frame.columns = [c.strip().lower() for c in frame.columns]
        if not {"symbol", "from", "to"} <= set(frame.columns):
            continue
        frame = frame.assign(date=file_date(path), symbol=frame["symbol"].str.strip(),
                             series=frame.get("series", pd.Series("", index=frame.index)).fillna("").str.strip(),
                             band_from=frame["from"].str.strip(), band_to=frame["to"].str.strip())
        rows.append(frame[["date", "symbol", "series", "band_from", "band_to"]])
    return pd.concat(rows, ignore_index=True).sort_values(["symbol", "date"]) if rows else pd.DataFrame(
        columns=["date", "symbol", "series", "band_from", "band_to"])


def norm_band(value) -> str:
    """'20', '20.0' and 20.0 → '20'; 'No Band' → 'no band'."""
    text = str(value).strip()
    try:
        return f"{float(text):g}"
    except ValueError:
        return text.lower()


def rebuild_bands(changes: pd.DataFrame, today: pd.DataFrame, first_file) -> tuple:
    """
    Band history: for each symbol, a row at the first file date with the band before its first change (its first
    'from'), then a row at each change date with the new band ('to'). Symbols with no change keep today's band from
    the first file date. Returns (history, checks) where checks lists symbols whose last 'to' disagrees with today.
    """
    rows, disagree = [], []
    today_band = dict(zip(today["symbol"], today["band"]))
    for symbol, g in changes.groupby("symbol", sort=False):
        g = g.sort_values("date")
        rows.append({"symbol": symbol, "series": g["series"].iloc[0], "band": g["band_from"].iloc[0],
                     "effective_date": first_file})
        for r in g.itertuples(index=False):
            rows.append({"symbol": symbol, "series": r.series, "band": r.band_to, "effective_date": r.date})
        if symbol in today_band and norm_band(today_band[symbol]) != norm_band(g["band_to"].iloc[-1]):
            disagree.append(symbol)
    changed = set(changes["symbol"])
    for symbol, band in today_band.items():
        if symbol not in changed:
            rows.append({"symbol": symbol, "series": "", "band": band, "effective_date": first_file})
    history = pd.DataFrame(rows)
    history["source"] = REBUILT
    return history.sort_values(["symbol", "effective_date"]).reset_index(drop=True), disagree


def build() -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    bans = fo_ban_history()
    bans.to_csv(OUT / "fo_ban_history.csv", index=False, date_format="%Y-%m-%d")
    changes = band_changes()
    lists = sorted(RAW.glob("sec_list_*.csv"), key=file_date)
    today = D.load_file(lists[-1], "price_bands", as_of=str(file_date(lists[-1]).date()))[0] if lists else pd.DataFrame(columns=["symbol", "band"])
    first_file = changes["date"].min() if len(changes) else pd.NaT
    history, disagree = rebuild_bands(changes, today, first_file)
    history.to_csv(OUT / "band_history.csv", index=False, date_format="%Y-%m-%d")
    files = {k: sorted((RAW / k).glob("*.csv")) for k in KINDS}
    summary = {"fo_ban": {"files": len(files["fo_ban"]), "first": str(bans["trade_date"].min().date()) if len(bans) else None,
                          "last": str(bans["trade_date"].max().date()) if len(bans) else None, "ban_rows": len(bans),
                          "stocks": int(bans["symbol"].nunique())},
               "band_changes": {"files": len(files["band_changes"]), "changes": len(changes),
                                "first": str(first_file.date()) if len(changes) else None,
                                "last": str(changes["date"].max().date()) if len(changes) else None,
                                "symbols": int(history["symbol"].nunique()), "anchor_list": lists[-1].name if lists else None,
                                "last_change_disagrees_with_today": len(disagree), "examples": disagree[:10]}}
    (OUT / "archives_summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", action="store_true")
    args = parser.parse_args()
    if not args.build:
        download(Client(), date.today())
    build()
    return 0


if __name__ == "__main__":
    sys.exit(main())
