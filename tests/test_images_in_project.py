"""Image object model tests: persistence validation + base64 serialize/deserialize roundtrip."""
import base64
import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from persistence import (validate_page_data, MAX_IMAGES_PER_PAGE, MAX_IMAGE_DATA_BYTES)


def _valid_image(**overrides):
    item = {
        "id": "img-1",
        "pos": [100.0, 200.0],
        "size": [40.0, 30.0],
        "rotation": 0.0,
        "data": base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\x00" * 16).decode("ascii"),
    }
    item.update(overrides)
    return {"segments": [], "texts": [], "shapes": [], "images": [item]}


class ImageValidationTests(unittest.TestCase):
    def test_valid_image_accepted(self):
        ok, reason = validate_page_data(_valid_image())
        self.assertTrue(ok, reason)

    def test_old_page_without_images_key_is_still_valid(self):
        page = {"segments": [], "texts": [], "shapes": []}
        ok, reason = validate_page_data(page)
        self.assertTrue(ok, reason)

    def test_too_many_images_rejected(self):
        page = {
            "segments": [], "texts": [], "shapes": [],
            "images": [dict(_valid_image()["images"][0], id=f"img-{i}") for i in range(MAX_IMAGES_PER_PAGE + 1)],
        }
        ok, _ = validate_page_data(page)
        self.assertFalse(ok)

    def test_oversized_image_data_rejected(self):
        page = _valid_image(data="A" * (MAX_IMAGE_DATA_BYTES + 1))
        ok, _ = validate_page_data(page)
        self.assertFalse(ok)

    def test_non_string_image_data_rejected(self):
        ok, _ = validate_page_data(_valid_image(data=12345))
        self.assertFalse(ok)

    def test_empty_image_data_rejected(self):
        ok, _ = validate_page_data(_valid_image(data=""))
        self.assertFalse(ok)

    def test_bad_position_rejected(self):
        ok, _ = validate_page_data(_valid_image(pos=[float("nan"), 0]))
        self.assertFalse(ok)

    def test_bad_size_rejected(self):
        ok, _ = validate_page_data(_valid_image(size=[0, 10]))   # 宽不能为 0
        self.assertFalse(ok)

    def test_bad_rotation_rejected(self):
        ok, _ = validate_page_data(_valid_image(rotation=999999))
        self.assertFalse(ok)

    def test_duplicate_id_with_stroke_rejected(self):
        page = _valid_image(id="shared")
        page["segments"] = [{"id": "shared", "p1": [0, 0], "p2": [1, 1], "color": "#000000", "width": 1}]
        ok, _ = validate_page_data(page)
        self.assertFalse(ok)


class ImageRoundTripTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])
        import main
        cls.main = main

    def test_serialize_and_deserialize_preserve_geometry(self):
        from PyQt6.QtGui import QColor, QPixmap
        pixmap = QPixmap(8, 6)
        pixmap.fill(QColor("#ff0000"))
        item = {
            "id": "img-x",
            "pos": self.main.QPointF(10.0, 20.0),
            "size": self.main.QSizeF(80.0, 60.0),
            "rotation": 15.0,
            "pixmap": pixmap,
        }
        data = self.main.serialize_image(item)
        self.assertEqual(data["id"], "img-x")
        self.assertTrue(data["data"], "PNG base64 不应为空")
        restored = self.main.deserialize_image(data)
        self.assertEqual(str(restored["id"]), "img-x")
        self.assertEqual(restored["pos"].x(), 10.0)
        self.assertEqual(restored["size"].width(), 80.0)
        self.assertEqual(restored["rotation"], 15.0)
        self.assertFalse(restored["pixmap"].isNull())

    def test_deserialize_guards_garbage_base64(self):
        item = {"id": "bad", "pos": [0, 0], "size": [10, 10], "rotation": 0, "data": "not-base64!!!"}
        restored = self.main.deserialize_image(item)
        self.assertTrue(restored["pixmap"].isNull())   # 解码失败 → 空图，不崩溃

    def test_decode_image_pixels_packs_padded_rgb_rows(self):
        from PyQt6.QtCore import QBuffer, QIODevice
        from PyQt6.QtGui import QColor, QImage

        # RGB888 aligns every row to four bytes. A one-pixel-wide image has one
        # trailing padding byte per row, which EPS must not receive.
        image = QImage(1, 2, QImage.Format.Format_RGB888)
        image.setPixelColor(0, 0, QColor(255, 0, 0))
        image.setPixelColor(0, 1, QColor(0, 255, 0))
        buffer = QBuffer()
        self.assertTrue(buffer.open(QIODevice.OpenModeFlag.WriteOnly))
        self.assertTrue(image.save(buffer, "PNG"))
        encoded = base64.b64encode(bytes(buffer.data())).decode("ascii")
        buffer.close()

        self.assertEqual(
            self.main.decode_image_pixels(encoded),
            (1, 2, b"\xff\x00\x00\x00\xff\x00"),
        )

    def test_full_page_roundtrip_with_image(self):
        page = {
            "segments": [], "texts": [], "shapes": [],
            "images": [{
                "id": "img-p",
                "pos": self.main.QPointF(5.0, 5.0),
                "size": self.main.QSizeF(30.0, 20.0),
                "rotation": 0.0,
                "pixmap": self.main.QPixmap(4, 4),
            }],
        }
        serialized = self.main.serialize_page(page)
        self.assertEqual(len(serialized["images"]), 1)
        self.assertTrue(serialized["images"][0]["data"])
        restored = self.main.deserialize_page(serialized)
        self.assertEqual(len(restored["images"]), 1)
        self.assertEqual(restored["images"][0]["size"].width(), 30.0)

    def test_serialize_page_without_images_is_compatible(self):
        page = {"segments": [], "texts": [], "shapes": []}
        serialized = self.main.serialize_page(page)
        self.assertEqual(serialized["images"], [])


if __name__ == "__main__":
    unittest.main()