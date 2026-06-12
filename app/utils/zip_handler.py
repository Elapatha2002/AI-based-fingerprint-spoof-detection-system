"""In-memory zip extraction for batch upload."""
import zipfile
from io import BytesIO
from .image_loader import is_supported

MAX_ZIP_BYTES = 50 * 1024 * 1024  # 50 MB
MAX_FILES = 5000


def inspect_zip(uploaded_file) -> dict:
    """
    Read a zip in-memory and return a summary without extracting.
    Returns: {valid: int, ignored: int, files: [(name, bytes)], errors: [str]}
    """
    summary = {"valid": 0, "ignored": 0, "files": [], "errors": []}

    raw = uploaded_file.read()
    uploaded_file.seek(0)

    if len(raw) > MAX_ZIP_BYTES:
        summary["errors"].append(f"Zip too large ({len(raw)/1024/1024:.1f} MB > 50 MB)")
        return summary

    try:
        zf = zipfile.ZipFile(BytesIO(raw))
    except zipfile.BadZipFile:
        summary["errors"].append("File is not a valid zip archive.")
        return summary

    names = zf.namelist()
    if len(names) > MAX_FILES:
        summary["errors"].append(f"Too many files in zip ({len(names)} > {MAX_FILES})")
        return summary

    seen_names = {}
    for n in names:
        if n.endswith("/"):
            continue
        base = n.split("/")[-1]
        if not is_supported(base):
            summary["ignored"] += 1
            continue
        # Dedup names
        if base in seen_names:
            seen_names[base] += 1
            stem, _, ext = base.rpartition(".")
            base = f"{stem}_{seen_names[base]}.{ext}"
        else:
            seen_names[base] = 0
        try:
            data = zf.read(n)
            summary["files"].append((base, data))
            summary["valid"] += 1
        except Exception as e:
            summary["errors"].append(f"Failed to read {n}: {e}")

    return summary
