"""Manual/browser fixture for the invisible session-cookie component."""
import streamlit as st

from app.components.session_cookie import sync_session_cookie

st.set_page_config(page_title="Session cookie fixture")
action = st.query_params.get("action", "read")
if action == "set":
    sync_session_cookie(
        name="fsdxai_session_fixture", value="signed-fixture-value",
        max_age=300, secure=False, key="fixture_cookie",
    )
elif action == "clear":
    sync_session_cookie(
        name="fsdxai_session_fixture", value="",
        max_age=300, secure=False, key="fixture_cookie",
    )

value = st.context.cookies.get("fsdxai_session_fixture", "missing")
st.write(f"COOKIE={value}")
