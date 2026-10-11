"""
One coverage line per page (FINAL_PLAN_V6 Phase 3): "Checked 7 of 8 items · Not checked: … · Data as of …".

A warning box is shown only for a fixable gap: a file the page needs that the user has not loaded or uploaded. Items missing by
design (no permitted source, a pillar that does not apply) are listed in the line, not warned about.
"""

import streamlit as st


def coverage_text(checked: list, not_checked: dict, as_of: str = None) -> str:
    """checked: item names; not_checked: {item: reason}."""
    total = len(checked) + len(not_checked)
    parts = [f"Checked {len(checked)} of {total} items"]
    if not_checked:
        parts.append("Not checked: " + "; ".join(f"{k} ({v})" if v else k for k, v in not_checked.items()))
    if as_of:
        parts.append(f"Data as of {as_of}")
    return " · ".join(parts)


def coverage_line(checked: list, not_checked: dict, as_of: str = None, fixable: list = None) -> None:
    """Print the line; add a warning only for fixable gaps (files that should be loaded and are not)."""
    st.caption(coverage_text(checked, not_checked, as_of))
    if fixable:
        st.warning("Not loaded: " + ", ".join(fixable) + ". NSE's terms do not allow this project to republish its "
                   "lists, so download them from NSE and upload them (Overview → Disclosure data, or the upload at the "
                   "top of this page); they stay in your session.")
