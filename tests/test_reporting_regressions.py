"""Regression coverage for thesis defects DEF-19, DEF-20 and DEF-21.

Uses temporary SQLite/local objects and generated images; no operational data,
cloud calls, questionnaire responses or model-performance claims.
"""
import hashlib
import io
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from PIL import Image
from pypdf import PdfReader

from app.services import auth, database, persistence, storage
from app.components import audit
from app.utils.report_generator import build_report


class Session(dict):
    __getattr__ = dict.__getitem__
    __setattr__ = dict.__setitem__


class ReportingRegressionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='fsd_reporting_tests_')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.enterContext(patch.object(database, 'DATABASE_URL', ''))
        self.enterContext(patch.object(database, 'DB_PATH', self.root/'test.db'))
        self.enterContext(patch.dict(os.environ, {'FSDXAI_OFFLINE_MODE': '0'}))
        database.init_db()
        self.local = storage.LocalStorageService(self.root/'objects')
        self.enterContext(patch.object(storage, 'get_storage', return_value=self.local))
        self.session = Session()
        self.enterContext(patch.object(audit, 'st', SimpleNamespace(session_state=self.session)))
        self.enterContext(patch.object(auth, 'st', SimpleNamespace(session_state=self.session)))
        buffer = io.BytesIO()
        Image.new('RGB', (100, 100), 'gray').save(buffer, format='PNG')
        self.image = buffer.getvalue()
        self.meta = {'case_id': 'CASE-TEST', 'examiner': 'Examiner A',
                     'timestamp': '2026-10-01T00:00:00+00:00'}
        self.result = {'label': 'spoof', 'confidence': .87, 'threshold_used': .61,
                       'model': {'name': 'fixture-model', 'commit': 'fixture-reference',
                                 'checkpoint_short': 'fixture-run',
                                 'checkpoint_sha256': 'a'*64, 'version': 'test'}}

    def report_text(self, result=None):
        pdf = build_report(self.meta, self.result if result is None else result,
                           image_bytes=self.image)
        return ' '.join(' '.join(p.extract_text() or '' for p in
                                PdfReader(io.BytesIO(pdf)).pages).split())

    def save(self, examiner='Examiner A'):
        return persistence.save_single_analysis(
            filename='fixture.png', image_bytes=self.image,
            meta={**self.meta, 'examiner': examiner}, result=self.result)

    def test_report_uses_supplied_provenance_and_input_hash(self):
        text = self.report_text()
        for value in ('fixture-model', 'fixture-reference', 'fixture-run', 'a'*64,
                      hashlib.sha256(self.image).hexdigest(), '0.61'):
            self.assertIn(value, text)
        self.assertNotIn('ResNet50V2-CBAM', text)
        self.assertNotIn('a3f9b21', text)
        self.assertNotIn('LivDet 2013', text)

    def test_distinct_models_do_not_reuse_report_metadata(self):
        second = {**self.result, 'model': {'name': 'second-model', 'commit': 'second-reference'}}
        text = self.report_text(second)
        self.assertIn('second-model', text)
        self.assertIn('second-reference', text)
        self.assertNotIn('fixture-model', text)

    def test_missing_provenance_is_not_invented(self):
        for model in (None, {}, 'legacy-model'):
            with self.subTest(model=model):
                text = self.report_text({**self.result, 'model': model})
                self.assertIn('Not recorded', text)
                self.assertNotIn('a3f9b21', text)
                self.assertNotIn('LivDet 2013', text)

    def test_report_discloses_uncompleted_validation(self):
        text = self.report_text()
        self.assertNotIn('validated through expert survey', text.lower())
        self.assertIn('Practitioner validation has not been established', text)
        self.assertIn('does not establish legal admissibility', text)

    def test_audit_survives_revoked_session(self):
        self.session['current_user'] = {'user_id': 'deleted-user'}
        self.session['current_single'] = {'private': 'previous examiner'}
        audit.log_action('viewed')
        self.assertNotIn('current_single', self.session)
        self.assertEqual(self.session['audit_log'][0]['actor'], 'Unattributed')

    def test_failed_explanation_is_not_saved_as_evidence_heatmap(self):
        analysis_id = persistence.save_single_analysis(
            filename='fixture.png', image_bytes=self.image, meta=self.meta,
            result=self.result, xai_panels={'gradcam': {
                'status': 'error', 'image': self.image, 'faithfulness': 0.0}})
        self.assertIsNotNone(analysis_id)
        self.assertEqual(database.list_xai_for_analysis(analysis_id), [])

    def test_loaded_checkpoint_provenance_reaches_prediction_and_pdf(self):
        import torch
        from app.services import real_model
        from src.models import factory

        def tiny_model(*args, **kwargs):
            return torch.nn.Sequential(torch.nn.AdaptiveAvgPool2d(1),
                                       torch.nn.Flatten(), torch.nn.Linear(3, 1))

        checkpoint = self.root/'fixture_checkpoint'/'best.pth'
        checkpoint.parent.mkdir()
        torch.save(tiny_model().state_dict(), checkpoint)
        with patch.object(factory, 'get_model', side_effect=tiny_model), \
             patch.object(torch.cuda, 'is_available', return_value=False):
            service = real_model._load_model.__wrapped__('resnet50', str(checkpoint))
        with patch.object(real_model, 'get_service_info', return_value=service):
            prediction = real_model.predict('fixture.png', Image.open(io.BytesIO(self.image)))
        expected_hash = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
        self.assertEqual(prediction['model']['checkpoint_sha256'], expected_hash)
        self.assertEqual(prediction['model']['checkpoint_short'], 'fixture_checkpoint')
        self.assertEqual(prediction['threshold_used'], .5)
        text = self.report_text(prediction)
        self.assertIn(expected_hash, text)
        self.assertIn('fixture_checkpoint', text)

    def test_analysis_audit_records_actor_action_and_time(self):
        analysis_id = self.save()
        self.assertIsNotNone(analysis_id)
        events = database.get_audit_trail(analysis_id=analysis_id)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['user'], 'Examiner A')
        self.assertEqual(events[0]['action'], 'analysed')
        self.assertTrue(events[0]['created_at'])

    def test_existing_case_does_not_override_new_analysis_actor(self):
        self.save('Examiner A')
        analysis_id = self.save('Examiner B')
        self.assertEqual(database.get_case(self.meta['case_id'])['examiner'], 'Examiner A')
        self.assertEqual(database.get_audit_trail(analysis_id=analysis_id)[0]['user'], 'Examiner B')

    def test_batch_audits_each_analysis_actor(self):
        ids = persistence.save_batch_analyses(
            meta=self.meta, files=[('a.png', self.image), ('b.png', self.image)],
            results=[self.result, self.result])
        self.assertEqual(len(ids), 2)
        for analysis_id in ids:
            self.assertEqual(database.get_audit_trail(analysis_id=analysis_id)[0]['user'], 'Examiner A')

    def test_missing_actor_is_explicitly_unattributed(self):
        analysis_id = self.save(None)
        self.assertIsNotNone(analysis_id)
        self.assertEqual(database.get_audit_trail(analysis_id=analysis_id)[0]['user'], 'Unattributed')

    def test_ui_audit_uses_current_account_not_stale_form_name(self):
        user_id = database.create_user('current', 'unused-test-hash', 'examiner', 'Current Examiner')
        self.session.update(current_user={'user_id': user_id, 'session_version': 0}, form_examiner='Previous Examiner')
        audit.log_action('Viewed result', case_id=self.meta['case_id'])
        self.assertEqual(self.session.audit_log[-1]['actor'], 'Current Examiner')
        self.assertEqual(database.get_audit_trail(case_id=self.meta['case_id'])[0]['user'], 'Current Examiner')

    def test_ui_audit_does_not_invent_system_actor(self):
        self.session['form_examiner'] = 'Previous Examiner'
        audit.log_action('Viewed result', case_id=self.meta['case_id'])
        self.assertEqual(self.session.audit_log[-1]['actor'], 'Unattributed')

    def test_explicit_actor_remains_supported(self):
        audit.log_action('Maintenance', actor='Maintenance job')
        self.assertEqual(self.session.audit_log[-1]['actor'], 'Maintenance job')


if __name__ == '__main__':
    unittest.main()
