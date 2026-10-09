# Demo snapshot (published daily)

Built by `.github/workflows/refresh-snapshot.yml` from `main` after each NSE session: the presets with the default
settings, prices to 2026-10-09. The app on `main` reads `meta.json` here and swaps in `snapshot.pkl.gz` when it
is newer than what it has. This branch is replaced on every publish; it has no history.
