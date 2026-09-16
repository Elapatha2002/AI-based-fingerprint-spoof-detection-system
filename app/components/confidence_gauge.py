"""Decision-score gauge for the result view.

The screen exposes the deployed decision threshold and uncertainty band. It
does not present an evaluation-only EER operating point as a competing case
decision, which would be confusing for examiners.
"""
import streamlit as st


def render_confidence_gauge(p_spoof: float,
                            eer_threshold: float = 0.22,
                            uncertainty_band: tuple[float, float] = (0.40, 0.60)
                           ) -> None:
    """Render the gauge.

    Args:
        p_spoof:           raw sigmoid output, in [0, 1]
        eer_threshold:     retained for API compatibility; evaluation
                            operating points belong in methodology
        uncertainty_band:  (lo, hi) range that should be marked as ambiguous
    """
    p_spoof = max(0.0, min(1.0, float(p_spoof)))
    pct = p_spoof * 100
    lo, hi = uncertainty_band
    band_left = lo * 100
    band_width = (hi - lo) * 100

    color = "var(--accent-spoof)" if p_spoof >= 0.5 else "var(--accent-live)"

    st.markdown(
        f"""
        <div class='fsd-gauge' role='status'
             aria-label='Model spoof score {p_spoof:.4f}; decision threshold 0.50'>
          <div class='fsd-card-title'>Model spoof score</div>
          <div class='fsd-gauge-track'>
            <div class='fsd-gauge-uncertainty'
                 style='left:{band_left}%; width:{band_width}%'></div>
            <div class='fsd-gauge-fill'
                 style='width:{pct}%; background:{color};'></div>
            <div class='fsd-gauge-marker fsd-gauge-marker-default' style='left:50%'>
              <span class='fsd-gauge-marker-label'>0.50 default</span>
            </div>
            <div class='fsd-gauge-needle' style='left:{pct}%'></div>
          </div>
          <div class='fsd-gauge-scale'>
            <span>Live</span><span>Uncertain</span><span>Spoof</span>
          </div>
          <div class='fsd-gauge-readout'>
            Score = <b style='color:{color}'>{p_spoof:.4f}</b>
            &nbsp;·&nbsp; threshold = <b>0.50</b>
            &nbsp;·&nbsp; result = <b>{'SPOOF' if p_spoof >= 0.5 else 'LIVE'}</b>
          </div>
          <div class='fsd-gauge-note'>A model score supports review; it is not a standalone forensic conclusion.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
