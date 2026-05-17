"""
SCITE App — Streamlit entry point for cframe-based course.

Run with:
    streamlit run scite/scite_app/app.py
or:
    ./scripts/run_scite_app.sh
"""
import streamlit as st

st.set_page_config(
    page_title="SCITE — Structural Concrete Interactive Teaching",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded",
)

from cframe import AppFrame

from scite.scite_app.registry import PARTS

AppFrame(
    title="SCITE",
    icon="🏗️",
    subtitle="Structural Concrete Interactive Teaching Environment",
    parts=PARTS,
).activate()
