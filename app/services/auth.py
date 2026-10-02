"""
Authentication service.

Password hashing uses stdlib PBKDF2-SHA256 with 200 000 iterations and a
16-byte random salt. Storage format: "<salt_hex>:<hash_hex>" (a single
opaque string, so schema stays simple).

The service exposes a Streamlit-aware session helper (current_user,
login, logout, require_role) plus a stdlib-only hashing pair
(hash_password, verify_password) that scripts can also use.

Bootstrap: seed_super_admin_if_needed() creates a super admin from
.env values when the users table is empty. Called from streamlit_app.py.
"""
from __future__ import annotations

import hashlib
import hmac
import base64
import binascii
import json
import logging
import os
import secrets
import time
from pathlib import Path
from typing import Optional
from contextlib import contextmanager
from contextvars import ContextVar
from urllib.parse import unquote, urlsplit

import streamlit as st
from dotenv import load_dotenv

from app.services import database

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")


PBKDF2_ITERATIONS = 200_000
PBKDF2_ALGO = "sha256"
SALT_BYTES = 16
MIN_PASSWORD_LEN = 8
IDENTITY_RECHECK_SECONDS = 30.0
_IDENTITY_VERIFIED_KEY = "_identity_verified_at"
SESSION_COOKIE_NAME = "fsdxai_session"
SESSION_COOKIE_SECONDS = 8 * 60 * 60
_CLEAR_COOKIE_KEY = "_clear_browser_session"

# ContextVar isolates concurrent Streamlit session threads. A short per-session
# verification timestamp prevents an identical cloud query on every tab click;
# privileged account changes always bypass it and revalidate immediately.
_render_identity = ContextVar('fsd_render_identity', default=None)


@contextmanager
def render_scope():
    token = _render_identity.set({})
    try:
        yield
    finally:
        _render_identity.reset(token)


def _invalidate_identity():
    memo = _render_identity.get()
    if memo is not None:
        memo.clear()
    try:
        st.session_state.pop(_IDENTITY_VERIFIED_KEY, None)
    except Exception:
        pass


def offline_mode_enabled() -> bool:
    """Return whether the loopback-only local recovery launcher is in use."""
    return not database.using_postgres() and os.environ.get("FSDXAI_OFFLINE_MODE", "").strip().lower() in {
        "1", "true", "yes", "on"
    }


def _offline_operator() -> dict:
    """Non-persistent identity used only in explicit local recovery mode."""
    return {
        "user_id": "USR-LOCAL-OFFLINE",
        "username": "local-operator",
        "role": "super_admin",
        "full_name": "Local Recovery Operator",
        "email": "",
        "offline_mode": True,
    }


def _session_signing_key() -> bytes | None:
    """Derive a dedicated HMAC key without exposing database credentials.

    Deployments may provide FSDXAI_SESSION_SECRET explicitly. Existing
    Supabase installations fall back to a domain-separated key derived from
    the high-entropy restricted database-role password already held server-side.
    """
    material = os.environ.get("FSDXAI_SESSION_SECRET", "").strip()
    if not material and database.using_postgres():
        try:
            material = unquote(urlsplit(database.DATABASE_URL).password or "")
        except ValueError:
            material = ""
    if len(material) < 32:
        return None
    return hashlib.sha256(
        b"FSD-XAI browser session signing key v1\0" + material.encode("utf-8")
    ).digest()


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _make_session_token(user: dict, *, now: int | None = None) -> str | None:
    key = _session_signing_key()
    if key is None or user.get("offline_mode"):
        return None
    issued = int(time.time() if now is None else now)
    payload = json.dumps({
        "exp": issued + SESSION_COOKIE_SECONDS,
        "iat": issued,
        "sv": int(user.get("session_version", 0)),
        "uid": str(user["user_id"]),
    }, sort_keys=True, separators=(",", ":")).encode("utf-8")
    encoded = _b64encode(payload)
    signature = _b64encode(hmac.new(key, encoded.encode("ascii"), hashlib.sha256).digest())
    return f"{encoded}.{signature}"


def _read_session_token(token: str, *, now: int | None = None) -> dict | None:
    key = _session_signing_key()
    if key is None or not token or len(token) > 2048:
        return None
    try:
        encoded, supplied = token.split(".", 1)
        expected = _b64encode(
            hmac.new(key, encoded.encode("ascii"), hashlib.sha256).digest()
        )
        if not hmac.compare_digest(supplied, expected):
            return None
        payload = json.loads(_b64decode(encoded))
        current = int(time.time() if now is None else now)
        if (set(payload) != {"exp", "iat", "sv", "uid"}
                or not isinstance(payload["uid"], str)
                or not payload["uid"]
                or not isinstance(payload["sv"], int)
                or not isinstance(payload["iat"], int)
                or not isinstance(payload["exp"], int)
                or payload["iat"] > current + 60
                or payload["exp"] <= current
                or payload["exp"] - payload["iat"] != SESSION_COOKIE_SECONDS):
            return None
        return payload
    except (ValueError, TypeError, KeyError, UnicodeError, binascii.Error):
        return None


def _browser_session_token() -> str:
    try:
        return str(st.context.cookies.get(SESSION_COOKIE_NAME, ""))
    except Exception:
        return ""


def _restore_browser_session() -> Optional[dict]:
    token = _browser_session_token()
    payload = _read_session_token(token)
    if not payload:
        if token:
            st.session_state[_CLEAR_COOKIE_KEY] = True
        return None
    try:
        fresh = database.get_user(payload["uid"])
    except Exception:
        # Preserve the valid signed token through a temporary cloud outage so
        # a later refresh can retry; access remains fail-closed in this render.
        return None
    if (not fresh or not fresh["active"]
            or fresh["session_version"] != payload["sv"]):
        st.session_state[_CLEAR_COOKIE_KEY] = True
        return None
    public = {key: value for key, value in fresh.items() if key != "password_hash"}
    st.session_state["current_user"] = public
    st.session_state[_IDENTITY_VERIFIED_KEY] = time.monotonic()
    return public


def render_session_cookie(user: Optional[dict]) -> None:
    """Synchronize the signed refresh session with the current browser."""
    if not user and not st.session_state.pop(_CLEAR_COOKIE_KEY, False):
        return
    token = _make_session_token(user) if user else None
    try:
        url = str(st.context.url)
        secure = urlsplit(url).scheme.lower() == "https"
    except Exception:
        secure = False
    from app.components.session_cookie import sync_session_cookie
    sync_session_cookie(
        name=SESSION_COOKIE_NAME,
        value=token or "",
        max_age=SESSION_COOKIE_SECONDS,
        secure=secure,
        key="fsdxai_session_cookie",
    )


# ── Password hashing (stdlib only) ────────────────────────────────────

def hash_password(password: str) -> str:
    """Return '<salt_hex>:<hash_hex>' for storage."""
    if not isinstance(password, str) or not password:
        raise ValueError("Password must be a non-empty string")
    salt = secrets.token_bytes(SALT_BYTES)
    dk = hashlib.pbkdf2_hmac(PBKDF2_ALGO, password.encode("utf-8"),
                              salt, PBKDF2_ITERATIONS)
    return f"{salt.hex()}:{dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """Constant-time verification against a stored hash."""
    if not stored or ":" not in stored:
        return False
    try:
        salt_hex, hash_hex = stored.split(":", 1)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(hash_hex)
        dk = hashlib.pbkdf2_hmac(PBKDF2_ALGO, password.encode("utf-8"),
                                  salt, PBKDF2_ITERATIONS)
        return hmac.compare_digest(dk, expected)
    except (ValueError, TypeError):
        return False


def password_error(password: str) -> Optional[str]:
    """Return an error message if the password is unacceptable, else None."""
    if not password:
        return "Password cannot be empty."
    if len(password) < MIN_PASSWORD_LEN:
        return f"Password must be at least {MIN_PASSWORD_LEN} characters."
    return None


# ── Bootstrap ─────────────────────────────────────────────────────────

def seed_super_admin_if_needed() -> Optional[str]:
    """If the users table is empty, seed one super admin from .env.

    Returns the new user_id, or None if not seeded (table already had users
    or the .env values were missing).
    """
    # Cloud accounts are provisioned explicitly by the setup wizard. Do not
    # reuse legacy INITIAL_ADMIN_* secrets after switching backends.
    if database.using_postgres() or offline_mode_enabled() or database.user_count() > 0:
        return None

    username = os.environ.get("INITIAL_ADMIN_USERNAME", "").strip()
    password = os.environ.get("INITIAL_ADMIN_PASSWORD", "").strip()
    full_name = os.environ.get("INITIAL_ADMIN_FULL_NAME",
                                "Super Administrator").strip()

    if not username or not password:
        logger.warning("No users exist and INITIAL_ADMIN_* env vars are not "
                       "set. Nobody can log in until an admin is created.")
        return None

    if password_error(password):
        logger.warning(f"INITIAL_ADMIN_PASSWORD too short "
                       f"(min {MIN_PASSWORD_LEN} chars). Skipping seed.")
        return None

    user_id = database.bootstrap_admin(
        username=username,
        password_hash=hash_password(password),
        full_name=full_name,
    )
    logger.info(f"Seeded super admin '{username}' (id={user_id})")
    return user_id


# ── Streamlit session helpers ────────────────────────────────────────

def current_user(*, force_refresh: bool = False) -> Optional[dict]:
    """Return the signed-in user, periodically revalidating cloud sessions.

    Within a Streamlit render scope, a recently verified identity can be used
    for ordinary navigation for a few seconds. Account mutations force a fresh
    database check and the database transaction independently verifies the
    actor's role/session version. Calls outside a render scope always recheck,
    which keeps scripts and security tests fail-closed.
    """
    if offline_mode_enabled():
        # The local launcher binds the server to 127.0.0.1. Do not create,
        # reset, or expose a persisted password just to run the demo locally.
        st.session_state["current_user"] = _offline_operator()
        return st.session_state['current_user']
    cached = st.session_state.get('current_user')
    if not cached:
        cached = _restore_browser_session()
    if not cached:
        return None
    memo = _render_identity.get()
    identity = (cached.get('user_id'), cached.get('session_version', 0))
    if not force_refresh and memo is not None and memo.get('identity') == identity:
        return memo['user']
    verified_at = st.session_state.get(_IDENTITY_VERIFIED_KEY)
    if (memo is not None and not force_refresh and verified_at is not None
            and time.monotonic() - float(verified_at) < IDENTITY_RECHECK_SECONDS):
        if memo is not None:
            memo.update(identity=identity, user=cached)
        return cached
    try:
        fresh = database.get_user(cached.get('user_id'))
    except Exception:
        fresh = None  # Fail closed on database outage, not cached privileges.
    if (not fresh or not fresh['active'] or
            fresh['session_version'] != cached.get('session_version', 0)):
        st.session_state.clear()
        st.session_state[_CLEAR_COOKIE_KEY] = True
        return None
    public = {k: v for k, v in fresh.items() if k != 'password_hash'}
    st.session_state['current_user'] = public
    st.session_state[_IDENTITY_VERIFIED_KEY] = time.monotonic()
    if memo is not None:
        memo.update(identity=identity, user=public)
    return public


def is_logged_in() -> bool:
    return current_user() is not None


def is_super_admin() -> bool:
    u = current_user()
    return bool(u and u.get("role") == "super_admin")


def is_examiner() -> bool:
    u = current_user()
    return bool(u and u.get("role") == "examiner")


def _transient_database_error(error: Exception) -> bool:
    """Return whether a failed read is safe to retry once."""
    if not database.using_postgres():
        return False
    try:
        from psycopg import InterfaceError, OperationalError
        from psycopg_pool import PoolTimeout
        return isinstance(error, (InterfaceError, OperationalError, PoolTimeout))
    except ImportError:
        return False


def login(username: str, password: str) -> tuple[bool, str]:
    """Attempt login. On success, stores user in session and returns (True, '').
    On failure, returns (False, error_message)."""
    _invalidate_identity()
    if not username or not password:
        return False, "Username and password are required."

    st.session_state.pop('current_user', None)
    user = None
    for attempt in range(2):
        try:
            user = database.get_user_by_username(username.strip())
            break
        except Exception as error:
            # Login is a read-only lookup, so one retry is safe when a pooled
            # connection has gone stale or the regional TLS handshake drops.
            if attempt == 0 and _transient_database_error(error):
                continue
            logger.warning("Login database lookup failed (%s)", type(error).__name__)
            return False, 'Database unavailable. Please try again or contact your administrator.'
    if not user:
        return False, "Invalid username or password."
    if not user.get("active"):
        return False, "Account is deactivated. Contact your administrator."
    if not verify_password(password, user["password_hash"]):
        return False, "Invalid username or password."

    # Success — strip password_hash before storing in session state
    user_copy = {k: v for k, v in user.items() if k != "password_hash"}
    st.session_state.clear()  # Do not retain a previous examiner's case context.
    st.session_state["current_user"] = user_copy
    st.session_state[_IDENTITY_VERIFIED_KEY] = time.monotonic()
    try:
        database.touch_last_login(user["user_id"])
    except Exception:
        pass
    return True, ""


def logout() -> None:
    """Clear the session's current_user (and related derived values)."""
    _invalidate_identity()
    if offline_mode_enabled():
        # The recovery operator is restored at the next app rerun.
        return
    st.session_state.clear()
    st.session_state[_CLEAR_COOKIE_KEY] = True


def require_role(role: str) -> bool:
    """Return True if current user has the required role. Otherwise render
    a small 'access denied' banner and return False."""
    u = current_user()
    if not u:
        st.error("You must sign in to access this page.")
        return False
    if u.get("role") != role:
        st.error(f"Access denied — requires role '{role}'.")
        return False
    return True


def _account_action(operation, *, target_id=None, values=None):
    # Never authorize a mutation from the short navigation cache.
    user = current_user(force_refresh=True)
    if not user or user.get('offline_mode'):
        raise PermissionError('Sign in with a database account to manage users.')
    try:
        return database.manage_account(user['user_id'], user['session_version'], operation,
                                       target_id=target_id, values=values)
    finally:
        _invalidate_identity()


def create_account(*, username, password, role, full_name, email=''):
    error = password_error(password)
    if error:
        raise ValueError(error)
    return _account_action('create', values=dict(username=username.strip(),
        password_hash=hash_password(password), role=role, full_name=full_name.strip(), email=email.strip()))


def update_account(user_id, **updates):
    password = updates.pop('password', None)
    if 'password_hash' in updates:
        raise ValueError('Supply a password, not a password hash.')
    if password is not None:
        error = password_error(password)
        if error:
            raise ValueError(error)
        updates['password_hash'] = hash_password(password)
    return _account_action('update', target_id=user_id, values=updates)


def delete_account(user_id, confirmation):
    return _account_action('delete', target_id=user_id, values={'confirmation': confirmation})


def change_password(current_password, new_password):
    error = password_error(new_password)
    if error:
        raise ValueError(error)
    result = _account_action('own_password', values=dict(current_password=current_password,
                            password_hash=hash_password(new_password)))
    logout()
    return result
