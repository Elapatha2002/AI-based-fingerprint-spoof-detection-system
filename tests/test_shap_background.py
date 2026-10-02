import hashlib
import io
import json
import unittest

from PIL import Image

from src.xai.shap_background import ShapBackgroundError, load_fixed_background


class _MemoryStorage:
    def __init__(self, objects):
        self.objects = objects

    def download_bytes(self, key):
        return self.objects[key]


def _png(value):
    output = io.BytesIO()
    Image.new("RGB", (32, 32), (value, value, value)).save(output, format="PNG")
    return output.getvalue()


class FixedShapBackgroundTests(unittest.TestCase):
    def _fixture(self):
        prefix = "shap-background/test"
        objects = {}
        images = []
        for index in range(8):
            data = _png(index * 20)
            key = f"{prefix}/{index}.png"
            objects[key] = data
            images.append({
                "object_key": key,
                "sha256": hashlib.sha256(data).hexdigest(),
                "label": "live" if index < 4 else "spoof",
            })
        manifest = {"schema_version": 1, "prefix": prefix, "images": images}
        objects[f"{prefix}/manifest.json"] = json.dumps(manifest).encode()
        return prefix, objects

    def test_loads_balanced_verified_background(self):
        prefix, objects = self._fixture()
        tensor, manifest = load_fixed_background(
            8, storage_service=_MemoryStorage(objects), prefix=prefix
        )
        self.assertEqual(tuple(tensor.shape), (8, 3, 224, 224))
        self.assertEqual(len(manifest["images"]), 8)

    def test_rejects_modified_background_object(self):
        prefix, objects = self._fixture()
        objects[f"{prefix}/0.png"] = _png(255)
        with self.assertRaisesRegex(ShapBackgroundError, "integrity check failed"):
            load_fixed_background(8, storage_service=_MemoryStorage(objects), prefix=prefix)


if __name__ == "__main__":
    unittest.main()
