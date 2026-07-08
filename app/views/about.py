"""Screen 9 — About / Methodology."""
import streamlit as st
from components.cards import page_title, section_header, divider
from components.model_picker import render_model_picker


def render():
    page_title("About / Methodology",
               "How this system works, what it was trained on, and what it cannot do.")

    # Model picker (real mode only)
    section_header("Active Model")
    render_model_picker()
    divider()

    cols = st.columns([1, 3])

    with cols[0]:
        st.markdown(
            """
            <div class='fsd-card' style='position:sticky;top:80px;'>
              <div class='fsd-section-h' style='margin:0 0 8px 0;'>On this page</div>
              <div class='fsd-mono' style='font-size:12px;line-height:2;'>
                • Overview<br/>
                • How it works<br/>
                • Datasets<br/>
                • Model<br/>
                • XAI methods<br/>
                • Limitations<br/>
                • Admissibility<br/>
                • References
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with cols[1]:
        section_header("Overview")
        st.markdown(
            "<div style='color:var(--text-secondary);line-height:1.7;'>"
            "This system detects spoofed fingerprints (silicone, gelatin, latex, "
            "wood glue, Play-Doh, ecoflex, etc.) using a convolutional neural "
            "network with attention, and explains its decisions using three XAI "
            "techniques: <b>Grad-CAM++</b>, <b>SHAP</b>, and <b>LIME</b>."
            "</div>",
            unsafe_allow_html=True,
        )

        section_header("How it works")
        st.markdown(
            "<ol style='color:var(--text-secondary);line-height:1.8;'>"
            "<li>The image is preprocessed: ROI extraction with NIST MINDTCT, "
            "CLAHE contrast enhancement, min-max normalization.</li>"
            "<li>A CNN (ResNet50V2 with CBAM attention, or MobileNetV3) "
            "classifies the patch as live or spoof.</li>"
            "<li>An anomaly branch (Isolation Forest + Variational Autoencoder) "
            "flags zero-day spoof materials.</li>"
            "<li>Three XAI methods generate visual explanations.</li>"
            "<li>A forensic report PDF is composed with all artifacts.</li>"
            "</ol>",
            unsafe_allow_html=True,
        )

        section_header("Datasets")
        st.markdown(
            "<div style='color:var(--text-secondary);line-height:1.7;'>"
            "Trained on <b>LivDet 2013</b> (intra-dataset). Evaluated on "
            "<b>LivDet 2015</b> (cross-dataset) and <b>MSU-FPAD v2</b> "
            "(zero-day, leave-one-material-out). All datasets are public; "
            "no PII; image hashes preserved.</div>",
            unsafe_allow_html=True,
        )

        section_header("Model")
        st.markdown(
            """
            <div class='fsd-card'>
            <div class='fsd-mono' style='line-height:1.9;'>
              Architecture &nbsp;:&nbsp; ResNet50V2 + CBAM attention<br/>
              Backbone alt &nbsp;:&nbsp; MobileNetV3 (faster)<br/>
              Anomaly branch &nbsp;:&nbsp; IsolationForest + VAE<br/>
              Training data &nbsp;:&nbsp; LivDet 2013 (10,012 patches)<br/>
              AUC (intra) &nbsp;&nbsp;:&nbsp; 0.978 (target)<br/>
              AUC (cross) &nbsp;&nbsp;:&nbsp; 0.921 (target)<br/>
              APCER &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;:&nbsp; 3.4%<br/>
              BPCER &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;:&nbsp; 2.1%<br/>
              Build &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;:&nbsp; commit a3f9b21
            </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        section_header("XAI methods")
        st.markdown(
            "<ul style='color:var(--text-secondary);line-height:1.8;'>"
            "<li><b>Grad-CAM++</b> — gradient-based heatmaps; best for "
            "ridge / pore localization.</li>"
            "<li><b>SHAP</b> — feature attribution via Shapley values; "
            "shows positive and negative contributions.</li>"
            "<li><b>LIME</b> — local linear approximation over superpixels.</li>"
            "</ul>",
            unsafe_allow_html=True,
        )

        section_header("Limitations")
        st.markdown(
            "<div style='color:var(--text-secondary);line-height:1.7;'>"
            "This is a research prototype. It does <b>not</b> cover: 3D-printed "
            "conductive spoofs, AI-generated ridge patterns, body-double prints, "
            "or live-signal biometrics (pulse, temperature). It uses 2D images "
            "only and was trained predominantly on optical sensors. "
            "See thesis §4.8 for full discussion.</div>",
            unsafe_allow_html=True,
        )

        section_header("Forensic admissibility")
        st.markdown(
            "<div style='color:var(--text-secondary);line-height:1.7;'>"
            "System outputs are designed against Daubert / Frye criteria: "
            "testability, peer-review potential, and known error rates. "
            "Practitioner usability is validated through expert survey "
            "(thesis Chapter 5). Every report PDF embeds the model commit "
            "hash and dataset version for reproducibility.</div>",
            unsafe_allow_html=True,
        )

        section_header("References")
        st.markdown(
            """
            <div class='fsd-mono' style='font-size:12px;color:var(--text-muted);
                 line-height:1.9;'>
              [1] Mukul & Lal (2022). Fingerprint Liveness Detection Using CNN-Based Hybrid Model. <i>NeuroQuantology</i>.<br/>
              [2] Chugh & Jain (2018). Fingerprint Spoof Detector Generalization. <i>IEEE TIFS</i>.<br/>
              [3] Cheniti et al. (2025). Dual-Model Synergy for Fingerprint Spoof Detection. <i>J. Imaging</i>.<br/>
              [4] Zhang et al. (2019). Slim-ResCNN. <i>IEEE Access</i>.<br/>
              [5] Kothadiya et al. (2023). Enhancing Fingerprint Liveness Detection Accuracy. <i>J. Imaging</i>.<br/>
              [6] Naeem et al. (2025). Revolutionizing Biometric Security. <i>IJAMRS</i>.<br/>
              [7] Uliyan et al. (2020). Anti-spoofing method for fingerprint recognition. <i>JESTECH</i>.<br/>
              [8] Agarwal & Bansal (2022). Fingerprint liveness detection through fusion of pores. <i>JKSU-CIS</i>.
            </div>
            """,
            unsafe_allow_html=True,
        )
