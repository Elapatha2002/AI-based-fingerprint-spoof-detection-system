"""Mantra MFS100 integration tests; no physical scanner or cloud access."""
import base64
import io
import json
import os
from pathlib import Path
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from PIL import Image

from app.services import mantra_sensor
from tools.mantra_bridge import bridge


class MantraServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        content = io.BytesIO()
        Image.new("L", (32, 48), 128).save(content, format="PNG")
        cls.image = content.getvalue()

    def payload(self):
        return {
            "ok": True,
            "image_base64": base64.b64encode(self.image).decode("ascii"),
            "width": 32, "height": 48, "dpi": 500, "quality": 72,
            "nfiq": 2, "serial": "TEST-123", "capture_id": "capture-1",
            "captured_at": "2026-10-02T00:00:00+00:00",
        }

    def test_real_capture_decodes_valid_sdk_image(self):
        with patch.object(mantra_sensor, "capture_transport", return_value="direct"), \
             patch.object(mantra_sensor, "_run_sdk_helper", return_value=self.payload()):
            result = mantra_sensor._real_capture(timeout_seconds=5)
        self.assertEqual(result.image_bytes, self.image)
        self.assertEqual((result.width, result.height, result.quality), (32, 48, 72))
        self.assertEqual(result.device_serial, "TEST-123")

    def test_invalid_sdk_image_is_rejected(self):
        payload = self.payload()
        payload["image_base64"] = base64.b64encode(b"not an image").decode("ascii")
        with patch.object(mantra_sensor, "capture_transport", return_value="direct"), \
             patch.object(mantra_sensor, "_run_sdk_helper", return_value=payload):
            with self.assertRaisesRegex(mantra_sensor.MantraSensorError, "invalid image"):
                mantra_sensor._real_capture(timeout_seconds=5)

    def test_hosted_transport_cannot_call_server_usb(self):
        with patch.object(mantra_sensor, "capture_transport", return_value="bridge"):
            with self.assertRaisesRegex(mantra_sensor.MantraSensorError, "browser-side"):
                mantra_sensor._real_capture(timeout_seconds=5)

    def test_real_is_default_and_mock_requires_explicit_setting(self):
        with patch.dict(os.environ, {"MANTRA_SENSOR_MODE": ""}):
            self.assertEqual(mantra_sensor.current_mode(), "real")
        with patch.dict(os.environ, {"MANTRA_SENSOR_MODE": "mock"}):
            self.assertEqual(mantra_sensor.current_mode(), "mock")

    def test_capture_helper_uses_autocapture_not_replaceable_file(self):
        helper = (Path(__file__).resolve().parents[1] / "tools" / "mantra_bridge" /
                  "capture.ps1").read_text(encoding="utf-8")
        self.assertIn("AutoCapture", helper)
        self.assertNotIn("FingerImage.bmp", helper)
        self.assertIn("[IntPtr]::Size -ne 4", helper)


class BridgeSecurityTests(unittest.TestCase):
    def setUp(self):
        self.origin = "https://fsd.test"
        self.token = "fixture-secret-token"
        self.server = bridge.BridgeServer(
            ("127.0.0.1", 0), bridge.Handler, token=self.token,
            origins={self.origin}, timeout=5,
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.url = f"http://127.0.0.1:{self.server.server_port}"

    def request(self, path, *, method="GET", origin=None, token=None):
        headers = {}
        if origin is not None:
            headers["Origin"] = origin
        if token is not None:
            headers["X-FSD-Bridge-Token"] = token
        if method == "POST":
            headers["Content-Type"] = "application/json"
        req = Request(self.url + path, method=method, headers=headers,
                      data=b"{}" if method == "POST" else None)
        with urlopen(req, timeout=3) as response:
            return response.status, dict(response.headers), json.loads(response.read())

    def test_bridge_binds_loopback_only(self):
        self.assertEqual(self.server.server_address[0], "127.0.0.1")

    def test_status_rejects_unapproved_origin_and_bad_token(self):
        with self.assertRaises(HTTPError) as wrong_origin:
            self.request("/status", origin="https://evil.test", token=self.token)
        self.assertEqual(wrong_origin.exception.code, 403)
        with self.assertRaises(HTTPError) as wrong_token:
            self.request("/status", origin=self.origin, token="wrong")
        self.assertEqual(wrong_token.exception.code, 401)

    def test_authorized_capture_returns_sdk_payload(self):
        payload = {"ok": True, "capture_id": "one", "image_base64": "abc"}
        with patch.object(bridge, "run_sdk", return_value=(200, payload)) as sdk:
            status, headers, response = self.request(
                "/capture", method="POST", origin=self.origin, token=self.token)
        self.assertEqual(status, 200)
        self.assertEqual(response, payload)
        self.assertEqual(headers["Access-Control-Allow-Origin"], self.origin)
        self.assertNotIn(self.token, json.dumps(response))
        sdk.assert_called_once_with("capture", 5)

    def test_preflight_allows_required_private_network_headers(self):
        request = Request(self.url + "/capture", method="OPTIONS", headers={
            "Origin": self.origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Private-Network": "true",
        })
        with urlopen(request, timeout=3) as response:
            self.assertEqual(response.status, 204)
            self.assertEqual(response.headers["Access-Control-Allow-Private-Network"], "true")
            self.assertIn("X-FSD-Bridge-Token",
                          response.headers["Access-Control-Allow-Headers"])

    def test_browser_component_keeps_pairing_code_local(self):
        html = (Path(__file__).resolve().parents[1] / "app" / "components" /
                "mantra_capture_frontend" / "index.html").read_text(encoding="utf-8")
        self.assertIn('localStorage.setItem(TOKEN_KEY, token())', html)
        self.assertIn('targetAddressSpace: "loopback"', html)
        self.assertIn("setValue(payload)", html)
        self.assertNotIn("setValue(token", html)


if __name__ == "__main__":
    unittest.main()
