"""Regression checks for compact navigation and equal batch export actions."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ActionLayoutTests(unittest.TestCase):
    def test_batch_exports_use_short_labels_and_shared_container(self):
        source = (ROOT / "app" / "views" / "batch_dashboard.py").read_text()
        self.assertIn('key="batch_export_actions"', source)
        self.assertIn('"Download CSV"', source)
        self.assertIn('"Download ZIP"', source)
        self.assertNotIn('"Download case bundle (ZIP)"', source)

    def test_sign_out_uses_content_width(self):
        source = (ROOT / "app" / "nav.py").read_text()
        self.assertIn('key="nav_signout", width="content"', source)

    def test_scoped_styles_preserve_equal_action_geometry(self):
        css = (ROOT / "app" / "theme.py").read_text()
        self.assertIn(".st-key-nav_signout", css)
        self.assertIn(".st-key-batch_export_actions", css)
        self.assertIn("height: 46px !important", css)


if __name__ == "__main__":
    unittest.main()
