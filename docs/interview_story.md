# The 2-minute story

A script to say out loud: about 330 words, roughly two minutes at a natural pace. Every number comes from the
committed results and is checked by `test_docs.py`. The written version is the
[research note](research_note.md).

---

**1. The problem (20 seconds)**

In an Indian crisis, market, liquidity and credit risk arrive together. Prices fall, the stock locks at its lower
circuit, and lenders sell pledged promoter shares, which pushes the price down further. Most risk tools show these on
separate pages, and few say which of their warning lights have ever worked.

**2. What I built (40 seconds)**

It's a risk tool for Indian and US stocks and portfolios, in Python and Streamlit, with 677 offline tests, plus a
website that publishes its results.

- **Five pillars** (market, liquidity, credit, concentration, and promoter pledges), linked in one stress engine.
  Forced selling moves the price round after round, and an exact Shapley split shows what each pillar adds.
- **A trust layer:** every headline number has a 90% range and an A-to-D grade.
- **Plain language:** every page opens with Clear, Watch or Warning, one sentence, and what to do.

**3. Testing it honestly (45 seconds)**

I tested every warning signal on every NSE stock from 2016 to 2024, delisted ones included, and wrote the rules
down before running each test. The simplest rule won: "down 30% in six months" flagged stocks that crashed 1.78
times as often as average out of sample. My own price flags barely beat chance, so I designed better ones on
2016–18 and tested them once on 2020–24. The best scored 2.26, but not by a margin the test could confirm, so the
app still uses the old flag and says why. Promoter pledges, tested on 27,033 shareholding filings, warn at 1.9
times average and still do among stocks that haven't fallen yet. My own idea, that being near the lenders' trigger
price adds more, was not supported.

**4. What I changed because of the evidence (15 seconds)**

An assumed crash overlay failed its own test, so its default is now zero. When NSE's terms turned out to forbid
automated collection, I stopped downloading, removed their lists from the repository and asked for permission.

---

**Likely CRO questions, and the short answers**

1. *Why Expected Shortfall rather than VaR?* VaR says where the bad tail starts; ES says how bad it is on average
   once you are in it, and it adds up across positions. Basel's market-risk rules moved to ES for that reason.
2. *How do you know the model works?* Every model is backtested out of sample with Kupiec, Christoffersen and the
   McNeil–Frey ES test. The recommended one has the lowest tick loss among those that pass.
3. *Survivorship and look-ahead bias?* NSE's daily files keep delisted stocks, and each filing counts only from the
   day it became public.
4. *Why pre-register?* Testing many rules and reporting the best one finds luck. Committing the rules first, with
   git as the timestamp, makes a failed test count as a failure.
5. *Why Shapley?* It splits a loss exactly across pillars, whatever order they act in; the interaction is what
   appears only when they act together.
6. *Why not add the default probability to equity losses?* The Merton PD is implied from the share price, which the
   scenario already marks down, so it would count the same risk twice. It is a loss only for bonds and loans.
7. *What would you do with more data?* With NSE's permission: a fresh 2025 holdout and a forward ledger that records
   each month's flags before the outcomes are known.
8. *What are the limits?* One market, few crises, overlapping outcomes, and pledges measured with other encumbrances
   before 2025. The ranges are wide, and the tool shows them.
