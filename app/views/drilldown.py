"""Screen 6 — Drill-down (reuses single_result with a back/prev/next strip)."""
import streamlit as st
from views import single_result


def render():
    batch = st.session_state.get("current_batch")
    filtered = st.session_state.get("drilldown_filtered")
    idx = st.session_state.get("drilldown_idx", 0)

    if not batch or not filtered:
        st.warning("No drill-down context.")
        if st.button("Back to dashboard"):
            st.session_state.current_page = "batch_dashboard"
            st.rerun()
        return

    idx = max(0, min(idx, len(filtered) - 1))

    # Breadcrumb / back row
    cols = st.columns([1, 4, 1, 1, 1])
    with cols[0]:
        if st.button("◀ Back", use_container_width=True, key="dd_back"):
            st.session_state.current_page = "batch_dashboard"
            st.rerun()
    with cols[1]:
        st.markdown(
            f"<div class='fsd-mono' style='padding:8px 0;color:var(--text-muted);'>"
            f"{batch['meta']['case_id']} / {filtered[idx]['filename']}</div>",
            unsafe_allow_html=True,
        )
    with cols[2]:
        st.markdown(
            f"<div style='text-align:right;padding:8px 0;color:var(--text-secondary);'>"
            f"Image {idx + 1} of {len(filtered)}</div>",
            unsafe_allow_html=True,
        )
    with cols[3]:
        if st.button("◀ Prev", disabled=idx == 0,
                     use_container_width=True, key="dd_prev"):
            st.session_state.drilldown_idx = idx - 1
            st.rerun()
    with cols[4]:
        if st.button("Next ▶", disabled=idx >= len(filtered) - 1,
                     use_container_width=True, key="dd_next"):
            st.session_state.drilldown_idx = idx + 1
            st.rerun()

    st.markdown("<div class='fsd-divider'></div>", unsafe_allow_html=True)

    # Find the matching original file bytes
    target_name = filtered[idx]["filename"]
    image_bytes = b""
    for fname, data in batch.get("files", []):
        if fname == target_name:
            image_bytes = data
            break

    drilldown_meta = {
        "filename": target_name,
        "image_bytes": image_bytes,
        "meta": batch["meta"],
    }
    single_result.render(from_drilldown=True, drilldown_meta=drilldown_meta)
