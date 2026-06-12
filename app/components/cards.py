"""Reusable card components."""
import streamlit as st


def metric_card(label: str, value: str, sub: str = "", color: str = "primary"):
    """Render a small KPI card.

    color: 'primary' | 'live' | 'spoof' | 'warn' | 'info'
    """
    color_map = {
        "primary": "var(--text-primary)",
        "live": "var(--accent-live)",
        "spoof": "var(--accent-spoof)",
        "warn": "var(--accent-warn)",
        "info": "var(--accent-info)",
    }
    css_color = color_map.get(color, "var(--text-primary)")
    sub_html = f"<div class='fsd-card-sub'>{sub}</div>" if sub else ""
    st.markdown(
        f"""
        <div class="fsd-card">
          <div class="fsd-card-title">{label}</div>
          <div class="fsd-card-value" style="color:{css_color};">{value}</div>
          {sub_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def verdict_card(label: str, confidence: float, material: str | None = None,
                 borderline: bool = False):
    """Render the big verdict block."""
    if borderline:
        cls = "warn"
        color_label = "BORDERLINE"
        caveat = "<div class='fsd-card-sub' style='color:var(--accent-warn);margin-top:8px;'>" \
                 "Re-capture recommended.</div>"
    else:
        cls = label.lower()
        color_label = label.upper()
        caveat = ""

    material_html = ""
    if material:
        material_html = (
            f"<div class='fsd-verdict-sub' style='margin-top:8px;'>"
            f"Material: <b>{material}</b></div>"
        )

    st.markdown(
        f"""
        <div class="fsd-verdict {cls}">
          <div class="fsd-verdict-label">Verdict</div>
          <div class="fsd-verdict-value">{color_label}</div>
          <div class="fsd-verdict-sub">{confidence:.2%} confidence</div>
          {material_html}
          {caveat}
        </div>
        """,
        unsafe_allow_html=True,
    )


def quality_card(nfiq2: int, tier: str):
    color = {"high": "var(--accent-live)",
             "medium": "var(--accent-warn)",
             "low": "var(--accent-spoof)"}.get(tier, "var(--text-muted)")
    st.markdown(
        f"""
        <div class="fsd-card">
          <div class="fsd-card-title">Quality (NFIQ2)</div>
          <div style="display:flex;align-items:center;gap:10px;">
            <div class="fsd-card-value" style="color:{color};">{nfiq2}</div>
            <span class="fsd-pill" style="background:rgba(255,255,255,0.05);
                  color:{color};">{tier.upper()}</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def anomaly_card(score: float, known: bool, vae_err: float):
    if known:
        status_html = "<span class='fsd-pill live'>KNOWN PATTERN</span>"
    else:
        status_html = "<span class='fsd-pill warn'>UNUSUAL — provisional</span>"
    st.markdown(
        f"""
        <div class="fsd-card">
          <div class="fsd-card-title">Anomaly Detector</div>
          <div style="margin:6px 0 8px;">{status_html}</div>
          <div class="fsd-mono">IsoForest: {score:.2f}</div>
          <div class="fsd-mono">VAE recon: {vae_err:.3f}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def timing_card(timings: dict):
    rows = "".join(
        f"<div class='fsd-mono' style='display:flex;justify-content:space-between;'>"
        f"<span>{k.title()}:</span><span>{v} ms</span></div>"
        for k, v in timings.items()
    )
    st.markdown(
        f"""
        <div class="fsd-card">
          <div class="fsd-card-title">Timing</div>
          {rows}
        </div>
        """,
        unsafe_allow_html=True,
    )


def feature_card(icon: str, title: str, text: str):
    st.markdown(
        f"""
        <div class="fsd-feature">
          <div class="fsd-feature-icon">{icon}</div>
          <div class="fsd-feature-title">{title}</div>
          <div class="fsd-feature-text">{text}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def banner(message: str, kind: str = "info"):
    """kind: info | warn | error"""
    st.markdown(
        f"<div class='fsd-banner {kind}'>{message}</div>",
        unsafe_allow_html=True,
    )


def page_title(title: str, subtitle: str = ""):
    sub_html = f"<div class='fsd-page-subtitle'>{subtitle}</div>" if subtitle else ""
    st.markdown(
        f"<div class='fsd-page-title'>{title}</div>{sub_html}",
        unsafe_allow_html=True,
    )


def section_header(text: str):
    st.markdown(f"<div class='fsd-section-h'>{text}</div>", unsafe_allow_html=True)


def divider():
    st.markdown("<div class='fsd-divider'></div>", unsafe_allow_html=True)
