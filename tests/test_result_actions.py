"""Result actions against disposable SQLite/storage, never live cloud records."""
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image
from streamlit.testing.v1 import AppTest
from app.services import database as db, storage, persistence

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'app'))

SCRIPT = '''
import streamlit as st
from state import init_state
from views.single_result import _render_result_actions
init_state()
_render_result_actions('fixture.png', st.session_state['image'],
    st.session_state['meta'], st.session_state['result'], st.session_state['xai'])
'''


class ResultActionsTests(unittest.TestCase):
    def setUp(self):
        from views import single_result
        tmp = tempfile.TemporaryDirectory(prefix='fsd_save_case_')
        self.addCleanup(tmp.cleanup)
        self.enterContext(patch.object(db, 'DATABASE_URL', ''))
        self.enterContext(patch.object(db, 'DB_PATH', Path(tmp.name)/'test.db'))
        db.init_db()
        self.local = storage.LocalStorageService(Path(tmp.name)/'objects')
        self.enterContext(patch.object(storage, 'get_storage', return_value=self.local))
        self.audit = self.enterContext(patch.object(single_result, 'log_action'))
        content = io.BytesIO()
        Image.new('RGB', (100,100), 'gray').save(content, format='PNG')
        self.image = content.getvalue()
        self.app = AppTest.from_string(SCRIPT)
        self.app.session_state['image'] = self.image
        self.app.session_state['meta'] = {'case_id':'CASE-SAVE-TEST', 'examiner':'Fixture Examiner'}
        self.app.session_state['result'] = {'label':'live', 'confidence':.9,
            'model': {'name':'fixture-model'}, 'threshold_used':.5}
        self.app.session_state['xai'] = {
            name: {
                'image': b'fixture-overlay', 'faithfulness': .7,
                'localization_iou': .6, 'compute_ms': 10,
                'summary': f'{name} fixture',
            }
            for name in ('gradcam', 'shap', 'lime')
        }
        self.app.run()
        self.assertFalse(self.app.exception)

    def test_report_and_compare_wait_for_all_explanations(self):
        self.app.session_state['xai'] = {'gradcam': self.app.session_state['xai']['gradcam']}
        self.app.run()
        self.assertTrue(self.app.button(key='sr_report').disabled)
        self.assertTrue(self.app.button(key='sr_compare').disabled)
        self.assertFalse(self.app.button(key='sr_save').disabled)

    def test_success_saves_bytes_and_record_without_toast_crash(self):
        self.app.button(key='sr_save').click().run()
        self.assertFalse(self.app.exception)
        rows = db.list_analyses()
        self.assertEqual(len(rows), 1)
        self.assertEqual(self.local.download_bytes(rows[0]['image_s3_key']), self.image)
        self.assertEqual(len(self.app.session_state['history']), 1)
        self.assertIn(rows[0]['analysis_id'], self.app.success[0].value)
        self.assertEqual(self.app.toast[0].value, 'Case record saved.')
        self.audit.assert_called_once()

    def test_repeat_click_does_not_duplicate_saved_result(self):
        self.app.button(key='sr_save').click().run()
        self.app.run()
        self.assertTrue(self.app.button(key='sr_save').disabled)
        self.assertEqual(self.app.button(key='sr_save').label, 'Saved')
        self.app.button(key='sr_save').click().run()
        self.assertFalse(self.app.exception)
        self.assertEqual(len(db.list_analyses()), 1)
        self.assertEqual(len(self.app.session_state['history']), 1)

    def test_failed_save_shows_error_and_can_be_retried(self):
        with patch.object(persistence, 'save_single_analysis', return_value=None):
            self.app.button(key='sr_save').click().run()
        self.assertFalse(self.app.exception)
        self.assertIn('was not saved', self.app.error[0].value)
        self.assertFalse(self.app.success)
        self.assertEqual(self.app.session_state['history'], [])
        self.assertFalse(self.app.button(key='sr_save').disabled)
        self.app.button(key='sr_save').click().run()
        self.assertFalse(self.app.exception)
        self.assertEqual(len(db.list_analyses()), 1)

    def test_storage_failure_identifies_the_failing_step_without_secret(self):
        failure = persistence.PersistenceSaveError('image')
        with patch.object(persistence, 'save_single_analysis', side_effect=failure):
            self.app.button(key='sr_save').click().run()
        self.assertFalse(self.app.exception)
        self.assertIn('Evidence storage', self.app.error[0].value)
        self.assertFalse(self.app.success)
        self.assertFalse(self.app.button(key='sr_save').disabled)

    def test_changed_model_is_a_new_result(self):
        self.app.button(key='sr_save').click().run()
        self.app.session_state['result'] = {'label':'live', 'confidence':.8,
            'model': {'name':'another-model'}, 'threshold_used':.5}
        self.app.run()
        self.assertFalse(self.app.button(key='sr_save').disabled)
        self.app.button(key='sr_save').click().run()
        self.assertEqual(len(db.list_analyses()), 2)

    def test_compare_and_report_keep_their_targets(self):
        self.app.button(key='sr_compare').click().run()
        self.assertEqual(self.app.session_state['current_page'], 'compare_xai')
        self.assertEqual(self.app.session_state['compare_target']['image_bytes'], self.image)
        self.app.button(key='sr_report').click().run()
        self.assertEqual(self.app.session_state['current_page'], 'report_preview')
        self.assertEqual(self.app.session_state['current_report_target']['image_bytes'], self.image)


if __name__ == '__main__':
    unittest.main()
