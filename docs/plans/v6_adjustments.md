# FINAL_PLAN_V6: adjustments for working without NSE data (12 Oct 2026)

NSE's Terms of Use forbid automated collection and redistribution without its written permission
([data sources](../data_sources.md)). The owner decided to continue without NSE data rather than wait for a reply.

| Plan item | Change |
| --- | --- |
| Phase 1: download every disclosure input | Stopped (see the Phase 1 checklist). |
| Current NSE lists in the repo (pledges, bands, surveillance, F&O ban, ratings) | Untracked on 12 Oct 2026; users upload their own in the app. Without files the pledge page says "not checked". |
| Phase 2.1: fresh 2025 holdout | **Dropped.** It needs NSE prices through Sep 2026 and new shareholding filings. Yahoo prices are not a substitute: they lack delisted stocks, which would bias crash rates down. Would run with NSE's permission. |
| Phase 2.2: margin-trigger distance | **Kept, on 2022–24 only**, from the data already held locally; only summary statistics are committed. Pre-registered first. |
| Phase 2.3: newly downloaded signals | **Dropped** (nothing new was downloaded). Those signals stay "not back-tested". |
| Phase 2.4: forecast ledger | **Dropped.** A monthly job pulling NSE files is automated collection. Would run with NSE's permission. |
| Phase 5: website | Built from the app's own output; the Evidence page shows the existing tests and the margin-trigger result, with no holdout or ledger. |
| Phase 6: research note | Covers 2016–2024; the limitations section explains the data access. |

Git history still contains the files committed before these dates; rewriting history is a separate decision.
