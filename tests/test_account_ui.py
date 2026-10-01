"""Exercise real Streamlit account widgets against a disposable local DB."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest
from app.services import auth, database as db

SCRIPT = '''
import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd() / 'app'))
from unittest.mock import patch
from views import settings
with patch.object(settings, 'render_model_picker', lambda: None):
    settings.render()
'''
PASSWORD = 'UI-test-password-2026!'


class AccountUITests(unittest.TestCase):
    def setUp(self):
        import os
        temp = tempfile.TemporaryDirectory(prefix='fsd_ui_')
        self.addCleanup(temp.cleanup)
        self.enterContext(patch.object(db, 'DATABASE_URL', ''))
        self.enterContext(patch.object(db, 'DB_PATH', Path(temp.name)/'test.db'))
        self.enterContext(patch.dict(os.environ, {'FSDXAI_OFFLINE_MODE': '0'}))
        db.init_db()
        self.admin = db.bootstrap_admin('admin', auth.hash_password(PASSWORD), 'Admin')
        self.examiner = db.create_user('examiner', auth.hash_password(PASSWORD), 'examiner', 'Examiner')

    def app(self, uid):
        app = AppTest.from_string(SCRIPT, default_timeout=15)
        app.session_state['current_user'] = {k: v for k, v in db.get_user(uid).items() if k != 'password_hash'}
        app.run()
        self.assertFalse(app.exception)
        return app

    def field(self, app, label, value):
        next(w for w in app.text_input if w.label == label).input(value)

    def button(self, app, label):
        next(w for w in app.button if w.label == label).click().run()
        self.assertFalse(app.exception)

    def test_admin_creates_updates_and_deletes_examiner(self):
        app = self.app(self.admin)
        for label, value in [('Username *', 'newuser'), ('Full name *', 'New Examiner'),
                             ('Password *', PASSWORD), ('Confirm password *', PASSWORD)]:
            self.field(app, label, value)
        self.button(app, 'Create account')
        user = db.get_user_by_username('newuser')
        self.assertIsNotNone(user)
        app.run()
        app.button(key='edit_'+user['user_id']).click().run()
        app.text_input(key='fn_'+user['user_id']).input('Updated Name')
        app.button(key='sv_'+user['user_id']).click().run()
        self.assertFalse(app.exception)
        self.assertEqual(db.get_user(user['user_id'])['full_name'], 'Updated Name')
        # Start a fresh page after the inline editor disappears; this also
        # verifies that the changed account is persisted, not just in UI state.
        app = self.app(self.admin)
        app.text_input(key='delete_confirmation_'+user['user_id']).input('newuser')
        app.button(key='delete_'+user['user_id']).click().run()
        self.assertFalse(app.exception)
        self.assertIsNone(db.get_user(user['user_id']))

    def test_examiner_only_has_self_service_and_can_change_password(self):
        app = self.app(self.examiner)
        self.assertFalse(app.tabs)
        self.assertEqual([b.label for b in app.button], ['Update password'])
        for label, value in [('Current password', PASSWORD), ('New password', 'Changed-UI-password!'),
                             ('Confirm new password', 'Changed-UI-password!')]:
            self.field(app, label, value)
        self.button(app, 'Update password')
        self.assertNotIn('current_user', app.session_state)
        self.assertTrue(auth.verify_password('Changed-UI-password!', db.get_user(self.examiner)['password_hash']))


if __name__ == '__main__':
    unittest.main()
