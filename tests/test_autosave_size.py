"""Autosave on disk: gzip, a 72-hour retention window, and no duplicate writes.

An autosave is a whole-page snapshot -- one object per line segment, each carrying
its own pen description and a 36-char UUID. That is extremely repetitive text, so
gzip shrinks pure-ink pages by roughly 97%. Pages holding an imported image do NOT
shrink much: the payload is base64 PNG, already compressed. Both cases are pinned
below so the difference does not get mistaken for a regression later.
"""
import gzip
import json
import os
import sys
import time
import unittest
from datetime import datetime, timedelta
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import persistence


class GzipWriterTests(unittest.TestCase):
    def setUp(self):
        import tempfile

        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        import shutil

        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_gz_round_trips(self):
        path = os.path.join(self.tmp, "a.json.gz")
        payload = {"pages": [{"segments": [{"id": "x", "line": [1, 2, 3, 4]}]}], "汉字": "值"}
        persistence.atomic_write_json_gz(path, payload)
        self.assertEqual(persistence.read_json_maybe_gz(path), payload)

    def test_plain_json_still_reads(self):
        """5.2.2 之前写的 autosave 是未压缩的，升级后必须还能恢复。"""
        path = os.path.join(self.tmp, "a.json")
        persistence.atomic_write_json(path, {"k": 1})
        self.assertEqual(persistence.read_json_maybe_gz(path), {"k": 1})

    def test_gz_is_actually_gzip(self):
        path = os.path.join(self.tmp, "a.json.gz")
        persistence.atomic_write_json_gz(path, {"k": "v"})
        with open(path, "rb") as handle:
            self.assertEqual(handle.read(2), b"\x1f\x8b", "不是 gzip 流")

    def test_repetitive_ink_compresses_hard(self):
        """笔迹型页面：每段带自己的 pen 和 id，重复度极高。"""
        segments = [{"id": "stroke-%d" % (i // 200),
                     "line": [i, 100, i + 3, 101],
                     "pen": {"color": "#ff4757", "width": 4, "style": 1},
                     "marker": False} for i in range(4000)]
        data = {"pages": [{"segments": segments, "texts": [], "shapes": [], "images": []}]}
        plain = os.path.join(self.tmp, "p.json")
        packed = os.path.join(self.tmp, "p.json.gz")
        persistence.atomic_write_json(plain, data)
        persistence.atomic_write_json_gz(packed, data)
        ratio = os.path.getsize(packed) / os.path.getsize(plain)
        self.assertLess(ratio, 0.15, "笔迹应压到原来的 15%% 以下，实际 %.1f%%" % (ratio * 100))

    def test_embedded_image_does_not_compress(self):
        """内嵌图片是 base64 PNG，本身已压缩——这里压不动是预期，不是 bug。

        实测你机器上那份 6.84MB 的 autosave 有 99.8% 是一张图片，只压掉 24.7%。
        写下这条是为了让将来看到「压缩率很低」的人知道原因在哪，不要去调 gzip 等级。
        """
        import base64
        import random

        rng = random.Random(4)
        noise = bytes(rng.randrange(256) for _ in range(200000))   # 不可压缩
        blob = base64.b64encode(noise).decode("ascii")
        data = {"pages": [{"segments": [], "texts": [], "shapes": [],
                           "images": [{"id": "i", "data": blob}]}]}
        plain = os.path.join(self.tmp, "i.json")
        packed = os.path.join(self.tmp, "i.json.gz")
        persistence.atomic_write_json(plain, data)
        persistence.atomic_write_json_gz(packed, data)
        ratio = os.path.getsize(packed) / os.path.getsize(plain)
        self.assertGreater(ratio, 0.5, "已压缩的图片数据不该被压掉一半以上")

    def test_identical_content_yields_identical_bytes(self):
        """mtime=0：同样的内容必须产出同样的字节，否则无法靠比对判断内容变了。"""
        a = os.path.join(self.tmp, "a.json.gz")
        b = os.path.join(self.tmp, "b.json.gz")
        payload = {"pages": [{"segments": [{"id": "x"}]}]}
        persistence.atomic_write_json_gz(a, payload)
        time.sleep(0.05)
        persistence.atomic_write_json_gz(b, payload)
        with open(a, "rb") as fa, open(b, "rb") as fb:
            self.assertEqual(fa.read(), fb.read())


class AutosaveCase(unittest.TestCase):
    """Shared fixture. Not a test collection itself -- subclassing a TestCase that
    already holds tests would run every inherited test again under each subclass."""

    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])
        import main

        cls.main = main

    def setUp(self):
        import shutil
        import tempfile

        self.tmp = tempfile.mkdtemp()
        self._original_dir = self.main.AUTOSAVE_DIR
        self.main.AUTOSAVE_DIR = self.tmp       # 绝不碰用户真实的 autosave 目录
        self.addCleanup(setattr, self.main, "AUTOSAVE_DIR", self._original_dir)
        self.addCleanup(shutil.rmtree, self.tmp, True)
        try:
            self.panel = self.main.ControlPanel()
        except Exception as exc:        # pragma: no cover - no display / no input hook
            self.skipTest(f"cannot build ControlPanel: {exc}")
        self.canvas = self.main.DrawingCanvas(self.panel)
        self.panel.canvas = self.canvas
        self.addCleanup(self.stop_timers)

    def stop_timers(self):
        for name in ("listener", "timer", "autosave_timer", "_thumbnail_live_timer"):
            try:
                getattr(self.panel, name).stop()
            except Exception:
                pass

    def make_autosave(self, when, name_suffix=".json.gz"):
        stamp = when.strftime("%Y%m%d_%H%M%S")
        path = os.path.join(self.tmp, f"autosave_{stamp}{name_suffix}")
        payload = {"pages": [{"segments": [], "texts": [], "shapes": [], "images": []}]}
        if name_suffix.endswith(".gz"):
            persistence.atomic_write_json_gz(path, payload)
        else:
            persistence.atomic_write_json(path, payload)
        return path

    def names(self):
        return sorted(os.listdir(self.tmp))


class AutosaveRetentionTests(AutosaveCase):
    def test_files_inside_the_window_survive(self):
        now = datetime.now()
        recent = [self.make_autosave(now - timedelta(hours=h)) for h in (0, 1, 24, 71)]
        self.panel._cleanup_autosave_files()
        for path in recent:
            self.assertTrue(os.path.exists(path),
                            f"{os.path.basename(path)} 在 72 小时内，不该被删")

    def test_files_past_the_window_are_removed(self):
        now = datetime.now()
        self.make_autosave(now)                                  # 最新，保留
        old = [self.make_autosave(now - timedelta(hours=h)) for h in (73, 100, 500)]
        self.panel._cleanup_autosave_files()
        for path in old:
            self.assertFalse(os.path.exists(path),
                             f"{os.path.basename(path)} 超过 72 小时，应被删")

    def test_the_newest_file_survives_even_when_ancient(self):
        """隔一周回来打开，也该有东西可恢复，而不是被清空。"""
        old = self.make_autosave(datetime.now() - timedelta(days=30))
        self.panel._cleanup_autosave_files()
        self.assertTrue(os.path.exists(old), "最新一份永远要留着")

    def test_a_count_ceiling_bounds_the_directory(self):
        """光按时间不够：每 30 秒一份，72 小时是 8640 份。"""
        now = datetime.now()
        for i in range(30):
            self.make_autosave(now - timedelta(seconds=i * 30))
        self.panel._cleanup_autosave_files(keep_max=10)
        self.assertLessEqual(len(self.names()), 10)

    def test_the_window_is_seventy_two_hours(self):
        self.assertEqual(self.panel.AUTOSAVE_KEEP_HOURS, 72)

    def test_creation_time_comes_from_the_filename(self):
        """按文件名里的时间戳判断，而不是 mtime——mtime 会被复制/同步工具改写。"""
        path = self.make_autosave(datetime(2020, 5, 4, 3, 2, 1))
        os.utime(path, None)        # 把 mtime 改成现在，模拟被工具碰过
        got = datetime.fromtimestamp(self.panel._autosave_created_at(path))
        self.assertEqual((got.year, got.month, got.day), (2020, 5, 4),
                         "应采用文件名里的时间，不受 mtime 影响")

    def test_legacy_plain_json_is_still_listed_and_cleaned(self):
        now = datetime.now()
        self.make_autosave(now)
        legacy = self.make_autosave(now - timedelta(hours=200), name_suffix=".json")
        listed = [p for _, p in self.panel._list_autosave_files()]
        self.assertIn(legacy, listed, "旧的未压缩 autosave 也要能被枚举到")
        self.panel._cleanup_autosave_files()
        self.assertFalse(os.path.exists(legacy))


class AutosaveWriteTests(AutosaveCase):
    def draw_something(self):
        from PyQt6.QtCore import QLine
        from PyQt6.QtGui import QPen

        self.canvas.all_segments = [
            {"line": QLine(10, 10, 20 + i, 20), "pen": QPen(), "id": "s", "marker": False}
            for i in range(5)
        ]

    def test_autosave_writes_a_gzip_file(self):
        self.draw_something()
        self.panel._last_autosave_signature = None
        self.panel.auto_save()
        produced = [n for n in self.names() if n.endswith(".json.gz")]
        self.assertTrue(produced, f"未写出 .json.gz，目录内容: {self.names()}")

    def test_unchanged_content_does_not_write_again(self):
        """内容没变就不该再落一份，否则一节课不动画布也会堆满目录。"""
        self.draw_something()
        self.panel._last_autosave_signature = None
        self.panel.auto_save()
        first = self.names()
        self.panel.auto_save()
        self.assertEqual(self.names(), first, "内容未变却又写了一份")

    def test_changed_content_writes_again(self):
        from PyQt6.QtCore import QLine
        from PyQt6.QtGui import QPen

        self.draw_something()
        self.panel._last_autosave_signature = None
        self.panel.auto_save()
        before = len(self.names())
        self.canvas.all_segments.append(
            {"line": QLine(99, 99, 120, 130), "pen": QPen(), "id": "t", "marker": False})
        self.panel.auto_save()
        self.assertGreater(len(self.names()), before, "内容变了必须落新的一份")

    def test_what_was_written_can_be_restored(self):
        self.draw_something()
        self.panel._last_autosave_signature = None
        self.panel.auto_save()
        path, data = self.panel._latest_restorable_autosave()
        self.assertIsNotNone(path, "写出的 autosave 必须能被读回")
        self.assertTrue(data.get("pages"))

    def test_a_blank_canvas_writes_nothing(self):
        self.canvas.all_segments = []
        self.canvas.shape_items = []
        self.canvas.text_items = []
        self.canvas.image_items = []
        self.panel._last_autosave_signature = None
        self.panel.auto_save()
        self.assertEqual([n for n in self.names() if n.startswith("autosave_")], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
