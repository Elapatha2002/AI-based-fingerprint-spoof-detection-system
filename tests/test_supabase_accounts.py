"""SQLite and opt-in disposable PostgreSQL contract tests for account security."""
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch, Mock
from urllib.parse import urlsplit, urlunsplit

from app.services import auth, database as db, storage

PASSWORD = 'Fixture-password-2026!'


class AccountContract:
    def make_accounts(self):
        self.session = {}
        self.enterContext(patch.object(auth, 'st', SimpleNamespace(session_state=self.session, error=lambda x: None)))
        self.enterContext(patch.dict(os.environ, {'FSDXAI_OFFLINE_MODE': '0'}))
        self.admin = db.bootstrap_admin('admin', auth.hash_password(PASSWORD), 'Super Admin')
        self.assertIsNotNone(self.admin)
        self.assertTrue(auth.login('admin', PASSWORD)[0])
        self.examiner = auth.create_account(username='examiner', password=PASSWORD,
            role='examiner', full_name='Test Examiner', email='examiner@example.invalid')

    def test_create_and_login(self):
        self.assertTrue(auth.login('examiner', PASSWORD)[0])
        user = auth.current_user()
        self.assertEqual(user['role'], 'examiner')
        self.assertNotIn('password_hash', user)
        self.assertNotEqual(db.get_user(self.examiner)['password_hash'], PASSWORD)

    def test_examiner_cannot_mutate_accounts(self):
        auth.login('examiner', PASSWORD)
        for operation in (
            lambda: auth.create_account(username='intruder', password=PASSWORD, role='super_admin', full_name='Intruder'),
            lambda: auth.update_account(self.examiner, role='super_admin'),
            lambda: auth.delete_account(self.admin, 'admin')):
            with self.assertRaises(PermissionError):
                operation()
        self.assertEqual(db.get_user(self.examiner)['role'], 'examiner')

    def test_bootstrap_is_idempotent(self):
        self.assertIsNone(db.bootstrap_admin('replacement', auth.hash_password(PASSWORD), 'Replacement'))
        self.assertEqual(db.user_count(), 2)

    def test_last_admin_cannot_be_disabled_demoted_or_deleted(self):
        for operation in (lambda: db.update_user(self.admin, active=0),
                          lambda: db.update_user(self.admin, role='examiner'),
                          lambda: db.delete_user(self.admin)):
            with self.assertRaises(ValueError):
                operation()
        self.assertTrue(db.get_user(self.admin)['active'])

    def test_self_delete_and_disable_denied_even_with_second_admin(self):
        auth.create_account(username='admin2', password=PASSWORD, role='super_admin', full_name='Second Admin')
        for operation in (lambda: auth.delete_account(self.admin, 'admin'),
                          lambda: auth.update_account(self.admin, active=0)):
            with self.assertRaises(ValueError):
                operation()

    def test_update_and_password_reset(self):
        auth.update_account(self.examiner, full_name='Updated Examiner', email='new@example.invalid', password='New-fixture-password!')
        self.assertEqual(db.get_user(self.examiner)['full_name'], 'Updated Examiner')
        self.assertFalse(auth.login('examiner', PASSWORD)[0])
        self.assertTrue(auth.login('examiner', 'New-fixture-password!')[0])

    def test_duplicate_invalid_role_and_blank_name_rejected(self):
        for values in (dict(username='examiner', role='examiner', full_name='Duplicate'),
                       dict(username='new', role='root', full_name='Invalid'),
                       dict(username='new', role='examiner', full_name=' ')):
            with self.assertRaises(ValueError):
                auth.create_account(password=PASSWORD, **values)
        self.assertEqual(db.user_count(), 2)

    def test_disable_revokes_session_and_prevents_login(self):
        auth.login('examiner', PASSWORD)
        self.session['current_single'] = {'private_case': 'fixture'}
        db.update_user(self.examiner, active=0)
        self.assertIsNone(auth.current_user())
        self.assertNotIn('current_single', self.session)
        self.assertFalse(auth.login('examiner', PASSWORD)[0])

    def test_password_change_revokes_previous_session(self):
        auth.login('examiner', PASSWORD)
        db.update_user(self.examiner, password_hash=auth.hash_password('Reset-fixture-password!'))
        self.assertIsNone(auth.current_user())

    def test_role_change_revokes_previous_session(self):
        auth.create_account(username='admin2', password=PASSWORD, role='super_admin', full_name='Second Admin')
        db.update_user(self.admin, role='examiner')
        self.assertFalse(auth.is_super_admin())

    def test_own_password_requires_current_password(self):
        auth.login('examiner', PASSWORD)
        with self.assertRaises(ValueError):
            auth.change_password('wrong', 'Updated-password-2026!')
        auth.change_password(PASSWORD, 'Updated-password-2026!')
        self.assertIsNone(auth.current_user())
        self.assertTrue(auth.login('examiner', 'Updated-password-2026!')[0])

    def test_delete_preserves_cases_and_records_actor(self):
        case_id = db.create_case('Preserve me', examiner='Test Examiner')
        db.log_event('viewed', case_id=case_id, user=self.examiner)
        with self.assertRaises(ValueError):
            auth.delete_account(self.examiner, 'wrong confirmation')
        auth.delete_account(self.examiner, 'examiner')
        self.assertIsNone(db.get_user(self.examiner))
        self.assertIsNotNone(db.get_case(case_id))
        self.assertEqual(len(db.get_audit_trail(case_id=case_id)), 2)
        events = [e for e in db.get_audit_trail() if e['action'] == 'user_delete']
        self.assertEqual(events[0]['user'], self.admin)
        self.assertIn(self.examiner, events[0]['details'])

    def test_deleted_account_session_revoked(self):
        auth.login('examiner', PASSWORD)
        db.delete_user(self.examiner)
        self.assertIsNone(auth.current_user())

    def test_database_outage_fails_closed(self):
        with patch.object(db, 'get_user', side_effect=RuntimeError('test outage')):
            self.assertIsNone(auth.current_user())

    def test_mutation_rechecks_version_inside_transaction(self):
        db.update_user(self.admin, password_hash=auth.hash_password('Rotated-password!'))
        with self.assertRaises(PermissionError):
            db.manage_account(self.admin, 0, 'delete', target_id=self.examiner,
                              values={'confirmation': 'examiner'})

    def test_logout_clears_previous_examiner_data(self):
        self.session['history'] = [{'case': 'private'}]
        auth.logout()
        self.assertEqual(self.session, {auth._CLEAR_COOKIE_KEY: True})

    def test_concurrent_admin_demotion_preserves_one_admin(self):
        other = auth.create_account(username='admin2', password=PASSWORD, role='super_admin', full_name='Second')
        def demote(pair):
            actor, target = pair
            try:
                db.manage_account(actor, 0, 'update', target_id=target, values={'role': 'examiner'})
                return True
            except (ValueError, PermissionError):
                return False
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(demote, [(self.admin, other), (other, self.admin)]))
        self.assertEqual(sum(outcomes), 1)
        self.assertEqual(sum(u['role']=='super_admin' and u['active'] for u in db.list_users()), 1)


class SQLiteAccounts(AccountContract, unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='fsd_accounts_')
        self.addCleanup(temp.cleanup)
        self.enterContext(patch.object(db, 'DATABASE_URL', ''))
        self.enterContext(patch.object(db, 'DB_PATH', Path(temp.name)/'test.db'))
        db.init_db()
        self.make_accounts()


@unittest.skipUnless(os.environ.get('FSD_TEST_POSTGRES_URL'), 'No disposable PostgreSQL test URL configured')
class PostgreSQLAccounts(AccountContract, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import psycopg
        from app.supabase_schema import provision
        cls.admin_url = os.environ['FSD_TEST_POSTGRES_URL']
        parts = urlsplit(cls.admin_url)
        if parts.hostname not in ('127.0.0.1', 'localhost') or parts.path != '/fsd_test':
            raise RuntimeError('Integration tests require a loopback database named fsd_test. Never use Supabase credentials here.')
        with psycopg.connect(cls.admin_url) as conn:
            # Supabase's postgres role is not a true superuser. Exercise
            # provisioning with a non-superuser that can create roles/schema.
            for role in ('anon', 'authenticated'):
                if not conn.execute('SELECT 1 FROM pg_roles WHERE rolname = %s', (role,)).fetchone():
                    conn.execute(psycopg.sql.SQL('CREATE ROLE {} NOLOGIN').format(psycopg.sql.Identifier(role)))
            if not conn.execute("SELECT 1 FROM pg_roles WHERE rolname = 'fsd_provisioner'").fetchone():
                conn.execute("CREATE ROLE fsd_provisioner LOGIN CREATEROLE PASSWORD 'provisioner-fixture-password'")
            conn.execute('GRANT CREATE ON DATABASE fsd_test TO fsd_provisioner')
        provisioning_url = urlunsplit(parts._replace(netloc=f'fsd_provisioner:provisioner-fixture-password@{parts.hostname}:{parts.port}'))
        with psycopg.connect(provisioning_url) as conn:
            provision(conn, 'runtime-fixture-password', allow_existing=True)
        cls.runtime_url = urlunsplit(parts._replace(netloc=f'fsd_app_runtime:runtime-fixture-password@{parts.hostname}:{parts.port}'))

    def setUp(self):
        import psycopg
        # This can only target the disposable loopback database checked above.
        with psycopg.connect(self.admin_url) as conn:
            conn.execute('TRUNCATE fsd_app.users, fsd_app.cases, fsd_app.analyses, fsd_app.xai_outputs, fsd_app.reports, fsd_app.audit_log CASCADE')
        self.enterContext(patch.object(db, 'DATABASE_URL', self.runtime_url))
        db.init_db()
        self.make_accounts()

    def test_runtime_cannot_delete_audit_or_create_tables(self):
        import psycopg
        for query in ('DELETE FROM audit_log', 'CREATE TABLE should_not_exist (n integer)'):
            with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                with db.connect() as conn:
                    conn.execute(query)

    def test_parameterised_case_and_analysis_roundtrip(self):
        case = db.create_case("O'Brien's % case?", 'Test Examiner')
        analysis = db.record_analysis(case, 'test.png', 'test-key', 'fixture', 'live', .9,
                                       examiner='Test Examiner')
        self.assertEqual(db.get_case(case)['case_name'], "O'Brien's % case?")
        self.assertEqual(db.get_analysis(analysis)['confidence'], .9)
        self.assertEqual(db.get_audit_trail(analysis_id=analysis)[0]['user'], 'Test Examiner')

    def test_browser_roles_cannot_read_private_users(self):
        import psycopg
        for role in ('anon', 'authenticated'):
            with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                with psycopg.connect(self.admin_url) as conn:
                    conn.execute(psycopg.sql.SQL('SET LOCAL ROLE {}').format(psycopg.sql.Identifier(role)))
                    conn.execute('SELECT * FROM fsd_app.users')


class SupabaseStorageConfiguration(unittest.TestCase):
    def test_upload_download_and_signed_url_use_private_bucket(self):
        config = storage.S3Config('fixture-access', 'fixture-secret', 'ap-southeast-1',
            'fingerprint-evidence', 'https://example.supabase.co/storage/v1/s3', 'path', 'none')
        service = storage.StorageService(config)
        client = service._client = Mock()
        service.upload_bytes('uploads/fixture.png', b'fixture', 'image/png')
        client.put_object.assert_called_once_with(Bucket='fingerprint-evidence',
            Key='uploads/fixture.png', Body=b'fixture', ContentType='image/png')
        client.download_fileobj.side_effect = lambda bucket, key, buffer: buffer.write(b'fixture')
        self.assertEqual(service.download_bytes('uploads/fixture.png'), b'fixture')
        service.presigned_url('uploads/fixture.png', 60)
        client.generate_presigned_url.assert_called_once_with('get_object',
            Params={'Bucket': 'fingerprint-evidence', 'Key': 'uploads/fixture.png'}, ExpiresIn=60)

    def test_supabase_does_not_reuse_old_aws_credentials(self):
        config = dict(FSDXAI_STORAGE_BACKEND='supabase', SUPABASE_S3_ENDPOINT='https://example.supabase.co/storage/v1/s3',
                      SUPABASE_S3_ACCESS_KEY_ID='fixture-access', SUPABASE_S3_SECRET_ACCESS_KEY='fixture-secret',
                      SUPABASE_S3_REGION='ap-southeast-1', SUPABASE_STORAGE_BUCKET='fingerprint-evidence',
                      AWS_ACCESS_KEY_ID='old-key')
        with patch.dict(os.environ, config):
            selected = storage.S3Config.from_env()
        self.assertEqual(selected.access_key, 'fixture-access')
        self.assertEqual(selected.addressing_style, 'path')
        self.assertEqual(selected.server_side_encryption, 'none')

    def test_missing_supabase_credentials_do_not_fall_back_to_local(self):
        with patch.object(storage, '_service', None), patch.dict(os.environ,
                dict(FSDXAI_STORAGE_BACKEND='supabase', SUPABASE_S3_ENDPOINT='https://example.supabase.co/storage/v1/s3',
                     SUPABASE_S3_ACCESS_KEY_ID='', SUPABASE_S3_SECRET_ACCESS_KEY='')):
            with self.assertRaises(RuntimeError):
                storage.get_storage()


if __name__ == '__main__':
    unittest.main()
