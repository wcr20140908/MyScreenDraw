# SPDX-FileCopyrightText: MyScreenDraw contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Structured formula model, layout and hit-testing.

Deliberately free of Qt so the layout maths can be unit-tested against a fake
metrics object with predictable numbers. main.py supplies a QFontMetricsF-backed
metrics implementation and only walks the resulting boxes with a QPainter.

Why structured rather than a LaTeX string
-----------------------------------------
Input arrives only from on-screen buttons, so a user can never produce syntax the
renderer does not handle -- the buttons and the node kinds are the same set. That
removes the tokenizer, the parser and the whole "user typed \\begin{pmatrix} but we
only support a subset" failure mode. It also removes cursor-inside-a-string
navigation, which is unusable on a touch screen: you cannot ask a teacher to poke
arrow keys to get between the braces of \\frac{}{} on a 75-inch board. Instead each
slot is a rectangle you tap.

A formula is a list of nodes. Every node kind names its child slots:

    {"k": "t",    "v": "x"}                     literal run
    {"k": "frac", "num": [...], "den": [...]}   fraction
    {"k": "sup",  "base": [...], "exp": [...]}  superscript
    {"k": "sub",  "base": [...], "sub": [...]}  subscript
    {"k": "sqrt", "arg": [...]}                 square root
    {"k": "int",  "lo": [...], "hi": [...], "arg": [...]}    integral with limits
    {"k": "sum",  "lo": [...], "hi": [...], "arg": [...]}    summation with limits

A slot is addressed by a path: a tuple alternating index and slot name, e.g.
(0, "num", 1, "base") means "node 0's numerator, that list's node 1, its base".
"""
from __future__ import annotations

# --- On-screen symbol panel ---
# Plain Unicode characters need no layout engine at all: drawText renders them
# directly. That makes this tier nearly free while covering most of what gets
# written on a classroom board. Only the "structure" group reaches the layout code.
#
# Each group is (group_key, i18n_key, entries). An entry is either a bare string to
# insert, or ("!kind", label) to insert a structure node.
SYMBOL_GROUPS = (
    ("greek", "sym_group_greek", (
        "α", "β", "γ", "δ", "ε", "ζ", "η", "θ", "ι", "κ", "λ", "μ",
        "ν", "ξ", "π", "ρ", "σ", "τ", "υ", "φ", "χ", "ψ", "ω",
        "Γ", "Δ", "Θ", "Λ", "Ξ", "Π", "Σ", "Φ", "Ψ", "Ω",
    )),
    ("operator", "sym_group_operator", (
        "+", "−", "×", "÷", "±", "∓", "·", "∗", "≤", "≥", "≠", "≈",
        "≡", "∝", "∞", "√", "∠", "⊥", "∥", "°", "′", "″", "%",
    )),
    ("relation", "sym_group_relation", (
        "∈", "∉", "⊂", "⊃", "⊆", "⊇", "∪", "∩", "∅", "∀", "∃", "∄",
        "→", "←", "↔", "⇒", "⇐", "⇔", "∴", "∵",
    )),
    ("calculus", "sym_group_calculus", (
        "∫", "∬", "∮", "∑", "∏", "∂", "∇", "Δ", "lim", "d", "dx", "dy",
        "sin", "cos", "tan", "log", "ln", "exp",
    )),
    ("structure", "sym_group_structure", (
        ("!frac", "a/b"), ("!sup", "x²"), ("!sub", "x₁"), ("!sqrt", "√‾"),
        ("!sum", "∑"), ("!int", "∫"),
    )),
)

STRUCTURE_PREFIX = "!"


SLOTS = {
    "t": (),
    "frac": ("num", "den"),
    "sup": ("base", "exp"),
    "sub": ("base", "sub"),
    "sqrt": ("arg",),
    "int": ("lo", "hi", "arg"),
    "sum": ("lo", "hi", "arg"),
}

# Layout constants. Hand-tuned rather than read from an OpenType MATH table:
# PyQt6 does not expose that table, and the fonts we can rely on being present
# (Microsoft YaHei) do not carry one anyway. See docs note in the changelog.
SCRIPT_RATIO = 0.72         # 上下标相对基准字号
SCRIPT_MIN = 9.0            # 再嵌套也不小于这个字号，否则触屏上点不中
FRAC_RATIO = 0.90           # 分子分母相对基准字号
FRAC_GAP = 0.22             # 分数线与分子/分母的间隙（相对字号）
FRAC_BAR = 0.055            # 分数线粗细（相对字号），至少 1px
FRAC_PAD = 0.18             # 分数线左右各留出的余量（相对字号）
AXIS_RATIO = 0.28           # 数学轴高度（分数线离基线多高，相对字号）
SUP_RISE = 0.42             # 上标抬升（相对基准字号）
SUB_DROP = 0.18             # 下标下沉（相对基准字号）
SQRT_LEAD = 0.62            # 根号钩部宽度（相对字号）
SQRT_GAP = 0.14             # 根号内容与上横线的间隙（相对字号）
LIMIT_GAP = 0.12            # 求和/积分上下限与主符号的间隙（相对字号）
EMPTY_W = 0.60              # 空槽宽度（相对字号）——必须够大，能用手指点中
EMPTY_H = 0.85              # 空槽高度（相对字号）


class Box:
    """A laid-out subtree: size plus where its children sit.

    Coordinates are relative to this box's own origin, which is at its left edge
    on the baseline. Children carry (dx, dy) offsets from that origin.
    """

    __slots__ = ("w", "ascent", "descent", "children", "kind", "text", "size",
                 "slot_path", "bar", "glyph")

    def __init__(self, w=0.0, ascent=0.0, descent=0.0, kind="row", text="",
                 size=0.0, slot_path=None):
        self.w = w
        self.ascent = ascent
        self.descent = descent
        self.children = []      # list of (dx, dy, Box)
        self.kind = kind
        self.text = text
        self.size = size
        self.slot_path = slot_path
        self.bar = None         # (x, y, width, thickness) for fraction/radical rules
        self.glyph = None       # (text, size, dx, dy) for a big operator or radical

    @property
    def height(self):
        return self.ascent + self.descent

    def __repr__(self):                                     # pragma: no cover
        return "Box(%s w=%.1f a=%.1f d=%.1f)" % (self.kind, self.w, self.ascent, self.descent)


def group_keys():
    return tuple(key for key, _label, _entries in SYMBOL_GROUPS)


def group_label(key):
    for group_key, label, _entries in SYMBOL_GROUPS:
        if group_key == key:
            return label
    return key


def group_entries(key):
    for group_key, _label, entries in SYMBOL_GROUPS:
        if group_key == key:
            return entries
    return ()


def is_structure(entry):
    """Structure entries insert a node; everything else inserts characters."""
    return isinstance(entry, tuple)


def structure_kind(entry):
    """('!frac', 'a/b') -> 'frac'. Returns None for a plain symbol."""
    if not is_structure(entry):
        return None
    token = entry[0]
    if not token.startswith(STRUCTURE_PREFIX):
        return None
    kind = token[len(STRUCTURE_PREFIX):]
    return kind if kind in SLOTS else None


def entry_label(entry):
    return entry[1] if is_structure(entry) else entry


def new_node(kind, value=""):
    """Build an empty node of the given kind, with empty slots ready to fill."""
    if kind not in SLOTS:
        raise ValueError("unknown node kind: %r" % (kind,))
    if kind == "t":
        return {"k": "t", "v": value}
    node = {"k": kind}
    for slot in SLOTS[kind]:
        node[slot] = []
    return node


def normalize(nodes):
    """Coerce loaded data into a valid tree, dropping anything unrecognised.

    Project files are user-editable and may come from another version, so this has
    to be total: never raise, always return something renderable.
    """
    out = []
    if not isinstance(nodes, list):
        return out
    for raw in nodes:
        if not isinstance(raw, dict):
            continue
        kind = raw.get("k")
        if kind not in SLOTS:
            continue
        if kind == "t":
            value = raw.get("v", "")
            if not isinstance(value, str):
                value = str(value)
            if value:
                out.append({"k": "t", "v": value})
            continue
        node = {"k": kind}
        for slot in SLOTS[kind]:
            node[slot] = normalize(raw.get(slot))
        out.append(node)
    return out


def is_empty(nodes):
    return not nodes


def get_slot(nodes, path):
    """Resolve a slot path to the list it names. Returns None if the path is stale."""
    current = nodes
    index = 0
    while index < len(path):
        position = path[index]
        if not isinstance(position, int) or position < 0 or position >= len(current):
            return None
        node = current[position]
        index += 1
        if index >= len(path):
            return None                     # path must end on a slot name
        name = path[index]
        if name not in SLOTS.get(node.get("k"), ()):
            return None
        current = node[name]
        index += 1
    return current


def layout(nodes, size, metrics, path=()):
    """Lay out a node list into a row Box.

    metrics must provide advance(text, size), ascent(size) and descent(size).
    Keeping that an interface rather than importing Qt is what lets the geometry
    be tested with exact expected numbers.
    """
    row = Box(kind="row", size=size, slot_path=path)
    x = 0.0
    ascent = 0.0
    descent = 0.0
    if not nodes:
        # An empty slot still needs a tappable rectangle, otherwise a fresh
        # fraction has nothing to aim at.
        width = EMPTY_W * size
        row.w = width
        row.ascent = EMPTY_H * size * 0.8
        row.descent = EMPTY_H * size * 0.2
        placeholder = Box(w=width, ascent=row.ascent, descent=row.descent,
                          kind="empty", size=size, slot_path=path)
        row.children.append((0.0, 0.0, placeholder))
        return row
    for index, node in enumerate(nodes):
        box = _layout_node(node, size, metrics, path + (index,))
        row.children.append((x, 0.0, box))
        x += box.w
        ascent = max(ascent, box.ascent)
        descent = max(descent, box.descent)
    row.w = x
    row.ascent = ascent
    row.descent = descent
    return row


def _script_size(size):
    return max(SCRIPT_MIN, size * SCRIPT_RATIO)


def _layout_node(node, size, metrics, path):
    kind = node.get("k")
    if kind == "t":
        text = node.get("v", "")
        box = Box(w=metrics.advance(text, size), ascent=metrics.ascent(size),
                  descent=metrics.descent(size), kind="t", text=text, size=size)
        return box
    if kind == "frac":
        return _layout_frac(node, size, metrics, path)
    if kind == "sup":
        return _layout_script(node, size, metrics, path, "exp", raise_it=True)
    if kind == "sub":
        return _layout_script(node, size, metrics, path, "sub", raise_it=False)
    if kind == "sqrt":
        return _layout_sqrt(node, size, metrics, path)
    if kind in ("int", "sum"):
        return _layout_bigop(node, size, metrics, path, kind)
    return Box(kind="row", size=size)


def _layout_frac(node, size, metrics, path):
    inner = max(SCRIPT_MIN, size * FRAC_RATIO)
    num = layout(node.get("num") or [], inner, metrics, path + ("num",))
    den = layout(node.get("den") or [], inner, metrics, path + ("den",))
    pad = FRAC_PAD * size
    width = max(num.w, den.w) + pad * 2.0
    axis = AXIS_RATIO * size            # 分数线离基线的高度
    gap = FRAC_GAP * size
    thickness = max(1.0, FRAC_BAR * size)

    box = Box(w=width, kind="frac", size=size, slot_path=path)
    # 分子底边贴在分数线上方 gap 处；dy 是基线偏移，向上为负
    num_dy = -(axis + gap + num.descent)
    den_dy = -axis + gap + den.ascent
    box.children.append(((width - num.w) / 2.0, num_dy, num))
    box.children.append(((width - den.w) / 2.0, den_dy, den))
    box.bar = (0.0, -axis, width, thickness)
    box.ascent = -num_dy + num.ascent
    box.descent = den_dy + den.descent
    return box


def _layout_script(node, size, metrics, path, slot, raise_it):
    base = layout(node.get("base") or [], size, metrics, path + ("base",))
    script = layout(node.get(slot) or [], _script_size(size), metrics, path + (slot,))
    box = Box(w=base.w + script.w, kind="sup" if raise_it else "sub",
              size=size, slot_path=path)
    box.children.append((0.0, 0.0, base))
    if raise_it:
        dy = -(SUP_RISE * size)
        box.children.append((base.w, dy, script))
        box.ascent = max(base.ascent, -dy + script.ascent)
        box.descent = max(base.descent, script.descent - (-dy))
    else:
        dy = SUB_DROP * size
        box.children.append((base.w, dy, script))
        box.ascent = max(base.ascent, script.ascent - dy)
        box.descent = max(base.descent, dy + script.descent)
    box.descent = max(0.0, box.descent)
    return box


def _layout_sqrt(node, size, metrics, path):
    arg = layout(node.get("arg") or [], size, metrics, path + ("arg",))
    lead = SQRT_LEAD * size
    gap = SQRT_GAP * size
    thickness = max(1.0, FRAC_BAR * size)
    box = Box(w=lead + arg.w + gap, kind="sqrt", size=size, slot_path=path)
    box.children.append((lead, 0.0, arg))
    box.ascent = arg.ascent + gap + thickness
    box.descent = arg.descent
    # 钩部由 main.py 用 QPainterPath 画：给出它要占的矩形和横线
    box.glyph = ("sqrt", size, 0.0, 0.0)
    box.bar = (lead, -(arg.ascent + gap), arg.w + gap, thickness)
    return box


def _layout_bigop(node, size, metrics, path, kind):
    symbol = "∫" if kind == "int" else "∑"
    op_size = size * 1.45
    op_w = metrics.advance(symbol, op_size)
    op_ascent = metrics.ascent(op_size)
    op_descent = metrics.descent(op_size)
    limit_size = _script_size(size)
    lo = layout(node.get("lo") or [], limit_size, metrics, path + ("lo",))
    hi = layout(node.get("hi") or [], limit_size, metrics, path + ("hi",))
    arg = layout(node.get("arg") or [], size, metrics, path + ("arg",))
    gap = LIMIT_GAP * size

    head_w = max(op_w, lo.w, hi.w)
    box = Box(w=head_w + arg.w, kind=kind, size=size, slot_path=path)
    box.glyph = (symbol, op_size, (head_w - op_w) / 2.0, 0.0)
    hi_dy = -(op_ascent + gap + hi.descent)
    lo_dy = op_descent + gap + lo.ascent
    box.children.append(((head_w - hi.w) / 2.0, hi_dy, hi))
    box.children.append(((head_w - lo.w) / 2.0, lo_dy, lo))
    box.children.append((head_w, 0.0, arg))
    box.ascent = max(-hi_dy + hi.ascent, arg.ascent, op_ascent)
    box.descent = max(lo_dy + lo.descent, arg.descent, op_descent)
    return box


def slot_rects(box, origin_x=0.0, baseline_y=0.0, out=None):
    """Collect (slot_path, x, y, w, h) for every slot, for hit-testing.

    Rects are absolute within the formula's own coordinate system. Only rows that
    name a slot are collected -- a literal text run is not independently tappable,
    tapping it targets the row that contains it.
    """
    if out is None:
        out = []
    if box.slot_path is not None and box.kind in ("row", "empty"):
        out.append((box.slot_path, origin_x, baseline_y - box.ascent, box.w, box.height))
    for dx, dy, child in box.children:
        slot_rects(child, origin_x + dx, baseline_y + dy, out)
    return out


def hit_slot(box, x, y):
    """Which slot does this point fall in? Deepest (smallest) match wins.

    Deepest-wins matters because slots nest: a point inside a fraction's numerator
    is also inside the fraction's own row. The user means the numerator.
    """
    best = None
    best_area = None
    for path, rx, ry, rw, rh in slot_rects(box):
        if rx <= x <= rx + rw and ry <= y <= ry + rh:
            area = rw * rh
            if best_area is None or area < best_area:
                best, best_area = path, area
    return best


def plain_text(nodes):
    """Flatten to something readable -- used for logs and accessibility, not rendering."""
    parts = []
    for node in nodes or []:
        kind = node.get("k")
        if kind == "t":
            parts.append(node.get("v", ""))
        elif kind == "frac":
            parts.append("(%s)/(%s)" % (plain_text(node.get("num")), plain_text(node.get("den"))))
        elif kind == "sup":
            parts.append("%s^(%s)" % (plain_text(node.get("base")), plain_text(node.get("exp"))))
        elif kind == "sub":
            parts.append("%s_(%s)" % (plain_text(node.get("base")), plain_text(node.get("sub"))))
        elif kind == "sqrt":
            parts.append("sqrt(%s)" % plain_text(node.get("arg")))
        elif kind in ("int", "sum"):
            head = "∫" if kind == "int" else "∑"
            parts.append("%s[%s..%s](%s)" % (head, plain_text(node.get("lo")),
                                             plain_text(node.get("hi")),
                                             plain_text(node.get("arg"))))
    return "".join(parts)
