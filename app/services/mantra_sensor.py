"""
Mantra MFS100 fingerprint sensor abstraction.

Two modes:

  MOCK — returns a real LivDet image, picked at random from the local
         test partition. Used before the physical sensor arrives, in
         CI environments, and as a fallback when the SDK can't reach the
         device. No hardware needed.

  REAL — calls the Mantra MFS100 SDK to capture from the USB device.
         Implementation TODO: filled in once the sensor arrives and the
         SDK is downloaded from the Mantra developer portal.

Both modes return the same MantraCaptureResult, so downstream code
does not need to change when we swap them.

The mode is chosen by the MANTRA_SENSOR_MODE environment variable:

    unset or "mock" -> MOCK
    "real"          -> REAL

We keep the mock as the default so the demo apps run out of the box on
any machine even without the sensor plugged in. When rehearsing the
final viva flow, set MANTRA_SENSOR_MODE=real in .env.
"""
from __future__ import annotations

import io
import os
import random
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
    return "real" if os.environ.get("MANTRA_SENSOR_MODE", "mock").lower() == "real" else "mock"


def is_available() -> tuple[bool, str]:
    """Cheap check the calling UI can display before showing the Capture
    button. Never raises.

    Returns (available, human_readable_status)."""
    mode = current_mode()
    if mode == "real":
        ok, msg = _real_sdk_available()
        return ok, msg
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


# ── Real SDK implementation (skeleton) ────────────────────────────────

def _real_sdk_available() -> tuple[bool, str]:
    """Check whether the Mantra SDK is present and the device is reachable.

    This is a light probe — it must not raise, and must not hang if the
    device is unplugged. Currently returns False because the SDK has not
    yet been downloaded / integrated. Update this function once the SDK
    is installed.
    """
    # TODO — once the physical sensor and SDK arrive:
    #
    # Approach A (recommended — subprocess):
    #   Compile a small C# capture helper that Mantra ships in
    #   SDK/Samples/CSharp/. Modify it to write the captured image to a
    #   given path and print quality/serial as stdout JSON. From Python,
    #   subprocess.run(["MantraCapture.exe", "--out", "capture.png"]).
    #   Check for the helper's presence here.
    #
    # Approach B (ctypes):
    #   Load MFS100.dll directly and bind CaptureFinger, StreamStart,
    #   etc. via ctypes. More brittle, more control.
    #
    # Approach C (pythonnet):
    #   Load the C# wrapper DLL through pythonnet.
    #
    return False, ("Real-mode SDK not yet wired. Install the Mantra "
                   "MFS100 SDK, then update _real_sdk_available() and "
                   "_real_capture() in mantra_sensor.py.")


def _real_capture(*, timeout_seconds: float) -> MantraCaptureResult:
    """Placeholder — raises until the SDK is wired.

    When implementing:
      1. Trigger the sensor stream / auto-capture with the SDK.
      2. Wait for a finger to be placed (up to timeout_seconds).
      3. Retrieve the raw image bytes (typically BMP or raw grey).
      4. Wrap into a PNG buffer for uniform downstream handling.
      5. Read quality score if the SDK exposes it (MFS100 usually
         returns an NFIQ-like score in the range 0-100).
      6. Read the device serial once via the SDK's info call.
      7. Return a MantraCaptureResult.
    """
    raise MantraSensorError(
        "Real capture is not yet implemented. Install the Mantra MFS100 "
        "SDK, then wire _real_capture() in app/services/mantra_sensor.py."
    )
