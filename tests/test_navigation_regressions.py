"""No cloud access: real Streamlit routing with temporary users and test images."""
import io
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch, Mock

from PIL import Image
from streamlit.testing.v1 import AppTest
from app.services import auth, database as db

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'app'))


class NavigationTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='fsd_navigation_')
        self.addCleanup(temp.cleanup)
        self.enterContext(patch.object(db, 'DATABASE_URL', ''))
        self.enterContext(patch.object(db, 'DB_PATH', Path(temp.name)/'test.db'))
        self.enterContext(patch.dict(os.environ, {'FSDXAI_OFFLINE_MODE':'0', 'FSDXAI_REAL_MODEL':'0'}))
        db.init_db()
        uid = db.bootstrap_admin('fixture', auth.hash_password('Fixture-password!'), 'Fixture Examiner')
        self.user = {k:v for k,v in db.get_user(uid).items() if k != 'password_hash'}

    def test_detail_pages_do_not_redirect_to_home(self):
        script = '''
import streamlit as st
from nav import render_nav
render_nav()
st.write('PAGE=' + st.session_state.current_page)
'''
        for page in ('single_result', 'processing', 'batch_dashboard', 'drilldown', 'report_preview'):
            with self.subTest(page=page):
                app = AppTest.from_string(script)
                app.session_state['current_user'] = self.user
                app.session_state['current_page'] = page
                app.run()
                self.assertFalse(app.exception)
                self.assertEqual(app.session_state['current_page'], page)

    def test_navigation_selection_renders_once(self):
        script = '''
import streamlit as st
from nav import render_nav
st.session_state['render_count'] = st.session_state.get('render_count', 0) + 1
render_nav()
'''
        app = AppTest.from_string(script)
        app.session_state['current_user'] = self.user
        app.session_state['current_page'] = 'home'
        app.run()
        count = app.session_state['render_count']
        app.get('button_group')[0].set_value('Analyze').run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state['current_page'], 'analyze')
        self.assertEqual(app.session_state['render_count'], count + 1)

    def test_run_analysis_reaches_classifier_and_result(self):
        from views import single_result
        from services import mock_model
        picture = Image.new('RGB', (100, 100), 'gray')
        content = io.BytesIO()
        picture.save(content, format='PNG')
        upload = io.BytesIO(content.getvalue())
        upload.name = 'fixture.png'
        def uploader(*args, **kwargs):
            return upload if kwargs.get('key') == 'single_uploader' else None
        prediction = mock_model.predict('fixture.png', picture)
        with patch('streamlit.file_uploader', side_effect=uploader), \
                patch.object(single_result, '_cached_predict', return_value=prediction) as classifier, \
                patch.object(single_result, '_cached_explain', return_value={}), \
                patch.object(single_result, 'xai_tabs'), \
                patch.object(single_result, 'render_xai_interpretation'):
            # Use the real Analyze and Single Result views, not a simulated route.
            script = '''
import streamlit as st
from state import init_state
from nav import render_nav
from views import analyze, single_result
from app.services import auth
with auth.render_scope():
    init_state()
    st.session_state['render_count'] = st.session_state.get('render_count', 0) + 1
    render_nav()
    if st.session_state.current_page == 'analyze':
        analyze.render()
    elif st.session_state.current_page == 'single_result':
        single_result.render()
'''
            app = AppTest.from_string(script, default_timeout=15)
            app.session_state['current_user'] = self.user
            app.session_state['current_page'] = 'analyze'
            app.run()
            self.assertFalse(app.exception)
            self.assertFalse(app.button(key='single_start').disabled)
            count = app.session_state['render_count']
            app.button(key='single_start').click().run()
            self.assertFalse(app.exception)
            self.assertEqual(app.session_state['current_page'], 'single_result')
            self.assertEqual(app.session_state['render_count'], count + 1)
            classifier.assert_called_once_with('fixture.png', content.getvalue())
            self.assertIsNotNone(app.button(key='sr_report'))

    def test_identity_is_queried_once_per_render_but_not_cached_between_clicks(self):
        session = {'current_user': self.user}
        with patch.object(auth, 'st', SimpleNamespace(session_state=session)), \
                patch.object(db, 'get_user', wraps=db.get_user) as fetch:
            with auth.render_scope():
                self.assertTrue(auth.is_logged_in())
                self.assertTrue(auth.is_super_admin())
                self.assertEqual(auth.current_user()['username'], 'fixture')
            self.assertEqual(fetch.call_count, 1)
            with auth.render_scope():
                self.assertTrue(auth.is_logged_in())
            self.assertEqual(fetch.call_count, 2)

    def test_cached_identity_does_not_authorise_stale_admin_mutation(self):
        session = {'current_user': self.user}
        with patch.object(auth, 'st', SimpleNamespace(session_state=session)):
            with auth.render_scope():
                self.assertTrue(auth.is_super_admin())
                db.update_user(self.user['user_id'], password_hash=auth.hash_password('Rotated-password!'))
                with self.assertRaises(PermissionError):
                    auth.create_account(username='intruder', password='Fixture-password!',
                                        role='super_admin', full_name='Intruder')
            with auth.render_scope():
                self.assertIsNone(auth.current_user())


class PoolTests(unittest.TestCase):
    def test_connections_reuse_bounded_pool(self):
        from app.services import postgres_backend as pg
        fake_pool = Mock()
        with patch.object(pg, '_pools', {}), patch('psycopg_pool.ConnectionPool', return_value=fake_pool) as factory:
            url = 'postgresql://fixture:fixture@localhost/fsd_test'
            self.assertIs(pg._get_pool(url), pg._get_pool(url))
            factory.assert_called_once()
            self.assertEqual(factory.call_args.kwargs['max_size'], 3)
            pg.close_pools()
            fake_pool.close.assert_called_once()


if __name__ == '__main__':
    unittest.main()
