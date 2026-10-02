"""Signed browser-session persistence and revocation tests."""
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from app.services import auth, database


SECRET = "fixture-session-secret-that-is-longer-than-32-bytes"


class BrowserSessionTests(unittest.TestCase):
    def setUp(self):
        self.env = self.enterContext(
            patch.dict("os.environ", {"FSDXAI_SESSION_SECRET": SECRET})
        )
        self.user = {
            "user_id": "USR-session-fixture",
            "username": "examiner",
            "password_hash": "not-returned-to-browser",
            "role": "examiner",
            "full_name": "Fixture Examiner",
            "email": "",
            "active": 1,
            "session_version": 3,
        }

    def test_signed_token_round_trip_and_tamper_rejection(self):
        token = auth._make_session_token(self.user, now=1_000)
        payload = auth._read_session_token(token, now=1_001)
        self.assertEqual(payload["uid"], self.user["user_id"])
        self.assertEqual(payload["sv"], 3)
        self.assertIsNone(auth._read_session_token(token + "x", now=1_001))
        self.assertIsNone(
            auth._read_session_token(token, now=1_000 + auth.SESSION_COOKIE_SECONDS)
        )

    def test_refresh_restores_only_an_active_matching_account(self):
        token = auth._make_session_token(self.user, now=1_000)
        fake_st = SimpleNamespace(
            session_state={},
            context=SimpleNamespace(cookies={auth.SESSION_COOKIE_NAME: token}),
        )
        with patch.object(auth, "st", fake_st), \
                patch.object(auth.time, "time", return_value=1_001), \
                patch.object(database, "get_user", return_value=self.user):
            restored = auth.current_user()
        self.assertEqual(restored["user_id"], self.user["user_id"])
        self.assertNotIn("password_hash", restored)

    def test_version_change_rejects_and_marks_cookie_for_deletion(self):
        token = auth._make_session_token(self.user, now=1_000)
        fake_st = SimpleNamespace(
            session_state={},
            context=SimpleNamespace(cookies={auth.SESSION_COOKIE_NAME: token}),
        )
        changed = dict(self.user, session_version=4)
        with patch.object(auth, "st", fake_st), \
                patch.object(auth.time, "time", return_value=1_001), \
                patch.object(database, "get_user", return_value=changed):
            self.assertIsNone(auth.current_user())
        self.assertTrue(fake_st.session_state[auth._CLEAR_COOKIE_KEY])

    def test_temporary_database_failure_keeps_cookie_for_retry(self):
        token = auth._make_session_token(self.user, now=1_000)
        fake_st = SimpleNamespace(
            session_state={},
            context=SimpleNamespace(cookies={auth.SESSION_COOKIE_NAME: token}),
        )
        with patch.object(auth, "st", fake_st), \
                patch.object(auth.time, "time", return_value=1_001), \
                patch.object(database, "get_user", side_effect=RuntimeError("offline")):
            self.assertIsNone(auth.current_user())
        self.assertNotIn(auth._CLEAR_COOKIE_KEY, fake_st.session_state)


if __name__ == "__main__":
    unittest.main()
