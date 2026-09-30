"""
Persistence bridge — the single API views use to save/list analyses.

Views never touch the storage backend or SQLite directly. They call one of these functions:

  save_single_analysis(...)   — one image + result + XAI  → storage + DB
  save_batch_analyses(...)    — many images + results     → storage + DB (loop)
  save_report_to_cloud(...)   — PDF bytes                 → storage + DB
  list_history_from_db(...)   — rolled-up cases           → history_table format

Design notes:
  • A "case" is created lazily the first time an analysis with a new
    case_id is saved. The examiner value from the analysis form becomes
    the case examiner.
  • Failures are logged and swallowed — persistence is best-effort so
    the user's demo does not break if S3 has a hiccup. The in-session
    history remains authoritative for the current session.
  • Image bytes are only uploaded to S3 on explicit save (single result)
    or on batch completion. Not on every quick classification.
"""
from __future__ import annotations

import hashlib
import logging
from io import BytesIO
from typing import Optional

from PIL import Image

from app.services import database, storage

logger = logging.getLogger(__name__)


# ── Case bootstrap ────────────────────────────────────────────────────

def _ensure_case(case_id: str, examiner: str, description: str = "") -> str:
    """Return case_id if it exists in DB. Otherwise create it and return.

    The Streamlit UI issues human-friendly case IDs like CASE-2026-0007.
    The database's own auto-issued IDs look like CASE-<hex16>. We honour
    whichever ID the UI already assigned so filenames and audit lines
    stay consistent.
    """
    existing = database.get_case(case_id)
    if existing:
        return case_id

    # Create with a directly-supplied case_id (bypass the auto id).
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        with database.connect() as conn:
            conn.execute(
                "INSERT INTO cases (case_id, case_name, examiner, "
                "description, status, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, 'open', ?, ?)",
                (case_id, case_id, examiner, description, now, now),
            )
    except Exception as e:
        logger.warning(f"Could not create case {case_id}: {e}")
    return case_id


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _guess_extension(filename: str) -> str:
    lower = filename.lower()
    for ext in ("png", "jpg", "jpeg", "bmp", "tif", "tiff"):
        if lower.endswith("." + ext):
            return ext
    return "png"


# ── Save operations ───────────────────────────────────────────────────

def save_single_analysis(*, filename: str, image_bytes: bytes,
                         meta: dict, result: dict,
                         xai_panels: Optional[dict] = None) -> Optional[str]:
    """Persist one image + one classification result + its XAI heatmaps.

    Returns the analysis_id on success, None on any failure.
    Persistence is best-effort — if storage or the DB is down, the caller's
    session-state save still succeeds and the user sees no error.
    """
    case_id = meta.get("case_id") or "CASE-UNKNOWN"
    examiner = (meta.get("examiner") or "").strip()

    try:
        _ensure_case(case_id, examiner)

        # 1. Upload the fingerprint image to the selected storage backend.
        ext = _guess_extension(filename)
        analysis_id_seed = f"AN-{_sha256(image_bytes)[:16]}"
        image_key = storage.upload_key(case_id, analysis_id_seed, ext)
        storage.get_storage().upload_bytes(image_key, image_bytes)

        # 2. Record analysis in SQLite
        analysis_id = database.record_analysis(
            case_id=case_id,
            image_filename=filename,
            image_s3_key=image_key,
            model_name=result.get("model", {}).get("name", "unknown"),
            verdict=result.get("label", "unknown"),
            confidence=float(result.get("confidence", 0.0)),
            threshold_used=float(result.get("threshold_used", 0.5)),
            inference_ms=float(result.get("timing_ms", {}).get("total", 0)),
            image_hash=_sha256(image_bytes),
            examiner=examiner,
        )

        # 3. Optionally save XAI heatmaps
        if xai_panels:
            for method_key in ("gradcam", "shap", "lime"):
                panel = xai_panels.get(method_key)
                if not panel or "image" not in panel:
                    continue
                try:
                    heatmap_bytes = _pil_to_png(panel["image"])
                    hkey = storage.heatmap_key(analysis_id, method_key)
                    storage.get_storage().upload_bytes(hkey, heatmap_bytes,
                                                       content_type="image/png")
                    database.record_xai(
                        analysis_id=analysis_id,
                        method=method_key,
                        heatmap_s3_key=hkey,
                        faithfulness=panel.get("faithfulness"),
                    )
                except Exception as xerr:
                    logger.warning(f"XAI upload failed for {method_key}: {xerr}")

        return analysis_id

    except Exception as e:
        logger.error(f"save_single_analysis failed for {filename}: {e}")
        return None


def save_batch_analyses(*, meta: dict, files: list, results: list) -> list[str]:
    """Persist a whole batch. Returns list of analysis_ids (None for failures)."""
    case_id = meta.get("case_id") or "CASE-UNKNOWN"
    examiner = meta.get("examiner", "")
    _ensure_case(case_id, examiner,
                 description=f"Batch of {len(files)} images")

    ids: list[str] = []
    for (fname, data), result in zip(files, results):
        aid = save_single_analysis(
            filename=fname,
            image_bytes=data or b"",
            meta=meta,
            result=result,
            xai_panels=None,   # batch skips XAI for speed
        )
        if aid:
            ids.append(aid)
    return ids


def save_report_to_cloud(*, case_id: str, pdf_bytes: bytes,
                          examiner: str = "") -> Optional[str]:
    """Upload a forensic PDF report to S3 and record it in DB."""
    try:
        _ensure_case(case_id, examiner)
        report_id_seed = f"RPT-{_sha256(pdf_bytes)[:16]}"
        rkey = storage.report_key(case_id, report_id_seed)
        storage.get_storage().upload_bytes(rkey, pdf_bytes,
                                            content_type="application/pdf")
        return database.record_report(case_id=case_id, report_s3_key=rkey,
                                       examiner=examiner)
    except Exception as e:
        logger.error(f"save_report_to_cloud failed for {case_id}: {e}")
        return None


# ── Query operations ──────────────────────────────────────────────────

def list_history_from_db() -> list[dict]:
    """Return history rows in the format history_table expects.

    Groups analyses by case_id. Each case becomes one history entry.
    Compatible with the existing tables.history_table renderer.
    """
    try:
        cases = database.list_cases()
    except Exception as e:
        logger.error(f"list_history_from_db failed: {e}")
        return []

    entries = []
    for case in cases:
        try:
            analyses = database.list_analyses(case_id=case["case_id"])
        except Exception:
            analyses = []
        if not analyses:
            continue

        live_count = sum(1 for a in analyses if a["verdict"] == "live")
        spoof_count = sum(1 for a in analyses if a["verdict"] == "spoof")
        entry_type = "single" if len(analyses) == 1 else "batch"
        latest = analyses[0]                              # DESC ordered

        entries.append({
            "type": entry_type,
            "case_id": case["case_id"],
            "count": len(analyses),
            "live_count": live_count,
            "spoof_count": spoof_count,
            "status": case.get("status", "open").title(),
            "created_at": latest["created_at"],
            "meta": {
                "case_id": case["case_id"],
                "examiner": case.get("examiner", ""),
                "sensor": "—",
            },
            "filename": latest["image_filename"],
            "analysis_id": latest["analysis_id"],
            "_source": "db",                              # marker for renderers
        })
    return entries


# ── Helpers ──────────────────────────────────────────────────────────

def _pil_to_png(img) -> bytes:
    """Convert PIL Image, numpy array, or already-PNG bytes to PNG bytes.

    mock_model.explain() returns raw PNG bytes from matplotlib.savefig;
    real_model.explain() may return either PIL Images or numpy arrays
    depending on the XAI method. All three formats are handled here.
    """
    if isinstance(img, (bytes, bytearray)):
        return bytes(img)
    if hasattr(img, "save"):
        buf = BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    try:
        import numpy as np
        if isinstance(img, np.ndarray):
            arr = img
            if arr.dtype != np.uint8:
                arr = (arr * 255).clip(0, 255).astype(np.uint8) if arr.max() <= 1.0 else arr.astype(np.uint8)
            pil = Image.fromarray(arr)
            buf = BytesIO()
            pil.save(buf, format="PNG")
            return buf.getvalue()
    except Exception:
        pass
    raise TypeError(f"Cannot convert {type(img)} to PNG bytes")
