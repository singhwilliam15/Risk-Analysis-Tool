# Screenshots

Images used in the README and the research note. No NSE data appears in them: the app was run with an empty
disclosure folder.

| File | What it shows | Made by |
| --- | --- | --- |
| `summary-overview.png` | The app's Overview page in the Summary view, default 5-stock portfolio at ₹10 lakh (prices to 9 Oct 2026) | Playwright, 12 Oct 2026 |
| `summary-market.png` | The app's Market page in the Summary view, same portfolio | Playwright, 12 Oct 2026 |
| `website-evidence.png` | The website's Evidence page: every signal and its tested record | Playwright, 12 Oct 2026 |
| `research_lifts.png` | Lift with 90% ranges for every tested signal | `scripts/build_research_note.py` |
| `case_studies.png` | Realised loss after each case-study date, red where the tool warned | `case_studies/run.py` |

To refresh the screenshots, run the app (`streamlit run app.py`) and capture the same pages in the Summary view.
