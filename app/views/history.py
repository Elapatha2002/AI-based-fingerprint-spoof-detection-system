"""Screen 8 — History."""
import streamlit as st
from components.cards import page_title
from components.tables import history_table


def render():
    page_title("History",
               "All past analyses on this device (in-session for the prototype).")

    history = st.session_state.get("history", [])

    if not history:
        st.markdown(
            "<div style='text-align:center;padding:64px 0;color:var(--text-muted);'>"
            "<div style='font-size:48px;'>📂</div>"
            "<div style='font-size:14px;margin-top:8px;'>No analyses yet.</div></div>",
            unsafe_allow_html=True,
        )
        if st.button("Start an analysis →", type="primary"):
            st.session_state.current_page = "analyze"
            st.rerun()
        return

    f1, f2, f3 = st.columns([3, 1, 1])
    with f1:
        search = st.text_input("Search case ID",
                               placeholder="🔍 Search by case ID...",
                               label_visibility="collapsed")
    with f2:
        type_filter = st.selectbox("Type", ["All", "Single", "Batch"],
                                   key="hist_type")
    with f3:
        if st.button("🗑  Clear All", use_container_width=True,
                     key="hist_clear"):
            st.session_state.history = []
            st.rerun()

    filtered = history
    if search:
        filtered = [h for h in filtered
                    if search.lower() in h.get("case_id", "").lower()]
    if type_filter != "All":
        filtered = [h for h in filtered
                    if h.get("type", "").lower() == type_filter.lower()]

    history_table(filtered)

    if filtered:
        st.markdown("<div class='fsd-section-h' style='margin-top:16px;'>"
                    "Open</div>", unsafe_allow_html=True)
        labels = [
            f"{h.get('created_at', '')[:19].replace('T', ' ')}  ·  "
            f"{h.get('case_id', '—')}  ·  {h.get('type', '').title()}"
            for h in filtered
        ]
        idx = st.selectbox("Pick an entry to reopen", list(range(len(labels))),
                           format_func=lambda i: labels[i],
                           key="hist_reopen_select")
        if st.button("Open →", type="primary", key="hist_open"):
            entry = filtered[idx]
            if entry["type"] == "batch":
                st.session_state.current_batch = {
                    "files": entry.get("files", []),
                    "results": entry.get("results", []),
                    "meta": entry.get("meta", {}),
                }
                st.session_state.current_page = "batch_dashboard"
            else:
                st.session_state.current_single = {
                    "filename": entry.get("filename", "—"),
                    "image_bytes": b"",
                    "meta": entry.get("meta", {}),
                }
                st.session_state.current_page = "single_result"
            st.rerun()
