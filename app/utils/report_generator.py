"""PDF reports based on the supplied analysis, not the currently selected model."""
import hashlib
from io import BytesIO
from datetime import datetime
from fpdf import FPDF


# fpdf2's default Helvetica core font is a Type 1 font that only supports
# Windows-1252 encoding. Any character outside that (em dash "—", curly
# quotes, symbols) crashes multi_cell with "Not enough horizontal space
# to render a single character" because internal width calculation
# returns ~0 for unmappable chars. Sanitise before writing.
_UNICODE_MAP = {
    "—": "-",   # em dash
    "–": "-",   # en dash
    "‘": "'",   # left single curly quote
    "’": "'",   # right single curly quote
    "“": '"',   # left double curly quote
    "”": '"',   # right double curly quote
    "…": "...", # ellipsis
    " ": " ",   # non-breaking space
    "•": "*",   # bullet
}


def _safe_text(s) -> str:
    """Coerce any value to a Windows-1252-safe string for fpdf core fonts."""
    text = "" if s is None else str(s)
    for uch, ascii_replacement in _UNICODE_MAP.items():
        text = text.replace(uch, ascii_replacement)
    # Anything still non-Windows-1252 gets stripped
    return text.encode("cp1252", errors="replace").decode("cp1252")


class ForensicReportPDF(FPDF):
    def header(self):
        self.set_fill_color(20, 27, 35)
        self.rect(0, 0, 210, 18, "F")
        self.set_text_color(230, 237, 243)
        self.set_font("Helvetica", "B", 11)
        self.set_xy(10, 6)
        self.cell(0, 6, "FSD-XAI  Forensic Spoof Detection Report", ln=False)
        self.set_font("Helvetica", "", 8)
        self.set_xy(150, 6)
        self.cell(0, 6, f"Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                  align="R")
        self.ln(20)
        self.set_text_color(0, 0, 0)

    def footer(self):
        self.set_y(-12)
        self.set_text_color(110, 118, 129)
        self.set_font("Helvetica", "", 8)
        self.cell(0, 6, f"Page {self.page_no()} / {{nb}}", align="C")


def build_report(case_meta: dict, result: dict, image_bytes: bytes | None = None,
                 xai_panels: list[tuple[str, bytes]] | None = None) -> bytes:
    """
    case_meta: {case_id, examiner, sensor, notes, timestamp}
    result: {label, confidence, material, nfiq2, anomaly_score, ...}
    xai_panels: list of (name, png_bytes)
    Returns PDF as bytes.
    """
    pdf = ForensicReportPDF(orientation="P", unit="mm", format="A4")
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=15)

    # Page 1 — case header
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, "Case Information", ln=True)
    pdf.ln(2)
    pdf.set_font("Helvetica", "", 11)

    model = result.get("model") or {}
    if not isinstance(model, dict):
        model = {"name": str(model)}
    missing = "Not recorded"
    rows = [
        ("Case ID", case_meta.get("case_id", "-")),
        ("Examiner", case_meta.get("examiner", "-")),
        ("Sensor", case_meta.get("sensor", "-")),
        ("Notes", case_meta.get("notes", "-") or "-"),
        ("Analysis timestamp", case_meta.get("timestamp") or missing),
        ("Model", model.get("name") or missing),
        ("Model reference", model.get("commit") or missing),
        ("Checkpoint run", model.get("checkpoint_short") or missing),
        ("Checkpoint SHA-256", model.get("checkpoint_sha256") or missing),
        ("Source commit", model.get("source_commit") or missing),
        ("Execution mode", model.get("version") or missing),
        ("Training data", model.get("training_data") or missing),
        ("Input SHA-256", hashlib.sha256(image_bytes).hexdigest()
         if image_bytes else missing),
        ("Decision threshold", result.get("threshold_used", missing)),
    ]
    for k, v in rows:
        # Force cursor to left margin so the label cell always starts there.
        # fpdf2 leaves the cursor at the RIGHT of a multi_cell by default,
        # which on the next iteration makes cell(40,...) start off-page.
        pdf.set_x(pdf.l_margin)
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(40, 7, _safe_text(f"{k}:"), border=0)
        pdf.set_font("Helvetica", "", 10)
        pdf.multi_cell(0, 7, _safe_text(v))

    # Page 2 — verdict + image
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, "Classification Result", ln=True)
    pdf.ln(2)

    label = result.get("label", "?").upper()
    conf = result.get("confidence", 0.0)
    color = (63, 185, 80) if label == "LIVE" else (248, 81, 73)

    pdf.set_fill_color(*color)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 12, _safe_text(f"  {label}    Confidence: {conf:.2%}"),
              ln=True, fill=True)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(4)

    pdf.set_font("Helvetica", "", 11)
    detail_rows = [
        ("Predicted material", result.get("material") or "-"),
        ("Image quality (NFIQ2)", str(result.get("nfiq2", "-"))),
        ("Anomaly score", f"{result.get('anomaly_score', 0.0):.2f}"),
        ("Pattern recognized", "Yes" if result.get("known_pattern", True) else "No (provisional)"),
    ]
    for k, v in detail_rows:
        pdf.set_x(pdf.l_margin)
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(60, 7, _safe_text(f"{k}:"))
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 7, _safe_text(v), ln=True)

    if image_bytes:
        try:
            pdf.ln(6)
            img_stream = BytesIO(image_bytes)
            pdf.image(img_stream, x=70, w=70)
        except Exception:
            pass

    # Page 3 — XAI panels
    if xai_panels:
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 14)
        pdf.cell(0, 10, "Explainable AI Analysis", ln=True)
        pdf.ln(2)
        pdf.set_font("Helvetica", "", 10)
        pdf.multi_cell(0, 6, _safe_text(
            "The following visualizations show which regions of the fingerprint "
            "drove the model's classification decision. All three methods are "
            "shown for comparative interpretation."))
        pdf.ln(4)

        x_positions = [10, 75, 140]
        for (name, img_bytes), x in zip(xai_panels[:3], x_positions):
            try:
                pdf.set_xy(x, pdf.get_y())
                pdf.image(BytesIO(img_bytes), x=x, w=60)
            except Exception:
                pass
        pdf.ln(70)
        for (name, _), x in zip(xai_panels[:3], x_positions):
            pdf.set_xy(x, pdf.get_y())
            pdf.set_font("Helvetica", "B", 10)
            pdf.cell(60, 6, name, align="C")
        pdf.ln(8)

    # Page 4 — methodology + signature
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, "Methodology & Limitations", ln=True)
    pdf.ln(2)
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(0, 6, _safe_text(
        "This report is generated by an Explainable AI fingerprint spoof "
        "detection research prototype. Model identifiers on the case page "
        "come from the supplied analysis. Missing provenance is marked 'Not "
        "recorded'; a model reference or checkpoint run is not necessarily a "
        "source-code commit.\n\n"
        "Any supplied explanation panels are aids for interpretation, not "
        "proof of causality or classification correctness. They support, but "
        "do not replace, qualified examiner judgment. Benchmark error rates "
        "do not establish performance on an unseen sensor or case.\n\n"
        "Practitioner validation has not been established. Pilot user feedback, "
        "if collected separately, must be reported with its participant group "
        "and limitations; it is not forensic expert certification.\n\n"
        "This report supports traceability and forensic scrutiny. It does not "
        "establish legal admissibility or compliance with Daubert or Frye "
        "standards. Independent review of the input, model, explanation and "
        "case circumstances is required."
    ))
    pdf.ln(8)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, "Signatures", ln=True)
    pdf.ln(4)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(90, 6, "Examiner: ___________________________", ln=False)
    pdf.cell(0, 6, "Date: ___________________", ln=True)
    pdf.ln(8)
    pdf.cell(90, 6, "Reviewer: ___________________________", ln=False)
    pdf.cell(0, 6, "Date: ___________________", ln=True)

    out = pdf.output(dest="S")
    if isinstance(out, str):
        return out.encode("latin-1")
    return bytes(out)
