# SPDX-FileCopyrightText: MyScreenDraw contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Project persistence helpers shared by autosave and user project files."""
from __future__ import annotations

import json
import math
import os
import re
import tempfile
from datetime import datetime
from typing import Any

SCHEMA_VERSION = 1
PROJECT_KIND = "myscreendraw-project"
AUTOSAVE_KIND = "myscreendraw-autosave"
MAX_PROJECT_BYTES = 64 * 1024 * 1024
MAX_PAGES = 1000
MAX_SEGMENTS_PER_PAGE = 100000
MAX_TEXTS_PER_PAGE = 10000
MAX_SHAPES_PER_PAGE = 10000
MAX_POLY_POINTS = 10000
MAX_TOTAL_POLY_POINTS = 200000
MAX_IMAGES_PER_PAGE = 500
MAX_IMAGE_DATA_BYTES = 8 * 1024 * 1024
MAX_ABS_COORD = 1_000_000.0
MAX_ID_LENGTH = 128
_COLOR_RE = re.compile(r"^#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")

POLY_POINT_COUNTS = {
    "LINE": 2,
    "DASHED_LINE": 2,
    "TRIANGLE": 3,
    "RECT": 4,
    "PARALLELOGRAM": 4,
    "TRAPEZOID": 4,
    "DIAMOND": 4,
}
RECT_TYPES = {"CUBE", "CUBOID", "CYLINDER", "CONE"}


def ensure_file_size(path: str, maximum: int = MAX_PROJECT_BYTES) -> None:
    """Reject an oversized project before json.load allocates it in memory."""
    try:
        size = os.path.getsize(path)
    except OSError:
        raise
    if size > maximum:
        raise ValueError(f"项目文件过大（上限 {maximum // (1024 * 1024)} MiB）")


def atomic_write_json(path: str, data: Any, *, indent: int = 2) -> None:
    """Write JSON durably, replacing the destination only after success."""
    directory = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(directory, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix="." + os.path.basename(path) + ".", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=indent, allow_nan=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def cleanup_temp_files(directory: str) -> int:
    removed = 0
    try:
        for name in os.listdir(directory):
            if name.endswith(".tmp") and name.startswith("."):
                try:
                    os.remove(os.path.join(directory, name))
                    removed += 1
                except OSError:
                    pass
    except OSError:
        pass
    return removed


def _finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _bounded_number(value: Any, low: float = -MAX_ABS_COORD, high: float = MAX_ABS_COORD) -> bool:
    return _finite_number(value) and low <= float(value) <= high


def _point(value: Any) -> bool:
    return isinstance(value, (list, tuple)) and len(value) == 2 and all(_bounded_number(v) for v in value)


def _color(value: Any) -> bool:
    return isinstance(value, str) and _COLOR_RE.fullmatch(value) is not None


def _valid_id(value: Any) -> bool:
    return value is None or isinstance(value, str) and 0 < len(value) <= MAX_ID_LENGTH


def _object_id(item: dict) -> str | None:
    value = item.get("id")
    return value if isinstance(value, str) else None


def validate_page_data(page: Any) -> tuple[bool, str]:
    if not isinstance(page, dict):
        return False, "页面必须是对象"
    for key in ("segments", "texts", "shapes", "images"):
        if not isinstance(page.get(key, []), list):
            return False, f"{key} 必须是数组"
    segments = page.get("segments", [])
    texts = page.get("texts", [])
    shapes = page.get("shapes", [])
    images = page.get("images", [])
    if (len(segments) > MAX_SEGMENTS_PER_PAGE or len(texts) > MAX_TEXTS_PER_PAGE
            or len(shapes) > MAX_SHAPES_PER_PAGE or len(images) > MAX_IMAGES_PER_PAGE):
        return False, "页面对象数量超出限制"

    # One stroke legitimately consists of many segments sharing an id. Texts and
    # shapes are individual objects, and ids may not alias another object class.
    stroke_ids: set[str] = set()
    object_ids: set[str] = set()
    for seg in segments:
        if not isinstance(seg, dict) or not _valid_id(seg.get("id")):
            return False, "笔迹 ID 无效"
        if not _point(seg.get("p1")) or not _point(seg.get("p2")):
            return False, "笔迹坐标无效"
        if not _color(seg.get("color", "#000000")) or not _bounded_number(seg.get("width", 1), 0.000001, 200):
            return False, "笔迹样式无效"
        object_id = _object_id(seg)
        if object_id:
            stroke_ids.add(object_id)

    for item in texts:
        if not isinstance(item, dict) or not _valid_id(item.get("id")):
            return False, "文本 ID 无效"
        if not isinstance(item.get("text", ""), str) or len(item.get("text", "")) > 100000:
            return False, "文本无效"
        if not _point(item.get("pos", [0, 0])) or not _color(item.get("color", "#000000")):
            return False, "文本位置或颜色无效"
        for key, low, high in (("width", 0, 200), ("size", 1, 500), ("scale", 0.01, 100), ("rotation", -36000, 36000)):
            default_value = 1 if key == "width" else 24 if key == "size" else 1 if key == "scale" else 0
            if not _bounded_number(item.get(key, default_value), low, high):
                return False, "文本数值无效或超出范围"
        object_id = _object_id(item)
        if object_id:
            if object_id in stroke_ids or object_id in object_ids:
                return False, "对象 ID 冲突"
            object_ids.add(object_id)

    total_poly_points = 0
    for item in shapes:
        if not isinstance(item, dict) or not _valid_id(item.get("id")):
            return False, "图形 ID 无效"
        if not _color(item.get("color", "#000000")):
            return False, "图形样式无效"
        object_id = _object_id(item)
        if object_id:
            if object_id in stroke_ids or object_id in object_ids:
                return False, "对象 ID 冲突"
            object_ids.add(object_id)
        kind = item.get("kind", "rect")
        shape_type = item.get("type", "RECT")
        if kind == "poly":
            points = item.get("points")
            if shape_type not in POLY_POINT_COUNTS or not isinstance(points, list):
                return False, "多边形类型或点无效"
            expected = POLY_POINT_COUNTS[shape_type]
            if len(points) != expected or len(points) > MAX_POLY_POINTS or not all(_point(p) for p in points):
                return False, "多边形点无效"
            closed = item.get("closed", shape_type not in ("LINE", "DASHED_LINE"))
            if not isinstance(closed, bool) or closed == (shape_type in ("LINE", "DASHED_LINE")):
                return False, "多边形闭合状态无效"
            total_poly_points += len(points)
            if total_poly_points > MAX_TOTAL_POLY_POINTS:
                return False, "多边形点总数超出限制"
        elif kind == "angle":
            if shape_type != "ANGLE" or not all(_point(item.get(k)) for k in ("vertex", "p1", "p2")):
                return False, "角的点无效"
        elif kind == "circle":
            if shape_type != "CIRCLE" or not _point(item.get("center")) or not _bounded_number(item.get("radius"), 0.000001, MAX_ABS_COORD):
                return False, "圆参数无效"
        elif kind == "ellipse":
            if (shape_type != "ELLIPSE" or not _point(item.get("center"))
                    or not _bounded_number(item.get("rx"), 0.000001, MAX_ABS_COORD)
                    or not _bounded_number(item.get("ry"), 0.000001, MAX_ABS_COORD)
                    or not _bounded_number(item.get("rotation", 0), -36000, 36000)):
                return False, "椭圆参数无效"
        elif kind == "rect":
            if shape_type not in RECT_TYPES:
                return False, "矩形图形类型无效"
            rect = item.get("rect")
            if not isinstance(rect, list) or len(rect) != 4 or not all(_bounded_number(v) for v in rect):
                return False, "矩形参数无效"
            x, y, width, height = (float(v) for v in rect)
            if width <= 0 or height <= 0 or not _bounded_number(x + width) or not _bounded_number(y + height):
                return False, "矩形参数无效"
            if not _bounded_number(item.get("rotation", 0), -36000, 36000):
                return False, "矩形旋转无效"
        else:
            return False, "未知图形类型"
        if not _bounded_number(item.get("width", 1), 0.000001, 200):
            return False, "图形粗细无效"

    # 图片：pos 为中心、size 为显示尺寸，data 为 base64 PNG（自包含内嵌）
    for item in images:
        if not isinstance(item, dict) or not _valid_id(item.get("id")):
            return False, "图片 ID 无效"
        object_id = _object_id(item)
        if object_id:
            if object_id in stroke_ids or object_id in object_ids:
                return False, "对象 ID 冲突"
            object_ids.add(object_id)
        if not _point(item.get("pos", [0, 0])):
            return False, "图片位置无效"
        size = item.get("size", [1, 1])
        if not (isinstance(size, list) and len(size) == 2
                and all(_bounded_number(value, 1.0, MAX_ABS_COORD) for value in size)):
            return False, "图片尺寸无效"
        if not _bounded_number(item.get("rotation", 0), -36000, 36000):
            return False, "图片旋转无效"
        data = item.get("data")
        if not isinstance(data, str) or not data or len(data) > MAX_IMAGE_DATA_BYTES:
            return False, "图片数据无效"
    return True, ""


def normalize_project_data(data: Any, *, kind: str | None = None) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("项目顶层必须是对象")
    pages = data.get("pages")
    if pages is None:
        if all(k in data for k in ("segments", "texts", "shapes")):
            pages = [data]
        else:
            raise ValueError("项目缺少 pages")
    if not isinstance(pages, list) or not pages or len(pages) > MAX_PAGES:
        raise ValueError("项目 pages 无效")
    for page in pages:
        ok, reason = validate_page_data(page)
        if not ok:
            raise ValueError(reason)
    current = data.get("current_page", 0)
    if not isinstance(current, int) or isinstance(current, bool):
        current = 0
    try:
        schema_version = int(data.get("schema_version", 1))
    except (TypeError, ValueError):
        schema_version = SCHEMA_VERSION
    if schema_version < 1 or schema_version > SCHEMA_VERSION:
        raise ValueError("项目格式版本不受支持")
    actual_kind = data.get("kind")
    expected_kind = kind
    if expected_kind is not None and actual_kind is not None and actual_kind != expected_kind:
        raise ValueError("项目类型不匹配")
    if actual_kind is not None and actual_kind not in (PROJECT_KIND, AUTOSAVE_KIND):
        raise ValueError("项目类型无效")
    return {
        "schema_version": schema_version,
        "kind": actual_kind or expected_kind or PROJECT_KIND,
        "app_version": data.get("app_version", ""),
        "saved_at": data.get("saved_at", ""),
        "timestamp": data.get("timestamp", ""),
        "whiteboard_mode": bool(data.get("whiteboard_mode", True)),
        "board_style": data.get("board_style") if data.get("board_style") in ("WHITE", "BLACK") else "WHITE",
        "current_page": max(0, min(len(pages) - 1, current)),
        "pages": pages,
        "metadata": data.get("metadata") if isinstance(data.get("metadata"), dict) else {},
    }


def make_project_data(*, pages: list[dict], current_page: int, whiteboard_mode: bool, board_style: str, app_version: str, metadata: dict | None = None, kind: str = PROJECT_KIND) -> dict[str, Any]:
    return {"schema_version": SCHEMA_VERSION, "kind": kind, "app_version": app_version, "saved_at": datetime.now().isoformat(timespec="seconds"), "whiteboard_mode": bool(whiteboard_mode), "board_style": board_style if board_style in ("WHITE", "BLACK") else "WHITE", "current_page": max(0, min(max(0, len(pages) - 1), int(current_page))), "pages": pages, "metadata": metadata or {}}
