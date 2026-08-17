# SPDX-FileCopyrightText: MyScreenDraw contributors
# SPDX-License-Identifier: GPL-3.0-or-later
# 版本号：见 version.py（唯一来源，代码里统一用 APP_VERSION）
# 更新日志：
# v5.1.0：统一文件工作流 + 导入稳定性
# 1. 打开/保存/另存为/导入/导出统一到分组“文件”面板
# 2. 大图在解码器内预缩放；PDF 逐页增量导入并以单次撤销提交
# 3. 修复 EPS RGB colorimage 与 Qt 行对齐填充
#
# v5.0.0：首个公开稳定版
# 1. 版本号统一为 5.0.0（version.py / README / SECURITY / 审计文档同步）
# 2. 国际化完成：补全 i18n theme key（修复测试套件失败）；计算器错误/溢出文案、
#    点名导入对话框改走 tr()，消除硬编码中文
# 3. 关键路径异常收敛：保存/打开/导出/窗口创建改为捕获具体异常类型
#    （OSError / ValueError / json.JSONDecodeError），并经 map_io_exception 映射为
#    用户友好的本地化错误对话框（复用 err_file_missing / err_permission 等文案）
# 4. 新增 SVG（QSvgGenerator）与 EPS（eps_export.py 矢量 PostScript）导出；
#    兑现此前只存在于 i18n 文案与文档中的「矢量导出」承诺
# 5. 新增图片/PDF 导入：页面模型增加 images 对象（PNG→base64 内嵌进 .msd，
#    自包含）；QImageReader 解码图片、QPdfDocument 渲染 PDF 逐页导入
# 6. 发行包合规：PyInstaller 打包纳入 LICENSE 与 THIRD_PARTY_LICENSES.txt
# 7. 新增英文版 README.en.md
#
# v4.8.1：修复 v4.8.0 触控尺寸过度放大造成的 UI 回归
# 1. 撤销全局 QPushButton min-height；它会与上下 padding 相加，把普通按钮实际撑到 50px+
# 2. 主栏按钮恢复紧凑，竖版面板从约 870px 收回约 394px（白板关闭）
# 3. 批注设置的色块/预览条/粗细标签/滑块恢复正常次序与间距
# 4. 横版白板控制区由 5 按钮横摊改回紧凑两行，不再挤乱主题/退出等后续按钮
# 5. 同步修复审查发现的非左键释放中断笔画、撤销后旧停笔计时复活、缩略图抓屏后停更，
#    以及实时缩略图原地移动/改色不更新和重页边界扫描性能问题
#
# v4.8.0：触控大屏专项（横版 UI 修复 + 停笔定形 + 实时缩略图）
# 0. 修复启动即崩溃：样式表引用的 TOUCH_* 常量从未定义，apply_theme 抛 NameError
# 1. 旋转键改为程序化绘制的图标（无文字、不占标题栏），并去掉它的提示气泡
# 2. 白板缩略图实时渲染：面板打开期间按内容指纹比对，落墨即现（当前页取实时内容，
#    不再等松手写回 pages；单页过重时自动退避到慢节拍，不拖慢书写）
# 3. 横版 UI 整改：
#    - 白板控制区按方向重排（竖版两行 / 横版一行），不再把按钮文字压得显示不全
#    - 子菜单锚定到触发它的功能键（横版开在键正下方、竖版与键同高），不再一律贴左上角
#    - 主面板贴屏幕下沿时子菜单翻到上方、贴右沿时翻到左侧；拖动主面板时实时跟随换边
#    - 横竖切换后把面板钳回屏幕内，修复贴边旋转跑出屏幕
# 4. 提示气泡不再被全屏画布压住（心跳会把 QTipLabel 一并抬到画布之上）
# 5/6. 手绘识别重做分类环节：由「阈值级联」改为「建形后量残差、择优采用」，
#    并按合成手绘样本扫参标定拐角检测。梯形不再被判成椭圆、平行四边形不再退化成三角形
# 7. 智能识别的触发时机改为「笔停在末端不动」：抬笔＝保留手绘，停笔＝定形，
#    停留期间笔尖显示进度环；定形后不必抬笔即可接着画
# 8. 触控优化：按钮/滑块/色块统一到 38px 级触控目标，命中容差放宽，缩略图支持手指甩动，
#    并关闭 Windows 的「按住变右键 / 甩动手势 / 等待光环」（它会直接破坏停笔定形）
#
# v4.5.1：恢复白板上页/下页按钮，并修复缩略图列表加载
# 1. 选中工具条：点选/框选图形后，浮动面板新增「复/删/⋯」三个方块按钮——复制（副本贴在
#    旁边不重叠并自动选中）、删除、更多（仅平面图形）：三角形的外接圆/内切圆/中线/高/
#    中位线，矩形对角线/外接圆/内切圆，梯形对角线/高，菱形对角线/内切圆，圆的直径/半径/
#    内接外切正方形/内接三角形，椭圆长短轴/焦点，直线中点/垂直平分线，角的角度调整等
# 2. 框选工具支持直接点选：单击图形/文字/笔迹即可选中并拖动
# 3. 新增图形：菱形（对角 2 点+侧点定宽，手绘识别同步支持）与角（顶点+两边端点，
#    「⋯」里可 ±5° 调整角度、设为常用角、作角平分线）
# 4. 直线端点吸附：点选画线、手绘识别、拖动直线时端点自动吸附到附近直线端点
# 5. 计时器：正计时/倒计时、常用时长预设、分秒上下箭头微调、开始/暂停与重置；子菜单
#    关闭后屏幕顶端居中显示迷你计时器；倒计时结束自动解除静音并调至最大音量+响铃
# 6. 主面板可按住空白处自由拖动，位置退出时记忆
#
# v3.9.2：
# 1. 根治点击闪烁与子菜单叠影：子菜单从主面板拆出，改为独立置顶浮窗；切换子菜单时
#    浮窗先隐藏、在不可见状态下完成换内容/调尺寸/定位再显示——半透明窗口从此不在
#    可见状态下缩放，合成器不再出现新旧画面交替；主面板窗口尺寸恒定（仅白板开关调整）
# 2. owner 绑定只在窗口句柄变化时执行（不再每次心跳重写），心跳不再 raise，
#    消除周期性重合成；子菜单浮窗与选中面板设为不抢焦点（WA_ShowWithoutActivating）
# 3. 选中面板/子菜单浮窗补上主题样式（此前独立顶层窗口吃不到面板样式表）
#
# v3.9.1：
# 1. 修复面板被全屏画布压住无法操作：面板/选中面板通过 GWLP_HWNDPARENT 绑定为画布的
#    owned window，系统级保证 Z 序永远在画布之上；切换穿透/绘图导致画布句柄重建时，
#    心跳自动重新绑定自愈
#
# v3.9.0：
# 1. 智能识别常驻：移除独立的「智能图形」工具，批注笔从启动起就自动识别笔迹——画得接近
#    直线/三角形/矩形/平行四边形/梯形/圆/椭圆时松手即转为标准图形，其余笔迹原样保留；
#    连画 3 段共线短线合成虚线；批注设置里可一键开关；撤销一次找回原笔迹、再撤销回落笔前
# 2. 移除手写文字识别功能及 winsdk 依赖
# 3. 修复面板残影/按钮高频闪烁/穿透与绘图模式看似自动跳变/撤销清屏点不中：子面板显隐后
#    窗口尺寸强制同步收紧并整窗重绘，杜绝旧画面残留；心跳置顶去掉 raise 与强制显示标志，
#    频率降为 500ms
# 4. 穿透模式下点选任意绘图工具自动切回绘图模式，不再出现「画不出来」
# 5. 修复小屏启动时面板顶出屏幕；按钮 emoji 乱码改纯文字
#
# v3.8.0：
# 1. 智能图形：随手画的笔迹松手即自动识别为标准图形；连画 3 段共线短线自动合成虚线
# 2. 手写识别：笔迹停顿后识别为楷体文字（本版已移除）
#
# v3.7.0：
# 1. 图形重做：平面图形改为「点选确认」——三角形点 3 顶点、圆用圆心+圆周点、梯形第 4 点自动
#    吸附保证平行；右键取消取点；立体图形（长方体/正方体/圆柱/圆锥）保留拖拽
# 2. 导出合并：快速截图并入导出；「导出」按钮点开后选 PNG / PDF
# 3. 白板收纳：上页/页码/下页/新页/黑白板切换默认隐藏，进入白板后才显示
# 4. 配置持久化：颜色/粗细/透明度/主题/橡皮/放大镜设置退出时保存，启动时恢复
#
# v3.6.0：
# 1. 导出：新增 PNG / PDF 导出，白板模式按页导出（PDF 合成多页），批注模式导出屏幕+批注
# 2. 荧光笔：颜色/透明度/粗细可调，整笔合成描边保证重叠不叠色，笔迹长期保留不淡出
# 3. 放大镜：进入时冻结屏幕，镜头跟随鼠标，倍率按 50% 步长调节（滚轮亦可），镜面大小可调
# 4. 修复：截图/导出时浮动的选中面板不再入镜
#
# v3.5.0：
# 1. 撤销重做：改为整页快照栈，严格按操作时间顺序回退，新增「重做」按钮
# 2. 撤销覆盖：笔画、橡皮、图形、文本、改色改粗细、移动缩放旋转、清屏全部可撤销
# 3. 日志治理：events.jsonl 超过 1MB 自动轮转，最多保留 3 份，总占用不再无限增长
#
# v3.4.0：
# 1. 垂直压缩：设置布局对齐方式为 AlignTop，彻底消除按钮之间的空缺感
# 2. 紧凑布局：Spacing 设置为 2，取消所有 Stretch，让面板像工具箱一样精致
# 3. 箭头重装：严谨补全批注与橡皮的微调箭头（▲/▼），步长精确为 1
# 4. 交互：默认绘图模式，左侧居中，一键切换工具高亮，二键横向开启紧凑菜单

import sys
import os
import errno
import ctypes
import uuid
import json
import math
import time
import threading
import random
import csv
import base64
import logging
import ast
from datetime import datetime
from persistence import (atomic_write_json, cleanup_temp_files, normalize_project_data, make_project_data,
                         ensure_file_size, PROJECT_KIND, AUTOSAVE_KIND, MAX_ABS_COORD,
                         MAX_IMAGES_PER_PAGE)
from calculator import evaluate as safe_calculate, CalculatorError
from display_utils import (clamp_rect, choose_screen, clamp_ruler_width, pixels_per_mm_from_dpi, sane_dpi,
                           valid_pixels_per_mm, screen_key, normalize_calibrations,
                           protractor_angle_degrees, ruler_geometry as physical_ruler_geometry,
                           ruler_mm_from_local_x)
from version import APP_VERSION
from i18n import tr, trf, CURRENT
import eps_export
from PyQt6.QtWidgets import (QApplication, QMainWindow, QLabel, QPushButton,
                             QVBoxLayout, QHBoxLayout, QWidget, QFrame, QGridLayout, QColorDialog, QSlider,
                             QInputDialog, QMessageBox, QMenu, QFileDialog, QLineEdit, QListWidget,
                             QAbstractItemView, QSizePolicy, QListWidgetItem, QDialog, QDoubleSpinBox,
                             QScroller, QToolTip)
from PyQt6.QtCore import (Qt, QPoint, QPointF, QRectF, QTimer, QTranslator, QLibraryInfo, QLine, pyqtSignal, QLocale,
                          QSizeF, QMarginsF, QEventLoop, QSize, QUrl, QBuffer, QIODevice)
from PyQt6.QtGui import (QPainter, QPen, QColor, QFont, QPainterPath, QFontMetricsF, QTransform, QPolygonF,
                         QPixmap, QPdfWriter, QPageSize, QCursor, QGuiApplication, QIcon, QImage, QImageReader)
from pynput import keyboard

APP_DIR = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(APP_DIR, "data")
EXPORT_DIR = os.path.join(APP_DIR, "exports")
AUTOSAVE_DIR = os.path.join(DATA_DIR, "autosave")
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")
ROSTER_FILE = os.path.join(DATA_DIR, "roster.json")
TELEMETRY_FILE = os.path.join(DATA_DIR, "events.jsonl")
TELEMETRY_MAX_BYTES = 1024 * 1024   # 单个日志文件上限：1MB
TELEMETRY_BACKUPS = 2               # 额外保留的历史日志份数，总占用上限约 3MB
AUTOSAVE_INTERVAL = 30              # 自动保存间隔（秒）

# --- 触控大屏适配：控件最小可点面积（像素）---
# 本程序的目标环境是教室触控大屏，手指的有效落点直径约 9mm，换算到常见 55~86 寸
# 大屏上大致就是 38~40px。低于这个尺寸的按钮在讲台上「点十次中七次」，因此所有按钮、
# 箭头、滑块手柄的下限统一由这里给出，apply_theme 的样式表引用这些常量。
TOUCH_MIN_BUTTON = 32     # 独立触控按钮目标高度；普通主栏按钮保持紧凑，不全局套用
TOUCH_ARROW = 32          # ▲▼ 微调箭头（方形）
TOUCH_SQUARE = 34         # 方形图标按钮（旋转键 / 复制删除更多）
TOUCH_SLIDER = 30         # 滑块控件整体最小高度（含手柄溢出）
TOUCH_SLIDER_HANDLE = 22  # 滑块手柄直径
TOUCH_SWATCH = 26         # 调色板色块边长
TOUCH_HIT_SLOP = 8        # 画布上手柄/端点等命中判定的额外容差

LOGGER = logging.getLogger("myscreendraw")
LOG_FILE = os.path.join(DATA_DIR, "app.log")

def setup_logging():
    """File + stderr logging; safe to call more than once."""
    LOGGER.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
    # Drop NullHandler / stale handlers so reloads don't duplicate lines.
    LOGGER.handlers.clear()
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
        file_handler.setFormatter(formatter)
        LOGGER.addHandler(file_handler)
    except OSError as exc:
        # Fall through to stderr-only if data dir is not writable.
        sys.stderr.write(f"MyScreenDraw: cannot open log file: {exc}\n")
    stream_handler = logging.StreamHandler(sys.stderr)
    stream_handler.setFormatter(formatter)
    LOGGER.addHandler(stream_handler)

def notify_user(parent, title, message, *, level="warning", exc=None):
    """Log and show a dialog. level: information | warning | critical."""
    text = str(message)
    if exc is not None:
        LOGGER.exception("%s: %s", title, text)
    elif level == "information":
        LOGGER.info("%s: %s", title, text)
    elif level == "critical":
        LOGGER.error("%s: %s", title, text)
    else:
        LOGGER.warning("%s: %s", title, text)
    if parent is None:
        return
    if level == "information":
        QMessageBox.information(parent, title, text)
    elif level == "critical":
        QMessageBox.critical(parent, title, text)
    else:
        QMessageBox.warning(parent, title, text)


def map_io_exception(exc, path="", *, default_key="err_io"):
    """把文件/解析类异常映射为用户可读的本地化文案（含下一步建议）。

    用户可感知路径（保存/打开/导出/导入）统一用它把具体异常翻译成友好提示，
    而不是把 Python 异常文本直接丢给用户。persistence/calculator 主动抛出的
    ValueError 消息本身已是友好文案，直接透出；其余映射到 i18n 的 err_* 模板。
    """
    if isinstance(exc, FileNotFoundError):
        return trf("err_file_missing", path=path)
    if isinstance(exc, PermissionError):
        return trf("err_permission", path=path)
    if isinstance(exc, OSError) and (getattr(exc, "winerror", None) == 112
                                     or getattr(exc, "errno", None) == errno.ENOSPC):
        return trf("err_disk_full", path=path)
    if isinstance(exc, json.JSONDecodeError):
        return trf("err_bad_json", path=path)
    if isinstance(exc, ValueError):
        return str(exc) if str(exc) else trf(default_key, path=path, detail="")
    return trf(default_key, path=path, detail=str(exc) or "")


# 确保必要的目录存在
def ensure_directories():
    """启动时确保所有必需的目录都已创建。"""
    for directory in [DATA_DIR, EXPORT_DIR, AUTOSAVE_DIR]:
        try:
            os.makedirs(directory, exist_ok=True)
        except Exception as e:
            LOGGER.warning("无法创建目录 %s: %s", directory, e)

def app_path(*parts):
    base_dir = getattr(sys, "_MEIPASS", APP_DIR)
    return os.path.join(base_dir, *parts)

def rotate_telemetry():
    """日志超过上限时轮转：events.jsonl -> .1 -> .2，最老的一份直接丢弃。"""
    try:
        if os.path.getsize(TELEMETRY_FILE) < TELEMETRY_MAX_BYTES:
            return
    except OSError:
        return
    oldest = f"{TELEMETRY_FILE}.{TELEMETRY_BACKUPS}"
    if os.path.exists(oldest):
        os.remove(oldest)
    for index in range(TELEMETRY_BACKUPS - 1, 0, -1):
        older = f"{TELEMETRY_FILE}.{index}"
        if os.path.exists(older):
            os.replace(older, f"{TELEMETRY_FILE}.{index + 1}")
    os.replace(TELEMETRY_FILE, f"{TELEMETRY_FILE}.1")

def _json_safe(value):
    """Coerce telemetry payloads so one bad value never kills event logging."""
    if value is None or isinstance(value, (bool, int, float, str)):
        if isinstance(value, float) and not math.isfinite(value):
            return str(value)
        return value
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]
    if hasattr(value, "name") and callable(value.name):
        try:
            return value.name()
        except Exception:
            pass
    return str(value)


def track_event(name, **payload):
    """Append one JSON line to data/events.jsonl (local product telemetry)."""
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        rotate_telemetry()
        event = {
            "time": datetime.now().isoformat(timespec="seconds"),
            "event": str(name),
            "payload": _json_safe(payload),
        }
        line = json.dumps(event, ensure_ascii=False, allow_nan=False) + "\n"
        with open(TELEMETRY_FILE, "a", encoding="utf-8") as handle:
            handle.write(line)
            handle.flush()
    except Exception:
        LOGGER.exception("事件日志写入失败: %s", name)
        return

def _color_to_hex(color):
    """带 alpha 时写 #AARRGGBB，避免荧光笔透明度在 autosave 里丢失。"""
    if color.alpha() >= 255:
        return color.name()
    return color.name(QColor.NameFormat.HexArgb)

def _parse_id(value):
    """Return a hashable runtime id; untrusted containers never reach set operations."""
    if value is None:
        return uuid.uuid4()
    if not isinstance(value, str) or not value or len(value) > 128:
        return uuid.uuid4()
    try:
        return uuid.UUID(value)
    except ValueError:
        return value


def _coerce_bounded_float(value, default, minimum=-MAX_ABS_COORD, maximum=MAX_ABS_COORD):
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return number if math.isfinite(number) and minimum <= number <= maximum else default


def _coerce_qt_int(value, default):
    return int(round(_coerce_bounded_float(value, default)))


def _coerce_int(value, default, minimum=None):
    """JSON 里 24 和 24.0 都合法（校验器两者都放行），但 QFont/QPen 只收 int，
    直接把浮点数喂给它们会 TypeError 并在 paintEvent 里炸掉整个程序。"""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(number):
        return default
    result = int(round(number))
    return result if minimum is None else max(minimum, result)

def _coerce_float(value, default):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _bounded_image_size(width, height, max_side, max_pixels):
    """Return a positive QSize bounded by both the longest side and pixel count."""
    try:
        width = int(math.ceil(float(width)))
        height = int(math.ceil(float(height)))
        max_side = int(max_side)
        max_pixels = int(max_pixels)
    except (TypeError, ValueError, OverflowError):
        return QSize()
    if width <= 0 or height <= 0 or max_side <= 0 or max_pixels <= 0:
        return QSize()
    scale = min(1.0, max_side / max(width, height), math.sqrt(max_pixels / (width * height)))
    return QSize(max(1, int(width * scale)), max(1, int(height * scale)))


def decode_image_pixels(base64_data):
    """把内嵌的 base64 PNG 解码为 (width, height, RGB bytes)，供 EPS 嵌入。"""
    if not base64_data:
        return None
    try:
        raw = base64.b64decode(base64_data)
    except (ValueError, TypeError):
        return None
    image = QImage.fromData(raw)
    if image.isNull():
        return None
    image = image.convertToFormat(QImage.Format.Format_RGB888)
    width, height = image.width(), image.height()
    row_bytes = width * 3
    stride = image.bytesPerLine()
    try:
        raw_pixels = image.constBits().asstring(image.sizeInBytes())
    except (AttributeError, IndexError, TypeError, ValueError):
        return None
    if stride < row_bytes or len(raw_pixels) < stride * height:
        return None
    # Qt aligns Format_RGB888 rows to 32-bit boundaries. EPS colorimage expects
    # exactly width * height * 3 bytes, with no per-row alignment bytes.
    pixels = (raw_pixels if stride == row_bytes else b"".join(
        raw_pixels[row * stride:row * stride + row_bytes] for row in range(height)
    ))
    return (width, height, pixels)


def serialize_image(item):
    """运行时图片 → JSON 可序列化数据（PNG→base64 内嵌，.msd 自包含）。"""
    pixmap = item.get("pixmap")
    data = ""
    if pixmap is not None and not pixmap.isNull():
        buffer = QBuffer()
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        pixmap.save(buffer, "PNG")
        data = base64.b64encode(bytes(buffer.data())).decode("ascii")
        buffer.close()
    return {
        "id": str(item["id"]),
        "pos": [item["pos"].x(), item["pos"].y()],
        "size": [item["size"].width(), item["size"].height()],
        "rotation": float(item["rotation"]),
        "data": data,
    }


def deserialize_image(data):
    """JSON 图片数据 → 运行时图片（base64 解码回 QPixmap）。"""
    pixmap = QPixmap()
    raw = data.get("data")
    if raw:
        try:
            image = QImage.fromData(base64.b64decode(raw))
            if not image.isNull():
                pixmap = QPixmap.fromImage(image)
        except (ValueError, TypeError):
            pixmap = QPixmap()
    pos = data.get("pos", [0, 0])
    size = data.get("size", [1, 1])
    return {
        "id": _parse_id(data.get("id", uuid.uuid4())),
        "pos": QPointF(_coerce_bounded_float(pos[0], 0.0), _coerce_bounded_float(pos[1], 0.0)),
        "size": QSizeF(max(1.0, _coerce_float(size[0], 1.0)), max(1.0, _coerce_float(size[1], 1.0))),
        "rotation": _coerce_float(data.get("rotation", 0.0), 0.0),
        "pixmap": pixmap,
    }


def serialize_page(page):
    """页面 → 可 JSON 化的纯数据（撤销 diff / autosave 共用）。"""
    serialized = {"segments": [], "texts": [], "shapes": [], "images": []}
    for seg in page.get("segments", []):
        line = seg["line"]
        serialized["segments"].append({
            "id": str(seg["id"]),
            "p1": [line.p1().x(), line.p1().y()],
            "p2": [line.p2().x(), line.p2().y()],
            "color": _color_to_hex(seg["pen"].color()),
            "width": seg["pen"].width(),
            "marker": bool(seg.get("marker", False)),
        })
    for item in page.get("texts", []):
        serialized["texts"].append({
            "id": str(item["id"]),
            "text": item["text"],
            "pos": [item["pos"].x(), item["pos"].y()],
            "color": _color_to_hex(item["color"]),
            "width": item["width"],
            "size": item["size"],
            "scale": item["scale"],
            "rotation": item["rotation"],
        })
    for item in page.get("shapes", []):
        shape_data = {
            "id": str(item["id"]),
            "type": item["type"],
            "kind": item.get("kind", "rect"),
            "color": _color_to_hex(item["color"]),
            "width": item["width"],
        }
        kind = shape_data["kind"]
        if kind == "poly":
            shape_data["points"] = [[p.x(), p.y()] for p in item["points"]]
            shape_data["closed"] = item.get("closed", True)
        elif kind == "angle":
            shape_data["vertex"] = [item["vertex"].x(), item["vertex"].y()]
            shape_data["p1"] = [item["p1"].x(), item["p1"].y()]
            shape_data["p2"] = [item["p2"].x(), item["p2"].y()]
        elif kind == "circle":
            shape_data["center"] = [item["center"].x(), item["center"].y()]
            shape_data["radius"] = item["radius"]
        elif kind == "ellipse":
            shape_data["center"] = [item["center"].x(), item["center"].y()]
            shape_data["rx"] = item["rx"]
            shape_data["ry"] = item["ry"]
            shape_data["rotation"] = item["rotation"]
        else:
            rect = item["rect"]
            shape_data["rect"] = [rect.x(), rect.y(), rect.width(), rect.height()]
            shape_data["rotation"] = item["rotation"]
        serialized["shapes"].append(shape_data)
    serialized["images"] = [serialize_image(item) for item in page.get("images", [])]
    return serialized

def deserialize_page(data):
    """JSON 页面数据 → 画布可用的页面快照。"""
    page = {"segments": [], "texts": [], "shapes": [], "images": []}
    for seg in data.get("segments", []):
        p1, p2 = seg["p1"], seg["p2"]
        color = QColor(seg.get("color", "#000000"))
        pen = QPen(color, _coerce_int(seg.get("width", 1), 1, minimum=1),
                   Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        page["segments"].append({
            "id": _parse_id(seg.get("id", uuid.uuid4())),
            "line": QLine(_coerce_qt_int(p1[0], 0), _coerce_qt_int(p1[1], 0),
                          _coerce_qt_int(p2[0], 0), _coerce_qt_int(p2[1], 0)),
            "pen": pen,
            "marker": bool(seg.get("marker", False)),
        })
    for item in data.get("texts", []):
        pos = item.get("pos", [0, 0])
        page["texts"].append({
            "id": _parse_id(item.get("id", uuid.uuid4())),
            "text": item.get("text", ""),
            "pos": QPointF(_coerce_bounded_float(pos[0], 0.0), _coerce_bounded_float(pos[1], 0.0)),
            "color": QColor(item.get("color", "#000000")),
            "width": _coerce_int(item.get("width", 1), 1, minimum=1),
            "size": _coerce_int(item.get("size", 24), 24, minimum=1),
            "scale": _coerce_float(item.get("scale", 1.0), 1.0),
            "rotation": _coerce_float(item.get("rotation", 0.0), 0.0),
        })
    for item in data.get("shapes", []):
        kind = item.get("kind", "rect")
        shape = {
            "id": _parse_id(item.get("id", uuid.uuid4())),
            "type": item.get("type", "RECT"),
            "kind": kind,
            "color": QColor(item.get("color", "#000000")),
            "width": _coerce_int(item.get("width", 1), 1, minimum=1),
        }
        if kind == "poly":
            shape["points"] = [QPointF(_coerce_bounded_float(p[0], 0.0),
                                             _coerce_bounded_float(p[1], 0.0))
                               for p in item.get("points", [])]
            shape["closed"] = bool(item.get("closed", True))
        elif kind == "angle":
            for key in ("vertex", "p1", "p2"):
                pt = item.get(key, [0, 0])
                shape[key] = QPointF(_coerce_bounded_float(pt[0], 0.0),
                                     _coerce_bounded_float(pt[1], 0.0))
        elif kind == "circle":
            c = item.get("center", [0, 0])
            shape["center"] = QPointF(_coerce_bounded_float(c[0], 0.0),
                                      _coerce_bounded_float(c[1], 0.0))
            shape["radius"] = _coerce_float(item.get("radius", 1), 1.0)
        elif kind == "ellipse":
            c = item.get("center", [0, 0])
            shape["center"] = QPointF(_coerce_bounded_float(c[0], 0.0),
                                      _coerce_bounded_float(c[1], 0.0))
            shape["rx"] = _coerce_float(item.get("rx", 1), 1.0)
            shape["ry"] = _coerce_float(item.get("ry", 1), 1.0)
            shape["rotation"] = _coerce_float(item.get("rotation", 0), 0.0)
        else:
            r = item.get("rect", [0, 0, 0, 0])
            shape["rect"] = QRectF(_coerce_bounded_float(r[0], 0.0),
                                   _coerce_bounded_float(r[1], 0.0),
                                   _coerce_bounded_float(r[2], 0.0),
                                   _coerce_bounded_float(r[3], 0.0))
            shape["rotation"] = _coerce_float(item.get("rotation", 0), 0.0)
        page["shapes"].append(shape)
    page["images"] = [deserialize_image(item) for item in data.get("images", [])]
    return page

def page_signature(page):
    """稳定内容指纹：不依赖 QLine/QPen/uuid 的对象相等语义。"""
    return json.dumps(serialize_page(page), ensure_ascii=False, sort_keys=True, separators=(",", ":"))

def page_has_content(page):
    return bool(page.get("segments") or page.get("texts") or page.get("shapes") or page.get("images"))

def install_qt_translations(app):
    """Install Qt's standard-dialog translations for the app's active language."""
    translator = QTranslator(app)
    translations_path = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
    # Qt uses a region-qualified filename for Simplified Chinese; the other seven
    # supported languages use their application language code directly.
    language = "zh_CN" if CURRENT == "zh" else CURRENT
    filename = f"qtbase_{language}.qm"
    if translator.load(filename, translations_path):
        app.installTranslator(translator)
        # A translator is removed when its Python wrapper is collected. Retain it
        # for the whole QApplication lifetime so dialogs created later stay localized.
        app.qtbase_translator = translator
        track_event("translation_loaded", source=translations_path, locale=language)
    else:
        track_event("translation_missing", source=translations_path, locale=language)

# --- Windows 底层 API ---
HWND_TOPMOST = ctypes.c_void_p(-1)   # 真 (HWND)-1：在 64 位 Python 上必须是 64 位指针，
                                      # 否则裸传 int -1 会被 ctypes 当 c_int 截断成
                                      # 0x00000000FFFFFFFF，SetWindowPos 进不了置顶层，
                                      # 心跳根本没把面板托到 TOPMOST——面板就被画布盖住。
SWP_NOMOVE, SWP_NOSIZE, SWP_NOACTIVATE, SWP_SHOWWINDOW = 0x0002, 0x0001, 0x0010, 0x0040
GWLP_HWNDPARENT = -8

# 给 SetWindowPos 固定函数签名：HWND 用 c_void_p（64 位指针），坐标/标志用 c_int。
# 不设 argtypes 时 ctypes 默认按 c_int 处理每个参数，64 位上会把真 HWND 和
# HWND_TOPMOST 截成 32 位 → 句柄损坏或进不了置顶层，force_topmost/force_above
# 静默失败（被 except 吞掉），面板就持续被画布盖住无法操作。
_user32 = ctypes.windll.user32
_user32.SetWindowPos.argtypes = [
    ctypes.c_void_p, ctypes.c_void_p,   # hwnd, hWndInsertAfter
    ctypes.c_int, ctypes.c_int,          # X, Y
    ctypes.c_int, ctypes.c_int,          # cx, cy
    ctypes.c_uint,                        # uFlags
]
_user32.SetWindowPos.restype = ctypes.c_int   # BOOL
# SetWindowLongPtrW 仅在 64 位 user32.dll 以独立符号导出；32 位上是宏（→SetWindowLongW），
# 直接访问会 AttributeError 让整个程序在 32 位解释器上启动失败。用 hasattr 守卫。
if hasattr(_user32, "SetWindowLongPtrW"):
    _user32.SetWindowLongPtrW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
    _user32.SetWindowLongPtrW.restype = ctypes.c_void_p

def force_topmost(window_id):
    # Keep HWND_TOPMOST without SWP_SHOWWINDOW: repeatedly forcing show during
    # the heartbeat re-composites layered windows and causes flicker.
    try:
        hwnd = int(window_id)
        if not hwnd:
            return
        _user32.SetWindowPos(
            ctypes.c_void_p(hwnd), HWND_TOPMOST, 0, 0, 0, 0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE,
        )
    except Exception:
        pass

def force_above(above_id, below_id):
    """把 above 窗口在 Z 序里排到 below 正上方。

    (HWND_TOPMOST) 只能说明「进了置顶层」，却无法决定同处于置顶层内两个兄弟窗口的相对
    高低；而 GWLP_HWNDPARENT 改归属关系后系统不会立刻重排。于是画布因
    set_drawing_mode 里的 setWindowFlag + show() 重建 HWND 时，新画布默认被创建到置顶
    层最顶端、压在面板之上，心跳的 force_topmost 拉不回来。

    注意参数方向：SetWindowPos(hWnd, hWndInsertAfter) 里 hWndInsertAfter 是「在 Z 序中
    位于 hWnd 之前」的窗口，即 hWnd 会被放到 hWndInsertAfter 的【下面】。所以要把
    above 排到 below 之上，必须定位 below、并以 above 作为插入锚点。写反的话在 owner
    绑定失效时会主动把面板/子菜单塞到全屏画布之下——点击穿到画布上，表现为「点不动」。
    """
    try:
        above = int(above_id)
        below = int(below_id)
        if not above or not below:
            return
        _user32.SetWindowPos(
            ctypes.c_void_p(below), ctypes.c_void_p(above), 0, 0, 0, 0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE,
        )
    except Exception:
        pass

VK_VOLUME_UP = 0xAF
KEYEVENTF_KEYUP = 0x0002

def force_system_max_volume():
    """倒计时结束用：连按 50 次系统音量+，既解除静音又拉满音量（音量+自带解除静音）。"""
    try:
        user32 = ctypes.windll.user32
        for _ in range(50):
            user32.keybd_event(VK_VOLUME_UP, 0, 0, 0)
            user32.keybd_event(VK_VOLUME_UP, 0, KEYEVENTF_KEYUP, 0)
    except Exception:
        pass

def play_alarm_async():
    """后台线程播放提示铃声，不阻塞界面。"""
    def run():
        try:
            import winsound
            for _ in range(4):
                winsound.Beep(1319, 160)
                winsound.Beep(1568, 160)
                winsound.Beep(2093, 320)
                time.sleep(0.15)
        except Exception:
            pass
    threading.Thread(target=run, daemon=True).start()

def set_window_owner(window_id, owner_id):
    """把窗口设为 owner 的 owned window。

    Windows 保证 owned 窗口的 Z 序永远压在 owner 之上——面板绑定到全屏画布后，
    无论画布被点击激活还是切模式后重新显示，都不可能盖住面板，无需轮询抢顶。
    """
    try:
        user32 = ctypes.windll.user32
        fn = user32.SetWindowLongPtrW if hasattr(user32, "SetWindowLongPtrW") else user32.SetWindowLongW
        fn.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
        fn.restype = ctypes.c_void_p
        fn(ctypes.c_void_p(int(window_id)), GWLP_HWNDPARENT, ctypes.c_void_p(int(owner_id)))
    except Exception:
        pass

# Windows 触控/手写笔手势开关（MSDN: Disabling the press and hold gesture）
TABLET_DISABLE_PRESSANDHOLD = 0x00000001
TABLET_DISABLE_PENTAPFEEDBACK = 0x00000008
TABLET_DISABLE_PENBARRELFEEDBACK = 0x00000010
TABLET_DISABLE_TOUCHUIFORCEON = 0x00000100
TABLET_DISABLE_TOUCHSWITCH = 0x00008000
TABLET_DISABLE_FLICKS = 0x00010000
TABLET_DISABLE_SMOOTHSCROLLING = 0x00080000
TABLET_DISABLE_FLICKFALLBACKKEYS = 0x00100000
TABLET_PEN_PROPERTY = "MicrosoftTabletPenServiceProperty"

def disable_touch_gestures(window_id):
    """关掉 Windows 对该窗口的触控手势加工，让触摸像鼠标一样即时、逐点上报。

    教室触控大屏上不关掉会踩三个坑：
    ① 「按住不动 = 右键」：系统按住约 800ms 后发 WM_RBUTTONDOWN，手指停在原地想让直线
       定形时会被判成右键——本程序右键是「取消取点 / 移除教具 / 退出聚光灯」，等于画到
       一半功能乱跳；这也正是「停笔转直线」必须先解决的前置问题。
    ② 按住时屏幕上会先画一圈系统自己的等待光环，盖在笔迹上。
    ③ flick（甩动）手势会把快速划动吞掉当成翻页/滚动，笔画直接丢一截。
    """
    try:
        user32 = ctypes.windll.user32
        flags = (TABLET_DISABLE_PRESSANDHOLD | TABLET_DISABLE_PENTAPFEEDBACK
                 | TABLET_DISABLE_PENBARRELFEEDBACK | TABLET_DISABLE_TOUCHUIFORCEON
                 | TABLET_DISABLE_TOUCHSWITCH | TABLET_DISABLE_FLICKS
                 | TABLET_DISABLE_SMOOTHSCROLLING | TABLET_DISABLE_FLICKFALLBACKKEYS)
        user32.SetPropW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_void_p]
        user32.SetPropW(ctypes.c_void_p(int(window_id)), TABLET_PEN_PROPERTY, ctypes.c_void_p(flags))
    except Exception:
        pass

def make_rotate_icon(color, size=22):
    """程序化绘制「旋转」圆弧箭头图标。

    不用 ⟳/🔄 之类字符：Windows 各版本的字体回退不一致，缺字形时按钮上会显示成
    豆腐块方框（本项目历史上已经因为 emoji 乱码退回过纯文字）。自己画则任何环境一致。
    """
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor(color), max(2.0, size / 11.0))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        margin = size * 0.22
        box = QRectF(margin, margin, size - 2 * margin, size - 2 * margin)
        painter.drawArc(box, 55 * 16, 265 * 16)          # 缺口留在右上角给箭头
        # 箭头：贴在圆弧起点（约 55°）的切线方向上
        angle = math.radians(55.0)
        radius = box.width() / 2.0
        tip = QPointF(box.center().x() + radius * math.cos(angle),
                      box.center().y() - radius * math.sin(angle))
        head = size * 0.26
        painter.setBrush(QColor(color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPolygon(QPolygonF([
            QPointF(tip.x() - head * 0.15, tip.y() - head * 0.95),
            QPointF(tip.x() + head * 0.85, tip.y() + head * 0.05),
            QPointF(tip.x() - head * 0.60, tip.y() + head * 0.55),
        ]))
    finally:
        painter.end()
    return QIcon(pixmap)

# --- 笔迹图形识别：把手绘的不规则笔迹拟合成标准平面图形（纯几何，零依赖） ---
class StrokeShapeRecognizer:
    """单笔笔迹 → LINE / TRIANGLE / RECT / PARALLELOGRAM / TRAPEZOID / CIRCLE / ELLIPSE。

    流程：去重 → 直线检验(主成分) → 闭合检验 → 等距重采样 → 弦角法找拐角 →
    按拐角数走多边形拟合(顶点=相邻边直线求交)或圆/椭圆拟合；全程带残差校验，
    拟合不达标返回 None，笔迹保留原样。虚线由画布层将连续共线短直线合并而成。
    """
    RESAMPLE_N = 128        # 闭合笔迹重采样点数
    # 下面四个常量用合成手绘样本（工整/潦草两档，各 800 例）扫参标定：
    # 平滑窗口调小 + 拐角弦窗口调大，能在不误伤圆/椭圆的前提下把「潦草梯形」「潦草平行
    # 四边形」的钝角保住——这两类正是被磨钝后掉进圆/椭圆分支的重灾区。
    SMOOTH_WINDOW = 3       # 重采样后的环形移动平均窗口（越大越平滑，但会磨钝真实拐角）
    CORNER_WINDOW = 6       # 拐角检测的弦窗口（重采样步数）
    CORNER_MIN_TURN = 26.0  # 视为拐角的最小转角（度）——细长菱形/平缓梯形的钝角转角很小，
                            # 宁可多收几个弱拐角，再由「建形后量残差」的评分环节筛掉
    CORNER_NMS = 8          # 拐角非极大值抑制半径（重采样步数）
    STRONG_TURN = 48.0      # 硬拐角阈值：≥5 个硬拐角视为不支持的多边形
    PARALLEL_TOL = 12.0     # 对边平行判定容差（度）
    AXIS_SNAP = 7.0         # 方向吸附到水平/垂直的容差（度）

    # ---------- 基础向量工具 ----------
    @staticmethod
    def _dist(a, b):
        return math.hypot(b[0] - a[0], b[1] - a[1])

    @staticmethod
    def _angle_between(v1, v2):
        """两向量夹角（度，0~180）。"""
        n1 = math.hypot(*v1)
        n2 = math.hypot(*v2)
        if n1 < 1e-9 or n2 < 1e-9:
            return 0.0
        c = max(-1.0, min(1.0, (v1[0] * v2[0] + v1[1] * v2[1]) / (n1 * n2)))
        return math.degrees(math.acos(c))

    @staticmethod
    def _line_angle_diff(a_deg, b_deg):
        """两条直线方向差（度，0~90，无向）。"""
        d = abs(a_deg - b_deg) % 180.0
        return min(d, 180.0 - d)

    @classmethod
    def _mean_axis_angle(cls, angles_lens):
        """按长度加权平均一组直线方向（倍角法回避 0/180 折叠）。输入 [(角度, 权重)]。"""
        sx = sy = 0.0
        for ang, weight in angles_lens:
            rad = math.radians(ang * 2.0)
            sx += math.cos(rad) * weight
            sy += math.sin(rad) * weight
        if abs(sx) < 1e-9 and abs(sy) < 1e-9:
            return angles_lens[0][0]
        return math.degrees(math.atan2(sy, sx)) / 2.0 % 180.0

    @classmethod
    def _snap_axis(cls, angle_deg, tol=None):
        """接近水平/垂直时吸附；返回吸附后的角度。"""
        tol = cls.AXIS_SNAP if tol is None else tol
        a = angle_deg % 180.0
        for target in (0.0, 90.0, 180.0):
            if abs(a - target) <= tol:
                return target % 180.0
        return a

    # ---------- 主入口 ----------
    @classmethod
    def recognize(cls, raw_points):
        try:
            return cls._recognize(raw_points)
        except Exception as exc:
            track_event("smart_shape_error", error=str(exc))
            return None

    @classmethod
    def _recognize(cls, raw_points):
        pts = []
        for p in raw_points:
            xy = (float(p[0]), float(p[1]))
            if not pts or cls._dist(pts[-1], xy) > 0.7:
                pts.append(xy)
        if len(pts) < 8:
            return None
        length = sum(cls._dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1))
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        diag = math.hypot(max(xs) - min(xs), max(ys) - min(ys))
        if length < 40 or diag < 18:
            return None
        line = cls._try_line(pts)
        if line:
            return line
        gap = cls._dist(pts[0], pts[-1])
        if gap > max(22.0, 0.12 * length) or gap > 0.55 * diag:
            return None                      # 既不是直线也没闭合 → 保留笔迹
        loop = cls._resample_closed(pts, cls.RESAMPLE_N)
        if loop is None:
            return None
        loop = cls._smooth_loop(loop, cls.SMOOTH_WINDOW)   # 抹掉抖动毛刺，避免噪声被当成拐角
        corners = cls._detect_corners(loop)
        spec = cls._classify_closed(loop, corners, length)
        return spec

    # ---------- 直线 ----------
    @classmethod
    def _pca(cls, pts):
        n = len(pts)
        mx = sum(p[0] for p in pts) / n
        my = sum(p[1] for p in pts) / n
        sxx = sxy = syy = 0.0
        for x, y in pts:
            dx, dy = x - mx, y - my
            sxx += dx * dx
            sxy += dx * dy
            syy += dy * dy
        sxx /= n; sxy /= n; syy /= n
        tr = sxx + syy
        det = sxx * syy - sxy * sxy
        root = math.sqrt(max(0.0, tr * tr / 4.0 - det))
        l1 = tr / 2.0 + root
        l2 = max(0.0, tr / 2.0 - root)
        if abs(sxy) > 1e-9:
            v = (l1 - syy, sxy)
        elif sxx >= syy:
            v = (1.0, 0.0)
        else:
            v = (0.0, 1.0)
        norm = math.hypot(*v)
        v = (v[0] / norm, v[1] / norm)
        return (mx, my), v, l1, l2

    @classmethod
    def _try_line(cls, pts):
        center, direction, l1, l2 = cls._pca(pts)
        proj = [(p[0] - center[0]) * direction[0] + (p[1] - center[1]) * direction[1] for p in pts]
        lo, hi = min(proj), max(proj)
        extent = hi - lo
        if extent < 26:
            return None
        if math.sqrt(l2) > max(3.5, 0.045 * extent):
            return None
        start = (center[0] + direction[0] * lo, center[1] + direction[1] * lo)
        end = (center[0] + direction[0] * hi, center[1] + direction[1] * hi)
        first, last = pts[0], pts[-1]
        if (last[0] - first[0]) * direction[0] + (last[1] - first[1]) * direction[1] < 0:
            start, end = end, start           # 端点顺序跟随书写方向
        return {"type": "LINE", "points": cls._snap_segment(start, end)}

    @classmethod
    def _snap_segment(cls, start, end):
        """直线方向接近 0/45/90/135 度时吸附摆正（绕中点旋转，长度不变）。"""
        angle = math.degrees(math.atan2(end[1] - start[1], end[0] - start[0])) % 180.0
        target = None
        for cand, tol in ((0.0, 6.0), (90.0, 6.0), (180.0, 6.0), (45.0, 4.0), (135.0, 4.0)):
            if abs(angle - cand) <= tol:
                target = cand % 180.0
                break
        if target is None:
            return [start, end]
        half = cls._dist(start, end) / 2.0
        mx = (start[0] + end[0]) / 2.0
        my = (start[1] + end[1]) / 2.0
        rad = math.radians(target)
        dx, dy = math.cos(rad), math.sin(rad)
        if (end[0] - start[0]) * dx + (end[1] - start[1]) * dy < 0:
            dx, dy = -dx, -dy
        return [(mx - dx * half, my - dy * half), (mx + dx * half, my + dy * half)]

    # ---------- 重采样与拐角 ----------
    @classmethod
    def _resample_closed(cls, pts, n):
        loop_pts = pts + [pts[0]]
        seg_lens = [cls._dist(loop_pts[i], loop_pts[i + 1]) for i in range(len(loop_pts) - 1)]
        total = sum(seg_lens)
        if total < 1e-6:
            return None
        step = total / n
        result = [loop_pts[0]]
        seg_index, seg_used = 0, 0.0
        for _ in range(1, n):
            need = step
            while seg_index < len(seg_lens):
                remain = seg_lens[seg_index] - seg_used
                if remain > need:
                    seg_used += need
                    a, b = loop_pts[seg_index], loop_pts[seg_index + 1]
                    t = seg_used / seg_lens[seg_index]
                    result.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
                    break
                need -= remain
                seg_index += 1
                seg_used = 0.0
            else:
                result.append(loop_pts[-1])
        return result

    @classmethod
    def _smooth_loop(cls, loop, window=5):
        """闭环环形移动平均：窗口很小，只压手抖噪声，真实拐角保持锐利。"""
        n = len(loop)
        half = window // 2
        out = []
        for i in range(n):
            sx = sy = 0.0
            for k in range(-half, half + 1):
                px, py = loop[(i + k) % n]
                sx += px
                sy += py
            out.append((sx / (2 * half + 1), sy / (2 * half + 1)))
        return out

    @classmethod
    def _detect_corners(cls, loop):
        n = len(loop)
        w = cls.CORNER_WINDOW
        turns = []
        for i in range(n):
            a = loop[(i - w) % n]
            b = loop[i]
            c = loop[(i + w) % n]
            turns.append(cls._angle_between((b[0] - a[0], b[1] - a[1]), (c[0] - b[0], c[1] - b[1])))
        candidates = sorted((i for i in range(n) if turns[i] >= cls.CORNER_MIN_TURN),
                            key=lambda i: turns[i], reverse=True)
        picked = []
        for i in candidates:
            if all(min((i - j) % n, (j - i) % n) >= cls.CORNER_NMS for j in picked):
                picked.append(i)
        picked.sort()
        return [(i, turns[i]) for i in picked]

    # ---------- 多边形 ----------
    @classmethod
    def _fit_side_line(cls, loop, i0, i1):
        """取两拐角之间靠中段的点拟合边所在直线，返回 (中心点, 单位方向)。"""
        n = len(loop)
        m = (i1 - i0) % n
        if m < 4:
            a, b = loop[i0], loop[i1 % n]
            d = (b[0] - a[0], b[1] - a[1])
            norm = math.hypot(*d)
            if norm < 1e-9:
                return None
            return a, (d[0] / norm, d[1] / norm)
        trim = max(1, m // 5)
        side_pts = [loop[(i0 + t) % n] for t in range(trim, m - trim + 1)]
        if len(side_pts) < 2:
            side_pts = [loop[i0], loop[i1 % n]]
        center, direction, _, _ = cls._pca(side_pts)
        return center, direction

    @staticmethod
    def _intersect_lines(line_a, line_b):
        (ax, ay), (adx, ady) = line_a
        (bx, by), (bdx, bdy) = line_b
        det = adx * bdy - ady * bdx
        if abs(det) < 1e-6:
            return None
        t = ((bx - ax) * bdy - (by - ay) * bdx) / det
        return (ax + adx * t, ay + ady * t)

    @classmethod
    def _refine_vertices(cls, loop, corner_indices):
        k = len(corner_indices)
        sides = []
        for j in range(k):
            side = cls._fit_side_line(loop, corner_indices[j], corner_indices[(j + 1) % k])
            if side is None:
                return None
            sides.append(side)
        diag = cls._loop_diag(loop)
        vertices = []
        for j in range(k):
            fallback = loop[corner_indices[j]]
            point = cls._intersect_lines(sides[(j - 1) % k], sides[j])
            if point is None or cls._dist(point, fallback) > 0.3 * diag:
                point = fallback
            vertices.append(point)
        return vertices

    @classmethod
    def _loop_diag(cls, loop):
        xs = [p[0] for p in loop]
        ys = [p[1] for p in loop]
        return math.hypot(max(xs) - min(xs), max(ys) - min(ys))

    @classmethod
    def _poly_residual(cls, loop, vertices):
        """重采样点到多边形轮廓的平均距离，衡量拟合好坏。"""
        total = 0.0
        k = len(vertices)
        for p in loop:
            best = float("inf")
            for j in range(k):
                a = vertices[j]
                b = vertices[(j + 1) % k]
                dx, dy = b[0] - a[0], b[1] - a[1]
                len_sq = dx * dx + dy * dy
                if len_sq < 1e-9:
                    d = cls._dist(p, a)
                else:
                    t = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / len_sq))
                    d = math.hypot(p[0] - a[0] - dx * t, p[1] - a[1] - dy * t)
                best = min(best, d)
            total += best
        return total / len(loop)

    # 候选形状的优先级：自由度越少越「标准」，残差接近时优先采用更受约束的那个。
    # 矩形/菱形 5 自由度 < 三角形/平行四边形 6 < 梯形 7。
    SHAPE_PREFERENCE = ("RECT", "DIAMOND", "TRIANGLE", "PARALLELOGRAM", "TRAPEZOID")
    SPECIALIZE_TOL = 1.18      # 更受约束的候选残差不超过最优候选的 1.18 倍即优先采用
    CLEAR_TURN = 40.0          # 「明确拐角」阈值：真圆/真椭圆上根本不会出现这种转角
    POLY_BIAS_STRONG = 0.80    # 明确拐角 ≥3 个时多边形残差打八折再与圆/椭圆比较
    POLY_BIAS_WEAK = 0.90      # 只有弱拐角时的轻度偏向

    @classmethod
    def _classify_closed(cls, loop, corners, stroke_length):
        """闭合笔迹分类：把所有候选形状「先建形、再量残差」，取拟合最好的那个。

        旧实现是一串阈值级联（先看有没有弱拐角就改试圆/椭圆、再按对边平行度分支），
        任何一个阈值擦边就整体走错分支——手绘梯形被判成椭圆、平行四边形被判成三角形
        都出在这里。现在改成：枚举三角形/矩形/菱形/平行四边形/梯形/圆/椭圆的具体形状，
        逐个量「重采样点到该形状轮廓的平均距离」，谁贴得最紧就是谁，阈值只用来兜底否决。
        """
        strong = [c for c in corners if c[1] >= cls.STRONG_TURN]
        if len(corners) >= 5 and len(strong) >= 5:
            return None                       # 五边形及以上：不在支持列表，保留笔迹
        clear = [c for c in corners if c[1] >= cls.CLEAR_TURN]
        diag = max(1e-6, cls._loop_diag(loop))
        poly = cls._best_polygon(loop, corners, diag)
        if poly is not None and poly[1] > min(20.0, max(5.0, 0.02 * stroke_length)):
            poly = None                       # 多边形拟合太糙，交给圆/椭圆或保留笔迹
        round_spec = cls._fit_round(loop)
        round_score = cls._round_residual(loop, round_spec) if round_spec is not None else None
        if poly is None:
            return round_spec
        if round_spec is None:
            return poly[0]
        # 拐角明确时多边形优先：否则一个略歪的梯形常常被椭圆抢走
        if len(clear) >= 3:
            bias = cls.POLY_BIAS_STRONG
        elif len(corners) >= 3:
            bias = cls.POLY_BIAS_WEAK
        else:
            bias = 1.0
        return poly[0] if poly[1] * bias <= round_score else round_spec

    @classmethod
    def _best_polygon(cls, loop, corners, diag):
        """枚举 3/4 顶点的多边形候选并评分，返回 (spec, 残差) 或 None。"""
        if len(corners) < 3:
            return None
        n = len(loop)
        by_strength = [c[0] for c in sorted(corners, key=lambda c: -c[1])]
        index_sets = [tuple(sorted(c[0] for c in corners))] if len(corners) in (3, 4) else []
        for want in (4, 3):
            if len(by_strength) >= want:
                index_sets.append(tuple(sorted(by_strength[:want])))
        if len(corners) == 3:
            # 只找到 3 个拐角时补一个「离三角形轮廓最远」的顶点再试四边形：
            # 手绘平行四边形的钝角常被平滑吃掉，只按 3 点拟合必然退化成三角形。
            base = sorted(c[0] for c in corners)
            tri = cls._refine_vertices(loop, base)
            if tri is not None:
                extra = cls._farthest_index(loop, tri, base, 0.05 * diag)
                if extra is not None:
                    index_sets.append(tuple(sorted(base + [extra])))
        scored = []
        for idx in dict.fromkeys(index_sets):
            if len(idx) < 3 or len(set(idx)) != len(idx):
                continue
            if any(min((a - b) % n, (b - a) % n) < 3 for a, b in zip(idx, idx[1:] + idx[:1])):
                continue                      # 顶点挨得太近，拟合出的边没有意义
            vertices = cls._refine_vertices(loop, list(idx))
            if vertices is None:
                continue
            for spec in cls._shape_candidates(vertices):
                points = spec.get("points") or []
                if len(points) < 3:
                    continue
                # 评分用「未吸附水平/垂直」的原始形状：摆正是有意的美化，
                # 若拿吸附后的形状去比残差，稍微歪一点的矩形就会输给平行四边形。
                score = cls._poly_residual(loop, spec.pop("raw_points", None) or points)
                rank = cls.SHAPE_PREFERENCE.index(spec["type"]) if spec["type"] in cls.SHAPE_PREFERENCE else 99
                scored.append((score, rank, spec))
        if not scored:
            return None
        best = min(s[0] for s in scored)
        tolerance = best * cls.SPECIALIZE_TOL + 0.004 * diag
        eligible = sorted((s for s in scored if s[0] <= tolerance), key=lambda s: (s[1], s[0]))
        chosen = eligible[0]
        return chosen[2], chosen[0]

    @classmethod
    def _farthest_index(cls, loop, vertices, existing, min_distance):
        """找出离给定多边形轮廓最远的重采样点下标（需与已有拐角拉开距离）。"""
        n = len(loop)
        best_index, best_distance = None, min_distance
        for i, p in enumerate(loop):
            if any(min((i - j) % n, (j - i) % n) < cls.CORNER_NMS for j in existing):
                continue
            distance = cls._poly_residual([p], vertices)
            if distance > best_distance:
                best_index, best_distance = i, distance
        return best_index

    @classmethod
    def _shape_candidates(cls, verts):
        """把一组顶点展开成所有可能的标准形状（建形失败的候选自动跳过）。"""
        if len(verts) == 3:
            return [{"type": "TRIANGLE", "points": list(verts)}]
        sides = [(verts[(i + 1) % 4][0] - verts[i][0], verts[(i + 1) % 4][1] - verts[i][1]) for i in range(4)]
        lens = [math.hypot(*s) for s in sides]
        perimeter = sum(lens)
        if perimeter < 1e-6:
            return []
        out = []
        if min(lens) < 0.12 * perimeter:
            # 一条边明显偏短：并掉这条边退化成三角形，作为候选参与评分（不再直接下结论）
            short = lens.index(min(lens))
            merged = ((verts[short][0] + verts[(short + 1) % 4][0]) / 2.0,
                      (verts[short][1] + verts[(short + 1) % 4][1]) / 2.0)
            out.append({"type": "TRIANGLE",
                        "points": [merged if i == short else verts[i] for i in range(4) if i != (short + 1) % 4]})
        builders = (
            ("RECT", cls._build_rect, ()),
            ("DIAMOND", cls._build_diamond, ()),
            ("PARALLELOGRAM", cls._build_parallelogram, None),
            ("TRAPEZOID", cls._build_trapezoid, (True,)),
            ("TRAPEZOID", cls._build_trapezoid, (False,)),
        )
        for name, build, extra in builders:
            try:
                if extra is None:                      # 平行四边形没有摆正步骤
                    out.append({"type": name, "points": build(verts)})
                else:
                    out.append({"type": name, "points": build(verts, *extra, snap=True),
                                "raw_points": build(verts, *extra, snap=False)})
            except Exception:
                continue
        return out

    @classmethod
    def _round_residual(cls, loop, spec):
        """重采样点到拟合圆/椭圆的平均距离，量纲与 _poly_residual 一致，可直接比大小。"""
        cx, cy = spec["center"]
        if spec["type"] == "CIRCLE":
            radius = spec["radius"]
            return sum(abs(cls._dist(p, (cx, cy)) - radius) for p in loop) / len(loop)
        a = max(1e-6, spec["rx"])
        b = max(1e-6, spec["ry"])
        rad = math.radians(spec.get("rotation", 0.0))
        cos_t, sin_t = math.cos(-rad), math.sin(-rad)
        total = 0.0
        for px, py in loop:
            dx, dy = px - cx, py - cy
            x = dx * cos_t - dy * sin_t
            y = dx * sin_t + dy * cos_t
            t = math.atan2(y / b, x / a)
            total += math.hypot(x - a * math.cos(t), y - b * math.sin(t))
        return total / len(loop)

    @classmethod
    def _build_rect(cls, verts, snap=True):
        cx = sum(v[0] for v in verts) / 4.0
        cy = sum(v[1] for v in verts) / 4.0
        sides = [(verts[(i + 1) % 4][0] - verts[i][0], verts[(i + 1) % 4][1] - verts[i][1]) for i in range(4)]
        lens = [math.hypot(*s) for s in sides]
        entries = []
        for i, s in enumerate(sides):
            ang = math.degrees(math.atan2(s[1], s[0]))
            if i % 2 == 1:
                ang += 90.0                    # 邻边旋转 90 度归到同一轴系
            entries.append((ang % 180.0, lens[i]))
        theta = cls._mean_axis_angle(entries)
        if snap:
            theta = cls._snap_axis(theta)
        rad = math.radians(theta)
        u = (math.cos(rad), math.sin(rad))
        v = (-u[1], u[0])
        pu = sorted((p[0] - cx) * u[0] + (p[1] - cy) * u[1] for p in verts)
        pv = sorted((p[0] - cx) * v[0] + (p[1] - cy) * v[1] for p in verts)
        # 每条边上本来就有两个顶点：取「两两平均」而不是最大最小包络，
        # 否则手绘四边形的外扩误差会被整体放大，建出的矩形永远比画的大一圈，
        # 拿去和平行四边形比残差就总是输——手绘矩形被判成平行四边形的根源。
        hw = ((pu[2] + pu[3]) - (pu[0] + pu[1])) / 4.0
        hh = ((pv[2] + pv[3]) - (pv[0] + pv[1])) / 4.0
        return [
            (cx - u[0] * hw - v[0] * hh, cy - u[1] * hw - v[1] * hh),
            (cx + u[0] * hw - v[0] * hh, cy + u[1] * hw - v[1] * hh),
            (cx + u[0] * hw + v[0] * hh, cy + u[1] * hw + v[1] * hh),
            (cx - u[0] * hw + v[0] * hh, cy - u[1] * hw + v[1] * hh),
        ]

    @classmethod
    def _build_diamond(cls, verts, snap=True):
        """标准菱形＝四边等长的平行四边形。

        先按平行四边形求两条边向量（每条都是一对对边的平均，天然带最小二乘的味道），
        再把两者拉到同一长度即可——四边等长时两条对角线自动互相垂直平分。
        早先的实现是「取两条对角线方向、强制正交、按半对角线长重建」：对角线只由
        单个顶点决定，手绘时那两个顶点的误差会被整份放大，建出来的菱形常常明显歪于
        笔迹，于是评分时输给平行四边形——手绘菱形被判成平行四边形的主因。
        """
        cx = sum(v[0] for v in verts) / 4.0
        cy = sum(v[1] for v in verts) / 4.0
        a, b, c, d = verts
        e1 = ((b[0] - a[0] + c[0] - d[0]) / 2.0, (b[1] - a[1] + c[1] - d[1]) / 2.0)
        e2 = ((c[0] - b[0] + d[0] - a[0]) / 2.0, (c[1] - b[1] + d[1] - a[1]) / 2.0)
        n1 = math.hypot(*e1)
        n2 = math.hypot(*e2)
        if n1 < 1e-6 or n2 < 1e-6:
            raise ValueError("degenerate quad")
        side = max(8.0, (n1 + n2) / 2.0)
        e1 = (e1[0] / n1 * side, e1[1] / n1 * side)
        e2 = (e2[0] / n2 * side, e2[1] / n2 * side)
        if snap:
            # 摆正：把较长的那条对角线吸附到水平/垂直（正菱形的观感）
            long_diag = (e1[0] + e2[0], e1[1] + e2[1])
            short_diag = (e2[0] - e1[0], e2[1] - e1[1])
            if math.hypot(*short_diag) > math.hypot(*long_diag):
                long_diag = short_diag
            angle = math.degrees(math.atan2(long_diag[1], long_diag[0])) % 180.0
            snapped = cls._snap_axis(angle)
            if snapped != angle:
                rad = math.radians(snapped - angle)
                cos_r, sin_r = math.cos(rad), math.sin(rad)
                e1 = (e1[0] * cos_r - e1[1] * sin_r, e1[0] * sin_r + e1[1] * cos_r)
                e2 = (e2[0] * cos_r - e2[1] * sin_r, e2[0] * sin_r + e2[1] * cos_r)
        origin = (cx - (e1[0] + e2[0]) / 2.0, cy - (e1[1] + e2[1]) / 2.0)
        return [
            origin,
            (origin[0] + e1[0], origin[1] + e1[1]),
            (origin[0] + e1[0] + e2[0], origin[1] + e1[1] + e2[1]),
            (origin[0] + e2[0], origin[1] + e2[1]),
        ]

    @staticmethod
    def _build_parallelogram(verts):
        a, b, c, d = verts
        e1 = ((b[0] - a[0] + c[0] - d[0]) / 2.0, (b[1] - a[1] + c[1] - d[1]) / 2.0)
        e2 = ((c[0] - b[0] + d[0] - a[0]) / 2.0, (c[1] - b[1] + d[1] - a[1]) / 2.0)
        cx = sum(v[0] for v in verts) / 4.0
        cy = sum(v[1] for v in verts) / 4.0
        a2 = (cx - (e1[0] + e2[0]) / 2.0, cy - (e1[1] + e2[1]) / 2.0)
        b2 = (a2[0] + e1[0], a2[1] + e1[1])
        c2 = (b2[0] + e2[0], b2[1] + e2[1])
        d2 = (a2[0] + e2[0], a2[1] + e2[1])
        return [a2, b2, c2, d2]

    @classmethod
    def _build_trapezoid(cls, verts, pair02, snap=True):
        order = verts if pair02 else verts[1:] + verts[:1]   # 让平行对总是边 0 与边 2
        s0 = (order[1][0] - order[0][0], order[1][1] - order[0][1])
        s2 = (order[3][0] - order[2][0], order[3][1] - order[2][1])
        theta = cls._mean_axis_angle([
            (math.degrees(math.atan2(s0[1], s0[0])), math.hypot(*s0)),
            (math.degrees(math.atan2(s2[1], s2[0])), math.hypot(*s2)),
        ])
        if snap:
            theta = cls._snap_axis(theta)
        rad = math.radians(theta)
        cx = sum(v[0] for v in order) / 4.0
        cy = sum(v[1] for v in order) / 4.0
        cos_t, sin_t = math.cos(-rad), math.sin(-rad)
        local = [((p[0] - cx) * cos_t - (p[1] - cy) * sin_t,
                  (p[0] - cx) * sin_t + (p[1] - cy) * cos_t) for p in order]
        y01 = (local[0][1] + local[1][1]) / 2.0
        y23 = (local[2][1] + local[3][1]) / 2.0
        local = [(local[0][0], y01), (local[1][0], y01), (local[2][0], y23), (local[3][0], y23)]
        cos_b, sin_b = math.cos(rad), math.sin(rad)
        return [(cx + x * cos_b - y * sin_b, cy + x * sin_b + y * cos_b) for x, y in local]

    # ---------- 圆 / 椭圆 ----------
    @staticmethod
    def _solve3(m, rhs):
        """3x3 高斯消元；奇异返回 None。"""
        a = [row[:] + [rhs[i]] for i, row in enumerate(m)]
        for col in range(3):
            pivot = max(range(col, 3), key=lambda r: abs(a[r][col]))
            if abs(a[pivot][col]) < 1e-12:
                return None
            a[col], a[pivot] = a[pivot], a[col]
            for r in range(3):
                if r != col:
                    factor = a[r][col] / a[col][col]
                    for cc in range(col, 4):
                        a[r][cc] -= factor * a[col][cc]
        return [a[i][3] / a[i][i] for i in range(3)]

    @classmethod
    def _fit_round(cls, loop):
        n = len(loop)
        sx = sy = sxx = sxy = syy = sxz = syz = sz = 0.0
        for x, y in loop:
            z = x * x + y * y
            sx += x; sy += y
            sxx += x * x; sxy += x * y; syy += y * y
            sxz += x * z; syz += y * z; sz += z
        sol = cls._solve3([[sxx, sxy, sx], [sxy, syy, sy], [sx, sy, float(n)]], [sxz, syz, sz])
        if sol is not None:
            cx, cy = sol[0] / 2.0, sol[1] / 2.0
            r_sq = sol[2] + cx * cx + cy * cy
            if r_sq > 1.0:
                radius = math.sqrt(r_sq)
                dists = [cls._dist(p, (cx, cy)) for p in loop]
                mean_r = sum(dists) / n
                if mean_r > 8.0:
                    std = math.sqrt(sum((d - mean_r) ** 2 for d in dists) / n)
                    xs = [p[0] for p in loop]
                    ys = [p[1] for p in loop]
                    w = max(xs) - min(xs)
                    h = max(ys) - min(ys)
                    aspect = max(w, h) / max(1e-6, min(w, h))
                    if std / mean_r <= 0.13 and aspect <= 1.42:
                        return {"type": "CIRCLE", "center": (cx, cy), "radius": mean_r}
        return cls._fit_ellipse(loop)

    @classmethod
    def _fit_ellipse(cls, loop):
        center, u1, l1, l2 = cls._pca(loop)
        if l1 < 1e-6:
            return None
        u2 = (-u1[1], u1[0])
        xi = [(p[0] - center[0]) * u1[0] + (p[1] - center[1]) * u1[1] for p in loop]
        eta = [(p[0] - center[0]) * u2[0] + (p[1] - center[1]) * u2[1] for p in loop]
        abs_xi = sorted(abs(v) for v in xi)
        abs_eta = sorted(abs(v) for v in eta)
        idx = int(len(loop) * 0.95)
        a = max(1e-6, abs_xi[min(idx, len(loop) - 1)])
        b = max(1e-6, abs_eta[min(idx, len(loop) - 1)])
        if a < 14.0 or b < 6.0 or a / b > 6.0:
            return None
        err = sum(abs((x / a) ** 2 + (y / b) ** 2 - 1.0) for x, y in zip(xi, eta)) / len(loop)
        if err > 0.24:
            return None
        if b / a >= 0.82:
            return {"type": "CIRCLE", "center": center, "radius": (a + b) / 2.0}
        rotation = math.degrees(math.atan2(u1[1], u1[0])) % 180.0
        snapped = cls._snap_axis(rotation, tol=8.0)
        if snapped == 90.0:
            a, b = b, a                        # 竖椭圆：主轴换到 ry，旋转归零
            snapped = 0.0
        return {"type": "ELLIPSE", "center": center, "rx": a, "ry": b, "rotation": snapped}

# --- 屏幕直尺校准对话框 ---
class RulerCalibrationDialog(QDialog):
    def __init__(self, screen, estimated_px_per_mm, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("calibration_title"))
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        geometry = screen.availableGeometry() if screen else QRectF(0, 0, 900, 600).toRect()
        width = max(520, min(1000, geometry.width() - 80))
        self.setFixedSize(width, 210)
        self.move(geometry.center().x() - width // 2, geometry.center().y() - 105)
        self.line_y = 62.0
        self.left_x = 55.0
        self.right_x = min(width - 55.0, self.left_x + 100.0 * estimated_px_per_mm)
        self.drag_endpoint = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 112, 18, 14)
        row = QHBoxLayout()
        row.addWidget(QLabel(tr("calibration_reference")))
        self.length_input = QDoubleSpinBox()
        self.length_input.setRange(10.0, 1000.0)
        self.length_input.setDecimals(1)
        self.length_input.setValue(100.0)
        self.length_input.setSuffix(" mm")
        row.addWidget(self.length_input)
        row.addStretch()
        layout.addLayout(row)
        hint = QLabel(tr("calibration_hint"))
        layout.addWidget(hint)
        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel_btn = QPushButton(tr("cancel"))
        cancel_btn.clicked.connect(self.reject)
        apply_btn = QPushButton(tr("calibration_apply"))
        apply_btn.clicked.connect(self.accept)
        buttons.addWidget(cancel_btn)
        buttons.addWidget(apply_btn)
        layout.addLayout(buttons)

    def measured_pixels(self):
        return abs(self.right_x - self.left_x)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor("#00cec9"), 3))
        painter.drawLine(QPointF(self.left_x, self.line_y), QPointF(self.right_x, self.line_y))
        painter.setBrush(QColor("#ffb84d"))
        painter.setPen(QPen(QColor("#202020"), 1))
        for x in (self.left_x, self.right_x):
            painter.drawEllipse(QPointF(x, self.line_y), 9, 9)
        painter.setPen(QColor("#f0f0f0"))
        painter.drawText(QRectF(20, 10, self.width() - 40, 24), Qt.AlignmentFlag.AlignCenter, tr("calibration_guide"))
        painter.drawText(QRectF(20, 82, self.width() - 40, 20), Qt.AlignmentFlag.AlignCenter, trf("calibration_length", value=f"{self.measured_pixels():.1f}"))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            point = event.position()
            distances = (abs(point.x() - self.left_x), abs(point.x() - self.right_x))
            if abs(point.y() - self.line_y) <= 20 and min(distances) <= 20:
                self.drag_endpoint = 0 if distances[0] <= distances[1] else 1
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.drag_endpoint is not None and event.buttons() & Qt.MouseButton.LeftButton:
            x = max(25.0, min(self.width() - 25.0, event.position().x()))
            if self.drag_endpoint == 0:
                self.left_x = min(x, self.right_x - 20.0)
            else:
                self.right_x = max(x, self.left_x + 20.0)
            self.update()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self.drag_endpoint = None
        super().mouseReleaseEvent(event)


# --- 1. 全屏画布类 ---
class DrawingCanvas(QMainWindow):
    MAGNIFIER_ZOOM_STEP = 0.5   # 放大倍率步长：每档 50%
    MAGNIFIER_ZOOM_MIN = 1.5
    MAGNIFIER_ZOOM_MAX = 5.0

    # 平面图形：点选确认，值为所需顶点数；立体图形仍用拖拽
    POINT_SHAPES = {
        "LINE": 2, "DASHED_LINE": 2, "RECT": 2, "CIRCLE": 2, "ELLIPSE": 2,
        "TRIANGLE": 3, "PARALLELOGRAM": 3, "TRAPEZOID": 4,
        "DIAMOND": 3, "ANGLE": 3,
    }
    # 「⋯」更多操作只对平面图形开放
    FLAT_TYPES = {"LINE", "DASHED_LINE", "TRIANGLE", "RECT", "PARALLELOGRAM",
                  "TRAPEZOID", "DIAMOND", "CIRCLE", "ELLIPSE", "ANGLE"}
    LINE_SNAP_RADIUS = 18.0   # 直线端点吸附半径（像素，按触控落点精度放宽）

    def __init__(self, panel_ref=None):
        super().__init__()
        self.panel = panel_ref
        # WindowDoesNotAcceptFocus(=WS_EX_NOACTIVATE)：点击画布绘图不触发窗口激活，
        # 画布就永远不会因为被点击而抬升到面板之上——面板被压住的根源之一
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
                            | Qt.WindowType.Tool | Qt.WindowType.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.is_drawing_mode = True
        self.draw_state = "PEN"
        self.eraser_type = "CIRCLE"
        self.all_segments = []
        self.text_items = []
        self.shape_items = []
        self.image_items = []     # 导入的图片/PDF 页：以 PNG→base64 内嵌进项目文件
        self.whiteboard_mode = False
        self.board_style = "WHITE"
        self.content_revision = 0     # O(1) 内容版本号：让实时缩略图看见原地移动/改色/撤销
        self.pages = []
        self.current_page = 0
        self.undo_stack = []
        self.redo_stack = []
        self.undo_limit = 100  # 智能识别的一笔占两步（先回笔迹再回落笔前），额度放宽到100步，
                               # 约对应50次用户操作，在内存占用和实用性之间取得更好平衡
        self.pending_undo = None
        self.last_undo_key = None
        self.shape_type = "LINE"
        self.shape_start = None
        self.preview_shape = None
        self.pending_points = []   # 点选式图形已确认的顶点
        self.selected_ids = set()
        self.selection_rect = None
        self.selection_start = None
        self.drag_start = None
        self.drag_action = None
        self.drag_moved = False
        self.transform_center = None
        self.transform_start_distance = None
        self.transform_start_angle = None
        self.move_originals = None
        self.text_font_size = 24
        self.last_point = None
        self.current_stroke_id = None
        self.current_stroke_widths = []
        self.current_stroke_points = []
        # 批注笔常驻智能识别：随手画自动转标准图形，可在批注设置里关闭
        self.smart_shapes_enabled = True
        # 智能识别的触发方式：笔按着不动停在图形末端 SMART_HOLD_MS 毫秒才定形（抬笔不触发）
        self.pending_smart = None
        self._smart_recognize_timer = None   # 停笔计时器（周期触发，兼作进度环节拍）
        self._hold_anchor = None             # 停笔判定锚点：最近一次「真的移动」到的位置
        self._hold_since = 0.0
        self._hold_active = False            # 笔是否按下且处于停笔判定中
        self._hold_progress = 0.0            # 0~1，笔尖进度环
        # 虚线连击链（连续共线短直线合并为虚线）
        self.dash_chain = None
        self.pen_color = QColor("#ff4757")
        self.pen_width = 4
        self.current_pressure = 1.0
        # 荧光笔：颜色/透明度/粗细独立于批注笔，笔迹长期保留不淡出
        self.marker_color = QColor("#fff200")
        self.marker_alpha = 89          # 约 35%
        self.marker_width = 24
        # 激光笔：只指示不落墨，不触发智能图形
        self.laser_color = QColor("#ff0000")
        self.laser_width = 14
        self.laser_trail = []           # [(QPointF, birth_time), ...]
        self.laser_trail_ms = 450
        # 辅助作图工具（不进撤销栈，可自由移动/缩放/旋转）
        self.aids = []                  # list of dicts
        self.ruler_calibrations = {}    # screen_key -> calibration record
        self.ruler_calibration = None   # 当前屏幕兼容别名
        self.active_aid_id = None
        self.aid_drag = None            # {"id", "mode": move|rotate|scale, "start", ...}
        self.aid_hover_pos = QPointF(-100, -100)
        self.aid_shift_pressed = False
        # 放大镜：进入时冻结一帧屏幕，镜头跟随鼠标
        self.magnifier_zoom = 2.0
        self.magnifier_size = 260
        self.magnifier_pixmap = None
        # 演示聚光灯：暗化全屏，仅在跟随鼠标的圆形亮区透出，滚轮调亮区大小，右键退出
        self.spotlight_radius = 220
        self._spotlight_overlay = None     # 懒加载的暗色叠加 pixmap（带亮区挖洞）
        self.eraser_size = 40
        self.mouse_pos = QPoint(-100, -100)
        self.last_erase_point = None
        self.setMouseTracking(True)
        self.showFullScreen()

    @staticmethod
    def point_to_segment_distance_sq(pos, line):
        px, py = pos.x(), pos.y()
        ax, ay = line.p1().x(), line.p1().y()
        bx, by = line.p2().x(), line.p2().y()
        dx, dy = bx - ax, by - ay
        length_sq = dx * dx + dy * dy
        if length_sq == 0:
            return (px - ax) ** 2 + (py - ay) ** 2
        t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length_sq))
        nearest_x = ax + t * dx
        nearest_y = ay + t * dy
        return (px - nearest_x) ** 2 + (py - nearest_y) ** 2

    @staticmethod
    def segment_center(line):
        return QPointF((line.p1().x() + line.p2().x()) / 2, (line.p1().y() + line.p2().y()) / 2)

    def object_bounds(self, object_id):
        points = []
        for seg in self.all_segments:
            if seg["id"] == object_id:
                line = seg["line"]
                points.extend([QPointF(line.p1()), QPointF(line.p2())])
        for item in self.text_items:
            if item["id"] == object_id:
                return self.text_bounds(item)
        for item in self.shape_items:
            if item["id"] == object_id:
                return self.shape_bounds(item)
        for item in self.image_items:
            if item["id"] == object_id:
                return self.image_bounds(item)
        if not points:
            return QRectF()
        min_x = min(p.x() for p in points)
        min_y = min(p.y() for p in points)
        max_x = max(p.x() for p in points)
        max_y = max(p.y() for p in points)
        return QRectF(QPointF(min_x, min_y), QPointF(max_x, max_y)).adjusted(-8, -8, 8, 8)

    def text_bounds(self, item):
        font = QFont("Microsoft YaHei", item["size"])
        metrics = QFontMetricsF(font)
        rect = metrics.boundingRect(item["text"]).adjusted(-6, -6, 6, 6)
        transform = QTransform()
        transform.translate(item["pos"].x(), item["pos"].y())
        transform.rotate(item["rotation"])
        transform.scale(item["scale"], item["scale"])
        return transform.mapRect(rect)

    def shape_bounds(self, item):
        kind = item.get("kind", "rect")
        if kind == "angle":
            pts = [item["vertex"], item["p1"], item["p2"]]
            xs = [p.x() for p in pts]
            ys = [p.y() for p in pts]
            margin = max(4, item["width"]) + 20   # 留出角度数字的位置
            return QRectF(QPointF(min(xs), min(ys)), QPointF(max(xs), max(ys))).adjusted(-margin, -margin, margin, margin)
        if kind == "poly":
            points = item.get("points") or []
            if not points:
                return QRectF()          # 空多边形（外部文件可能带）不参与包围盒计算
            xs = [p.x() for p in points]
            ys = [p.y() for p in points]
            margin = max(4, item["width"])
            return QRectF(QPointF(min(xs), min(ys)), QPointF(max(xs), max(ys))).adjusted(-margin, -margin, margin, margin)
        if kind == "circle":
            r = item["radius"] + max(4, item["width"])
            c = item["center"]
            return QRectF(c.x() - r, c.y() - r, 2 * r, 2 * r)
        if kind == "ellipse":
            rx, ry = item["rx"], item["ry"]
            rect = QRectF(-rx, -ry, 2 * rx, 2 * ry)
            transform = QTransform()
            transform.translate(item["center"].x(), item["center"].y())
            transform.rotate(item["rotation"])
            margin = max(4, item["width"])
            return transform.mapRect(rect).adjusted(-margin, -margin, margin, margin)
        transform = QTransform()
        center = item["rect"].center()
        transform.translate(center.x(), center.y())
        transform.rotate(item["rotation"])
        transform.translate(-center.x(), -center.y())
        return transform.mapRect(item["rect"].normalized())

    @staticmethod
    def shape_pen(item):
        return QPen(item["color"], max(1, item["width"]),
                    Qt.PenStyle.DashLine if item["type"] == "DASHED_LINE" else Qt.PenStyle.SolidLine,
                    Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)

    @staticmethod
    def angle_span(item):
        """角的有向张角（度，Qt 视觉逆时针为正，范围 (-180, 180]）。"""
        v, p1, p2 = item["vertex"], item["p1"], item["p2"]
        a1 = math.degrees(math.atan2(-(p1.y() - v.y()), p1.x() - v.x()))
        a2 = math.degrees(math.atan2(-(p2.y() - v.y()), p2.x() - v.x()))
        span = (a2 - a1) % 360.0
        if span > 180.0:
            span -= 360.0
        return a1, span

    def draw_shape_item(self, painter, item):
        kind = item.get("kind", "rect")
        if kind == "angle":
            v, p1, p2 = item["vertex"], item["p1"], item["p2"]
            painter.setPen(self.shape_pen(item))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawLine(v, p1)
            painter.drawLine(v, p2)
            len1 = math.hypot(p1.x() - v.x(), p1.y() - v.y())
            len2 = math.hypot(p2.x() - v.x(), p2.y() - v.y())
            radius = max(14.0, min(40.0, 0.35 * min(len1, len2)))
            a1, span = self.angle_span(item)
            arc_rect = QRectF(v.x() - radius, v.y() - radius, radius * 2, radius * 2)
            painter.drawArc(arc_rect, int(a1 * 16), int(span * 16))
            mid = math.radians(a1 + span / 2.0)
            text_pos = QPointF(v.x() + (radius + 15) * math.cos(mid), v.y() - (radius + 15) * math.sin(mid))
            painter.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
            painter.drawText(QRectF(text_pos.x() - 22, text_pos.y() - 10, 44, 20),
                             Qt.AlignmentFlag.AlignCenter, f"{abs(round(span))}°")
            return
        if kind == "poly":
            painter.setPen(self.shape_pen(item))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            polygon = QPolygonF(item["points"])
            if item.get("closed"):
                painter.drawPolygon(polygon)
            else:
                painter.drawPolyline(polygon)
            return
        if kind == "circle":
            painter.setPen(self.shape_pen(item))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            c = item["center"]
            painter.drawEllipse(c, item["radius"], item["radius"])
            painter.drawLine(QPointF(c.x() - 4, c.y()), QPointF(c.x() + 4, c.y()))
            painter.drawLine(QPointF(c.x(), c.y() - 4), QPointF(c.x(), c.y() + 4))
            return
        if kind == "ellipse":
            painter.save()
            painter.translate(item["center"])
            painter.rotate(item["rotation"])
            painter.setPen(self.shape_pen(item))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QPointF(0, 0), item["rx"], item["ry"])
            painter.restore()
            return
        rect = QRectF(item["rect"]).normalized()
        center = rect.center()
        painter.save()
        painter.translate(center)
        painter.rotate(item["rotation"])
        painter.translate(-center)
        painter.setPen(self.shape_pen(item))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        shape = item["type"]
        if shape == "CUBE":
            painter.drawRect(rect)
            offset = min(rect.width(), rect.height()) * 0.18
            back = rect.translated(offset, -offset)
            painter.drawRect(back)
            for a, b in [(rect.topLeft(), back.topLeft()), (rect.topRight(), back.topRight()), (rect.bottomLeft(), back.bottomLeft()), (rect.bottomRight(), back.bottomRight())]:
                painter.drawLine(a, b)
        elif shape == "CUBOID":
            offset = min(rect.width(), rect.height()) * 0.2
            front = QRectF(rect.left(), rect.top() + offset, rect.width() - offset, rect.height() - offset)
            back = QRectF(rect.left() + offset, rect.top(), rect.width() - offset, rect.height() - offset)
            painter.drawRect(front)
            painter.drawRect(back)
            for a, b in [(front.topLeft(), back.topLeft()), (front.topRight(), back.topRight()), (front.bottomLeft(), back.bottomLeft()), (front.bottomRight(), back.bottomRight())]:
                painter.drawLine(a, b)
        elif shape == "CYLINDER":
            h = rect.height() * 0.2
            painter.drawEllipse(QRectF(rect.left(), rect.top(), rect.width(), h))
            painter.drawLine(QPointF(rect.left(), rect.top() + h / 2), QPointF(rect.left(), rect.bottom() - h / 2))
            painter.drawLine(QPointF(rect.right(), rect.top() + h / 2), QPointF(rect.right(), rect.bottom() - h / 2))
            painter.drawEllipse(QRectF(rect.left(), rect.bottom() - h, rect.width(), h))
        elif shape == "CONE":
            h = rect.height() * 0.22
            apex = QPointF(rect.center().x(), rect.top())
            left = QPointF(rect.left(), rect.bottom() - h / 2)
            right = QPointF(rect.right(), rect.bottom() - h / 2)
            painter.drawLine(apex, left)
            painter.drawLine(apex, right)
            painter.drawEllipse(QRectF(rect.left(), rect.bottom() - h, rect.width(), h))
        painter.restore()

    def selection_bounds(self):
        bounds = [self.object_bounds(object_id) for object_id in self.selected_ids]
        bounds = [rect for rect in bounds if not rect.isNull()]
        if not bounds:
            return QRectF()
        result = QRectF(bounds[0])
        for rect in bounds[1:]:
            result = result.united(rect)
        return result

    # 触控大屏上 10px 的手柄用手指基本抓不住，放大到 18px 并加一圈额外容差
    HANDLE_SIZE = 18

    def selection_handles(self):
        rect = self.selection_bounds()
        if rect.isNull():
            return {}
        size = self.HANDLE_SIZE
        half = size / 2
        return {
            "scale": QRectF(rect.right() - half, rect.bottom() - half, size, size),
            "rotate": QRectF(rect.center().x() - half, rect.top() - 38 - half, size, size),
        }

    def hit_selection_handle(self, pos):
        point = QPointF(pos)
        slop = TOUCH_HIT_SLOP
        for name, rect in self.selection_handles().items():
            if rect.adjusted(-slop, -slop, slop, slop).contains(point):
                return name
        return None

    @staticmethod
    def point_angle(center, point):
        return math.degrees(math.atan2(point.y() - center.y(), point.x() - center.x()))

    @staticmethod
    def point_distance(center, point):
        return math.hypot(point.x() - center.x(), point.y() - center.y())

    @staticmethod
    def event_pressure(event):
        try:
            points = event.points()
            if points:
                return max(0.05, float(points[0].pressure()))
        except Exception:
            pass
        return 1.0

    def clone_segments(self):
        return [{"line": QLine(seg["line"]), "pen": QPen(seg["pen"]), "id": seg["id"], "marker": seg.get("marker", False)} for seg in self.all_segments]

    def clone_text_items(self):
        return [
            {
                "id": item["id"],
                "text": item["text"],
                "pos": QPointF(item["pos"]),
                "color": QColor(item["color"]),
                "width": item["width"],
                "size": item["size"],
                "scale": item["scale"],
                "rotation": item["rotation"],
            }
            for item in self.text_items
        ]

    @staticmethod
    def clone_shape(item):
        clone = {
            "id": item["id"],
            "type": item["type"],
            "kind": item.get("kind", "rect"),
            "color": QColor(item["color"]),
            "width": item["width"],
        }
        kind = clone["kind"]
        if kind == "poly":
            clone["points"] = [QPointF(p) for p in item["points"]]
            clone["closed"] = item.get("closed", True)
        elif kind == "angle":
            clone["vertex"] = QPointF(item["vertex"])
            clone["p1"] = QPointF(item["p1"])
            clone["p2"] = QPointF(item["p2"])
        elif kind == "circle":
            clone["center"] = QPointF(item["center"])
            clone["radius"] = item["radius"]
        elif kind == "ellipse":
            clone["center"] = QPointF(item["center"])
            clone["rx"] = item["rx"]
            clone["ry"] = item["ry"]
            clone["rotation"] = item["rotation"]
        else:
            clone["rect"] = QRectF(item["rect"])
            clone["rotation"] = item["rotation"]
        return clone

    def clone_shape_items(self):
        return [self.clone_shape(item) for item in self.shape_items]

    def clone_image(self, item):
        return {
            "id": item["id"],
            "pos": QPointF(item["pos"]),
            "size": QSizeF(item["size"]),
            "rotation": item["rotation"],
            "pixmap": item["pixmap"],   # QPixmap 隐式共享：快照/克隆共享引用，安全
        }

    def clone_image_items(self):
        return [self.clone_image(item) for item in self.image_items]

    def image_bounds(self, item):
        """图片的包围盒（pos 为中心，含旋转）。"""
        width, height = item["size"].width(), item["size"].height()
        rect = QRectF(-width / 2.0, -height / 2.0, width, height)
        transform = QTransform()
        transform.translate(item["pos"].x(), item["pos"].y())
        transform.rotate(item["rotation"])
        return transform.mapRect(rect)

    def capture_page(self):
        return {
            "segments": self.clone_segments(),
            "texts": self.clone_text_items(),
            "shapes": self.clone_shape_items(),
            "images": self.clone_image_items(),
        }

    def live_page(self):
        """当前页的实时内容，直接引用而不克隆——只读场景（实时缩略图）专用。

        capture_page() 会把每条线段/图形/文本深拷贝一份，用来做撤销快照没问题，
        但缩略图每 150ms 就要一次，深拷贝整页会在书写时抢走绘制线程的时间。
        """
        return {"segments": self.all_segments, "shapes": self.shape_items, "texts": self.text_items, "images": self.image_items}

    def mark_content_changed(self):
        """标记页面发生了原地修改，使实时缩略图下一拍必定更新。"""
        self.content_revision += 1
        self.update()

    def content_signature(self):
        """极轻量内容指纹：判断缩略图要不要重画，避免空转重绘。"""
        last = self.all_segments[-1]["line"] if self.all_segments else None
        return (len(self.all_segments), len(self.shape_items), len(self.text_items), len(self.image_items),
                self.current_page, len(self.pages), self.board_style, self.content_revision,
                (last.x2(), last.y2()) if last is not None else None)

    def load_page(self, page):
        self.all_segments = [{"line": QLine(seg["line"]), "pen": QPen(seg["pen"]), "id": seg["id"], "marker": seg.get("marker", False)} for seg in page.get("segments", [])]
        self.text_items = [
            {
                "id": item["id"],
                "text": item["text"],
                "pos": QPointF(item["pos"]),
                "color": QColor(item["color"]),
                "width": item["width"],
                "size": item["size"],
                "scale": item["scale"],
                "rotation": item["rotation"],
            }
            for item in page.get("texts", [])
        ]
        self.shape_items = [self.clone_shape(item) for item in page.get("shapes", [])]
        self.image_items = [self.clone_image(item) for item in page.get("images", [])]
        self.selected_ids.clear()
        self.pending_points = []
        self.dash_chain = None     # 撤销/换页后虚线连击作废
        self.mark_content_changed()

    def ensure_page_state(self):
        if not self.pages:
            self.pages = [self.capture_page()]
            self.current_page = 0

    def save_current_page(self):
        self.ensure_page_state()
        self.pages[self.current_page] = self.capture_page()

    # --- 撤销/重做：整页快照栈，按操作发生的时间顺序回退 ---
    def commit_undo(self, snapshot):
        self.undo_stack.append(snapshot)
        if len(self.undo_stack) > self.undo_limit:
            del self.undo_stack[0]
        self.redo_stack.clear()
        self.last_undo_key = None
        if self.panel:
            self.panel.update_history_ui()

    def push_undo(self, coalesce_key=None):
        """在修改画布内容之前调用，压入当前快照。

        coalesce_key 用于合并连续的同类操作（例如拖动粗细滑块），
        让一整次连续调节只占一个撤销步骤。
        """
        if coalesce_key is not None and coalesce_key == self.last_undo_key and self.undo_stack:
            return
        self.commit_undo(self.capture_page())
        self.last_undo_key = coalesce_key

    def apply_snapshot(self, snapshot):
        # 撤销/重做会整页替换内容：停笔计时、落笔前快照和当前笔画瞬态全部失效。
        # 若不清理，笔还按着时点撤销，650ms 后旧笔迹会以标准图形「复活」并清空重做栈。
        self._cancel_smart_recognition(drop_pending=True)
        self.pending_undo = None
        self.current_stroke_id = None
        self.current_stroke_points = []
        self.current_stroke_widths = []
        self.last_point = None
        self.load_page(snapshot)
        if self.whiteboard_mode:
            self.save_current_page()
        self.last_undo_key = None
        if self.panel:
            self.panel.sync_selection_controls()
            self.panel.position_selection_panel(self.selection_bounds())
            self.panel.update_history_ui()

    def snapshot_differs(self, snapshot):
        # ponytail: QLine/QPen/uuid 的 == 不稳定，用序列化指纹比内容
        return page_signature(snapshot) != page_signature(self.capture_page())

    def undo(self):
        if not self.undo_stack:
            return False
        self.redo_stack.append(self.capture_page())
        self.apply_snapshot(self.undo_stack.pop())
        track_event("undo", depth=len(self.undo_stack))
        return True

    def redo(self):
        if not self.redo_stack:
            return False
        self.undo_stack.append(self.capture_page())
        self.apply_snapshot(self.redo_stack.pop())
        track_event("redo", depth=len(self.redo_stack))
        return True

    def reset_history(self):
        """切页/进出白板时调用：历史属于当前页面，跨页回退没有意义。"""
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.pending_undo = None
        self.last_undo_key = None
        if self.panel:
            self.panel.update_history_ui()

    def enter_whiteboard(self):
        if self.whiteboard_mode:
            return
        self._cancel_smart_recognition(drop_pending=True)  # 进白板：放弃当前页未触发的延迟识别
        self.whiteboard_mode = True
        # 之前用过白板就保留整本页面，只把当前画布内容写回上次停留的那一页。
        # 早先无条件 self.pages = [capture_page()]，导致「建了多页 → 退出白板 → 再进白板」
        # 时第 2 页及以后的内容被悄悄丢弃，且撤销栈也已重置、无法找回。
        if self.pages:
            self.current_page = max(0, min(len(self.pages) - 1, self.current_page))
            self.pages[self.current_page] = self.capture_page()
        else:
            self.pages = [self.capture_page()]
            self.current_page = 0
        self.selected_ids.clear()
        self.reset_history()
        track_event("whiteboard_entered", board_style=self.board_style, pages=len(self.pages))
        self.update()

    def exit_whiteboard(self):
        if not self.whiteboard_mode:
            return
        self._cancel_smart_recognition(drop_pending=True)  # 退白板：放弃未触发的延迟识别
        self.save_current_page()
        self.whiteboard_mode = False
        self.selected_ids.clear()
        self.reset_history()
        track_event("whiteboard_exited", pages=len(self.pages))
        self.update()

    def new_page(self):
        self.enter_whiteboard()
        self._cancel_smart_recognition(drop_pending=True)  # 新页：放弃上一页未触发的延迟识别
        self.save_current_page()
        self.pages.append({"segments": [], "texts": [], "shapes": []})
        self.current_page = len(self.pages) - 1
        self.load_page(self.pages[self.current_page])
        self.reset_history()
        track_event("whiteboard_page_new", page=self.current_page + 1)

    def switch_page(self, offset):
        if not self.whiteboard_mode or not self.pages:
            return
        target = max(0, min(len(self.pages) - 1, self.current_page + offset))
        if target == self.current_page:
            return
        self._cancel_smart_recognition(drop_pending=True)  # 翻页：放弃当前页未触发的延迟识别
        self.save_current_page()
        self.current_page = target
        self.load_page(self.pages[self.current_page])
        self.reset_history()
        track_event("whiteboard_page_changed", page=self.current_page + 1)

    def toggle_board_style(self):
        self.board_style = "BLACK" if self.board_style == "WHITE" else "WHITE"
        track_event("whiteboard_style_changed", board_style=self.board_style)
        self.update()

    def board_background(self):
        if not self.whiteboard_mode:
            return QColor(0, 0, 0, 1)
        return QColor("#f7f7f1") if self.board_style == "WHITE" else QColor("#254237")

    def transformed_point(self, point, center, scale=1.0, rotation=0.0):
        transform = QTransform()
        transform.translate(center.x(), center.y())
        transform.rotate(rotation)
        transform.scale(scale, scale)
        transform.translate(-center.x(), -center.y())
        return transform.map(QPointF(point))

    def select_objects_in_rect(self, rect):
        normalized = QRectF(rect).normalized()
        self.selected_ids.clear()
        for item in self.shape_items:
            if normalized.intersects(self.shape_bounds(item)):
                self.selected_ids.add(item["id"])
        for item in self.image_items:
            if normalized.intersects(self.image_bounds(item)):
                self.selected_ids.add(item["id"])
        self.selection_rect = None
        self.selection_start = None
        if self.panel:
            self.panel.sync_selection_controls()
            self.panel.position_selection_panel(self.selection_bounds())
        track_event("selection_changed", count=len(self.selected_ids))
        self.update()

    def create_text_item(self, pos):
        text, ok = QInputDialog.getText(self, tr("text_input_title"), tr("text_input_label"))
        if not ok or not text:
            return
        item_id = uuid.uuid4()
        item = {
            "id": item_id,
            "text": text,
            "pos": QPointF(pos),
            "color": QColor(self.pen_color),
            "width": max(1, self.pen_width),
            "size": self.text_font_size,
            "scale": 1.0,
            "rotation": 0.0,
        }
        # 文本在「按下即成」流程里：mousePressEvent 已在 3313 行存了 pending_undo = capture_page()
        # （无文本的整页），松开时 mouseReleaseEvent 的 snapshot_differs 守卫会把它 commit 进
        # undo 栈——这与 add_shape_item（finish_shape_item）依赖同一套 pending_undo 机制一致。
        # 因此这里不要重复 push_undo，否则按下捕获一次 + 这里又 capture 一次，会往 undo 栈塞
        # 两份相同的创建前快照，让每个文本创建多占一个空操作的撤销步骤。文本创建本身可被撤销。
        self.text_items.append(item)
        self.selected_ids = {item_id}
        if self.whiteboard_mode:
            self.save_current_page()
        if self.panel:
            self.panel.sync_selection_controls()
            self.panel.position_selection_panel(self.selection_bounds())
        track_event("text_created", length=len(text))
        self.update()

    def make_shape_item(self, rect):
        return {
            "id": uuid.uuid4(),
            "type": self.shape_type,
            "kind": "rect",
            "rect": QRectF(rect).normalized(),
            "color": QColor(self.pen_color),
            "width": max(1, self.pen_width),
            "rotation": 0.0,
        }

    @staticmethod
    def project_to_parallel(anchor, direction, point):
        """把 point 投影到「过 anchor、方向为 direction」的直线上（梯形保平行用）。"""
        dx, dy = direction.x(), direction.y()
        length_sq = dx * dx + dy * dy
        if length_sq == 0:
            return QPointF(point)
        t = ((point.x() - anchor.x()) * dx + (point.y() - anchor.y()) * dy) / length_sq
        return QPointF(anchor.x() + t * dx, anchor.y() + t * dy)

    def build_point_shape(self, shape_type, pts):
        """由顶点序列构造图形。pts 数量不足所需时返回未闭合折线用作预览。"""
        base = {
            "id": uuid.uuid4(),
            "type": shape_type,
            "color": QColor(self.pen_color),
            "width": max(1, self.pen_width),
        }
        required = self.POINT_SHAPES[shape_type]
        pts = [QPointF(p) for p in pts]
        if len(pts) < required:
            return {**base, "kind": "poly", "points": pts, "closed": False} if len(pts) >= 2 else None
        if shape_type in ("LINE", "DASHED_LINE"):
            return {**base, "kind": "poly", "points": pts[:2], "closed": False}
        if shape_type == "TRIANGLE":
            return {**base, "kind": "poly", "points": pts[:3], "closed": True}
        if shape_type == "RECT":
            rect = QRectF(pts[0], pts[1]).normalized()
            return {**base, "kind": "poly", "closed": True,
                    "points": [rect.topLeft(), rect.topRight(), rect.bottomRight(), rect.bottomLeft()]}
        if shape_type == "PARALLELOGRAM":
            a, b, c = pts[:3]
            d = QPointF(a.x() + c.x() - b.x(), a.y() + c.y() - b.y())
            return {**base, "kind": "poly", "points": [a, b, c, d], "closed": True}
        if shape_type == "TRAPEZOID":
            a, b, c = pts[0], pts[1], pts[2]
            direction = QPointF(b.x() - a.x(), b.y() - a.y())
            d = self.project_to_parallel(c, direction, pts[3])   # 第 4 点吸附，保证上下底平行
            return {**base, "kind": "poly", "points": [a, b, c, d], "closed": True}
        if shape_type == "DIAMOND":
            a, c, p = pts[0], pts[1], pts[2]
            center = QPointF((a.x() + c.x()) / 2, (a.y() + c.y()) / 2)
            length = max(1e-6, self.point_distance(a, c))
            ux, uy = (c.x() - a.x()) / length, (c.y() - a.y()) / length
            vx, vy = -uy, ux
            off = (p.x() - center.x()) * vx + (p.y() - center.y()) * vy   # 第三点决定另一条半对角线
            if abs(off) < 6:
                off = 6.0 if off >= 0 else -6.0
            b = QPointF(center.x() + vx * off, center.y() + vy * off)
            d = QPointF(center.x() - vx * off, center.y() - vy * off)
            return {**base, "kind": "poly", "points": [a, b, c, d], "closed": True}
        if shape_type == "ANGLE":
            return {**base, "kind": "angle", "vertex": pts[0], "p1": pts[1], "p2": pts[2]}
        if shape_type == "CIRCLE":
            radius = self.point_distance(pts[0], pts[1])
            return {**base, "kind": "circle", "center": pts[0], "radius": radius}
        if shape_type == "ELLIPSE":
            rx = abs(pts[1].x() - pts[0].x())
            ry = abs(pts[1].y() - pts[0].y())
            return {**base, "kind": "ellipse", "center": pts[0], "rx": rx, "ry": ry, "rotation": 0.0}
        return None

    def add_shape_item(self, item, select=True):
        bounds = self.shape_bounds(item)
        if bounds.width() < 6 and bounds.height() < 6:
            return
        self.shape_items.append(item)
        if select:
            self.selected_ids = {item["id"]}
            if self.panel:
                self.panel.sync_selection_controls()
                self.panel.position_selection_panel(self.selection_bounds())
        if self.whiteboard_mode:
            self.save_current_page()
        track_event("shape_created", shape_type=item["type"])
        self.update()

    def finish_shape_item(self, rect):
        normalized = QRectF(rect).normalized()
        if normalized.width() < 4 and normalized.height() < 4:
            return
        self.add_shape_item(self.make_shape_item(normalized))

    def add_pending_point(self, pos):
        """点选式图形：左键落一个顶点，攒够后成形。画直线时端点自动吸附。"""
        pos = QPointF(pos)
        if self.shape_type in ("LINE", "DASHED_LINE"):
            snapped = self.snap_to_line_endpoint(pos)
            if self.pending_points:
                first = self.pending_points[0]
                if math.hypot(snapped.x() - first.x(), snapped.y() - first.y()) <= 8:
                    snapped = pos              # 两点吸到同一端点会生成零长度线，放弃吸附
                if math.hypot(pos.x() - first.x(), pos.y() - first.y()) <= 8:
                    return                     # 原地双击，忽略这次落点
            pos = snapped
        self.pending_points.append(pos)
        required = self.POINT_SHAPES[self.shape_type]
        if len(self.pending_points) >= required:
            item = self.build_point_shape(self.shape_type, self.pending_points)
            self.pending_points = []
            if item:
                self.add_shape_item(item)
        self.update()

    def cancel_pending_points(self):
        if self.pending_points:
            self.pending_points = []
            track_event("shape_points_cancelled", shape_type=self.shape_type)
            self.update()

    # --- 批注笔常驻识别：笔迹 → 标准图形 ---
    DASH_CHAIN_TIMEOUT = 2.5   # 虚线连击：相邻两段的最大间隔秒数
    DASH_MIN_COUNT = 3         # 连画多少段共线短线后合成虚线

    # --- 「停笔定形」：笔尖停在图形末端不动，才把这一笔换成标准图形 ---
    # 语义必须是「笔还按着、停在原地」，不是「抬笔后等一会儿」：
    # 抬笔后再变形，用户已经在看别处/准备下一笔，图形在眼皮底下自己跳变，既突然又无法
    # 预判，想保留手绘还没有任何办法阻止。改成停笔触发后，规则变成用户完全可控的一句话：
    # 「想要标准图形就停一下笔，想保留手绘就直接抬笔」。
    SMART_HOLD_MS = 650             # 笔停在原地多久触发定形
    SMART_HOLD_TOLERANCE = 6.0      # 停笔判定容差（像素）：手指/笔尖的生理抖动不算移动
    SMART_HOLD_FEEDBACK_MS = 200    # 停多久开始显示笔尖进度环
    SMART_HOLD_TICK_MS = 33         # 进度环刷新节拍
    HOLD_RING_RADIUS = 18.0

    def _hold_timer(self):
        if self._smart_recognize_timer is None:
            self._smart_recognize_timer = QTimer(self)
            self._smart_recognize_timer.setInterval(self.SMART_HOLD_TICK_MS)
            self._smart_recognize_timer.timeout.connect(self._tick_smart_hold)
        return self._smart_recognize_timer

    def _start_smart_hold(self, pos):
        """（重新）开始停笔计时：落笔时、以及每次笔尖真的移动之后。"""
        if self.draw_state != "PEN" or not self.smart_shapes_enabled:
            return
        if self._hold_progress:
            # 先按【旧】锚点擦掉上一个进度环，再挪锚点：顺序反了的话，旧位置那一圈
            # 不在任何失效区域内，会作为残影留在画布上。
            self._hold_progress = 0.0
            self._update_hold_ring()
        self._hold_anchor = QPointF(pos)
        self._hold_since = time.perf_counter()
        self._hold_active = True
        self._hold_timer().start()

    def _track_smart_hold(self, pos):
        """笔尖移出容差就把计时清零重来——只有真正「停住」才会走到定形。

        这里不看 _hold_active：上一次停笔判定若因为「这一笔还不像任何标准图形」而空手
        而归，计时是停着的；用户继续画、再停下时必须能重新判定一次，否则一笔之内只有
        第一次停顿有效，后面怎么停都没反应。
        """
        anchor = self._hold_anchor
        if anchor is None or math.hypot(pos.x() - anchor.x(), pos.y() - anchor.y()) > self.SMART_HOLD_TOLERANCE:
            self._start_smart_hold(pos)

    def _cancel_smart_recognition(self, *, drop_pending=True):
        """停掉停笔计时并抹掉进度环（抬笔 / 切工具 / 翻页 / 撤销清屏都会调用）。"""
        if self._smart_recognize_timer is not None and self._smart_recognize_timer.isActive():
            self._smart_recognize_timer.stop()
        self._hold_active = False
        self._hold_anchor = None
        if self._hold_progress:
            self._hold_progress = 0.0
            self.update()
        if drop_pending:
            self.pending_smart = None

    def _tick_smart_hold(self):
        if (not self._hold_active or self._hold_anchor is None or self.current_stroke_id is None
                or self.draw_state != "PEN" or not self.smart_shapes_enabled):
            self._cancel_smart_recognition()
            return
        held_ms = (time.perf_counter() - self._hold_since) * 1000.0
        if held_ms >= self.SMART_HOLD_MS:
            self._commit_hold_recognition()
            return
        progress = 0.0
        if held_ms >= self.SMART_HOLD_FEEDBACK_MS:
            progress = (held_ms - self.SMART_HOLD_FEEDBACK_MS) / max(1.0, self.SMART_HOLD_MS - self.SMART_HOLD_FEEDBACK_MS)
        if abs(progress - self._hold_progress) > 0.02:
            self._hold_progress = progress
            self._update_hold_ring()

    def _update_hold_ring(self):
        """只重绘笔尖周围那一小块：进度环 30fps 全屏重绘会明显拖慢正在书写的笔迹。"""
        anchor = self._hold_anchor
        if anchor is None:
            self.update()
            return
        reach = int(self.HOLD_RING_RADIUS + 10)
        self.update(int(anchor.x()) - reach, int(anchor.y()) - reach, reach * 2, reach * 2)

    def _commit_hold_recognition(self):
        """停笔到时：就地把这一笔换成标准图形，笔不需要抬起。"""
        stroke_id = self.current_stroke_id
        points = [(p.x(), p.y()) for p in self.current_stroke_points]
        self._cancel_smart_recognition()
        if stroke_id is None or len(points) < 2:
            return
        self.finish_smart_stroke(stroke_id, points)
        if any(seg.get("id") == stroke_id for seg in self.all_segments):
            return          # 没识别成标准图形：原笔迹还在，继续画就是了
        # 已定形。笔可能还按着，就此收束当前这一笔；继续移动会在 mouseMoveEvent 里另起一笔。
        self.current_stroke_id = None
        self.current_stroke_points = []
        self.current_stroke_widths = []
        self.last_point = None
        self.update()

    def _begin_stroke(self, pos, snapshot=False):
        """开始新的一笔。snapshot=True 用于「没抬笔就接着画」的续笔，补一份撤销快照。"""
        self.last_point = pos
        self.current_stroke_id = uuid.uuid4()
        self.current_stroke_widths = []
        self.current_stroke_points = [QPointF(pos)]
        if snapshot and self.pending_undo is None:
            self.pending_undo = self.capture_page()

    def draw_hold_ring(self, painter):
        """笔尖停留进度环：转满一圈这一笔就定形。

        没有这个反馈的话，「停笔变形」在触控大屏上就是一次无法预判的突变；
        有了它，用户能看着它决定「继续停住定形」还是「动一下保留手绘」。
        """
        center = self._hold_anchor
        if center is None:
            return
        radius = self.HOLD_RING_RADIUS
        box = QRectF(center.x() - radius, center.y() - radius, radius * 2, radius * 2)
        painter.save()
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(255, 255, 255, 90), 2.0))
        painter.drawEllipse(box)
        arc_pen = QPen(QColor(self.pen_color), 3.0)
        arc_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(arc_pen)
        painter.drawArc(box, 90 * 16, int(-360 * 16 * max(0.0, min(1.0, self._hold_progress))))
        painter.restore()

    def finish_smart_stroke(self, stroke_id=None, points=None):
        """按给定笔迹识别并替换为标准图形（否则原样保留）。

        撤销做成两步：第一次撤销找回原笔迹（识别错了有退路），
        第二次撤销回到落笔之前。

        调用时机只有一个：笔按着停在原地满 SMART_HOLD_MS（_commit_hold_recognition）。
        此时 pending_undo 还挂着「落笔之前」的快照（mouseRelease 尚未发生），先提交它，
        再提交一份含原笔迹的快照，两次撤销就能依次回到「含原笔迹」与「落笔之前」。
        """
        if stroke_id is None or points is None:
            # 兼容历史调用（无入参）：从当前 stroke 状态取
            stroke_id = self.current_stroke_id
            points = [(p.x(), p.y()) for p in self.current_stroke_points]
        spec = StrokeShapeRecognizer.recognize(points)
        if spec is None:
            self.dash_chain = None         # 非直线笔迹打断虚线连击
            return
        # 先把标准图形构造出来，成功后才动撤销栈和笔迹——构造若出错，笔迹原样保留
        try:
            if spec["type"] == "LINE":
                a, b = (QPointF(x, y) for x, y in spec["points"])
                sa, sb = self.snap_line_pair(a, b)       # 识别出的直线端点吸附（带防焊接保护）
                if math.hypot(sa.x() - sb.x(), sa.y() - sb.y()) > 8:
                    spec = {**spec, "points": [(sa.x(), sa.y()), (sb.x(), sb.y())]}
            item = self.build_recognized_item(spec)
        except Exception as exc:
            track_event("smart_build_failed", shape_type=spec.get("type"), error=str(exc))
            self.dash_chain = None
            return
        if self.pending_undo is not None:
            # 能走到这里说明这一笔已经落进 all_segments，必然不同于落笔前快照；
            # 再做 page_signature 双序列化只会在笔仍按着时冻结主线程。
            self.commit_undo(self.pending_undo)            # 第二步：落笔之前
            self.pending_undo = None
        self.commit_undo(self.capture_page())            # 第一步：带原笔迹
        self.all_segments = [s for s in self.all_segments if s["id"] != stroke_id]
        self.add_shape_item(item, select=False)
        if spec["type"] == "LINE":
            self.update_dash_chain(item)
        else:
            self.dash_chain = None
        track_event("smart_shape", shape_type=spec["type"])

    def build_recognized_item(self, spec):
        base = {
            "id": uuid.uuid4(),
            "type": spec["type"],
            "color": QColor(self.pen_color),
            "width": max(1, self.pen_width),
        }
        kind = spec["type"]
        if kind in ("LINE", "DASHED_LINE"):
            return {**base, "kind": "poly", "closed": False,
                    "points": [QPointF(x, y) for x, y in spec["points"]]}
        if kind in ("TRIANGLE", "RECT", "PARALLELOGRAM", "TRAPEZOID", "DIAMOND"):
            return {**base, "kind": "poly", "closed": True,
                    "points": [QPointF(x, y) for x, y in spec["points"]]}
        if kind == "CIRCLE":
            cx, cy = spec["center"]
            return {**base, "kind": "circle", "center": QPointF(cx, cy), "radius": spec["radius"]}
        cx, cy = spec["center"]
        return {**base, "kind": "ellipse", "center": QPointF(cx, cy),
                "rx": spec["rx"], "ry": spec["ry"], "rotation": spec["rotation"]}

    def update_dash_chain(self, line_item):
        """连续画出 3 段共线且时间相近的短直线时，自动合并成一条虚线。"""
        p1, p2 = line_item["points"][0], line_item["points"][1]
        now = time.monotonic()
        chain = self.dash_chain
        if chain is not None:
            alive = {s["id"] for s in self.shape_items}
            if now - chain["t"] > self.DASH_CHAIN_TIMEOUT or not all(i in alive for i in chain["ids"]):
                chain = None               # 超时或链上的线段已被撤销/擦除
        if chain is not None:
            dx, dy = chain["dir"]
            ax, ay = chain["anchor"]
            seg_angle = math.degrees(math.atan2(p2.y() - p1.y(), p2.x() - p1.x()))
            chain_angle = math.degrees(math.atan2(dy, dx))
            diff = abs(seg_angle - chain_angle) % 180.0
            diff = min(diff, 180.0 - diff)
            mid_x, mid_y = (p1.x() + p2.x()) / 2.0, (p1.y() + p2.y()) / 2.0
            perp = abs(dx * (mid_y - ay) - dy * (mid_x - ax))
            span = max(1.0, chain["hi"] - chain["lo"])
            if diff > 14.0 or perp > max(16.0, 0.05 * span):
                chain = None
        if chain is None:
            length = math.hypot(p2.x() - p1.x(), p2.y() - p1.y())
            if length < 1e-6:
                return
            dx, dy = (p2.x() - p1.x()) / length, (p2.y() - p1.y()) / length
            self.dash_chain = {
                "dir": (dx, dy), "anchor": (p1.x(), p1.y()),
                "lo": 0.0, "hi": length, "t": now,
                "ids": [line_item["id"]], "count": 1,
            }
            return
        dx, dy = chain["dir"]
        ax, ay = chain["anchor"]
        for pt in (p1, p2):
            proj = (pt.x() - ax) * dx + (pt.y() - ay) * dy
            chain["lo"] = min(chain["lo"], proj)
            chain["hi"] = max(chain["hi"], proj)
        chain["ids"].append(line_item["id"])
        chain["count"] += 1
        chain["t"] = now
        self.dash_chain = chain
        if chain["count"] >= self.DASH_MIN_COUNT:
            self.merge_dash_chain()

    def merge_dash_chain(self):
        chain = self.dash_chain
        ids = set(chain["ids"])
        self.shape_items = [s for s in self.shape_items if s["id"] not in ids]
        self.selected_ids -= ids
        dx, dy = chain["dir"]
        ax, ay = chain["anchor"]
        start = QPointF(ax + dx * chain["lo"], ay + dy * chain["lo"])
        end = QPointF(ax + dx * chain["hi"], ay + dy * chain["hi"])
        dashed = {
            "id": uuid.uuid4(), "type": "DASHED_LINE", "kind": "poly", "closed": False,
            "points": [start, end],
            "color": QColor(self.pen_color), "width": max(1, self.pen_width),
        }
        self.shape_items.append(dashed)
        chain["ids"] = [dashed["id"]]      # 后续共线短线继续延长这条虚线
        if self.whiteboard_mode:
            self.save_current_page()
        track_event("smart_dash_merged", segments=chain["count"])
        self.update()

    # --- 直线端点吸附 ---
    def line_endpoints(self, exclude_ids=frozenset()):
        points = []
        for item in self.shape_items:
            if (item.get("kind") == "poly" and not item.get("closed", True)
                    and len(item["points"]) == 2 and item["type"] in ("LINE", "DASHED_LINE")
                    and item["id"] not in exclude_ids):
                points.extend(item["points"])
        return points

    def snap_to_line_endpoint(self, pos, exclude_ids=frozenset()):
        best = None
        best_dist = self.LINE_SNAP_RADIUS
        for p in self.line_endpoints(exclude_ids):
            d = math.hypot(p.x() - pos.x(), p.y() - pos.y())
            if d < best_dist:
                best_dist = d
                best = p
        return QPointF(best) if best is not None else QPointF(pos)

    def _line_snap_candidates(self, exclude_ids=frozenset()):
        """吸附候选：(端点, 所属直线 id, 所属直线方向角)。"""
        out = []
        for item in self.shape_items:
            if (item.get("kind") == "poly" and not item.get("closed", True)
                    and len(item["points"]) == 2 and item["type"] in ("LINE", "DASHED_LINE")
                    and item["id"] not in exclude_ids):
                a, b = item["points"]
                ang = math.degrees(math.atan2(b.y() - a.y(), b.x() - a.x()))
                out.append((a, item["id"], ang))
                out.append((b, item["id"], ang))
        return out

    @staticmethod
    def _angle_diff_line(a_deg, b_deg):
        d = abs(a_deg - b_deg) % 180.0
        return min(d, 180.0 - d)

    def snap_line_pair(self, p1, p2, exclude_ids=frozenset()):
        """整条直线的端点吸附，带防焊接保护：

        - 位移不超过线长的 25%（短线不被大幅拽走）
        - 与目标线近平行（<20°）不吸——否则写等号/排线会被焊成一条
        - 两端都吸向同一条目标线（意味着重合而非连接）时整体放弃
        """
        length = math.hypot(p2.x() - p1.x(), p2.y() - p1.y())
        if length < 1e-6:
            return QPointF(p1), QPointF(p2)
        limit = min(self.LINE_SNAP_RADIUS, 0.25 * length)
        my_ang = math.degrees(math.atan2(p2.y() - p1.y(), p2.x() - p1.x()))
        candidates = self._line_snap_candidates(exclude_ids)

        def best_for(pt):
            found = None
            for target, owner, ang in candidates:
                if self._angle_diff_line(my_ang, ang) < 20.0:
                    continue
                d = math.hypot(target.x() - pt.x(), target.y() - pt.y())
                if d <= limit and (found is None or d < found[0]):
                    found = (d, target, owner)
            return found

        b1, b2 = best_for(p1), best_for(p2)
        if b1 and b2 and b1[2] == b2[2]:
            return QPointF(p1), QPointF(p2)
        return (QPointF(b1[1]) if b1 else QPointF(p1)), (QPointF(b2[1]) if b2 else QPointF(p2))

    def snap_moved_line(self):
        """拖动单条直线松手后：端点靠近其他直线端点则整条平移贴上（近平行不吸）。"""
        if len(self.selected_ids) != 1:
            return
        item = next((s for s in self.shape_items if s["id"] in self.selected_ids), None)
        if (not item or item.get("kind") != "poly" or item.get("closed", True)
                or len(item["points"]) != 2 or item["type"] not in ("LINE", "DASHED_LINE")):
            return
        p1, p2 = item["points"]
        length = math.hypot(p2.x() - p1.x(), p2.y() - p1.y())
        if length < 1e-6:
            return
        limit = min(self.LINE_SNAP_RADIUS, 0.25 * length)
        my_ang = math.degrees(math.atan2(p2.y() - p1.y(), p2.x() - p1.x()))
        best = None
        for endpoint in (p1, p2):
            for target, owner, ang in self._line_snap_candidates({item["id"]}):
                if self._angle_diff_line(my_ang, ang) < 20.0:
                    continue   # 想摆一条近平行线，不是想接上去
                d = math.hypot(target.x() - endpoint.x(), target.y() - endpoint.y())
                if d <= limit and (best is None or d < best[0]):
                    best = (d, target.x() - endpoint.x(), target.y() - endpoint.y())
        if best:
            item["points"] = [QPointF(p.x() + best[1], p.y() + best[2]) for p in item["points"]]
            self.update()

    # --- 点选命中：框选模式下单击直接选中对象 ---
    @staticmethod
    def _point_segment_dist(px, py, ax, ay, bx, by):
        dx, dy = bx - ax, by - ay
        len_sq = dx * dx + dy * dy
        if len_sq < 1e-9:
            return math.hypot(px - ax, py - ay)
        t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / len_sq))
        return math.hypot(px - ax - dx * t, py - ay - dy * t)

    def hit_object_at(self, pos):
        px, py = float(pos.x()), float(pos.y())
        # 命中顺序与绘制顺序（draw_content：segments → images → shapes → texts）严格相反，
        # 这样点击重叠区域时命中的的是视觉上最上层的对象，而非固定某一类。
        # 文本画在最上层，因此最优先；笔迹最底层，最后才命中。
        for item in reversed(self.text_items):
            if self.text_bounds(item).contains(QPointF(pos)):
                return item["id"]
        # 容差按触控手指的落点精度放宽（TOUCH_HIT_SLOP）：细线图形在大屏上用手指点，
        # 8px 的判定几乎点不中，只能反复戳。
        for item in reversed(self.shape_items):          # 图形优先，后画的在上
            if self._shape_outline_hit(px, py, item, max(float(TOUCH_HIT_SLOP), item["width"] + 5.0)):
                return item["id"]
        for item in reversed(self.image_items):          # 图片按外接包围盒命中
            if self.image_bounds(item).contains(QPointF(pos)):
                return item["id"]
        for seg in reversed(self.all_segments):
            line = seg["line"]
            tol = max(float(TOUCH_HIT_SLOP), seg["pen"].width() / 2.0 + 4.0)
            if self._point_segment_dist(px, py, line.p1().x(), line.p1().y(), line.p2().x(), line.p2().y()) <= tol:
                return seg["id"]
        return None

    def _shape_outline_hit(self, px, py, item, tol):
        """点 pos 是否落在图形轮廓/边线容差内（execute_erase 与点选共用，保证擦除与命中一致）。

        多边形/圆/椭圆/角等「空心轮廓」图形只接受点击真正靠近边线的情况，
        而不是落在空外接矩形内就命中——否则擦除会误删内部空白的相邻图形。
        立体图形（rect kind）是边线+辅助线的框架结构，按外接包围盒命中。
        """
        kind = item.get("kind", "rect")
        if kind == "poly":
            pts = item["points"]
            n = len(pts)
            count = n if item.get("closed", True) and n > 2 else max(0, n - 1)
            for i in range(count):
                a, b = pts[i], pts[(i + 1) % n]
                if self._point_segment_dist(px, py, a.x(), a.y(), b.x(), b.y()) <= tol:
                    return True
            return False
        if kind == "angle":
            v = item["vertex"]
            for p in (item["p1"], item["p2"]):
                if self._point_segment_dist(px, py, v.x(), v.y(), p.x(), p.y()) <= tol:
                    return True
            return False
        if kind == "circle":
            return abs(math.hypot(px - item["center"].x(), py - item["center"].y()) - item["radius"]) <= tol
        if kind == "ellipse":
            rad = math.radians(item["rotation"])
            dx, dy = px - item["center"].x(), py - item["center"].y()
            xi = dx * math.cos(rad) + dy * math.sin(rad)
            eta = -dx * math.sin(rad) + dy * math.cos(rad)
            rx, ry = max(1e-6, item["rx"]), max(1e-6, item["ry"])
            return abs(math.hypot(xi / rx, eta / ry) - 1.0) * min(rx, ry) <= tol
        # 立体图形框架：按外接包围盒命中
        return self.shape_bounds(item).contains(QPointF(px, py))

    # --- 复制 / 删除选中对象 ---
    def duplicate_selection(self):
        if not self.selected_ids:
            return
        self.push_undo()
        bounds = self.selection_bounds()
        dx, dy = bounds.width() + 14.0, 0.0
        if bounds.right() + dx > self.width() - 4:    # 右边放不下→左边→下面→上面→原地错位
            if bounds.left() - dx >= 4:
                dx = -dx
            else:
                dx, dy = 0.0, bounds.height() + 14.0
                if bounds.bottom() + dy > self.height() - 4:
                    if bounds.top() - dy >= 4:
                        dy = -dy
                    else:
                        dx, dy = 14.0, 14.0   # 大对象四面都放不下：错位叠放，保证副本可见
        delta = QPointF(dx, dy)
        new_ids = set()
        stroke_map = {}
        for seg in list(self.all_segments):
            if seg["id"] in self.selected_ids:
                if seg["id"] not in stroke_map:
                    stroke_map[seg["id"]] = uuid.uuid4()
                line = seg["line"]
                self.all_segments.append({
                    "line": QLine(round(line.p1().x() + dx), round(line.p1().y() + dy),
                                  round(line.p2().x() + dx), round(line.p2().y() + dy)),
                    "pen": QPen(seg["pen"]), "id": stroke_map[seg["id"]], "marker": seg.get("marker", False),
                })
        new_ids.update(stroke_map.values())
        for item in list(self.text_items):
            if item["id"] in self.selected_ids:
                clone = {**item, "id": uuid.uuid4(), "pos": QPointF(item["pos"].x() + dx, item["pos"].y() + dy),
                         "color": QColor(item["color"])}
                self.text_items.append(clone)
                new_ids.add(clone["id"])
        for item in list(self.shape_items):
            if item["id"] in self.selected_ids:
                clone = self.clone_shape(item)
                clone["id"] = uuid.uuid4()
                kind = clone.get("kind", "rect")
                if kind == "poly":
                    clone["points"] = [QPointF(p.x() + dx, p.y() + dy) for p in clone["points"]]
                elif kind == "angle":
                    for key in ("vertex", "p1", "p2"):
                        clone[key] = QPointF(clone[key].x() + dx, clone[key].y() + dy)
                elif kind in ("circle", "ellipse"):
                    clone["center"] = QPointF(clone["center"].x() + dx, clone["center"].y() + dy)
                else:
                    clone["rect"] = clone["rect"].translated(delta)
                self.shape_items.append(clone)
                new_ids.add(clone["id"])
        for item in list(self.image_items):
            if item["id"] in self.selected_ids:
                clone = self.clone_image(item)
                clone["id"] = uuid.uuid4()
                clone["pos"] = QPointF(clone["pos"].x() + dx, clone["pos"].y() + dy)
                self.image_items.append(clone)
                new_ids.add(clone["id"])
        self.selected_ids = new_ids
        if self.whiteboard_mode:
            self.save_current_page()
        if self.panel:
            self.panel.sync_selection_controls()
            self.panel.position_selection_panel(self.selection_bounds())
        track_event("selection_duplicated", count=len(new_ids))
        self.update()

    def delete_selection(self):
        if not self.selected_ids:
            return
        self.push_undo()
        self.all_segments = [s for s in self.all_segments if s["id"] not in self.selected_ids]
        self.text_items = [t for t in self.text_items if t["id"] not in self.selected_ids]
        self.shape_items = [s for s in self.shape_items if s["id"] not in self.selected_ids]
        self.image_items = [i for i in self.image_items if i["id"] not in self.selected_ids]
        count = len(self.selected_ids)
        self.selected_ids = set()
        if self.whiteboard_mode:
            self.save_current_page()
        if self.panel:
            self.panel.sync_selection_controls()
            self.panel.position_selection_panel(QRectF())
        track_event("selection_deleted", count=count)
        self.update()

    def single_flat_shape(self):
        """「⋯」按钮可用条件：恰好选中一个平面图形。"""
        if len(self.selected_ids) != 1:
            return None
        sid = next(iter(self.selected_ids))
        item = next((s for s in self.shape_items if s["id"] == sid), None)
        if item and item["type"] in self.FLAT_TYPES:
            return item
        return None

    # --- 「⋯」几何构造：每类图形的常用操作 ---
    def _aux_line(self, src, a, b, dashed=True):
        return {"id": uuid.uuid4(), "type": "DASHED_LINE" if dashed else "LINE", "kind": "poly",
                "closed": False, "points": [QPointF(a[0], a[1]), QPointF(b[0], b[1])],
                "color": QColor(src["color"]), "width": max(1, src["width"])}

    def _aux_circle(self, src, center, radius):
        return {"id": uuid.uuid4(), "type": "CIRCLE", "kind": "circle",
                "center": QPointF(center[0], center[1]), "radius": max(2.0, radius),
                "color": QColor(src["color"]), "width": max(1, src["width"])}

    def _aux_poly(self, src, pts, dashed=False, type_=None):
        return {"id": uuid.uuid4(), "type": type_ or ("DASHED_LINE" if dashed else "LINE"), "kind": "poly",
                "closed": True, "points": [QPointF(p[0], p[1]) for p in pts],
                "color": QColor(src["color"]), "width": max(1, src["width"])}

    def _aux_cross(self, src, center, size=7.0):
        cx, cy = center
        return [self._aux_line(src, (cx - size, cy), (cx + size, cy), dashed=False),
                self._aux_line(src, (cx, cy - size), (cx, cy + size), dashed=False)]

    # 值是 i18n key，取用时再翻译，避免把中文钉死在数据表里。
    SHAPE_OPS = {
        "TRIANGLE": [("circumcircle", "op_circumcircle"), ("incircle", "op_incircle"), ("medians", "op_medians"),
                     ("altitudes", "op_altitudes"), ("midsegment", "op_midsegment")],
        "RECT": [("diagonals", "op_diagonals"), ("circumcircle", "op_circumcircle"), ("incircle", "op_incircle"), ("center", "op_center")],
        "PARALLELOGRAM": [("diagonals", "op_diagonals"), ("center", "op_center")],
        "TRAPEZOID": [("diagonals", "op_diagonals"), ("height", "op_height")],
        "DIAMOND": [("diagonals", "op_diagonals"), ("incircle", "op_incircle"), ("center", "op_center")],
        "CIRCLE": [("diameter", "op_diameter"), ("radius", "op_radius"), ("inscribed_square", "op_inscribed_square"),
                   ("circumscribed_square", "op_circumscribed_square"), ("inscribed_triangle", "op_inscribed_triangle")],
        "ELLIPSE": [("axes", "op_axes"), ("foci", "op_foci")],
        "LINE": [("midpoint", "op_midpoint"), ("perp_bisector", "op_perp_bisector")],
        "DASHED_LINE": [("midpoint", "op_midpoint"), ("perp_bisector", "op_perp_bisector")],
    }

    def shape_op_list(self, item):
        """返回 [(操作key, 已翻译的菜单文字)]。"""
        return [(key, tr(label_key)) for key, label_key in self.SHAPE_OPS.get(item["type"], [])]

    def apply_shape_op(self, item, op):
        new_items = self._make_op_items(item, op)
        if not new_items:
            return
        self.push_undo()
        for aux in new_items:
            self.add_shape_item(aux, select=False)
        track_event("shape_op", shape_type=item["type"], op=op)

    def _make_op_items(self, item, op):
        try:
            return self._make_op_items_unsafe(item, op) or []
        except Exception as exc:
            track_event("shape_op_failed", op=op, error=str(exc))
            return []

    def _make_op_items_unsafe(self, item, op):
        kind = item.get("kind", "rect")
        # 只有多边形才有顶点表；旧版本/外部文件里 RECT 可能是 kind="rect"，
        # 那时 pts 必须是空表而不是未定义（否则整个函数 UnboundLocalError，
        # 被 _make_op_items 吞掉后「⋯」菜单点了毫无反应且只留一条失败埋点）。
        pts = [(p.x(), p.y()) for p in item["points"]] if kind == "poly" else []
        if item["type"] == "TRIANGLE":
            if len(pts) < 3:
                return []
            a, b, c = pts[0], pts[1], pts[2]
            if op == "circumcircle":
                d = 2.0 * (a[0] * (b[1] - c[1]) + b[0] * (c[1] - a[1]) + c[0] * (a[1] - b[1]))
                if abs(d) < 1e-9:
                    return []
                ux = ((a[0] ** 2 + a[1] ** 2) * (b[1] - c[1]) + (b[0] ** 2 + b[1] ** 2) * (c[1] - a[1])
                      + (c[0] ** 2 + c[1] ** 2) * (a[1] - b[1])) / d
                uy = ((a[0] ** 2 + a[1] ** 2) * (c[0] - b[0]) + (b[0] ** 2 + b[1] ** 2) * (a[0] - c[0])
                      + (c[0] ** 2 + c[1] ** 2) * (b[0] - a[0])) / d
                return [self._aux_circle(item, (ux, uy), math.hypot(a[0] - ux, a[1] - uy))]
            if op == "incircle":
                la = math.hypot(b[0] - c[0], b[1] - c[1])
                lb = math.hypot(a[0] - c[0], a[1] - c[1])
                lc = math.hypot(a[0] - b[0], a[1] - b[1])
                perimeter = la + lb + lc
                if perimeter < 1e-9:
                    return []
                ix = (la * a[0] + lb * b[0] + lc * c[0]) / perimeter
                iy = (la * a[1] + lb * b[1] + lc * c[1]) / perimeter
                area = abs((b[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (b[1] - a[1])) / 2.0
                return [self._aux_circle(item, (ix, iy), 2.0 * area / perimeter)]
            if op == "medians":
                out = []
                for i in range(3):
                    v = pts[i]
                    o1, o2 = pts[(i + 1) % 3], pts[(i + 2) % 3]
                    mid = ((o1[0] + o2[0]) / 2, (o1[1] + o2[1]) / 2)
                    out.append(self._aux_line(item, v, mid))
                return out
            if op == "altitudes":
                out = []
                for i in range(3):
                    v = pts[i]
                    o1, o2 = pts[(i + 1) % 3], pts[(i + 2) % 3]
                    dx, dy = o2[0] - o1[0], o2[1] - o1[1]
                    len_sq = dx * dx + dy * dy
                    if len_sq < 1e-9:
                        continue
                    t = ((v[0] - o1[0]) * dx + (v[1] - o1[1]) * dy) / len_sq
                    foot = (o1[0] + dx * t, o1[1] + dy * t)
                    out.append(self._aux_line(item, v, foot))
                return out
            if op == "midsegment":
                mids = [((pts[i][0] + pts[(i + 1) % 3][0]) / 2, (pts[i][1] + pts[(i + 1) % 3][1]) / 2) for i in range(3)]
                return [self._aux_poly(item, mids, type_="DASHED_LINE")]
        if item["type"] in ("RECT", "PARALLELOGRAM", "TRAPEZOID", "DIAMOND"):
            if len(pts) < 4:
                return []
            cx = sum(p[0] for p in pts) / 4.0
            cy = sum(p[1] for p in pts) / 4.0
            if op == "diagonals":
                return [self._aux_line(item, pts[0], pts[2]), self._aux_line(item, pts[1], pts[3])]
            if op == "center":
                return self._aux_cross(item, (cx, cy))
            if op == "circumcircle":     # 矩形：过四顶点
                return [self._aux_circle(item, (cx, cy), math.hypot(pts[0][0] - cx, pts[0][1] - cy))]
            if op == "incircle":
                if item["type"] == "DIAMOND":
                    side = math.hypot(pts[1][0] - pts[0][0], pts[1][1] - pts[0][1])
                    d1 = math.hypot(pts[2][0] - pts[0][0], pts[2][1] - pts[0][1])
                    d2 = math.hypot(pts[3][0] - pts[1][0], pts[3][1] - pts[1][1])
                    if side < 1e-9:
                        return []
                    return [self._aux_circle(item, (cx, cy), (d1 * d2 / 4.0) / side)]
                l0 = math.hypot(pts[1][0] - pts[0][0], pts[1][1] - pts[0][1])
                l1 = math.hypot(pts[2][0] - pts[1][0], pts[2][1] - pts[1][1])
                return [self._aux_circle(item, (cx, cy), min(l0, l1) / 2.0)]
            if op == "height":           # 梯形：从上底中点向下底所在直线作垂线
                top_mid = ((pts[2][0] + pts[3][0]) / 2, (pts[2][1] + pts[3][1]) / 2)
                dx, dy = pts[1][0] - pts[0][0], pts[1][1] - pts[0][1]
                len_sq = dx * dx + dy * dy
                if len_sq < 1e-9:
                    return []
                t = ((top_mid[0] - pts[0][0]) * dx + (top_mid[1] - pts[0][1]) * dy) / len_sq
                foot = (pts[0][0] + dx * t, pts[0][1] + dy * t)
                return [self._aux_line(item, top_mid, foot)]
        if item["type"] == "CIRCLE":
            c = (item["center"].x(), item["center"].y())
            r = item["radius"]
            if op == "diameter":
                return [self._aux_line(item, (c[0] - r, c[1]), (c[0] + r, c[1]), dashed=False)]
            if op == "radius":
                return [self._aux_line(item, c, (c[0] + r, c[1]), dashed=False)]
            if op == "inscribed_square":
                corners = [(c[0] + r * math.cos(math.radians(deg)), c[1] + r * math.sin(math.radians(deg)))
                           for deg in (45, 135, 225, 315)]
                return [self._aux_poly(item, corners)]
            if op == "circumscribed_square":
                return [self._aux_poly(item, [(c[0] - r, c[1] - r), (c[0] + r, c[1] - r),
                                              (c[0] + r, c[1] + r), (c[0] - r, c[1] + r)])]
            if op == "inscribed_triangle":
                corners = [(c[0] + r * math.cos(math.radians(deg)), c[1] + r * math.sin(math.radians(deg)))
                           for deg in (-90, 30, 150)]
                return [self._aux_poly(item, corners)]
        if item["type"] == "ELLIPSE":
            c = (item["center"].x(), item["center"].y())
            rad = math.radians(item["rotation"])
            u = (math.cos(rad), math.sin(rad))
            v = (-u[1], u[0])
            rx, ry = item["rx"], item["ry"]
            if op == "axes":
                return [self._aux_line(item, (c[0] - u[0] * rx, c[1] - u[1] * rx), (c[0] + u[0] * rx, c[1] + u[1] * rx)),
                        self._aux_line(item, (c[0] - v[0] * ry, c[1] - v[1] * ry), (c[0] + v[0] * ry, c[1] + v[1] * ry))]
            if op == "foci":
                if abs(rx - ry) < 1e-6:
                    return self._aux_cross(item, c)
                focus = math.sqrt(abs(rx * rx - ry * ry))
                axis = u if rx >= ry else v
                out = []
                for sign in (1, -1):
                    out.extend(self._aux_cross(item, (c[0] + axis[0] * focus * sign, c[1] + axis[1] * focus * sign), size=5))
                return out
        if item["type"] in ("LINE", "DASHED_LINE") and kind == "poly" and len(item["points"]) == 2:
            a, b = pts[0], pts[1]
            mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
            if op == "midpoint":
                return self._aux_cross(item, mid)
            if op == "perp_bisector":
                length = math.hypot(b[0] - a[0], b[1] - a[1])
                if length < 1e-9:
                    return []
                nx, ny = -(b[1] - a[1]) / length, (b[0] - a[0]) / length
                half = max(30.0, length * 0.4)
                return [self._aux_line(item, (mid[0] - nx * half, mid[1] - ny * half),
                                       (mid[0] + nx * half, mid[1] + ny * half))]
        return []

    # --- 角：角度调整与角平分线 ---
    def adjust_angle_item(self, item, delta=None, target=None):
        a1, span = self.angle_span(item)
        magnitude = abs(span)
        sign = 1.0 if span >= 0 else -1.0
        new_mag = max(5.0, min(175.0, (magnitude + delta) if delta is not None else float(target)))
        if abs(new_mag - magnitude) < 0.01:
            return
        self.push_undo(coalesce_key=f"angle_{item['id']}")
        v = item["vertex"]
        ray_len = math.hypot(item["p2"].x() - v.x(), item["p2"].y() - v.y())
        new_angle = math.radians(a1 + sign * new_mag)
        item["p2"] = QPointF(v.x() + ray_len * math.cos(new_angle), v.y() - ray_len * math.sin(new_angle))
        if self.whiteboard_mode:
            self.save_current_page()
        track_event("angle_adjusted", degrees=round(new_mag))
        self.update()

    def angle_bisector_item(self, item):
        v = item["vertex"]
        a1, span = self.angle_span(item)
        mid = math.radians(a1 + span / 2.0)
        length = min(math.hypot(item["p1"].x() - v.x(), item["p1"].y() - v.y()),
                     math.hypot(item["p2"].x() - v.x(), item["p2"].y() - v.y()))
        end = (v.x() + length * math.cos(mid), v.y() - length * math.sin(mid))
        self.push_undo()
        self.add_shape_item(self._aux_line(item, (v.x(), v.y()), end), select=False)
        track_event("shape_op", shape_type="ANGLE", op="bisector")

    def capture_selection_state(self):
        return {
            "segments": [
                {
                    "index": i,
                    "line": QLine(seg["line"]),
                    "pen": QPen(seg["pen"]),
                }
                for i, seg in enumerate(self.all_segments)
                if seg["id"] in self.selected_ids
            ],
            "texts": [
                {
                    "index": i,
                    "pos": QPointF(item["pos"]),
                    "scale": item["scale"],
                    "rotation": item["rotation"],
                    "size": item["size"],
                    "width": item["width"],
                    "color": QColor(item["color"]),
                }
                for i, item in enumerate(self.text_items)
                if item["id"] in self.selected_ids
            ],
            "shapes": [
                {"index": i, "item": self.clone_shape(item)}
                for i, item in enumerate(self.shape_items)
                if item["id"] in self.selected_ids
            ],
        }

    def restore_selection_state(self, state):
        for saved in state["segments"]:
            self.all_segments[saved["index"]]["line"] = QLine(saved["line"])
            self.all_segments[saved["index"]]["pen"] = QPen(saved["pen"])
        for saved in state["texts"]:
            item = self.text_items[saved["index"]]
            item["pos"] = QPointF(saved["pos"])
            item["scale"] = saved["scale"]
            item["rotation"] = saved["rotation"]
            item["size"] = saved["size"]
            item["width"] = saved["width"]
            item["color"] = QColor(saved["color"])
        for saved in state.get("shapes", []):
            # 重新克隆，避免拖动过程中的原地修改污染保存的原始状态
            self.shape_items[saved["index"]] = self.clone_shape(saved["item"])

    def move_selection(self, delta):
        for seg in self.all_segments:
            if seg["id"] in self.selected_ids:
                line = seg["line"]
                seg["line"] = QLine(
                    round(line.p1().x() + delta.x()), round(line.p1().y() + delta.y()),
                    round(line.p2().x() + delta.x()), round(line.p2().y() + delta.y()),
                )
        for item in self.text_items:
            if item["id"] in self.selected_ids:
                item["pos"] = QPointF(item["pos"].x() + delta.x(), item["pos"].y() + delta.y())
        for item in self.image_items:
            if item["id"] in self.selected_ids:
                item["pos"] = QPointF(item["pos"].x() + delta.x(), item["pos"].y() + delta.y())
        for item in self.shape_items:
            if item["id"] in self.selected_ids:
                kind = item.get("kind", "rect")
                if kind == "poly":
                    item["points"] = [QPointF(p.x() + delta.x(), p.y() + delta.y()) for p in item["points"]]
                elif kind == "angle":
                    for key in ("vertex", "p1", "p2"):
                        item[key] = QPointF(item[key].x() + delta.x(), item[key].y() + delta.y())
                elif kind in ("circle", "ellipse"):
                    item["center"] = QPointF(item["center"].x() + delta.x(), item["center"].y() + delta.y())
                else:
                    item["rect"] = item["rect"].translated(delta)
        self.mark_content_changed()

    def scale_selection(self, factor, emit_event=True):
        if not self.selected_ids:
            return
        center = self.selection_bounds().center()
        for seg in self.all_segments:
            if seg["id"] in self.selected_ids:
                p1 = self.transformed_point(seg["line"].p1(), center, scale=factor)
                p2 = self.transformed_point(seg["line"].p2(), center, scale=factor)
                seg["line"] = QLine(round(p1.x()), round(p1.y()), round(p2.x()), round(p2.y()))
                pen = QPen(seg["pen"])
                pen.setWidth(max(1, round(pen.width() * factor)))
                seg["pen"] = pen
        for item in self.text_items:
            if item["id"] in self.selected_ids:
                item["pos"] = self.transformed_point(item["pos"], center, scale=factor)
                item["scale"] = max(0.2, item["scale"] * factor)
        for item in self.image_items:
            if item["id"] in self.selected_ids:
                item["pos"] = self.transformed_point(item["pos"], center, scale=factor)
                item["size"] = QSizeF(max(1.0, item["size"].width() * factor),
                                      max(1.0, item["size"].height() * factor))
        for item in self.shape_items:
            if item["id"] in self.selected_ids:
                kind = item.get("kind", "rect")
                if kind == "poly":
                    item["points"] = [self.transformed_point(p, center, scale=factor) for p in item["points"]]
                elif kind == "angle":
                    for key in ("vertex", "p1", "p2"):
                        item[key] = self.transformed_point(item[key], center, scale=factor)
                elif kind == "circle":
                    item["center"] = self.transformed_point(item["center"], center, scale=factor)
                    item["radius"] = item["radius"] * factor
                elif kind == "ellipse":
                    item["center"] = self.transformed_point(item["center"], center, scale=factor)
                    item["rx"] = item["rx"] * factor
                    item["ry"] = item["ry"] * factor
                else:
                    rect = item["rect"]
                    top_left = self.transformed_point(rect.topLeft(), center, scale=factor)
                    bottom_right = self.transformed_point(rect.bottomRight(), center, scale=factor)
                    item["rect"] = QRectF(top_left, bottom_right)
                item["width"] = max(1, round(item["width"] * factor))
        if emit_event:
            track_event("selection_scaled", factor=factor, count=len(self.selected_ids))
        self.mark_content_changed()

    def rotate_selection(self, degrees, emit_event=True):
        if not self.selected_ids:
            return
        center = self.selection_bounds().center()
        for seg in self.all_segments:
            if seg["id"] in self.selected_ids:
                p1 = self.transformed_point(seg["line"].p1(), center, rotation=degrees)
                p2 = self.transformed_point(seg["line"].p2(), center, rotation=degrees)
                seg["line"] = QLine(round(p1.x()), round(p1.y()), round(p2.x()), round(p2.y()))
        for item in self.text_items:
            if item["id"] in self.selected_ids:
                item["pos"] = self.transformed_point(item["pos"], center, rotation=degrees)
                item["rotation"] = (item["rotation"] + degrees) % 360
        for item in self.image_items:
            if item["id"] in self.selected_ids:
                item["pos"] = self.transformed_point(item["pos"], center, rotation=degrees)
                item["rotation"] = (item["rotation"] + degrees) % 360
        for item in self.shape_items:
            if item["id"] in self.selected_ids:
                kind = item.get("kind", "rect")
                if kind == "poly":
                    item["points"] = [self.transformed_point(p, center, rotation=degrees) for p in item["points"]]
                elif kind == "angle":
                    for key in ("vertex", "p1", "p2"):
                        item[key] = self.transformed_point(item[key], center, rotation=degrees)
                elif kind == "circle":
                    item["center"] = self.transformed_point(item["center"], center, rotation=degrees)
                elif kind == "ellipse":
                    item["center"] = self.transformed_point(item["center"], center, rotation=degrees)
                    item["rotation"] = (item["rotation"] + degrees) % 360
                else:
                    item["rect"].moveCenter(self.transformed_point(item["rect"].center(), center, rotation=degrees))
                    item["rotation"] = (item["rotation"] + degrees) % 360
        if emit_event:
            track_event("selection_rotated", degrees=degrees, count=len(self.selected_ids))
        self.mark_content_changed()

    def apply_selection_color(self, color):
        if not self.selected_ids:
            return
        self.push_undo()
        for seg in self.all_segments:
            if seg["id"] in self.selected_ids:
                pen = QPen(seg["pen"])
                new_color = QColor(color)
                if seg.get("marker"):
                    new_color.setAlpha(pen.color().alpha())   # 荧光笔改色时保留原透明度
                pen.setColor(new_color)
                seg["pen"] = pen
        for item in self.text_items:
            if item["id"] in self.selected_ids:
                item["color"] = QColor(color)
        for item in self.shape_items:
            if item["id"] in self.selected_ids:
                item["color"] = QColor(color)
        self.mark_content_changed()

    def apply_selection_width(self, width):
        if not self.selected_ids:
            return
        self.push_undo(coalesce_key="selection_width")
        for seg in self.all_segments:
            if seg["id"] in self.selected_ids:
                pen = QPen(seg["pen"])
                pen.setWidth(max(1, width))
                seg["pen"] = pen
        for item in self.text_items:
            if item["id"] in self.selected_ids:
                item["width"] = max(1, width)
                item["size"] = max(8, width * 6)
        for item in self.shape_items:
            if item["id"] in self.selected_ids:
                item["width"] = max(1, width)
        self.mark_content_changed()

    def marker_pen(self):
        color = QColor(self.marker_color)
        color.setAlpha(max(10, min(255, self.marker_alpha)))
        return QPen(color, max(1, self.marker_width), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)

    def add_smooth_segments(self, pos):
        if self.last_point is None:
            self.last_point = pos
            return
        is_marker = self.draw_state == "MARKER"
        base_width = self.marker_width if is_marker else self.pen_width
        dx = pos.x() - self.last_point.x()
        dy = pos.y() - self.last_point.y()
        distance = math.hypot(dx, dy)
        spacing = base_width * (0.3 if is_marker else 0.6)
        steps = max(1, int(distance / max(2, spacing)))
        previous = self.last_point
        for step in range(1, steps + 1):
            t = step / steps
            point = QPoint(round(self.last_point.x() + dx * t), round(self.last_point.y() + dy * t))
            if point != previous:
                if is_marker:
                    # 荧光笔宽度恒定，不受压感和起笔渐变影响
                    pen = self.marker_pen()
                    width = pen.width()
                else:
                    taper = min(1.0, max(0.35, len(self.current_stroke_widths) / 10))
                    pressure = max(0.08, min(1.0, self.current_pressure))
                    width = max(1, int(round(self.pen_width * taper * pressure)))
                    pen = QPen(self.pen_color, width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
                line = QLine(previous.x(), previous.y(), point.x(), point.y())
                self.all_segments.append({"line": line, "pen": pen, "id": self.current_stroke_id, "marker": is_marker})
                self.current_stroke_widths.append(width)
                previous = point
        self.last_point = pos

    def draw_segments(self, painter, segments):
        """普通笔迹逐段绘制；荧光笔按整笔合成一条路径，避免重叠处叠色发黑。"""
        index = 0
        total = len(segments)
        while index < total:
            seg = segments[index]
            if not seg.get("marker"):
                painter.setPen(seg["pen"])
                painter.drawLine(seg["line"])
                index += 1
                continue
            stroke_id = seg["id"]
            path = QPainterPath(QPointF(seg["line"].p1()))
            end = seg["line"].p1()
            while index < total and segments[index].get("marker") and segments[index]["id"] == stroke_id:
                line = segments[index]["line"]
                if line.p1() != end:            # 中间被擦断，另起一段，不要连成直线
                    path.moveTo(QPointF(line.p1()))
                path.lineTo(QPointF(line.p2()))
                end = line.p2()
                index += 1
            pen = QPen(seg["pen"])
            color = QColor(pen.color())
            alpha = color.alpha()
            color.setAlpha(255)
            pen.setColor(color)
            painter.save()
            painter.setOpacity(alpha / 255)     # 整条路径一次性合成，透明度均匀
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(path)
            painter.restore()

    def draw_image_item(self, painter, item):
        """图片对象：以 pos 为中心、按 size 绘制（含旋转）。"""
        pixmap = item["pixmap"]
        if pixmap is None or pixmap.isNull():
            return
        width, height = item["size"].width(), item["size"].height()
        if width < 1 or height < 1:
            return
        painter.save()
        painter.translate(item["pos"])
        painter.rotate(item["rotation"])
        painter.drawPixmap(QRectF(-width / 2.0, -height / 2.0, width, height),
                           pixmap, QRectF(0, 0, pixmap.width(), pixmap.height()))
        painter.restore()

    def draw_content(self, painter, segments=None, shapes=None, texts=None, images=None):
        """只画内容本身（笔迹/图片/图形/文本），不含选中框、预览、光标等辅助图元，导出复用。"""
        self.draw_segments(painter, self.all_segments if segments is None else segments)
        for item in (self.image_items if images is None else images):
            self.draw_image_item(painter, item)
        for item in (self.shape_items if shapes is None else shapes):
            self.draw_shape_item(painter, item)
        for item in (self.text_items if texts is None else texts):
            painter.save()
            painter.translate(item["pos"])
            painter.rotate(item["rotation"])
            painter.scale(item["scale"], item["scale"])
            font = QFont("Microsoft YaHei", item["size"])
            font.setBold(item.get("bold", False))
            painter.setFont(font)
            painter.setPen(QPen(item["color"], max(1, item["width"])))
            painter.drawText(QPointF(0, 0), item["text"])
            painter.restore()

    def render_page_pixmap(self, page, size):
        """把一页页面数据渲染为缩略图或导出图，兼容 JSON 和运行时页面。"""
        width, height = self._page_px_size(size)
        pixmap = QPixmap(width, height)
        painter = QPainter(pixmap)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            self._render_page_painter(painter, page, width, height)
        finally:
            painter.end()
        return pixmap

    @staticmethod
    def _page_px_size(size):
        if hasattr(size, "width"):
            return max(1, int(size.width())), max(1, int(size.height()))
        return 1920, 1080

    def _render_page_painter(self, painter, page, width, height):
        """在给定 painter 上渲染一页：探测序列化→deserialize→边界适配→draw_content。

        PNG/SVG/缩略图共用这一绘制体，保证同一页面在各导出格式下外观一致。
        """
        painter.fillRect(QRectF(0, 0, width, height), self.board_background())
        if not isinstance(page, dict):
            page = {"segments": [], "texts": [], "shapes": [], "images": []}
        segments = page.get("segments") or []
        shapes = page.get("shapes") or []
        texts = page.get("texts") or []
        images = page.get("images") or []
        # Detect serialized (JSON) pages without indexing empty lists.
        needs_deserialize = False
        if segments and isinstance(segments[0], dict) and "p1" in segments[0]:
            needs_deserialize = True
        elif shapes and isinstance(shapes[0], dict) and isinstance(shapes[0].get("color"), str):
            needs_deserialize = True
        elif images and isinstance(images[0], dict) and isinstance(images[0].get("data"), str):
            needs_deserialize = True
        if needs_deserialize:
            page = deserialize_page(page)
            segments = page.get("segments", [])
            shapes = page.get("shapes", [])
            texts = page.get("texts", [])
            images = page.get("images", [])
        if segments or shapes or texts or images:
            bounds = QRectF()
            # 笔迹很多时，逐段构造 QRectF/QPointF 再 united 是缩略图卡顿的主要来源；
            # 用纯数值 min/max 一次扫完，结果相同但大幅减少 Python/Qt 对象创建。
            min_x = min_y = float("inf")
            max_x = max_y = float("-inf")
            for seg in segments:
                line = seg.get("line") if isinstance(seg, dict) else None
                if line is None:
                    continue
                x1, y1, x2, y2 = line.x1(), line.y1(), line.x2(), line.y2()
                min_x = min(min_x, x1, x2); max_x = max(max_x, x1, x2)
                min_y = min(min_y, y1, y2); max_y = max(max_y, y1, y2)
            if min_x <= max_x and min_y <= max_y:
                bounds = QRectF(QPointF(min_x, min_y), QPointF(max_x, max_y))
            for item in images:
                try:
                    bounds = bounds.united(self.image_bounds(item))
                except Exception:
                    continue
            for item in shapes:
                try:
                    bounds = bounds.united(self.shape_bounds(item))
                except Exception:
                    continue
            for item in texts:
                try:
                    bounds = bounds.united(self.text_bounds(item))
                except Exception:
                    continue
            bounds = bounds.adjusted(-20, -20, 20, 20)
            if not bounds.isNull() and bounds.width() > 0 and bounds.height() > 0:
                margin = 10.0
                scale = min((width - 2 * margin) / bounds.width(), (height - 2 * margin) / bounds.height())
                scale = max(0.01, min(scale, 20.0))
                painter.translate(width / 2, height / 2)
                painter.scale(scale, scale)
                painter.translate(-bounds.center())
            self.draw_content(painter, segments, shapes, texts, images)

    def write_svg_page(self, path, page, size):
        """把一页渲染为 SVG（矢量，可再编辑）。"""
        from PyQt6.QtSvg import QSvgGenerator
        width, height = self._page_px_size(size)
        generator = QSvgGenerator()
        generator.setFileName(path)
        generator.setSize(QSize(width, height))
        generator.setViewBox(QRectF(0, 0, width, height))
        generator.setTitle("MyScreenDraw")
        painter = QPainter(generator)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            self._render_page_painter(painter, page, width, height)
        finally:
            painter.end()

    def step_magnifier_zoom(self, direction):
        zoom = round(self.magnifier_zoom + direction * self.MAGNIFIER_ZOOM_STEP, 2)
        self.magnifier_zoom = max(self.MAGNIFIER_ZOOM_MIN, min(self.MAGNIFIER_ZOOM_MAX, zoom))
        if self.panel:
            self.panel.update_magnifier_ui()
        track_event("magnifier_zoom_changed", zoom=self.magnifier_zoom)
        self.update()

    # --- 激光笔（不落墨） ---
    def push_laser_point(self, pos):
        now = time.monotonic()
        self.laser_trail.append((QPointF(pos), now))
        cutoff = now - self.laser_trail_ms / 1000.0
        self.laser_trail = [(p, t) for p, t in self.laser_trail if t >= cutoff]

    def prune_laser_trail(self):
        if not self.laser_trail:
            return False
        cutoff = time.monotonic() - self.laser_trail_ms / 1000.0
        before = len(self.laser_trail)
        self.laser_trail = [(p, t) for p, t in self.laser_trail if t >= cutoff]
        return len(self.laser_trail) != before or bool(self.laser_trail)

    def draw_laser(self, painter):
        self.prune_laser_trail()
        now = time.monotonic()
        if self.laser_trail:
            path = QPainterPath(self.laser_trail[0][0])
            for p, _ in self.laser_trail[1:]:
                path.lineTo(p)
            for width, alpha in ((self.laser_width * 2.2, 40), (self.laser_width * 1.2, 110), (self.laser_width * 0.55, 220)):
                c = QColor(self.laser_color)
                c.setAlpha(alpha)
                painter.setPen(QPen(c, max(2, width), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawPath(path)
        # 光点始终跟鼠标
        glow = QColor(self.laser_color)
        glow.setAlpha(70)
        core = QColor(self.laser_color)
        core.setAlpha(230)
        r = max(6, self.laser_width)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(glow)
        painter.drawEllipse(QPointF(self.mouse_pos), r * 1.8, r * 1.8)
        painter.setBrush(core)
        painter.drawEllipse(QPointF(self.mouse_pos), r * 0.55, r * 0.55)
        white = QColor(255, 255, 255, 220)
        painter.setBrush(white)
        painter.drawEllipse(QPointF(self.mouse_pos.x() - r * 0.15, self.mouse_pos.y() - r * 0.15), r * 0.18, r * 0.18)

    # --- 辅助作图工具 ---
    def current_screen_calibration(self):
        screen = self.screen() or QApplication.primaryScreen()
        if screen is None:
            return "screen", pixels_per_mm_from_dpi(96.0), False
        geometry = screen.geometry()
        dpr = screen.devicePixelRatio()
        dpi = sane_dpi(screen.logicalDotsPerInch())
        key = screen_key(screen.name(), (geometry.left(), geometry.top(), geometry.width(), geometry.height()), dpr, dpi)
        record = self.ruler_calibrations.get(key)
        if isinstance(record, dict) and valid_pixels_per_mm(record.get("px_per_mm")):
            self.ruler_calibration = record
            return key, float(record["px_per_mm"]), True
        estimate = pixels_per_mm_from_dpi(dpi)
        self.ruler_calibration = {"screen_key": key, "px_per_mm": estimate, "calibrated": False}
        return key, estimate, False

    def ruler_px_per_mm(self, aid):
        key = aid.get("screen_key")
        if not key:
            key, _, _ = self.current_screen_calibration()
            aid["screen_key"] = key
        record = self.ruler_calibrations.get(key)
        if isinstance(record, dict) and valid_pixels_per_mm(record.get("px_per_mm")):
            return float(record["px_per_mm"])
        return self.current_screen_calibration()[1]

    def ruler_width(self, aid):
        width = clamp_ruler_width(aid.get("width", 36.0))
        aid["width"] = width
        return width

    def ruler_geometry(self, aid):
        geometry = physical_ruler_geometry(
            aid.get("length_mm", 150.0),
            aid.get("tick_mm", 1.0),
            aid.get("major_tick_mm", 10.0),
            self.ruler_px_per_mm(aid),
        )
        geometry["width"] = self.ruler_width(aid)
        geometry["top"] = -geometry["width"] / 2.0
        geometry["bottom"] = geometry["width"] / 2.0
        return geometry

    def protractor_measurement(self, aid, pos, snap=False):
        inv, ok = self.aid_transform(aid).inverted()
        if not ok:
            return None
        local = inv.map(QPointF(pos))
        radius = max(20.0, float(aid.get("radius", 160.0)))
        if local.y() > 2.0 or local.x() * local.x() + local.y() * local.y() > (radius + 16.0) ** 2:
            return None
        distance = math.hypot(local.x(), local.y())
        if distance < 8.0:
            return None
        return protractor_angle_degrees(local.x(), local.y(), snap=snap)

    def ruler_measurement(self, aid, pos):
        inv, ok = self.aid_transform(aid).inverted()
        if not ok:
            return None
        local = inv.map(QPointF(pos))
        geometry = self.ruler_geometry(aid)
        if local.y() < geometry["top"] - 4.0 or local.y() > geometry["bottom"] + 4.0:
            return None
        if abs(local.x()) > geometry["length"] / 2.0 + 8.0:
            return None
        return ruler_mm_from_local_x(local.x(), geometry["length"], geometry["length_mm"])

    def add_aid(self, kind):
        """放置一把辅助工具到屏幕中央。"""
        screen = self.rect()
        center = QPointF(screen.center())
        screen_key_value, _, _ = self.current_screen_calibration()
        defaults = {
            "ruler": {
                "scale": 1.0, "length_mm": 150.0, "width": 36.0,
                "tick_mm": 1.0, "major_tick_mm": 10.0, "unit_label": "cm", "screen_key": screen_key_value,
            },
            "set_square_45": {"scale": 1.0, "size": 260, "rotation": 0.0},
            "set_square_30": {"scale": 1.0, "size": 280, "rotation": 0.0},
            "protractor": {"scale": 1.0, "radius": 160, "rotation": 0.0},
        }
        if kind not in defaults:
            return
        item = {"id": uuid.uuid4(), "kind": kind, "pos": center, **defaults[kind]}
        self.aids.append(item)
        self.active_aid_id = item["id"]
        # 不把 draw_state 改成 "AID"：教具在任意绘图态下都可直接拖动（mousePressEvent 优先处理 aid_hit），
        # 改 state 反而会让用户放下教具后画布「点不动」直到重选工具。
        track_event("aid_added", kind=kind)
        self.update()
        return item

    def clear_aids(self):
        self.aids.clear()
        self.active_aid_id = None
        self.aid_drag = None
        self.update()

    def remove_aid(self, aid_id):
        self.aids = [a for a in self.aids if a["id"] != aid_id]
        if self.active_aid_id == aid_id:
            self.active_aid_id = self.aids[-1]["id"] if self.aids else None
        self.aid_drag = None
        self.update()

    def find_aid(self, aid_id):
        return next((a for a in self.aids if a["id"] == aid_id), None)

    def aid_transform(self, aid):
        t = QTransform()
        pos = aid.get("pos", QPointF())
        t.translate(pos.x(), pos.y())
        t.rotate(float(aid.get("rotation", 0.0)))
        try:
            scale = float(aid.get("scale", 1.0))
        except (TypeError, ValueError):
            scale = 1.0
        scale = 1.0 if aid.get("kind") == "ruler" else max(0.4, min(3.0, scale))
        aid["scale"] = scale
        t.scale(scale, scale)
        return t

    def aid_map(self, aid, x, y):
        return self.aid_transform(aid).map(QPointF(x, y))

    def aid_hit(self, pos):
        """Return the topmost aid and interaction mode under the pointer."""
        p = QPointF(pos)
        for aid in reversed(self.aids):
            inv, ok = self.aid_transform(aid).inverted()
            if not ok:
                continue
            local = inv.map(p)
            handle_radius = 14.0 / max(0.4, float(aid.get("scale", 1.0)))
            # 关闭柄要排在最前面判定，否则它和旋转柄挨着时会先被旋转柄吃掉
            close_handle = self._aid_close_handle_local(aid)
            if QRectF(close_handle.x() - handle_radius, close_handle.y() - handle_radius,
                      handle_radius * 2, handle_radius * 2).contains(local):
                return aid, "close"
            # 旋转柄（统一在工具上方）
            handle = self._aid_rotate_handle_local(aid)
            if QRectF(handle.x() - handle_radius, handle.y() - handle_radius,
                      handle_radius * 2, handle_radius * 2).contains(local):
                return aid, "rotate"
            width_handle = self._aid_width_handle_local(aid)
            if width_handle is not None and QRectF(width_handle.x() - handle_radius, width_handle.y() - handle_radius,
                                                  handle_radius * 2, handle_radius * 2).contains(local):
                return aid, "width"
            scale_handle = self._aid_scale_handle_local(aid)
            if QRectF(scale_handle.x() - handle_radius, scale_handle.y() - handle_radius,
                      handle_radius * 2, handle_radius * 2).contains(local):
                return aid, "scale"
            if self._aid_body_contains(aid, local):
                return aid, "move"
        return None, None

    def _aid_rotate_handle_local(self, aid):
        kind = aid["kind"]
        if kind == "ruler":
            geometry = self.ruler_geometry(aid)
            return QPointF(0, geometry["top"] - 18.0)
        if kind in ("set_square_45", "set_square_30"):
            return QPointF(0, -aid.get("size", 260) * 0.55)
        if kind == "protractor":
            return QPointF(0, -aid.get("radius", 160) - 28)
        return QPointF(0, -40)

    def _aid_close_handle_local(self, aid):
        """关闭柄（红色 ✕）：统一放在旋转柄右侧。

        触控大屏上「右键移除教具」是够不着的——Windows 的按住变右键已被本程序关掉
        （它会打断停笔定形），而触摸屏本来也没有物理右键。所以每把教具都要有一个
        能直接点的移除按钮。鼠标右键移除仍然保留。
        """
        rotate = self._aid_rotate_handle_local(aid)
        return QPointF(rotate.x() + 30.0, rotate.y())

    def _aid_width_handle_local(self, aid):
        if aid.get("kind") == "ruler":
            geometry = self.ruler_geometry(aid)
            return QPointF(0, geometry["bottom"] + 18.0)
        return None

    def _aid_scale_handle_local(self, aid):
        kind = aid["kind"]
        if kind == "ruler":
            geometry = self.ruler_geometry(aid)
            return QPointF(geometry["length"] / 2.0, geometry["bottom"] + 18.0)
        if kind in ("set_square_45", "set_square_30"):
            size = float(aid.get("size", 260))
            return QPointF(size * 0.85, size * 0.45)
        if kind == "protractor":
            radius = float(aid.get("radius", 160))
            return QPointF(radius, 0)
        return QPointF(40, 40)

    def _aid_body_contains(self, aid, local):
        kind = aid["kind"]
        x, y = local.x(), local.y()
        if kind == "ruler":
            geometry = self.ruler_geometry(aid)
            half = geometry["length"] / 2.0
            return -half - 8 <= x <= half + 8 and geometry["top"] - 4 <= y <= geometry["bottom"] + 4
        if kind == "set_square_45":
            s = aid.get("size", 260)
            # 绘制是顶点在原点、向右/下展开的等腰直角三角形 (0,0),(s,0),(0,s)，
            # 命中范围必须与绘制重合：带 8 像素容差地闭合在「右上 + 左下」之外的两个直角边内。
            return -8 <= x <= s + 8 and -8 <= y <= s + 8 and (x + y <= s + 8)
        if kind == "set_square_30":
            s = aid.get("size", 280)
            # 绘制为直角在原点、向右/下展开的 30-60-90 三角形 (0,0),(s,0),(0,s/√3)，
            # 斜边从 (s,0) 到 (0,s/√3)：y <= (s/√3)*(1 - x/s)。命中范围与此绘制重合。
            height = s / math.sqrt(3)
            return -8 <= x <= s + 8 and -8 <= y <= height + 8 and y <= max(0.0, height * (1.0 - max(0.0, x) / (s + 1e-9)) + 8)
        if kind == "protractor":
            r = aid.get("radius", 160)
            return x * x + y * y <= (r + 12) ** 2 and y <= 18
        return False

    def draw_aids(self, painter):
        for aid in self.aids:
            painter.save()
            painter.setTransform(self.aid_transform(aid), True)
            active = aid["id"] == self.active_aid_id
            self._draw_aid_local(painter, aid, active)
            aid_scale = 1.0 if aid.get("kind") == "ruler" else max(0.4, float(aid.get("scale", 1.0)))
            h = self._aid_rotate_handle_local(aid)
            painter.setPen(QPen(QColor(0, 206, 201, 220), 2 / aid_scale))
            painter.setBrush(QColor(0, 206, 201, 230) if active else QColor(255, 255, 255, 200))
            painter.drawLine(QPointF(0, 0), h)
            painter.drawEllipse(h, 8 / aid_scale, 8 / aid_scale)
            scale_handle = self._aid_scale_handle_local(aid)
            painter.setPen(QPen(QColor(255, 184, 77, 230), 2 / aid_scale))
            painter.setBrush(QColor(255, 184, 77, 230) if active else QColor(255, 255, 255, 210))
            painter.drawEllipse(scale_handle, 8 / aid_scale, 8 / aid_scale)
            painter.drawLine(QPointF(0, 0), scale_handle)
            # 关闭柄：红底白 ✕，触屏用户唯一能移除单把教具的入口
            close_handle = self._aid_close_handle_local(aid)
            painter.setPen(QPen(QColor(255, 255, 255, 230), 2 / aid_scale))
            painter.setBrush(QColor(214, 48, 49, 235) if active else QColor(214, 48, 49, 170))
            painter.drawEllipse(close_handle, 9 / aid_scale, 9 / aid_scale)
            tick = 4.0 / aid_scale
            painter.drawLine(QPointF(close_handle.x() - tick, close_handle.y() - tick),
                             QPointF(close_handle.x() + tick, close_handle.y() + tick))
            painter.drawLine(QPointF(close_handle.x() + tick, close_handle.y() - tick),
                             QPointF(close_handle.x() - tick, close_handle.y() + tick))
            width_handle = self._aid_width_handle_local(aid)
            if width_handle is not None:
                painter.setPen(QPen(QColor(162, 155, 254, 235), 2 / aid_scale))
                painter.setBrush(QColor(162, 155, 254, 235) if active else QColor(255, 255, 255, 210))
                painter.drawLine(QPointF(0, 0), width_handle)
                painter.drawRect(QRectF(width_handle.x() - 7 / aid_scale, width_handle.y() - 7 / aid_scale,
                                        14 / aid_scale, 14 / aid_scale))
            painter.restore()
            if aid.get("kind") == "ruler":
                self._draw_ruler_screen_overlay(painter, aid)
            elif aid.get("kind") == "protractor":
                reading = self.protractor_measurement(aid, self.aid_hover_pos, snap=self.aid_shift_pressed)
                if reading is not None:
                    center = self.aid_map(aid, 0, 0)
                    painter.save()
                    painter.setPen(QPen(QColor(0, 206, 201, 235), 1))
                    painter.setBrush(QColor(20, 20, 20, 210))
                    label_rect = QRectF(center.x() - 42, center.y() + 12, 84, 26)
                    painter.drawRoundedRect(label_rect, 4, 4)
                    painter.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
                    painter.drawText(label_rect, Qt.AlignmentFlag.AlignCenter, f"{reading:.1f}°")
                    painter.restore()

    def _screen_label_rect(self, painter, center, text, padding=7.0):
        metrics = painter.fontMetrics()
        width = metrics.horizontalAdvance(text) + padding * 2.0
        height = metrics.height() + padding
        x = max(4.0, min(self.width() - width - 4.0, center.x() - width / 2.0))
        y = max(4.0, min(self.height() - height - 4.0, center.y() - height / 2.0))
        return QRectF(x, y, width, height)

    def _draw_ruler_screen_overlay(self, painter, aid):
        geometry = self.ruler_geometry(aid)
        half = geometry["length"] / 2.0
        painter.save()
        painter.setFont(QFont("Microsoft YaHei", 8))
        major_count = int(math.floor(geometry["length_mm"] / geometry["major_tick_mm"] + 1e-9))
        min_label_gap = 34.0
        step = max(1, int(math.ceil(min_label_gap / max(1.0, geometry["major_spacing"]))))
        occupied = []
        for major_index in range(major_count + 1):
            if major_index % step != 0 and major_index != major_count:
                continue
            mm_value = major_index * geometry["major_tick_mm"]
            local_x = -half + mm_value * geometry["px_per_mm"]
            anchor = self.aid_map(aid, local_x, geometry["bottom"] + 10.0)
            text = f"{mm_value / 10:g}cm"
            rect = self._screen_label_rect(painter, anchor, text, 4.0)
            collision_rect = rect.adjusted(-3.0, -2.0, 3.0, 2.0)
            if any(existing.intersects(collision_rect) for existing in occupied):
                continue
            occupied.append(collision_rect)
            painter.setPen(QPen(QColor(20, 20, 20, 230), 1))
            painter.setBrush(QColor(255, 248, 220, 225))
            painter.drawRoundedRect(rect, 3, 3)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)
        reading = self.ruler_measurement(aid, self.aid_hover_pos)
        if reading is not None:
            inv, ok = self.aid_transform(aid).inverted()
            if ok:
                local = inv.map(self.aid_hover_pos)
                local_x = max(-half, min(half, local.x()))
                anchor = self.aid_map(aid, local_x, geometry["bottom"] + 34.0)
                text = f"{reading:.1f} mm / {reading / 10:.2f} cm"
                painter.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
                rect = self._screen_label_rect(painter, anchor, text, 8.0)
                painter.setPen(QPen(QColor(0, 206, 201, 240), 2))
                painter.setBrush(QColor(15, 15, 15, 225))
                painter.drawRoundedRect(rect, 5, 5)
                painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)
        painter.restore()

    def _draw_aid_local(self, painter, aid, active):
        kind = aid["kind"]
        edge = QColor(30, 30, 30, 220)
        fill = QColor(255, 248, 220, 150 if active else 110)
        accent = QColor(0, 206, 201, 200)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        try:
            scale = float(aid.get("scale", 1.0))
        except (TypeError, ValueError):
            scale = 1.0
        scale = 1.0 if kind == "ruler" else max(0.4, min(3.0, scale))
        if kind == "ruler":
            geometry = self.ruler_geometry(aid)
            length = geometry["length"]
            half = length / 2.0
            top = geometry["top"]
            bottom = geometry["bottom"]
            body = QRectF(-half, top, length, geometry["width"])
            painter.setPen(QPen(edge, 1.5)); painter.setBrush(fill); painter.drawRoundedRect(body, 4, 4)
            spacing = geometry["spacing"]
            tick_count = int(math.floor(geometry["length_mm"] / geometry["tick_mm"] + 1e-9))
            for index in range(tick_count + 1):
                mm_value = index * geometry["tick_mm"]
                x = -half + mm_value * geometry["px_per_mm"]
                major_index = mm_value / geometry["major_tick_mm"]
                major = abs(major_index - round(major_index)) < 1e-6
                height = min(geometry["width"] * 0.48, 18.0) if major else (min(geometry["width"] * 0.36, 13.0) if index % 5 == 0 else min(geometry["width"] * 0.22, 8.0))
                painter.setPen(QPen(edge, 1)); painter.drawLine(QPointF(x, top), QPointF(x, top + height))
            remainder = length - tick_count * spacing
            if remainder > 1e-6:
                painter.setPen(QPen(edge, 1)); painter.drawLine(QPointF(half, top), QPointF(half, top + min(geometry["width"] * 0.48, 18.0)))
            painter.setPen(QPen(accent if active else edge, 1)); painter.drawText(QRectF(-90, top - 22, 180, 16), Qt.AlignmentFlag.AlignCenter, trf("ruler_length_mm", value=f"{geometry['length_mm']:g}"))
            reading = self.ruler_measurement(aid, self.aid_hover_pos)
            if reading is not None:
                inv, ok = self.aid_transform(aid).inverted()
                if ok:
                    local = inv.map(self.aid_hover_pos)
                    x = max(-half, min(half, local.x()))
                    painter.setPen(QPen(accent, 2)); painter.drawLine(QPointF(x, top), QPointF(x, bottom))
        elif kind == "set_square_45":
            s = aid.get("size", 260)
            poly = QPolygonF([QPointF(0, 0), QPointF(s, 0), QPointF(0, s)])
            painter.setPen(QPen(edge, 1.5)); painter.setBrush(fill); painter.drawPolygon(poly)
            # 45° 角平分线从直角顶点画到斜边中点 (s/2, s/2) 为止，不再画到 (s,s) 穿出斜边。
            painter.setPen(QPen(edge, 1)); painter.drawLine(QPointF(0, 0), QPointF(s * 0.5, s * 0.5))
            painter.setFont(QFont("Microsoft YaHei", 9, QFont.Weight.Bold))
            painter.drawText(QRectF(s * 0.55, s * 0.55, 60, 18), Qt.AlignmentFlag.AlignLeft, "45°")
        elif kind == "set_square_30":
            s = aid.get("size", 280); width = s; height = s / math.sqrt(3)
            poly = QPolygonF([QPointF(0, 0), QPointF(width, 0), QPointF(0, height)])
            painter.setPen(QPen(edge, 1.5)); painter.setBrush(fill); painter.drawPolygon(poly)
            # 三角板 (0,0)=(width,0)=(0,height)：(0,0) 是 90° 顶点，(width,0) 是 30° 顶点，
            # (0,height) 是 60° 顶点。把 30° 标在右下底角、60° 标在左上斜角，与几何对齐。
            painter.setFont(QFont("Microsoft YaHei", 9, QFont.Weight.Bold))
            painter.drawText(QRectF(width - 40, 10, 50, 16), Qt.AlignmentFlag.AlignLeft, "30°")
            painter.drawText(QRectF(10, height - 18, 50, 16), Qt.AlignmentFlag.AlignLeft, "60°")
        elif kind == "protractor":
            try:
                r = float(aid.get("radius", 160))
            except (TypeError, ValueError):
                r = 160.0
            r = max(20.0, r)
            painter.setPen(QPen(edge, 1.5)); painter.setBrush(fill)
            path = QPainterPath(); path.moveTo(-r, 0); path.arcTo(QRectF(-r, -r, 2 * r, 2 * r), 180, -180); path.closeSubpath(); painter.drawPath(path)
            painter.setPen(QPen(edge, 1)); painter.drawLine(QPointF(-r, 0), QPointF(r, 0))
            # 所有 1 度刻度都在局部坐标中绘制，缩放由 aid_transform 统一处理。
            # 标签仅根据缩放后的弧长间距稀疏化，不会改变刻度的角度或位置。
            screen_degree_spacing = math.radians(1) * r * scale
            label_step = 5 if screen_degree_spacing >= 5 else (10 if screen_degree_spacing >= 2.5 else 30)
            for deg in range(181):
                rad = math.radians(deg)
                direction = QPointF(math.cos(math.pi - rad), -math.sin(rad))
                outer = direction * r
                if deg % 10 == 0:
                    inner_len = 20
                elif deg % 5 == 0:
                    inner_len = 14
                else:
                    inner_len = 7
                inner = direction * (r - inner_len)
                painter.setPen(QPen(edge, 1)); painter.drawLine(outer, inner)
                if deg % 5 == 0 and deg % label_step == 0:
                    label_pos = direction * (r - 30)
                    painter.setFont(QFont("Microsoft YaHei", 7))
                    painter.drawText(QRectF(label_pos.x() - 13, label_pos.y() - 7, 26, 14), Qt.AlignmentFlag.AlignCenter, str(deg))
                    # 内圈显示从右端起算的反向读数，测量时两侧基线均可直接读取。
                    if deg not in (0, 90, 180) and label_step >= 10:
                        reverse_pos = direction * (r - 49)
                        painter.setFont(QFont("Microsoft YaHei", 6))
                        painter.drawText(QRectF(reverse_pos.x() - 11, reverse_pos.y() - 6, 22, 12), Qt.AlignmentFlag.AlignCenter, str(180 - deg))
            reading = self.protractor_measurement(aid, self.aid_hover_pos, snap=self.aid_shift_pressed)
            if reading is not None:
                inv, ok = self.aid_transform(aid).inverted()
                if ok:
                    local = inv.map(self.aid_hover_pos)
                    distance = max(1.0, math.hypot(local.x(), local.y()))
                    ray = QPointF(local.x() * r / distance, local.y() * r / distance)
                    painter.setPen(QPen(accent, 2)); painter.drawLine(QPointF(0, 0), ray)
                    painter.setBrush(accent); painter.drawEllipse(ray, 4, 4)
            painter.setBrush(QColor(edge)); painter.drawEllipse(QPointF(0, 0), 3, 3)

    def draw_magnifier(self, painter):
        if not self.magnifier_pixmap or self.magnifier_pixmap.isNull():
            return
        dpr = self.magnifier_pixmap.devicePixelRatio() or 1.0
        radius = self.magnifier_size / 2
        center = QPointF(self.mouse_pos)
        target = QRectF(center.x() - radius, center.y() - radius, self.magnifier_size, self.magnifier_size)
        src_side = self.magnifier_size / self.magnifier_zoom
        source = QRectF((center.x() - src_side / 2) * dpr, (center.y() - src_side / 2) * dpr, src_side * dpr, src_side * dpr)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        clip = QPainterPath()
        clip.addEllipse(target)
        painter.setClipPath(clip)
        painter.fillRect(target, QColor("#101010"))
        painter.drawPixmap(target, self.magnifier_pixmap, source)
        painter.restore()
        painter.setPen(QPen(QColor(0, 206, 201, 235), 3))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(target)
        badge = QRectF(target.center().x() - 34, target.bottom() + 6, 68, 22)
        painter.setBrush(QColor(0, 0, 0, 170))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(badge, 8, 8)
        painter.setPen(QPen(QColor("#00cec9")))
        painter.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        painter.drawText(badge, Qt.AlignmentFlag.AlignCenter, f"{int(self.magnifier_zoom * 100)}%")

    def draw_spotlight(self, painter):
        """暗化全屏，只在跟随鼠标的圆形亮区透出底层批注/桌面。"""
        rect = self.rect()
        w, h = rect.width(), rect.height()
        if w < 2 or h < 2:
            return
        radius = self.spotlight_radius
        center = QPointF(self.mouse_pos)
        # HiDPI：按设备像素率创建 overlay，避免高分屏下暗化层/亮区边缘被放大模糊
        dpr = self.devicePixelRatio() or 1.0
        dev_w, dev_h = int(round(w * dpr)), int(round(h * dpr))
        overlay = self._spotlight_overlay
        if overlay is None or overlay.width() != dev_w or overlay.height() != dev_h:
            overlay = QPixmap(dev_w, dev_h)
            overlay.setDevicePixelRatio(dpr)
            self._spotlight_overlay = overlay
        # 先把整层填成半透明黑，再在亮区圆里用 DestinationOut 挖洞，让该处透出底层
        overlay.fill(QColor(0, 0, 0, 190))
        p = QPainter(overlay)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationOut)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(255, 255, 255))   # DestinationOut 只看 alpha，颜色无所谓
        # overlay 设了 devicePixelRatio，painter 坐标按逻辑像素，圆心/半径用逻辑值即可
        p.drawEllipse(center, radius, radius)
        p.end()
        painter.drawPixmap(0, 0, overlay)
        # 亮区描边，便于看清边界
        painter.setPen(QPen(QColor(255, 230, 0, 200), 3))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(center, radius, radius)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), self.board_background())
        self.draw_content(painter)
        # 穿透模式下不绘制任何交互 HUD（选择框 / 拖拽框 / 预览图形 / 光标圈），
        # 只保留已落墨的批注内容，避免画布层残留会误导用户的叠加元素。
        if self.is_drawing_mode:
            if self.preview_shape:
                preview = dict(self.preview_shape)
                preview["color"] = QColor(self.pen_color)
                preview["width"] = max(1, self.pen_width)
                self.draw_shape_item(painter, preview)
            if self.draw_state == "SHAPE" and self.pending_points:
                preview = self.build_point_shape(self.shape_type, self.pending_points + [QPointF(self.mouse_pos)])
                if preview:
                    painter.setOpacity(0.65)
                    self.draw_shape_item(painter, preview)
                    painter.setOpacity(1.0)
                painter.setPen(QPen(QColor(255, 255, 255, 230), 1))
                painter.setBrush(QColor(self.pen_color))
                for p in self.pending_points:
                    painter.drawEllipse(p, 4, 4)
            if self.selected_ids:
                # selection_handles() 在包围盒为空时返回 {}（选中 id 已失效等边界情况）。
                # 这里不判空直接 handles["scale"] 会在 paintEvent 里抛 KeyError，
                # 而 PyQt6 遇到虚函数里的未捕获异常会直接终止进程。
                handles = self.selection_handles()
                if handles:
                    rect = self.selection_bounds()
                    painter.setPen(QPen(QColor(0, 206, 201, 230), 2))
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.drawRect(rect)
                    painter.setBrush(QColor(0, 206, 201, 230))
                    painter.drawRect(handles["scale"])
                    painter.drawEllipse(handles["rotate"])
                    painter.drawLine(QPointF(rect.center().x(), rect.top()), handles["rotate"].center())
            if self.selection_rect:
                painter.setPen(QPen(QColor(255, 255, 255, 220), 1, Qt.PenStyle.DashLine))
                painter.setBrush(QColor(0, 206, 201, 35))
                painter.drawRect(QRectF(self.selection_rect).normalized())
            if self.draw_state == "ERASER" and self.eraser_type == "CIRCLE":
                r = int(self.eraser_size / 2)
                painter.setPen(QPen(QColor(0, 255, 255, 200), 2))
                painter.setBrush(QColor(0, 255, 255, 30))
                painter.drawEllipse(self.mouse_pos, r, r)
            if self.draw_state == "MARKER":
                r = max(3, int(self.marker_width / 2))
                preview_color = QColor(self.marker_color)
                preview_color.setAlpha(max(10, min(255, self.marker_alpha)))
                painter.setPen(QPen(QColor(255, 255, 255, 160), 1))
                painter.setBrush(preview_color)
                painter.drawEllipse(self.mouse_pos, r, r)
            if self._hold_progress > 0.0:
                self.draw_hold_ring(painter)
            if self.draw_state == "LASER":
                self.draw_laser(painter)
            if self.draw_state == "MAGNIFIER":
                self.draw_magnifier(painter)
            if self.draw_state == "SPOTLIGHT":
                self.draw_spotlight(painter)
        if self.aids:
            self.draw_aids(painter)

    def mousePressEvent(self, event):
        if not self.is_drawing_mode: return
        pos = event.position().toPoint()
        if event.button() == Qt.MouseButton.RightButton:
            if self.draw_state == "SHAPE":
                self.cancel_pending_points()
                return
            # 聚光灯右键退出 → 回到批注笔
            if self.draw_state == "SPOTLIGHT" and self.panel is not None:
                self.panel.set_tool("PEN", self.panel.btn_pen)
                track_event("spotlight_exited", via="right_click")
                return
            # 右键点中辅助工具 → 移除
            aid, _mode = self.aid_hit(pos)
            if aid is not None:
                self.remove_aid(aid["id"])
                track_event("aid_removed", kind=aid["kind"])
            return
        # 只有左键/笔尖接触才能启动一笔或拖动对象；右键已在上面单独处理，
        # 中键/笔侧键不能重置 pending_undo 或把一笔切成两段。
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self.current_pressure = self.event_pressure(event)
        self.drag_moved = False    # 本次按下是否真的拖动过（纯点选不触发吸附/变换埋点）
        # 辅助工具优先：任意绘图态下都能拖动已放置的教具
        aid, mode = self.aid_hit(pos)
        if aid is not None and mode == "close" and self.draw_state != "MAGNIFIER":
            self.remove_aid(aid["id"])           # 触屏可点的移除入口（等价于鼠标右键）
            track_event("aid_removed", kind=aid["kind"], via="close_handle")
            return
        if aid is not None and self.draw_state != "MAGNIFIER":
            inv, invertible = self.aid_transform(aid).inverted()
            start_local_y = inv.map(QPointF(pos)).y() if invertible else 0.0
            self.active_aid_id = aid["id"]
            self.aid_drag = {
                "id": aid["id"],
                "mode": mode,
                "start": QPointF(pos),
                "origin_pos": QPointF(aid["pos"]),
                "origin_rot": float(aid.get("rotation", 0.0)),
                "origin_span": float(aid.get("span", 70.0)),
                "origin_scale": float(aid.get("scale", 1.0)),
                "origin_length_mm": float(aid.get("length_mm", 150.0)),
                "origin_width": self.ruler_width(aid) if aid.get("kind") == "ruler" else 36.0,
                "start_local_y": start_local_y,
                "start_pointer_angle": math.degrees(math.atan2(pos.y() - aid["pos"].y(), pos.x() - aid["pos"].x())),
                "start_pointer_distance": max(1.0, math.hypot(pos.x() - aid["pos"].x(), pos.y() - aid["pos"].y())),
                # 进入教具拖拽前把当前工具体存到 aid_drag，松开时原样恢复，
                # 否则 draw_state 永久停留在 "AID"、之后画布点击匹配不到任何工具分支。
                "prev_draw_state": self.draw_state,
            }
            self.draw_state = "AID"
            self.update()
            return
        # 每次按下先暂存整页快照，松开时若内容确实变了才计入撤销栈
        self.pending_undo = self.capture_page()
        if self.draw_state == "LASER":
            self.laser_trail = []
            self.push_laser_point(pos)
            self.update()
            return
        if self.draw_state == "SELECT":
            handle = self.hit_selection_handle(pos) if self.selected_ids else None
            if handle:
                self.drag_action = handle
                self.drag_start = pos
                self.move_originals = self.capture_selection_state()
                self.transform_center = self.selection_bounds().center()
                self.transform_start_distance = max(1, self.point_distance(self.transform_center, QPointF(pos)))
                self.transform_start_angle = self.point_angle(self.transform_center, QPointF(pos))
            elif self.selected_ids and self.selection_bounds().contains(QPointF(pos)):
                self.drag_action = "move"
                self.drag_start = pos
                self.move_originals = self.capture_selection_state()
            else:
                hit = self.hit_object_at(pos)
                if self.selected_ids and not self.selection_bounds().contains(QPointF(pos)) and hit is None:
                    self.selected_ids.clear()
                    self.drag_action = "select"
                    self.selection_start = pos
                    self.selection_rect = QRectF(QPointF(pos), QPointF(pos))
                    if self.panel:
                        self.panel.sync_selection_controls()
                        self.panel.position_selection_panel(QRectF())
                    self.update()
                    return
                if hit is not None:
                    # 单击直接选中对象，并允许按住直接拖动
                    self.selected_ids = {hit}
                    self.drag_action = "move"
                    self.drag_start = pos
                    self.move_originals = self.capture_selection_state()
                    if self.panel:
                        self.panel.sync_selection_controls()
                        self.panel.position_selection_panel(self.selection_bounds())
                    track_event("selection_click", object_id=str(hit))
                    self.update()
                else:
                    self.drag_action = "select"
                    self.selection_start = pos
                    self.selection_rect = QRectF(QPointF(pos), QPointF(pos))
        elif self.draw_state == "TEXT":
            self.create_text_item(pos)
        elif self.draw_state == "SHAPE":
            self.selected_ids.clear()
            if self.shape_type in self.POINT_SHAPES:
                self.add_pending_point(pos)      # 平面图形：逐点确认
            else:
                self.shape_start = pos           # 立体图形：拖拽
                self.preview_shape = self.make_shape_item(QRectF(QPointF(pos), QPointF(pos)))
        elif self.draw_state in ("PEN", "MARKER"):
            # 又落新笔：先清掉上一笔的停笔计时，避免旧笔在新笔画到一半时突然定形
            self._cancel_smart_recognition(drop_pending=True)
            self.selected_ids.clear()
            self._begin_stroke(pos)
            self._start_smart_hold(pos)
            if self.draw_state == "MARKER":
                track_event("marker_stroke_start", color=self.marker_color.name(), width=self.marker_width, alpha=self.marker_alpha)
            else:
                track_event("stroke_start", color=self.pen_color.name(), width=self.pen_width)
        elif self.draw_state == "ERASER":
            self.last_erase_point = pos
            track_event("erase_start", eraser_type=self.eraser_type, size=self.eraser_size)
            self.execute_erase(pos)

    def mouseMoveEvent(self, event):
        pos = event.position().toPoint()
        self.mouse_pos = pos
        self.aid_hover_pos = QPointF(pos)
        self.aid_shift_pressed = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        if self.aids:
            for aid in reversed(self.aids):
                if aid.get("kind") == "protractor" and self.protractor_measurement(aid, pos, snap=self.aid_shift_pressed) is not None:
                    break
                if aid.get("kind") == "ruler" and self.ruler_measurement(aid, pos) is not None:
                    break
        self.current_pressure = self.event_pressure(event)
        if self.is_drawing_mode and self.aid_drag and (event.buttons() & Qt.MouseButton.LeftButton):
            aid = self.find_aid(self.aid_drag["id"])
            if aid is not None:
                mode = self.aid_drag["mode"]
                if mode == "move":
                    delta = QPointF(pos) - self.aid_drag["start"]
                    aid["pos"] = self.aid_drag["origin_pos"] + delta
                elif mode == "rotate":
                    start_angle = self.aid_drag["start_pointer_angle"]
                    current_angle = math.degrees(math.atan2(pos.y() - aid["pos"].y(), pos.x() - aid["pos"].x()))
                    delta_angle = (current_angle - start_angle + 180.0) % 360.0 - 180.0
                    aid["rotation"] = self.aid_drag["origin_rot"] + delta_angle
                elif mode == "width" and aid.get("kind") == "ruler":
                    inv, ok = self.aid_transform(aid).inverted()
                    if ok:
                        local_y = inv.map(QPointF(pos)).y()
                        delta = (local_y - self.aid_drag.get("start_local_y", local_y)) * 2.0
                        aid["width"] = round(clamp_ruler_width(self.aid_drag.get("origin_width", 36.0) + delta), 1)
                elif mode == "scale":
                    distance = max(1.0, math.hypot(pos.x() - aid["pos"].x(), pos.y() - aid["pos"].y()))
                    ratio = distance / self.aid_drag["start_pointer_distance"]
                    if aid.get("kind") == "ruler":
                        aid["length_mm"] = max(10.0, min(1000.0, round(self.aid_drag.get("origin_length_mm", 150.0) * ratio, 1)))
                    else:
                        aid["scale"] = max(0.4, min(3.0, round(self.aid_drag["origin_scale"] * ratio, 3)))
                self.update()
                return
        if self.is_drawing_mode and self.draw_state == "LASER":
            if event.buttons() & Qt.MouseButton.LeftButton:
                self.push_laser_point(pos)
            self.update()
            return
        if self.is_drawing_mode and self.draw_state == "SELECT" and (event.buttons() & Qt.MouseButton.LeftButton):
            if self.drag_action in ("move", "scale", "rotate") and pos != self.drag_start:
                self.drag_moved = True
            if self.drag_action == "move" and self.drag_start and self.move_originals:
                delta = QPointF(pos - self.drag_start)
                self.restore_selection_state(self.move_originals)
                self.move_selection(delta)
                if self.panel:
                    self.panel.position_selection_panel(self.selection_bounds())
            elif self.drag_action == "scale" and self.move_originals and self.transform_center:
                self.restore_selection_state(self.move_originals)
                distance = max(1, self.point_distance(self.transform_center, QPointF(pos)))
                self.scale_selection(distance / self.transform_start_distance, emit_event=False)
                if self.panel:
                    self.panel.position_selection_panel(self.selection_bounds())
            elif self.drag_action == "rotate" and self.move_originals and self.transform_center:
                self.restore_selection_state(self.move_originals)
                angle = self.point_angle(self.transform_center, QPointF(pos))
                self.rotate_selection(angle - self.transform_start_angle, emit_event=False)
                if self.panel:
                    self.panel.position_selection_panel(self.selection_bounds())
            elif self.drag_action == "select" and self.selection_start:
                self.selection_rect = QRectF(QPointF(self.selection_start), QPointF(pos))
        elif self.is_drawing_mode and self.draw_state in ("PEN", "MARKER") and (event.buttons() & Qt.MouseButton.LeftButton):
            if self.last_point is None:
                # 上一笔刚被「停笔」定形，而笔一直没抬起：就地另起一笔，书写不中断
                self._begin_stroke(pos, snapshot=True)
                self._start_smart_hold(pos)
            else:
                self.current_stroke_points.append(QPointF(pos))
                self.add_smooth_segments(pos)
                self._track_smart_hold(pos)
        elif self.is_drawing_mode and self.draw_state == "SHAPE" and (event.buttons() & Qt.MouseButton.LeftButton) and self.shape_start:
            self.preview_shape = self.make_shape_item(QRectF(QPointF(self.shape_start), QPointF(pos)))
        elif self.is_drawing_mode and self.draw_state == "ERASER" and (event.buttons() & Qt.MouseButton.LeftButton):
            self.execute_erase_path(pos)
        self.update()

    def execute_erase(self, pos):
        r_sq = (self.eraser_size / 2) ** 2
        point = QPointF(pos)
        px, py = float(pos.x()), float(pos.y())
        r = self.eraser_size / 2.0
        if self.eraser_type == "CIRCLE":
            self.all_segments = [s for s in self.all_segments if self.point_to_segment_distance_sq(pos, s["line"]) >= r_sq]
            # 形状只删除「轮廓真正进入擦除圆内」的，而不是外接包围盒被覆盖到的——
            # 后者会连空心矩形/圆等内部空白的图形一并删掉（见 _shape_outline_hit 注释）。
            self.shape_items = [item for item in self.shape_items
                                if not self._shape_outline_hit(px, py, item, r)]
            self.text_items = [item for item in self.text_items if not self.text_bounds(item).contains(point)]
            self.image_items = [item for item in self.image_items if not self.image_bounds(item).contains(point)]
        else:
            hit_id = next((s["id"] for s in self.all_segments if self.point_to_segment_distance_sq(pos, s["line"]) < r_sq), None)
            if hit_id: self.all_segments = [s for s in self.all_segments if s["id"] != hit_id]
            hit_shape = next((item["id"] for item in self.shape_items
                              if self._shape_outline_hit(px, py, item, r)), None)
            if hit_shape: self.shape_items = [item for item in self.shape_items if item["id"] != hit_shape]
            hit_text = next((item["id"] for item in self.text_items if self.text_bounds(item).contains(point)), None)
            if hit_text: self.text_items = [item for item in self.text_items if item["id"] != hit_text]
            hit_image = next((item["id"] for item in self.image_items if self.image_bounds(item).contains(point)), None)
            if hit_image: self.image_items = [item for item in self.image_items if item["id"] != hit_image]
        if self.selected_ids:
            alive = ({s["id"] for s in self.all_segments}
                     | {t["id"] for t in self.text_items}
                     | {s["id"] for s in self.shape_items}
                     | {i["id"] for i in self.image_items})
            before = len(self.selected_ids)
            self.selected_ids &= alive
            if self.panel and len(self.selected_ids) != before:
                self.panel.sync_selection_controls()
                self.panel.position_selection_panel(self.selection_bounds())
        self.update()

    def execute_erase_path(self, pos):
        if not self.last_erase_point:
            self.last_erase_point = pos
        dx = pos.x() - self.last_erase_point.x()
        dy = pos.y() - self.last_erase_point.y()
        distance = math.hypot(dx, dy)
        steps = max(1, int(distance / max(2, self.eraser_size * 0.25)))
        start = self.last_erase_point
        for step in range(1, steps + 1):
            t = step / steps
            point = QPoint(round(start.x() + dx * t), round(start.y() + dy * t))
            self.execute_erase(point)
        self.last_erase_point = pos

    def mouseReleaseEvent(self, event):
        # 与 mousePressEvent 对称：右键/中键释放不能结束仍按着的左键笔画、清掉停笔计时。
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if self.aid_drag is not None:
            # 先把暂存的绘图工具恢复回去，否则 draw_state 停在 "AID"，
            # 后续输入匹配不到任何工具分支，导致画布「点不动」直到重选工具。
            prev = self.aid_drag.get("prev_draw_state")
            if prev is not None and prev != "AID" and self.draw_state == "AID":
                self.draw_state = prev
            self.aid_drag = None
            self.update()
            if self.panel:
                self.panel.heartbeat_refresh()
            return
        if self.draw_state == "LASER":
            # 轨迹自然淡出，不写页面；按下时存的整页快照在这里作废，
            # 否则它会一直挂在 pending_undo 上白占一份页面内存。
            self.pending_undo = None
            self.update()
            if self.panel:
                self.panel.heartbeat_refresh()
            return
        if self.draw_state == "SELECT" and self.selection_rect:
            self.select_objects_in_rect(self.selection_rect)
            self.selection_rect = None
            self.selection_start = None
        if self.draw_action_changed() and getattr(self, "drag_moved", False):
            track_event("selection_transformed", action=self.drag_action, count=len(self.selected_ids))
            if self.drag_action == "move":
                self.snap_moved_line()       # 真的拖动过单条直线才做端点吸附，纯点选不动它
        if self.draw_state == "SHAPE" and self.preview_shape:
            self.finish_shape_item(self.preview_shape["rect"])
            self.preview_shape = None
            self.shape_start = None
        # 抬笔＝明确表示「就要这条手绘」，此处不做任何识别，只把停笔计时收掉。
        # 想要标准图形的话，画完最后一点后把笔停在原地别抬即可（见 _tick_smart_hold）。
        self._cancel_smart_recognition(drop_pending=True)
        self.current_stroke_points = []
        if self.pending_undo is not None:
            if self.snapshot_differs(self.pending_undo):
                self.commit_undo(self.pending_undo)
            self.pending_undo = None
        if self.panel:
            self.panel.position_selection_panel(self.selection_bounds())
        self.drag_start = None
        self.drag_action = None
        self.transform_center = None
        self.transform_start_distance = None
        self.transform_start_angle = None
        self.move_originals = None
        self.last_point = None
        self.last_erase_point = None
        if self.whiteboard_mode and self.draw_state in {"PEN", "MARKER", "ERASER", "SELECT", "TEXT"}:
            self.save_current_page()
        if self.panel: self.panel.heartbeat_refresh()

    def wheelEvent(self, event):
        if self.is_drawing_mode and self.draw_state == "MAGNIFIER":
            self.step_magnifier_zoom(1 if event.angleDelta().y() > 0 else -1)
            event.accept()
            return
        if self.is_drawing_mode and self.draw_state == "SPOTLIGHT":
            step = 24 if (event.modifiers() & Qt.KeyboardModifier.ShiftModifier) else 12
            self.spotlight_radius = max(60, min(900, int(round(self.spotlight_radius + (step if event.angleDelta().y() > 0 else -step)))))
            self.update()
            event.accept()
            return
        # 滚轮只缩放指针下命中的辅助工具，避免活动工具与指针位置不一致。
        if self.is_drawing_mode and self.aids:
            aid, _ = self.aid_hit(event.position().toPoint())
            if aid is not None:
                direction = 1 if event.angleDelta().y() > 0 else -1
                if aid.get("kind") == "ruler":
                    if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                        aid["width"] = round(clamp_ruler_width(self.ruler_width(aid) + direction * 4.0), 1)
                    else:
                        step = 10.0 if event.modifiers() & Qt.KeyboardModifier.ShiftModifier else 5.0
                        aid["length_mm"] = max(10.0, min(1000.0, round(float(aid.get("length_mm", 150.0)) + direction * step, 1)))
                else:
                    aid["scale"] = max(0.4, min(3.0, round(float(aid.get("scale", 1.0)) + direction * 0.1, 3)))
                self.active_aid_id = aid["id"]
                self.update()
                event.accept()
                return
        super().wheelEvent(event)

    def leaveEvent(self, event):
        """鼠标离开画布时把跟随光标的橡皮/荧光圈、放大镜、聚光灯挪到屏外，避免离开瞬间
        停在某处被反复重绘。否则鼠标移到工具栏或屏幕外后，下次任意 update() 都会按冻结的
        mouse_pos 再画一次光标圈/暗化层，造成"退出/移开后不立刻消失"的残影；聚光灯更会
        让整屏暗化卡在最后位置。同时清除教具的悬停测量读数。
        """
        self.mouse_pos = QPoint(-100, -100)
        self.aid_hover_pos = QPointF(-100, -100)
        if self.is_drawing_mode and (
            self.draw_state in ("ERASER", "MARKER", "MAGNIFIER", "SPOTLIGHT") or self.aids
        ):
            self.update()
        super().leaveEvent(event)

    def draw_action_changed(self):
        return self.draw_state == "SELECT" and self.drag_action in {"move", "scale", "rotate"}

# --- 2. 悬浮面板类 ---
class ControlPanel(QWidget):
    exit_requested = pyqtSignal()

    HEARTBEAT_MS = 500   # 置顶心跳间隔：200ms 会让分层窗口频繁重新合成产生闪烁

    THEMES = {
        "dark": {
            "frame": "#2d3436",
            "panel": "#353b48",
            "button": "#3d3d3d",
            "button_hover": "#555555",
            "text": "#ffffff",
            "label": "#00cec9",
            "accent": "#00cec9",
            "active_text": "#111111",
            "danger": "#c0392b",
            "mode": "#d63031",
            "mode_off": "#636e72",
            "clear": "#fab1a0",
        },
        "light": {
            "frame": "#f7f9fb",
            "panel": "#edf2f7",
            "button": "#dfe6e9",
            "button_hover": "#cfd8dc",
            "text": "#1f2933",
            "label": "#006d75",
            "accent": "#00a8a8",
            "active_text": "#ffffff",
            "danger": "#d63031",
            "mode": "#e17055",
            "mode_off": "#95a5a6",
            "clear": "#c0392b",
        },
    }

    def __init__(self):
        super().__init__()
        self.canvas = None
        self.project_path = None
        self.project_dirty = False
        self.color_buttons = []
        self.theme_name = "dark"
        self.theme = self.THEMES[self.theme_name]
        self._bound_key = None
        self._topmost_state = None
        self._drag_offset = None
        self._grabbing = False
        self.orientation = "portrait"   # portrait=竖版工具栏 | landscape=横版工具栏（标题栏旋转键切换）
        self._menu_anchor = None        # 当前子菜单对齐到哪个主栏按钮
        self.last_annotate_tool = "PEN" # 主栏「批注」回到哪支笔：记住上次选的普通笔/荧光笔/激光笔
        self.calc_panel = None
        self.roster_panel = None
        self.exit_requested.connect(QApplication.quit)

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        # 接受把 .msd / .json 项目文件拖到主面板直接打开
        self.setAcceptDrops(True)

        # 极致样式控制
        self.apply_theme()

        # 主水平布局：[工具栏] [右侧内容]
        self.h_layout = QHBoxLayout(self)
        self.h_layout.setContentsMargins(0, 0, 0, 0)
        self.h_layout.setSpacing(4)
        self.h_layout.setAlignment(Qt.AlignmentFlag.AlignTop) # 核心：横向也向上对齐

        # 1. 左侧工具栏 (固定宽度，强制紧凑)
        self.main_frame = QFrame(); self.main_frame.setObjectName("MainFrame")
        self.main_frame.setFixedWidth(150)
        self.toolbar_layout = QVBoxLayout(self.main_frame)
        self.toolbar_layout.setContentsMargins(8, 8, 8, 8)
        self.toolbar_layout.setSpacing(2) # 极致压缩上下间距
        self.toolbar_layout.setAlignment(Qt.AlignmentFlag.AlignTop) # 核心：垂直向上对齐，杜绝空缺

        # 标题栏：应用名 + 版本 + 旋转（横竖切换）按钮。竖版下也在显眼位置，横版下作为标题
        title_row = QHBoxLayout(); title_row.setSpacing(4)
        self.title_label = QLabel(f" ⠿ {tr('app')} {APP_VERSION}")
        title_row.addWidget(self.title_label)
        # 旋转键：纯图标、无文字。带文字时按钮要占掉标题栏一半宽度，横版下直接把
        # 标题压得显示不全；同时不设 ToolTip——提示气泡会弹在光标正下方盖住标题栏，
        # 而它作为独立顶层窗口又排不进本程序的置顶层，出现半截黑框的遮挡残影。
        self.btn_rotate = QPushButton(); self.btn_rotate.setObjectName("RotateBtn")
        self.btn_rotate.setFlat(True)
        self.btn_rotate.setIconSize(QSize(20, 20))
        # 图标在这里就先画一次：apply_theme() 在构造函数里跑得比本按钮还早，
        # 只靠它设置的话，按钮会一直空到下一次切主题为止。
        self.btn_rotate.setIcon(make_rotate_icon(self.theme["label"], 22))
        self.btn_rotate.setAccessibleName(tr("rotate"))
        self.btn_rotate.clicked.connect(self.toggle_orientation)
        title_row.addWidget(self.btn_rotate)
        self.toolbar_layout.addLayout(title_row)

        self.btn_mode = QPushButton(tr("passthrough")); self.btn_mode.setObjectName("ModeBtn")
        self.btn_mode.clicked.connect(self.toggle_mode); self.toolbar_layout.addWidget(self.btn_mode)

        self.btn_pen = QPushButton(tr("annotate")); self.btn_pen.setObjectName("ActiveTool")
        self.btn_pen.clicked.connect(self.handle_annotate_click); self.toolbar_layout.addWidget(self.btn_pen)

        self.btn_eraser = QPushButton(tr("eraser")); self.btn_eraser.clicked.connect(self.handle_eraser_click)
        self.toolbar_layout.addWidget(self.btn_eraser)

        self.btn_select = QPushButton(tr("select")); self.btn_select.clicked.connect(self.handle_select_click)
        self.toolbar_layout.addWidget(self.btn_select)

        self.btn_text = QPushButton(tr("text")); self.btn_text.clicked.connect(self.handle_text_click)
        self.toolbar_layout.addWidget(self.btn_text)

        self.btn_shape = QPushButton(tr("shape")); self.btn_shape.clicked.connect(self.handle_shape_click)
        self.toolbar_layout.addWidget(self.btn_shape)

        self.btn_tools = QPushButton(tr("tools")); self.btn_tools.clicked.connect(self.handle_tools_click)
        self.toolbar_layout.addWidget(self.btn_tools)

        self.btn_file = QPushButton(tr("file")); self.btn_file.clicked.connect(self.handle_file_click)
        self.toolbar_layout.addWidget(self.btn_file)

        # 撤销 / 重做 / 清屏
        btn_row = QHBoxLayout(); btn_row.setSpacing(2)
        self.btn_undo = QPushButton(tr("undo")); self.btn_undo.setObjectName("HistoryBtn"); self.btn_undo.clicked.connect(self.undo); self.btn_undo.setEnabled(False); btn_row.addWidget(self.btn_undo)
        self.btn_redo = QPushButton(tr("redo")); self.btn_redo.setObjectName("HistoryBtn"); self.btn_redo.clicked.connect(self.redo); self.btn_redo.setEnabled(False); btn_row.addWidget(self.btn_redo)
        self.btn_clear = QPushButton(tr("clear")); self.btn_clear.setObjectName("HistoryBtn"); self.btn_clear.clicked.connect(self.clear); btn_row.addWidget(self.btn_clear)
        self.toolbar_layout.addLayout(btn_row)

        self.btn_whiteboard = QPushButton(tr("whiteboard")); self.btn_whiteboard.clicked.connect(self.toggle_whiteboard); self.toolbar_layout.addWidget(self.btn_whiteboard)

        # 白板控制区：默认隐藏，进入白板后才显示。
        # 用一个 QGridLayout 承载，横竖版切换时只重排格子（见 _layout_wb_box）：
        # 竖版两行三列，横版一行五列。旧实现是写死的「两行」嵌套布局，横版工具栏只有
        # 一行高，两行按钮被压进去就会把「上页/下页/新页/黑板」的字裁掉一半。
        self.wb_box = QWidget()
        self.wb_grid = QGridLayout(self.wb_box)
        self.wb_grid.setContentsMargins(0, 0, 0, 0); self.wb_grid.setSpacing(2)
        self.btn_prev_page = QPushButton(tr("prev")); self.btn_prev_page.clicked.connect(lambda: self.switch_whiteboard_page(-1))
        self.page_label = QPushButton("1/1")
        self.page_label.setObjectName("PageLabelBtn")
        self.page_label.clicked.connect(self.toggle_thumbnail_panel)
        self.btn_next_page = QPushButton(tr("next")); self.btn_next_page.clicked.connect(lambda: self.switch_whiteboard_page(1))
        self.btn_new_page = QPushButton(tr("new_page")); self.btn_new_page.clicked.connect(self.new_whiteboard_page)
        self.btn_board_style = QPushButton(tr("board")); self.btn_board_style.clicked.connect(self.toggle_board_style)
        self._layout_wb_box()
        self.wb_box.setVisible(False)
        self.toolbar_layout.addWidget(self.wb_box)

        self.btn_theme = QPushButton(tr("light_theme"))
        self.btn_theme.clicked.connect(self.toggle_theme)
        self.toolbar_layout.addWidget(self.btn_theme)

        self.thumbnail_panel = QWidget()
        self.thumbnail_panel.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.thumbnail_panel.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        thumb_layout = QVBoxLayout(self.thumbnail_panel)
        self.thumbnail_list = QListWidget(); self.thumbnail_list.setViewMode(QListWidget.ViewMode.IconMode)
        self.thumbnail_list.setIconSize(QSize(260, 170)); self.thumbnail_list.setGridSize(QSize(280, 205))
        self.thumbnail_list.setMinimumSize(580, 430)
        self.thumbnail_list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.thumbnail_list.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.thumbnail_list.currentRowChanged.connect(self._thumbnail_page_changed)
        # 触屏：允许直接用手指按住列表甩动翻页，而不是去够那条细滚动条
        try:
            QScroller.grabGesture(self.thumbnail_list.viewport(),
                                  QScroller.ScrollerGestureType.TouchGesture)
        except Exception:
            pass
        thumb_layout.addWidget(self.thumbnail_list)
        self.thumbnail_panel.hide()
        self.thumbnail_panel.setStyleSheet(self.styleSheet())

        self.btn_exit = QPushButton(tr("exit")); self.btn_exit.clicked.connect(QApplication.quit); self.toolbar_layout.addWidget(self.btn_exit)

        # 2. 子菜单浮窗：独立置顶小窗（不再挤在主面板窗口里）。
        #    换内容/调尺寸/定位全部在隐藏状态下完成后再显示——半透明窗口只要不在
        #    可见状态下缩放，合成器就不会出现新旧画面交替（闪烁/叠影的根源）。
        self.menu_panel = QWidget()
        self.menu_panel.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.menu_panel.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.menu_panel.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)   # 不抢焦点
        self.menu_layout = QVBoxLayout(self.menu_panel)
        self.menu_layout.setContentsMargins(0, 0, 0, 0)
        self.menu_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.draw_sub = QFrame(); self.draw_sub.setProperty("class", "Sub"); self.draw_sub_layout = QVBoxLayout(self.draw_sub)
        self.draw_sub_layout.setSpacing(4); self.setup_draw_sub(); self.menu_layout.addWidget(self.draw_sub); self.draw_sub.setVisible(False)

        self.annotate_sub = QFrame(); self.annotate_sub.setProperty("class", "Sub"); self.annotate_sub_layout = QVBoxLayout(self.annotate_sub)
        self.annotate_sub_layout.setSpacing(4); self.setup_annotate_sub(); self.menu_layout.addWidget(self.annotate_sub); self.annotate_sub.setVisible(False)

        self.eraser_sub = QFrame(); self.eraser_sub.setProperty("class", "Sub"); self.eraser_sub_layout = QVBoxLayout(self.eraser_sub)
        self.eraser_sub_layout.setSpacing(4); self.setup_eraser_sub(); self.menu_layout.addWidget(self.eraser_sub); self.eraser_sub.setVisible(False)

        self.shape_sub = QFrame(); self.shape_sub.setProperty("class", "Sub"); self.shape_sub_layout = QVBoxLayout(self.shape_sub)
        self.shape_sub_layout.setSpacing(4); self.setup_shape_sub(); self.menu_layout.addWidget(self.shape_sub); self.shape_sub.setVisible(False)

        self.marker_sub = QFrame(); self.marker_sub.setProperty("class", "Sub"); self.marker_sub_layout = QVBoxLayout(self.marker_sub)
        self.marker_sub_layout.setSpacing(4); self.setup_marker_sub(); self.menu_layout.addWidget(self.marker_sub); self.marker_sub.setVisible(False)

        self.laser_sub = QFrame(); self.laser_sub.setProperty("class", "Sub"); self.laser_sub_layout = QVBoxLayout(self.laser_sub)
        self.laser_sub_layout.setSpacing(4); self.setup_laser_sub(); self.menu_layout.addWidget(self.laser_sub); self.laser_sub.setVisible(False)

        self.tools_sub = QFrame(); self.tools_sub.setProperty("class", "Sub"); self.tools_sub_layout = QVBoxLayout(self.tools_sub)
        self.tools_sub_layout.setSpacing(4); self.setup_tools_sub(); self.menu_layout.addWidget(self.tools_sub); self.tools_sub.setVisible(False)

        self.file_sub = QFrame(); self.file_sub.setProperty("class", "Sub"); self.file_sub_layout = QVBoxLayout(self.file_sub)
        self.file_sub_layout.setSpacing(4); self.setup_file_sub(); self.menu_layout.addWidget(self.file_sub); self.file_sub.setVisible(False)

        self.aid_sub = QFrame(); self.aid_sub.setProperty("class", "Sub"); self.aid_sub_layout = QVBoxLayout(self.aid_sub)
        self.aid_sub_layout.setSpacing(4); self.setup_aid_sub(); self.menu_layout.addWidget(self.aid_sub); self.aid_sub.setVisible(False)

        self.magnifier_sub = QFrame(); self.magnifier_sub.setProperty("class", "Sub"); self.magnifier_sub_layout = QVBoxLayout(self.magnifier_sub)
        self.magnifier_sub_layout.setSpacing(4); self.setup_magnifier_sub(); self.menu_layout.addWidget(self.magnifier_sub); self.magnifier_sub.setVisible(False)

        # 计时器：先建引擎状态再建界面
        self.timer_mode = "DOWN"          # DOWN=倒计时 / UP=正计时
        self.timer_target = 300           # 倒计时目标秒数
        self.timer_left = 300.0           # 当前剩余(倒)或已计(正)秒数
        self.timer_running = False
        self.timer_alerting = False
        self._timer_last = 0.0
        self._flash_on = False
        self.timer_clock = QTimer(self); self.timer_clock.setInterval(200); self.timer_clock.timeout.connect(self._timer_tick)
        self.timer_flash = QTimer(self); self.timer_flash.setInterval(350); self.timer_flash.timeout.connect(self._timer_flash)
        self.timer_sub = QFrame(); self.timer_sub.setProperty("class", "Sub"); self.timer_sub_layout = QVBoxLayout(self.timer_sub)
        self.timer_sub_layout.setSpacing(4); self.setup_timer_sub(); self.menu_layout.addWidget(self.timer_sub); self.timer_sub.setVisible(False)

        # 点名名单
        self.roster = []
        self.roster_drawn = set()
        self.load_roster()

        self.select_panel = QFrame()
        self.select_panel.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.select_panel.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.select_panel.setProperty("class", "Sub")
        self.select_sub_layout = QVBoxLayout(self.select_panel)
        self.select_sub_layout.setSpacing(4)
        self.setup_select_sub()
        self.select_panel.hide()

        # 迷你计时器：计时进行中且子菜单关闭时，悬浮在屏幕顶端居中
        self.mini_timer = QWidget()
        self.mini_timer.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.mini_timer.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.mini_timer.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        mini_layout = QVBoxLayout(self.mini_timer)
        mini_layout.setContentsMargins(0, 0, 0, 0)
        self.mini_timer_label = QLabel("00:00")
        self.mini_timer_label.setObjectName("MiniTimer")
        self.mini_timer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mini_layout.addWidget(self.mini_timer_label)
        self.mini_timer.mousePressEvent = lambda e: self.handle_timer_click()   # 点迷你计时器打开计时面板
        self.mini_timer.hide()
        self.update_timer_ui()      # mini 建好后补一次初始同步

        # 计算器 / 点名 独立浮窗
        self.calc_panel = None
        self.roster_panel = None
        self._calc_expr = "0"
        self._calc_display = None

        self.h_layout.addWidget(self.main_frame)

        self._syncing_thumbnails = False
        self._thumbnail_refresh_timer = QTimer(self)
        self._thumbnail_refresh_timer.setSingleShot(True)
        self._thumbnail_refresh_timer.setInterval(100)
        self._thumbnail_refresh_timer.timeout.connect(self.refresh_page_thumbnails)
        # 缩略图实时渲染：面板打开期间按节拍比对内容指纹，变了就重画当前页
        self._thumbnail_signature = None
        self._thumbnail_live_timer = QTimer(self)
        self._thumbnail_live_timer.setInterval(self.THUMBNAIL_LIVE_MS)
        self._thumbnail_live_timer.timeout.connect(self._tick_live_thumbnail)
        self._laser_fade = QTimer(self)
        self._laser_fade.setInterval(33)
        self._laser_fade.timeout.connect(self._tick_laser_fade)
        self._resize_to_content()
        self.timer = QTimer(self); self.timer.timeout.connect(self.heartbeat_refresh); self.timer.start(self.HEARTBEAT_MS)

        # 自动保存定时器：每30秒保存一次画布内容
        self.autosave_timer = QTimer(self)
        self.autosave_timer.timeout.connect(self.auto_save)
        self.autosave_timer.start(AUTOSAVE_INTERVAL * 1000)  # 转换为毫秒

        self.listener = keyboard.Listener(on_press=self.on_global_key_press); self.listener.start()
        track_event("app_started", theme=self.theme_name)

    def apply_theme(self):
        t = self.theme
        self.setStyleSheet(f"""
            QWidget#MainFrame {{ background-color: {t["frame"]}; border-radius: 12px; border: 2px solid {t["accent"]}; }}
            /* 普通按钮恢复紧凑高度：min-height 会和上下 padding【相加】，之前写成
               min-height:38 + padding:16 + margin:2，实际每颗按钮至少 56px，竖栏因此
               被拉成截图里近百像素一颗。触控命中不能靠粗暴撑高整个界面。 */
            QPushButton {{ background-color: {t["button"]}; color: {t["text"]}; border-radius: 6px; padding: 6px 8px; font-weight: bold; border: none; margin: 1px; }}
            QPushButton:hover {{ background-color: {t["button_hover"]}; }}
            QPushButton:pressed {{ background-color: {t["accent"]}; color: {t["active_text"]}; }}
            QPushButton:disabled {{ background-color: {t["button"]}; color: {t["mode_off"]}; }}
            QPushButton:checked {{ background-color: {t["accent"]}; color: {t["active_text"]}; }}
            QPushButton#HistoryBtn {{ padding: 8px 2px; margin: 1px 0px; }}
            QPushButton#ModeBtn {{ background-color: {t["mode"]}; color: white; }}
            QPushButton#ActiveTool {{ background-color: {t["accent"]}; color: {t["active_text"]}; }}
            QPushButton#ArrowBtn {{ background-color: {t["button"]}; min-width: {TOUCH_ARROW}px; max-width: {TOUCH_ARROW}px; min-height: {TOUCH_ARROW}px; max-height: {TOUCH_ARROW}px; padding: 0px; font-size: 12px; }}
            QPushButton#SquareBtn {{ min-width: {TOUCH_SQUARE}px; max-width: {TOUCH_SQUARE}px; min-height: {TOUCH_SQUARE}px; max-height: {TOUCH_SQUARE}px; padding: 0px; font-size: 15px; }}
            QPushButton#RotateBtn {{ min-width: {TOUCH_SQUARE}px; max-width: {TOUCH_SQUARE}px; min-height: {TOUCH_SQUARE}px; max-height: {TOUCH_SQUARE}px; padding: 0px; margin: 0px; background-color: transparent; border: none; }}
            QPushButton#RotateBtn:hover {{ background-color: {t["button_hover"]}; border-radius: 6px; }}
            QPushButton#RotateBtn:pressed {{ background-color: {t["accent"]}; border-radius: 6px; }}
            QLabel {{ color: {t["label"]}; font-size: 11px; padding: 2px; }}
            QLabel#TimerDisplay {{ font-size: 26px; font-weight: bold; color: {t["accent"]}; font-family: Consolas, "Microsoft YaHei"; padding: 2px 6px; }}
            QLabel#MiniTimer {{ background-color: {t["frame"]}; border: 2px solid {t["accent"]}; border-radius: 10px; font-size: 20px; font-weight: bold; color: {t["accent"]}; font-family: Consolas, "Microsoft YaHei"; padding: 5px 16px; }}
            QMenu {{ background-color: {t["panel"]}; color: {t["text"]}; border: 1.5px solid {t["accent"]}; border-radius: 6px; padding: 4px; }}
            QMenu::item {{ padding: 10px 24px; border-radius: 4px; }}
            QMenu::item:selected {{ background-color: {t["accent"]}; color: {t["active_text"]}; }}
            QMenu::item:disabled {{ color: {t["mode_off"]}; }}
            QToolTip {{ background-color: {t["panel"]}; color: {t["text"]}; border: 1px solid {t["accent"]}; border-radius: 4px; padding: 4px 6px; font-size: 12px; }}
            .Sub {{ background-color: {t["panel"]}; border-radius: 10px; border: 1.5px solid {t["accent"]}; padding: 6px; }}
            QSlider {{ min-height: {TOUCH_SLIDER}px; }}
            QSlider::groove:horizontal {{ height: 6px; background: {t["button_hover"]}; border-radius: 3px; }}
            QSlider::handle:horizontal {{ background: {t["accent"]}; width: {TOUCH_SLIDER_HANDLE}px; height: {TOUCH_SLIDER_HANDLE}px; margin: -{TOUCH_SLIDER_HANDLE // 2 - 3}px 0; border-radius: {TOUCH_SLIDER_HANDLE // 2}px; }}
            QListWidget {{ background-color: {t["panel"]}; color: {t["text"]}; border: none; }}
            QColorDialog QPushButton, QColorDialog QLabel {{ font-size: 12px; }}
        """)
        # 子菜单浮窗/选中面板/迷你计时器是独立顶层窗口，主面板的样式表覆盖不到，需各自下发
        for floating in (getattr(self, "menu_panel", None), getattr(self, "select_panel", None),
                         getattr(self, "mini_timer", None), getattr(self, "calc_panel", None),
                         getattr(self, "roster_panel", None), getattr(self, "thumbnail_panel", None)):
            if floating is not None:
                floating.setStyleSheet(self.styleSheet())
        if hasattr(self, "btn_clear"):
            self.btn_clear.setStyleSheet(f"color: {t['clear']};")
        if hasattr(self, "btn_theme"):
            # Light mode → offer dark; dark mode → offer light.
            self.btn_theme.setText(tr("dark_theme") if self.theme_name == "light" else tr("light_theme"))
        if hasattr(self, "btn_exit"):
            self.btn_exit.setStyleSheet(f"background-color: {t['danger']}; color: white;")
        if hasattr(self, "btn_rotate"):
            # 图标按主题重绘：亮色主题下白色箭头会看不见
            self.btn_rotate.setIcon(make_rotate_icon(t["label"], 22))

    def _layout_wb_box(self):
        """白板控制区始终保持紧凑两行。

        横版主栏本身是一行，若把 5 个白板按钮也横向塞成一行，会额外吃掉约 300px，
        把后面的主题/退出按钮挤出屏幕，正是截图中的错位。白板控制区是一个独立的小组，
        在横版里也应保持「翻页一行 + 新页/板色一行」的紧凑块。
        """
        widgets = (self.btn_prev_page, self.page_label, self.btn_next_page,
                   self.btn_new_page, self.btn_board_style)
        for widget in widgets:
            self.wb_grid.removeWidget(widget)
        self.wb_grid.addWidget(self.btn_prev_page, 0, 0)
        self.wb_grid.addWidget(self.page_label, 0, 1)
        self.wb_grid.addWidget(self.btn_next_page, 0, 2)
        self.wb_grid.addWidget(self.btn_new_page, 1, 0, 1, 2)
        self.wb_grid.addWidget(self.btn_board_style, 1, 2)
        # 白板小按钮不继承主栏的大尺寸；固定到可读但紧凑的高度，避免横版整栏被撑高。
        for widget in widgets:
            widget.setMinimumHeight(0)
            widget.setMaximumHeight(28)
            widget.setVisible(True)
        self.wb_grid.invalidate()
        self.wb_grid.activate()

    def _thumbnail_page_changed(self, row):
        if getattr(self, "_syncing_thumbnails", False) or row < 0:
            return
        if self.canvas and self.canvas.whiteboard_mode and row != self.canvas.current_page:
            self.canvas.switch_page(row - self.canvas.current_page)
            self.update_whiteboard_ui()

    def toggle_thumbnail_panel(self):
        if not self.canvas or not self.canvas.whiteboard_mode:
            return
        if self.thumbnail_panel.isVisible():
            self.thumbnail_panel.hide()
            self._thumbnail_live_timer.stop()
            return
        self.refresh_page_thumbnails(force=True)
        self.thumbnail_panel.adjustSize()
        x, y = self._floating_anchor(self.thumbnail_panel.width(), self.thumbnail_panel.height())
        self.thumbnail_panel.move(x, y)
        self.thumbnail_panel.show()
        self.raise_floating(self.thumbnail_panel)
        self._thumbnail_live_timer.start()      # 打开即进入实时渲染

    THUMBNAIL_SIZE = QSize(260, 170)
    THUMBNAIL_LIVE_MS = 150        # 实时刷新节拍：约 7fps，肉眼上就是「落墨即现」
    THUMBNAIL_MAX_MS = 2000        # 退避上限：再重的页面也至少两秒更新一次
    THUMBNAIL_DUTY = 10            # 节拍 ≥ 单帧渲染耗时的 10 倍，即最多占用 10% 的主线程

    def refresh_page_thumbnails(self, force=False):
        if not hasattr(self, "thumbnail_list") or not self.canvas:
            return
        # 缩略图面板没打开时不必渲染：update_whiteboard_ui 每次翻页/进出白板都会调到这里，
        # 而每次都会把整本白板逐页渲染成 pixmap，页数一多就是明显的翻页卡顿。
        if not force and not self.thumbnail_panel.isVisible():
            return
        self._syncing_thumbnails = True
        try:
            self.thumbnail_list.clear()
            pages = self.canvas.pages if self.canvas.whiteboard_mode else [self.canvas.capture_page()]
            current = self.canvas.current_page
            for index, page in enumerate(pages):
                # 当前页取实时内容：pages[current] 要等松手 save_current_page() 才更新，
                # 用它渲染的话正在写的这一笔永远缺席，缩略图始终慢半拍。
                source = self.canvas.live_page() if (self.canvas.whiteboard_mode and index == current) else page
                pixmap = self.canvas.render_page_pixmap(source, self.THUMBNAIL_SIZE)
                item = QListWidgetItem(QIcon(pixmap), trf("page_label", index=index + 1))
                item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter)
                self.thumbnail_list.addItem(item)
            if pages:
                self.thumbnail_list.setCurrentRow(min(current, len(pages) - 1))
        finally:
            self._syncing_thumbnails = False
        self._thumbnail_signature = self.canvas.content_signature()

    def _tick_live_thumbnail(self):
        """实时缩略图节拍：只在内容真的变了时重画当前页那一格。"""
        if getattr(self, "_grabbing", False):
            return                              # 抓屏是暂时隐藏，不要因此永久 stop
        if not self.canvas or not self.thumbnail_panel.isVisible() or not self.canvas.whiteboard_mode:
            self._thumbnail_live_timer.stop()
            return
        signature = self.canvas.content_signature()
        if signature == getattr(self, "_thumbnail_signature", None):
            return
        self._thumbnail_signature = signature
        if self.thumbnail_list.count() != len(self.canvas.pages):
            self.refresh_page_thumbnails(force=True)   # 加/删页：整列表重建
            return
        item = self.thumbnail_list.item(self.canvas.current_page)
        if item is None:
            self.refresh_page_thumbnails(force=True)
            return
        started = time.perf_counter()
        item.setIcon(QIcon(self.canvas.render_page_pixmap(self.canvas.live_page(), self.THUMBNAIL_SIZE)))
        # 缩略图渲染跑在主线程上，写满一页的白板单帧要几十毫秒——固定节拍会按比例吃掉
        # 笔迹的绘制时间，表现为「越写越顿」。这里按实测耗时把节拍拉长到它的 10 倍，
        # 让缩略图最多占用 10% 主线程：轻页面保持 150ms「落墨即现」，重页面自动降频。
        cost_ms = (time.perf_counter() - started) * 1000.0
        target = int(max(self.THUMBNAIL_LIVE_MS, min(self.THUMBNAIL_MAX_MS, cost_ms * self.THUMBNAIL_DUTY)))
        if abs(self._thumbnail_live_timer.interval() - target) > 20:
            self._thumbnail_live_timer.setInterval(target)

    def update_whiteboard_ui(self):
        if not self.canvas:
            return
        total = max(1, len(self.canvas.pages))
        current = self.canvas.current_page + 1
        if hasattr(self, "page_label"):
            self.page_label.setText(f"{current}/{total}")
        if hasattr(self, "btn_whiteboard"):
            self.btn_whiteboard.setText(tr("exit_whiteboard") if self.canvas.whiteboard_mode else tr("whiteboard"))
        if hasattr(self, "btn_board_style"):
            self.btn_board_style.setText(tr("board_white") if self.canvas.board_style == "BLACK" else tr("board"))
        if hasattr(self, "wb_box"):
            self.wb_box.setVisible(self.canvas.whiteboard_mode)   # 白板设置只在白板模式显示
            self._resize_to_content()
        # 退出白板时必须把可能打开着的缩略图面板一起收起：toggle_thumbnail_panel 在非白板态会
        # 直接 return 不允许再关闭，若不在这里主动 hide，面板会一直留在屏幕上、还显示一张
        # 名为「第 1 页」的误导性整屏截图缩略图，直到重启程序。
        if hasattr(self, "thumbnail_panel") and not self.canvas.whiteboard_mode:
            self.thumbnail_panel.hide()
            self._thumbnail_live_timer.stop()
        self.refresh_page_thumbnails()

    def toggle_whiteboard(self):
        if self.canvas.whiteboard_mode:
            self.canvas.exit_whiteboard()
            self.select_panel.hide()
        else:
            self.canvas.enter_whiteboard()
            self.select_panel.hide()
        self.update_whiteboard_ui()
        self.heartbeat_refresh()

    def new_whiteboard_page(self):
        self.canvas.new_page()
        self.update_whiteboard_ui()
        self.select_panel.hide()

    def switch_whiteboard_page(self, offset):
        self.canvas.switch_page(offset)
        self.update_whiteboard_ui()
        self.select_panel.hide()

    def toggle_board_style(self):
        self.canvas.toggle_board_style()
        self.project_dirty = True
        self.update_whiteboard_ui()

    def toggle_theme(self):
        self.theme_name = "light" if self.theme_name == "dark" else "dark"
        self.theme = self.THEMES[self.theme_name]
        self.apply_theme()
        self.refresh_ui()
        track_event("theme_changed", theme=self.theme_name)

    def on_global_key_press(self, key):
        if key == keyboard.Key.f12:
            self.exit_requested.emit()
            return False

    def setup_draw_sub(self):
        grid = QGridLayout(); grid.setSpacing(4)
        colors = ["#ff4757", "#1e90ff", "#2ed573", "#ffa502", "#ffffff", "#a29bfe", "#00cec9", "#000000", "#ff7f50"]
        for i, hex_c in enumerate(colors):
            btn = QPushButton(); btn.setFixedSize(TOUCH_SWATCH, TOUCH_SWATCH); btn.setProperty("color_val", hex_c)
            btn.setStyleSheet(f"background-color: {hex_c}; border: 1px solid #777;")
            btn.clicked.connect(self.on_color_clicked); grid.addWidget(btn, i // 5, i % 5); self.color_buttons.append(btn)
        rainbow = QPushButton("🌈"); rainbow.setFixedSize(TOUCH_SWATCH, TOUCH_SWATCH); rainbow.setStyleSheet("background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 red, stop:1 blue); border: 1px solid #777;")
        rainbow.clicked.connect(self.open_custom_color); grid.addWidget(rainbow, 1, 4); self.color_buttons.append(rainbow)
        self.draw_sub_layout.addLayout(grid)
        self.color_preview = QWidget(); self.color_preview.setFixedHeight(6); self.draw_sub_layout.addWidget(self.color_preview)

        # 粗细调节 (滑轨+箭头回归)
        self.label_w = QLabel(trf("width_value", value=4)); self.label_w.setStyleSheet("color: white; font-weight: bold;"); self.draw_sub_layout.addWidget(self.label_w)
        s_row = QHBoxLayout(); s_row.setSpacing(2)
        btn_d = QPushButton("▼"); btn_d.setObjectName("ArrowBtn"); btn_d.clicked.connect(lambda: self.pen_slider.setValue(self.pen_slider.value()-1))
        self.pen_slider = QSlider(Qt.Orientation.Horizontal); self.pen_slider.setRange(1, 40); self.pen_slider.setValue(4); self.pen_slider.setFixedWidth(80)
        self.pen_slider.valueChanged.connect(self.on_pen_slider_changed)
        btn_u = QPushButton("▲"); btn_u.setObjectName("ArrowBtn"); btn_u.clicked.connect(lambda: self.pen_slider.setValue(self.pen_slider.value()+1))
        s_row.addWidget(btn_d); s_row.addWidget(self.pen_slider); s_row.addWidget(btn_u); self.draw_sub_layout.addLayout(s_row)

        # 常驻智能识别开关：批注笔画完自动把近似图形转成标准图形
        self.btn_smart_toggle = QPushButton(tr("smart_shapes_on"))
        self.btn_smart_toggle.setCheckable(True)
        self.btn_smart_toggle.setChecked(True)
        self.btn_smart_toggle.clicked.connect(self.on_smart_toggle)
        self.draw_sub_layout.addWidget(self.btn_smart_toggle)
        self.draw_sub_layout.addWidget(QLabel(tr("smart_shapes_hint")))

    def setup_annotate_sub(self):
        """批注入口：普通笔 / 荧光笔 / 激光笔（始终三选一，不再藏设置里）。"""
        self.annotate_sub_layout.addWidget(QLabel(tr("choose_annotate_tool")))
        self.btn_ann_pen = QPushButton(tr("pen"))
        self.btn_ann_pen.clicked.connect(self.choose_pen_tool)
        self.annotate_sub_layout.addWidget(self.btn_ann_pen)
        self.btn_ann_marker = QPushButton(tr("marker"))
        self.btn_ann_marker.clicked.connect(self.choose_marker_tool)
        self.annotate_sub_layout.addWidget(self.btn_ann_marker)
        self.btn_ann_laser = QPushButton(tr("laser"))
        self.btn_ann_laser.clicked.connect(self.choose_laser_tool)
        self.annotate_sub_layout.addWidget(self.btn_ann_laser)
        self.annotate_sub_layout.addWidget(QLabel(tr("annotate_hint")))

    def setup_laser_sub(self):
        self.laser_sub_layout.addWidget(QLabel(tr("laser_color")))
        grid = QGridLayout(); grid.setSpacing(4)
        colors = ["#ff0000", "#00ff66", "#00e5ff", "#ffea00", "#ff6bff", "#ffffff"]
        self.laser_color_buttons = []
        for i, hex_c in enumerate(colors):
            btn = QPushButton(); btn.setFixedSize(TOUCH_SWATCH, TOUCH_SWATCH); btn.setProperty("color_val", hex_c)
            btn.setStyleSheet(f"background-color: {hex_c}; border: 1px solid #777;")
            btn.clicked.connect(self.on_laser_color_clicked)
            grid.addWidget(btn, i // 3, i % 3)
            self.laser_color_buttons.append(btn)
        rainbow = QPushButton("🌈"); rainbow.setFixedSize(TOUCH_SWATCH, TOUCH_SWATCH)
        rainbow.setStyleSheet("background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 red, stop:1 cyan); border: 1px solid #777;")
        rainbow.clicked.connect(self.open_laser_color)
        grid.addWidget(rainbow, 2, 0)
        self.laser_color_buttons.append(rainbow)
        self.laser_sub_layout.addLayout(grid)
        self.laser_width_label = QLabel(trf("laser_dot", value=14))
        self.laser_sub_layout.addWidget(self.laser_width_label)
        row = QHBoxLayout(); row.setSpacing(2)
        btn_d = QPushButton("▼"); btn_d.setObjectName("ArrowBtn"); btn_d.clicked.connect(lambda: self.laser_width_slider.setValue(self.laser_width_slider.value() - 1))
        self.laser_width_slider = QSlider(Qt.Orientation.Horizontal); self.laser_width_slider.setRange(6, 40); self.laser_width_slider.setValue(14); self.laser_width_slider.setFixedWidth(80)
        self.laser_width_slider.valueChanged.connect(self.on_laser_width_changed)
        btn_u = QPushButton("▲"); btn_u.setObjectName("ArrowBtn"); btn_u.clicked.connect(lambda: self.laser_width_slider.setValue(self.laser_width_slider.value() + 1))
        row.addWidget(btn_d); row.addWidget(self.laser_width_slider); row.addWidget(btn_u)
        self.laser_sub_layout.addLayout(row)
        self.laser_sub_layout.addWidget(QLabel(tr("laser_hint")))

    def setup_tools_sub(self):
        self.tools_sub_layout.addWidget(QLabel(tr("tools")))
        items = [
            (tr("calculator"), self.open_calculator),
            (tr("roster"), self.open_roster_panel),
            (tr("aids"), self.open_aid_menu),
            (tr("timer"), self.handle_timer_click),
            (tr("magnifier"), self.handle_magnifier_click),
            (tr("spotlight"), self.handle_spotlight_click),
        ]
        for label, handler in items:
            btn = QPushButton(label)
            btn.clicked.connect(handler)
            self.tools_sub_layout.addWidget(btn)

    def setup_file_sub(self):
        """Build one flat file panel; project/import/export remain distinct groups."""
        self.file_sub_layout.addWidget(QLabel(tr("project_group")))
        project_grid = QGridLayout(); project_grid.setSpacing(3)
        self.btn_open_project = QPushButton(tr("open_project"))
        self.btn_open_project.clicked.connect(self.open_project_from_file_panel)
        self.btn_save_project = QPushButton(tr("save_project"))
        self.btn_save_project.clicked.connect(self.save_project_from_file_panel)
        self.btn_save_project_as = QPushButton(tr("save_project_as"))
        self.btn_save_project_as.clicked.connect(self.save_project_as_from_file_panel)
        project_grid.addWidget(self.btn_open_project, 0, 0)
        project_grid.addWidget(self.btn_save_project, 0, 1)
        project_grid.addWidget(self.btn_save_project_as, 1, 0, 1, 2)
        self.file_sub_layout.addLayout(project_grid)

        self.file_sub_layout.addWidget(QLabel(tr("import_group")))
        self.btn_import_media = QPushButton(tr("import_media"))
        self.btn_import_media.clicked.connect(self.import_media_from_file_panel)
        self.file_sub_layout.addWidget(self.btn_import_media)

        self.file_sub_layout.addWidget(QLabel(tr("export_group")))
        export_grid = QGridLayout(); export_grid.setSpacing(3)
        self.btn_export_png = QPushButton(tr("export_png"))
        self.btn_export_pdf = QPushButton(tr("export_pdf"))
        self.btn_export_svg = QPushButton(tr("export_svg"))
        self.btn_export_eps = QPushButton(tr("export_eps"))
        for button, fmt in (
            (self.btn_export_png, "PNG"), (self.btn_export_pdf, "PDF"),
            (self.btn_export_svg, "SVG"), (self.btn_export_eps, "EPS"),
        ):
            button.clicked.connect(lambda _=False, value=fmt: self.do_export(value))
        export_grid.addWidget(self.btn_export_png, 0, 0)
        export_grid.addWidget(self.btn_export_pdf, 0, 1)
        export_grid.addWidget(self.btn_export_svg, 1, 0)
        export_grid.addWidget(self.btn_export_eps, 1, 1)
        self.file_sub_layout.addLayout(export_grid)
        self.export_hint = QLabel(tr("export_hint"))
        self.file_sub_layout.addWidget(self.export_hint)

    def setup_aid_sub(self):
        self.aid_sub_layout.addWidget(QLabel(tr("aids")))
        grid = QGridLayout(); grid.setSpacing(3)
        aids = [
            (tr("aid_ruler"), "ruler"),
            (tr("aid_set_square_45"), "set_square_45"),
            (tr("aid_set_square_30"), "set_square_30"),
            (tr("aid_protractor"), "protractor"),
        ]
        for i, (label, kind) in enumerate(aids):
            btn = QPushButton(label)
            btn.clicked.connect(lambda _=False, k=kind: self.spawn_aid(k))
            grid.addWidget(btn, i // 2, i % 2)
        self.aid_sub_layout.addLayout(grid)
        self.aid_calibration_label = QLabel(tr("ruler_scale_dpi"))
        self.aid_sub_layout.addWidget(self.aid_calibration_label)
        calibrate_btn = QPushButton(tr("calibrate_screen"))
        calibrate_btn.clicked.connect(self.calibrate_ruler)
        self.aid_sub_layout.addWidget(calibrate_btn)
        reset_calibration_btn = QPushButton(tr("reset_to_dpi"))
        reset_calibration_btn.clicked.connect(self.reset_ruler_calibration)
        self.aid_sub_layout.addWidget(reset_calibration_btn)
        clear_btn = QPushButton(tr("aid_clear_all"))
        clear_btn.clicked.connect(self.clear_aids)
        self.aid_sub_layout.addWidget(clear_btn)
        self.aid_sub_layout.addWidget(QLabel(tr("aid_hint")))

    def on_smart_toggle(self):
        enabled = self.btn_smart_toggle.isChecked()
        self.canvas.smart_shapes_enabled = enabled
        self.canvas.dash_chain = None
        self.btn_smart_toggle.setText(tr("smart_shapes_on") if enabled else tr("smart_shapes_off"))
        track_event("smart_shapes_toggled", enabled=enabled)

    # --- 计时器 ---
    def setup_timer_sub(self):
        mode_row = QHBoxLayout(); mode_row.setSpacing(2)
        self.btn_timer_up = QPushButton(tr("timer_up"))
        self.btn_timer_up.clicked.connect(lambda: self.set_timer_mode("UP"))
        self.btn_timer_down = QPushButton(tr("timer_down"))
        self.btn_timer_down.clicked.connect(lambda: self.set_timer_mode("DOWN"))
        mode_row.addWidget(self.btn_timer_up); mode_row.addWidget(self.btn_timer_down)
        self.timer_sub_layout.addLayout(mode_row)

        # xx:yy 数字块，每个数字都有上下箭头微调（长按连发）
        grid = QGridLayout(); grid.setSpacing(2)
        def arrow(text, secs):
            btn = QPushButton(text); btn.setObjectName("ArrowBtn")
            btn.setAutoRepeat(True); btn.setAutoRepeatDelay(320); btn.setAutoRepeatInterval(70)
            btn.clicked.connect(lambda: self.adjust_timer(secs))
            return btn

        # 第一行：4个上箭头（十位分钟、个位分钟、十位秒钟、个位秒钟）
        grid.addWidget(arrow("▲", 600), 0, 0, Qt.AlignmentFlag.AlignCenter)   # 十位分钟 +10分钟
        grid.addWidget(arrow("▲", 60), 0, 1, Qt.AlignmentFlag.AlignCenter)    # 个位分钟 +1分钟
        grid.addWidget(arrow("▲", 10), 0, 3, Qt.AlignmentFlag.AlignCenter)    # 十位秒钟 +10秒
        grid.addWidget(arrow("▲", 1), 0, 4, Qt.AlignmentFlag.AlignCenter)     # 个位秒钟 +1秒

        # 第二行：时间显示
        self.timer_display = QLabel("05:00")
        self.timer_display.setObjectName("TimerDisplay")
        self.timer_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        grid.addWidget(self.timer_display, 1, 0, 1, 5)

        # 第三行：4个下箭头
        grid.addWidget(arrow("▼", -600), 2, 0, Qt.AlignmentFlag.AlignCenter)  # 十位分钟 -10分钟
        grid.addWidget(arrow("▼", -60), 2, 1, Qt.AlignmentFlag.AlignCenter)   # 个位分钟 -1分钟
        grid.addWidget(arrow("▼", -10), 2, 3, Qt.AlignmentFlag.AlignCenter)   # 十位秒钟 -10秒
        grid.addWidget(arrow("▼", -1), 2, 4, Qt.AlignmentFlag.AlignCenter)    # 个位秒钟 -1秒

        self.timer_sub_layout.addLayout(grid)

        preset_row = QHBoxLayout(); preset_row.setSpacing(2)
        for label, secs in ((trf("timer_preset_min", value=1), 60), (trf("timer_preset_min", value=3), 180),
                            (trf("timer_preset_min", value=5), 300), (trf("timer_preset_min", value=10), 600)):
            btn = QPushButton(label); btn.setObjectName("HistoryBtn")
            btn.clicked.connect(lambda _, s=secs: self.set_timer_preset(s))
            preset_row.addWidget(btn)
        self.timer_sub_layout.addLayout(preset_row)

        control_row = QHBoxLayout(); control_row.setSpacing(2)
        self.btn_timer_start = QPushButton(tr("timer_start"))
        self.btn_timer_start.clicked.connect(self.toggle_timer_running)
        control_row.addWidget(self.btn_timer_start, 1)
        self.btn_timer_reset = QPushButton("↺"); self.btn_timer_reset.setObjectName("SquareBtn")
        self.btn_timer_reset.setToolTip(tr("timer_reset"))
        self.btn_timer_reset.clicked.connect(self.reset_timer)
        control_row.addWidget(self.btn_timer_reset)
        self.timer_sub_layout.addLayout(control_row)
        self.update_timer_ui()

    @staticmethod
    def format_timer(secs):
        total = max(0, int(round(secs)))
        return f"{min(99, total // 60):02d}:{total % 60:02d}"

    def set_timer_mode(self, mode):
        self.timer_mode = mode
        self.timer_alerting = False
        self.timer_flash.stop()
        if not self.timer_running:
            self.timer_left = float(self.timer_target) if mode == "DOWN" else 0.0
        track_event("timer_mode", mode=mode)
        self.update_timer_ui()

    def adjust_timer(self, secs):
        if self.timer_mode == "UP" and not self.timer_running:
            self.timer_mode = "DOWN"                     # 手调时长即视为要倒计时
        self.timer_left = max(0.0, min(99 * 60 + 59, self.timer_left + secs))
        if self.timer_mode == "DOWN" and not self.timer_running:
            self.timer_target = int(self.timer_left)
        self.timer_alerting = False
        self.timer_flash.stop()
        self.update_timer_ui()

    def set_timer_preset(self, secs):
        self.timer_mode = "DOWN"
        self.timer_target = secs
        self.timer_left = float(secs)
        self.timer_alerting = False
        self.timer_flash.stop()
        track_event("timer_preset", seconds=secs)
        self.update_timer_ui()

    def toggle_timer_running(self):
        if self.timer_running:
            self.timer_running = False
            self.timer_clock.stop()
        else:
            if self.timer_mode == "DOWN" and self.timer_left <= 0:
                self.timer_left = float(self.timer_target)   # 归零后再按开始 = 重新来
                if self.timer_left <= 0:
                    return
            self.timer_alerting = False
            self.timer_flash.stop()
            self.timer_running = True
            self._timer_last = time.monotonic()
            self.timer_clock.start()
        track_event("timer_toggled", running=self.timer_running, mode=self.timer_mode)
        self.update_timer_ui()

    def reset_timer(self):
        self.timer_running = False
        self.timer_alerting = False
        self.timer_clock.stop()
        self.timer_flash.stop()
        self.timer_left = float(self.timer_target) if self.timer_mode == "DOWN" else 0.0
        track_event("timer_reset")
        self.update_timer_ui()

    def _timer_tick(self):
        now = time.monotonic()
        delta = max(0.0, now - self._timer_last)
        self._timer_last = now
        if self.timer_mode == "DOWN":
            self.timer_left -= delta
            if self.timer_left <= 0:
                self.timer_left = 0.0
                self._timer_finished()
                return
        else:
            self.timer_left = min(99 * 60 + 59, self.timer_left + delta)
        self.update_timer_ui()

    def _timer_finished(self):
        """倒计时到点：解除静音并拉满音量 + 响铃 + 红色闪烁提醒。"""
        self.timer_running = False
        self.timer_alerting = True
        self.timer_clock.stop()
        self.timer_flash.start()
        force_system_max_volume()
        play_alarm_async()
        track_event("timer_finished", target=self.timer_target)
        self.update_timer_ui()

    def _timer_flash(self):
        self._flash_on = not self._flash_on
        self._apply_timer_alert_style()

    def _apply_timer_alert_style(self):
        alert = self.timer_alerting and self._flash_on
        style = f"color: {self.theme['danger']};" if alert else ""
        self.timer_display.setStyleSheet(style)
        self.mini_timer_label.setStyleSheet(style)

    def update_timer_ui(self):
        # 构建顺序：timer_sub 先于 mini_timer 创建，二者齐备后才允许刷新
        if not hasattr(self, "timer_display") or not hasattr(self, "mini_timer_label"):
            return
        text = self.format_timer(self.timer_left)
        self.timer_display.setText(text)
        self.mini_timer_label.setText(text)
        self.btn_timer_start.setText(tr("timer_pause") if self.timer_running else tr("timer_start"))
        self.btn_timer_up.setObjectName("ActiveTool" if self.timer_mode == "UP" else "")
        self.btn_timer_down.setObjectName("ActiveTool" if self.timer_mode == "DOWN" else "")
        self.btn_timer_up.setStyle(self.btn_timer_up.style())
        self.btn_timer_down.setStyle(self.btn_timer_down.style())
        if not self.timer_alerting:
            self._flash_on = False
            self._apply_timer_alert_style()
        # 迷你计时器：计时中或响铃提醒中、且计时子菜单没开着时，顶端居中显示
        want_mini = ((self.timer_running or self.timer_alerting) and hasattr(self, "mini_timer")
                     and not self.timer_sub.isVisible() and not getattr(self, "_grabbing", False))
        if want_mini and not self.mini_timer.isVisible():
            self.mini_timer.adjustSize()
            screen = self.screen_geometry(self) or QApplication.primaryScreen().availableGeometry()
            self.mini_timer.move(screen.center().x() - self.mini_timer.width() // 2, screen.top() + 8)
            self.mini_timer.show()
            self.raise_floating(self.mini_timer)
        elif not want_mini and hasattr(self, "mini_timer") and self.mini_timer.isVisible():
            self.mini_timer.hide()

    def handle_timer_click(self):
        self.show_only_sub(None if self.timer_sub.isVisible() else self.timer_sub)
        self.refresh_ui()
        track_event("timer_panel_toggled", visible=self.timer_sub.isVisible())

    def handle_file_click(self):
        self.show_only_sub(None if self.file_sub.isVisible() else self.file_sub)
        self.refresh_ui()

    def do_export(self, fmt):
        self.show_only_sub(None)
        self.refresh_ui()
        self.export_pages(fmt)

    def setup_marker_sub(self):
        grid = QGridLayout(); grid.setSpacing(4)
        colors = ["#fff200", "#ffa502", "#ff6b81", "#7bed9f", "#70a1ff", "#e84393"]
        self.marker_color_buttons = []
        for i, hex_c in enumerate(colors):
            btn = QPushButton(); btn.setFixedSize(TOUCH_SWATCH, TOUCH_SWATCH); btn.setProperty("color_val", hex_c)
            btn.setStyleSheet(f"background-color: {hex_c}; border: 1px solid #777;")
            btn.clicked.connect(self.on_marker_color_clicked)
            grid.addWidget(btn, i // 3, i % 3)
            self.marker_color_buttons.append(btn)
        marker_rainbow = QPushButton("🌈"); marker_rainbow.setFixedSize(TOUCH_SWATCH, TOUCH_SWATCH)
        marker_rainbow.setStyleSheet("background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 yellow, stop:1 magenta); border: 1px solid #777;")
        marker_rainbow.clicked.connect(self.open_marker_color)
        grid.addWidget(marker_rainbow, 2, 0)
        self.marker_color_buttons.append(marker_rainbow)
        self.marker_sub_layout.addLayout(grid)

        self.marker_alpha_label = QLabel(trf("opacity_value", value=35))
        self.marker_sub_layout.addWidget(self.marker_alpha_label)
        ma_row = QHBoxLayout(); ma_row.setSpacing(2)
        btn_ad = QPushButton("▼"); btn_ad.setObjectName("ArrowBtn"); btn_ad.clicked.connect(lambda: self.marker_alpha_slider.setValue(self.marker_alpha_slider.value() - 1))
        self.marker_alpha_slider = QSlider(Qt.Orientation.Horizontal); self.marker_alpha_slider.setRange(10, 90); self.marker_alpha_slider.setValue(35); self.marker_alpha_slider.setFixedWidth(80)
        self.marker_alpha_slider.valueChanged.connect(self.on_marker_alpha_changed)
        btn_au = QPushButton("▲"); btn_au.setObjectName("ArrowBtn"); btn_au.clicked.connect(lambda: self.marker_alpha_slider.setValue(self.marker_alpha_slider.value() + 1))
        ma_row.addWidget(btn_ad); ma_row.addWidget(self.marker_alpha_slider); ma_row.addWidget(btn_au)
        self.marker_sub_layout.addLayout(ma_row)

        self.marker_width_label = QLabel(trf("width_value", value=24))
        self.marker_sub_layout.addWidget(self.marker_width_label)
        mw_row = QHBoxLayout(); mw_row.setSpacing(2)
        btn_wd = QPushButton("▼"); btn_wd.setObjectName("ArrowBtn"); btn_wd.clicked.connect(lambda: self.marker_width_slider.setValue(self.marker_width_slider.value() - 1))
        self.marker_width_slider = QSlider(Qt.Orientation.Horizontal); self.marker_width_slider.setRange(6, 80); self.marker_width_slider.setValue(24); self.marker_width_slider.setFixedWidth(80)
        self.marker_width_slider.valueChanged.connect(self.on_marker_width_changed)
        btn_wu = QPushButton("▲"); btn_wu.setObjectName("ArrowBtn"); btn_wu.clicked.connect(lambda: self.marker_width_slider.setValue(self.marker_width_slider.value() + 1))
        mw_row.addWidget(btn_wd); mw_row.addWidget(self.marker_width_slider); mw_row.addWidget(btn_wu)
        self.marker_sub_layout.addLayout(mw_row)

    def setup_magnifier_sub(self):
        self.mag_zoom_label = QLabel(trf("zoom_value", value=200))
        self.magnifier_sub_layout.addWidget(self.mag_zoom_label)
        z_row = QHBoxLayout(); z_row.setSpacing(2)
        btn_out = QPushButton("－"); btn_out.setObjectName("ArrowBtn"); btn_out.clicked.connect(lambda: self.canvas.step_magnifier_zoom(-1))
        btn_in = QPushButton("＋"); btn_in.setObjectName("ArrowBtn"); btn_in.clicked.connect(lambda: self.canvas.step_magnifier_zoom(1))
        z_row.addWidget(btn_out); z_row.addWidget(QLabel(tr("zoom_step"))); z_row.addWidget(btn_in)
        self.magnifier_sub_layout.addLayout(z_row)

        self.mag_size_label = QLabel(trf("lens_value", value=260))
        self.magnifier_sub_layout.addWidget(self.mag_size_label)
        self.mag_size_slider = QSlider(Qt.Orientation.Horizontal)
        self.mag_size_slider.setRange(120, 600); self.mag_size_slider.setValue(260); self.mag_size_slider.setFixedWidth(110)
        self.mag_size_slider.valueChanged.connect(self.on_magnifier_size_changed)
        self.magnifier_sub_layout.addWidget(self.mag_size_slider)

        refresh_btn = QPushButton(tr("refresh_frame"))
        refresh_btn.clicked.connect(self.refresh_magnifier)
        self.magnifier_sub_layout.addWidget(refresh_btn)
        self.magnifier_sub_layout.addWidget(QLabel(tr("wheel_zoom_hint")))

    def on_marker_color_clicked(self):
        btn = self.sender()
        self.canvas.marker_color = QColor(btn.property("color_val"))
        self.highlight_marker_color(btn)
        self.canvas.update()
        track_event("marker_color_changed", color=self.canvas.marker_color.name())

    def open_marker_color(self):
        self.timer.stop()
        try:
            d = QColorDialog(self.canvas.marker_color, self)
            d.setWindowTitle(tr("choose_marker_color"))
            d.setOption(QColorDialog.ColorDialogOption.DontUseNativeDialog, True)
            d.setOption(QColorDialog.ColorDialogOption.ShowAlphaChannel, False)
            if d.exec():
                self.canvas.marker_color = d.selectedColor()
                self.highlight_marker_color(self.marker_color_buttons[-1])
                self.canvas.update()
                track_event("marker_custom_color", color=self.canvas.marker_color.name())
        finally:
            self.timer.start(self.HEARTBEAT_MS)

    def highlight_marker_color(self, active_btn):
        for btn in self.marker_color_buttons:
            base = btn.styleSheet().split("border:")[0]
            btn.setStyleSheet(base + (f"border: 2px solid {self.theme['accent']};" if btn == active_btn else "border: 1px solid #777;"))

    def on_marker_alpha_changed(self, v):
        self.canvas.marker_alpha = max(10, min(255, round(v * 255 / 100)))
        self.marker_alpha_label.setText(trf("opacity_value", value=v))
        self.canvas.update()
        track_event("marker_alpha_changed", percent=v)

    def on_marker_width_changed(self, v):
        self.canvas.marker_width = v
        self.marker_width_label.setText(trf("width_value", value=v))
        self.canvas.update()
        track_event("marker_width_changed", width=v)

    def update_magnifier_ui(self):
        if not hasattr(self, "mag_zoom_label") or not self.canvas:
            return
        self.mag_zoom_label.setText(trf("zoom_value", value=int(self.canvas.magnifier_zoom * 100)))
        self.mag_size_label.setText(trf("lens_value", value=self.canvas.magnifier_size))

    def on_magnifier_size_changed(self, v):
        self.canvas.magnifier_size = v
        self.update_magnifier_ui()
        self.canvas.update()

    def refresh_magnifier(self):
        self.canvas.magnifier_pixmap = self.grab_screen()
        self.canvas.update()
        track_event("magnifier_refreshed", zoom=self.canvas.magnifier_zoom)

    def setup_eraser_sub(self):
        self.btn_circ = QPushButton(tr("eraser_circle")); self.btn_circ.setObjectName("ActiveTool")
        self.btn_stroke = QPushButton(tr("eraser_stroke"))
        self.btn_circ.clicked.connect(lambda: self.set_eraser_type("CIRCLE")); self.btn_stroke.clicked.connect(lambda: self.set_eraser_type("STROKE"))
        self.eraser_sub_layout.addWidget(self.btn_circ); self.eraser_sub_layout.addWidget(self.btn_stroke)

        self.e_label = QLabel(trf("sensitivity_value", value=40)); self.eraser_sub_layout.addWidget(self.e_label)
        es_row = QHBoxLayout(); es_row.setSpacing(2)
        btn_ed = QPushButton("▼"); btn_ed.setObjectName("ArrowBtn"); btn_ed.clicked.connect(lambda: self.e_slider.setValue(self.e_slider.value()-1))
        self.e_slider = QSlider(Qt.Orientation.Horizontal); self.e_slider.setRange(10, 150); self.e_slider.setValue(40); self.e_slider.setFixedWidth(80)
        self.e_slider.valueChanged.connect(self.on_eraser_slider_changed)
        btn_eu = QPushButton("▲"); btn_eu.setObjectName("ArrowBtn"); btn_eu.clicked.connect(lambda: self.e_slider.setValue(self.e_slider.value()+1))
        es_row.addWidget(btn_ed); es_row.addWidget(self.e_slider); es_row.addWidget(btn_eu); self.eraser_sub_layout.addLayout(es_row)

    # 提示文案统一走 i18n：这里存 key，取用时再 tr()，切换语言不需要重建这张表。
    SHAPE_HINTS = {
        "LINE": "hint_two_endpoints", "DASHED_LINE": "hint_two_endpoints",
        "TRIANGLE": "hint_three_vertices", "RECT": "hint_two_corners",
        "PARALLELOGRAM": "hint_three_adjacent", "TRAPEZOID": "hint_trapezoid",
        "CIRCLE": "hint_circle", "ELLIPSE": "hint_ellipse",
        "DIAMOND": "hint_diamond", "ANGLE": "hint_angle",
    }

    def shape_hint_text(self, shape_type):
        """取图形的操作提示；没有登记的（立体图形）回退到「拖拽绘制」。"""
        key = self.SHAPE_HINTS.get(shape_type)
        return tr(key) if key else tr("hint_drag_draw")

    def setup_shape_sub(self):
        grid = QGridLayout(); grid.setSpacing(3)
        shapes = [
            (tr("shape_line"), "LINE"), (tr("shape_dashed_line"), "DASHED_LINE"),
            (tr("shape_triangle"), "TRIANGLE"), (tr("shape_rect"), "RECT"),
            (tr("shape_parallelogram"), "PARALLELOGRAM"), (tr("shape_trapezoid"), "TRAPEZOID"),
            (tr("shape_diamond"), "DIAMOND"), (tr("shape_angle"), "ANGLE"),
            (tr("shape_circle"), "CIRCLE"), (tr("shape_ellipse"), "ELLIPSE"),
            (tr("shape_cuboid"), "CUBOID"), (tr("shape_cube"), "CUBE"),
            (tr("shape_cylinder"), "CYLINDER"), (tr("shape_cone"), "CONE"),
        ]
        self.shape_buttons = []
        for i, (label, shape_type) in enumerate(shapes):
            btn = QPushButton(label)
            btn.setProperty("shape_type", shape_type)
            btn.setToolTip(self.shape_hint_text(shape_type))
            btn.clicked.connect(self.on_shape_selected)
            grid.addWidget(btn, i // 2, i % 2)
            self.shape_buttons.append(btn)
        self.shape_sub_layout.addLayout(grid)
        # 触屏上没有右键（系统的「按住变右键」被我们关掉了，否则会打断停笔定形），
        # 所以「取消取点」必须有一个可以直接点的按钮。
        self.btn_cancel_points = QPushButton(tr("cancel_points"))
        self.btn_cancel_points.clicked.connect(self.cancel_shape_points)
        self.shape_sub_layout.addWidget(self.btn_cancel_points)
        self.shape_hint_label = QLabel(tr("shape_hint_default"))
        self.shape_sub_layout.addWidget(self.shape_hint_label)
        self.update_shape_buttons()

    def cancel_shape_points(self):
        if self.canvas:
            self.canvas.cancel_pending_points()

    def on_shape_selected(self):
        btn = self.sender()
        self.set_drawing_mode(True)
        self.canvas.cancel_pending_points()          # 换图形类型时丢弃已落的顶点
        self.canvas.shape_type = btn.property("shape_type")
        self.canvas.draw_state = "SHAPE"
        self.set_active_tool(self.btn_shape)
        self.update_shape_buttons()
        key = self.SHAPE_HINTS.get(self.canvas.shape_type)
        self.shape_hint_label.setText(
            trf("shape_hint_suffix", hint=tr(key)) if key else tr("hint_drag_draw"))
        track_event("shape_selected", shape_type=self.canvas.shape_type)

    def update_shape_buttons(self):
        if not hasattr(self, "shape_buttons"):
            return
        for btn in self.shape_buttons:
            active = btn.property("shape_type") == self.canvas.shape_type if self.canvas else False
            btn.setObjectName("ActiveTool" if active else "")
            btn.setStyle(btn.style())

    def setup_select_sub(self):
        # 三个方块：复制 / 删除 / 更多（仅平面图形）
        squares = QHBoxLayout(); squares.setSpacing(4)
        self.btn_dup = QPushButton(tr("duplicate")); self.btn_dup.setObjectName("SquareBtn")
        self.btn_dup.setToolTip(tr("duplicate_tip"))
        self.btn_dup.clicked.connect(lambda: self.canvas.duplicate_selection())
        squares.addWidget(self.btn_dup)
        self.btn_del = QPushButton(tr("delete")); self.btn_del.setObjectName("SquareBtn")
        self.btn_del.setToolTip(tr("delete_tip"))
        self.btn_del.clicked.connect(lambda: self.canvas.delete_selection())
        squares.addWidget(self.btn_del)
        self.btn_more = QPushButton("⋯"); self.btn_more.setObjectName("SquareBtn")
        self.btn_more.setToolTip(tr("more_tip"))
        self.btn_more.clicked.connect(self.open_more_menu)
        squares.addWidget(self.btn_more)
        squares.addStretch(1)
        self.select_sub_layout.addLayout(squares)

        self.select_label = QLabel(tr("selection_none"))
        self.select_sub_layout.addWidget(self.select_label)

        color_btn = QPushButton(tr("change_color"))
        color_btn.clicked.connect(self.open_selection_color)
        self.select_sub_layout.addWidget(color_btn)

        self.select_width_label = QLabel(trf("width_value", value=4))
        self.select_sub_layout.addWidget(self.select_width_label)
        self.select_width_slider = QSlider(Qt.Orientation.Horizontal)
        self.select_width_slider.setRange(1, 40)
        self.select_width_slider.setValue(4)
        self.select_width_slider.setFixedWidth(110)
        self.select_width_slider.valueChanged.connect(self.on_selection_width_changed)
        self.select_sub_layout.addWidget(self.select_width_slider)


    def all_subs(self):
        return (self.draw_sub, self.annotate_sub, self.eraser_sub, self.shape_sub, self.marker_sub,
                self.laser_sub, self.tools_sub, self.file_sub, self.aid_sub,
                self.magnifier_sub, self.timer_sub)

    def show_only_sub(self, target=None):
        """同一时间只展开一个子面板，并收起浮动的选中面板。

        关键：浮窗先隐藏，在不可见状态下换内容、调尺寸、定位，最后一次性显示。
        半透明窗口在可见状态下缩放会让合成器呈现新旧交替的画面（闪烁/叠影）。
        """
        self.select_panel.hide()
        if target is not None and target.isVisible() and self.menu_panel.isVisible():
            self._menu_anchor = self.sub_anchor_button(target)
            self.position_menu_panel()          # 已是目标状态，只校正位置，避免无谓的隐藏重显
            return
        self.menu_panel.hide()
        for sub in self.all_subs():
            sub.setVisible(sub is target)
        self._menu_anchor = self.sub_anchor_button(target) if target is not None else None
        if target is None:
            if hasattr(self, "timer_display"):
                self.update_timer_ui()   # 关闭计时面板后，计时中→迷你计时器接管
            return
        layout = self.menu_panel.layout()
        layout.invalidate()
        layout.activate()
        self.menu_panel.setFixedSize(layout.sizeHint())
        self.position_menu_panel()
        self.menu_panel.show()
        # 只 force_topmost 不够：画布也是 TOPMOST，HWND_TOPMOST 决定不了同层兄弟的高低，
        # 刚显示的子菜单可能落在全屏画布之下——点它等于点画布（橡皮态下直接擦掉内容，
        # 还会在菜单上画出橡皮光标圈），表现就是「子菜单点不动、其他功能失灵」。
        # raise_floating 会重绑 owner 并补上 force_above(菜单, 画布)。
        self.raise_floating(self.menu_panel)
        if hasattr(self, "timer_display"):
            self.update_timer_ui()      # 计时面板开/关联动迷你计时器显隐

    def position_menu_panel(self):
        x, y = self._floating_anchor(self.menu_panel.width(), self.menu_panel.height(), gap=6,
                                     anchor=getattr(self, "_menu_anchor", None))
        self.menu_panel.move(x, y)

    def set_tool(self, state, button):
        if not self.canvas.is_drawing_mode:
            self.set_drawing_mode(True)              # 穿透状态下点工具自动回到绘图模式
        if self.canvas.draw_state == state:
            # 已是该工具则只刷新高亮，不重置状态、不取消正在进行的延迟智能识别
            # （否则 PEN→PEN 再次点击打开设置时会误取消刚画那一笔的延迟识别）
            self.set_active_tool(button)
            return
        self.canvas._cancel_smart_recognition(drop_pending=True)  # 切工具：取消上一笔的延迟识别
        prev = self.canvas.draw_state
        # 离开任意工具时的统一善后：不再有「橡皮特殊分支提前 return」跳过这些清理，
        # 这样从橡皮切到任意绘图工具时，旧工具残留状态（放大镜冻结帧 / 聚光灯叠加 /
        # 图形未完成顶点 / 批注笔虚线连击 / 激光笔轨迹 / 橡皮光标圈与带笔状态）都会被清掉，
        # 杜绝「橡皮退出后仍可使用、绘图不正常」的状态串味。
        if prev == "ERASER" and state != "ERASER":
            self.canvas.last_erase_point = None
            self.canvas.mouse_pos = QPoint(-100, -100)   # 把橡皮光标挪到屏外
            self.canvas.current_stroke_id = None         # 顺带清掉残留的笔迹瞬态，避免拖回时误接
            self.canvas.current_stroke_points = []
            self.canvas.current_stroke_widths = []
            self.canvas.last_point = None
        if prev == "MAGNIFIER" and state != "MAGNIFIER":
            self.canvas.magnifier_pixmap = None      # 离开放大镜时释放冻结帧
        if prev == "SPOTLIGHT" and state != "SPOTLIGHT":
            self.canvas._spotlight_overlay = None    # 离开聚光灯时释放全屏叠加 pixmap
        if prev == "SHAPE" and state != "SHAPE":
            self.canvas.cancel_pending_points()      # 离开图形工具时丢弃未完成的顶点
        if prev == "PEN" and state != "PEN":
            self.canvas.dash_chain = None            # 离开批注笔时打断虚线连击
        if prev == "LASER" and state != "LASER":
            self.canvas.laser_trail = []
            self._laser_fade.stop()
        # 立刻改 draw_state，再 update：确保排队的重绘已经按新工具绘制，不再出现上一工具的光标圈。
        self.canvas.draw_state = state
        self.canvas.update()
        self.set_active_tool(button)
        if state == "LASER":
            self._laser_fade.start()
        else:
            self._laser_fade.stop()
        # 调用方各自 track_event("tool_changed")，此处不再重复记录

    def _tick_laser_fade(self):
        if self.canvas and self.canvas.draw_state == "LASER":
            if self.canvas.prune_laser_trail() or self.canvas.laser_trail:
                self.canvas.update()
        else:
            self._laser_fade.stop()

    def update_annotate_buttons(self):
        """高亮当前批注子工具（普通笔/荧光笔/激光笔）。"""
        if not hasattr(self, "btn_ann_pen") or not self.canvas:
            return
        state = self.canvas.draw_state
        mapping = {
            "PEN": self.btn_ann_pen,
            "MARKER": self.btn_ann_marker,
            "LASER": self.btn_ann_laser,
        }
        for btn in (self.btn_ann_pen, self.btn_ann_marker, self.btn_ann_laser):
            btn.setObjectName("ActiveTool" if mapping.get(state) is btn else "")
            btn.setStyle(btn.style())

    def handle_annotate_click(self):
        """主栏「批注」：始终先出 普通笔/荧光笔/激光笔 三选一。

        - 已打开三选一 → 关闭
        - 正在看某工具设置面板 → 回到三选一（方便切换荧光笔/激光笔）
        - 其它情况 → 打开三选一
        """
        self.set_drawing_mode(True)
        # 这里必须真正把工具切回批注笔，而不是只把高亮挪到「批注」。
        # 只挪高亮会让画布停在上一个工具（典型是橡皮）：高亮说在批注、鼠标却还拖着橡皮
        # 光标圈、点画布是擦除；而且 draw_state 仍是 ERASER，用户再点「橡皮」时
        # handle_eraser_click 只会开关设置面板、不再重置高亮，界面就永久停在错位状态。
        if self.canvas.draw_state not in ("PEN", "MARKER", "LASER"):
            self.set_tool(self.last_annotate_tool, self.btn_pen)
            self.canvas.selected_ids.clear()
        self.set_active_tool(self.btn_pen)
        # 若正开着笔/荧/激光设置，回到三选一，别把另外两个藏死
        if self.draw_sub.isVisible() or self.marker_sub.isVisible() or self.laser_sub.isVisible():
            self.update_annotate_buttons()
            self.show_only_sub(self.annotate_sub)
        elif self.annotate_sub.isVisible():
            self.show_only_sub(None)
        else:
            self.update_annotate_buttons()
            self.show_only_sub(self.annotate_sub)
        self.refresh_ui()
        track_event("annotate_menu")

    def choose_pen_tool(self):
        was_pen = self.canvas.draw_state == "PEN"
        self.last_annotate_tool = "PEN"
        self.set_tool("PEN", self.btn_pen)
        self.canvas.selected_ids.clear()
        self.update_annotate_buttons()
        # 首次切换：直接可用；已是普通笔再点：打开颜色/粗细设置
        if was_pen:
            self.show_only_sub(None if self.draw_sub.isVisible() else self.draw_sub)
        else:
            self.show_only_sub(None)
        self.refresh_ui()
        track_event("tool_changed", tool="PEN")

    def choose_marker_tool(self):
        was_marker = self.canvas.draw_state == "MARKER"
        self.last_annotate_tool = "MARKER"
        self.set_tool("MARKER", self.btn_pen)
        self.canvas.selected_ids.clear()
        self.update_annotate_buttons()
        # 首次切换：直接可用并关菜单；已是荧光笔再点：打开颜色设置
        if was_marker:
            self.show_only_sub(None if self.marker_sub.isVisible() else self.marker_sub)
        else:
            self.show_only_sub(None)
        self.refresh_ui()
        track_event("tool_changed", tool="MARKER")

    def choose_laser_tool(self):
        was_laser = self.canvas.draw_state == "LASER"
        self.last_annotate_tool = "LASER"
        self.set_tool("LASER", self.btn_pen)
        self.canvas.selected_ids.clear()
        self.canvas.laser_trail = []
        self.update_annotate_buttons()
        if was_laser:
            self.show_only_sub(None if self.laser_sub.isVisible() else self.laser_sub)
        else:
            self.show_only_sub(None)
        self.refresh_ui()
        track_event("tool_changed", tool="LASER")

    def handle_pen_click(self):
        self.choose_pen_tool()

    def handle_marker_click(self):
        self.choose_marker_tool()

    def handle_tools_click(self):
        self.show_only_sub(None if self.tools_sub.isVisible() else self.tools_sub)
        self.refresh_ui()
        track_event("tools_menu")

    def open_aid_menu(self):
        self.show_only_sub(self.aid_sub)
        self.refresh_ui()

    def spawn_aid(self, kind):
        self.set_drawing_mode(True)
        if self.canvas.draw_state == "MAGNIFIER":
            self.canvas.magnifier_pixmap = None
        self.canvas.add_aid(kind)
        # 不改 draw_state（教具在任意绘图态下都能拖），因此也不能把高亮挪到「工具」——
        # 那会谎报当前工具。高亮由 refresh_ui → sync_tool_highlight 按真实状态给出。
        self.show_only_sub(self.aid_sub)
        self.refresh_ui()

    def clear_aids(self):
        if self.canvas:
            self.canvas.clear_aids()
        track_event("aids_cleared")

    def update_ruler_calibration_label(self):
        if not hasattr(self, "aid_calibration_label") or not self.canvas:
            return
        _key, px_per_mm, calibrated = self.canvas.current_screen_calibration()
        source = tr("calibrated_source") if calibrated else tr("dpi_source")
        self.aid_calibration_label.setText(trf("ruler_scale_value", source=source, ratio=f"{px_per_mm:.3f}"))

    def calibrate_ruler(self):
        if not self.canvas:
            return
        current_key, estimated, _ = self.canvas.current_screen_calibration()
        screen = self.canvas.screen() or QApplication.primaryScreen()
        track_event("ruler_calibration_started", screen=current_key)
        self.timer.stop()
        try:
            dialog = RulerCalibrationDialog(screen, estimated, self)
            accepted = dialog.exec() == QDialog.DialogCode.Accepted
        finally:
            self.timer.start(self.HEARTBEAT_MS)
        if not accepted:
            track_event("ruler_calibration_cancelled")
            return
        known_mm = dialog.length_input.value()
        px_per_mm = dialog.measured_pixels() / known_mm
        if not valid_pixels_per_mm(px_per_mm):
            notify_user(self, tr("calibration_invalid"), tr("calibration_invalid_msg"), level="warning")
            track_event("ruler_calibration_invalid", px_per_mm=px_per_mm)
            return
        geometry = screen.geometry() if screen else self.canvas.geometry()
        record = {
            "screen_key": current_key,
            "px_per_mm": px_per_mm,
            "known_length_mm": known_mm,
            "dpr": screen.devicePixelRatio() if screen else 1.0,
            "logical_dpi": sane_dpi(screen.logicalDotsPerInch()) if screen else 96.0,
            "geometry": [geometry.left(), geometry.top(), geometry.width(), geometry.height()],
        }
        self.canvas.ruler_calibrations[current_key] = record
        self.canvas.ruler_calibration = record
        self.update_ruler_calibration_label()
        self.canvas.update()
        self.save_settings()
        track_event("ruler_calibrated", px_per_mm=round(px_per_mm, 5), length_mm=known_mm)

    def reset_ruler_calibration(self):
        if not self.canvas:
            return
        current_key, _, _ = self.canvas.current_screen_calibration()
        self.canvas.ruler_calibrations.pop(current_key, None)
        self.canvas.ruler_calibration = None
        self.update_ruler_calibration_label()
        self.canvas.update()
        self.save_settings()
        track_event("ruler_calibration_reset")

    def on_laser_color_clicked(self):
        btn = self.sender()
        self.canvas.laser_color = QColor(btn.property("color_val"))
        self.highlight_laser_color(btn)
        self.canvas.update()
        track_event("laser_color_changed", color=self.canvas.laser_color.name())

    def open_laser_color(self):
        self.timer.stop()
        try:
            d = QColorDialog(self.canvas.laser_color, self)
            d.setWindowTitle(tr("choose_laser_color"))
            d.setOption(QColorDialog.ColorDialogOption.DontUseNativeDialog, True)
            d.setOption(QColorDialog.ColorDialogOption.ShowAlphaChannel, False)
            if d.exec():
                self.canvas.laser_color = d.selectedColor()
                self.highlight_laser_color(self.laser_color_buttons[-1])
                self.canvas.update()
                track_event("laser_custom_color", color=self.canvas.laser_color.name())
        finally:
            self.timer.start(self.HEARTBEAT_MS)

    def highlight_laser_color(self, active_btn):
        for btn in self.laser_color_buttons:
            base = btn.styleSheet().split("border:")[0]
            btn.setStyleSheet(base + (f"border: 2px solid {self.theme['accent']};" if btn == active_btn else "border: 1px solid #777;"))

    def on_laser_width_changed(self, v):
        self.canvas.laser_width = v
        self.laser_width_label.setText(trf("laser_dot", value=v))
        self.canvas.update()

    def handle_eraser_click(self):
        self.set_drawing_mode(True)
        if self.canvas.draw_state != "ERASER":
            self.set_tool("ERASER", self.btn_eraser)
            self.canvas.selected_ids.clear()
            self.show_only_sub(None)
        else:
            self.show_only_sub(None if self.eraser_sub.isVisible() else self.eraser_sub)
        self.refresh_ui()

    def handle_magnifier_click(self):
        self.set_drawing_mode(True)
        if self.canvas.draw_state != "MAGNIFIER":
            self.set_tool("MAGNIFIER", self.btn_tools)
            self.canvas.selected_ids.clear()
            self.show_only_sub(self.magnifier_sub)
            self.update_magnifier_ui()
            self.refresh_magnifier()
        else:
            self.show_only_sub(None if self.magnifier_sub.isVisible() else self.magnifier_sub)
        self.refresh_ui()
        track_event("tool_changed", tool="MAGNIFIER")

    def handle_spotlight_click(self):
        """演示聚光灯：暗化全屏，只留跟随鼠标的圆形亮区。再次点击即退出。

        退出原来只有「画布上右键」和「改点别的工具」两条路。触屏没有右键（系统的
        按住变右键已被关掉），而聚光灯下整屏是暗的，最直觉的动作就是再点一次它，
        所以这里做成开关。
        """
        self.set_drawing_mode(True)
        self.show_only_sub(None)
        if self.canvas.draw_state != "SPOTLIGHT":
            self.set_tool("SPOTLIGHT", self.btn_tools)
            self.canvas.selected_ids.clear()
            track_event("tool_changed", tool="SPOTLIGHT")
        else:
            self.choose_pen_tool()               # 再点一次：退出聚光灯回到批注笔
            track_event("spotlight_exited", via="tools_button")
        self.refresh_ui()

    def handle_select_click(self):
        self.set_drawing_mode(True)
        if self.canvas.draw_state != "SELECT":
            self.set_tool("SELECT", self.btn_select)
            self.show_only_sub(None)
        self.position_selection_panel(self.canvas.selection_bounds())
        self.refresh_ui()
        track_event("tool_changed", tool="SELECT")

    def handle_text_click(self):
        self.set_drawing_mode(True)
        self.set_tool("TEXT", self.btn_text)
        self.show_only_sub(None)
        self.position_selection_panel(self.canvas.selection_bounds())
        self.refresh_ui()
        track_event("tool_changed", tool="TEXT")

    def handle_shape_click(self):
        self.set_drawing_mode(True)
        self.set_tool("SHAPE", self.btn_shape)
        self.show_only_sub(None if self.shape_sub.isVisible() else self.shape_sub)
        self.update_shape_buttons()
        self.refresh_ui()
        track_event("tool_changed", tool="SHAPE")

    def tool_buttons(self):
        return (self.btn_pen, self.btn_eraser, self.btn_select, self.btn_text, self.btn_shape, self.btn_tools)

    def set_active_tool(self, active_button):
        for btn in self.tool_buttons():
            btn.setObjectName("ActiveTool" if btn == active_button else "")
            btn.setStyle(btn.style())

    def _resize_to_content(self):
        """子面板显隐后立即按内容收紧窗口并整窗重绘。

        半透明无边框窗口缩放时，旧内容不会自动清除；必须先让布局同步生效
        （activate），再用布局的真实 sizeHint 定死窗口尺寸，最后强制重绘，
        否则会出现残影、按钮视觉位置与真实位置错开导致点不中。
        """
        layout = self.layout()
        if layout:
            # 嵌套布局的 sizeHint 有缓存，白板区显隐后必须逐层失效再重算，
            # 否则窗口只会变大不会缩回
            for nested in (getattr(self, "wb_grid", None), getattr(self, "toolbar_layout", None), layout):
                if nested:
                    nested.invalidate()
                    nested.activate()
            self.setFixedSize(layout.sizeHint())
        else:
            self.adjustSize()
        # 尺寸一变就可能越界（进白板变高、横竖切换长宽互换），立刻收回屏幕内
        self.clamp_into_screen()
        self.update()

    def clamp_into_screen(self):
        """把主面板整体收进当前屏幕可用区，并让已展开的子菜单跟着换位。

        横竖切换时长宽互换：竖版贴在屏幕最右侧的窄条转成横版后会有大半截伸到屏幕外，
        反向（横转竖）贴底时同理会掉到屏幕下方——两者都要在尺寸生效后立即钳回来。
        """
        screen_obj = self.active_screen(self)
        screen = screen_obj.availableGeometry() if screen_obj is not None else QApplication.primaryScreen().availableGeometry()
        x, y = clamp_rect(self.x(), self.y(), self.width(), self.height(),
                          (screen.left(), screen.top(), screen.width(), screen.height()))
        if (x, y) != (self.x(), self.y()):
            self.move(x, y)
        if getattr(self, "menu_panel", None) is not None and self.menu_panel.isVisible():
            self.position_menu_panel()

    # 主栏高亮 ← draw_state 的唯一映射表。放大镜/聚光灯没有独立主栏按钮，归到「工具」。
    TOOL_HIGHLIGHT = {
        "PEN": "btn_pen", "MARKER": "btn_pen", "LASER": "btn_pen",
        "ERASER": "btn_eraser", "SELECT": "btn_select", "TEXT": "btn_text",
        "SHAPE": "btn_shape", "MAGNIFIER": "btn_tools", "SPOTLIGHT": "btn_tools",
    }

    def sync_tool_highlight(self):
        """让主栏高亮永远是 canvas.draw_state 的函数。

        以前每个入口各自 set_active_tool()，只要有一处挪了高亮却没换工具（主栏「批注」
        和放教具就是这样），界面就会停在「高亮在 A、实际工具是 B」的错位状态，而且
        再点那个真正生效的工具按钮也只会开关设置面板，错位无法自愈。
        拖动教具期间 draw_state 临时为 "AID"，映射不到按钮时保持原样即可。
        """
        if not self.canvas:
            return
        name = self.TOOL_HIGHLIGHT.get(self.canvas.draw_state)
        button = getattr(self, name, None) if name else None
        if button is not None:
            self.set_active_tool(button)
        self.update_annotate_buttons()

    def refresh_ui(self):
        # 只刷新按钮样式。主面板窗口尺寸恒定（子菜单在独立浮窗里），
        # 频繁点击不再触发半透明窗口缩放，也就没有点击闪烁
        self.sync_tool_highlight()
        for btn in self.tool_buttons():
            btn.setStyle(btn.style())

    def sync_selection_controls(self):
        if hasattr(self, "select_label"):
            self.select_label.setText(trf("selection_count", count=len(self.canvas.selected_ids)))
        if hasattr(self, "btn_more") and self.canvas:
            has_selection = bool(self.canvas.selected_ids)
            self.btn_dup.setEnabled(has_selection)
            self.btn_del.setEnabled(has_selection)
            self.btn_more.setEnabled(self.canvas.single_flat_shape() is not None)

    def open_more_menu(self):
        """「⋯」：对唯一选中的平面图形做几何构造 / 角度调整。"""
        item = self.canvas.single_flat_shape()
        if item is None:
            return

        # 临时隐藏 select_panel，避免遮挡菜单
        select_was_visible = self.select_panel.isVisible()
        if select_was_visible:
            self.select_panel.hide()

        # 不挂父窗口：select_panel 的 owner 被我们手工改写过（GWLP_HWNDPARENT），
        # 作为弹出菜单的 transient parent 会破坏 Qt 的内部假设导致崩溃
        menu = QMenu()
        # 设置菜单为置顶窗口，确保不被其他窗口遮挡
        menu.setWindowFlags(menu.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        menu.setStyleSheet(self.styleSheet())
        self._more_menu = menu             # 持引用防止弹出期间被回收

        if item["type"] == "ANGLE":
            _, span = self.canvas.angle_span(item)
            info = menu.addAction(trf("angle_current", value=abs(round(span))))
            info.setEnabled(False)
            menu.addSeparator()
            menu.addAction(tr("angle_plus"), lambda: self.canvas.adjust_angle_item(item, delta=5))
            menu.addAction(tr("angle_minus"), lambda: self.canvas.adjust_angle_item(item, delta=-5))
            preset = menu.addMenu(tr("angle_preset"))
            for deg in (30, 45, 60, 90, 120, 135):
                preset.addAction(f"{deg}°", lambda d=deg: self.canvas.adjust_angle_item(item, target=d))
            menu.addSeparator()
            menu.addAction(tr("angle_bisector"), lambda: self.canvas.angle_bisector_item(item))
        else:
            ops = self.canvas.shape_op_list(item)
            if not ops:
                if select_was_visible:
                    self.select_panel.show()
                    self.raise_floating(self.select_panel)
                return
            for key, label in ops:
                menu.addAction(label, lambda k=key: self.canvas.apply_shape_op(item, k))

        # 弹出期间必须停掉置顶心跳：bind_topmost_stack 里的 force_topmost(画布) 会把全屏
        # 画布拉到置顶层最顶端。这个 QMenu 刻意不挂父窗口，因而没有 owner 保护，弹出后
        # 500ms 内就会被画布盖住——菜单还在，但画布上的笔迹直接压在菜单文字上，点击也穿到
        # 画布。其余模态对话框（取色/校准/导入名单）早就用同一套 stop/start 处理。
        # singleShot(0)：QMenu 的原生窗口要等 exec() 弹出后才存在，此时再矫正一次 Z 序；
        # bind_owner=False 表示只排 Z 序、不改它的 owner，避免干扰 Qt 的弹窗管理。
        self.timer.stop()
        try:
            QTimer.singleShot(0, lambda: self.raise_floating(menu, bind_owner=False))
            menu.exec(QCursor.pos())
        finally:
            self.timer.start(self.HEARTBEAT_MS)

        # 菜单关闭后恢复 select_panel
        if select_was_visible:
            self.select_panel.show()
            self.raise_floating(self.select_panel)

    def position_selection_panel(self, rect):
        if not hasattr(self, "select_panel") or not self.canvas or not self.canvas.selected_ids or rect.isNull():
            if hasattr(self, "select_panel"):
                self.select_panel.hide()
            return
        was_visible = self.select_panel.isVisible()
        self.select_panel.adjustSize()
        screen = self.screen_geometry(self.canvas, self) or QApplication.primaryScreen().availableGeometry()
        x = min(screen.right() - self.select_panel.width() - 8, int(rect.right()) + 12)
        y = max(screen.top() + 8, min(screen.bottom() - self.select_panel.height() - 8, int(rect.top())))
        self.select_panel.move(max(screen.left() + 8, x), y)
        self.select_panel.show()
        self.select_panel.raise_()
        # 只在「隐藏→显示」这一次矫正 Z 序：拖动选中对象时本方法每帧都被调用，
        # 每帧重排窗口会让分层窗口反复重新合成而闪烁。
        if not was_visible:
            self.raise_floating(self.select_panel)
        else:
            force_topmost(self.select_panel.winId())

    def open_selection_color(self):
        self.timer.stop()
        try:
            d = QColorDialog(self.canvas.pen_color, self)
            d.setWindowTitle(tr("choose_object_color"))
            d.setOption(QColorDialog.ColorDialogOption.DontUseNativeDialog, True)
            if d.exec():
                self.canvas.pen_color = d.selectedColor()
                self.canvas.apply_selection_color(self.canvas.pen_color)
                self.color_preview.setStyleSheet(f"background-color: {self.canvas.pen_color.name()}; border: 1px solid white;")
                track_event("selection_color_changed", color=self.canvas.pen_color.name(), count=len(self.canvas.selected_ids))
        finally:
            self.timer.start(self.HEARTBEAT_MS)

    def on_selection_width_changed(self, v):
        self.canvas.pen_width = v
        self.canvas.apply_selection_width(v)
        self.select_width_label.setText(trf("width_value", value=v))
        self.label_w.setText(trf("width_value", value=v))
        track_event("selection_width_changed", width=v, count=len(self.canvas.selected_ids))

    def set_drawing_mode(self, enabled):
        cv = self.canvas
        if cv.is_drawing_mode == enabled:
            return
        cv.is_drawing_mode = enabled
        if not enabled:
            # 进入穿透模式：彻底隔离交互状态——清空选择、取消未完成图形与延迟识别，
            # 收起选择面板，避免画布在穿透态残留 HUD / 拦截输入。
            cv.selected_ids.clear()
            cv.selection_rect = None
            cv.selection_start = None
            cv.drag_start = None
            cv.drag_action = None
            cv.preview_shape = None
            cv.aid_drag = None
            cv.active_aid_id = None
            cv.cancel_pending_points()
            cv._cancel_smart_recognition(drop_pending=True)
            # 激光笔淡出定时器在穿透态无意义，停掉并清轨迹，避免穿透后空转触发全量重绘
            cv.laser_trail = []
            self._laser_fade.stop()
            self.select_panel.hide()
            self.show_only_sub(None)
        # setWindowFlag + show() can recreate the HWND; drop the owner cache so
        # the next bind_topmost_stack re-parents the panel above the new canvas.
        cv.setWindowFlag(Qt.WindowType.WindowTransparentForInput, not enabled)
        cv.show()
        self._bound_key = None
        self._topmost_state = None
        self.btn_mode.setText(tr("passthrough") if enabled else tr("drawing_mode"))
        self.btn_mode.setStyleSheet(f"background-color: {self.theme['mode'] if enabled else self.theme['mode_off']}; color: white;")
        track_event("mode_changed", drawing_mode=enabled)
        # 画布 HWND 刚被 setWindowFlag+show() 重建，新画布默认压在面板之上。
        # bind_topmost_stack 里的 force_above 会同步矫正兄弟高度，但新 HWND 可能
        # 还没完全 settle，于是用几个短延迟重绑，确保面板即时置顶、不留被压住的窗口。
        # 关键：HEARTBEAT_MS=500，前几次重绑（0/120ms）可能赶在合成器 settle 之前，
        # 新画布在这 500ms 内仍可能反压面板。最后一拍（540ms）刻意刚跨过首个心跳周期，
        # 保证在心跳自己接管前列出一次「面板压在画布之上」的矫正，消除 ≤500ms 的被盖窗口。
        self.bind_topmost_stack()
        QTimer.singleShot(0, self.bind_topmost_stack)
        QTimer.singleShot(120, self.bind_topmost_stack)
        QTimer.singleShot(320, self.bind_topmost_stack)
        QTimer.singleShot(540, self.bind_topmost_stack)
        if enabled and cv.draw_state == "LASER":
            # 退出穿透重新进入绘图态：激光笔仍是当前工具就必须把淡出定时器重新启动，
            # 否则轨迹在鼠标停下时不再淡出/裁剪（set_tool 因 draw_state 已是 LASER 会直接 return，
            # 不会再走 _laser_fade.start() 那条路径，激光笔的定时重绘就被永久跳过了）。
            cv.laser_trail = []
            self._laser_fade.start()

    def toggle_mode(self):
        self.set_drawing_mode(not self.canvas.is_drawing_mode)

    def toggle_orientation(self):
        self.set_orientation("landscape" if self.orientation == "portrait" else "portrait")
        track_event("orientation_changed", orientation=self.orientation)

    def _floating_anchor(self, panel_width, panel_height, gap=8, anchor=None):
        """公共浮动面板锚点计算。

        - 横版：面板挂在触发它的那个功能键【正下方】；下方放不下就整体翻到工具栏上方。
        - 竖版：面板挂在工具栏右侧，并与触发键【同高】；右侧放不下就翻到左侧。

        anchor 传入触发子菜单的按钮，用来对齐；不传（缩略图等公共浮窗）时退化为对齐
        工具栏本身。返回的 (x, y) 已经 clamp 进当前屏幕可用区。

        三个必须「翻面」而不是「clamp」的场景（clamp 会把子菜单压在主面板身上）：
        主面板贴屏幕底部时横版子菜单要往上开、贴右侧时竖版子菜单要往左开、
        以及拖动主面板到边缘的过程中实时换边。
        """
        screen = self.screen_geometry(self) or QApplication.primaryScreen().availableGeometry()
        frame = self.frameGeometry()
        if anchor is not None and anchor.isVisible():
            spot = anchor.mapToGlobal(QPoint(0, 0))
            anchor_rect = QRectF(spot.x(), spot.y(), anchor.width(), anchor.height())
        else:
            anchor_rect = QRectF(frame.x(), frame.y(), frame.width(), frame.height())

        def fit(value, low, high):
            return max(low, min(high, value))

        if self.orientation == "landscape":
            # 水平：以触发键中心对齐子菜单中心，再收进屏幕
            x = fit(anchor_rect.center().x() - panel_width / 2.0,
                    screen.left() + 8, screen.right() - panel_width - 8)
            below = frame.bottom() + gap
            above = frame.top() - gap - panel_height
            if below + panel_height <= screen.bottom() - 4:
                y = below
            elif above >= screen.top() + 4:
                y = above                      # 主面板在屏幕下方：子菜单改在主面板上方
            else:
                y = fit(below, screen.top() + 8, screen.bottom() - panel_height - 8)
        else:
            right = frame.right() + gap
            left = frame.left() - gap - panel_width
            if right + panel_width <= screen.right() - 4:
                x = right
            elif left >= screen.left() + 4:
                x = left                       # 主面板贴右边：子菜单改开在左侧
            else:
                x = fit(right, screen.left() + 8, screen.right() - panel_width - 8)
            # 垂直：与触发键顶端齐平，长面板则整体上移到屏幕内
            y = fit(anchor_rect.top() - 6, screen.top() + 8, screen.bottom() - panel_height - 8)
        return int(x), int(y)

    # 子菜单 → 触发它的主栏按钮。横版下子菜单要开在这个按钮正下方，
    # 竖版下要与它同高；缺了这张表，所有子菜单都只能对齐面板左上角
    # （表现就是「子菜单永远跑到最左边，不在当前功能键下方」）。
    SUB_ANCHORS = {
        "draw_sub": "btn_pen", "annotate_sub": "btn_pen", "marker_sub": "btn_pen",
        "laser_sub": "btn_pen", "eraser_sub": "btn_eraser", "shape_sub": "btn_shape",
        "tools_sub": "btn_tools", "aid_sub": "btn_tools", "magnifier_sub": "btn_tools",
        "file_sub": "btn_file", "timer_sub": "btn_tools",
    }

    def sub_anchor_button(self, target):
        for name, button_name in self.SUB_ANCHORS.items():
            if getattr(self, name, None) is target:
                return getattr(self, button_name, None)
        return None

    def set_orientation(self, orientation):
        """在竖版 / 横版工具栏之间切换：把已有的工具栏条目重新排布。

        实现方式是从 main_frame 当前布局里把所有条目（widget / sublayout）一并 takeAt
        取出，再用目标方向的布局重新插回——元素本身（按钮 / 行布局 / 白板区）不变，
        只是排布方向从纵向变横向。竖版固定宽度 150、横版不固定宽度按高度收紧。
        """
        if orientation not in ("portrait", "landscape") or orientation == self.orientation:
            return
        self.orientation = orientation
        # 先把现有条目从 toolbar_layout 全部取下，保留对象本身
        items = []
        while self.toolbar_layout.count():
            item = self.toolbar_layout.takeAt(0)
            w = item.widget()
            sub = item.layout()
            if w is not None:
                items.append(("widget", w))
            elif sub is not None:
                items.append(("layout", sub))
        # 把旧布局从 main_frame 卸下（交给一个临时 QWidget 接管，避免 Qt 警告）
        temp = QWidget()
        temp.setLayout(self.toolbar_layout)
        # 新建目标方向布局
        if orientation == "landscape":
            new_layout = QHBoxLayout(self.main_frame)
        else:
            new_layout = QVBoxLayout(self.main_frame)
        new_layout.setContentsMargins(8, 8, 8, 8)
        new_layout.setSpacing(2)
        new_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter if orientation == "landscape" else Qt.AlignmentFlag.AlignTop)
        for kind, obj in items:
            if kind == "widget":
                new_layout.addWidget(obj)
            else:
                new_layout.addLayout(obj)
        self.toolbar_layout = new_layout
        self._layout_wb_box()      # 白板控制区跟着换行/换列，否则横版下文字被压掉
        # 竖版：固定宽度、高度自适应；横版：宽度自适应、高度按内容收紧。
        # 横版原来写死 setFixedHeight(70)：白板控制区一显示就要两行按钮的高度，
        # 硬压在 70px 里会把「上页/下页/新页/黑板」的字裁掉，所以改由内容决定高度。
        self.main_frame.setMinimumHeight(0)
        self.main_frame.setMaximumHeight(16777215)       # QWIDGETSIZE_MAX
        self.main_frame.setMinimumWidth(0)
        self.main_frame.setMaximumWidth(16777215)
        if orientation == "portrait":
            self.main_frame.setFixedWidth(150)
        self.title_label.setText(f" ⠿ {tr('app')} {APP_VERSION}")
        self._resize_to_content()                        # 内部会 clamp_into_screen 收回屏幕
        track_event("orientation_set", orientation=orientation)
        self.heartbeat_refresh()

    def on_color_clicked(self):
        btn = self.sender(); self.canvas.pen_color = QColor(btn.property("color_val"))
        self.canvas.apply_selection_color(self.canvas.pen_color)
        self.update_button_highlight(btn); self.color_preview.setStyleSheet(f"background-color: {self.canvas.pen_color.name()}; border: 1px solid white;")
        track_event("color_changed", color=self.canvas.pen_color.name())

    def on_pen_slider_changed(self, v): self.canvas.pen_width = v; self.canvas.apply_selection_width(v); self.label_w.setText(trf("width_value", value=v)); track_event("pen_width_changed", width=v)
    def on_eraser_slider_changed(self, v): self.canvas.eraser_size = v; self.e_label.setText(trf("sensitivity_value", value=v)); track_event("eraser_size_changed", size=v)
    def set_eraser_type(self, t):
        self.canvas.eraser_type = t
        self.btn_circ.setObjectName("ActiveTool" if t == "CIRCLE" else ""); self.btn_stroke.setObjectName("ActiveTool" if t == "STROKE" else "")
        self.btn_circ.setStyle(self.btn_circ.style()); self.btn_stroke.setStyle(self.btn_stroke.style())
        track_event("eraser_type_changed", eraser_type=t)

    def update_button_highlight(self, active_btn):
        for btn in self.color_buttons:
            c = btn.styleSheet().split("border:")[0]
            btn.setStyleSheet(c + (f"border: 2px solid {self.theme['accent']};" if btn == active_btn else "border: 1px solid #777;"))

    def open_custom_color(self):
        self.timer.stop()
        try:
            d = QColorDialog(self.canvas.pen_color, self)
            d.setWindowTitle(tr("choose_custom_color"))
            d.setOption(QColorDialog.ColorDialogOption.DontUseNativeDialog, True)
            d.setOption(QColorDialog.ColorDialogOption.ShowAlphaChannel, False)
            if d.exec():
                self.canvas.pen_color = d.selectedColor()
                self.canvas.apply_selection_color(self.canvas.pen_color)
                self.update_button_highlight(self.color_buttons[-1])
                self.color_preview.setStyleSheet(f"background-color: {self.canvas.pen_color.name()}; border: 1px solid white;")
                track_event("custom_color_changed", color=self.canvas.pen_color.name())
        finally:
            self.timer.start(self.HEARTBEAT_MS)

    def undo(self):
        self.canvas.undo()

    def redo(self):
        self.canvas.redo()

    def update_history_ui(self):
        if not self.canvas or not hasattr(self, "btn_undo"):
            return
        self.btn_undo.setEnabled(bool(self.canvas.undo_stack))
        self.btn_redo.setEnabled(bool(self.canvas.redo_stack))

    def clear(self):
        if not (self.canvas.all_segments or self.canvas.text_items or self.canvas.shape_items or self.canvas.image_items):
            return
        self.canvas._cancel_smart_recognition(drop_pending=True)  # 清屏：丢弃还没触发的延迟识别
        self.canvas.push_undo()
        self.canvas.dash_chain = None
        self.canvas.all_segments = []; self.canvas.text_items = []; self.canvas.shape_items = []; self.canvas.image_items = []; self.canvas.selected_ids.clear(); self.canvas.update()
        if self.canvas.whiteboard_mode: self.canvas.save_current_page()
        self.select_panel.hide()
        track_event("clear")
    def bind_topmost_stack(self):
        """Keep the control panel and floating tools above the fullscreen canvas.

        Canvas and panel are both topmost Tool windows. Windows only guarantees
        that an *owned* window stays above its owner, so every panel HWND is
        bound to the canvas via GWLP_HWNDPARENT. Owner rebind runs only when a
        winId changes; force_topmost still runs each heartbeat so a canvas
        show()/mode switch cannot permanently bury the panel.

        关键补充：仅靠 GWLP_HWNDPARENT 与 HWND_TOPMOST 不足以修掉「面板被画布盖住」。
        两者同处置顶层时 HWND_TOPMOST 不决定兄弟高低，而 set_drawing_mode 里
        setWindowFlag+show() 会让画布重建 HWND，新画布默认落在置顶层顶端反而压住面板。
        因此每次心跳都额外 force_above(panel/floatings, canvas) 用 SetWindowPos 把窗口
        显式叠到画布正上方，同步矫正兄弟高度——面板即时置顶。
        """
        if not self.canvas or getattr(self, "_grabbing", False):
            return
        floatings = [
            w for w in (
                getattr(self, "menu_panel", None),
                getattr(self, "select_panel", None),
                getattr(self, "mini_timer", None),
                getattr(self, "thumbnail_panel", None),
                getattr(self, "calc_panel", None),
                getattr(self, "roster_panel", None),
            ) if w is not None
        ]
        try:
            owner = int(self.canvas.winId())
            panel_hwnd = int(self.winId())
            floating_hwnds = tuple(int(w.winId()) for w in floatings)
            key = (owner, panel_hwnd) + floating_hwnds
            if key != getattr(self, "_bound_key", None):
                set_window_owner(panel_hwnd, owner)
                for hwnd in floating_hwnds:
                    set_window_owner(hwnd, owner)
                # 句柄新建/重建时顺手关掉系统触控手势加工（按住变右键、甩动、等待光环）。
                # 挂在这里而不是每拍心跳：SetProp 是按窗口一次性生效的，而画布切换
                # 穿透/绘图模式会重建 HWND，新句柄必须重新设置一次。
                for hwnd in (owner, panel_hwnd) + floating_hwnds:
                    disable_touch_gestures(hwnd)
                self._bound_key = key
            if not self.isVisible():
                self.show()
            # 关键：只 force_topmost(HWND_TOPMOST) 无法决定同在置顶层的两个兄弟谁高谁低。
            # set_drawing_mode 里画布的 setWindowFlag + show() 会重建画布 HWND，新画布默认
            # 落到置顶层最顶端（面板之上）。这里显式把面板/浮窗用 SetWindowPos 叠到画布正上方，
            # 同步矫正兄弟高度，面板就不再被画布盖住。顺序很重要：
            #   ① 先把画布托进 TOPMOST 层，避免下方 force_above(panel,canvas) 把面板从
            #     非置顶的画布之上连带拉出 TOPMOST 层（那样面板会跌层、被普通窗口盖住）。
            #   ② 面板进 TOPMOST 层。
            #   ③ 面板排到画布正上方（同置顶层内矫正兄弟高低）。
            #   ④ 各浮窗同样进 TOPMOST 并压到画布正上方。
            force_topmost(owner)
            force_topmost(panel_hwnd)
            force_above(panel_hwnd, owner)
            for floating in floatings:
                if floating.isVisible():
                    force_topmost(int(floating.winId()))
                    force_above(int(floating.winId()), owner)
            self._raise_tooltip(owner)
            self._topmost_state = key
            self._topmost_error = None
        except Exception:
            self._bound_key = None  # retry cleanly on the next heartbeat
            self._topmost_state = None
            if not getattr(self, "_topmost_error", False):
                self._topmost_error = True
                LOGGER.exception("窗口层级更新失败")

    @staticmethod
    def _raise_tooltip(owner):
        """把正在显示的提示气泡抬到全屏画布之上。

        气泡是 Qt 自己建的顶层窗口（QTipLabel），既不在我们的 owner 链里，也没进心跳
        管理的浮窗列表。而心跳每 500ms 会把全屏画布重新推到置顶层顶端——气泡一弹出来，
        半秒内就被画布压住，只剩一角露在面板上，看起来就是「悬停按钮时冒出一块遮挡」。
        """
        if not QToolTip.isVisible():
            return
        for widget in QApplication.topLevelWidgets():
            if widget.isVisible() and widget.metaObject().className() == "QTipLabel":
                hwnd = int(widget.winId())
                force_topmost(hwnd)
                force_above(hwnd, owner)

    def heartbeat_refresh(self):
        self.bind_topmost_stack()

    def raise_floating(self, widget, bind_owner=True):
        """把刚显示出来的浮窗重新钉到全屏画布之上。

        bind_topmost_stack 只在 winId 组合变化时才重绑 owner；而 hide()/show() 不会改
        winId，Qt 却可能在 show 时把 GWLP_HWNDPARENT 重置回它自己的值。owner 一丢，画布
        和浮窗就成了置顶层里两个普通兄弟，谁在上全看运气——浮窗落到全屏画布之下时点击会
        穿到画布上，表现就是「子菜单不置顶、点不动」。计算器/点名浮窗一直正常，正是因为
        它们显示后会 _bound_key=None 触发重绑；这里把同一套动作补给所有浮窗。

        bind_owner=False 用于 QMenu 这类 Qt 自己管理的弹出窗口：只矫正 Z 序，不去改它的
        GWLP_HWNDPARENT，免得干扰 Qt 的弹窗/失焦关闭逻辑。
        """
        if widget is None or not self.canvas or not widget.isVisible():
            return
        try:
            hwnd = int(widget.winId())
            owner = int(self.canvas.winId())
        except Exception:
            return
        if not hwnd or not owner:
            return
        if bind_owner:
            set_window_owner(hwnd, owner)
        force_topmost(owner)      # 先保证画布在置顶层，避免下一步把浮窗带出置顶层
        force_topmost(hwnd)
        force_above(hwnd, owner)
        if bind_owner:
            self._bound_key = None    # 让下一拍心跳重新校验整组窗口的 owner

    # --- 主面板拖动：按住空白处/标题拖动，按钮不受影响 ---
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_offset is not None and (event.buttons() & Qt.MouseButton.LeftButton):
            target = event.globalPosition().toPoint() - self._drag_offset
            # Clamp to the screen under the pointer so the panel can travel to a secondary display.
            pointer = event.globalPosition().toPoint()
            screen_obj = QGuiApplication.screenAt(pointer) or self.active_screen(self)
            screen = screen_obj.availableGeometry() if screen_obj is not None else QApplication.primaryScreen().availableGeometry()
            x = max(screen.left(), min(screen.right() - self.width(), target.x()))
            y = max(screen.top(), min(screen.bottom() - self.height(), target.y()))
            self.move(x, y)
            if self.menu_panel.isVisible():
                self.position_menu_panel()   # 子菜单跟随面板
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_offset = None
        super().mouseReleaseEvent(event)

    # --- 拖拽项目文件打开 ---
    PROJECT_SUFFIXES = (".msd", ".json")

    def _dragged_project_path(self, event):
        """从拖拽事件里取第一个本地 .msd/.json 文件路径，不是则返回 None。"""
        if not event.mimeData().hasUrls():
            return None
        for url in event.mimeData().urls():
            local = url.toLocalFile()
            if not local:
                continue
            if local.lower().endswith(self.PROJECT_SUFFIXES):
                return local
        return None

    def dragEnterEvent(self, event):
        if self._dragged_project_path(event) is not None:
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if self._dragged_project_path(event) is not None:
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        super().dragLeaveEvent(event)

    def dropEvent(self, event):
        path = self._dragged_project_path(event)
        if path is None:
            event.ignore()
            return
        event.acceptProposedAction()
        # 拖拽放下时暂停心跳，避免在打开过程中窗口被反复重排
        self.timer.stop()
        try:
            self.open_project_from_path(path)
        finally:
            self.timer.start(self.HEARTBEAT_MS)
        self.heartbeat_refresh()
        track_event("project_dropped", path=os.path.basename(path))

    # --- 配置持久化：可自定义项退出/定时落盘，启动原样恢复 ---
    TOOL_STATES = ("PEN", "MARKER", "LASER", "ERASER", "SELECT", "TEXT", "SHAPE")
    SHAPE_TYPES = (
        "LINE", "DASHED_LINE", "TRIANGLE", "RECT", "PARALLELOGRAM", "TRAPEZOID",
        "DIAMOND", "ANGLE", "CIRCLE", "ELLIPSE", "CUBE", "CUBOID", "CYLINDER", "CONE",
    )

    def collect_settings(self):
        """汇总当前全部可自定义配置（纯 dict，便于测试/落盘）。"""
        cv = self.canvas
        if not cv:
            return {}
        tool = cv.draw_state if cv.draw_state in self.TOOL_STATES else "PEN"
        return {
            "theme": self.theme_name,
            "pen_color": cv.pen_color.name(),
            "pen_width": int(cv.pen_width),
            "eraser_type": cv.eraser_type,
            "eraser_size": int(cv.eraser_size),
            "marker_color": cv.marker_color.name(),
            "marker_alpha_pct": int(self.marker_alpha_slider.value()),
            "marker_width": int(cv.marker_width),
            "laser_color": cv.laser_color.name(),
            "laser_width": int(cv.laser_width),
            "magnifier_zoom": float(cv.magnifier_zoom),
            "magnifier_size": int(cv.magnifier_size),
            "board_style": cv.board_style,
            "smart_shapes": bool(cv.smart_shapes_enabled),
            "timer_mode": self.timer_mode,
            "timer_target": int(self.timer_target),
            "panel_x": int(self.x()),
            "panel_y": int(self.y()),
            "panel_screen": self.screen().name() if self.screen() else "",
            "orientation": self.orientation,
            "draw_state": tool,
            "shape_type": cv.shape_type if cv.shape_type in self.SHAPE_TYPES else "LINE",
            "text_font_size": int(cv.text_font_size),
            "drawing_mode": bool(cv.is_drawing_mode),
            "ruler_calibrations": normalize_calibrations(cv.ruler_calibrations),
        }

    def save_settings(self):
        """写入 data/config.json；原子替换，避免写到一半崩掉把配置写坏。"""
        settings = self.collect_settings()
        if not settings:
            return
        last_error = None
        for attempt in range(5):
            try:
                # Unique temp name + atomic replace; retries cover Windows file locks
                # (antivirus / concurrent autosave / explorer preview).
                atomic_write_json(CONFIG_FILE, settings)
                track_event("settings_saved", keys=len(settings))
                return
            except PermissionError as e:
                last_error = e
                time.sleep(0.05 * (attempt + 1))
            except OSError as e:
                # WinError 32 often surfaces as OSError on some Python builds.
                if getattr(e, "winerror", None) == 32 or e.errno in (13, 11):
                    last_error = e
                    time.sleep(0.05 * (attempt + 1))
                    continue
                last_error = e
                break
            except Exception as e:
                last_error = e
                break
        LOGGER.error("配置保存失败: %s", last_error)
        track_event("settings_save_failed", error=str(last_error))

    def highlight_color_for(self, buttons, color_name):
        """按颜色值找到对应预设按钮高亮；不在预设里则高亮自定义（最后一个）按钮。"""
        target = buttons[-1]
        for btn in buttons[:-1]:
            if str(btn.property("color_val")).lower() == color_name.lower():
                target = btn
                break
        return target

    def restore_position(self):
        """启动时恢复面板位置，并钳制到当前可用屏幕。"""
        saved = getattr(self, "_saved_pos", None)
        if not saved:
            return False
        screens = []
        for screen in QGuiApplication.screens():
            geometry = screen.availableGeometry()
            screens.append({"name": screen.name(), "geometry": (geometry.left(), geometry.top(), geometry.width(), geometry.height())})
        selected = choose_screen(saved[0], saved[1], screens, getattr(self, "_saved_screen", None))
        if not selected:
            return False
        x, y = clamp_rect(saved[0], saved[1], self.width(), self.height(), selected["geometry"])
        self.move(x, y)
        return True

    def restore_tool(self, state):
        """恢复上次工具高亮；不弹子菜单。放大镜启动时无不到冻结帧，回退批注笔。"""
        mapping = {
            "PEN": self.btn_pen,
            "MARKER": self.btn_pen,
            "LASER": self.btn_pen,
            "ERASER": self.btn_eraser,
            "SELECT": self.btn_select,
            "TEXT": self.btn_text,
            "SHAPE": self.btn_shape,
        }
        if state not in mapping:
            state = "PEN"
        self.canvas.draw_state = state
        self.set_active_tool(mapping[state])
        if state == "SHAPE":
            self.update_shape_buttons()
        if state == "LASER":
            self._laser_fade.start()

    def sync_settings_ui(self):
        """把已写入 canvas/slider 的值同步到预览条、高亮、选中粗细标签等。"""
        cv = self.canvas
        if not cv:
            return
        if hasattr(self, "color_preview"):
            self.color_preview.setStyleSheet(
                f"background-color: {cv.pen_color.name()}; border: 1px solid white;"
            )
        if self.color_buttons:
            self.update_button_highlight(self.highlight_color_for(self.color_buttons, cv.pen_color.name()))
        if getattr(self, "marker_color_buttons", None):
            self.highlight_marker_color(
                self.highlight_color_for(self.marker_color_buttons, cv.marker_color.name())
            )
        if getattr(self, "laser_color_buttons", None):
            self.highlight_laser_color(
                self.highlight_color_for(self.laser_color_buttons, cv.laser_color.name())
            )
        if hasattr(self, "label_w"):
            self.label_w.setText(trf("width_value", value=cv.pen_width))
        if hasattr(self, "laser_width_label"):
            self.laser_width_label.setText(trf("laser_dot", value=cv.laser_width))
        if hasattr(self, "laser_width_slider"):
            self.laser_width_slider.blockSignals(True)
            self.laser_width_slider.setValue(max(6, min(40, int(cv.laser_width))))
            self.laser_width_slider.blockSignals(False)
        if hasattr(self, "select_width_label"):
            self.select_width_label.setText(trf("width_value", value=cv.pen_width))
        if hasattr(self, "select_width_slider"):
            self.select_width_slider.blockSignals(True)
            self.select_width_slider.setValue(max(1, min(40, int(cv.pen_width))))
            self.select_width_slider.blockSignals(False)
        self.update_magnifier_ui()
        self.update_timer_ui()
        self.update_shape_buttons()
        self.refresh_ui()

    def load_settings(self):
        """加载配置文件，带容错处理和默认值回退。"""
        self._saved_pos = None
        self._saved_screen = None
        cv = self.canvas

        default_settings = self.collect_settings()
        default_settings.setdefault("marker_alpha_pct", 35)
        default_settings.setdefault("timer_mode", "DOWN")
        default_settings.setdefault("timer_target", 10)
        default_settings.setdefault("draw_state", "PEN")
        default_settings.setdefault("shape_type", "LINE")
        default_settings.setdefault("text_font_size", 24)
        default_settings.setdefault("drawing_mode", True)

        settings = default_settings.copy()

        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, encoding="utf-8") as f:
                    loaded = json.load(f)
                    if isinstance(loaded, dict):
                        settings.update(loaded)
                    else:
                        track_event("config_invalid_format")
            else:
                track_event("config_not_found", using_defaults=True)
        except json.JSONDecodeError as e:
            track_event("config_parse_error", error=str(e))
        except Exception as e:
            track_event("config_load_error", error=str(e))

        try:
            if settings.get("theme") in self.THEMES and settings["theme"] != self.theme_name:
                self.theme_name = settings["theme"]
                self.theme = self.THEMES[self.theme_name]
                self.apply_theme()

            color = QColor(str(settings.get("pen_color", cv.pen_color.name())))
            if color.isValid():
                cv.pen_color = color
            # 直接写 canvas：slider 值未变时 setValue 不发信号，不能只靠滑条回写
            cv.pen_width = max(1, min(40, int(settings.get("pen_width", cv.pen_width))))
            self.pen_slider.blockSignals(True)
            self.pen_slider.setValue(cv.pen_width)
            self.pen_slider.blockSignals(False)

            if settings.get("eraser_type") in ("CIRCLE", "STROKE"):
                self.set_eraser_type(settings["eraser_type"])
            cv.eraser_size = max(1, min(200, int(settings.get("eraser_size", cv.eraser_size))))
            self.e_slider.blockSignals(True)
            self.e_slider.setValue(cv.eraser_size)
            self.e_slider.blockSignals(False)

            marker_color = QColor(str(settings.get("marker_color", cv.marker_color.name())))
            if marker_color.isValid():
                cv.marker_color = marker_color
            alpha_pct = max(10, min(90, int(settings.get("marker_alpha_pct", 35))))
            self.marker_alpha_slider.blockSignals(True)
            self.marker_alpha_slider.setValue(alpha_pct)
            self.marker_alpha_slider.blockSignals(False)
            cv.marker_alpha = max(10, min(255, round(alpha_pct * 255 / 100)))
            if hasattr(self, "marker_alpha_label"):
                self.marker_alpha_label.setText(trf("opacity_value", value=alpha_pct))
            cv.marker_width = max(1, min(80, int(settings.get("marker_width", cv.marker_width))))
            self.marker_width_slider.blockSignals(True)
            self.marker_width_slider.setValue(cv.marker_width)
            self.marker_width_slider.blockSignals(False)
            if hasattr(self, "marker_width_label"):
                self.marker_width_label.setText(trf("width_value", value=cv.marker_width))
            if hasattr(self, "e_label"):
                self.e_label.setText(trf("sensitivity_value", value=cv.eraser_size))

            laser_color = QColor(str(settings.get("laser_color", cv.laser_color.name())))
            if laser_color.isValid():
                cv.laser_color = laser_color
            cv.laser_width = max(6, min(40, int(settings.get("laser_width", cv.laser_width))))
            if hasattr(self, "laser_width_slider"):
                self.laser_width_slider.blockSignals(True)
                self.laser_width_slider.setValue(cv.laser_width)
                self.laser_width_slider.blockSignals(False)

            zoom = float(settings.get("magnifier_zoom", cv.magnifier_zoom))
            cv.magnifier_zoom = max(cv.MAGNIFIER_ZOOM_MIN, min(cv.MAGNIFIER_ZOOM_MAX, zoom))
            cv.magnifier_size = max(80, min(600, int(settings.get("magnifier_size", cv.magnifier_size))))
            self.mag_size_slider.blockSignals(True)
            self.mag_size_slider.setValue(cv.magnifier_size)
            self.mag_size_slider.blockSignals(False)

            if settings.get("board_style") in ("WHITE", "BLACK"):
                cv.board_style = settings["board_style"]
            smart = settings.get("smart_shapes")
            if isinstance(smart, bool):
                self.btn_smart_toggle.blockSignals(True)
                self.btn_smart_toggle.setChecked(smart)
                self.btn_smart_toggle.blockSignals(False)
                cv.smart_shapes_enabled = smart
                self.btn_smart_toggle.setText(tr("smart_shapes_on") if smart else tr("smart_shapes_off"))
            if settings.get("timer_mode") in ("UP", "DOWN"):
                self.timer_mode = settings["timer_mode"]
            target = settings.get("timer_target")
            if isinstance(target, int) and 0 < target <= 99 * 60 + 59:
                self.timer_target = target
                self.timer_left = float(target) if self.timer_mode == "DOWN" else 0.0
            if settings.get("shape_type") in self.SHAPE_TYPES:
                cv.shape_type = settings["shape_type"]
            font_size = settings.get("text_font_size")
            if isinstance(font_size, int) and 8 <= font_size <= 200:
                cv.text_font_size = font_size
            drawing_mode = settings.get("drawing_mode")
            if isinstance(drawing_mode, bool):
                self.set_drawing_mode(drawing_mode)
            cv.ruler_calibrations = normalize_calibrations(settings.get("ruler_calibrations", {}))
            legacy = settings.get("ruler_calibration")
            if not cv.ruler_calibrations and isinstance(legacy, dict) and valid_pixels_per_mm(legacy.get("px_per_mm")):
                current_key, _, _ = cv.current_screen_calibration()
                cv.ruler_calibrations[current_key] = {
                    "screen_key": current_key,
                    "px_per_mm": float(legacy["px_per_mm"]),
                    "known_length_mm": float(legacy.get("known_length_mm", 100.0)),
                    "dpr": 1.0,
                    "logical_dpi": 96.0,
                    "geometry": [],
                }
            self.update_ruler_calibration_label()
            self.restore_tool(settings.get("draw_state", "PEN"))
            # 方向要在读回位置之前恢复：横竖版尺寸不同，restore_position 得按最终尺寸钳制
            saved_orientation = settings.get("orientation")
            if saved_orientation in ("portrait", "landscape"):
                self.set_orientation(saved_orientation)
            px, py = settings.get("panel_x"), settings.get("panel_y")
            if isinstance(px, int) and isinstance(py, int):
                self._saved_pos = (px, py)
            self._saved_screen = settings.get("panel_screen") if isinstance(settings.get("panel_screen"), str) else None
            self.sync_settings_ui()
            track_event("settings_loaded", tool=cv.draw_state, theme=self.theme_name)
        except Exception as e:
            track_event("settings_apply_failed", error=str(e))

    def auto_save(self):
        """自动保存配置 + 画布内容。"""
        if not self.canvas:
            return
        self.save_settings()  # 偏好也定期落盘，异常退出也不丢
        try:
            if self.canvas.whiteboard_mode:
                self.canvas.save_current_page()
                pages = [serialize_page(page) for page in self.canvas.pages]
            else:
                pages = [serialize_page(self.canvas.capture_page())]
            if not any(page_has_content(page) for page in pages):
                return  # 空白不写，避免刷一堆空快照

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = os.path.join(AUTOSAVE_DIR, f"autosave_{timestamp}.json")
            # Keep autosaves on the same schema construction path as normal projects;
            # duplicated payloads previously drifted to a legacy `version` field.
            data = make_project_data(
                pages=pages,
                current_page=self.canvas.current_page,
                whiteboard_mode=self.canvas.whiteboard_mode,
                board_style=self.canvas.board_style,
                app_version=APP_VERSION,
                kind=AUTOSAVE_KIND,
            )
            data["timestamp"] = timestamp
            atomic_write_json(filepath, data)
            self._cleanup_autosave_files(keep=5)
            track_event("autosave_success", pages=len(pages))
        except Exception as e:
            LOGGER.exception("自动保存失败")
            track_event("autosave_failed", error=str(e))

    def _list_autosave_files(self):
        files = []
        try:
            for filename in os.listdir(AUTOSAVE_DIR):
                if filename.startswith("autosave_") and filename.endswith(".json"):
                    filepath = os.path.join(AUTOSAVE_DIR, filename)
                    files.append((os.path.getmtime(filepath), filepath))
        except OSError:
            return []
        files.sort(reverse=True)
        return files

    def _latest_restorable_autosave(self):
        """找最近一份「有内容」的自动保存；坏文件/空文件跳过。"""
        for _, filepath in self._list_autosave_files():
            try:
                with open(filepath, encoding="utf-8") as f:
                    data = json.load(f)
                data = normalize_project_data(data, kind=AUTOSAVE_KIND)
                pages = data.get("pages") or []
                if any(page_has_content(page) for page in pages):
                    return filepath, data
            except Exception as exc:
                LOGGER.warning("跳过无效自动保存 %s: %s", os.path.basename(filepath), exc)
        return None, None

    def apply_autosave_data(self, data):
        """把 autosave JSON 灌回画布（启动恢复用）。"""
        cv = self.canvas
        if not cv or not data:
            return False
        pages_data = data.get("pages") or []
        if not pages_data:
            return False
        pages = [deserialize_page(page) for page in pages_data]
        board_style = data.get("board_style")
        if board_style in ("WHITE", "BLACK"):
            cv.board_style = board_style
        current = int(data.get("current_page", 0) or 0)
        current = max(0, min(len(pages) - 1, current))
        if data.get("whiteboard_mode"):
            cv.whiteboard_mode = True
            cv.pages = pages
            cv.current_page = current
            cv.load_page(pages[current])
        else:
            cv.whiteboard_mode = False
            cv.pages = []
            cv.current_page = 0
            cv.load_page(pages[current])
        cv.reset_history()
        self.update_whiteboard_ui()
        self.update_history_ui()
        self.sync_selection_controls()
        self.position_selection_panel(QRectF())
        return True

    def offer_autosave_restore(self):
        """启动时若有未空的自动保存，询问是否恢复。"""
        filepath, data = self._latest_restorable_autosave()
        if not data:
            return False
        stamp = data.get("timestamp") or os.path.basename(filepath)
        pages = data.get("pages") or []
        mode = tr("whiteboard") if data.get("whiteboard_mode") else tr("annotate")
        detail = f"{mode} · {len(pages)}\n{stamp}"
        reply = QMessageBox.question(
            self, tr("restore_autosave"), detail,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if reply != QMessageBox.StandardButton.Yes:
            track_event("autosave_restore_declined", file=os.path.basename(filepath))
            return False
        try:
            ok = self.apply_autosave_data(data)
            track_event("autosave_restored" if ok else "autosave_restore_empty",
                        file=os.path.basename(filepath), pages=len(pages))
            return ok
        except Exception as e:
            track_event("autosave_restore_failed", error=str(e), file=os.path.basename(filepath))
            notify_user(self, tr("restore_failed"), str(e), level="warning", exc=e)
            return False

    def _cleanup_autosave_files(self, keep=5):
        """清理旧的自动保存文件，只保留最近的 N 个。"""
        try:
            files = self._list_autosave_files()
            for _, filepath in files[keep:]:
                os.remove(filepath)
                track_event("autosave_cleanup", file=os.path.basename(filepath))
        except Exception as e:
            track_event("autosave_cleanup_failed", error=str(e))

    def active_screen(self, *widgets):
        """Return the QScreen under the first given widget, else panel/canvas, else primary."""
        candidates = list(widgets) + [getattr(self, "canvas", None), self]
        for widget in candidates:
            if widget is None:
                continue
            try:
                screen = widget.screen()
            except Exception:
                screen = None
            if screen is not None:
                return screen
            try:
                center = widget.frameGeometry().center()
                screen = QGuiApplication.screenAt(center)
            except Exception:
                screen = None
            if screen is not None:
                return screen
        return QApplication.primaryScreen()

    def screen_geometry(self, *widgets):
        screen = self.active_screen(*widgets)
        if screen is None:
            return None
        return screen.availableGeometry()

    def grab_screen(self):
        """抓取当前画布所在屏幕（含已画好的批注），抓取前把面板/浮窗藏起来避免入镜。"""
        select_visible = self.select_panel.isVisible()
        menu_visible = self.menu_panel.isVisible()
        mini_visible = self.mini_timer.isVisible()
        calc_visible = bool(self.calc_panel and self.calc_panel.isVisible())
        roster_visible = bool(self.roster_panel and self.roster_panel.isVisible())
        thumb_visible = bool(getattr(self, "thumbnail_panel", None) and self.thumbnail_panel.isVisible())
        proj_visible = bool(self._name_projection is not None and self._name_projection.isVisible())
        try:
            # 抓屏期间 timer_clock 仍在跑，禁止它把迷你计时器拉回画面；
            # timer.stop/hide 必须在 try 内，否则一旦中间任意步骤抛异常，
            # _grabbing 会卡在 True（bind_topmost_stack 永久早退）+ 面板被隐藏
            # + 心跳停摆，面板就永久无法操作。
            self._grabbing = True
            self.timer.stop()                        # 等待期间别让心跳把面板又拉回画面
            self.hide()
            if select_visible:
                self.select_panel.hide()
            if menu_visible:
                self.menu_panel.hide()
            if mini_visible:
                self.mini_timer.hide()
            if calc_visible:
                self.calc_panel.hide()
            if roster_visible:
                self.roster_panel.hide()
            if thumb_visible:
                self.thumbnail_panel.hide()
            if proj_visible:
                self._name_projection.hide()
            QApplication.processEvents()
            loop = QEventLoop()                      # 给合成器一点时间，否则可能拍到残影
            QTimer.singleShot(120, loop.quit)
            loop.exec()
            screen = self.target_screen()
            if screen is None:
                raise RuntimeError(tr("no_screen"))
            geometry = screen.geometry()
            pixmap = QPixmap()
            # Prefer grabbing the virtual desktop once, then crop to the target
            # monitor. On Windows multi-monitor setups this is more reliable than
            # screen.grabWindow offsets, which some drivers treat inconsistently.
            primary = QApplication.primaryScreen()
            if primary is not None:
                try:
                    desktop = primary.virtualGeometry()
                    full = primary.grabWindow(
                        0,
                        desktop.x(),
                        desktop.y(),
                        desktop.width(),
                        desktop.height(),
                    )
                    if not full.isNull() and full.width() > 1:
                        left = geometry.x() - desktop.x()
                        top = geometry.y() - desktop.y()
                        cropped = full.copy(left, top, geometry.width(), geometry.height())
                        if not cropped.isNull() and cropped.width() > 1:
                            pixmap = cropped
                except Exception as exc:
                    LOGGER.warning("virtual-desktop grab failed: %s", exc)
            if pixmap.isNull():
                try:
                    pixmap = screen.grabWindow(0, 0, 0, geometry.width(), geometry.height())
                except TypeError:
                    pixmap = screen.grabWindow(0)
            if pixmap.isNull() and primary is not None and primary is not screen:
                pixmap = primary.grabWindow(0)
            if pixmap.isNull():
                raise RuntimeError(tr("no_screen"))
            track_event(
                "screen_grabbed",
                screen=screen.name(),
                width=pixmap.width(),
                height=pixmap.height(),
                geometry=[geometry.x(), geometry.y(), geometry.width(), geometry.height()],
            )
            return pixmap
        finally:
            self._grabbing = False
            self.show()
            if select_visible:
                self.select_panel.show()
            if menu_visible:
                self.menu_panel.show()
            if mini_visible:
                self.mini_timer.show()
            if calc_visible:
                self.calc_panel.show()
            if roster_visible:
                self.roster_panel.show()
            if thumb_visible:
                self.thumbnail_panel.show()
                # 抓屏隐藏缩略图期间，实时定时器的一拍会看到 panel 不可见并自停；
                # 恢复面板时必须同步复活，否则之后落墨缩略图不再更新。
                self._thumbnail_live_timer.start()
            if proj_visible:
                self._name_projection.show()
                force_topmost(self._name_projection.winId())
            self.timer.start(self.HEARTBEAT_MS)
            self._bound_key = None      # 抓屏期间这些窗口被 hide/show 过，owner 需重绑
            self.heartbeat_refresh()
            # 逐个重新钉到画布之上：Qt 在 show() 时可能清掉我们设的 owner，
            # 只靠一次 heartbeat 的缓存判断会漏掉它们（见 raise_floating）。
            for restored, was_visible in (
                (self.select_panel, select_visible),
                (self.menu_panel, menu_visible),
                (self.mini_timer, mini_visible),
                (self.calc_panel, calc_visible),
                (self.roster_panel, roster_visible),
                (getattr(self, "thumbnail_panel", None), thumb_visible),
            ):
                if was_visible:
                    self.raise_floating(restored)

    def save_project(self, path=None):
        if not self.canvas:
            return False
        if path is None:
            path = self.project_path
        if not path:
            path, _ = QFileDialog.getSaveFileName(self, tr("save_project"), "", tr("project_filter_save"))
        if not path:
            return False
        try:
            self.canvas.save_current_page()
            pages = [serialize_page(page) for page in (self.canvas.pages if self.canvas.whiteboard_mode else [self.canvas.capture_page()])]
            data = make_project_data(pages=pages, current_page=self.canvas.current_page, whiteboard_mode=self.canvas.whiteboard_mode, board_style=self.canvas.board_style, app_version=APP_VERSION, metadata={"title": os.path.basename(path)})
            atomic_write_json(path, data)
            self.project_path = path
            self.project_dirty = False
            self.setWindowTitle(f"{tr('app')} - {os.path.basename(path)}")
            track_event("project_saved", path=os.path.basename(path), pages=len(pages))
            return True
        except (OSError, ValueError, TypeError) as exc:
            notify_user(self, tr("save_failed"), map_io_exception(exc, path), level="warning", exc=exc)
            return False

    def open_project_from_file_panel(self):
        self.show_only_sub(None)
        return self.open_project()

    def save_project_from_file_panel(self):
        self.show_only_sub(None)
        return self.save_project()

    def save_project_as_from_file_panel(self):
        self.show_only_sub(None)
        return self.save_project_as()

    def import_media_from_file_panel(self):
        self.show_only_sub(None)
        return self.import_media()

    def save_project_as(self):
        """Always choose a new destination; cancellation preserves the current project path."""
        path, _ = QFileDialog.getSaveFileName(
            self, tr("save_project_as"), "", tr("project_filter_save"))
        if not path:
            return False
        return self.save_project(path)

    def open_project(self):
        path, _ = QFileDialog.getOpenFileName(self, tr("open_project"), "", tr("project_filter_open"))
        if not path:
            return False
        return self.open_project_from_path(path)

    def open_project_from_path(self, path):
        """按给定路径打开 .msd/.json 项目文件（对话框与拖拽共用入口）。"""
        if not path:
            return False
        self.canvas._cancel_smart_recognition(drop_pending=True)  # 加载项目：放弃未触发的延迟识别
        try:
            ensure_file_size(path)
            with open(path, encoding="utf-8") as handle:
                data = normalize_project_data(json.load(handle), kind=PROJECT_KIND)
            pages = [deserialize_page(page) for page in data["pages"]]
            cv = self.canvas
            cv.whiteboard_mode = bool(data["whiteboard_mode"])
            cv.board_style = data["board_style"]
            cv.pages = pages if cv.whiteboard_mode else []
            cv.current_page = data["current_page"] if cv.whiteboard_mode else 0
            cv.load_page(pages[data["current_page"]])
            cv.reset_history()
            self.project_path = path
            self.project_dirty = False
            self.update_whiteboard_ui()
            self.update_history_ui()
            track_event("project_opened", path=os.path.basename(path), pages=len(pages))
            return True
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            notify_user(self, tr("open_failed"), map_io_exception(exc, path), level="warning", exc=exc)
            return False

    def collect_export_pages(self):
        """白板模式导出每一页（纯净渲染）；批注模式导出当前屏幕 + 批注。"""
        cv = self.canvas
        if cv is None:
            return []
        if getattr(cv, "whiteboard_mode", False):
            if hasattr(cv, "save_current_page"):
                cv.save_current_page()
            pages = list(getattr(cv, "pages", None) or [])
            if not pages and hasattr(cv, "capture_page"):
                pages = [cv.capture_page()]
            size = cv.size() if hasattr(cv, "size") else QSize(1920, 1080)
            if size.width() < 2 or size.height() < 2:
                screen = self.target_screen()
                geo = screen.geometry() if screen is not None else None
                size = QSize(geo.width(), geo.height()) if geo is not None else QSize(1920, 1080)
            rendered = []
            total = len(pages)
            for idx, page in enumerate(pages):
                try:
                    pix = cv.render_page_pixmap(page, size)
                except Exception as exc:
                    LOGGER.exception("render_page_pixmap failed: %s", exc)
                    continue
                if pix is not None and not pix.isNull():
                    if total > 1:
                        self._stamp_page_number(pix, idx + 1, total)
                    rendered.append(pix)
            return rendered
        return [self.grab_screen()]

    @staticmethod
    def _stamp_page_number(pix, index, total):
        """在导出图右下角叠加半透明页码标签（多页导出时才打）。"""
        if pix is None or pix.isNull():
            return
        painter = QPainter(pix)
        try:
            w, h = pix.width(), pix.height()
            font_px = max(14, int(min(w, h) * 0.022))
            font = QFont("Microsoft YaHei", font_px, QFont.Weight.Bold)
            painter.setFont(font)
            fm = painter.fontMetrics()
            text = f"{index} / {total}"
            tw = fm.horizontalAdvance(text)
            th = fm.height()
            pad_x, pad_y = int(font_px * 0.5), int(font_px * 0.35)
            box_w, box_h = tw + 2 * pad_x, th + 2 * pad_y
            margin = max(12, int(font_px * 0.6))
            box = QRectF(w - box_w - margin, h - box_h - margin, box_w, box_h)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(0, 0, 0, 140))
            painter.drawRoundedRect(box, int(font_px * 0.35), int(font_px * 0.35))
            painter.setPen(QColor(255, 255, 255, 235))
            painter.drawText(box, Qt.AlignmentFlag.AlignCenter, text)
        finally:
            painter.end()

    def target_screen(self):
        """Screen used for capture/export: canvas screen, else panel, else primary."""
        return self.active_screen(getattr(self, "canvas", None), self)

    @staticmethod
    def write_pdf(path, pixmaps):
        if not pixmaps:
            raise RuntimeError(tr("export_failed"))
        first = pixmaps[0]
        if first is None or first.isNull():
            raise RuntimeError(tr("export_failed"))
        writer = QPdfWriter(path)
        writer.setResolution(96)
        writer.setCreator("MyScreenDraw")
        page_size = QSizeF(max(1, first.width()) / 96 * 25.4, max(1, first.height()) / 96 * 25.4)
        writer.setPageSize(QPageSize(page_size, QPageSize.Unit.Millimeter))
        writer.setPageMargins(QMarginsF(0, 0, 0, 0))
        painter = QPainter(writer)
        try:
            for index, pix in enumerate(pixmaps):
                if pix is None or pix.isNull():
                    continue
                if index:
                    writer.newPage()
                painter.drawPixmap(painter.viewport(), pix, pix.rect())
        finally:
            painter.end()

    def export_pages(self, fmt):
        if not self.canvas:
            return
        self.timer.stop()
        path = ""          # 记录当前正在写的文件，供失败提示定位
        page_count = 0
        try:
            if not hasattr(self, "collect_export_pages"):
                raise AttributeError("collect_export_pages")
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            os.makedirs(EXPORT_DIR, exist_ok=True)
            fmt = str(fmt).upper()
            if fmt in ("SVG", "EPS"):
                summary, page_count = self._export_vector_pages(fmt, stamp)
                if summary is None:
                    # SVG/EPS 仅白板模式：已在下面统一弹一次提示，跳过后续通知
                    notify_user(self, tr("export_done"), tr("export_whiteboard_only"), level="information")
                    return
            else:
                pages = self.collect_export_pages()
                pages = [pix for pix in (pages or []) if pix is not None and not pix.isNull()]
                if not pages:
                    raise RuntimeError(tr("export_failed"))
                page_count = len(pages)
                if fmt == "PNG":
                    paths = []
                    for index, pix in enumerate(pages):
                        suffix = f"_p{index + 1}" if len(pages) > 1 else ""
                        path = os.path.join(EXPORT_DIR, f"Export_{stamp}{suffix}.png")
                        if not pix.save(path, "PNG"):
                            raise RuntimeError(f"{tr('export_failed')}: {path}")
                        paths.append(path)
                    summary = tr("export_png_summary").format(
                        count=len(paths),
                        path=EXPORT_DIR if len(paths) > 1 else paths[0],
                    )
                else:
                    path = os.path.join(EXPORT_DIR, f"Export_{stamp}.pdf")
                    self.write_pdf(path, pages)
                    summary = tr("export_pdf_summary").format(count=len(pages), path=path)
            track_event("export", fmt=fmt, pages=page_count, whiteboard=bool(self.canvas.whiteboard_mode))
            notify_user(self, tr("export_done"), summary, level="information")
        except (OSError, ValueError, RuntimeError) as exc:
            track_event("export_failed", fmt=fmt, error=str(exc))
            notify_user(self, tr("export_failed"), map_io_exception(exc, path), level="warning", exc=exc)
        finally:
            self.timer.start(self.HEARTBEAT_MS)
            self.heartbeat_refresh()

    def _export_vector_pages(self, fmt, stamp):
        """SVG/EPS 矢量导出：仅白板模式，逐页写出，返回 (summary, page_count)。
        非白板模式返回 (None, 0)，由调用方统一提示「仅支持白板」。"""
        cv = self.canvas
        if not cv.whiteboard_mode:
            return None, 0
        cv.save_current_page()
        page_datas = [serialize_page(page) for page in cv.pages]
        if not page_datas:
            raise RuntimeError(tr("export_failed"))
        size = cv.size()
        if size.width() < 2 or size.height() < 2:
            screen = self.target_screen()
            geo = screen.geometry() if screen is not None else None
            size = QSize(geo.width(), geo.height()) if geo is not None else QSize(1920, 1080)
        paths = []
        total = len(page_datas)
        for index, page_data in enumerate(page_datas):
            suffix = f"_p{index + 1}" if total > 1 else ""
            path = os.path.join(EXPORT_DIR, f"Export_{stamp}{suffix}.{fmt.lower()}")
            if fmt == "SVG":
                cv.write_svg_page(path, page_data, size)
            else:
                # EPS 无法内嵌 PNG，把图片解码为原始 RGB 供 eps_export 用 colorimage 运算符嵌入
                decoded = {}
                for img in page_data.get("images", []):
                    pixels = decode_image_pixels(img.get("data"))
                    if pixels is not None:
                        decoded[img.get("id")] = pixels
                eps_export.write_eps(path, page_data, size.width(), size.height(),
                                     board_style=cv.board_style, decoded_images=decoded)
            paths.append(path)
        summary = (tr("export_svg_summary") if fmt == "SVG"
                   else tr("export_eps_summary")).format(
            count=len(paths), path=EXPORT_DIR if len(paths) > 1 else paths[0])
        return summary, len(paths)

    # --- 计算器 ---
    def _make_tool_window(self, title_text):
        win = QWidget()
        win.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        win.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        win.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        win.setStyleSheet(self.styleSheet())
        outer = QVBoxLayout(win)
        outer.setContentsMargins(0, 0, 0, 0)
        frame = QFrame(); frame.setObjectName("MainFrame")
        outer.addWidget(frame)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(4)
        title_row = QHBoxLayout()
        title = QLabel(title_text)
        title_row.addWidget(title, 1)
        close_btn = QPushButton("×"); close_btn.setObjectName("SquareBtn")
        close_btn.clicked.connect(win.hide)
        title_row.addWidget(close_btn)
        layout.addLayout(title_row)
        win._drag_offset = None
        def press(e, w=win):
            if e.button() == Qt.MouseButton.LeftButton:
                w._drag_offset = e.globalPosition().toPoint() - w.pos()
        def move(e, w=win):
            if w._drag_offset is not None and (e.buttons() & Qt.MouseButton.LeftButton):
                w.move(e.globalPosition().toPoint() - w._drag_offset)
        def release(e, w=win):
            w._drag_offset = None
        win.mousePressEvent = press
        win.mouseMoveEvent = move
        win.mouseReleaseEvent = release
        return win, layout

    def open_calculator(self):
        self.show_only_sub(None)
        if self.calc_panel is None:
            self.calc_panel, layout = self._make_tool_window(tr("calculator"))
            self._calc_expr = "0"
            self._calc_just_evaluated = False
            self._calc_display = QLabel("0")
            self._calc_display.setObjectName("TimerDisplay")
            self._calc_display.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._calc_display.setMinimumWidth(180)
            layout.addWidget(self._calc_display)
            keys = [
                ("C", "C"), ("⌫", "B"), ("%", "%"), ("÷", "/"),
                ("7", "7"), ("8", "8"), ("9", "9"), ("×", "*"),
                ("4", "4"), ("5", "5"), ("6", "6"), ("−", "-"),
                ("1", "1"), ("2", "2"), ("3", "3"), ("+", "+"),
                ("±", "N"), ("0", "0"), (".", "."), ("=", "="),
            ]
            grid = QGridLayout(); grid.setSpacing(3)
            for i, (label, code) in enumerate(keys):
                btn = QPushButton(label)
                btn.setFixedSize(52, TOUCH_MIN_BUTTON)
                btn.clicked.connect(lambda _=False, c=code: self._calc_input(c))
                grid.addWidget(btn, i // 4, i % 4)
            layout.addLayout(grid)
            copy_btn = QPushButton(tr("copy_result"))
            copy_btn.clicked.connect(self._calc_copy)
            layout.addWidget(copy_btn)
        self.calc_panel.adjustSize()
        screen = self.screen_geometry(self) or QApplication.primaryScreen().availableGeometry()
        self.calc_panel.move(screen.center().x() - self.calc_panel.width() // 2,
                             screen.center().y() - self.calc_panel.height() // 2)
        self.calc_panel.show()
        self.raise_floating(self.calc_panel)
        self.heartbeat_refresh()
        track_event("calculator_opened")

    def _calc_input(self, code):
        exp = self._calc_expr
        if code == "C":
            exp = "0"
            self._calc_just_evaluated = False
        elif code == "B":
            # 退格遇到错误/溢出占位串直接清零，否则会留下半个词（如「错」/「溢」）。
            if exp in (tr("calc_state_error"), tr("calc_state_overflow")):
                exp = "0"
            else:
                exp = exp[:-1] if len(exp) > 1 else "0"
            self._calc_just_evaluated = False
        elif code == "N":
            # 按下「±」：若刚按下「=」得到结果，应当对结果取负，而不是把结果清成 0 再试图取负。
            # 旧逻辑里 `if just_evaluated: exp = "0"` 是误抄自数字输入分支的复位，会让
            # 3+2= 后按 ± 显示 0 而不是 -5。这里去掉那条复位，直接对当前显示取反。
            if exp.startswith("-"):
                exp = exp[1:] or "0"
            else:
                exp = "-" + exp if exp != "0" else exp
            self._calc_just_evaluated = False
        elif code == "=":
            exp = self._calc_eval(exp)
            self._calc_just_evaluated = True
        elif code == "%":
            try:
                exp = self._calc_format(float(self._calc_eval(exp)) / 100.0)
            except Exception:
                exp = tr("calc_state_error")
            self._calc_just_evaluated = True
        elif code in ("+", "-", "*", "/"):
            if exp in (tr("calc_state_error"), tr("calc_state_overflow")):
                exp = "0"
            exp += code
            self._calc_just_evaluated = False
        else:
            if self._calc_just_evaluated or exp in ("0", tr("calc_state_error"), tr("calc_state_overflow")):
                exp = code
            else:
                exp += code
            self._calc_just_evaluated = False
        self._calc_expr = exp
        if self._calc_display:
            self._calc_display.setText(exp)

    def _calc_eval(self, expr):
        try:
            return self._calc_format(safe_calculate(expr))
        except CalculatorError:
            return tr("calc_state_error")
        except Exception:
            LOGGER.exception("计算器执行失败")
            return tr("calc_state_error")

    @staticmethod
    def _calc_format(val):
        try:
            if isinstance(val, float) and (math.isinf(val) or math.isnan(val)):
                return tr("calc_state_overflow")
            if isinstance(val, float) and val.is_integer():
                return str(int(val))
            text = f"{val:.10g}"
            return text
        except Exception:
            return tr("calc_state_error")

    def _calc_copy(self):
        QGuiApplication.clipboard().setText(str(self._calc_expr))
        track_event("calculator_copied", value=str(self._calc_expr))

    # --- 随机点名 ---
    def load_roster(self):
        self.roster = []
        self.roster_drawn = set()
        try:
            if os.path.exists(ROSTER_FILE):
                with open(ROSTER_FILE, encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    names = data.get("names", [])
                    drawn = data.get("drawn", [])
                elif isinstance(data, list):
                    names, drawn = data, []
                else:
                    names, drawn = [], []
                self.roster = [str(n).strip() for n in names if str(n).strip()]
                self.roster_drawn = set(str(n) for n in drawn if str(n) in self.roster)
        except Exception as e:
            track_event("roster_load_failed", error=str(e))

    def save_roster(self):
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            payload = {"names": self.roster, "drawn": sorted(self.roster_drawn)}
            tmp = ROSTER_FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            os.replace(tmp, ROSTER_FILE)
        except Exception as e:
            track_event("roster_save_failed", error=str(e))

    def open_roster_panel(self):
        self.show_only_sub(None)
        if self.roster_panel is None:
            self.roster_panel, layout = self._make_tool_window(tr("roster"))
            self.roster_result = QLabel(tr("roster_start_hint"))
            self.roster_result.setObjectName("TimerDisplay")
            self.roster_result.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.roster_result.setMinimumWidth(200)
            layout.addWidget(self.roster_result)
            self.roster_stats = QLabel(trf("roster_stats", total=0, drawn=0))
            layout.addWidget(self.roster_stats)
            self.roster_list = QListWidget()
            self.roster_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
            self.roster_list.setMinimumHeight(140)
            layout.addWidget(self.roster_list)
            row1 = QHBoxLayout()
            btn_draw = QPushButton(tr("roster_draw"))
            btn_draw.clicked.connect(self.draw_random_name)
            row1.addWidget(btn_draw)
            btn_reset = QPushButton(tr("roster_reset"))
            btn_reset.clicked.connect(self.reset_drawn_names)
            row1.addWidget(btn_reset)
            layout.addLayout(row1)
            row2 = QHBoxLayout()
            btn_import = QPushButton(tr("roster_import"))
            btn_import.clicked.connect(self.import_roster)
            row2.addWidget(btn_import)
            btn_add = QPushButton(tr("roster_add"))
            btn_add.clicked.connect(self.add_roster_name)
            row2.addWidget(btn_add)
            btn_del = QPushButton(tr("roster_delete"))
            btn_del.clicked.connect(self.delete_roster_names)
            row2.addWidget(btn_del)
            layout.addLayout(row2)
            hint = QLabel(tr("roster_file_hint"))
            layout.addWidget(hint)
        self.refresh_roster_ui()
        self.roster_panel.adjustSize()
        x, y = self._floating_anchor(self.roster_panel.width(), self.roster_panel.height(), gap=20)
        self.roster_panel.move(x, y)
        self.roster_panel.show()
        self.raise_floating(self.roster_panel)
        self.heartbeat_refresh()
        track_event("roster_opened", count=len(self.roster))

    def refresh_roster_ui(self):
        if not hasattr(self, "roster_list"):
            return
        self.roster_list.clear()
        for name in self.roster:
            mark = "✓ " if name in self.roster_drawn else ""
            self.roster_list.addItem(f"{mark}{name}")
        self.roster_stats.setText(trf("roster_stats", total=len(self.roster), drawn=len(self.roster_drawn)))

    def draw_random_name(self):
        pool = [n for n in self.roster if n not in self.roster_drawn]
        if not pool:
            if not self.roster:
                self.roster_result.setText(tr("roster_empty"))
                return
            # 全员已点：自动重置再抽
            self.roster_drawn.clear()
            pool = list(self.roster)
        name = random.choice(pool)
        self.roster_drawn.add(name)
        self.roster_result.setText(name)
        self.save_roster()
        self.refresh_roster_ui()
        self._show_name_projection(name)
        track_event("roster_draw", name=name, left=len(self.roster) - len(self.roster_drawn))

    # --- 抽中结果大字投影 / 临时全屏展示 ---
    NAME_PROJECTION_MS = 3000      # 投影自动消失时间
    _name_projection = None
    _name_projection_label = None
    _name_projection_timer = None

    def _show_name_projection(self, name):
        """把抽中的名字以大字全屏投影展示片刻（自动消失；点击/按键可立即关闭）。"""
        if self._name_projection is None:
            win = QWidget()
            win.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
            win.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
            win.setStyleSheet("background-color: #111;")
            outer = QVBoxLayout(win)
            outer.setContentsMargins(0, 0, 0, 0)
            outer.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label = QLabel(name)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setStyleSheet("color: #ffe600; background: transparent;")
            # 字号按屏幕尺寸自适应：取屏幕短边的 1/6，约相当于整屏显示 1 个词的名字
            screen = self.screen_geometry(self) or QApplication.primaryScreen().availableGeometry()
            font_px = max(80, int(min(screen.width(), screen.height()) / 6))
            label.setFont(QFont("Microsoft YaHei", font_px, QFont.Weight.Black))
            outer.addWidget(label)
            # 关闭桩：任意鼠标按下与按键都立即关闭投影
            win.mousePressEvent = lambda _e: self._close_name_projection()
            win.keyPressEvent = lambda _e: self._close_name_projection()
            win.setWindowState(Qt.WindowState.WindowFullScreen)
            win.showFullScreen()
            self._name_projection = win
            self._name_projection_label = label
            if self._name_projection_timer is None:
                self._name_projection_timer = QTimer(self)
                self._name_projection_timer.setSingleShot(True)
                self._name_projection_timer.timeout.connect(self._close_name_projection)
        else:
            self._name_projection_label.setText(name)
        # 重新启动自动关闭计时
        self._name_projection.show()
        self._name_projection.raise_()
        force_topmost(self._name_projection.winId())
        self._name_projection.activateWindow()
        self._name_projection_timer.start(self.NAME_PROJECTION_MS)
        track_event("name_projection_shown", name=name)

    def _close_name_projection(self):
        if self._name_projection_timer is not None:
            self._name_projection_timer.stop()
        if self._name_projection is not None and self._name_projection.isVisible():
            self._name_projection.hide()
        track_event("name_projection_closed")

    def reset_drawn_names(self):
        self.roster_drawn.clear()
        self.save_roster()
        self.refresh_roster_ui()
        if hasattr(self, "roster_result"):
            self.roster_result.setText(tr("roster_reset_done"))
        track_event("roster_reset")

    def add_roster_name(self):
        self.timer.stop()
        try:
            text, ok = QInputDialog.getText(self, tr("roster_add_title"), tr("roster_add_label"))
        finally:
            self.timer.start(self.HEARTBEAT_MS)
        if not ok:
            return
        name = text.strip()
        if not name:
            return
        if name not in self.roster:
            self.roster.append(name)
            self.save_roster()
            self.refresh_roster_ui()

    def delete_roster_names(self):
        if not hasattr(self, "roster_list"):
            return
        rows = sorted({i.row() for i in self.roster_list.selectedIndexes()}, reverse=True)
        if not rows:
            return
        for row in rows:
            if 0 <= row < len(self.roster):
                name = self.roster.pop(row)
                self.roster_drawn.discard(name)
        self.save_roster()
        self.refresh_roster_ui()

    def import_roster(self):
        self.timer.stop()
        try:
            path, _ = QFileDialog.getOpenFileName(
                self, tr("roster_import_title"), "",
                tr("roster_filter")
            )
        finally:
            self.timer.start(self.HEARTBEAT_MS)
        if not path:
            return
        names = []
        try:
            if os.path.getsize(path) > self.MAX_IMPORT_BYTES:
                raise ValueError(trf("err_file_too_large", path=path, limit="64 MiB"))
            if path.lower().endswith(".csv"):
                with open(path, encoding="utf-8-sig", newline="") as f:
                    reader = csv.reader(f)
                    for row in reader:
                        for cell in row:
                            cell = cell.strip()
                            if cell and cell.lower() not in ("姓名", "name", "名字"):
                                names.append(cell)
            else:
                with open(path, encoding="utf-8-sig") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        # 兼容逗号/顿号/空白分隔
                        parts = [p.strip() for p in line.replace("、", ",").replace("，", ",").replace("\t", ",").split(",")]
                        names.extend([p for p in parts if p])
        except (OSError, ValueError, csv.Error) as e:
            notify_user(self, tr("import_failed"), map_io_exception(e, path), level="warning", exc=e)
            return
        if len(names) > self.MAX_ROSTER_NAMES:
            names = names[:self.MAX_ROSTER_NAMES]
            notify_user(self, tr("import_done"),
                        trf("roster_imported", count=len(names)), level="information")
        # 去重保序
        seen = set()
        merged = []
        for n in self.roster + names:
            if n not in seen:
                seen.add(n)
                merged.append(n)
        self.roster = merged
        self.roster_drawn &= set(self.roster)
        self.save_roster()
        self.refresh_roster_ui()
        if hasattr(self, "roster_result"):
            self.roster_result.setText(trf("roster_imported", count=len(names)))
        track_event("roster_imported", added=len(names), total=len(self.roster))

    # --- 图片 / PDF 导入（图片以 PNG→base64 内嵌进项目文件，.msd 自包含） ---
    MAX_IMPORT_BYTES = 64 * 1024 * 1024   # 单文件上限，与项目文件上限一致
    MAX_IMPORT_PIXELS = 2560              # 图片最长边上限，超限在解码前等比缩图
    MAX_IMAGE_PIXELS = 8_000_000          # 单张解码像素硬上限（约 32 MiB RGBA）
    MAX_PDF_TOTAL_PIXELS = 32_000_000     # 当前页图片总驻留像素上限（约 128 MiB RGBA）
    MAX_PDF_PAGES = 50                    # PDF 最多导入前 N 页
    PDF_EXPORT_DPI = 120                  # PDF 页面渲染分辨率（dpi）
    MAX_ROSTER_NAMES = 5000               # 点名名单行数上限

    def import_media(self):
        self.timer.stop()
        try:
            options = QFileDialog.Option.DontUseNativeDialog
            path, _ = QFileDialog.getOpenFileName(
                self, tr("import_media"), "", tr("import_media_filter"), options=options)
            if not path:
                return
            self.canvas._cancel_smart_recognition(drop_pending=True)  # 导入前放弃未触发的延迟识别
            size = os.path.getsize(path)
            if size > self.MAX_IMPORT_BYTES:
                raise ValueError(trf("err_file_too_large", path=path, limit="64 MiB"))
            if path.lower().endswith(".pdf"):
                count = self.import_pdf(path)
                if count:
                    track_event("pdf_imported", pages=count, file=os.path.basename(path))
                    notify_user(self, tr("import_done"),
                                trf("import_pdf_summary", count=count, name=os.path.basename(path)),
                                level="information")
            else:
                item = self.import_image_file(path)
                if item is None:
                    notify_user(self, tr("import_failed"),
                                trf("err_unsupported_image", path=path), level="warning")
                    return
                track_event("image_imported", file=os.path.basename(path))
                notify_user(self, tr("import_done"),
                            trf("import_image_summary", name=os.path.basename(path)),
                            level="information")
        except (OSError, ValueError, RuntimeError, MemoryError) as exc:
            notify_user(self, tr("import_failed"), map_io_exception(exc, locals().get("path", "")),
                        level="warning", exc=exc)
        finally:
            self.timer.start(self.HEARTBEAT_MS)
            self.heartbeat_refresh()

    def import_image_file(self, path):
        """有界解码一张图片并插入画布；返回新 image item 或 None。"""
        reader = QImageReader(path)
        reader.setAutoTransform(True)     # 尊重 EXIF 旋转方向
        source_size = reader.size()
        if not source_size.isValid():
            return None
        target = _bounded_image_size(
            source_size.width(), source_size.height(),
            self.MAX_IMPORT_PIXELS, self.MAX_IMAGE_PIXELS,
        )
        if target.isEmpty():
            return None
        if target != source_size:
            # QImageReader 在解码器内降采样，避免先分配巨幅原图再缩小导致主线程假死/OOM。
            reader.setScaledSize(target)
        image = reader.read()
        if image.isNull():
            return None
        target = _bounded_image_size(
            image.width(), image.height(), self.MAX_IMPORT_PIXELS, self.MAX_IMAGE_PIXELS,
        )
        if target.isEmpty():
            return None
        if image.size() != target:
            # 某些插件会忽略 setScaledSize；解码后再守一次边界，绝不把超限图放进撤销栈。
            image = image.scaled(target, Qt.AspectRatioMode.KeepAspectRatio,
                                 Qt.TransformationMode.SmoothTransformation)
        return self.insert_image_pixmap(QPixmap.fromImage(image))

    def insert_image_pixmap(self, pixmap, pos=None, *, record_undo=True, finalize=True):
        """插入一张位图；批量调用可延迟撤销、页面保存和 UI 刷新。"""
        cv = self.canvas
        if cv is None or pixmap is None or pixmap.isNull():
            return None
        if len(cv.image_items) >= MAX_IMAGES_PER_PAGE:
            raise ValueError(tr("import_failed"))
        incoming_pixels = pixmap.width() * pixmap.height()
        resident_pixels = sum(
            max(0, item["pixmap"].width() * item["pixmap"].height())
            for item in cv.image_items
            if item.get("pixmap") is not None and not item["pixmap"].isNull()
        )
        if incoming_pixels <= 0 or resident_pixels + incoming_pixels > self.MAX_PDF_TOTAL_PIXELS:
            raise ValueError(tr("import_failed"))
        if pos is None:
            pos = QPointF(cv.width() / 2.0, cv.height() / 2.0)
        item = {
            "id": uuid.uuid4(),
            "pos": QPointF(pos),
            "size": QSizeF(float(pixmap.width()), float(pixmap.height())),
            "rotation": 0.0,
            "pixmap": pixmap,
        }
        if record_undo:
            cv.push_undo()
        cv.image_items.append(item)
        cv.selected_ids = {item["id"]}
        if finalize:
            if cv.whiteboard_mode:
                cv.save_current_page()
            self.sync_selection_controls()
            self.position_selection_panel(cv.selection_bounds())
            cv.mark_content_changed()
        return item

    def import_pdf(self, path):
        """逐页有界渲染并批量插入 PDF，不把整本文件同时驻留在内存。"""
        try:
            from PyQt6.QtPdf import QPdfDocument
        except ImportError:
            notify_user(self, tr("import_failed"), tr("import_pdf_unsupported"), level="warning")
            return 0
        document = QPdfDocument(None)
        error = document.load(path)
        if error != QPdfDocument.Error.None_:
            try:
                document.close()
            except (AttributeError, RuntimeError):
                pass
            raise ValueError(str(error) or tr("import_failed"))
        total = document.pageCount()
        pages = min(total, self.MAX_PDF_PAGES, MAX_IMAGES_PER_PAGE - len(self.canvas.image_items))
        if total > self.MAX_PDF_PAGES:
            notify_user(self, tr("import_done"),
                        trf("import_pdf_pages_limited", count=self.MAX_PDF_PAGES), level="information")
        if pages <= 0:
            try:
                document.close()
            except (AttributeError, RuntimeError):
                pass
            return 0

        cv = self.canvas
        before = cv.capture_page()
        old_selected = set(cv.selected_ids)
        old_undo_depth = len(cv.undo_stack)
        old_redo_stack = list(cv.redo_stack)
        old_undo_key = cv.last_undo_key
        autosave_timer = getattr(self, "autosave_timer", None)
        was_autosaving = bool(autosave_timer and autosave_timer.isActive())
        if was_autosaving:
            autosave_timer.stop()
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        inserted = 0
        batch_started = False
        resident_pixels = sum(
            max(0, item["pixmap"].width() * item["pixmap"].height())
            for item in cv.image_items if item.get("pixmap") is not None and not item["pixmap"].isNull()
        )
        try:
            for index in range(pages):
                point_size = document.pagePointSize(index)
                if point_size.width() <= 0 or point_size.height() <= 0:
                    continue
                scale = self.PDF_EXPORT_DPI / 72.0
                source_width = max(1, int(point_size.width() * scale))
                source_height = max(1, int(point_size.height() * scale))
                remaining_pixels = self.MAX_PDF_TOTAL_PIXELS - resident_pixels
                target = _bounded_image_size(
                    source_width, source_height, self.MAX_IMPORT_PIXELS,
                    remaining_pixels,
                )
                if target.isEmpty():
                    break
                image = document.render(index, target)
                if image.isNull():
                    continue
                pixmap = QPixmap.fromImage(image)
                if pixmap.isNull():
                    continue
                actual_pixels = pixmap.width() * pixmap.height()
                if actual_pixels <= 0 or actual_pixels > remaining_pixels:
                    continue
                if not batch_started:
                    # `before` 已在批次开始时捕获；直接提交它，避免 push_undo()
                    # 对含大量图片的当前页再做一次相同的完整克隆。
                    cv.commit_undo(before)
                    batch_started = True
                item = self.insert_image_pixmap(
                    pixmap, record_undo=False, finalize=False)
                if item is None:
                    continue
                inserted += 1
                resident_pixels += actual_pixels
                # Let Qt repaint the wait cursor and canvas without admitting a
                # second user action into the half-built batch.
                QApplication.processEvents(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)
            if inserted:
                if cv.whiteboard_mode:
                    cv.save_current_page()
                self.sync_selection_controls()
                self.position_selection_panel(cv.selection_bounds())
                cv.mark_content_changed()
            elif batch_started:
                cv.undo_stack = cv.undo_stack[:old_undo_depth]
                cv.redo_stack = old_redo_stack
                cv.last_undo_key = old_undo_key
            return inserted
        except Exception:
            if batch_started:
                cv.load_page(before)
                cv.selected_ids = old_selected
                if cv.whiteboard_mode:
                    cv.save_current_page()
                cv.undo_stack = cv.undo_stack[:old_undo_depth]
                cv.redo_stack = old_redo_stack
                cv.last_undo_key = old_undo_key
                self.sync_selection_controls()
                self.position_selection_panel(cv.selection_bounds())
                cv.panel.update_history_ui() if cv.panel else None
            raise
        finally:
            try:
                document.close()
            except (AttributeError, RuntimeError):
                pass
            QApplication.restoreOverrideCursor()
            if was_autosaving:
                autosave_timer.start(AUTOSAVE_INTERVAL * 1000)

if __name__ == "__main__":
    ensure_directories()
    setup_logging()
    LOGGER.info("MyScreenDraw %s starting (lang=%s)", APP_VERSION, CURRENT)

    app = QApplication(sys.argv)
    # The build pipeline uses this bounded path to verify that a frozen bundle can
    # import Qt, create its runtime directories, and exit without opening windows.
    if "--smoke" in sys.argv[1:]:
        LOGGER.info("MyScreenDraw %s smoke check passed", APP_VERSION)
        sys.exit(0)
    app.setApplicationName(tr("app"))
    app.setOrganizationName("MyScreenDraw")
    install_qt_translations(app)
    # 窗口创建是启动时唯一的「无界面可依赖」步骤：失败就弹友好错误并退出，
    # 不裸崩。Qt 虚函数/构造异常在 PyQt6 下会终结进程，必须在这里拦下。
    try:
        pnl = ControlPanel()
        cvs = DrawingCanvas(pnl)
        pnl.canvas = cvs
    except Exception as exc:
        LOGGER.exception("窗口创建失败")
        QMessageBox.critical(None, tr("app"), trf("err_window_create", detail=str(exc)))
        sys.exit(1)
    if "--smoke-ui" in sys.argv[1:]:
        # The release pipeline uses this bounded path to construct both production
        # windows without entering the event loop or showing recovery dialogs.
        pnl.apply_theme()
        pnl.load_settings()
        if getattr(pnl, "listener", None) is not None:
            pnl.listener.stop()
        cvs.close()
        pnl.close()
        LOGGER.info("MyScreenDraw %s UI smoke check passed", APP_VERSION)
        sys.exit(0)
    pnl.apply_theme()
    pnl.load_settings()
    app.aboutToQuit.connect(pnl.save_settings)
    pnl.update_whiteboard_ui()
    pnl.update_history_ui()
    # Prefer the screen the panel will live on; fall back to primary.
    boot_screen = pnl.screen() or QApplication.primaryScreen()
    screen = boot_screen.geometry() if boot_screen else QApplication.primaryScreen().geometry()
    pnl.show()
    if not pnl.restore_position():
        pnl.move(0, max(8, (screen.height() - pnl.frameGeometry().height()) // 2))
    # Canvas showFullScreen may finish after panel construction; rebind once the
    # HWNDs are live, then again after the first event-loop tick.
    pnl.bind_topmost_stack()
    QTimer.singleShot(0, pnl.bind_topmost_stack)
    QTimer.singleShot(200, pnl.bind_topmost_stack)
    pnl.save_settings()
    pnl.offer_autosave_restore()
    sys.exit(app.exec())
