# Deploying and renaming

## Deploy on Streamlit Community Cloud

The entry point is `app.py`, the requirements are pinned and no secrets are needed.

1. Sign in at [share.streamlit.io](https://share.streamlit.io) with the GitHub account that owns the repository.
2. Click **Create app** → **Deploy a public app from GitHub**.
3. Pick the repository, branch `main`, main file `app.py`.
4. Under **Advanced settings**, choose **Python 3.11 or 3.12**. The demo snapshot works on both: it needs the same
   pandas version (pinned) and numpy major version, and is ignored otherwise.
5. Click **Deploy**. The first build takes a few minutes.

**Demo snapshot.** The repository ships `data/snapshot/snapshot.zip`: the presets with the default settings,
computed in advance (`scripts/build_snapshot.py`). The app opens on it, so the hosted demo answers at once instead
of downloading and fitting models on Streamlit's small CPU allocation. **Data → Live** in the sidebar switches to
today's prices; any other ticker or setting is computed live either way. Rebuild the snapshot to move its date
forward:

```bash
python scripts/build_snapshot.py     # needs internet; about 30 minutes
pytest test_snapshot.py test_deploy.py
```

**Daily refresh.** You don't need to rebuild by hand to keep the date current. `.github/workflows/refresh-snapshot.yml`
runs Monday to Friday at 18:00 IST, after NSE closes at 15:30. It rebuilds the snapshot from `main`, checks it
offline (`test_snapshot.py`, `test_deploy.py`) and publishes `snapshot.zip` on the `snapshot-data` branch. That
branch has a single commit, replaced on every publish, so the repository does not grow. It then commits the zip's
sha256 to `data/snapshot/published.json` on **`main`**: one small bot commit per trading day, marked `[skip ci]`.

Every 15 minutes the running app reads `published.json` from `main`. If it describes a newer snapshot, the app
downloads the zip from `snapshot-data` and accepts it only if its sha256 matches. The sidebar's "Demo snapshot
(date)" then moves to the last trading day.

**Why it is built this way (security):**
- The snapshot is a zip of JSON and Parquet (`ui/snapshot_format.py`), never a pickle, so loading it cannot run
  code.
- The hash it must match is committed on `main`, not next to the data, so a file changed on the data branch alone
  is rejected.

Details:

- **Market holidays:** the prices don't move, so nothing is published.
- **If a build fails** (for example, Yahoo Finance refuses the runner), the app keeps the last published snapshot,
  or the one bundled in the repository if nothing has been published yet.
- **US presets** show their previous session's close, which is their last completed session at 18:00 IST.
- **To run it now:** GitHub → **Actions** → **refresh snapshot** → **Run workflow** (tick *force* to publish even
  when the prices are not newer).
- **Pulling `main` locally:** expect a bot commit of `data/snapshot/published.json` on each trading day.
- **Turning it off:** setting `RISK_TOOL_SNAPSHOT_URL=""` switches the app's check off. GitHub pauses scheduled
  workflows in a public repository after 60 days without activity; re-enable it from the Actions tab.

**Memory.** Streamlit's documentation gives each app 690 MB to 2.7 GB of memory and 0.078 to 2 CPU cores.
`test_deploy.py` starts the app cold in snapshot mode with the network blocked, renders every page of the default
portfolio, and checks the peak memory against the 690 MB minimum. `python scripts/measure_app.py [--live]` prints
the same figures.

## Website on GitHub Pages

The website (`web/`, Next.js static export) shows the app's results for 8 presets in the Summary style. It does no
calculations: `site_data/build.py` runs the app on each preset and writes JSON, and the site renders it. The workflow
`.github/workflows/site.yml` runs the tests, builds the data and the site, and publishes it on every push to main,
weekly, and by hand.

**One-time manual steps:**
1. On GitHub: **Settings → Pages → Build and deployment → Source: GitHub Actions.**
2. Merge `final-v6` into main and push. The first run of the "website" workflow publishes
   https://singhwilliam15.github.io/Risk-Analysis-Tool/.
3. Optional custom domain: Settings → Pages → Custom domain, then build with `NEXT_PUBLIC_BASE_PATH=""`
   (set it as an env value in the workflow's build step).

**Build locally** (Node.js 24 and the Python environment):

```bash
python site_data/build.py          # web/public/data (about 3 minutes; the demo snapshot makes it offline)
cd web && npm ci && npm run build && npm run check
node scripts/serve.mjs              # http://localhost:8600/Risk-Analysis-Tool/
```

**Rules:**
- No NSE lists are published (NSE's terms; [data sources](data_sources.md)). The pledge page shows the tested
  evidence and links to the live app's upload.
- `npm audit` reports advisories in build-time tooling only (Tailwind 3's file watcher and PostCSS). The published
  site is static files, with no server code.

## Manual steps for the rename (review P1)

These need your GitHub and Streamlit accounts, so they are listed here rather than done by a script.

1. **Rename the repository.** GitHub → the repository → **Settings** → **General** → **Repository name**:
   `Risk-Analysis-Tool` (fixing the capital I in "RIsk"). GitHub redirects the old URL, but update links anyway.
2. **Point your clone at it:**
   ```bash
   git remote set-url origin https://github.com/singhwilliam15/Risk-Analysis-Tool.git
   git remote -v
   ```
3. **Streamlit app.** At [share.streamlit.io](https://share.streamlit.io), open the app's **⋮** menu → **Settings**:
   - **General → App URL**: set the custom subdomain `risk-analysis-tool` (giving `risk-analysis-tool.streamlit.app`),
     if it is free;
   - check the app still points at the renamed repository and branch `main`; if not, delete the app and deploy it
     again from the renamed repository (steps above);
   - **Reboot** the app so it picks up the latest commit.
4. **Links in this repository.** Done on 4 Oct 2026: the repository is `singhwilliam15/Risk-Analysis-Tool`, the app
   is at https://risk-analysis-tool.streamlit.app/, and the README links to both. GitHub redirects the old
   repository URL; the old `var-analysis-tool-….streamlit.app` address may stop working, so replace it wherever
   it was shared.
5. **Links elsewhere:** your GitHub profile README, pinned repositories, resume (PDF and any online version),
   LinkedIn (Featured, Projects and the About section), and anything already sent out with the old
   `var-analysis-tool-….streamlit.app` link.

## Manual steps after the October 2026 work (Phases F–H)

These need your GitHub or Streamlit account, so they are listed here rather than done by a script.

1. **Merge `next-steps-v5` into `main` and push.** Until then `main` keeps publishing the old pickle snapshot, and
   the live app keeps reading it.
2. **After the merge:**
   - **Publish the first zip:** GitHub → **Actions** → **refresh snapshot** → **Run workflow**, with *force*
     ticked. It publishes the first zip and commits `data/snapshot/published.json` to `main`.
   - **Check the live app:** open https://risk-analysis-tool.streamlit.app/ and confirm the sidebar shows the new
     date and the Market page shows the "Signals with a tested record" panel. Reboot it once from the app's ⋮ menu if it doesn't.
3. **Delete the merged branches,** locally and on GitHub: `review-fixes-v4` and `full-risk-tool` now, and
   `next-steps-v5` after the merge.
4. **Old repositories:** archive the old VaR-Tool repository (GitHub → Settings → Archive), and decide whether to
   keep Trading-System or Trading_Tool.
5. **Profile README:** update the test count on your GitHub profile (it still says 588).

