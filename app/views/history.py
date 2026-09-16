"""Screen 8 — History."""
import streamlit as st
from components.cards import page_title, empty_state
from components.tables import history_table


def render():
    page_title("History",
               "Find and reopen analyses saved in the case record.")

    # Reset widget values before the inputs are instantiated on this rerun.
    if st.session_state.pop("history_reset_filters", False):
        st.session_state.pop("hist_search", None)
        st.session_state.pop("hist_type", None)

    # Prefer the persisted store; fall back to session history if DB read fails
    # or nothing has been saved yet.
    history = _load_history_from_db_or_session()

    if not history:
        empty_state(
            icon="📂",
            message="No analyses saved yet. Run one to see it here.",
            action_label="Start an analysis  →",
            action_page="analyze",
            key="empty_history_start",
        )
        return

    f1, f2, f3 = st.columns([3, 1.25, 1])
    with f1:
        search = st.text_input("Search by case ID",
                               placeholder="e.g. CASE-2026-0004",
                               key="hist_search")
    with f2:
        type_filter = st.selectbox(
            "Analysis type",
            ["All", "Single", "Batch"],
            key="hist_type",
        )
    with f3:
        st.markdown("<div style='height:27px;'></div>", unsafe_allow_html=True)
        if st.button("Reset filters", width="stretch",
                     key="hist_reset"):
            st.session_state.history_reset_filters = True
            st.rerun()

    filtered = history
    if search:
        filtered = [h for h in filtered
                    if search.lower() in h.get("case_id", "").lower()]
    if type_filter != "All":
        filtered = [h for h in filtered
                    if h.get("type", "").lower() == type_filter.lower()]

    if not filtered:
        empty_state(
            icon="🔎",
            title="No matching analyses",
            message="Try a different case ID or reset the filters to view all saved analyses.",
        )
        return

    st.caption(f"{len(filtered)} saved {'analysis' if len(filtered) == 1 else 'analyses'}")
    history_table(filtered)

    if filtered:
        st.markdown("<div class='fsd-section-h' style='margin-top:20px;'>"
                    "Open a saved analysis</div>", unsafe_allow_html=True)
        labels = [
            f"{h.get('created_at', '')[:19].replace('T', ' ')}  ·  "
            f"{h.get('case_id', '—')}  ·  {h.get('type', '').title()}"
            for h in filtered
        ]
        open_col, button_col = st.columns([4, 1])
        with open_col:
            idx = st.selectbox("Choose an analysis", list(range(len(labels))),
                           format_func=lambda i: labels[i],
                           key="hist_reopen_select")
        with button_col:
            st.markdown("<div style='height:27px;'></div>", unsafe_allow_html=True)
            open_selected = st.button("Open analysis", type="primary",
                                      width="stretch", key="hist_open")
        if open_selected:
            entry = filtered[idx]
            if entry["type"] == "batch":
                # For persisted batches, refetch every image from storage.
                # For in-session batches, use the cached files list.
                if entry.get("_source") == "db":
                    files = _fetch_batch_from_s3(entry["case_id"])
                    st.session_state.current_batch = {
                        "files": files,
                        "results": [],
                        "meta": entry.get("meta", {}),
                    }
                else:
                    st.session_state.current_batch = {
                        "files": entry.get("files", []),
                        "results": entry.get("results", []),
                        "meta": entry.get("meta", {}),
                    }
                st.session_state.current_page = "batch_dashboard"
            else:
                # For persisted single, download the original image from storage.
                image_bytes = b""
                if entry.get("_source") == "db":
                    image_bytes = _fetch_single_from_s3(entry["case_id"])
                st.session_state.current_single = {
                    "filename": entry.get("filename", "-"),
                    "image_bytes": image_bytes,
                    "meta": entry.get("meta", {}),
                }
                st.session_state.current_page = "single_result"
            st.rerun()


def _fetch_single_from_s3(case_id: str) -> bytes:
    """Download the most recent analysis image from the active backend."""
    try:
        from app.services import database, storage
        analyses = database.list_analyses(case_id=case_id, limit=1)
        if not analyses:
            return b""
        return storage.get_storage().download_bytes(analyses[0]["image_s3_key"])
    except Exception:
        return b""


def _fetch_batch_from_s3(case_id: str) -> list[tuple[str, bytes]]:
    """Download every analysis image as ``(filename, bytes)`` tuples."""
    try:
        from app.services import database, storage
        svc = storage.get_storage()
        analyses = database.list_analyses(case_id=case_id, limit=500)
        files: list[tuple[str, bytes]] = []
        for a in analyses:
            try:
                data = svc.download_bytes(a["image_s3_key"])
                files.append((a["image_filename"], data))
            except Exception:
                continue
        return files
    except Exception:
        return []


def _load_history_from_db_or_session() -> list[dict]:
    """DB-first with graceful fallback.

    Merges DB rows and session-state rows so unsaved (in-flight) analyses
    remain visible during a session, while restarts still show persisted
    history from previous sessions.
    """
    session_history = list(st.session_state.get("history", []))
    try:
        from app.services import persistence
        db_history = persistence.list_history_from_db()
    except Exception:
        db_history = []

    # Prefer DB rows for case IDs that exist in both places; append any
    # session rows for cases not yet persisted.
    db_case_ids = {row["case_id"] for row in db_history}
    session_only = [row for row in session_history
                    if row.get("case_id") not in db_case_ids]

    merged = db_history + session_only
    merged.sort(key=lambda r: r.get("created_at", ""), reverse=True)
    return merged
