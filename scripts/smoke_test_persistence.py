"""
End-to-end smoke test for the persistence layer.

Exercises both services in isolation from the Streamlit app:

  1. S3
     - upload a small text file
     - download it back
     - verify bytes match
     - generate a presigned URL
     - delete the object

  2. SQLite
     - create a test case
     - record a test analysis
     - record a test XAI output
     - list cases / analyses / audit log
     - clean up the test records

Run:
    .venv\\Scripts\\python.exe scripts\\smoke_test_persistence.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services import storage, database


def line(char: str = "─", n: int = 60) -> None:
    print(char * n)


def check(condition: bool, message: str) -> None:
    if condition:
        print(f"  [OK] {message}")
    else:
        print(f"  [FAIL] {message}")
        sys.exit(1)


def test_s3():
    line("=")
    print("S3 SMOKE TEST")
    line("=")

    svc = storage.get_storage()

    print("\n[1] Health check ...")
    ok, msg = svc.health_check()
    check(ok, msg)

    test_key = "smoke_test/hello.txt"
    test_bytes = b"Hello from FSD-XAI persistence smoke test!"

    print(f"\n[2] Upload {len(test_bytes)} bytes to s3://{svc.config.bucket}/{test_key} ...")
    returned_key = svc.upload_bytes(test_key, test_bytes, content_type="text/plain")
    check(returned_key == test_key, f"upload returned expected key: {returned_key}")

    print("\n[3] Confirm object exists ...")
    check(svc.object_exists(test_key), "head_object succeeds")

    print("\n[4] Download and verify byte-exact match ...")
    downloaded = svc.download_bytes(test_key)
    check(downloaded == test_bytes,
          f"round-trip preserved bytes ({len(downloaded)} bytes)")

    print("\n[5] Generate presigned URL (5 min expiry) ...")
    url = svc.presigned_url(test_key, expires_seconds=300)
    check(url.startswith("https://") and svc.config.bucket in url,
          f"URL looks valid: {url[:80]}...")

    print("\n[6] Delete test object ...")
    svc.delete(test_key)
    check(not svc.object_exists(test_key), "object gone after delete")

    print("\nS3 smoke test PASSED\n")


def test_database():
    line("=")
    print("SQLITE SMOKE TEST")
    line("=")

    print(f"\n[1] Database path: {database.DB_PATH}")
    check(database.DB_PATH.exists(), "database file exists")

    print("\n[2] Create a test case ...")
    case_id = database.create_case(
        case_name="SMOKE TEST — DELETE ME",
        examiner="smoke_tester",
        description="Automated smoke test record",
    )
    check(case_id.startswith("CASE-"), f"case_id issued: {case_id}")

    print("\n[3] Retrieve the case ...")
    case = database.get_case(case_id)
    check(case is not None and case["case_name"] == "SMOKE TEST — DELETE ME",
          f"round-trip: examiner='{case['examiner']}' status='{case['status']}'")

    print("\n[4] Record a test analysis ...")
    analysis_id = database.record_analysis(
        case_id=case_id,
        image_filename="test_fingerprint.png",
        image_s3_key="uploads/CASE-test/test.png",
        model_name="fsd_cbam_v2",
        verdict="live",
        confidence=0.9847,
        threshold_used=0.5,
        inference_ms=125.3,
        image_hash="sha256_dummy_hash_for_test",
    )
    check(analysis_id.startswith("AN-"), f"analysis_id issued: {analysis_id}")

    print("\n[5] Record a test XAI output ...")
    xai_id = database.record_xai(
        analysis_id=analysis_id,
        method="gradcam",
        heatmap_s3_key=f"heatmaps/{analysis_id}/gradcam.png",
        faithfulness=0.734,
    )
    check(xai_id.startswith("XAI-"), f"xai_id issued: {xai_id}")

    print("\n[6] List analyses for this case ...")
    analyses = database.list_analyses(case_id=case_id)
    check(len(analyses) == 1 and analyses[0]["analysis_id"] == analysis_id,
          f"found {len(analyses)} analysis with verdict='{analyses[0]['verdict']}' "
          f"conf={analyses[0]['confidence']:.4f}")

    print("\n[7] List XAI outputs for this analysis ...")
    xai_rows = database.list_xai_for_analysis(analysis_id)
    check(len(xai_rows) == 1 and xai_rows[0]["method"] == "gradcam",
          f"found {len(xai_rows)} XAI output")

    print("\n[8] Check audit trail was written ...")
    audit = database.get_audit_trail(case_id=case_id)
    actions = [row["action"] for row in audit]
    check("created" in actions and "analysed" in actions,
          f"audit trail actions: {actions}")

    print("\n[9] Cleanup — delete test case (cascades to analysis + xai + audit) ...")
    with database.connect() as conn:
        conn.execute("DELETE FROM cases WHERE case_id = ?", (case_id,))
        conn.execute("DELETE FROM audit_log WHERE case_id = ?", (case_id,))
    check(database.get_case(case_id) is None, "test case deleted")

    print("\nSQLite smoke test PASSED\n")


def main():
    print()
    line("#")
    print("# FSD-XAI PERSISTENCE SMOKE TEST")
    line("#")
    print()

    try:
        test_s3()
        test_database()
    except Exception as e:
        line("!")
        print(f"SMOKE TEST FAILED with exception:\n  {type(e).__name__}: {e}")
        line("!")
        raise

    line("=")
    print("ALL TESTS PASSED — persistence layer is ready.")
    line("=")


if __name__ == "__main__":
    main()
