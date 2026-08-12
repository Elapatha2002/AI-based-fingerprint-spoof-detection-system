"""
Smoke test for the three fixes just applied.

  Fix 1: heatmaps (raw PNG bytes) upload correctly
  Fix 2: fetch image bytes back from S3 by case_id
  Fix 3: PDF generator handles em dash + None values without crashing

Cleans up all test data at the end.
"""
from __future__ import annotations

import sys
from pathlib import Path
from io import BytesIO
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services import database, storage, persistence


def line(char: str = "─", n: int = 60) -> None:
    print(char * n)


def check(condition: bool, message: str) -> None:
    status = "[OK]" if condition else "[FAIL]"
    print(f"  {status} {message}")
    if not condition:
        sys.exit(1)


def test_fix_1_heatmap_bytes():
    print("\n[Fix 1] Heatmap upload accepts raw PNG bytes")

    # Fake image + fake XAI panels in the mock_model format (bytes)
    img = Image.new("RGB", (100, 100), color="white")
    img_bytes = BytesIO()
    img.save(img_bytes, format="PNG")
    img_bytes = img_bytes.getvalue()

    # Build a heatmap "image" — bytes, matching mock_model._heatmap_image output
    heatmap = Image.new("RGB", (50, 50), color="red")
    hb = BytesIO()
    heatmap.save(hb, format="PNG")
    heatmap_bytes = hb.getvalue()

    xai_panels = {
        "gradcam": {"image": heatmap_bytes, "faithfulness": 0.82},
        "shap": {"image": heatmap_bytes, "faithfulness": 0.78},
        "lime": {"image": heatmap_bytes, "faithfulness": 0.65},
    }

    result = {
        "label": "spoof",
        "confidence": 0.87,
        "raw_score": 0.87,
        "model": {"name": "test_model", "commit": "abc123"},
        "timing_ms": {"total": 100},
    }

    meta = {"case_id": "CASE-FIXTEST-001", "examiner": "test_user"}

    analysis_id = persistence.save_single_analysis(
        filename="test.png",
        image_bytes=img_bytes,
        meta=meta,
        result=result,
        xai_panels=xai_panels,
    )
    check(analysis_id is not None,
          f"save_single_analysis returned analysis_id={analysis_id}")

    xai_rows = database.list_xai_for_analysis(analysis_id)
    check(len(xai_rows) == 3,
          f"expected 3 XAI rows in DB, got {len(xai_rows)}")

    for row in xai_rows:
        exists = storage.get_storage().object_exists(row["heatmap_s3_key"])
        check(exists,
              f"heatmap in S3: {row['method']} → {row['heatmap_s3_key']}")

    return analysis_id, "CASE-FIXTEST-001"


def test_fix_2_image_download(case_id: str):
    print("\n[Fix 2] Image fetch by case_id downloads from S3")

    analyses = database.list_analyses(case_id=case_id, limit=1)
    check(len(analyses) == 1, "one analysis found for the case")

    image_key = analyses[0]["image_s3_key"]
    downloaded = storage.get_storage().download_bytes(image_key)
    check(len(downloaded) > 0, f"downloaded {len(downloaded)} bytes from S3")

    pil = Image.open(BytesIO(downloaded))
    check(pil.size == (100, 100),
          f"round-tripped image preserves dimensions: {pil.size}")


def test_fix_3_pdf_unicode():
    print("\n[Fix 3] PDF generator handles em dash + None values")

    from app.utils.report_generator import build_report

    case_meta = {
        "case_id": "CASE — with em dash",
        "examiner": "Someone with 'curly quotes' and “double curly” — plus…",
        "sensor": None,
        "notes": "",
        "timestamp": "2026-08-12T14:00:00",
    }

    result = {
        "label": "spoof",
        "confidence": 0.87,
        "material": None,
        "nfiq2": 78,
        "anomaly_score": 0.12,
        "known_pattern": True,
    }

    pdf_bytes = build_report(case_meta, result, image_bytes=None, xai_panels=None)
    check(pdf_bytes.startswith(b"%PDF"),
          f"PDF generated: {len(pdf_bytes)} bytes, starts with %PDF header")


def cleanup(case_id: str):
    print(f"\n[Cleanup] Removing test data for {case_id} ...")
    try:
        analyses = database.list_analyses(case_id=case_id, limit=500)
        svc = storage.get_storage()
        for a in analyses:
            try:
                svc.delete(a["image_s3_key"])
            except Exception:
                pass
            for xai in database.list_xai_for_analysis(a["analysis_id"]):
                try:
                    svc.delete(xai["heatmap_s3_key"])
                except Exception:
                    pass

        with database.connect() as conn:
            conn.execute("DELETE FROM xai_outputs WHERE analysis_id IN "
                         "(SELECT analysis_id FROM analyses WHERE case_id = ?)",
                         (case_id,))
            conn.execute("DELETE FROM analyses WHERE case_id = ?", (case_id,))
            conn.execute("DELETE FROM cases WHERE case_id = ?", (case_id,))
            conn.execute("DELETE FROM audit_log WHERE case_id = ?", (case_id,))
        print("  cleaned")
    except Exception as e:
        print(f"  cleanup warning: {e}")


def main():
    print()
    line("#")
    print("# FIXES SMOKE TEST — Issues 1, 2, 3")
    line("#")

    analysis_id, case_id = test_fix_1_heatmap_bytes()
    try:
        test_fix_2_image_download(case_id)
        test_fix_3_pdf_unicode()
    finally:
        cleanup(case_id)

    line("=")
    print("ALL THREE FIXES VERIFIED")
    line("=")


if __name__ == "__main__":
    main()
