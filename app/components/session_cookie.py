"""Invisible browser component used to persist a signed login session."""
from pathlib import Path

import streamlit.components.v1 as components

_FRONTEND = Path(__file__).with_name("session_cookie_frontend")
_component = components.declare_component("fsdxai_session_cookie", path=str(_FRONTEND))


def sync_session_cookie(*, name: str, value: str, max_age: int,
                        secure: bool, key: str) -> None:
    _component(
        name=name,
        value=value,
        max_age=max_age,
        secure=secure,
        key=key,
        default=None,
    )
