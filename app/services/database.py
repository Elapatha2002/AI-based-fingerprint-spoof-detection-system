"""
SQLite or private Supabase/PostgreSQL persistence for the FSD-XAI app.

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
load_dotenv(PROJECT_ROOT / ".env.supabase")
load_dotenv(PROJECT_ROOT / ".env")

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()


def using_postgres() -> bool:
    if DATABASE_URL and not DATABASE_URL.startswith(('postgresql://', 'postgres://')):
        raise ValueError('DATABASE_URL must be a PostgreSQL connection URL.')
    return bool(DATABASE_URL)

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
    "user"       TEXT,
    action       TEXT NOT NULL,             -- created | analysed | viewed | exported | deleted
    details      TEXT,
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    user_id        TEXT PRIMARY KEY,
    username       TEXT UNIQUE NOT NULL,
    password_hash  TEXT NOT NULL,             -- format: <salt_hex>:<hash_hex>
    role           TEXT NOT NULL,             -- super_admin | examiner
    full_name      TEXT NOT NULL,
    email          TEXT,
    active         INTEGER NOT NULL DEFAULT 1,
    created_at     TEXT NOT NULL,
    last_login     TEXT,
    session_version INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_analyses_case ON analyses(case_id);
CREATE INDEX IF NOT EXISTS idx_xai_analysis ON xai_outputs(analysis_id);
CREATE INDEX IF NOT EXISTS idx_audit_case ON audit_log(case_id);
CREATE INDEX IF NOT EXISTS idx_audit_analysis ON audit_log(analysis_id);
CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_log(created_at);
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _uid() -> str:
    return uuid.uuid4().hex[:16]


@contextmanager
def connect():
    """Select the configured backend. Never fall back after a cloud failure."""
    if using_postgres():
        from app.services.postgres_backend import connect as pg_connect
        with pg_connect(DATABASE_URL) as conn:
            yield conn
        return
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
    """Initialise local SQLite, or verify the explicitly provisioned PG schema."""
    if using_postgres():
        with connect() as conn:
            conn.execute('SELECT session_version FROM users LIMIT 0')
        return
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with connect() as conn:
        conn.executescript(SCHEMA)
        columns = {r['name'] for r in conn.execute('PRAGMA table_info(users)')}
        if 'session_version' not in columns:
            conn.execute('ALTER TABLE users ADD COLUMN session_version INTEGER NOT NULL DEFAULT 0')


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
                    image_hash: str = "", examiner: str = "") -> str:
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
             action="analysed", user=(examiner or "").strip() or "Unattributed",
             details=f"{model_name} → {verdict} ({confidence:.2%})")
    return analysis_id


def get_analysis(analysis_id: str) -> Optional[dict]:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM analyses WHERE analysis_id = ?", (analysis_id,)
        ).fetchone()
        return dict(row) if row else None


def list_analyses(case_id: Optional[str] = None,
                  limit: Optional[int] = 200) -> list[dict]:
    q = "SELECT * FROM analyses"
    params: tuple = ()
    if case_id:
        q += " WHERE case_id = ?"
        params = (case_id,)
    # A stable tie-breaker is necessary for legacy second-resolution timestamps.
    q += " ORDER BY created_at DESC, analysis_id DESC"
    if limit is not None:
        q += " LIMIT ?"
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
        'INSERT INTO audit_log (event_id, case_id, analysis_id, "user", '
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


# ── Users ─────────────────────────────────────────────────────────────

def create_user(username: str, password_hash: str, role: str,
                full_name: str, email: str = "") -> str:
    """Insert a user row. Caller supplies the pre-hashed password."""
    if role not in ("super_admin", "examiner"):
        raise ValueError(f"Invalid role: {role}")
    user_id = f"USR-{_uid()}"
    with connect() as conn:
        conn.execute(
            "INSERT INTO users (user_id, username, password_hash, role, "
            "full_name, email, active, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, 1, ?)",
            (user_id, username, password_hash, role, full_name, email, _now()),
        )
    return user_id


def get_user_by_username(username: str) -> Optional[dict]:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
        return dict(row) if row else None


def get_user(user_id: str) -> Optional[dict]:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()
        return dict(row) if row else None


def list_users(include_inactive: bool = True) -> list[dict]:
    q = "SELECT * FROM users"
    if not include_inactive:
        q += " WHERE active = 1"
    q += " ORDER BY role DESC, username ASC"
    with connect() as conn:
        return [dict(r) for r in conn.execute(q).fetchall()]


def user_count() -> int:
    with connect() as conn:
        return conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]


def update_user(user_id: str, *, full_name: Optional[str] = None,
                email: Optional[str] = None, role: Optional[str] = None,
                active: Optional[int] = None,
                password_hash: Optional[str] = None) -> None:
    updates = dict(full_name=full_name, email=email, role=role, active=active,
                   password_hash=password_hash)
    with connect() as conn:
        _lock_users(conn)
        _update_account(conn, user_id, updates)


def _lock_users(conn):
    # Serialize role/status changes, including concurrent last-admin removal.
    conn.execute('LOCK TABLE users IN SHARE ROW EXCLUSIVE MODE' if using_postgres()
                 else 'BEGIN IMMEDIATE')


def _protect_last_admin(conn, user_id, *, removing=False, role=None, active=None):
    target = conn.execute('SELECT * FROM users WHERE user_id = ?', (user_id,)).fetchone()
    if not target:
        raise ValueError('Account no longer exists.')
    loses_access = removing or role == 'examiner' or active == 0
    if target['role'] == 'super_admin' and target['active'] and loses_access:
        count = conn.execute("SELECT COUNT(*) AS n FROM users WHERE role = 'super_admin' AND active = 1").fetchone()['n']
        if count <= 1:
            raise ValueError('Cannot remove, disable or demote the last active super admin.')
    return target


def _update_account(conn, user_id, updates):
    allowed = {'full_name', 'email', 'role', 'active', 'password_hash'}
    if set(updates) - allowed:
        raise ValueError('Unsupported account field.')
    if updates.get('role') is not None and updates['role'] not in ('examiner', 'super_admin'):
        raise ValueError('Invalid account role.')
    if updates.get('active') is not None and updates['active'] not in (0, 1):
        raise ValueError('Invalid account status.')
    if updates.get('full_name') is not None and not updates['full_name'].strip():
        raise ValueError('Full name is required.')
    _protect_last_admin(conn, user_id, role=updates.get('role'), active=updates.get('active'))
    fields, params = [], []
    for name, value in updates.items():
        if value is not None:
            fields.append(f"{name} = ?")
            params.append(value)
    if not fields:
        return
    if any(updates.get(k) is not None for k in ('role', 'active', 'password_hash')):
        fields.append('session_version = session_version + 1')
    params.append(user_id)
    conn.execute(f"UPDATE users SET {', '.join(fields)} WHERE user_id = ?", params)


def touch_last_login(user_id: str) -> None:
    with connect() as conn:
        conn.execute("UPDATE users SET last_login = ? WHERE user_id = ?",
                      (_now(), user_id))


def delete_user(user_id: str) -> None:
    """Trusted maintenance primitive; UI must use auth.delete_account instead."""
    with connect() as conn:
        _lock_users(conn)
        _protect_last_admin(conn, user_id, removing=True)
        conn.execute("DELETE FROM users WHERE user_id = ?", (user_id,))


def bootstrap_admin(username, password_hash, full_name):
    """One-time provisioning only; cannot overwrite any existing account."""
    with connect() as conn:
        _lock_users(conn)
        if conn.execute('SELECT COUNT(*) AS n FROM users').fetchone()['n']:
            return None
        user_id = f'USR-{_uid()}'
        conn.execute("INSERT INTO users (user_id, username, password_hash, role, full_name, active, created_at) VALUES (?, ?, ?, 'super_admin', ?, 1, ?)",
                     (user_id, username, password_hash, full_name, _now()))
        _log(conn, action='admin_bootstrapped', user=user_id,
             details=f'Initial super admin: {username}')
        return user_id


def manage_account(actor_id, session_version, operation, *, target_id=None, values=None):
    """Authorised user mutation plus audit, in one serialized transaction.

    actor_id/version come from the authenticated server session, never a form.
    Low-level create_user/update_user are reserved for trusted local maintenance.
    """
    values = dict(values or {})
    with connect() as conn:
        _lock_users(conn)
        actor = conn.execute('SELECT * FROM users WHERE user_id = ?', (actor_id,)).fetchone()
        if not actor or not actor['active'] or actor['session_version'] != session_version:
            raise PermissionError('Your session expired. Sign in again.')
        if operation != 'own_password' and actor['role'] != 'super_admin':
            raise PermissionError('Only a super admin can manage accounts.')
        if operation == 'create':
            if set(values) != {'username', 'password_hash', 'full_name', 'email', 'role'}:
                raise ValueError('Invalid account fields.')
            if not values['username'].strip() or not values['full_name'].strip():
                raise ValueError('Username and full name are required.')
            if values['role'] not in ('examiner', 'super_admin'):
                raise ValueError('Invalid account role.')
            if conn.execute('SELECT user_id FROM users WHERE username = ?', (values['username'],)).fetchone():
                raise ValueError('Username is already taken.')
            target_id = f'USR-{_uid()}'
            conn.execute('INSERT INTO users (user_id, username, password_hash, role, full_name, email, active, created_at) VALUES (?, ?, ?, ?, ?, ?, 1, ?)',
                         (target_id, values['username'], values['password_hash'], values['role'], values['full_name'], values['email'], _now()))
        elif operation == 'update':
            if target_id == actor_id and values.get('active') == 0:
                raise ValueError('You cannot disable your own account.')
            _update_account(conn, target_id, values)
        elif operation == 'delete':
            if target_id == actor_id:
                raise ValueError('You cannot delete your own account.')
            target = _protect_last_admin(conn, target_id, removing=True)
            if values.get('confirmation') != target['username']:
                raise ValueError('Type the exact username to confirm deletion.')
            # No case/analysis/audit rows are deleted. Their recorded attribution stays.
            conn.execute('DELETE FROM users WHERE user_id = ?', (target_id,))
        elif operation == 'own_password':
            from app.services.auth import verify_password
            if not verify_password(values.get('current_password', ''), actor['password_hash']):
                raise ValueError('Current password is incorrect.')
            target_id = actor_id
            _update_account(conn, actor_id, {'password_hash': values['password_hash']})
        else:
            raise ValueError('Unknown account operation.')
        _log(conn, action=f'user_{operation}', user=actor_id,
             details=f'actor={actor["username"]}; target={target_id}')
        return target_id


# Schema setup is explicit; importing this module never changes a database.
