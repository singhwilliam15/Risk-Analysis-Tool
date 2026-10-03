# Deploying and renaming

## Deploy on Streamlit Community Cloud

The entry point is `app.py`, the requirements are pinned and no secrets are needed.

1. Sign in at [share.streamlit.io](https://share.streamlit.io) with the GitHub account that owns the repository.
2. Click **Create app** → **Deploy a public app from GitHub**.
3. Pick the repository, branch `main`, main file `app.py`.
4. Under **Advanced settings**, choose **Python 3.11 or 3.12**. The demo snapshot works on both: it needs the same
   pandas version (pinned) and numpy major version, and is ignored otherwise.
5. Click **Deploy**. The first build takes a few minutes.

**Demo snapshot.** The repository ships `data/snapshot/snapshot.pkl.gz`: the presets with the default settings,
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
offline (`test_snapshot.py`, `test_deploy.py`) and publishes it on the `snapshot-data` branch. That branch holds
`snapshot.pkl.gz`, a `meta.json` with its sha256, and a single commit that is replaced on every publish, so the
repository does not grow. The running app reads `meta.json` every 15 minutes and swaps in a newer snapshot. The
sidebar's "Demo snapshot (date)" then moves to the last trading day without a redeploy or reboot. Details:

- **Market holidays:** the prices don't move, so nothing is published.
- **If a build fails** (for example, Yahoo Finance refuses the runner), the app keeps the last published snapshot,
  or the one bundled in the repository if nothing has been published yet.
- **US presets** show their previous session's close, which is their last completed session at 18:00 IST.
- **To run it now:** GitHub → **Actions** → **refresh snapshot** → **Run workflow** (tick *force* to publish even
  when the prices are not newer).
- **Turning it off:** setting `RISK_TOOL_SNAPSHOT_URL=""` switches the app's check off. GitHub pauses scheduled
  workflows in a public repository after 60 days without activity; re-enable it from the Actions tab.

**Memory.** Streamlit's documentation gives each app 690 MB to 2.7 GB of memory and 0.078 to 2 CPU cores.
`test_deploy.py` starts the app cold in snapshot mode with the network blocked, renders every page of the default
portfolio, and checks the peak memory against the 690 MB minimum. `python scripts/measure_app.py [--live]` prints
the same figures.

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
