# System fixes before pilot evaluation — 1 October 2026

## Closed defects

| Test / defect | Change | Verification |
| --- | --- | --- |
| TC-19 / DEF-19 | PDF metadata is taken from the supplied prediction, not a hard-coded ResNet50V2-CBAM/commit/training-corpus string. Real predictions now carry the checkpoint run and full SHA-256. Reports distinguish a model reference from a source-code commit, include the input hash and threshold, and explicitly mark missing provenance. | Original service test passes. Regression checks cover two different models, missing/legacy metadata, input hashes and the checkpoint-load → prediction → PDF path using a generated tiny test checkpoint. |
| TC-20 / DEF-20 | Removed the claim of completed expert-survey validation. The methodology page states that practitioner validation has not been established and does not claim legal admissibility. | Original service test and report-text regression pass; generated methodology page inspected visually. |
| TC-21 / DEF-21 | Persistence passes the analysis examiner into the database audit event in the same transaction as the analysis insert. UI audit actions resolve the current authenticated account rather than a stale form field. Missing actors are explicitly `Unattributed`, not silently blank or falsely attributed to `System`. | Original service test and single/batch/existing-case/current-account regressions pass. |

The report preview no longer substitutes the report-generation time for a missing analysis timestamp. These changes do not retroactively alter old PDF files or old audit records. A missing historical actor cannot safely be reconstructed by guessing.

## Execution evidence

Before the fixes, the isolated service harness reproduced exactly three failures: TC-19, TC-20 and TC-21 (26 pass, 3 fail, 6 not executed). After the fixes it reports **29 pass, 0 fail, 6 not executed**. The separate regression suite reports **12 tests passed**. These are different suites, not a claim of 41 unique end-to-end acceptance scenarios.

Records and a generated fixture PDF are saved separately under:

`Documents/Thsis final submission/verification/system_fixes_20261001/`

- `before/test_case_results.json`: reproduced failures before the changes.
- `after/test_case_results.json`: post-fix service checks.
- `after/report_fixture.pdf`: synthetic-input PDF used for verification.

Original thesis test records and thesis documents were preserved. The six unexecuted entries in the service harness include TC-33 and TC-35, whose separate GPU evaluation evidence already exists under `results/research_completion_20260930`; that experiment was not rerun here. Considering that earlier evidence alongside the new service checks gives 31 evidenced cases and four still unexecuted, with dates and methods kept distinct.

Reproduce the checks from the repository root:

```powershell
python -B -X utf8 -m unittest discover -s tests -v
python -B -X utf8 scripts/thesis_submission_tests.py --output-dir "Documents/Thsis final submission/verification/system_fixes_20261001/after"
```

The service harness now supports a separate output directory and exits nonzero if a case fails. Its injected storage-outage message is expected test output. Tests use temporary SQLite/local storage and generated input; they do not access an operational case database, cloud account or participant data. Existing fpdf deprecation warnings do not fail the checks.

## Before involving participants

Restart the Streamlit application so cached model services/predictions acquire the new provenance fields. Newly generated reports use the fixed code; previously downloaded PDFs remain unchanged.

This closes the three logged failures, not every possible pilot-readiness issue. A real browser workflow, keyboard/responsive checks and physical sensor testing remain unexecuted. Practitioner testing has not begun and no survey was distributed. The existing real-model service also still contains prototype quality/anomaly values and placeholder explanation-quality scores; these must not be presented to pilot participants as measured or validated results. Review/label or remove those separately before collecting trust ratings. Persisted-history reopening currently recomputes predictions instead of replaying the complete original result, so it should not be described as immutable historical reproduction.

No authentication bypass, cloud migration, retrospective alteration of audit history, or thesis regeneration was performed.
