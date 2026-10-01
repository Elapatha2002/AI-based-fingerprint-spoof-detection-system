"""Offline checks of setup safety; never load/write real configuration files."""
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit, unquote

from app import setup_supabase as setup
from app.services import database as db
from app.services.postgres_backend import connect


class SetupTests(unittest.TestCase):
    def test_password_special_characters_are_encoded(self):
        password = "spaces @:/?#%&'secret"
        parts = urlsplit(setup.url_for('fixture.user', password))
        self.assertEqual(unquote(parts.password), password)
        self.assertEqual(parts.hostname, setup.HOST)
        self.assertEqual(parts.query, 'sslmode=require')

    def test_private_configuration_roundtrip(self):
        from dotenv import dotenv_values
        with tempfile.TemporaryDirectory(prefix='fsd_setup_') as directory:
            target = Path(directory)/'.env.supabase'
            with patch.object(setup, 'CONFIG', target):
                setup.write_configuration({'SUPABASE_S3_SECRET_ACCESS_KEY': "a'b $ c#d"})
                setup.write_configuration({'DATABASE_URL': 'fixture-only'})
            self.assertEqual(dotenv_values(target)['SUPABASE_S3_SECRET_ACCESS_KEY'], "a'b $ c#d")
            self.assertNotIn('INITIAL_ADMIN_PASSWORD', dotenv_values(target))
            if os.name != 'nt':
                self.assertEqual(target.stat().st_mode & 0o777, 0o600)

    def test_remote_database_without_tls_is_rejected_before_connecting(self):
        with patch('psycopg.connect') as driver:
            with self.assertRaises(ValueError):
                with connect('postgresql://fixture:fixture@db.example.invalid/postgres'):
                    pass
            driver.assert_not_called()

    def test_invalid_url_does_not_fall_back_to_sqlite(self):
        with patch.object(db, 'DATABASE_URL', 'https://invalid.example'), patch('sqlite3.connect') as driver:
            with self.assertRaises(ValueError):
                db.init_db()
            driver.assert_not_called()

    def test_legacy_sqlite_migration_preserves_accounts(self):
        with tempfile.TemporaryDirectory(prefix='fsd_migrate_') as directory:
            target = Path(directory)/'legacy.db'
            with sqlite3.connect(target) as conn:
                conn.execute('CREATE TABLE users (user_id TEXT PRIMARY KEY, username TEXT UNIQUE, password_hash TEXT, role TEXT, full_name TEXT, email TEXT, active INTEGER, created_at TEXT, last_login TEXT)')
                conn.execute("INSERT INTO users VALUES ('fixture', 'legacy', 'fixture-hash', 'super_admin', 'Legacy', '', 1, '', '')")
            conn.close()
            with patch.object(db, 'DATABASE_URL', ''), patch.object(db, 'DB_PATH', target):
                db.init_db()
                db.init_db()
                self.assertEqual(db.get_user('fixture')['password_hash'], 'fixture-hash')
                self.assertEqual(db.get_user('fixture')['session_version'], 0)


if __name__ == '__main__':
    unittest.main()
