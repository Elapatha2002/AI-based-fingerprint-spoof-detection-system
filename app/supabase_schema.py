"""Explicit provisioning; never called during ordinary app startup.

Creates only the fsd_app schema and its dedicated runtime login. Supabase Auth,
public tables and storage objects are not changed. Admin credentials stay in
memory. The resulting runtime login cannot change schemas or delete audit rows.
"""
from psycopg import sql
from app.services.database import SCHEMA

TABLES = ('cases', 'analyses', 'xai_outputs', 'reports', 'audit_log', 'users')
RUNTIME_ROLE = 'fsd_app_runtime'


def provision(connection, runtime_password, *, allow_existing=False):
    role = sql.Identifier(RUNTIME_ROLE)
    existing = connection.execute('SELECT 1 FROM pg_roles WHERE rolname = %s', (RUNTIME_ROLE,)).fetchone()
    if existing and not allow_existing:
        raise ValueError('An application runtime role already exists. Use the original .env.supabase file to resume setup; no credentials were replaced.')
    if not existing:
        connection.execute(sql.SQL('CREATE ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS').format(role, sql.Literal(runtime_password)))
    # Existing credentials are never rotated implicitly.
    connection.execute('CREATE SCHEMA IF NOT EXISTS fsd_app')
    connection.execute('REVOKE ALL ON SCHEMA fsd_app FROM PUBLIC')
    connection.execute('SET LOCAL search_path TO fsd_app, pg_catalog')
    # The shared schema contains only ordinary DDL, without procedural bodies.
    for statement in SCHEMA.replace('REAL', 'DOUBLE PRECISION').split(';'):
        if statement.strip():
            connection.execute(statement)
    connection.execute('ALTER TABLE users ADD COLUMN IF NOT EXISTS session_version INTEGER NOT NULL DEFAULT 0')
    for name in TABLES:
        table = sql.Identifier('fsd_app', name)
        connection.execute(sql.SQL('REVOKE ALL ON TABLE {} FROM PUBLIC').format(table))
        connection.execute(sql.SQL('ALTER TABLE {} ENABLE ROW LEVEL SECURITY').format(table))
        connection.execute(sql.SQL('DROP POLICY IF EXISTS server_access ON {}').format(table))
        connection.execute(sql.SQL('CREATE POLICY server_access ON {} TO {} USING (true) WITH CHECK (true)').format(table, role))
        connection.execute(sql.SQL('REVOKE ALL ON TABLE {} FROM {}').format(table, role))
        privilege = sql.SQL('SELECT, INSERT') if name == 'audit_log' else sql.SQL('SELECT, INSERT, UPDATE, DELETE')
        connection.execute(sql.SQL('GRANT {} ON TABLE {} TO {}').format(privilege, table, role))
    # No browser Data API access to password hashes or forensic case records.
    for public_role in ('anon', 'authenticated'):
        if connection.execute('SELECT 1 FROM pg_roles WHERE rolname = %s', (public_role,)).fetchone():
            connection.execute(sql.SQL('REVOKE ALL ON SCHEMA fsd_app FROM {}').format(sql.Identifier(public_role)))
            connection.execute(sql.SQL('REVOKE ALL ON ALL TABLES IN SCHEMA fsd_app FROM {}').format(sql.Identifier(public_role)))
    connection.execute(sql.SQL('GRANT USAGE ON SCHEMA fsd_app TO {}').format(role))


def verify_private_bucket(connection, name):
    """Read the bucket metadata; never silently make an existing bucket public/private."""
    row = connection.execute('SELECT public FROM storage.buckets WHERE id = %s', (name,)).fetchone()
    if not row:
        raise ValueError('Create the fingerprint-evidence bucket in Supabase Storage first.')
    if row[0]:
        raise ValueError('The evidence bucket is public. Turn Public bucket OFF before proceeding.')
