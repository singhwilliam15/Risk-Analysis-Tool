# Risk Analysis Tool — Final Plan (v6)

This plan merges everything still open after v5:
- the data download for every disclosure input,
- the remaining tests (a fresh 2025 holdout, margin-trigger distance, the newly downloaded signals) and a forecast ledger,
- an evidence-led early-warning panel and a slimmer, pledge-centred event pillar,
- a presentation that is easy to read but keeps every technical term (in brackets), so it reads as rigorous,
- the website, the research note, the interview story and final housekeeping.

It replaces PLAIN_LANGUAGE_REDESIGN.md and WEBSITE_PLAN.md. Both are folded in below.

---

## Master prompt (paste into Claude Code)

```
Read docs/plans/FINAL_PLAN_V6.md (move this file there first). Work through Phases 1–6 in order,
ONE phase at a time: plan mode → my approval → implement → pytest → run the app and send me
screenshots of anything visible that changed → commit → summary with real numbers → STOP.
Branch: `final-v6`. Never push.

PERMISSION FOR DOWNLOADS: you have my standing permission to download every public input this plan
needs (NSE, BSE, SEBI, RBI and rating-agency public pages and archives) without asking me first,
within these limits:
- public pages and files only; no logins, no paywalls, no CAPTCHA solving or bypassing, no
  evading blocks;
- respect robots.txt and each site's terms; send an honest User-Agent; at most about 1 request per
  second per site, with retries and backoff; resume safely after an interruption;
- if a source blocks scripts or its terms forbid automated download, log it, skip it, continue, and
  put it on a manual checklist for me at the end of the phase.

Project rules stay in force: point-in-time data only (each record counts from its public date),
never invent or fill data from memory, label every assumption, pre-register every test before
computing its results, offline tests against independent references, and update the README,
methodology and case studies after each phase. No calculation changes in the presentation phase.

If you disagree with any instruction after reading the code, tell me with evidence first.

Start with Phase 1.
```

---

## Phase 1 — Download every disclosure input (data completeness)

```
Phase 1 of FINAL_PLAN_V6.md. Extend scripts/fetch_disclosures.py and nse_sources.py, or add new
fetchers, so that every event and credit signal has the deepest history the official sources serve.
For each dataset: find the official source, download, parse, validate, keep the source URL per row,
and record coverage (first date, last date, companies, gaps) in data/disclosures/manifest.json.

1. Promoter pledges and encumbrance:
   - refresh NSE shareholding XBRL through the latest quarter (2025–2026);
   - for pre-2021 history, try BSE quarterly shareholding-pattern filings and NSE's SAST
     Regulation 31 (encumbrance) disclosures, for every NSE company if the source allows, or at
     least the case-study companies and controls (Zee, Jet Airways, Future Retail, DHFL, Yes Bank,
     Adani Enterprises and the 10 controls);
   - keep "pledged" and "otherwise encumbered" separate wherever the filing separates them.
2. Auditor events: from exchange corporate announcements (Regulation 30), collect statutory-auditor
   resignations, and statements on impact of audit qualifications / modified opinions filed with
   annual results. Classify each as resignation / qualified / adverse / disclaimer, with the
   announcement date and link. Show me 20 random classified rows to check before using them.
3. Credit rating actions: from exchange announcements (rating disclosures under Regulation 30) and,
   where needed, the rating agencies' public rating-rationale pages (CRISIL, ICRA, CARE, India
   Ratings, Acuité). Record agency, instrument, old → new rating, outlook/watch, date, link.
4. Surveillance (ASM/GSM): find whether NSE/BSE publish historical lists (daily files, circulars or
   archives). Download what exists. If only current lists exist, start recording them daily from
   now (Phase 2 ledger) and say so.
5. F&O ban list: every daily file from NSE's archive, 2016 to today.
6. Price bands: daily or change-based history from NSE's archives if available; otherwise keep the
   current file and label historical bands "inferred from prices".
7. Group links: derive business groups from the promoter entities named in shareholding XBRL
   (companies sharing a promoter or promoter holding company). Label them "derived", show the
   evidence (shared entity names), and let the user override in the holdings table.
8. Banks and NBFCs: refresh the latest quarter for the preset banks, and extend the PCA module's
   data to every listed bank (results XBRL and Basel III Pillar 3 disclosures), point in time.
9. Prices: extend the NSE bhavcopies to the latest trading day (needed for the 2025 holdout).
10. LICENSING: read the terms of use of NSE, BSE and each agency. Write docs/data_sources.md with,
   per source, what may be redistributed. Commit raw downloads ONLY where redistribution is allowed;
   otherwise keep raw files out of git (data/raw/, git-ignored, rebuilt by the scripts) and commit
   only derived summaries the terms allow. Apply this to the existing 6.9 MB shareholding extract too.
11. Tests: parsers on saved sample files from every source; classification of auditor events and
   rating actions against hand-labelled samples; point-in-time selection.

End of phase: a coverage table (dataset × years × companies) and the manual checklist of anything
blocked.
```

---

## Phase 2 — Evidence: fresh holdout, new tests, forecast ledger

```
Phase 2 of FINAL_PLAN_V6.md. Pre-register everything in docs/preregistration_v6.md and commit it
BEFORE computing any result. One stage per commit: pre-registration → design (if any) → test.

1. FRESH 2025 HOLDOUT (never used before): month-ends Jan–Sep 2025, outcome a ≥ 50% fall within
   12 months (prices through Sep 2026 or later). Rules, frozen exactly as they are now:
   v1 any price flag; R2 peer-relative ES; R4 combined score (frozen model, no refit);
   E1 encumbered ≥ 50%; E2 encumbrance up ≥ 10 pp in 4 quarters; momentum (a); and one new
   combined rule fixed now: C1 = momentum OR E1 OR R2. Metrics as in Phase F (lift with block-
   bootstrap 90% ranges, incremental lift among stocks not down 30%, liquid subset). State clearly
   that 9 month-ends of one regime give limited power.
2. MARGIN-TRIGGER DISTANCE (new, original): among stock-dates with encumbrance ≥ 20%, does being
   CLOSE to the pledge margin-call trigger predict a ≥ 50% fall better than encumbrance alone?
   Distance = how far the price must fall before lenders could sell, using the tool's margin-call
   model (loan sized at the price on the filing date). Pre-register the cover assumptions
   (2× initial, 1.5× trigger, plus the 1.75×/1.25× sensitivity), the bins (e.g. < 10%, 10–25%,
   > 25% fall to trigger) and the test. Run on 2022–2024 and on the 2025 holdout.
3. NEWLY DOWNLOADED SIGNALS: for each signal Phase 1 obtained with enough history (auditor events,
   rating downgrades, surveillance, F&O bans, derived group links, pre-2021 pledges), pre-register a
   rule (the existing thresholds in config/event_rules.json) and test it on every NSE stock over its
   available years: lift, incremental lift beyond momentum, and the case-study dates (Zee, Jet,
   Future Retail, DHFL, Yes Bank) if pre-2021 data now exist. Signals still without history stay
   labelled "not back-tested".
4. FORECAST LEDGER (prospective test): a GitHub Actions workflow on the first trading day of each
   month that computes, for every NSE stock, all flags (v1, R2, R4, E1, E2, C1, momentum, event tier)
   and the margin-trigger distance, and APPENDS them to ledger/forecasts_YYYY-MM.csv (never edits
   past files), plus a daily snapshot of the current ASM/GSM lists if no history exists. A script
   scores matured forecasts (12 months later) and the README shows "forecasts made / matured / hit
   rate". The git history is the timestamp proof.
5. Decisions, as pre-registered, feed Phase 3: which signals count as "tested, works", "tested,
   does not beat momentum", "tested, no effect" or "not back-tested".
```

---

## Phase 3 — Evidence-led warnings and a pledge-centred event pillar

```
Phase 3 of FINAL_PLAN_V6.md. Use the Phase 2 results; change no thresholds that were tested.

1. EARLY-WARNING PANEL = "Signals with a tested record". For each stock or holding, list every
   signal with: whether it fires now; its tested lift with 90% range and test period; its incremental
   lift beyond momentum; and an evidence badge: Tested · works / Tested · weaker than momentum /
   Tested · no effect / Not back-tested. Order by evidence strength. The pre-registered decision on
   which rule is the "official" market flag is unchanged and shown, with v1 labelled the legacy rule.
2. RENAME AND RESTRUCTURE the pillar to "Promoter Pledge & Governance Risk":
   - the core, at the top: pledge level, 4-quarter change, margin-call trigger price and distance,
     and forced selling in days of volume, with the tested evidence;
   - "Other red flags": surveillance, rating actions, auditor events, F&O ban and group links, each
     with its evidence badge from Phase 2;
   - the jump overlay moves into the analyst details, labelled "off by default (0), see
     methodology §12.4", with its sensitivity grid. No ES cards in the summary while it is 0.
3. Missing data: one coverage line per page ("Checked 7 of 8 items · Not checked: … · Data as of
   …"). A warning box only for a fixable gap (a file that should be loaded and is not).
```

---

## Phase 4 — Presentation: clear for anyone, rigorous for a CRO

```
Phase 4 of FINAL_PLAN_V6.md. Presentation only: no calculation, rule or number changes.

PRINCIPLES
- Answer first: every page opens with the question it answers, a one-line verdict and a status
  word (Clear / Watch / Warning, with colour as a second signal, never the only one).
- Plain words WITH the technical term in brackets, the first time on each page and in every
  heading and card title, e.g.
    "Bad-day loss (95% 1-day VaR)",
    "Average loss on the worst days (Expected Shortfall, 95%, 1-day)",
    "Owners' shares pledged for loans (promoter pledge / encumbrance)",
    "On NSE's watch-list (ASM / GSM surveillance)",
    "Distance from default (Merton distance to default)",
    "How reliable this number is (trust grade A–D)",
    "Extra loss when risks hit together (interaction effect, Shapley split)".
  Never remove a technical term; never replace precision with vagueness.
- Rigour stays visible, so the simple view never looks weak:
  - under each headline number, one small method line: e.g. "Model: GARCH(1,1)-t, chosen by
    out-of-sample tick loss; passes Kupiec, Christoffersen and McNeil–Frey tests · Methodology §4";
  - evidence chips: "Tested on 2,165 NSE companies, 2022–24: 1.9× crash rate (1.6–2.2)";
  - precise numbers with units and context: "₹36,070 on ₹10 lakh (3.6%)";
  - the trust grade as a badge with a popover of its reasons (no repeated deduction text under
    cards; no grade or range on values fixed by an assumption);
  - a professional, report-like style: no emojis in headings, consistent typography, restrained
    colour, tables aligned, sources and as-of dates on every page.
- Two views via a sidebar switch: "Summary" (default) and "Full analysis". Summary shows the verdict,
  3–4 facts with "so what", "What to do", evidence chips and method lines, with "Show the full
  analysis" expanders. Full analysis shows everything as today. Nothing is deleted.

PHASES INSIDE
4a. ui/plain.py: one vocabulary dictionary (plain phrase, technical term, one-line definition,
    methodology anchor) and helpers: verdict(), fact(), action(), method_line(), evidence_chip(),
    coverage_line(), grade_badge(), details().
4b. Pilot on the Promoter Pledge & Governance page for Asian Paints, Jaiprakash Power and the 5-stock
    portfolio. Send screenshots of both views and WAIT for my feedback.
4c. All other pages: Overview (one verdict row per pillar), Market ("On a bad day (95% 1-day VaR)
    you could lose about ₹X (Y%)"), Liquidity ("You could sell it all in N days (days to
    liquidate, 20% participation)"), Credit ("Credit health: strong (Merton DD 20.9, 96th
    percentile)"; banks: "X pp above RBI's intervention level (PCA risk threshold 1)"),
    Concentration & Factors, Integrated Stress ("In a 2008-style crash: −₹X; risks hitting together
    add ₹Y (interaction effect)"), Decisions, Trust.
4d. A Glossary page from the vocabulary dictionary (plain phrase, technical term, definition,
    formula, link to methodology) and a dismissible "How to read this tool" note on Overview.
4e. The CRO memo keeps full technical wording, with the plain verdicts as its first paragraph.
Tests: every page renders in both views; each page starts with a verdict and status word; every
vocabulary term appears with its technical term in brackets at first use; no warning box for data
missing by design; a word limit for the Summary text above the first expander.
```

---

## Phase 5 — Website (from the earlier website plan, now in Summary style)

```
Phase 5 of FINAL_PLAN_V6.md. A static website fed by JSON from the Python engine; the site does no
calculations.

1. site_data/build.py: run the engine for the presets (RELIANCE.NS, HDFCBANK.NS, TCS.NS,
   ASIANPAINT.NS, BRITANNIA.NS, Jaiprakash Power, AAPL, the 5-stock portfolio at ₹10 lakh and
   ₹50 crore) and write web/public/data/<preset>/<page>.json: verdicts, facts, method lines,
   evidence chips, tables, Plotly figure JSON, sources and as-of dates. JSON schemas and tests.
   Keep the last good JSON if a fetch fails and mark it stale.
2. web/: Next.js (static export), TypeScript, Tailwind, Plotly.js. Pages: Home, Market, Liquidity,
   Credit, Concentration & Factors, Promoter Pledge & Governance, Integrated Stress, Evidence (case
   studies, wider tests, 2025 holdout, forecast ledger), Methodology, Glossary, About. A preset
   switcher on every page; "Try it live" links to the Streamlit app.
3. Same presentation rules as Phase 4 (plain words with technical terms in brackets, method lines,
   evidence chips, grade badges). Report-like design, light and dark, mobile-friendly, Lighthouse
   performance and accessibility ≥ 90.
4. GitHub Actions: tests → data build → site build → deploy to GitHub Pages, on push and weekly.
   List the manual steps for me (enable Pages; optional custom domain).
```

---

## Phase 6 — Research note, story and final housekeeping

```
Phase 6 of FINAL_PLAN_V6.md.

1. RESEARCH NOTE (docs/research_note.md and a PDF, 6–8 pages):
   "What predicts 50% crashes in Indian stocks? Evidence from every NSE stock, 2016–2025."
   Sections: question; data (bhavcopies with delisted stocks, shareholding XBRL, disclosures;
   point in time); method (pre-registration, design/embargo/test, block bootstrap, incremental lift);
   results (momentum, tail-risk rules, pledges, margin-trigger distance, the 2025 holdout, the other
   signals); what failed; limitations; how the tool uses it. Every number read from the results
   files by a script, so the note cannot drift from the data. Cite sources and methods.
2. INTERVIEW STORY: update docs/interview_story.md (2 minutes) around the strongest tested result
   and the honest negatives, plus 8 likely CRO questions with short answers.
3. README: a one-screen opening (pitch, website link, live app link, 3 screenshots in Summary view,
   6 findings with evidence ranges), then the feature table with plain words and technical terms.
   All numbers checked by test_docs.py.
4. HOUSEKEEPING: all plan files in docs/plans/; delete stale files; confirm the snapshot workflow,
   the forecast ledger workflow and the site workflow all pass; list the manual steps for me
   (delete merged branches, archive the old VaR-Tool repo, choose between Trading-System and
   Trading_Tool, check the live app and the website).
```

---

## What you get at the end

- **Complete inputs:** every disclosure dataset the official sources serve, with provenance and a
  licensing decision per source.
- **Evidence:** a fresh 2025 holdout, an original margin-trigger test, tests of every signal that has
  history, and a live forecast ledger that proves itself over time.
- **A tool anyone can read and a CRO can respect:** plain verdicts, technical terms in brackets,
  method lines and evidence chips on every number.
- **Distribution:** a website, a research note, and an interview story built on tested results.
