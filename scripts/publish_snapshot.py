"""
Stage the freshly built snapshot for publishing (used by .github/workflows/refresh-snapshot.yml).

    python scripts/publish_snapshot.py OUT_DIR [--force]

Writes OUT_DIR/snapshot.zip (data/snapshot/snapshot.zip, ui/snapshot_format.py) and OUT_DIR/published.json (the
snapshot's meta plus its sha256 and size). The workflow pushes the zip to the `snapshot-data` branch and commits
published.json to data/snapshot/published.json on `main`: the app only accepts a zip whose sha256 matches the one on
main. Prints `publish=true` or `publish=false` (and appends it to $GITHUB_OUTPUT when set): false when main already
describes a snapshot with prices to the same date or later, for example after a market holiday, unless --force.
"""

import argparse
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ui import snapshot, snapshot_format  # noqa: E402

README = """# Demo snapshot (published daily)

Built by `.github/workflows/refresh-snapshot.yml` from `main` after each NSE session: the presets with the default
settings, prices to {prices_as_of}, as a zip of JSON and Parquet (`ui/snapshot_format.py`). The app accepts this
`snapshot.zip` only if its sha256 matches `data/snapshot/published.json` on `main`. This branch is replaced on every
publish; it has no history.
"""


def published_meta(url: str) -> dict:
    """main's published.json now, or {} if there is none yet or it cannot be read."""
    try:
        return json.loads(snapshot._fetch(url, timeout=10)) if url else {}
    except Exception:
        return {}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("out_dir")
    parser.add_argument("--force", action="store_true", help="publish even if the prices are not newer")
    args = parser.parse_args()

    blob = snapshot.PATH.read_bytes()
    meta = snapshot_format.read_meta(blob)
    info = {**meta, "sha256": hashlib.sha256(blob).hexdigest(), "bytes": len(blob)}
    current = published_meta(os.environ.get(snapshot.HASH_ENV, snapshot.HASH_URL))
    later_prices = str(meta.get("prices_as_of") or "") > str(current.get("prices_as_of") or "")
    publish = args.force or not current or later_prices
    print(f"built: prices to {meta.get('prices_as_of')}; published on main: prices to {current.get('prices_as_of')}")

    if publish:
        out = Path(args.out_dir)
        out.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(snapshot.PATH, out / "snapshot.zip")
        (out / "published.json").write_text(json.dumps(info, indent=2) + "\n")
        (out / "README.md").write_text(README.format(prices_as_of=str(meta.get("prices_as_of"))[:10]))
    line = f"publish={'true' if publish else 'false'}"
    print(line)
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(line + "\n" + f"prices_as_of={str(meta.get('prices_as_of'))[:10]}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
