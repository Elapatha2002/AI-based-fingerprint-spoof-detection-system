"""Unified image loader for PNG / JPG / BMP / TIFF."""
from io import BytesIO
from PIL import Image
import numpy as np

SUPPORTED_EXT = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}
MAX_SINGLE_BYTES = 10 * 1024 * 1024  # 10 MB
MAX_DIM = 4096
MIN_DIM = 50


def is_supported(filename: str) -> bool:
    name = filename.lower()
    return any(name.endswith(ext) for ext in SUPPORTED_EXT)


def load_image(source) -> tuple[Image.Image | None, str | None]:
    """
    Load any supported image format and return a normalized RGB PIL.Image.
    Returns (image, error_message). Either image is None or error is None.
    """
    try:
        if hasattr(source, "read"):
            data = source.read()
        elif isinstance(source, (bytes, bytearray)):
            data = bytes(source)
        else:
            with open(source, "rb") as f:
                data = f.read()

        if len(data) > MAX_SINGLE_BYTES:
            return None, f"File too large ({len(data)/1024/1024:.1f} MB > 10 MB limit)"

        img = Image.open(BytesIO(data))
        # Multi-page TIFF: take first frame
        try:
            img.seek(0)
        except Exception:
            pass

        if img.mode != "RGB":
            img = img.convert("RGB")

        w, h = img.size
        if w < MIN_DIM or h < MIN_DIM:
            return None, f"Image too small ({w}x{h}, min {MIN_DIM}px)"
        if w > MAX_DIM or h > MAX_DIM:
            return None, f"Image too large ({w}x{h}, max {MAX_DIM}px)"

        return img, None
    except Exception as e:
        return None, f"Could not decode image: {e}"


def to_numpy(img: Image.Image) -> np.ndarray:
    """Convert PIL image to (H, W, 3) uint8 numpy array."""
    return np.array(img)
