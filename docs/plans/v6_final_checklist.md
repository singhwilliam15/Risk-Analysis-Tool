# Final checklist (owner's manual steps, October 2026)

Everything in FINAL_PLAN_V6 that could be automated is done: the app, the website and the research note are live
and tested. These steps need the owner.

1. **Send the NSE permission request.** The draft is in [docs/permissions/nse_permission_request.md](../permissions/nse_permission_request.md).
   With permission, the 2025 holdout and the forward ledger can run ([v6 adjustments](v6_adjustments.md)).
2. **Renew the GitHub command-line login** (`gh auth login --web`). The saved login has expired; it is needed for the
   repository About box and the profile update below.
3. **Repository About box:** add the website, https://singhwilliam15.github.io/Risk-Analysis-Tool/, as the repository
   website (repository page → the gear next to About).
4. **GitHub profile README:** add the website and the research note links.
5. **Delete the merged `final-v6` branch** (on GitHub and locally) once you no longer need it.
6. **Check the live app and the website** after each push: https://risk-analysis-tool.streamlit.app/ and the website.
7. **Optional:** post the walkthrough videos and link them from the README, the profile and the app.
8. **Optional:** decide whether to rewrite git history to remove the NSE files committed before October 2026
   ([data sources](../data_sources.md)).
