"""Regression checks for lightweight model configuration and Git LFS files."""
from pathlib import Path
from types import SimpleNamespace
import os
import tempfile
import unittest
from unittest.mock import Mock, patch

from app import nav
from app.services import model_config


class CheckpointStateTests(unittest.TestCase):
    def test_git_lfs_pointer_is_reported_before_pytorch_load(self):
        with tempfile.TemporaryDirectory(prefix="fsd_lfs_") as folder:
            checkpoint = Path(folder) / "best.pth"
            checkpoint.write_bytes(
                b"version https://git-lfs.github.com/spec/v1\n"
                b"oid sha256:0000000000000000000000000000000000000000000000000000000000000000\n"
                b"size 123\n"
            )
            self.assertEqual(model_config.checkpoint_state(checkpoint)[0], "lfs_pointer")
            with self.assertRaisesRegex(RuntimeError, "git lfs pull"):
                model_config.require_materialized_checkpoint(checkpoint)

    def test_binary_checkpoint_is_ready(self):
        with tempfile.TemporaryDirectory(prefix="fsd_model_") as folder:
            checkpoint = Path(folder) / "best.pth"
            checkpoint.write_bytes(b"PK\x03\x04pytorch-model-data")
            self.assertEqual(model_config.checkpoint_state(checkpoint)[0], "ready")


class NavigationModelTests(unittest.TestCase):
    def test_statusbar_does_not_import_or_load_real_model(self):
        fake_streamlit = SimpleNamespace(
            session_state={"decision_threshold": 0.5},
            markdown=Mock(),
        )
        poison = SimpleNamespace(
            get_service_info=Mock(side_effect=AssertionError("model was loaded"))
        )
        storage = SimpleNamespace(
            LocalStorageService=type("LocalStorageService", (), {}),
            get_storage=Mock(return_value=object()),
        )
        auth = SimpleNamespace(offline_mode_enabled=Mock(return_value=False))
        with patch.object(nav, "st", fake_streamlit), \
                patch.dict(os.environ, {"FSDXAI_REAL_MODEL": "1"}), \
                patch.dict("sys.modules", {
                    "app.services.real_model": poison,
                    "app.services.auth": auth,
                    "app.services.storage": storage,
                }):
            nav.render_statusbar()
        poison.get_service_info.assert_not_called()
        fake_streamlit.markdown.assert_called_once()


if __name__ == "__main__":
    unittest.main()
