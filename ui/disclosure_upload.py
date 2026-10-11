"""
Upload disclosure files in the app. The repository ships no NSE lists (NSE's terms reserve redistribution for its
written permission; docs/data_sources.md), so the user downloads them from NSE, BSE or the rating agencies and uploads
them here. Uploads last for the session and feed every page through ui/foundations.py.
"""

import pandas as pd
import streamlit as st

from disclosures import DATASETS

UPLOADS_KEY = "disclosure_uploads"  # session state: [{"name", "dataset", "as_of", "content"}]


def uploads() -> list:
    return st.session_state.get(UPLOADS_KEY, [])


def render(key: str) -> None:
    """Dataset, as-of date and file; 'Add' stores the file for the session and reruns so every page uses it."""
    st.markdown("**Add your own files.** Download a list from the official source (Overview → Disclosure data → "
                "Where each dataset comes from) and upload it unchanged, or copy its rows into the template.")
    c1, c2 = st.columns(2)
    dataset = c1.selectbox("Dataset", list(DATASETS), format_func=lambda n: DATASETS[n].title, key=f"{key}_dataset")
    as_of = c2.date_input("List date (for files without a date column)", value=pd.Timestamp.today().date(),
                          key=f"{key}_as_of")
    files = st.file_uploader("Disclosure files", type="csv", accept_multiple_files=True, key=f"{key}_files")
    b1, b2 = st.columns(2)
    if b1.button("Add the files", key=f"{key}_add", disabled=not files):
        st.session_state[UPLOADS_KEY] = uploads() + [
            {"name": f.name, "dataset": dataset, "as_of": str(as_of), "content": f.getvalue()} for f in files]
        st.rerun()
    if uploads():
        st.caption("Uploaded this session: " + ", ".join(f"{u['name']} ({DATASETS[u['dataset']].title})" for u in uploads()))
        if b2.button("Remove uploaded files", key=f"{key}_clear"):
            st.session_state[UPLOADS_KEY] = []
            st.rerun()
