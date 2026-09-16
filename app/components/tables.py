"""Sortable result tables built on st.dataframe."""
import streamlit as st
import pandas as pd


def results_table(results: list[dict], filter_verdict: str = "All",
                  filter_quality: str = "All", anomaly_only: bool = False,
                  search: str = "") -> pd.DataFrame:
    """Render a filterable, sortable results table for a batch."""
    df = pd.DataFrame(results)
    if df.empty:
        st.info("No results yet.")
        return df

    # Apply filters
    if filter_verdict != "All":
        df = df[df["label"].str.upper() == filter_verdict.upper()]
    if filter_quality != "All":
        df = df[df["quality_tier"].str.lower() == filter_quality.lower()]
    if anomaly_only:
        df = df[~df["known_pattern"]]
    if search:
        df = df[df["filename"].str.contains(search, case=False, na=False)]

    # Sort: highest confidence first
    if "confidence" in df.columns:
        df = df.sort_values("confidence", ascending=False).reset_index(drop=True)

    display = df.copy()
    display["#"] = display.index + 1
    display = display.rename(columns={
        "filename": "Filename",
        "label": "Verdict",
        "confidence": "Confidence",
        "nfiq2": "NFIQ2",
        "material": "Material",
        "anomaly_score": "Anomaly",
    })
    display["Verdict"] = display["Verdict"].str.upper()
    display["Confidence"] = display["Confidence"].apply(lambda v: f"{v:.2f}" if pd.notnull(v) else "—")
    display["Anomaly"] = display["Anomaly"].apply(lambda v: f"{v:.2f}" if pd.notnull(v) else "—")
    display["Material"] = display["Material"].fillna("—")

    cols = ["#", "Filename", "Verdict", "Confidence", "NFIQ2", "Material", "Anomaly"]
    st.dataframe(
        display[cols],
        width="stretch",
        hide_index=True,
        height=min(420, 60 + 35 * len(display)),
        column_config={
            "#": st.column_config.NumberColumn(width="small"),
            "Confidence": st.column_config.TextColumn(width="small"),
            "NFIQ2": st.column_config.NumberColumn(width="small"),
            "Anomaly": st.column_config.TextColumn(width="small"),
        },
    )
    return df


def history_table(history: list[dict]) -> pd.DataFrame:
    """Render the history list."""
    if not history:
        st.info("No analyses yet. Start one from Analyze.")
        return pd.DataFrame()

    rows = []
    for h in history:
        rows.append({
            "Date": h.get("created_at", "—")[:19].replace("T", " "),
            "Case ID": h.get("case_id", "—"),
            "Type": h.get("type", "—").title(),
            "Items": h.get("count", 1),
            "Live": h.get("live_count", "—"),
            "Spoof": h.get("spoof_count", "—"),
            "Status": h.get("status", "Done"),
        })
    df = pd.DataFrame(rows)
    st.dataframe(df, width="stretch", hide_index=True)
    return df
