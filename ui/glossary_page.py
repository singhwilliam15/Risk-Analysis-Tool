"""Glossary (FINAL_PLAN_V6 Phase 4): every term the tool uses, in plain words with its technical name and method."""

import pandas as pd
import streamlit as st

from ui.plain import VOCAB

METHODOLOGY_URL = "https://github.com/singhwilliam15/Risk-Analysis-Tool/blob/main/docs/methodology.md"


def table() -> pd.DataFrame:
    return pd.DataFrame([{"In plain words": p, "Technical term": t, "What it means": d, "Methodology": a}
                         for p, t, d, a in VOCAB.values()])


def render(ctx=None):
    st.subheader("Glossary")
    st.caption("Every page shows plain words first and the technical term in brackets. The sections refer to the "
               f"[methodology]({METHODOLOGY_URL}), which gives the formulas, sources and tests.")
    st.table(table().set_index("In plain words"))  # a static table wraps the definitions instead of cutting them
