"""
Read the workflow output JSON and write:
    scripts/chapter_content.py   (new chapter content as Python tuples)
    scripts/figures.py           (figure-generation code, ready to run)

After this, run:
    python scripts/figures.py        # creates assets/figures/*.png
    python scripts/build_thesis.py   # generates Thesis_Chapters_1-3.docx
"""
import json
import re
from pathlib import Path

WORKFLOW_OUTPUT = Path(
    r"C:\Users\ASUS\AppData\Local\Temp\claude\d--Projects-University-Final-year-Resarch-project"
    r"\82a19c32-7204-4a2d-9c35-fc1e6c6bf309\tasks\w7nex8b8y.output"
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = PROJECT_ROOT / "scripts"


def _py_escape(s: str) -> str:
    """Escape a string so it can be embedded as a Python triple-double-quoted literal."""
    # Use triple-quoted strings; just need to escape literal """ inside
    return s.replace('"""', '\\"\\"\\"')


def _format_block(block: dict) -> str:
    """Convert a single block dict to a Python tuple-literal string."""
    kind = block["kind"]
    text = _py_escape(block["text"])
    caption = block.get("caption", "")

    if caption:
        caption_esc = _py_escape(caption)
        return (
            f'    ("{kind}", """{text}""", """{caption_esc}"""),'
        )
    return f'    ("{kind}", """{text}"""),'


def _format_blocks(blocks: list, var_name: str) -> str:
    lines = [f"{var_name} = ["]
    for b in blocks:
        lines.append(_format_block(b))
    lines.append("]")
    return "\n".join(lines)


# References — kept as a hard-coded list because the workflow doesn't include them
REFERENCES_BLOCKS = [
    ("h1", "References"),
    ("p", "[1] Mukul and M. Lal, “Fingerprint Liveness Detection Using Convolutional Neural Network Based Hybrid Model,” NeuroQuantology, vol. 20, no. 2, pp. 619–633, 2022, doi: 10.48047/nq.2022.20.2.NQ22357."),
    ("p", "[2] T. Chugh and A. K. Jain, “Fingerprint Spoof Detector Generalization,” IEEE Transactions on Information Forensics and Security, no. March, pp. 1–14, 2013."),
    ("p", "[3] N. Reza and H. Y. Jung, “Cross-sensor Generalization for Fingerprint Presentation Attack Detection Leveraging Local Feature Enhancement,” IEEE Transactions on Biometrics, Behavior, and Identity Science, p. 1, 2025, doi: 10.1109/TBIOM.2025.3590827."),
    ("p", "[4] M. Cheniti, Z. Akhtar, and P. K. Chandaliya, “Dual-Model Synergy for Fingerprint Spoof Detection Using VGG16 and ResNet50,” Journal of Imaging, vol. 11, no. 2, pp. 1–13, 2025, doi: 10.3390/jimaging11020042."),
    ("p", "[5] Y. Zhang, D. Shi, X. Zhan, D. Cao, K. Zhu, and Z. Li, “Slim-ResCNN: A Deep Residual Convolutional Neural Network for Fingerprint Liveness Detection,” IEEE Access, vol. 7, pp. 91476–91487, 2019, doi: 10.1109/ACCESS.2019.2927357."),
    ("p", "[6] D. Kothadiya et al., “Enhancing Fingerprint Liveness Detection Accuracy Using Deep Learning: A Comprehensive Study and Novel Approach,” Journal of Imaging, vol. 9, no. 8, 2023, doi: 10.3390/jimaging9080158."),
    ("p", "[7] I. Naeem, B. Nadeem, M. Khan, R. Bibi, E. Mehmood, and A. Shaukat, “Revolutionizing Biometric Security: Advanced Deep Learning Strategies for Fingerprint Anti-Spoofing in High-Risk Applications,” International Journal of Advanced Multidisciplinary Research and Studies, vol. 5, no. 1, pp. 889–894, 2025, doi: 10.62225/2583049x.2025.5.1.3739."),
    ("p", "[8] D. M. Uliyan, S. Sadeghi, and H. A. Jalab, “Anti-spoofing method for fingerprint recognition using patch based deep learning machine,” Engineering Science and Technology, an International Journal, vol. 23, no. 2, pp. 264–273, 2020, doi: 10.1016/j.jestch.2019.06.005."),
    ("p", "[9] D. Agarwal and A. Bansal, “Fingerprint liveness detection through fusion of pores perspiration and texture features,” Journal of King Saud University - Computer and Information Sciences, vol. 34, no. 7, pp. 4089–4098, 2022, doi: 10.1016/j.jksuci.2020.10.003."),
    ("p", "[10] S. Woo, J. Park, J.-Y. Lee, and I. S. Kweon, “CBAM: Convolutional Block Attention Module,” in Proceedings of the European Conference on Computer Vision (ECCV), 2018, pp. 3–19."),
    ("p", "[11] A. Howard et al., “Searching for MobileNetV3,” in Proceedings of the IEEE/CVF International Conference on Computer Vision (ICCV), 2019, pp. 1314–1324."),
    ("p", "[12] A. Chattopadhay, A. Sarkar, P. Howlader, and V. N. Balasubramanian, “Grad-CAM++: Improved Visual Explanations for Deep Convolutional Networks,” in 2018 IEEE Winter Conference on Applications of Computer Vision (WACV), 2018, pp. 839–847."),
    ("p", "[13] S. M. Lundberg and S.-I. Lee, “A Unified Approach to Interpreting Model Predictions,” in Advances in Neural Information Processing Systems (NeurIPS), 2017."),
    ("p", "[14] M. T. Ribeiro, S. Singh, and C. Guestrin, “‘Why Should I Trust You?’: Explaining the Predictions of Any Classifier,” in Proceedings of the 22nd ACM SIGKDD International Conference on Knowledge Discovery and Data Mining, 2016, pp. 1135–1144."),
    ("p", "[15] V. Petsiuk, A. Das, and K. Saenko, “RISE: Randomized Input Sampling for Explanation of Black-box Models,” in Proceedings of the British Machine Vision Conference (BMVC), 2018."),
    ("p", "[16] K. Peffers, T. Tuunanen, M. A. Rothenberger, and S. Chatterjee, “A Design Science Research Methodology for Information Systems Research,” Journal of Management Information Systems, vol. 24, no. 3, pp. 45–77, 2007."),
    ("p", "[17] K. He, X. Zhang, S. Ren, and J. Sun, “Deep Residual Learning for Image Recognition,” in Proceedings of the IEEE Conference on Computer Vision and Pattern Recognition (CVPR), 2016, pp. 770–778."),
    ("p", "[18] J. Adebayo, J. Gilmer, M. Muelly, I. Goodfellow, M. Hardt, and B. Kim, “Sanity Checks for Saliency Maps,” in Advances in Neural Information Processing Systems (NeurIPS), 2018."),
    ("p", "[19] R. R. Selvaraju, M. Cogswell, A. Das, R. Vedantam, D. Parikh, and D. Batra, “Grad-CAM: Visual Explanations from Deep Networks via Gradient-based Localization,” in Proceedings of the IEEE International Conference on Computer Vision (ICCV), 2017, pp. 618–626."),
    ("p", "[20] W. Samek, A. Binder, G. Montavon, S. Lapuschkin, and K.-R. Müller, “Evaluating the Visualization of What a Deep Neural Network Has Learned,” IEEE Transactions on Neural Networks and Learning Systems, vol. 28, no. 11, pp. 2660–2673, 2017."),
]


def main():
    data = json.loads(WORKFLOW_OUTPUT.read_text(encoding="utf-8"))
    result = data["result"]

    ch1 = result["chapter_1"]
    ch2 = result["chapter_2"]
    ch3 = result["chapter_3"]
    figures_code = result["figures_code"]
    verifications = result["verifications"]

    print(f"Chapter 1: {len(ch1)} blocks")
    print(f"Chapter 2: {len(ch2)} blocks")
    print(f"Chapter 3: {len(ch3)} blocks")

    # ── Write scripts/figures.py ──
    figures_py = SCRIPTS_DIR / "figures.py"
    figures_py.write_text(figures_code, encoding="utf-8")
    print(f"Wrote {figures_py} ({len(figures_code)} chars)")

    # ── Write scripts/chapter_content.py ──
    parts = [
        '"""',
        "Chapter content for the thesis Word document.",
        "",
        "Generated by scripts/assemble_from_workflow.py from the structured",
        "output of the thesis-restructure workflow.",
        "",
        "Block kinds supported:",
        '    h1, h2, h3   headings',
        '    p            body paragraph (justified)',
        '    bullet       bullet list item',
        '    numbered     numbered list item',
        '    figure       (kind, filename, caption)   image inserted from assets/figures/',
        '    table_md     (kind, markdown table text, caption)',
        '    caption      italic centred caption',
        '    pagebreak    new page',
        '"""',
        "",
    ]
    parts.append(_format_blocks(ch1, "CHAPTER_1"))
    parts.append("")
    parts.append(_format_blocks(ch2, "CHAPTER_2"))
    parts.append("")
    parts.append(_format_blocks(ch3, "CHAPTER_3"))
    parts.append("")

    # References
    parts.append("REFERENCES = [")
    for kind, text in REFERENCES_BLOCKS:
        text_esc = _py_escape(text)
        parts.append(f'    ("{kind}", """{text_esc}"""),')
    parts.append("]")
    parts.append("")

    chapter_py = SCRIPTS_DIR / "chapter_content.py"
    chapter_py.write_text("\n".join(parts), encoding="utf-8")
    print(f"Wrote {chapter_py}")

    # ── Print verification summary ──
    print()
    print("=" * 70)
    print("VERIFICATION SUMMARY")
    print("=" * 70)
    for ch_key in ("ch1", "ch2", "ch3"):
        v = verifications[ch_key]
        print(f"\n{ch_key.upper()}: compliance {v['compliance_score']}%")
        if v.get("structural_issues"):
            print("  Structural issues:")
            for i in v["structural_issues"]:
                print(f"    - {i}")
        if v.get("quality_issues"):
            print(f"  Quality issues ({len(v['quality_issues'])} items)")
        if v.get("factual_issues"):
            print(f"  Factual issues ({len(v['factual_issues'])} items)")


if __name__ == "__main__":
    main()
