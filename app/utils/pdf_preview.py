"""Render generated PDF pages on the server for browser-independent previews."""

from __future__ import annotations

def page_count(pdf_bytes: bytes) -> int:
    """Read the actual number of pages instead of assuming a fixed layout."""
    import pymupdf

    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as document:
        return len(document)


def render_page_png(pdf_bytes: bytes, page_index: int, *, dpi: int = 120) -> bytes:
    """Render one page to PNG; the browser never has to open a PDF data URL."""
    import pymupdf

    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as document:
        if not 0 <= page_index < len(document):
            raise IndexError("Report page is out of range")
        return document[page_index].get_pixmap(dpi=dpi, alpha=False).tobytes("png")
