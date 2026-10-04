"""Report preview must work without a browser PDF data-URL iframe."""

import unittest

from app.utils.pdf_preview import page_count, render_page_png
from app.utils.report_generator import build_report


class PdfPreviewTests(unittest.TestCase):
    def test_generated_report_pages_render_to_png(self):
        pdf = build_report(
            {"case_id": "CASE-PREVIEW-TEST", "examiner": "Fixture Examiner"},
            {"label": "live", "confidence": 0.9},
        )
        self.assertEqual(page_count(pdf), 3)
        first_page = render_page_png(pdf, 0)
        self.assertTrue(first_page.startswith(b"\x89PNG\r\n\x1a\n"))

    def test_out_of_range_page_is_rejected(self):
        pdf = build_report({"case_id": "CASE-PREVIEW-TEST"},
                           {"label": "spoof", "confidence": 0.8})
        with self.assertRaises(IndexError):
            render_page_png(pdf, page_count(pdf))


if __name__ == "__main__":
    unittest.main()
