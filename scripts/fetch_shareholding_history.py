"""
Quarterly promoter holding and pledged/encumbered shares for every NSE company, Sep 2021 - Dec 2024, from NSE's
shareholding-pattern XBRL (NEXT_STEPS_V5 Phase G; docs/preregistration_events.md).

    python scripts/fetch_shareholding_history.py            # resumable; about 12-15 hours at 1.5 s a request
    python scripts/fetch_shareholding_history.py --write    # only rebuild the output CSV from what is downloaded

1. The all-company filing list (corporate-share-holdings-master) in monthly broadcast windows, Oct 2021 - Jan 2025,
   saved unchanged in data/cache/shareholding/listings/.
2. For each (ISIN, quarter end), the ORIGINAL filing (earliest broadcast): later revisions are not used, so every
   figure is as the market first saw it. Filings dated on a day that is not a quarter end (listings, allotments)
   are left out.
3. Each XBRL is read with nse_sources.shareholding_any: the current taxonomy (pledges only) or the older one
   (pledged OR otherwise encumbered, which every filing used until mid-2025). The measure is kept on each row.
   Raw XBRL is not kept; a small excerpt of the facts read is, so a parsing fix can be re-applied offline.
4. Output: data/disclosures/history/shareholding_2021_2024.csv with the source XBRL URL on every row, and the
   filings that could not be read in shareholding_2021_2024_unreadable.csv. Nothing is filled in.
"""

import argparse
import gzip
import json
import re
import sys
import time
from datetime import date
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import nse_sources as N  # noqa: E402

CACHE = ROOT / "data" / "cache" / "shareholding"
LISTINGS = CACHE / "listings"
PARSED = CACHE / "parsed.jsonl"
EXCERPTS = CACHE / "excerpts.jsonl.gz"
OUT_DIR = ROOT / "data" / "disclosures" / "history"
OUT = OUT_DIR / "shareholding_2021_2024.csv"
UNREADABLE = OUT_DIR / "shareholding_2021_2024_unreadable.csv"
API = "https://www.nseindia.com/api"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36",
           "Accept": "application/json,text/html,*/*", "Accept-Language": "en-US,en;q=0.9", "Referer": "https://www.nseindia.com/"}
FIRST_QUARTER, LAST_QUARTER = pd.Timestamp("2021-09-30"), pd.Timestamp("2024-12-31")
WINDOWS = pd.period_range("2021-10", "2025-01", freq="M")
DELAY = 1.5
FACTS = re.compile(
    r'<[A-Za-z\-]+:(?:NumberOfShares|ShareholdingAsAPercentageOfTotalNumberOfShares|PledgedOrEncumberedNumberOfShares|'
    r'PledgedOrEncumberedSharesHeldAsPercentageOfTotalNumberOfShares|NumberOfSharesEncumberedUnderPledged|'
    r'EncumberedShareUnderPledgedAsPercentageOfTotalNumberOfShares)\b[^>]*contextRef="(?:ShareholdingOfPromoterAndPromoterGroup'
    r'(?:_Context)?I|ShareholdingPattern(?:_Context)?I)"[^>]*>[^<]*</[^>]+>'
    r'|<[A-Za-z\-]+:(?:DateOfReport|WhetherAnySharesHeldByPromotersArePledgeOrOtherwiseEncumbered|'
    r'WhetherAnySharesHeldByPromotersAreEncumberedUnderPledged)\b[^>]*>[^<]*</[^>]+>')


class Client:
    """A browser-like NSE session: 1.5 s between requests, backs off on refusals, refreshes cookies regularly."""

    def __init__(self):
        self.calls, self.refusals = 0, 0
        self._new_session()

    def _new_session(self):
        self.s = requests.Session()
        self.s.headers.update(HEADERS)
        try:
            self.s.get("https://www.nseindia.com/", timeout=30)
        except requests.RequestException:
            pass

    def get(self, url: str):
        for attempt in range(6):
            time.sleep(DELAY)
            self.calls += 1
            if self.calls % 250 == 0:
                self._new_session()
            try:
                r = self.s.get(url, timeout=60)
            except (requests.Timeout, requests.ConnectionError):
                time.sleep(15 * (attempt + 1))
                continue
            if r.status_code in (401, 403, 429, 503):
                self.refusals += 1
                wait = min(60 * 2 ** attempt, 900)
                print(f"    refused ({r.status_code}); waiting {wait}s", flush=True)
                time.sleep(wait)
                self._new_session()
                continue
            return r
        raise RuntimeError(f"NSE kept refusing {url}; stopping (rerun later: finished work is kept)")


def fetch_listings(client) -> pd.DataFrame:
    LISTINGS.mkdir(parents=True, exist_ok=True)
    for m in WINDOWS:
        path = LISTINGS / f"{m}.json"
        if path.exists():
            continue
        start, end = m.start_time, m.end_time
        r = client.get(f"{API}/corporate-share-holdings-master?index=equities&from_date={start:%d-%m-%Y}&to_date={end:%d-%m-%Y}")
        data = r.json() if r is not None and r.status_code == 200 else None
        if not isinstance(data, list):
            raise RuntimeError(f"listing {m}: unexpected answer; stopping")
        path.write_text(json.dumps(data))
        print(f"  listing {m}: {len(data)} filings", flush=True)
    rows = [f for p in sorted(LISTINGS.glob("*.json")) for f in json.loads(p.read_text())]
    return pd.DataFrame(rows)


def original_filings(listing: pd.DataFrame) -> pd.DataFrame:
    """One row per (ISIN, quarter end): the earliest broadcast filing with an XBRL file, quarters in range only."""
    df = listing.copy()
    df["quarter_end"] = pd.to_datetime(df["date"], format="%d-%b-%Y", errors="coerce")
    df["broadcast"] = pd.to_datetime(df["broadcastDate"], format="%d-%b-%Y %H:%M:%S", errors="coerce")
    df = df[df["quarter_end"].notna() & df["broadcast"].notna() & df["xbrl"].fillna("").str.endswith(".xml")]
    df = df[df["quarter_end"].dt.is_quarter_end & (df["quarter_end"] >= FIRST_QUARTER) & (df["quarter_end"] <= LAST_QUARTER)]
    df = df.sort_values("broadcast").drop_duplicates(["isin", "quarter_end"], keep="first")
    return df.sort_values(["quarter_end", "symbol"]).reset_index(drop=True)


def read_parsed() -> list:
    """Rows read so far; a line cut short by a shutdown is skipped (that filing is simply read again)."""
    if not PARSED.exists():
        return []
    rows = []
    for line in PARSED.read_text(encoding="utf-8").splitlines():
        try:
            rows.append(json.loads(line))
        except ValueError:
            continue
    return rows


def done_urls() -> set:
    return {row["source"] for row in read_parsed()}


def download(client, filings: pd.DataFrame) -> None:
    done = done_urls()
    todo = filings[~filings["xbrl"].isin(done)]
    print(f"{len(filings):,} original filings; {len(done):,} already read; {len(todo):,} to go", flush=True)
    started = time.time()
    if PARSED.exists() and PARSED.stat().st_size and not PARSED.read_bytes().endswith(b"\n"):
        with open(PARSED, "a", encoding="utf-8") as out:
            out.write("\n")  # finish a line cut short by a shutdown, so new rows start on their own line
    with open(PARSED, "a", encoding="utf-8") as out, gzip.open(EXCERPTS, "at", encoding="utf-8") as ex:
        for i, f in enumerate(todo.itertuples(index=False), 1):
            r = client.get(f.xbrl)
            row = {"symbol": f.symbol, "isin": f.isin, "quarter_end": f"{f.quarter_end:%Y-%m-%d}",
                   "disclosure_date": f"{f.broadcast:%Y-%m-%d}", "source": f.xbrl}
            if r is None or r.status_code != 200:
                row["status"] = f"HTTP {getattr(r, 'status_code', 'none')}"
            else:
                text = r.content.decode("utf-8", errors="replace")
                parsed = N.shareholding_any(text)
                ex.write(json.dumps({"source": f.xbrl, "facts": FACTS.findall(text)}) + "\n")
                if parsed is None:
                    row["status"] = "not readable"
                else:
                    row.update(status="ok", measure=parsed["measure"],
                               promoter_holding_pct=round(parsed["promoter_holding_pct"], 4),
                               encumbered_pct_of_promoter=round(parsed["pledged_pct_of_promoter"], 4),
                               encumbered_pct_of_total=round(parsed["pledged_pct_of_total"], 4),
                               encumbered_shares=parsed["pledged_shares"], total_shares=parsed["total_shares"])
            out.write(json.dumps(row) + "\n")
            if i % 100 == 0:
                out.flush()
                ex.flush()
                rate = (time.time() - started) / i
                print(f"  {i:,}/{len(todo):,} ({rate:.1f}s each, about {rate * (len(todo) - i) / 3600:.1f}h left; "
                      f"{client.refusals} refusals)", flush=True)


def write_outputs() -> None:
    rows = pd.DataFrame(read_parsed())
    rows = rows.drop_duplicates("source", keep="last")
    ok = rows[rows["status"] == "ok"].drop(columns="status")
    cols = ["symbol", "isin", "quarter_end", "disclosure_date", "measure", "promoter_holding_pct",
            "encumbered_pct_of_promoter", "encumbered_pct_of_total", "encumbered_shares", "total_shares", "source"]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ok[cols].sort_values(["quarter_end", "symbol"]).to_csv(OUT, index=False)
    rows[rows["status"] != "ok"][["symbol", "isin", "quarter_end", "disclosure_date", "status", "source"]].to_csv(UNREADABLE, index=False)
    by_q = ok.groupby("quarter_end").size()
    print(f"wrote {OUT.relative_to(ROOT)}: {len(ok):,} rows, {ok['isin'].nunique():,} companies; per quarter: "
          + ", ".join(f"{q[:7]} {n}" for q, n in by_q.items()) + f"; unreadable {int((rows['status'] != 'ok').sum())}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="only rebuild the output from the downloaded rows")
    args = parser.parse_args()
    if not args.write:
        client = Client()
        filings = original_filings(fetch_listings(client))
        CACHE.mkdir(parents=True, exist_ok=True)
        filings.to_csv(CACHE / "original_filings.csv", index=False)
        download(client, filings)
    write_outputs()
    print(f"done {date.today()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
