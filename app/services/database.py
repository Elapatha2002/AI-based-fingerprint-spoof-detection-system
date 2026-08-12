"""
SQLite persistence for the FSD-XAI forensic app.

Stores case metadata, analysis records, XAI output pointers, and audit
events. Files themselves live in S3 (see storage.py); this module only
holds structured metadata and pointers (S3 keys).

Schema:
    cases         — one row per forensic case
    analyses      — one row per fingerprint image analysed
    xai_outputs   — one row per XAI method run against an analysis
    audit_log     — append-only event log (creation, view, export, delete)

Design decisions:
  • sqlite3.Row row_factory so callers get dict-like access
  • WAL journal mode for better concurrent-read behaviour
  • FOREIGN KEY constraints enforced (they are OFF by default in SQLite)
  • All timestamps stored as ISO-8601 strings in UTC
"""
from __future__ import annotations

import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")


DB_PATH = Path(os.environ.get("DATABASE_PATH", "./fsd_xai.db"))
if not DB_PATH.is_absolute():
    DB_PATH = PROJECT_ROOT / DB_PATH


SCHEMA = """
CREATE TABLE IF NOT EXISTS cases (
    case_id       TEXT PRIMARY KEY,
    case_name     TEXT NOT NULL,
    examiner      TEXT,
    description   TEXT,
    status        TEXT DEFAULT 'open',      -- open | closed | archived
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS analyses (
    analysis_id     TEXT PRIMARY KEY,
    case_id         TEXT NOT NULL,
    image_filename  TEXT NOT NULL,
    image_s3_key    TEXT NOT NULL,
    image_hash      TEXT,
    model_name      TEXT NOT NULL,
    verdict         TEXT NOT NULL,          -- live | spoof
    confidence      REAL NOT NULL,
    threshold_used  REAL,
    inference_ms    REAL,
    created_at      TEXT NOT NULL,
    FOREIGN KEY (case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS xai_outputs (
    xai_id         TEXT PRIMARY KEY,
    analysis_id    TEXT NOT NULL,
    method         TEXT NOT NULL,           -- gradcam | shap | lime
    heatmap_s3_key TEXT NOT NULL,
    faithfulness   REAL,
    created_at     TEXT NOT NULL,
    FOREIGN KEY (analysis_id) REFERENCES analyses(analysis_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS reports (
    report_id      TEXT PRIMARY KEY,
    case_id        TEXT NOT NULL,
    report_s3_key  TEXT NOT NULL,
    examiner       TEXT,
    created_at     TEXT NOT NULL,
    FOREIGN KEY (case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS audit_log (
    event_id     TEXT PRIMARY KEY,
    case_id      TEXT,
    analysis_id  TEXT,
    user         TEXT,
    action       TEXT NOT NULL,             -- created | analysed | viewed | exported | deleted
    details      TEXT,
    created_at   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_analyses_case ON analyses(case_id);
CREATE INDEX IF NOT EXISTS idx_xai_analysis ON xai_outputs(analysis_id);
CREATE INDEX IF NOT EXISTS idx_audit_case ON audit_log(case_id);
CREATE INDEX IF NOT EXISTS idx_audit_analysis ON audit_log(analysis_id);
CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_log(created_at);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _uid() -> str:
    return uuid.uuid4().hex[:16]


@contextmanager
def connect():
    """Context-managed SQLite connection with sane defaults."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """Create tables if they don't yet exist. Idempotent."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with connect() as conn:
        conn.executescript(SCHEMA)


# ── Cases ─────────────────────────────────────────────────────────────

def create_case(case_name: str, examiner: str = "",
                description: str = "") -> str:
    case_id = f"CASE-{_uid()}"
    now = _now()
    with connect() as conn:
        conn.execute(
            "INSERT INTO cases (case_id, case_name, examiner, description, "
            "status, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, 'open', ?, ?)",
            (case_id, case_name, examiner, description, now, now),
        )
        _log(conn, case_id=case_id, action="created",
             user=examiner, details=f"Case '{case_name}' created")
    return case_id


def get_case(case_id: str) -> Optional[dict]:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM cases WHERE case_id = ?", (case_id,)
        ).fetchone()
        return dict(row) if row else None


def list_cases(status: Optional[str] = None) -> list[dict]:
    q = "SELECT * FROM cases"
    params: tuple = ()
    if status:
        q += " WHERE status = ?"
        params = (status,)
    q += " ORDER BY created_at DESC"
    with connect() as conn:
        return [dict(r) for r in conn.execute(q, params).fetchall()]


def update_case_status(case_id: str, status: str) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE cases SET status = ?, updated_at = ? WHERE case_id = ?",
            (status, _now(), case_id),
        )


# ── Analyses ──────────────────────────────────────────────────────────

def record_analysis(case_id: str, image_filename: str, image_s3_key: str,
                    model_name: str, verdict: str, confidence: float,
                    threshold_used: float = 0.5, inference_ms: float = 0.0,
                    image_hash: str = "") -> str:
    analysis_id = f"AN-{_uid()}"
    now = _now()
    with connect() as conn:
        conn.execute(
            "INSERT INTO analyses (analysis_id, case_id, image_filename, "
            "image_s3_key, image_hash, model_name, verdict, confidence, "
            "threshold_used, inference_ms, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (analysis_id, case_id, image_filename, image_s3_key, image_hash,
             model_name, verdict, confidence, threshold_used, inference_ms, now),
        )
        _log(conn, case_id=case_id, analysis_id=analysis_id,
             action="analysed",
             details=f"{model_name} → {verdict} ({confidence:.2%})")
    return analysis_id


def get_analysis(analysis_id: str) -> Optional[dict]:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM analyses WHERE analysis_id = ?", (analysis_id,)
        ).fetchone()
        return dict(row) if row else None


def list_analyses(case_id: Optional[str] = None,
                  limit: int = 200) -> list[dict]:
    q = "SELECT * FROM analyses"
    params: tuple = ()
    if case_id:
        q += " WHERE case_id = ?"
        params = (case_id,)
    q += " ORDER BY created_at DESC LIMIT ?"
    params = params + (limit,)
    with connect() as conn:
        return [dict(r) for r in conn.execute(q, params).fetchall()]


# ── XAI outputs ───────────────────────────────────────────────────────

def record_xai(analysis_id: str, method: str, heatmap_s3_key: str,
               faithfulness: Optional[float] = None) -> str:
    xai_id = f"XAI-{_uid()}"
    with connect() as conn:
        conn.execute(
            "INSERT INTO xai_outputs (xai_id, analysis_id, method, "
            "heatmap_s3_key, faithfulness, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (xai_id, analysis_id, method, heatmap_s3_key, faithfulness, _now()),
        )
    return xai_id


def list_xai_for_analysis(analysis_id: str) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM xai_outputs WHERE analysis_id = ? "
            "ORDER BY created_at",
            (analysis_id,),
        ).fetchall()
        return [dict(r) for r in rows]


# ── Reports ───────────────────────────────────────────────────────────

def record_report(case_id: str, report_s3_key: str,
                  examiner: str = "") -> str:
    report_id = f"RPT-{_uid()}"
    with connect() as conn:
        conn.execute(
            "INSERT INTO reports (report_id, case_id, report_s3_key, "
            "examiner, created_at) VALUES (?, ?, ?, ?, ?)",
            (report_id, case_id, report_s3_key, examiner, _now()),
        )
        _log(conn, case_id=case_id, action="exported",
             user=examiner, details=f"Report {report_id} generated")
    return report_id


def list_reports(case_id: str) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM reports WHERE case_id = ? "
            "ORDER BY created_at DESC",
            (case_id,),
        ).fetchall()
        return [dict(r) for r in rows]


# ── Audit log ─────────────────────────────────────────────────────────

def _log(conn: sqlite3.Connection, action: str,
         case_id: str = "", analysis_id: str = "",
         user: str = "", details: str = "") -> None:
    conn.execute(
        "INSERT INTO audit_log (event_id, case_id, analysis_id, user, "
        "action, details, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (f"EV-{_uid()}", case_id, analysis_id, user, action, details, _now()),
    )


def log_event(action: str, case_id: str = "", analysis_id: str = "",
              user: str = "", details: str = "") -> None:
    """Public helper — logs an audit event in its own transaction."""
    with connect() as conn:
        _log(conn, action=action, case_id=case_id,
             analysis_id=analysis_id, user=user, details=details)


def get_audit_trail(case_id: Optional[str] = None,
                    analysis_id: Optional[str] = None,
                    limit: int = 500) -> list[dict]:
    q = "SELECT * FROM audit_log WHERE 1=1"
    params: list[Any] = []
    if case_id:
        q += " AND case_id = ?"
        params.append(case_id)
    if analysis_id:
        q += " AND analysis_id = ?"
        params.append(analysis_id)
    q += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    with connect() as conn:
        return [dict(r) for r in conn.execute(q, params).fetchall()]


# ── One-liner init when imported ──────────────────────────────────────

init_db()
