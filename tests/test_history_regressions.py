"""History regressions with disposable SQLite and local evidence only."""
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image
from streamlit.testing.v1 import AppTest
from app.services import database as db, persistence, storage

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))

SCRIPT = '''
import streamlit as st
from state import init_state
from views import history, saved_analysis
init_state()
if st.session_state.current_page == 'saved_analysis':
    saved_analysis.render()
else:
    history.render()
'''


class HistoryTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix='fsd_history_')
        self.addCleanup(tmp.cleanup)
        self.enterContext(patch.object(db, 'DATABASE_URL', ''))
        self.enterContext(patch.object(db, 'DB_PATH', Path(tmp.name) / 'test.db'))
        db.init_db()
        persistence._ensure_case('CASE-HISTORY', 'Test Examiner')
        self.local = storage.LocalStorageService(Path(tmp.name) / 'objects')
        self.enterContext(patch.object(storage, 'get_storage', return_value=self.local))
        content = io.BytesIO()
        Image.new('RGB', (32, 32), 'gray').save(content, format='PNG')
        self.image = content.getvalue()

    def save(self, *, image=None, model='test-model', verdict='spoof'):
        return persistence.save_single_analysis(
            filename='fingerprint.png', image_bytes=image or self.image,
            meta={'case_id': 'CASE-HISTORY', 'examiner': 'Test Examiner'},
            result={'label': verdict, 'confidence': .91,
                    'model': {'name': model}, 'threshold_used': .5,
                    'timing_ms': {'total': 12}},
        )

    def app(self):
        app = AppTest.from_string(SCRIPT).run()
        self.assertFalse(app.exception)
        return app

    def test_repeated_saves_count_one_image_and_keep_all_records(self):
        ids = [self.save() for _ in range(3)]
        row, = persistence.list_history_from_db()
        self.assertEqual((row['type'], row['count'], row['spoof_count'], row['live_count']),
                         ('single', 1, 1, 0))
        self.assertEqual(row['saved_count'], 3)
        self.assertEqual({r['analysis_id'] for r in db.list_analyses()}, set(ids))

    def test_different_models_retained_and_counts_use_latest_image_result(self):
        old = self.save()
        new = self.save(model='new-model', verdict='live')
        with db.connect() as conn:
            conn.execute('UPDATE analyses SET created_at = ? WHERE analysis_id = ?',
                         ('2020-01-01T00:00:00+00:00', old))
            conn.execute('UPDATE analyses SET created_at = ? WHERE analysis_id = ?',
                         ('2021-01-01T00:00:00+00:00', new))
        row, = persistence.list_history_from_db()
        self.assertEqual((row['count'], row['live_count'], row['spoof_count']), (1, 1, 0))
        self.assertEqual(row['saved_count'], 2)
        app = self.app()
        app.button(key='hist_open').click().run()
        app.selectbox(key='saved_record_CASE-HISTORY').select(old).run()
        self.assertFalse(app.exception)
        self.assertEqual(app.metric[0].value, 'SPOOF')
        self.assertEqual(app.dataframe[0].value.iloc[0]['Saved value'], 'test-model')

    def test_same_filename_different_images_are_not_collapsed(self):
        self.save()
        content = io.BytesIO()
        Image.new('RGB', (32, 32), 'white').save(content, format='PNG')
        self.save(image=content.getvalue(), verdict='live')
        row, = persistence.list_history_from_db()
        self.assertEqual((row['type'], row['count'], row['live_count'], row['spoof_count']),
                         ('multiple images', 2, 1, 1))
        app = self.app()
        app.selectbox(key='hist_type').select('Multiple images').run()
        app.button(key='hist_open').click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state['current_page'], 'saved_analysis')
        self.assertEqual(len(app.selectbox(key='saved_record_CASE-HISTORY').options), 2)
        self.assertFalse(app.warning)

    def test_open_restores_exact_record_without_inference_or_resaving(self):
        from services import mock_model
        aid = self.save()
        with patch.object(mock_model, 'predict', side_effect=AssertionError('No inference')) as predict, \
             patch.object(mock_model, 'explain', side_effect=AssertionError('No XAI')) as explain:
            app = self.app()
            app.button(key='hist_open').click().run()
            self.assertFalse(app.exception)
            self.assertEqual(app.session_state['saved_analysis_id'], aid)
            self.assertEqual(app.metric[0].value, 'SPOOF')
            self.assertEqual(app.metric[1].value, '91.0%')
            self.assertFalse(app.warning)
            predict.assert_not_called()
            explain.assert_not_called()
            app.button(key='saved_back').click().run()
            self.assertEqual(app.session_state['current_page'], 'history')
        self.assertEqual(len(db.list_analyses()), 1)

    def test_storage_failure_keeps_saved_result_and_shows_warning(self):
        self.save()
        app = self.app()
        with patch.object(self.local, 'download_bytes', side_effect=FileNotFoundError):
            app.button(key='hist_open').click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.metric[0].value, 'SPOOF')
        self.assertIn('original image could not be loaded', app.warning[0].value)
        self.assertFalse(app.get('imgs'))

    def test_hash_mismatch_never_displays_wrong_image(self):
        self.save()
        app = self.app()
        with patch.object(self.local, 'download_bytes', return_value=b'changed file'):
            app.button(key='hist_open').click().run()
        self.assertFalse(app.exception)
        self.assertIn('integrity check failed', app.error[0].value)
        self.assertEqual(app.metric[0].value, 'SPOOF')
        self.assertFalse(app.get('imgs'))

    def test_saved_xai_loaded_from_selected_analysis(self):
        aid = self.save()
        key = storage.heatmap_key(aid, 'gradcam')
        self.local.upload_bytes(key, self.image)
        db.record_xai(aid, 'gradcam', key, .7)
        app = self.app()
        app.button(key='hist_open').click().run()
        self.assertFalse(app.exception)
        self.assertTrue(any('Saved faithfulness: 0.700' in c.value for c in app.caption))
        self.assertEqual(len(app.get('imgs')), 2)

    def test_legacy_identity_does_not_deduplicate_by_filename(self):
        rows = [dict(analysis_id=str(i), image_hash='', image_s3_key=key,
                     image_filename='same.png')
                for i, key in enumerate(['one', 'one', 'two', '', ''])]
        self.assertEqual(len(persistence.latest_analyses_by_image(rows)), 4)

    def test_history_not_silently_truncated_at_200_records(self):
        for i in range(201):
            db.record_analysis('CASE-HISTORY', 'same.png', f'key-{i}',
                               'test', 'spoof', .9, image_hash=str(i))
        row, = persistence.list_history_from_db()
        self.assertEqual((row['count'], row['saved_count']), (201, 201))

    def test_saved_page_belongs_to_history_navigation(self):
        from nav import PAGE_SECTION
        self.assertEqual(PAGE_SECTION['saved_analysis'], 'history')


if __name__ == '__main__':
    unittest.main()
