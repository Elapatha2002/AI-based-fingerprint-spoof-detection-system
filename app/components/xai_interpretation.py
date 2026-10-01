"""Guided XAI interpretation panel.

Sits below the three XAI heatmap tabs. Auto-generates plain-language
guidance based on (a) whether the three methods agree on attribution
location and (b) the verdict's confidence level. Aimed at examiners who
have never read a saliency map before.
"""
import numpy as np
import streamlit as st


def _cross_method_agreement(xai_panels: dict) -> float:
    """Crude pairwise IoU at top-20% between heatmaps. Returns mean ∈ [0,1]."""
    methods = [m for m in ("gradcam", "shap", "lime") if m in xai_panels]
    if len(methods) < 2:
        return 0.0

    maps = []
    for m in methods:
        h = xai_panels[m].get("heatmap")
        if h is None:
            return 0.0
        h = np.asarray(h, dtype=np.float32)
        if h.ndim != 2:
            return 0.0
        maps.append(np.abs(h))

    ious = []
    for i in range(len(maps)):
        for j in range(i + 1, len(maps)):
            a, b = maps[i], maps[j]
            if a.shape != b.shape:
                continue
            ta = np.percentile(a, 80)
            tb = np.percentile(b, 80)
            ma = a >= ta
            mb = b >= tb
            inter = (ma & mb).sum()
            union = (ma | mb).sum()
            ious.append(inter / max(union, 1))

    return float(np.mean(ious)) if ious else 0.0


def render_xai_interpretation(xai_panels: dict,
                              verdict_label: str,
                              p_spoof: float) -> None:
    """Render the guided interpretation panel."""
    if any(p.get('status') == 'error' for p in xai_panels.values()):
        st.warning('Explanation generation is incomplete. Cross-method agreement '
                   'cannot be interpreted until all explanation methods are available.')
        return
    agreement = _cross_method_agreement(xai_panels)
    methods_agree = agreement >= 0.30           # IoU threshold for "agreement"
    is_borderline = 0.40 <= p_spoof <= 0.60

    # Decide the headline message
    if is_borderline:
        consensus = (
            "⚠ This prediction sits in the uncertain zone (P(spoof) between "
            "0.40 and 0.60). All three explanations should be reviewed; "
            "consider a re-capture or additional review before drawing a conclusion."
        )
        border_color = "var(--accent-warn)"
    elif methods_agree:
        consensus = (
            "✓ All three explanation methods agree on the discriminative "
            "region. This provides more consistent supporting evidence, but "
            "the overlays still require examiner review alongside image quality "
            "and case context."
        )
        border_color = "var(--accent-live)"
    else:
        consensus = (
            "ⓘ The three methods highlight different regions. This often "
            "occurs when multiple visual features contribute to the "
            "decision. Treat Grad-CAM++ as the primary localization claim "
            "and cross-check with SHAP's signed attribution to see "
            "competing evidence."
        )
        border_color = "var(--accent-info)"

    iou_pct = int(agreement * 100)

    st.markdown(
        f"""
        <div class='fsd-interpretation' style='border-left-color:{border_color}'>
          <div class='fsd-interp-title'>
            How to read these explanations
            &nbsp;·&nbsp; cross-method agreement: <b>{iou_pct}%</b> IoU@20
          </div>
          <div class='fsd-interp-body'>{consensus}</div>
          <div class='fsd-interp-grid'>
            <div>
              <div class='fsd-interp-method'>Grad-CAM++</div>
              <div class='fsd-interp-desc'>
                Yellow / green = high attribution. Best for spatial
                localization of ridge anomalies.
              </div>
            </div>
            <div>
              <div class='fsd-interp-method'>SHAP</div>
              <div class='fsd-interp-desc'>
                <span style='color:#F85149'>Red</span> pushes toward SPOOF,
                <span style='color:#58A6FF'>blue</span> pushes toward LIVE.
                Signed evidence.
              </div>
            </div>
            <div>
              <div class='fsd-interp-method'>LIME</div>
              <div class='fsd-interp-desc'>
                Highlights specific superpixels. Useful for non-technical
                reviewers when used with the other explanations.
              </div>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
