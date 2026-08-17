# SPDX-FileCopyrightText: MyScreenDraw contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Vector EPS (PostScript Level-2) export for MyScreenDraw pages.

EPS 本质是 PostScript。本模块把「序列化页面」（`serialize_page` 的输出格式）翻译成
矢量 PostScript 命令，供导出菜单的 EPS 选项使用。模块不含任何 Qt 依赖，便于单测。

已知局限（已写入导出说明与 README）：
- EPS 无 alpha：荧光笔等半透明色按白/黑板背景预乘成实色；
- 文本使用标准字体 Helvetica：拉丁字符正常，含中文字符的文本在缺少 CJK 字体的
  查看器中可能显示为占位/缺字；
- 导入的位图以 `colorimage` 运算符嵌入（EPS 无法把照片转成矢量）。
"""
from __future__ import annotations

import math


def _fmt(value: object) -> str:
    """PostScript 数字格式：去掉无意义的小数尾零。"""
    number = float(value)
    if number == int(number) and abs(number) < 1e15:
        return str(int(number))
    return repr(number)


def _ps_text(text: object) -> str:
    """PostScript 字符串字面量：转义 \\ ( )，非 latin-1 字符替换为 '?'。"""
    out = []
    for char in str(text):
        if char in ("\\", "(", ")"):
            out.append("\\" + char)
        elif ord(char) < 256:
            out.append(char)
        else:
            out.append("?")
    return "".join(out)


def _parse_color(value: object):
    """'#RRGGBB' 或 '#AARRGGBB' → (r, g, b, alpha) 0..1。"""
    text = str(value).lstrip("#")
    try:
        if len(text) == 8:
            alpha = int(text[0:2], 16) / 255.0
            return (int(text[2:4], 16) / 255.0,
                    int(text[4:6], 16) / 255.0,
                    int(text[6:8], 16) / 255.0,
                    alpha)
        return (int(text[0:2], 16) / 255.0,
                int(text[2:4], 16) / 255.0,
                int(text[4:6], 16) / 255.0,
                1.0)
    except (TypeError, ValueError):
        return (0.0, 0.0, 0.0, 1.0)


def _background(board_style: str):
    """白/黑板背景色（与 main.py 的 board_background 一致）。"""
    if board_style == "BLACK":
        return (0.145, 0.259, 0.216)   # #254237
    return (0.969, 0.969, 0.945)       # #f7f7f1


def _blend_color(value: object, board_style: str):
    """颜色按 alpha 预乘到背景色上，得到 EPS 可用的不透明 RGB。"""
    r, g, b, alpha = _parse_color(value)
    if alpha >= 1.0:
        return (r, g, b)
    br, bg, bb = _background(board_style)
    return (r * alpha + br * (1.0 - alpha),
            g * alpha + bg * (1.0 - alpha),
            b * alpha + bb * (1.0 - alpha))


def _rotate(pt, cx: float, cy: float, phi_deg: float):
    """绕 (cx, cy) 旋转 Qt 坐标点（Qt 正角度 = y 向下空间的逆时针）。"""
    phi = math.radians(phi_deg)
    c, s = math.cos(phi), math.sin(phi)
    dx, dy = pt[0] - cx, pt[1] - cy
    return (cx + dx * c - dy * s, cy + dx * s + dy * c)


def _sample_arc(center, radius: float, a1: float, span: float, n: int = 36):
    """按 Qt drawArc 的角度约定采样一段弧（y 向下，正角度逆时针）。"""
    pts = []
    for i in range(n + 1):
        theta = math.radians(a1 + span * i / n)
        pts.append((center[0] + radius * math.cos(theta),
                    center[1] + radius * math.sin(theta)))
    return pts


def _sample_ellipse(center, rx: float, ry: float, rotation: float = 0.0, n: int = 48):
    """采样一个椭圆轮廓（含旋转），返回 Qt 坐标点序列。"""
    cx, cy = center
    phi = math.radians(rotation)
    c, s = math.cos(phi), math.sin(phi)
    pts = []
    for i in range(n + 1):
        theta = 2.0 * math.pi * i / n
        lx = rx * math.cos(theta)
        ly = ry * math.sin(theta)
        pts.append((cx + lx * c - ly * s, cy + lx * s + ly * c))
    return pts


def _emit_path(L, pts, height: int, *, closed: bool, color, width: float, dashed: bool = False):
    """把 Qt 坐标点序列画成一条 PostScript 折线/多边形。"""
    if len(pts) < 2:
        return
    L.append(f"{_fmt(color[0])} {_fmt(color[1])} {_fmt(color[2])} setrgbcolor")
    L.append(f"{_fmt(width)} setlinewidth")
    L.append("1 setlinecap")
    L.append("1 setlinejoin")
    L.append("[8 6] 0 setdash" if dashed else "[] 0 setdash")
    x, y = pts[0]
    L.append(f"{_fmt(x)} {_fmt(height - y)} moveto")
    for px, py in pts[1:]:
        L.append(f"{_fmt(px)} {_fmt(height - py)} lineto")
    if closed and len(pts) > 2:
        L.append("closepath")
    L.append("stroke")


def _emit_segment(L, seg, height: int, board_style: str):
    p1, p2 = seg["p1"], seg["p2"]
    color = _blend_color(seg.get("color", "#000000"), board_style)
    width = max(1.0, float(seg.get("width", 1)))
    L.append(f"{_fmt(color[0])} {_fmt(color[1])} {_fmt(color[2])} setrgbcolor")
    L.append(f"{_fmt(width)} setlinewidth")
    L.append("1 setlinecap")
    L.append("1 setlinejoin")
    L.append("[] 0 setdash")
    L.append(f"{_fmt(p1[0])} {_fmt(height - p1[1])} moveto")
    L.append(f"{_fmt(p2[0])} {_fmt(height - p2[1])} lineto")
    L.append("stroke")


def _emit_shape(L, item, height: int, board_style: str):
    kind = item.get("kind", "rect")
    color = _blend_color(item.get("color", "#000000"), board_style)
    width = max(1.0, float(item.get("width", 1)))
    if kind == "poly":
        pts = item.get("points", [])
        closed = bool(item.get("closed", False))
        dashed = item.get("type") == "DASHED_LINE"
        _emit_path(L, pts, height, closed=closed, color=color, width=width, dashed=dashed)
        return
    if kind == "angle":
        v, p1, p2 = item["vertex"], item["p1"], item["p2"]
        _emit_path(L, [v, p1], height, closed=False, color=color, width=width)
        _emit_path(L, [v, p2], height, closed=False, color=color, width=width)
        len1 = math.hypot(p1[0] - v[0], p1[1] - v[1])
        len2 = math.hypot(p2[0] - v[0], p2[1] - v[1])
        radius = max(14.0, min(40.0, 0.35 * min(len1, len2)))
        a1 = math.degrees(math.atan2(-(p1[1] - v[1]), p1[0] - v[0]))
        a2 = math.degrees(math.atan2(-(p2[1] - v[1]), p2[0] - v[0]))
        span = (a2 - a1) % 360.0
        if span > 180.0:
            span -= 360.0
        _emit_path(L, _sample_arc(v, radius, a1, span), height,
                   closed=False, color=color, width=1.5)
        mid = math.radians(a1 + span / 2.0)
        tx = v[0] + (radius + 15) * math.cos(mid)
        ty = v[1] - (radius + 15) * math.sin(mid)
        _emit_text_at(L, tx, ty, f"{abs(round(span))}°", 10.0, color, height)
        return
    if kind == "circle":
        c, r = item["center"], float(item["radius"])
        _emit_path(L, _sample_arc(c, r, 0.0, 360.0), height, closed=True, color=color, width=width)
        return
    if kind == "ellipse":
        c = item["center"]
        rx, ry = float(item["rx"]), float(item["ry"])
        rot = float(item.get("rotation", 0.0))
        _emit_path(L, _sample_ellipse(c, rx, ry, rot), height, closed=True, color=color, width=width)
        return
    # 立体图形：与 main.py 的 draw_shape_item 相同的几何，逐条线输出
    rect = item.get("rect")
    if not isinstance(rect, (list, tuple)) or len(rect) != 4:
        return
    x, y, w, h = (float(value) for value in rect)
    if w <= 0 or h <= 0:
        return
    rot = float(item.get("rotation", 0.0))
    cx, cy = x + w / 2.0, y + h / 2.0
    shape_type = item.get("type", "CUBE")
    if shape_type == "CUBE":
        offset = min(w, h) * 0.18
        front = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
        back = [(x + offset, y - offset), (x + w + offset, y - offset),
                (x + w + offset, y + h - offset), (x + offset, y + h - offset)]
        _emit_path(L, [_rotate(p, cx, cy, rot) for p in front], height, closed=True, color=color, width=width)
        _emit_path(L, [_rotate(p, cx, cy, rot) for p in back], height, closed=True, color=color, width=width)
        for a, b in zip(front, back):
            _emit_path(L, [_rotate(a, cx, cy, rot), _rotate(b, cx, cy, rot)], height,
                       closed=False, color=color, width=width)
    elif shape_type == "CUBOID":
        offset = min(w, h) * 0.2
        front = [(x, y + offset), (x + w - offset, y + offset),
                 (x + w - offset, y + h), (x, y + h)]
        back = [(x + offset, y), (x + w, y),
                (x + w, y + h - offset), (x + offset, y + h - offset)]
        _emit_path(L, [_rotate(p, cx, cy, rot) for p in front], height, closed=True, color=color, width=width)
        _emit_path(L, [_rotate(p, cx, cy, rot) for p in back], height, closed=True, color=color, width=width)
        for a, b in zip(front, back):
            _emit_path(L, [_rotate(a, cx, cy, rot), _rotate(b, cx, cy, rot)], height,
                       closed=False, color=color, width=width)
    elif shape_type == "CYLINDER":
        hh = h * 0.2
        top = _sample_ellipse((x + w / 2.0, y + hh / 2.0), w / 2.0, hh / 2.0)
        bottom = _sample_ellipse((x + w / 2.0, y + h - hh / 2.0), w / 2.0, hh / 2.0)
        _emit_path(L, [_rotate(p, cx, cy, rot) for p in top], height, closed=True, color=color, width=width)
        _emit_path(L, [_rotate(p, cx, cy, rot) for p in bottom], height, closed=True, color=color, width=width)
        for sx in (x, x + w):
            a = (sx, y + hh / 2.0)
            b = (sx, y + h - hh / 2.0)
            _emit_path(L, [_rotate(a, cx, cy, rot), _rotate(b, cx, cy, rot)], height,
                       closed=False, color=color, width=width)
    else:  # CONE
        hh = h * 0.22
        apex = (x + w / 2.0, y)
        left = (x, y + h - hh / 2.0)
        right = (x + w, y + h - hh / 2.0)
        bottom = _sample_ellipse((x + w / 2.0, y + h - hh / 2.0), w / 2.0, hh / 2.0)
        _emit_path(L, [_rotate(apex, cx, cy, rot), _rotate(left, cx, cy, rot)], height,
                   closed=False, color=color, width=width)
        _emit_path(L, [_rotate(apex, cx, cy, rot), _rotate(right, cx, cy, rot)], height,
                   closed=False, color=color, width=width)
        _emit_path(L, [_rotate(p, cx, cy, rot) for p in bottom], height, closed=True, color=color, width=width)


def _emit_text_at(L, x, y, text, size, color, height: int):
    L.append("gsave")
    L.append(f"{_fmt(x)} {_fmt(height - y)} translate")
    L.append(f"{_fmt(color[0])} {_fmt(color[1])} {_fmt(color[2])} setrgbcolor")
    L.append(f"/Helvetica-Bold findfont {_fmt(max(1.0, size))} scalefont setfont")
    L.append(f"({_ps_text(text)}) show")
    L.append("grestore")


def _emit_text(L, item, height: int, board_style: str):
    text = item.get("text", "")
    if not text:
        return
    pos = item["pos"]
    size = float(item.get("size", 24)) * float(item.get("scale", 1.0))
    rot = float(item.get("rotation", 0.0))
    color = _blend_color(item.get("color", "#000000"), board_style)
    L.append("gsave")
    L.append(f"{_fmt(pos[0])} {_fmt(height - pos[1])} translate")
    L.append(f"{_fmt(-rot)} rotate")
    L.append(f"{_fmt(color[0])} {_fmt(color[1])} {_fmt(color[2])} setrgbcolor")
    L.append(f"/Helvetica findfont {_fmt(max(1.0, size))} scalefont setfont")
    L.append(f"({_ps_text(text)}) show")
    L.append("grestore")


def _emit_image(L, img, height: int, decoded_images: dict):
    """把 RGB 位图用 PostScript `colorimage` 运算符嵌入。"""
    data = decoded_images.get(img.get("id"))
    if not data:
        return
    try:
        pw, ph, raw = data
    except (TypeError, ValueError):
        return
    if (isinstance(pw, bool) or isinstance(ph, bool)
            or not isinstance(pw, int) or not isinstance(ph, int)
            or pw <= 0 or ph <= 0 or not isinstance(raw, (bytes, bytearray))
            or len(raw) != pw * ph * 3):
        return
    pos = img.get("pos", [0.0, 0.0])
    size = img.get("size", [float(pw), float(ph)])
    dw = max(1.0, float(size[0]))
    dh = max(1.0, float(size[1]))
    rot = float(img.get("rotation", 0.0))
    cx, cy = pos[0], height - pos[1]
    L.append("gsave")
    L.append(f"{_fmt(cx)} {_fmt(cy)} translate")
    L.append(f"{_fmt(-rot)} rotate")
    L.append(f"{_fmt(-dw / 2.0)} {_fmt(-dh / 2.0)} translate")
    # 源坐标 (0,0)→(0,dh) 顶部、源 (pw,ph)→(dw,0) 底部：像素行序与 Qt 一致
    L.append(
        f"{pw} {ph} 8 [{_fmt(dw)} 0 0 {_fmt(-dh)} 0 {_fmt(dh)}] "
        f"{{<{bytes(raw).hex()}>}} false 3 colorimage"
    )
    L.append("grestore")


def _eps_lines(page, width: int, height: int, board_style: str, decoded_images: dict):
    L = []
    bg = _background(board_style)
    L.append("%!PS-Adobe-3.0 EPSF-3.0")
    L.append(f"%%BoundingBox: 0 0 {width} {height}")
    L.append(f"%%HiResBoundingBox: 0 0 {_fmt(width)} {_fmt(height)}")
    L.append("%%Pages: 1")
    L.append("%%EndComments")
    L.append(f"{_fmt(bg[0])} {_fmt(bg[1])} {_fmt(bg[2])} setrgbcolor")
    L.append("0 0 moveto")
    L.append(f"{width} 0 lineto")
    L.append(f"{width} {height} lineto")
    L.append(f"0 {height} lineto")
    L.append("closepath fill")
    for seg in page.get("segments", []):
        _emit_segment(L, seg, height, board_style)
    for item in page.get("shapes", []):
        _emit_shape(L, item, height, board_style)
    for img in page.get("images", []):
        _emit_image(L, img, height, decoded_images)
    for item in page.get("texts", []):
        _emit_text(L, item, height, board_style)
    L.append("%%EOF")
    return L


def write_eps(path, page, width: int, height: int, board_style: str = "WHITE",
              decoded_images: dict | None = None) -> None:
    """把一页序列化页面写成矢量 EPS 文件（latin-1 编码，含 BoundingBox）。"""
    width = max(1, int(width))
    height = max(1, int(height))
    lines = _eps_lines(page, width, height, board_style, decoded_images or {})
    with open(path, "w", encoding="latin-1", newline="\n") as handle:
        handle.write("\n".join(lines))
        handle.write("\n")