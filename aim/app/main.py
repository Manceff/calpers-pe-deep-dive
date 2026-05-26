"""
Streamlit app — CalPERS Private Equity Deep Dive.

Lancement :
    streamlit run aim/app/main.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from aim.app.config import APP_SUBTITLE, APP_TITLE, FIXED_SNAPSHOT, GLOBAL_CSS  # noqa: E402
from aim.app.tabs import t1_cockpit, t2_allocation, t3_fonds, t4_vintages, t5_pme, t6_data  # noqa: E402

st.set_page_config(
    page_title="CalPERS Private Equity",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="collapsed",
    menu_items={"Get help": None, "Report a bug": None, "About": None},
)

st.markdown(GLOBAL_CSS, unsafe_allow_html=True)


def main() -> None:
    # Snapshot figé — pas de filtres globaux
    st.session_state["snapshot"] = pd.Timestamp(FIXED_SNAPSHOT)

    # Hero
    st.markdown(
        f"""
        <div class="aim-hero">
          <div class="aim-hero-title">{APP_TITLE}</div>
          <div class="aim-hero-subtitle">{APP_SUBTITLE}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    tabs = st.tabs([
        "Cockpit",
        "Allocation",
        "Fonds",
        "Millésimes",
        "PME",
        "Données",
    ])
    with tabs[0]:
        t1_cockpit.render()
    with tabs[1]:
        t2_allocation.render()
    with tabs[2]:
        t3_fonds.render()
    with tabs[3]:
        t4_vintages.render()
    with tabs[4]:
        t5_pme.render()
    with tabs[5]:
        t6_data.render()


if __name__ == "__main__":
    main()
