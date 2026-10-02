"""Browser-side Streamlit component for the local MFS100 bridge."""
from pathlib import Path

import streamlit.components.v1 as components

_FRONTEND = Path(__file__).with_name("mantra_capture_frontend")
_component = components.declare_component("fsd_mantra_capture", path=str(_FRONTEND))


def render_mantra_capture(*, bridge_url: str, key: str = "mantra_capture"):
    """Render pairing/capture controls and return a captured payload, if any.

    The pairing token remains inside browser localStorage and is never sent to
    the hosted Streamlit Python process.
    """
    return _component(bridge_url=bridge_url, key=key, default=None)
