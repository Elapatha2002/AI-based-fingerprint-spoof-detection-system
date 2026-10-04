"""Explicit case saves report the failed phase without leaking credentials."""

import unittest
from unittest.mock import MagicMock, patch

from app.services import database, persistence, storage


class PersistenceErrorsTests(unittest.TestCase):
    def test_missing_image_is_identified_before_any_write(self):
        with patch.object(persistence, "_ensure_case") as ensure_case:
            with self.assertRaises(persistence.PersistenceSaveError) as caught:
                persistence.save_single_analysis(
                    filename="empty.bmp", image_bytes=b"",
                    meta={"case_id": "CASE-TEST"}, result={},
                    raise_on_error=True,
                )
        self.assertEqual(caught.exception.stage, "validation")
        ensure_case.assert_not_called()

    def test_storage_upload_error_has_safe_stage(self):
        service = MagicMock()
        service.upload_bytes.side_effect = RuntimeError("secret endpoint details")
        with patch.object(persistence, "_ensure_case"), \
             patch.object(storage, "get_storage", return_value=service), \
             patch.object(database, "record_analysis") as record:
            with self.assertRaises(persistence.PersistenceSaveError) as caught:
                persistence.save_single_analysis(
                    filename="finger.bmp", image_bytes=b"image",
                    meta={"case_id": "CASE-TEST"}, result={},
                    raise_on_error=True,
                )
        self.assertEqual(caught.exception.stage, "image")
        self.assertNotIn("secret endpoint", str(caught.exception))
        record.assert_not_called()

    def test_failed_case_insert_is_not_silently_ignored(self):
        with patch.object(database, "get_case", side_effect=[None, None]), \
             patch.object(database, "connect", side_effect=RuntimeError("insert failed")):
            with self.assertRaisesRegex(RuntimeError, "insert failed"):
                persistence._ensure_case("CASE-TEST", "Fixture Examiner")


if __name__ == "__main__":
    unittest.main()
