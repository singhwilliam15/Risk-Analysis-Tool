"""
Stage the freshly built snapshot for the `snapshot-data` branch (used by .github/workflows/refresh-snapshot.yml).

    python scripts/publish_snapshot.py OUT_DIR [--force]

Copies data/snapshot/snapshot.pkl.gz to OUT_DIR with a meta.json (the snapshot's meta plus its sha256 and size),
which the app reads to decide whether to swap it in (ui/snapshot.py). Prints `publish=true` or `publish=false`
(and appends it to $GITHUB_OUTPUT when set): false when the published snapshot already has prices to the same
date or later, for example after a market holiday, unless --force.
"""

import argparse
import gzip
import hashlib
import json
import os
import pickle
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ui import snapshot  # noqa: E402

README = """# Demo snapshot (published daily)

Built by `.github/workflows/refresh-snapshot.yml` from `main` after each NSE session: the presets with the default
settings, prices to {prices_as_of}. The app on `main` reads `meta.json` here and swaps in `snapshot.pkl.gz` when it
is newer than what it has. This branch is replaced on every publish; it has no history.
"""


def published_meta(base: str) -> dict:
    """meta.json of the snapshot published now, or {} if there is none (first run) or it cannot be read."""
    try:
        return json.loads(snapshot._fetch(base + "meta.json", timeout=10)) if base else {}
    except Exception:
        return {}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("out_dir")
    parser.add_argument("--force", action="store_true", help="publish even if the prices are not newer")
    args = parser.parse_args()

    blob = snapshot.PATH.read_bytes()
    meta = pickle.loads(gzip.decompress(blob))["meta"]
    info = {**meta, "sha256": hashlib.sha256(blob).hexdigest(), "bytes": len(blob)}
    current = published_meta(os.environ.get(snapshot.REMOTE_ENV, snapshot.REMOTE_URL))
    later_prices = str(meta.get("prices_as_of") or "") > str(current.get("prices_as_of") or "")
    publish = args.force or not current or later_prices
    print(f"built: prices to {meta.get('prices_as_of')}; published: prices to {current.get('prices_as_of')}")

    if publish:
        out = Path(args.out_dir)
        out.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(snapshot.PATH, out / "snapshot.pkl.gz")
        (out / "meta.json").write_text(json.dumps(info, indent=2) + "\n")
        (out / "README.md").write_text(README.format(prices_as_of=str(meta.get("prices_as_of"))[:10]))
    line = f"publish={'true' if publish else 'false'}"
    print(line)
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(line + "\n" + f"prices_as_of={str(meta.get('prices_as_of'))[:10]}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
