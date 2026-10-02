"""Login transport retry and password-control style regression checks."""
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from psycopg import OperationalError

from app.services import auth, database


ROOT = Path(__file__).resolve().parents[1]


class LoginResilienceTests(unittest.TestCase):
    def test_transient_postgres_read_is_retried_once(self):
        password = "Fixture-password-2026!"
        user = {
            "user_id": "USR-fixture", "username": "fixture",
            "password_hash": auth.hash_password(password),
            "role": "examiner", "full_name": "Fixture Examiner",
            "email": "", "active": 1, "session_version": 0,
        }
        fake_st = SimpleNamespace(session_state={})
        lookup = Mock(side_effect=[OperationalError("temporary"), user])
        with patch.object(auth, "st", fake_st), \
                patch.object(database, "using_postgres", return_value=True), \
                patch.object(database, "get_user_by_username", lookup), \
                patch.object(database, "touch_last_login"):
            ok, message = auth.login("fixture", password)
        self.assertTrue(ok)
        self.assertEqual(message, "")
        self.assertEqual(lookup.call_count, 2)

    def test_password_toggle_styles_are_scoped_and_centered(self):
        css = (ROOT / "app" / "theme.py").read_text()
        self.assertIn('input:-webkit-autofill', css)
        self.assertIn('justify-content: center !important', css)
        self.assertIn('padding: 0 !important', css)
        self.assertIn('button:hover', css)


if __name__ == "__main__":
    unittest.main()
