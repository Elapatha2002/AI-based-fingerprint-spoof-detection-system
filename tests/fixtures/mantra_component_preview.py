"""Isolated browser fixture for the Mantra custom component."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "app"))

import streamlit as st
from components.mantra_capture import render_mantra_capture

st.set_page_config(page_title="Mantra component fixture")
st.title("Mantra capture fixture")
payload = render_mantra_capture(bridge_url="http://127.0.0.1:18766")
if payload:
    st.success(f"Received capture {payload.get('capture_id')}")
