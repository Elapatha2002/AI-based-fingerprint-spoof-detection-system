"""Screen 4 — Batch Dashboard."""
import streamlit as st
import pandas as pd
from io import BytesIO
import zipfile

from components.cards import page_title, divider, section_header
from components.tables import results_table


def render():
    batch = st.session_state.get("current_batch")
    if not batch or not batch.get("results"):
        st.warning("No batch results to display.")
        if st.button("Go to Analyze"):
            st.session_state.current_page = "analyze"
            st.rerun()
        return

    results = batch["results"]
    meta = batch["meta"]

    page_title(
        "Batch Dashboard",
        f"{meta['case_id']} · {meta['examiner']} · {len(results)} images",
    )

    # Top: export buttons
    e1, e2, e3 = st.columns([1, 1, 6])
    with e1:
        csv_bytes = _build_csv(results)
        st.download_button("⬇ CSV", data=csv_bytes,
                           file_name=f"{meta['case_id']}_results.csv",
                           mime="text/csv", use_container_width=True)
    with e2:
        zip_bytes = _build_zip_bundle(results, meta)
        st.download_button("⬇ ZIP", data=zip_bytes,
                           file_name=f"{meta['case_id']}_bundle.zip",
                           mime="application/zip", use_container_width=True)

    st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)

    # Metric cards
    total = len(results)
    live_count = sum(1 for r in results if r["label"] == "live")
    spoof_count = sum(1 for r in results if r["label"] == "spoof")
    failed = sum(1 for r in results if r.get("status") == "failed")
    avg_conf = sum(r["confidence"] for r in results) / total if total else 0
    low_q = sum(1 for r in results if r["quality_tier"] == "low")
    anomalies = sum(1 for r in results if not r["known_pattern"])

    cols = st.columns(4)
    cols[0].metric("Total", str(total))
    cols[1].metric("Live", f"{live_count} ({live_count/total:.0%})" if total else "0")
    cols[2].metric("Spoof", f"{spoof_count} ({spoof_count/total:.0%})" if total else "0")
    cols[3].metric("Failed", str(failed))

    cols2 = st.columns(4)
    cols2[0].metric("Avg Confidence", f"{avg_conf:.2f}")
    cols2[1].metric("Low Quality", f"{low_q} ({low_q/total:.0%})" if total else "0")
    cols2[2].metric("Anomalies", str(anomalies))
    cols2[3].metric("Material types",
                    str(len({r["material"] for r in results if r.get("material")})))

    divider()

    # Filters
    section_header("Results")

    f1, f2, f3, f4 = st.columns([3, 1, 1, 1])
    with f1:
        search = st.text_input("Search filename",
                               placeholder="🔍 Search...",
                               label_visibility="collapsed")
    with f2:
        filter_v = st.selectbox("Verdict", ["All", "Live", "Spoof"],
                                key="bd_filter_v")
    with f3:
        filter_q = st.selectbox("Quality", ["All", "High", "Medium", "Low"],
                                key="bd_filter_q")
    with f4:
        anomaly_only = st.checkbox("⚠ Anomaly only", key="bd_anomaly_only")

    filtered = results_table(results, filter_verdict=filter_v,
                             filter_quality=filter_q,
                             anomaly_only=anomaly_only,
                             search=search)

    # Drill-down navigation: filename selector
    if not filtered.empty:
        st.markdown("<div class='fsd-section-h' style='margin-top:16px;'>"
                    "Inspect</div>", unsafe_allow_html=True)
        names = filtered["filename"].tolist()
        choice = st.selectbox("Select an image to drill down",
                              names, key="bd_drilldown_select")
        c1, c2 = st.columns([1, 5])
        with c1:
            if st.button("Open →", type="primary", use_container_width=True,
                         key="bd_open_drilldown"):
                idx = names.index(choice)
                st.session_state.drilldown_idx = idx
                st.session_state.drilldown_filtered = filtered.to_dict("records")
                st.session_state.current_page = "drilldown"
                st.rerun()


def _build_csv(results: list[dict]) -> bytes:
    rows = []
    for r in results:
        rows.append({
            "filename": r["filename"],
            "label": r["label"],
            "confidence": r["confidence"],
            "raw_score": r["raw_score"],
            "material": r.get("material") or "",
            "nfiq2": r["nfiq2"],
            "quality_tier": r["quality_tier"],
            "anomaly_score": r["anomaly_score"],
            "known_pattern": r["known_pattern"],
        })
    df = pd.DataFrame(rows)
    return df.to_csv(index=False).encode("utf-8")


def _build_zip_bundle(results: list[dict], meta: dict) -> bytes:
    """ZIP containing summary CSV + manifest JSON."""
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"{meta['case_id']}_summary.csv",
                    _build_csv(results).decode("utf-8"))
        manifest = {
            "case_id": meta["case_id"],
            "examiner": meta["examiner"],
            "sensor": meta["sensor"],
            "count": len(results),
            "model": "ResNet50V2-CBAM",
            "commit": "a3f9b21",
        }
        import json
        zf.writestr("manifest.json", json.dumps(manifest, indent=2))
    buf.seek(0)
    return buf.read()
