"""
Page list and navigation.

Navigation is one keyed radio at the top of the main area rather than st.navigation. Every page shares
one run of the sidebar, data loading and cached calculations, so all pages show the same inputs and
results; and Streamlit's AppTest can switch between radio options, but cannot switch to callable
st.navigation pages, which would leave the pages untested.
"""

import re

import streamlit as st

OVERVIEW = "Overview"
MARKET = "Market"
LIQUIDITY = "Liquidity"
CREDIT = "Credit"
CONCENTRATION = "Concentration & Factors"
EVENTS = "Promoter Pledge & Governance"
INTEGRATED = "Integrated Stress"
DECISIONS = "Decisions"
TRUST = "Trust"
GLOSSARY = "Glossary"
PAGES = (OVERVIEW, MARKET, LIQUIDITY, CREDIT, CONCENTRATION, EVENTS, INTEGRATED, DECISIONS, TRUST, GLOSSARY)
PAGE_KEY = "page"
# Shareable links: ?page=market opens the Market page (slugs: overview, market, liquidity, credit,
# concentration-factors, promoter-pledge-governance, integrated-stress, decisions, trust, glossary; old links
# ?page=event-governance and ?page=events still open the pledge page)
SLUGS = {p: re.sub(r"[^a-z]+", "-", p.lower()).strip("-") for p in PAGES}
ALIASES = {"event-governance": SLUGS[EVENTS], "events": SLUGS[EVENTS], "pledges": SLUGS[EVENTS]}  # renamed in v6 Phase 3


def page_from_url(value) -> str:
    """The page a ?page= value names (slug or title, any case), or None."""
    if not value:
        return None
    wanted = re.sub(r"[^a-z]+", "-", str(value).lower()).strip("-")
    wanted = ALIASES.get(wanted, wanted)
    return next((p for p, slug in SLUGS.items() if slug == wanted), None)


def render_navigation() -> str:
    """The page selector; returns the selected page. The URL's ?page= sets the first page and follows changes."""
    if PAGE_KEY not in st.session_state:
        linked = page_from_url(st.query_params.get("page"))
        if linked:
            st.session_state[PAGE_KEY] = linked
    page = st.radio("Page", PAGES, horizontal=True, key=PAGE_KEY, label_visibility="collapsed")
    if st.query_params.get("page") != SLUGS[page]:
        st.query_params["page"] = SLUGS[page]  # the address bar always holds a link to this page
    return page
