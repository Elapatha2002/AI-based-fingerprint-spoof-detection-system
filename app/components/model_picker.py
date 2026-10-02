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
import json
import os
from pathlib import Path
from html import escape

import streamlit as st


# Test-metrics JSON files land in <project_root>/results/, named
# "<checkpoint_folder>_test_metrics.json" (see src/training/train.py).
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_RESULTS_DIR = _PROJECT_ROOT / "results"


def _load_test_metrics(checkpoint_short: str) -> dict | None:
    """Return the test-metrics dict for a checkpoint folder name, or None if
    no matching file exists. Falls back gracefully — the picker still works
    for checkpoints that don't have a metrics file yet."""
    if not checkpoint_short:
        return None
    path = _RESULTS_DIR / f"{checkpoint_short}_test_metrics.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None


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

    from app.services.model_config import (
        checkpoint_state, configured_selection, list_available_checkpoints,
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
    current_arch, current_checkpoint = configured_selection(st.session_state)
    current_path = str(current_checkpoint)

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

    # Configuration pages must not load a 100+ MB checkpoint on every rerun.
    # Actual loading is on first analysis or the explicit validation button.
    try:
        checkpoint = Path(chosen["path"])
        state, state_label = checkpoint_state(checkpoint)
        checkpoint_short = checkpoint.parent.name
        metrics = _load_test_metrics(checkpoint_short)

        # Build the test-metrics lines only if we have a metrics file for
        # this checkpoint (some older or in-progress checkpoints won't).
        metric_lines = ""
        if metrics:
            acc = metrics.get("accuracy")
            auc = metrics.get("roc_auc")
            ace = metrics.get("ace")
            if acc is not None:
                metric_lines += (
                    f"Accuracy &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;:&nbsp; "
                    f"<b>{acc:.2%}</b><br/>"
                )
            if auc is not None:
                metric_lines += (
                    f"AUC &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;:&nbsp; "
                    f"{auc:.4f}<br/>"
                )
            if ace is not None:
                metric_lines += (
                    f"ACE &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;:&nbsp; "
                    f"{ace:.2f}%<br/>"
                )
        else:
            metric_lines = (
                "Accuracy &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;:&nbsp; "
                "<span style='color:var(--text-muted);'>no test metrics on "
                "file for this checkpoint</span><br/>"
            )

        st.markdown(
            f"""
            <div class='fsd-card'>
              <div class='fsd-card-title'>Configured model</div>
              <div class='fsd-mono' style='font-size:13px;line-height:1.8;'>
                Architecture &nbsp;:&nbsp; <b>{escape(chosen['arch'])}</b><br/>
                Checkpoint &nbsp;&nbsp;&nbsp;:&nbsp; {escape(checkpoint_short)}<br/>
                File status &nbsp;&nbsp;:&nbsp; {escape(state_label)}<br/>
                Loading &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;:&nbsp; on first analysis<br/>
                {metric_lines}
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("Validate model now", key="validate_selected_model"):
            if state != "ready":
                st.error(
                    "Model data is unavailable. Run 'git lfs install' and "
                    "'git lfs pull', then restart the application."
                )
            else:
                try:
                    from app.services.real_model import get_service_info
                    with st.spinner("Loading and validating model..."):
                        svc = get_service_info()
                    st.success(f"{svc['name']} loaded successfully on {svc['device']}.")
                except Exception as error:
                    st.error(f"Model validation failed: {type(error).__name__}: {error}")
    except Exception as e:
        st.markdown(
            f"<div class='fsd-banner error'>"
            f"Could not read model configuration: {type(e).__name__}: {escape(str(e))}"
            f"</div>",
            unsafe_allow_html=True,
        )
