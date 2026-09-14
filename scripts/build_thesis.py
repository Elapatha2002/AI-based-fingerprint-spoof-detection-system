"""
Build Thesis_Final.docx from structured content.

Generates a single Microsoft Word document containing:
  • Title page
  • Abstract
  • Acknowledgements
  • List of Abbreviations
  • Table of Contents  (auto-populated on first open in Word)
  • List of Figures    (auto-populated on first open in Word)
  • List of Tables     (auto-populated on first open in Word)
  • Chapter 1 — Introduction
  • Chapter 2 — Literature Review
  • Chapter 3 — Methodology
  • Chapter 4 — Results and Implementation
  • Chapter 5 — Discussion
  • Chapter 6 — Conclusion
  • References

Page numbers appear in the footer of every page. Formal academic
third-person voice throughout. Output file lands at the project root.
"""
from pathlib import Path

from docx import Document
from docx.shared import Pt, Inches, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT = PROJECT_ROOT / "Thesis_Final.docx"
FIGURES_DIR = PROJECT_ROOT / "assets" / "figures"


# ─────────────────────────────────────────────────────────────────────
# Styling helpers
# ─────────────────────────────────────────────────────────────────────

def setup_styles(doc: Document) -> None:
    """Set standard thesis styling: Times New Roman 12pt, 1.5 line spacing."""
    normal = doc.styles["Normal"]
    normal.font.name = "Times New Roman"
    normal.font.size = Pt(12)
    pf = normal.paragraph_format
    pf.line_spacing = 1.5
    pf.space_after = Pt(6)

    # Headings — Times New Roman, bold, sized appropriately
    for lvl, size in [(1, 18), (2, 14), (3, 12)]:
        h = doc.styles[f"Heading {lvl}"]
        h.font.name = "Times New Roman"
        h.font.size = Pt(size)
        h.font.bold = True
        h.font.color.rgb = RGBColor(0x00, 0x00, 0x00)
        h.paragraph_format.space_before = Pt(12)
        h.paragraph_format.space_after = Pt(6)


def add_title_page(doc: Document) -> None:
    """Insert a thesis-style title page."""
    for _ in range(4):
        doc.add_paragraph()

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("EXPLAINABLE AI-BASED FINGERPRINT SPOOF DETECTION SYSTEM "
                  "FOR DIGITAL FORENSICS")
    r.bold = True
    r.font.size = Pt(18)

    doc.add_paragraph()
    doc.add_paragraph()

    for line, italic, bold in [
        ("A dissertation submitted", True, False),
        ("", False, False),
        ("to the Faculty of Computing", False, False),
        ("NSBM Green University", False, False),
        ("in partial fulfilment of the requirements for the degree of", False, False),
        ("BSc (Hons) Software Engineering", False, False),
    ]:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(line)
        r.italic = italic
        r.bold = bold

    for _ in range(2):
        doc.add_paragraph()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run("by")
    doc.add_paragraph()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("K. M. Pasindu Chanuka Elapatha")
    r.bold = True
    r.font.size = Pt(14)

    doc.add_paragraph()
    doc.add_paragraph()

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("Supervised by")
    r.italic = True
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("Ms. Hirushi Dilpriya")
    r.bold = True
    r.font.size = Pt(13)

    for _ in range(4):
        doc.add_paragraph()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run("September 2026")

    doc.add_page_break()


def _add_caption(doc: Document, text: str) -> None:
    """Italic centred 10pt caption used for figures and tables."""
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(text)
    r.italic = True
    r.font.size = Pt(10)


def _add_figure(doc: Document, filename: str, caption: str) -> None:
    """Insert an image from assets/figures/ at 6 inches wide, centred, with caption."""
    img_path = FIGURES_DIR / filename
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run()
    if img_path.exists():
        run.add_picture(str(img_path), width=Inches(6.0))
    else:
        run.add_text(f"[Missing figure: {filename}]")
    if caption:
        _add_caption(doc, caption)


def _add_markdown_table(doc: Document, md_text: str, caption: str) -> None:
    """Insert a Word table from a pipe-delimited markdown-style block.

    First row is treated as the header. Cells are separated by '|', rows by '\\n'.
    Header row is bolded and shaded; body rows alternate subtle background.
    """
    rows = [line.strip() for line in md_text.split("\n") if line.strip()]
    rows = [r for r in rows if not set(r) <= set("|- ")]   # drop md alignment row if any
    if not rows:
        return
    matrix = [[cell.strip() for cell in r.split("|")] for r in rows]
    ncols = max(len(r) for r in matrix)
    matrix = [r + [""] * (ncols - len(r)) for r in matrix]

    table = doc.add_table(rows=len(matrix), cols=ncols)
    table.style = "Light Grid Accent 1"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER

    for i, row_data in enumerate(matrix):
        for j, cell_text in enumerate(row_data):
            cell = table.rows[i].cells[j]
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            cell.text = ""
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            run = p.add_run(cell_text)
            run.font.size = Pt(10)
            if i == 0:
                run.font.bold = True
                run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
                # Shade header row dark blue-grey
                tcPr = cell._tc.get_or_add_tcPr()
                shd = OxmlElement("w:shd")
                shd.set(qn("w:val"), "clear")
                shd.set(qn("w:color"), "auto")
                shd.set(qn("w:fill"), "2C3E50")
                tcPr.append(shd)

    if caption:
        _add_caption(doc, caption)


def render_blocks(doc: Document, blocks) -> None:
    """Render a list of (kind, text[, caption]) tuples as Word paragraphs.

    Supported kinds:
        h1, h2, h3      — headings at the corresponding level
        p                — body paragraph (justified)
        bullet           — bullet list item
        numbered         — numbered list item
        quote            — italic block quote
        caption          — figure / table caption (italic, centred, 10pt)
        figure           — insert PNG from assets/figures/<text>; third item is caption
        table_md         — pipe-delimited markdown table; third item is caption
        pagebreak        — start new page
    """
    for block in blocks:
        if len(block) == 2:
            kind, text = block
            caption = ""
        elif len(block) == 3:
            kind, text, caption = block
        else:
            raise ValueError(f"block tuple must have 2 or 3 elements: {block!r}")

        if kind == "h1":
            doc.add_heading(text, level=1)
        elif kind == "h2":
            doc.add_heading(text, level=2)
        elif kind == "h3":
            doc.add_heading(text, level=3)
        elif kind == "p":
            p = doc.add_paragraph(text)
            p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        elif kind == "bullet":
            doc.add_paragraph(text, style="List Bullet")
        elif kind == "numbered":
            doc.add_paragraph(text, style="List Number")
        elif kind == "quote":
            p = doc.add_paragraph()
            r = p.add_run(text)
            r.italic = True
            p.paragraph_format.left_indent = Cm(1.0)
        elif kind == "caption":
            _add_caption(doc, text)
        elif kind == "figure":
            _add_figure(doc, text, caption)
        elif kind == "table_md":
            _add_markdown_table(doc, text, caption)
        elif kind == "pagebreak":
            doc.add_page_break()
        else:
            raise ValueError(f"unknown block kind: {kind}")


# ─────────────────────────────────────────────────────────────────────
# Chapter content
# ─────────────────────────────────────────────────────────────────────

from chapter_content import (
    ABSTRACT, ACKNOWLEDGEMENTS, ABBREVIATIONS,
    CHAPTER_1, CHAPTER_2, CHAPTER_3, CHAPTER_4, CHAPTER_5, CHAPTER_6,
    REFERENCES,
)


def _add_field_page(doc: Document, title: str, instr_text: str,
                     placeholder: str) -> None:
    """Generic helper that drops a Word field on its own page. Used for
    Table of Contents, List of Figures, and List of Tables — all three
    are Word field codes that behave identically."""
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(title)
    r.bold = True
    r.font.size = Pt(18)

    doc.add_paragraph()  # spacer

    p = doc.add_paragraph()
    run = p.add_run()

    fld_begin = OxmlElement("w:fldChar")
    fld_begin.set(qn("w:fldCharType"), "begin")

    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = instr_text

    fld_sep = OxmlElement("w:fldChar")
    fld_sep.set(qn("w:fldCharType"), "separate")

    ph = OxmlElement("w:t")
    ph.text = placeholder

    fld_end = OxmlElement("w:fldChar")
    fld_end.set(qn("w:fldCharType"), "end")

    run._r.append(fld_begin)
    run._r.append(instr)
    run._r.append(fld_sep)
    run._r.append(ph)
    run._r.append(fld_end)

    doc.add_page_break()


def add_list_of_figures(doc: Document) -> None:
    """Word field that lists every 'Figure X.Y: ...' caption once refreshed."""
    _add_field_page(
        doc,
        title="List of Figures",
        # \h = hyperlinks, \z = suppress web-view tab leaders, \c "Figure" = filter
        instr_text='TOC \\h \\z \\c "Figure"',
        placeholder=("[Right-click here and choose 'Update Field' in Word "
                     "to populate the list of figures.]"),
    )


def add_list_of_tables(doc: Document) -> None:
    """Word field that lists every 'Table X.Y: ...' caption once refreshed."""
    _add_field_page(
        doc,
        title="List of Tables",
        instr_text='TOC \\h \\z \\c "Table"',
        placeholder=("[Right-click here and choose 'Update Field' in Word "
                     "to populate the list of tables.]"),
    )


def add_table_of_contents(doc: Document) -> None:
    """Insert a Word TOC field that auto-populates from Heading 1/2/3 styles.

    The field is empty until the reader opens the document in Word and
    right-clicks the placeholder -> Update Field. This is the same pattern
    Word itself uses when TOCs are inserted via the References menu.
    """
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("Table of Contents")
    r.bold = True
    r.font.size = Pt(18)

    doc.add_paragraph()  # spacer

    p = doc.add_paragraph()
    run = p.add_run()

    fld_begin = OxmlElement("w:fldChar")
    fld_begin.set(qn("w:fldCharType"), "begin")

    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    # \o "1-3"  headings 1..3
    # \h        hyperlinks
    # \z        hide tab leader in web view
    # \u        use paragraph outline level
    instr.text = 'TOC \\o "1-3" \\h \\z \\u'

    fld_sep = OxmlElement("w:fldChar")
    fld_sep.set(qn("w:fldCharType"), "separate")

    placeholder = OxmlElement("w:t")
    placeholder.text = ("[Right-click here and choose 'Update Field' in Word "
                        "to populate the table of contents.]")

    fld_end = OxmlElement("w:fldChar")
    fld_end.set(qn("w:fldCharType"), "end")

    run._r.append(fld_begin)
    run._r.append(instr)
    run._r.append(fld_sep)
    run._r.append(placeholder)
    run._r.append(fld_end)

    doc.add_page_break()


def add_page_numbers(doc: Document) -> None:
    """Add a centred 'Page X' number to the footer of every page."""
    section = doc.sections[0]
    footer = section.footer
    p = footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.text = ""

    # Add "Page "
    run = p.add_run("Page ")
    run.font.size = Pt(9)

    # Add PAGE field
    run2 = p.add_run()
    run2.font.size = Pt(9)

    fld_begin = OxmlElement("w:fldChar")
    fld_begin.set(qn("w:fldCharType"), "begin")

    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = "PAGE"

    fld_end = OxmlElement("w:fldChar")
    fld_end.set(qn("w:fldCharType"), "end")

    run2._r.append(fld_begin)
    run2._r.append(instr)
    run2._r.append(fld_end)


def main():
    doc = Document()
    setup_styles(doc)

    # Front matter — order matches typical NSBM submission layout
    add_title_page(doc)
    render_blocks(doc, ABSTRACT)
    render_blocks(doc, ACKNOWLEDGEMENTS)
    render_blocks(doc, ABBREVIATIONS)
    add_table_of_contents(doc)
    add_list_of_figures(doc)
    add_list_of_tables(doc)

    # Main matter — one chapter per page-break
    for chapter in (CHAPTER_1, CHAPTER_2, CHAPTER_3,
                    CHAPTER_4, CHAPTER_5, CHAPTER_6):
        render_blocks(doc, chapter)
        doc.add_page_break()

    # Back matter
    render_blocks(doc, REFERENCES)

    add_page_numbers(doc)

    try:
        doc.save(OUTPUT)
        actual = OUTPUT
    except PermissionError:
        # Target file is locked (probably open in Word). Save to a fresh name.
        from datetime import datetime
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        actual = OUTPUT.with_name(f"Thesis_Chapters_1-3_{stamp}.docx")
        doc.save(actual)
        print(f"NOTE: {OUTPUT.name} was locked - saved to {actual.name} instead.")
        print(f"      Close the document in Word and re-run to overwrite the main file.")
    print(f"Wrote {actual}")
    print(f"File size: {actual.stat().st_size / 1024:.1f} KB")


if __name__ == "__main__":
    main()
