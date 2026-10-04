"""Missing optional explainers must not take down the result page."""
import builtins
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from PIL import Image
from app.services import real_model


class ExplainerDependencyTests(unittest.TestCase):
    def test_all_registered_model_families_have_gradcam_target_layers(self):
        from src.xai.base import get_target_layer

        resnet_target = object()
        mobile_target = object()
        resnet = SimpleNamespace(layer4=[resnet_target])
        mobile = SimpleNamespace(features=[mobile_target])

        for name in ("resnet50", "resnet50_cbam", "fsd_cbam"):
            with self.subTest(model=name):
                self.assertIs(get_target_layer(resnet, name), resnet_target)
        for name in ("mobilenetv3_large", "mobilenetv3_small",
                     "mobilenet_fsd_cbam"):
            with self.subTest(model=name):
                self.assertIs(get_target_layer(mobile, name), mobile_target)

    def test_failed_panel_displays_error_not_numeric_metrics(self):
        from app.components import xai_views
        ui = Mock()
        with patch.object(xai_views, 'st', ui):
            xai_views._single_panel({'status': 'error', 'error': 'Missing package'},
                                   'Grad-CAM++', None, 'legend')
        ui.error.assert_called_once()
        ui.columns.assert_not_called()

    def test_incomplete_explanations_do_not_claim_agreement(self):
        from app.components import xai_interpretation
        ui = Mock()
        with patch.object(xai_interpretation, 'st', ui):
            xai_interpretation.render_xai_interpretation({'gradcam': {'status': 'error'}}, 'live', .1)
        ui.warning.assert_called_once()
        ui.markdown.assert_not_called()

    def test_each_missing_import_is_isolated_from_other_methods(self):
        mapping = {'gradcam': 'gradcam', 'shap_explainer': 'shap', 'lime_explainer': 'lime'}
        original_import = builtins.__import__
        for unavailable, panel_key in mapping.items():
            with self.subTest(unavailable=unavailable):
                explainers = {name: SimpleNamespace(explain=Mock(return_value=name)) for name in mapping}
                def importer(name, globals=None, locals=None, fromlist=(), level=0):
                    if name == 'src.xai':
                        if unavailable in fromlist:
                            raise ModuleNotFoundError('Missing test dependency', name='fixture_missing_package')
                        return SimpleNamespace(**explainers)
                    return original_import(name, globals, locals, fromlist, level)
                with patch.object(builtins, '__import__', side_effect=importer), \
                        patch.object(real_model, 'get_service_info', return_value={'model': object(), 'device': 'cpu', 'name': 'fixture'}), \
                        patch.object(real_model, '_panel_from_result', side_effect=lambda r, **kw: {'summary':r}):
                    panels = real_model.explain('fixture.png', Image.new('RGB', (100,100)))
                self.assertEqual(panels[panel_key]['status'], 'error')
                self.assertIn('Missing test dependency', panels[panel_key]['error'])
                for name, key in mapping.items():
                    if name != unavailable:
                        explainers[name].explain.assert_called_once()
                        self.assertNotIn('status', panels[key])


if __name__ == '__main__':
    unittest.main()
