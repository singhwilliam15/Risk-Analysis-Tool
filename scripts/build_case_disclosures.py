"""
The case studies' pledge file, from the NSE shareholding history (scripts/fetch_shareholding_history.py):
every case and control company's quarterly rows in the pledges template, listed in
case_studies/data/disclosures/manifest.json with its source.

    python scripts/build_case_disclosures.py

The history covers quarters Sep 2021 - Dec 2024 only (NSE serves no older XBRL to scripts), so of the cases only
Adani Enterprises (event Jan 2023) and the controls on Adani's dates get the event pillar. The figures are
"pledged or otherwise encumbered" % of promoter holding, the only measure filed before mid-2025.
"""

import json
import sys
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from case_studies import engine as K  # noqa: E402

HISTORY = ROOT / "data" / "disclosures" / "history" / "shareholding_2021_2024.csv"
OUT_DIR = K.DATA_DIR / "disclosures"
FILE = "pledges_nse_history_2021_2024.csv"


def main() -> int:
    config = K.load_cases()
    symbols = {c["ticker"].split(".")[0] for c in config["cases"]} | {t.split(".")[0] for t in config["control_group"]}
    history = pd.read_csv(HISTORY)
    rows = history[history["symbol"].isin(symbols)].rename(columns={
        "encumbered_pct_of_promoter": "pledged_pct_of_promoter", "encumbered_pct_of_total": "pledged_pct_of_total",
        "encumbered_shares": "pledged_shares"})
    cols = ["symbol", "quarter_end", "promoter_holding_pct", "pledged_pct_of_promoter", "pledged_pct_of_total",
            "pledged_shares", "disclosure_date", "source"]
    rows[cols].sort_values(["symbol", "quarter_end"]).to_csv(OUT_DIR / FILE, index=False)
    manifest_path = OUT_DIR / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"] = [e for e in manifest["files"] if e["file"] != FILE] + [{
        "file": FILE, "dataset": "pledges",
        "source_url": "https://www.nseindia.com/api/corporate-share-holdings-master (XBRL per row in 'source')",
        "downloaded_on": str(date.today()), "coverage_start": "2021-09-30", "coverage_end": "2024-12-31",
        "notes": "Quarterly shareholding-pattern XBRL, original filing of each quarter, disclosure_date = NSE broadcast "
                 "date. The pledged_* columns hold shares 'pledged or otherwise encumbered' (pledges and non-disposal "
                 "undertakings together: the only measure filed before mid-2025), an upper bound on pledges. Built by "
                 "scripts/build_case_disclosures.py from data/disclosures/history/shareholding_2021_2024.csv."}]
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    found = sorted(set(rows["symbol"]))
    print(f"{FILE}: {len(rows)} rows for {', '.join(found)}; missing: {', '.join(sorted(symbols - set(found))) or 'none'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
