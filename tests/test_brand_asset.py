"""Brand asset and application placement regression checks."""
from pathlib import Path
import unittest

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
LOGO = ROOT / "app" / "static" / "brand" / "fsd-xai-logo.png"


class BrandAssetTests(unittest.TestCase):
    def test_logo_is_square_transparent_png(self):
        self.assertTrue(LOGO.is_file())
        with Image.open(LOGO) as image:
            self.assertEqual(image.format, "PNG")
            self.assertEqual(image.width, image.height)
            self.assertIn("A", image.getbands())
            self.assertEqual(image.getchannel("A").getextrema()[0], 0)

    def test_logo_is_referenced_by_login_navigation_and_favicon(self):
        expected = "app/static/brand/fsd-xai-logo.png"
        self.assertIn(expected, (ROOT / "app" / "views" / "login.py").read_text())
        self.assertIn(expected, (ROOT / "app" / "nav.py").read_text())
        app_source = (ROOT / "app" / "streamlit_app.py").read_text()
        self.assertIn('"fsd-xai-logo.png"', app_source)

    def test_static_serving_is_enabled_for_both_launch_locations(self):
        for config in (ROOT / ".streamlit" / "config.toml",
                       ROOT / "app" / ".streamlit" / "config.toml"):
            self.assertIn("enableStaticServing = true", config.read_text())


if __name__ == "__main__":
    unittest.main()
