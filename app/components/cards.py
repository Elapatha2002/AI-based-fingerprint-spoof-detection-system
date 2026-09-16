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
                 borderline: bool = False, hero: bool = False):
    """Render the big verdict block.

    Args:
        hero: if True, applies the larger "hero" treatment (44px verdict text,
              tighter spacing) — recommended on result pages where the verdict
              is the primary information.
    """
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

    hero_class = " fsd-verdict-hero" if hero else ""

    st.markdown(
        f"""
        <div class="fsd-verdict {cls}{hero_class}">
          <div class="fsd-verdict-label">Verdict</div>
          <div class="fsd-verdict-value">{color_label}</div>
          <div class="fsd-verdict-sub">{confidence:.2%} confidence</div>
          {material_html}
          {caveat}
        </div>
        """,
        unsafe_allow_html=True,
    )


def tech_strip(items: list[str]) -> None:
    """Compact monospace strip for tertiary tech info (timing, model, hash).

    items: list of HTML strings (or plain text) to display, separated by dots.
    """
    sep = "<span class='sep'>·</span>"
    inner = sep.join(f"<span>{x}</span>" for x in items)
    st.markdown(
        f"<div class='fsd-tech-strip'>{inner}</div>",
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


def empty_state(icon: str, message: str,
                title: str = "Nothing to show yet",
                action_label: str | None = None,
                action_page: str | None = None,
                key: str | None = None) -> None:
    """Render a helpful empty state with a clear next action.

    Args:
        icon:         a single emoji or short glyph
        message:      concise explanation of why the view is empty
        title:        human-readable state heading
        action_label: optional CTA text (e.g. "Start an analysis")
        action_page:  page key to navigate to on click
        key:          Streamlit widget key (required if action_label is set)
    """
    st.markdown(
        f"""
        <div class='fsd-empty-state' role='status'>
          <div class='fsd-empty-icon' aria-hidden='true'>{icon}</div>
          <div class='fsd-empty-title'>{title}</div>
          <div class='fsd-empty-message'>{message}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if action_label and action_page:
        _, mid, _ = st.columns([2, 1, 2])
        with mid:
            if st.button(action_label, type="primary",
                          width="stretch",
                          key=key or f"empty_{action_page}"):
                st.session_state.current_page = action_page
                st.rerun()
