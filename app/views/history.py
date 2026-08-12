"""Screen 8 — History."""
import streamlit as st
from components.cards import page_title
from components.tables import history_table


def render():
    page_title("History",
               "Persisted analyses (SQLite + AWS S3). "
               "Falls back to session-state if cloud is offline.")

    # Prefer the persisted store; fall back to session history if DB read fails
    # or nothing has been saved yet.
    history = _load_history_from_db_or_session()

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
        type_filter = st.selectbox(
            "Type filter",
            ["All", "Single", "Batch"],
            key="hist_type",
            label_visibility="collapsed",
            format_func=lambda x: f"Type: {x}",
        )
    with f3:
        st.markdown("<div style='height:2px;'></div>", unsafe_allow_html=True)
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
                # For persisted batches, refetch every image from S3.
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
                # For persisted single, download the original image from S3.
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
    """Download the most recent analysis's image bytes for a case."""
    try:
        from app.services import database, storage
        analyses = database.list_analyses(case_id=case_id, limit=1)
        if not analyses:
            return b""
        return storage.get_storage().download_bytes(analyses[0]["image_s3_key"])
    except Exception:
        return b""


def _fetch_batch_from_s3(case_id: str) -> list[tuple[str, bytes]]:
    """Download every analysis's image bytes as (filename, bytes) tuples."""
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
