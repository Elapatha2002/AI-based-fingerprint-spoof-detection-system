"""
Mantra MFS100 fingerprint sensor abstraction.

Two modes:

  MOCK — returns a real LivDet image, picked at random from the local
         test partition. Used before the physical sensor arrives, in
         CI environments, and as a fallback when the SDK can't reach the
         device. No hardware needed.

  REAL — calls the Mantra MFS100 SDK directly when Streamlit is local, or
         receives a capture from the authenticated loopback bridge when the
         application is hosted.

Both modes return the same MantraCaptureResult, so downstream code
does not need to change when we swap them.

The mode is chosen by the MANTRA_SENSOR_MODE environment variable:

    unset or "real" -> REAL
    "mock"          -> MOCK (development/test only)

Set MANTRA_SENSOR_MODE=mock explicitly only when a sensor demonstration
is intentionally being simulated.
"""
from __future__ import annotations

import base64
import io
import json
import os
import random
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from PIL import Image, ImageFile
from dotenv import load_dotenv

ImageFile.LOAD_TRUNCATED_IMAGES = True

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")


# Mock-mode source of realistic fingerprint samples. Points at the LivDet
# Normalized test partition, so mock captures look like the sensor's target
# distribution.
_MOCK_LIVE_DIR = PROJECT_ROOT / "DataSet" / "LivDet Datasets" / "Normalized" / "test" / "live"
_MOCK_SPOOF_DIR = PROJECT_ROOT / "DataSet" / "LivDet Datasets" / "Normalized" / "test" / "spoof"
_CAPTURE_HELPER = PROJECT_ROOT / "tools" / "mantra_bridge" / "capture.ps1"
_DEFAULT_SDK_DIR = Path(r"C:\Program Files\Mantra\MFS100\Driver\MFS100Test")


# ── Data class ────────────────────────────────────────────────────────

@dataclass
class MantraCaptureResult:
    """Everything a downstream consumer needs from a single capture."""

    image_bytes: bytes                 # PNG-encoded raw image
    width: int                         # pixels
    height: int                        # pixels
    dpi: int                           # nominal DPI (500 for MFS100)
    quality: Optional[int]             # 0-100, or None if unavailable
    captured_at: str                   # ISO timestamp
    mode: str                          # "mock" or "real"
    device_serial: Optional[str] = None  # populated in real mode

    def pil_image(self) -> Image.Image:
        return Image.open(io.BytesIO(self.image_bytes))


# ── Mode selection ────────────────────────────────────────────────────

def current_mode() -> str:
    """Return 'real' or 'mock' — never anything else."""
    return "mock" if os.environ.get("MANTRA_SENSOR_MODE", "real").lower() == "mock" else "real"


def capture_transport() -> str:
    """Return ``direct`` or ``bridge`` for real capture.

    Direct capture is possible only when Streamlit itself runs on the Windows
    PC containing the SDK. A hosted server must ask the browser-side bridge.
    ``MANTRA_SENSOR_TRANSPORT`` can override the automatic choice.
    """
    configured = os.environ.get("MANTRA_SENSOR_TRANSPORT", "auto").strip().lower()
    if configured in {"direct", "bridge"}:
        return configured
    sdk_dir = Path(os.environ.get("MFS100_SDK_DIR", str(_DEFAULT_SDK_DIR)))
    return "direct" if os.name == "nt" and (sdk_dir / "MANTRA.MFS100.dll").is_file() else "bridge"


def bridge_url() -> str:
    return os.environ.get("MANTRA_BRIDGE_URL", "http://127.0.0.1:8765").rstrip("/")


def is_available() -> tuple[bool, str]:
    """Cheap check the calling UI can display before showing the Capture
    button. Never raises.

    Returns (available, human_readable_status)."""
    mode = current_mode()
    if mode == "real" and capture_transport() == "direct":
        ok, msg = _real_sdk_available()
        return ok, msg
    if mode == "real":
        return True, "Use the local MFS100 bridge in this browser"
    # Mock mode is always available if the LivDet test folder exists
    if _MOCK_LIVE_DIR.exists() or _MOCK_SPOOF_DIR.exists():
        return True, "Mock mode — sensor emulator ready"
    return False, ("Mock mode requires LivDet Normalized/test folder; "
                   "add real images or connect the sensor + set "
                   "MANTRA_SENSOR_MODE=real")


# ── Public capture API ────────────────────────────────────────────────

def capture_fingerprint(*, prefer_class: Optional[str] = None,
                        timeout_seconds: float = 15.0) -> MantraCaptureResult:
    """Capture one fingerprint from the sensor (or the mock).

    Args:
        prefer_class:    In mock mode, "live" or "spoof" biases the
                         random pick toward that folder so a demo can
                         script a deterministic sequence. In real mode
                         this argument is ignored — the sensor doesn't
                         know ahead of time whether it's seeing a spoof.
        timeout_seconds: How long to wait for a finger to be placed on
                         the sensor before giving up. Real mode only.

    Raises:
        MantraSensorError: if capture fails for any reason.
    """
    if current_mode() == "real":
        return _real_capture(timeout_seconds=timeout_seconds)
    return _mock_capture(prefer_class=prefer_class)


class MantraSensorError(RuntimeError):
    pass


# ── Mock implementation ───────────────────────────────────────────────

def _mock_capture(prefer_class: Optional[str] = None) -> MantraCaptureResult:
    """Pick a random image from the LivDet test partition and return it as
    if it had just come off the sensor. Introduces a small artificial
    latency so demos feel real."""
    time.sleep(random.uniform(0.35, 0.7))

    candidates: list[Path] = []
    if prefer_class == "live" and _MOCK_LIVE_DIR.exists():
        candidates = list(_MOCK_LIVE_DIR.glob("*.*"))
    elif prefer_class == "spoof" and _MOCK_SPOOF_DIR.exists():
        candidates = list(_MOCK_SPOOF_DIR.glob("*.*"))
    else:
        for d in (_MOCK_LIVE_DIR, _MOCK_SPOOF_DIR):
            if d.exists():
                candidates.extend(d.glob("*.*"))

    if not candidates:
        raise MantraSensorError(
            "Mock mode has no source images. Ensure LivDet Normalized/test "
            "exists, or plug in the sensor and set MANTRA_SENSOR_MODE=real."
        )

    src = random.choice(candidates)
    with Image.open(src) as img:
        img = img.convert("L")   # grayscale, matching the sensor
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        w, h = img.size

    return MantraCaptureResult(
        image_bytes=buf.getvalue(),
        width=w, height=h,
        dpi=500,
        quality=random.randint(58, 92),
        captured_at=datetime.now().isoformat(timespec="seconds"),
        mode="mock",
        device_serial="MOCK-DEV-0001",
    )


# ── Real SDK implementation ───────────────────────────────────────

def _powershell32() -> Path:
    if os.name != "nt":
        raise MantraSensorError("Direct MFS100 capture requires Windows.")
    windows = Path(os.environ.get("WINDIR", r"C:\Windows"))
    candidates = [
        windows / "SysWOW64" / "WindowsPowerShell" / "v1.0" / "powershell.exe",
        windows / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise MantraSensorError("32-bit Windows PowerShell was not found.")


def _run_sdk_helper(action: str, timeout_seconds: float = 15.0) -> dict:
    if not _CAPTURE_HELPER.is_file():
        raise MantraSensorError(f"MFS100 helper is missing: {_CAPTURE_HELPER}")
    sdk_dir = os.environ.get("MFS100_SDK_DIR", str(_DEFAULT_SDK_DIR))
    command = [
        str(_powershell32()), "-NoProfile", "-NonInteractive",
        "-ExecutionPolicy", "Bypass", "-File", str(_CAPTURE_HELPER),
        "-Action", action, "-TimeoutSeconds", str(max(1, int(timeout_seconds))),
        "-SdkDirectory", sdk_dir,
    ]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=max(10.0, timeout_seconds + 10.0),
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except subprocess.TimeoutExpired as exc:
        raise MantraSensorError("The MFS100 SDK did not respond before the timeout.") from exc
    except OSError as exc:
        raise MantraSensorError(f"Could not start the MFS100 helper: {exc}") from exc

    payload = None
    for line in reversed(completed.stdout.splitlines()):
        try:
            candidate = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(candidate, dict) and "ok" in candidate:
            payload = candidate
            break
    if not payload:
        detail = completed.stderr.strip() or "The helper returned no valid response."
        raise MantraSensorError(detail)
    if not payload.get("ok"):
        raise MantraSensorError(payload.get("error") or "MFS100 operation failed.")
    return payload

def _real_sdk_available() -> tuple[bool, str]:
    """Check whether the Mantra SDK is present and the device is reachable.

    This is a bounded SDK initialization probe; it never raises.
    """
    try:
        payload = _run_sdk_helper("status", timeout_seconds=5)
        name = " ".join(filter(None, [payload.get("make"), payload.get("model")])).strip()
        serial = payload.get("serial") or "serial unavailable"
        return True, f"{name or 'Mantra MFS100'} ready ({serial})"
    except MantraSensorError as exc:
        return False, str(exc)


def _real_capture(*, timeout_seconds: float) -> MantraCaptureResult:
    """Start AutoCapture and return its in-memory PNG result."""
    if capture_transport() != "direct":
        raise MantraSensorError(
            "This Streamlit server cannot access the local USB scanner. "
            "Use the browser-side Mantra bridge."
        )
    payload = _run_sdk_helper("capture", timeout_seconds=timeout_seconds)
    try:
        image_bytes = base64.b64decode(payload["image_base64"], validate=True)
        with Image.open(io.BytesIO(image_bytes)) as image:
            image.verify()
    except (KeyError, ValueError, OSError) as exc:
        raise MantraSensorError("The MFS100 SDK returned an invalid image.") from exc
    return MantraCaptureResult(
        image_bytes=image_bytes,
        width=int(payload["width"]),
        height=int(payload["height"]),
        dpi=int(payload.get("dpi") or 500),
        quality=(int(payload["quality"])
                 if payload.get("quality") is not None else None),
        captured_at=payload.get("captured_at") or datetime.now().isoformat(timespec="seconds"),
        mode="real",
        device_serial=payload.get("serial"),
    )
