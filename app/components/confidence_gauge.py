"""Confidence gauge with operating-point markers.

Shows P(spoof) as a horizontal needle on a tri-zone track (live / uncertain /
spoof) with markers for the default 0.50 threshold and the empirical EER
threshold. Designed so forensic examiners can see at a glance where the
decision sits relative to defensible operating points.
"""
import streamlit as st


def render_confidence_gauge(p_spoof: float,
                            eer_threshold: float = 0.22,
                            uncertainty_band: tuple[float, float] = (0.40, 0.60)
                           ) -> None:
    """Render the gauge.

    Args:
        p_spoof:           raw sigmoid output, in [0, 1]
        eer_threshold:     operating point where APCER = BPCER
                           (default 0.22 from your thesis evaluation)
        uncertainty_band:  (lo, hi) range that should be marked as ambiguous
    """
    p_spoof = max(0.0, min(1.0, float(p_spoof)))
    pct = p_spoof * 100
    eer_pct = eer_threshold * 100
    lo, hi = uncertainty_band
    band_left = lo * 100
    band_width = (hi - lo) * 100

    color = "var(--accent-spoof)" if p_spoof >= 0.5 else "var(--accent-live)"

    st.markdown(
        f"""
        <div class='fsd-gauge'>
          <div class='fsd-gauge-track'>
            <div class='fsd-gauge-uncertainty'
                 style='left:{band_left}%; width:{band_width}%'></div>
            <div class='fsd-gauge-fill'
                 style='width:{pct}%; background:{color};'></div>
            <div class='fsd-gauge-marker fsd-gauge-marker-default' style='left:50%'>
              <span class='fsd-gauge-marker-label'>0.50 default</span>
            </div>
            <div class='fsd-gauge-marker fsd-gauge-marker-eer' style='left:{eer_pct}%'>
              <span class='fsd-gauge-marker-label'>{eer_threshold:.2f} EER</span>
            </div>
            <div class='fsd-gauge-needle' style='left:{pct}%'></div>
          </div>
          <div class='fsd-gauge-scale'>
            <span>Live</span><span>Uncertain</span><span>Spoof</span>
          </div>
          <div class='fsd-gauge-readout'>
            P(spoof) = <b style='color:{color}'>{p_spoof:.4f}</b>
            &nbsp;·&nbsp; decision @ 0.50 = <b>{'SPOOF' if p_spoof >= 0.5 else 'LIVE'}</b>
            &nbsp;·&nbsp; decision @ EER = <b>{'SPOOF' if p_spoof >= eer_threshold else 'LIVE'}</b>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
