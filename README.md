# Demo snapshot (published daily)

Built by `.github/workflows/refresh-snapshot.yml` from `main` after each NSE session: the presets with the default
settings, prices to 2026-10-23, as a zip of JSON and Parquet (`ui/snapshot_format.py`). The app accepts this
`snapshot.zip` only if its sha256 matches `data/snapshot/published.json` on `main`. This branch is replaced on every
publish; it has no history.
