"""Screen 3 — Batch Processing with progress + live tail."""
import time
from datetime import datetime
from io import BytesIO

import streamlit as st
import pandas as pd
from PIL import Image

from components.cards import page_title
from services import mock_model
from state import add_to_history


def render():
    batch = st.session_state.get("current_batch")
    if not batch or not batch.get("files"):
        st.warning("No active batch. Returning to Analyze.")
        st.session_state.current_page = "analyze"
        st.rerun()
        return

    files = batch["files"]
    meta = batch["meta"]

    page_title("Processing Batch",
               f"{meta['case_id']} · {len(files)} images")

    progress_bar = st.progress(0, text="Starting...")
    counter_slot = st.empty()
    cancel_slot = st.empty()

    st.markdown("<div class='fsd-divider'></div>", unsafe_allow_html=True)
    st.markdown("<div class='fsd-section-h'>Recent results</div>",
                unsafe_allow_html=True)
    tail_slot = st.empty()

    if cancel_slot.button("✕ Cancel", key="cancel_batch"):
        st.session_state.current_batch["results"] = batch.get("results", [])
        add_to_history({
            "type": "batch",
            "case_id": meta["case_id"],
            "count": len(batch.get("results", [])),
            "live_count": sum(1 for r in batch.get("results", []) if r["label"] == "live"),
            "spoof_count": sum(1 for r in batch.get("results", []) if r["label"] == "spoof"),
            "status": "Cancelled",
            "results": batch.get("results", []),
            "meta": meta,
        })
        st.session_state.current_page = "analyze"
        st.rerun()
        return

    results = []
    started = time.time()
    for i, (filename, data) in enumerate(files):
        try:
            img = Image.open(BytesIO(data)) if data else None
        except Exception:
            img = None
        result = mock_model.predict(filename, img)
        results.append(result)

        pct = (i + 1) / len(files)
        elapsed = time.time() - started
        throughput = (i + 1) / max(elapsed, 0.1)
        eta = (len(files) - i - 1) / max(throughput, 0.1)

        progress_bar.progress(pct, text=f"{int(pct * 100)}%")
        counter_slot.markdown(
            f"""
            <div style='text-align:center;margin-top:12px;'>
              <div class='fsd-mono' style='font-size:14px;color:var(--text-primary);'>
                {i + 1} / {len(files)} images
              </div>
              <div class='fsd-mono' style='color:var(--text-muted);'>
                ETA: {eta:.0f}s  ·  Throughput: {throughput:.1f} imgs/s
                ·  Elapsed: {elapsed:.0f}s
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Live tail (last 5)
        tail = results[-5:][::-1]
        df = pd.DataFrame([{
            "#": len(results) - j,
            "Filename": r["filename"][:30],
            "Verdict": r["label"].upper(),
            "Conf": f"{r['confidence']:.2f}",
            "NFIQ2": r["nfiq2"],
            "Time": f"{r['timing_ms']['total']}ms",
        } for j, r in enumerate(tail)])
        tail_slot.dataframe(df, width="stretch", hide_index=True)

    # Done
    st.session_state.current_batch["results"] = results
    st.session_state.current_batch["finished_at"] = datetime.now().isoformat()

    add_to_history({
        "type": "batch",
        "case_id": meta["case_id"],
        "count": len(results),
        "live_count": sum(1 for r in results if r["label"] == "live"),
        "spoof_count": sum(1 for r in results if r["label"] == "spoof"),
        "status": "Done",
        "results": results,
        "meta": meta,
        "files": files,
    })

    # Persist the batch to S3 + SQLite (best-effort). Runs after the visible
    # progress has finished so cloud latency does not affect the UX.
    try:
        from app.services import persistence
        from components.audit import log_action
        ids = persistence.save_batch_analyses(meta=meta, files=files,
                                               results=results)
        if ids:
            log_action(
                action=f"Persisted batch of {len(ids)} analyses to S3 + SQLite",
                case_id=meta.get("case_id", "—"),
                details=f"first_id={ids[0]}, last_id={ids[-1]}",
            )
    except Exception:
        pass

    time.sleep(0.4)
    st.session_state.current_page = "batch_dashboard"
    st.rerun()
