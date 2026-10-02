"""Optional Edge check for browser -> loopback bridge -> Streamlit value."""
import base64
import io
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import tempfile
import threading

from PIL import Image
from playwright.sync_api import sync_playwright

ORIGIN = "http://127.0.0.1:8515"
TOKEN = "browser-fixture-token"


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def headers_common(self):
        self.send_header("Access-Control-Allow-Origin", ORIGIN)
        self.send_header("Access-Control-Allow-Private-Network", "true")

    def send_json(self, payload):
        body = json.dumps(payload).encode()
        self.send_response(200)
        self.headers_common()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.headers_common()
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-FSD-Bridge-Token")
        self.end_headers()

    def authorized(self):
        return (self.headers.get("Origin") == ORIGIN and
                self.headers.get("X-FSD-Bridge-Token") == TOKEN)

    def do_GET(self):
        if not self.authorized():
            self.send_error(401)
            return
        self.send_json({"ok": True, "make": "Fixture", "model": "MFS100"})

    def do_POST(self):
        if not self.authorized():
            self.send_error(401)
            return
        stream = io.BytesIO()
        Image.new("L", (32, 48), 128).save(stream, format="PNG")
        self.send_json({
            "ok": True, "capture_id": "browser-test", "width": 32,
            "height": 48, "dpi": 500, "quality": 75, "nfiq": 2,
            "captured_at": "2026-10-02T00:00:00Z",
            "image_base64": base64.b64encode(stream.getvalue()).decode(),
        })


def main():
    output = Path(tempfile.mkdtemp(prefix="fsd_mantra_component_"))
    server = ThreadingHTTPServer(("127.0.0.1", 18766), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(channel="msedge", headless=True)
            page = browser.new_page(viewport={"width": 900, "height": 700})
            page.goto(ORIGIN)
            page.get_by_text("Mantra capture fixture", exact=True).wait_for()
            frame = page.frame_locator('iframe[title$="fsd_mantra_capture"]')
            frame.get_by_placeholder("Pairing code from bridge window").fill(TOKEN)
            frame.get_by_role("button", name="Connect").click()
            frame.get_by_text("Fixture MFS100 ready", exact=True).wait_for()
            frame.get_by_role("button", name="Capture fingerprint").click()
            page.get_by_text("Received capture browser-test", exact=True).wait_for()
            frame.get_by_text("Fingerprint captured successfully", exact=True).wait_for()
            page.screenshot(path=str(output / "mantra-component.png"), full_page=True)
            assert page.get_by_test_id("stException").count() == 0
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
    print(json.dumps({"result": "passed", "screenshot": str(output / "mantra-component.png")}))


if __name__ == "__main__":
    main()
