"""Model picker for the Settings / About page.

Renders only when the app is in real mode (FSDXAI_REAL_MODEL=1).
Lists every checkpoint found under <project>/checkpoints/ and lets the
user switch between them at runtime. The selection is stored in
st.session_state and read by real_model.get_service_info() on the next
inference call.

Switching models is cheap if the new model has already been loaded once:
@st.cache_resource keeps every (model_name, checkpoint_path) combo in
memory across reruns.
"""
import os
import streamlit as st


def render_model_picker():
    """Render the picker only in real mode. Otherwise no-op."""
    if os.environ.get("FSDXAI_REAL_MODEL") != "1":
        st.markdown(
            "<div class='fsd-banner info'>"
            "Mock mode active — set <code>FSDXAI_REAL_MODEL=1</code> "
            "and relaunch to enable the model picker."
            "</div>",
            unsafe_allow_html=True,
        )
        return

    from services.real_model import (
        list_available_checkpoints, get_service_info,
    )

    options = list_available_checkpoints()
    if not options:
        st.markdown(
            "<div class='fsd-banner warn'>"
            "No checkpoints found in <code>checkpoints/</code>. "
            "Train a model first."
            "</div>",
            unsafe_allow_html=True,
        )
        return

    # Current active checkpoint (from session state OR env var)
    current_arch = (
        st.session_state.get("selected_model")
        or os.environ.get("FSDXAI_MODEL", "mobilenetv3_large")
    )
    current_path = (
        st.session_state.get("selected_checkpoint")
        or os.environ.get(
            "FSDXAI_CHECKPOINT",
            options[0]["path"] if options else "",
        )
    )

    labels = [f"{o['arch']}  ·  {o['folder']}" for o in options]
    current_idx = 0
    for i, o in enumerate(options):
        if o["path"] == current_path:
            current_idx = i
            break
        if o["arch"] == current_arch:
            current_idx = i        # tentative match by arch

    chosen_label = st.selectbox(
        "Active model",
        labels,
        index=current_idx,
        key="model_picker_select",
        help="Switch the model used for predictions and XAI in real time.",
    )
    chosen = options[labels.index(chosen_label)]

    # If selection changed, update session state and clear data caches
    changed = (
        chosen["arch"] != current_arch
        or chosen["path"] != current_path
    )
    if changed:
        st.session_state.selected_model = chosen["arch"]
        st.session_state.selected_checkpoint = chosen["path"]
        st.cache_data.clear()       # invalidate cached predictions / XAI
        st.toast(f"Switched to {chosen['arch']}", icon="🔄")
        st.rerun()

    # Show what's currently loaded (this also triggers initial load)
    try:
        svc = get_service_info()
        st.markdown(
            f"""
            <div class='fsd-card'>
              <div class='fsd-card-title'>Currently loaded</div>
              <div class='fsd-mono' style='font-size:13px;line-height:1.8;'>
                Architecture &nbsp;:&nbsp; <b>{svc['name']}</b><br/>
                Checkpoint &nbsp;&nbsp;&nbsp;:&nbsp; {svc['checkpoint_short']}<br/>
                Device &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;:&nbsp; {svc['device']}
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    except Exception as e:
        st.markdown(
            f"<div class='fsd-banner error'>"
            f"Failed to load model: {type(e).__name__}: {e}"
            f"</div>",
            unsafe_allow_html=True,
        )
