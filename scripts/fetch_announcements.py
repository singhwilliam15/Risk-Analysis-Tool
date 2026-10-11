"""
NOT RUN: NSE's Terms of Use forbid automated data collection without written permission (docs/data_sources.md).
Kept ready for when permission is granted; see docs/permissions/nse_permission_request.md.

NSE corporate announcements (Regulation 30), 2014 to today: auditor events and credit-rating disclosures
(FINAL_PLAN_V6 Phase 1, steps 2 and 3).

    python scripts/fetch_announcements.py --listings       # weekly listings, about 650 requests (~15 minutes)
    python scripts/fetch_announcements.py --attachments    # the relevant attachments' text (many hours; resumable)
    python scripts/fetch_announcements.py --classify       # classify into data/disclosures/history/

Listings keep only the relevant rows (subjects "Change in Auditors", "Statement on Impact of Audit Qualifications",
anything with "Credit Rating", and any text about an auditor resigning), with the number of rows each week had.
Attachments (PDF, or a zip holding one) are read with pypdf; only the text is kept, in data/raw/nse/announcements/
(git-ignored; see docs/data_sources.md). Classification lives in nse_announcements.py.
"""

import argparse
import io
import json
import re
import sys
import zipfile
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from nse_client import API, Checkpoint, Client  # noqa: E402

RAW = ROOT / "data" / "raw" / "nse" / "announcements"
LISTINGS = RAW / "listings"
TEXT = RAW / "text"
START = date(2014, 1, 1)
AUDITOR_SUBJECTS = ("Change in Auditors", "Statement on Impact of Audit Qualifications")
RESIGN = re.compile(r"(resign\w*.{0,80}auditor|auditor.{0,80}resign\w*)", re.I | re.S)


def relevant(row: dict) -> bool:
    desc, text = row.get("desc") or "", row.get("attchmntText") or ""
    return desc in AUDITOR_SUBJECTS or "credit rating" in desc.lower() or bool(RESIGN.search(text))


def weeks(end: date):
    d = START
    while d <= end:
        yield d, min(d + timedelta(days=6), end)
        d += timedelta(days=7)


def fetch_listings(client, end: date) -> None:
    LISTINGS.mkdir(parents=True, exist_ok=True)
    for a, b in weeks(end):
        path = LISTINGS / f"{a.isoformat()}.json"
        if path.exists() and b < end - timedelta(days=7):  # the last weeks are re-read: late filings arrive
            continue
        data = client.json(f"{API}/corporate-announcements?index=equities&from_date={a:%d-%m-%Y}&to_date={b:%d-%m-%Y}")
        if not isinstance(data, list):
            raise RuntimeError(f"listing {a}: unexpected answer; stopping (rerun to resume)")
        keep = [r for r in data if relevant(r)]
        path.write_text(json.dumps({"from": a.isoformat(), "to": b.isoformat(), "rows_in_week": len(data), "relevant": keep}))
        if a.day <= 7 and a.month == 1:
            print(f"  {a.year}: listing done", flush=True)


def listing_rows() -> pd.DataFrame:
    rows = []
    for path in sorted(LISTINGS.glob("*.json")):
        for r in json.loads(path.read_text())["relevant"]:
            rows.append({"seq_id": str(r.get("seq_id")), "symbol": r.get("symbol"), "company": r.get("sm_name"),
                         "isin": r.get("sm_isin"), "subject": r.get("desc"), "summary": r.get("attchmntText"),
                         "broadcast": r.get("an_dt"), "attachment": r.get("attchmntFile")})
    df = pd.DataFrame(rows).drop_duplicates("seq_id")
    df["broadcast"] = pd.to_datetime(df["broadcast"], format="%d-%b-%Y %H:%M:%S", errors="coerce")
    return df.sort_values("broadcast").reset_index(drop=True)


def pdf_text(blob: bytes) -> str:
    from pypdf import PdfReader
    try:
        reader = PdfReader(io.BytesIO(blob))
        return "\n".join((page.extract_text() or "") for page in reader.pages[:12])
    except Exception:
        return ""


def attachment_text(blob: bytes, name: str) -> str:
    if blob[:2] == b"PK" or name.lower().endswith(".zip"):
        try:
            with zipfile.ZipFile(io.BytesIO(blob)) as z:
                parts = []
                for member in z.namelist():
                    data = z.read(member)
                    parts.append(pdf_text(data) if member.lower().endswith(".pdf") or data[:4] == b"%PDF"
                                 else data.decode("utf-8", errors="replace") if member.lower().endswith((".xml", ".txt", ".html")) else "")
                return "\n".join(parts)
        except zipfile.BadZipFile:
            return ""
    if blob[:4] == b"%PDF":
        return pdf_text(blob)
    return ""


def fetch_attachments(client) -> None:
    TEXT.mkdir(parents=True, exist_ok=True)
    done = Checkpoint(RAW / "attachments_done.jsonl")
    rows = listing_rows()
    todo = rows[~rows["seq_id"].isin(done.done) & rows["attachment"].fillna("").str.startswith("http")]
    print(f"{len(rows):,} relevant announcements; {len(todo):,} attachments to read", flush=True)
    for i, r in enumerate(todo.itertuples(index=False), 1):
        resp = client.get(r.attachment)
        text = attachment_text(resp.content, r.attachment) if resp.status_code == 200 else ""
        (TEXT / f"{r.seq_id}.txt").write_text(text, encoding="utf-8")
        done.add(r.seq_id)
        if i % 250 == 0:
            print(f"  {i:,}/{len(todo):,} attachments ({client.refusals} refusals)", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--listings", action="store_true")
    parser.add_argument("--attachments", action="store_true")
    parser.add_argument("--classify", action="store_true")
    args = parser.parse_args()
    client = Client() if (args.listings or args.attachments) else None
    if args.listings:
        fetch_listings(client, date.today())
        rows = listing_rows()
        print(f"listings: {len(rows):,} relevant rows; by subject:\n{rows['subject'].value_counts().head(15).to_string()}")
    if args.attachments:
        fetch_attachments(client)
    if args.classify:
        import nse_announcements as A
        A.write_outputs(listing_rows(), TEXT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
