"""★ FishGeometry —— 双端共享的"画鱼规范"（ARCHITECTURE §7.4，需求 Q5：零 PNG）。

🔴 禁止 `from __future__ import annotations`（E6，全项目统一）。

本文件分成泾渭分明的两半：

* **纯函数区**（:func:`geometry` 及其下属 `_part_*`）——
  不 import tkinter、不碰颜色字符串以外的平台类型、不读全局状态。
  输入 `shape` 字典 + 阶段 + 相位，输出一串与平台无关的 :class:`Prim`。
  **T05 的 C++ `fish_paint.cpp` 必须逐条对齐这一区**，这是双端视觉同源的唯一依据。
* **Tk 适配区**（:class:`FishPainter`）——把 Prim 翻译成 canvas item。

坐标系约定（C++ 端照抄）
------------------------
* 原点 = 鱼的中心；**+x 指向鱼头朝向**（永远画成朝右，朝左由渲染层水平镜像）。
* 单位 = 归一化体长。`L = shape.length * base_len * stage_scale[stage]`，
  其中 `base_len` 由调用方给（Py 端传像素，XJ 端传像素，规范本身与单位无关）。
* `rx = L / 2`，`ry = rx * height_ratio`。
* `phase ∈ [0, 1)` 是摆尾相位，尾尖 y 偏移 = `sin(2π·phase) * rx * TAIL_SWING`。

图元类型（C++ 端映射见每项注释）
--------------------------------
=============== ================================ ==========================
kind            Py 端                            XJ380 端
=============== ================================ ==========================
`ellipse`       `create_oval`                    `fill_ellipse`
`ellipse_half`  `create_arc(style=CHORD)`        `fill_ellipse` + 裁剪
`polygon`       `create_polygon`                 `fill_tri` 扇形分解
`circle`        `create_oval`                    `fill_circle`
`outline`       `create_oval(outline=…)`         加粗描边（不做外晕）
=============== ================================ ==========================
"""

import math

# ── 图元类型常量 ──
KIND_ELLIPSE = "ellipse"
KIND_ELLIPSE_HALF = "ellipse_half"
KIND_POLYGON = "polygon"
KIND_CIRCLE = "circle"
KIND_OUTLINE = "outline"

# ── 语义角色（决定用哪个颜色，渲染层查 Appearance）──
ROLE_BODY = "body"
ROLE_BELLY = "belly"
ROLE_FIN = "fin"
ROLE_ACCENT = "accent"
ROLE_EYE = "eye"
ROLE_EYE_HL = "eye_hl"
ROLE_OUTLINE = "outline"

TAIL_SWING = 0.25
"""尾尖摆动幅度（相对 rx）。ARCHITECTURE §7.4：`sin(2π·phase) * rx * 0.25`。"""

_DEFAULT_STAGE_SCALE = {"fry": 0.45, "juvenile": 0.7, "adult": 1.0, "mature": 1.1}
"""阶段缩放兜底。正常路径由 `balance.growth.stage_scale` 传入，这里只防 None。"""

_EYE_X = 0.55
_EYE_Y = -0.25
_EYE_R = 0.22
_EYE_HL_R = 0.08
_BELLY_RY = 0.55
_BELLY_CY = 0.35
_DORSAL_H = 0.55
_STRIPE_COUNT = 4
_SPOT_COUNT = 5


class Prim(object):
    """一个平台无关的绘制图元。

    :ivar kind: 见 `KIND_*`
    :ivar role: 见 `ROLE_*`，渲染层据此取色
    :ivar cx, cy: 中心（ellipse / circle / ellipse_half / outline 用）
    :ivar rx, ry: 半轴
    :ivar points: [(x, y), ...]（polygon 用）
    :ivar width: 线宽（outline 用）
    """

    __slots__ = ("kind", "role", "cx", "cy", "rx", "ry", "points", "width")

    def __init__(self, kind, role, cx=0.0, cy=0.0, rx=0.0, ry=0.0,
                 points=None, width=0.0):
        self.kind = kind
        self.role = role
        self.cx = float(cx)
        self.cy = float(cy)
        self.rx = float(rx)
        self.ry = float(ry)
        self.points = list(points or [])
        self.width = float(width)

    def __repr__(self):
        if self.points:
            return "<Prim %s/%s pts=%d>" % (self.kind, self.role, len(self.points))
        return "<Prim %s/%s c=(%.3f,%.3f) r=(%.3f,%.3f)>" % (
            self.kind, self.role, self.cx, self.cy, self.rx, self.ry)


# ══════════════════════════════════════════════════════════════
#  纯函数区 —— ★ C++ 端逐条对齐这一段
# ══════════════════════════════════════════════════════════════

def body_size(shape, stage, base_len=1.0, stage_scale=None):
    """算出鱼的半长 rx 与半高 ry。

    :param shape: fish_data.json 的 `shape` 段（length / height_ratio / tail）
    :param stage: fry / juvenile / adult / mature
    :param base_len: 基准体长（Py 端= 像素）
    :param stage_scale: 阶段缩放表，None 用内置兜底
    :returns: (rx, ry)
    """
    table = stage_scale or _DEFAULT_STAGE_SCALE
    try:
        length = float((shape or {}).get("length", 1.0) or 1.0)
    except (TypeError, ValueError):
        length = 1.0
    try:
        ratio = float((shape or {}).get("height_ratio", 0.4) or 0.4)
    except (TypeError, ValueError):
        ratio = 0.4
    try:
        sc = float(table.get(str(stage), 1.0) or 1.0)
    except (TypeError, ValueError, AttributeError):
        sc = 1.0
    total = length * float(base_len) * sc
    rx = total * 0.5
    return rx, rx * ratio


def _tail_tip_dy(rx, phase):
    """尾尖的摆动偏移。双端必须用同一条公式，否则摆尾节奏会不一致。"""
    return math.sin(2.0 * math.pi * float(phase)) * rx * TAIL_SWING


def _part_body(rx, ry):
    """身体：一个整椭圆。"""
    return Prim(KIND_ELLIPSE, ROLE_BODY, cx=0.0, cy=0.0, rx=rx, ry=ry)


def _part_belly(rx, ry):
    """腹部：下半椭圆，`ry*0.55`、`cy=+ry*0.35`。"""
    return Prim(KIND_ELLIPSE_HALF, ROLE_BELLY,
                cx=0.0, cy=ry * _BELLY_CY, rx=rx * 0.92, ry=ry * _BELLY_RY)


def _part_tail(rx, ry, tail, phase):
    """尾鳍：按 `tail` 分四型。根部锚在 `(-rx, 0)`，尾尖带摆动偏移。

    :returns: Prim 列表（fork 是双三角，所以可能多于一个）
    """
    dy = _tail_tip_dy(rx, phase)
    root_x = -rx * 0.92          # 稍微插进身体，避免出现缝隙
    span = rx * 0.55             # 尾鳍长度
    tip_x = -rx - span
    h = ry * 1.35                # 尾鳍张开高度

    kind = str(tail or "fork").lower()

    if kind == "fork":
        # 双三角：上下各一片，中间凹陷 —— 斑马鱼/霓虹灯这类速游鱼
        upper = [(root_x, 0.0), (tip_x, -h + dy), (-rx * 0.55, -ry * 0.15)]
        lower = [(root_x, 0.0), (tip_x, h + dy), (-rx * 0.55, ry * 0.15)]
        return [Prim(KIND_POLYGON, ROLE_FIN, points=upper),
                Prim(KIND_POLYGON, ROLE_FIN, points=lower)]

    if kind == "fan":
        # 五点扇：孔雀鱼那种展开的大尾
        pts = [(root_x, 0.0),
               (tip_x, -h * 0.95 + dy),
               (tip_x - span * 0.18, dy * 0.6),
               (tip_x, h * 0.95 + dy),
               (-rx * 0.6, 0.0)]
        return [Prim(KIND_POLYGON, ROLE_FIN, points=pts)]

    if kind == "round":
        # 半椭圆：金鱼那种圆尾。用折线逼近，保证 C++ 端也能用同样的点数复现
        pts = [(root_x, 0.0)]
        steps = 8
        for i in range(steps + 1):
            a = -math.pi * 0.5 + math.pi * (float(i) / steps)
            pts.append((tip_x + span * (1.0 - math.cos(a)) * 0.35,
                        math.sin(a) * h * 0.9 + dy))
        return [Prim(KIND_POLYGON, ROLE_FIN, points=pts)]

    # long：四点飘带（斗鱼/龙睛那种长尾），摆动更夸张
    long_span = span * 1.8
    pts = [(root_x, 0.0),
           (-rx - long_span * 0.5, -h * 0.7 + dy * 1.4),
           (-rx - long_span, dy * 2.0),
           (-rx - long_span * 0.5, h * 0.7 + dy * 1.4)]
    return [Prim(KIND_POLYGON, ROLE_FIN, points=pts)]


def _part_dorsal(rx, ry, phase):
    """背鳍：三点三角，锚在 `(0, -ry)`，随相位轻微摆动。"""
    sway = math.sin(2.0 * math.pi * float(phase)) * rx * 0.04
    pts = [(rx * 0.20, -ry * 0.95),
           (-rx * 0.10 + sway, -ry * (1.0 + _DORSAL_H)),
           (-rx * 0.45, -ry * 0.90)]
    return Prim(KIND_POLYGON, ROLE_FIN, points=pts)


def _part_pelvic(rx, ry, phase):
    """腹鳍：身体下方的小三角，让鱼看起来不那么"光秃"。"""
    sway = math.sin(2.0 * math.pi * float(phase) + math.pi * 0.5) * ry * 0.10
    pts = [(rx * 0.10, ry * 0.72),
           (-rx * 0.10, ry * (1.05 + 0.10) + sway),
           (-rx * 0.30, ry * 0.70)]
    return Prim(KIND_POLYGON, ROLE_FIN, points=pts)


def _part_eyes(rx, ry):
    """眼睛 + 高光。位置/半径严格照 §7.4 部件表。"""
    ex = rx * _EYE_X
    ey = ry * _EYE_Y
    er = ry * _EYE_R
    return [Prim(KIND_CIRCLE, ROLE_EYE, cx=ex, cy=ey, rx=er, ry=er),
            Prim(KIND_CIRCLE, ROLE_EYE_HL,
                 cx=ex + er * 0.35, cy=ey - er * 0.35,
                 rx=ry * _EYE_HL_R, ry=ry * _EYE_HL_R)]


def _part_pattern(rx, ry, pattern):
    """花纹：R3+ 才有。`stripes` 竖条 / `spots` 圆点。"""
    out = []
    kind = str(pattern or "none").lower()
    if kind == "stripes":
        for i in range(_STRIPE_COUNT):
            # 沿体长均匀分布，避开头部（眼睛区）和尾柄
            t = (i + 1.0) / (_STRIPE_COUNT + 1.0)
            cx = rx * (0.45 - 1.30 * t)
            half_h = ry * math.sqrt(max(0.0, 1.0 - (cx / rx) ** 2)) * 0.92
            w = rx * 0.055
            out.append(Prim(KIND_POLYGON, ROLE_ACCENT, points=[
                (cx - w, -half_h), (cx + w, -half_h),
                (cx + w, half_h), (cx - w, half_h)]))
    elif kind == "spots":
        for i in range(_SPOT_COUNT):
            t = (i + 1.0) / (_SPOT_COUNT + 1.0)
            cx = rx * (0.40 - 1.20 * t)
            cy = ry * (0.30 if i % 2 else -0.28)
            r = ry * 0.20
            out.append(Prim(KIND_CIRCLE, ROLE_ACCENT, cx=cx, cy=cy, rx=r, ry=r))
    return out


def _part_outline(rx, ry, level):
    """描边：R4 = 1px 弱光，R5 = 2px（XJ 端不做外晕，只加粗）。"""
    if level <= 0:
        return []
    return [Prim(KIND_OUTLINE, ROLE_OUTLINE, cx=0.0, cy=0.0,
                 rx=rx, ry=ry, width=float(level))]


def geometry(shape, stage, phase, base_len=1.0, stage_scale=None,
             pattern="none", outline=0):
    """★ 生成一条鱼的完整图元列表（纯函数，双端共享）。

    绘制顺序 = 列表顺序，后画的盖前面的：
    尾鳍 → 背鳍 → 腹鳍 → 身体 → 腹部 → 花纹 → 眼睛 → 描边。

    :param shape: fish_data.json 的 `shape` 段
    :param stage: 成长阶段
    :param phase: 摆尾相位 [0, 1)
    :param base_len: 基准体长（Py 端传像素）
    :param stage_scale: `balance.growth.stage_scale` 表
    :param pattern: none / stripes / spots（由稀有度决定）
    :param outline: 0 / 1 / 2（由稀有度决定）
    :returns: :class:`Prim` 列表
    """
    rx, ry = body_size(shape, stage, base_len, stage_scale)
    if rx <= 0.0 or ry <= 0.0:
        return []
    tail = (shape or {}).get("tail", "fork")

    prims = []
    prims.extend(_part_tail(rx, ry, tail, phase))
    prims.append(_part_dorsal(rx, ry, phase))
    prims.append(_part_pelvic(rx, ry, phase))
    prims.append(_part_body(rx, ry))
    prims.append(_part_belly(rx, ry))
    prims.extend(_part_pattern(rx, ry, pattern))
    prims.extend(_part_eyes(rx, ry))
    prims.extend(_part_outline(rx, ry, outline))
    return prims


def bounding_box(prims):
    """图元列表的包围盒 `(min_x, min_y, max_x, max_y)`；空列表返回全 0。

    渲染层用它决定点击命中范围与脏矩形。
    """
    if not prims:
        return (0.0, 0.0, 0.0, 0.0)
    xs = []
    ys = []
    for p in prims:
        if p.points:
            for (px, py) in p.points:
                xs.append(px)
                ys.append(py)
        else:
            xs.extend((p.cx - p.rx, p.cx + p.rx))
            ys.extend((p.cy - p.ry, p.cy + p.ry))
    return (min(xs), min(ys), max(xs), max(ys))


# ══════════════════════════════════════════════════════════════
#  Tk 适配区
# ══════════════════════════════════════════════════════════════

class FishPainter(object):
    """把 :func:`geometry` 的输出画到 tkinter Canvas 上（差分复用 item）。"""

    def __init__(self, canvas, theme, stage_scale=None):
        """:param canvas: tk.Canvas
        :param theme: :class:`pyapp.theme.Theme`
        :param stage_scale: `balance.growth.stage_scale` 表
        """
        self.canvas = canvas
        self.theme = theme
        self.stage_scale = stage_scale or dict(_DEFAULT_STAGE_SCALE)

    def color_for(self, role, view):
        """按角色取颜色。R3+ 的渐变用"身体色调亮/调暗"廉价模拟。"""
        if role == ROLE_BODY:
            return str(view.get("body_color", "#8899AA"))
        if role == ROLE_BELLY:
            return str(view.get("belly_color", view.get("body_color", "#B8C4CE")))
        if role == ROLE_FIN:
            return str(view.get("fin_color", view.get("body_color", "#9AA7B2")))
        if role == ROLE_ACCENT:
            return str(view.get("accent_color", "#2B2F36"))
        if role == ROLE_EYE:
            return "#101418"
        if role == ROLE_EYE_HL:
            return "#FFFFFF"
        return str(view.get("accent_color", "#FFFFFF"))

    def prims_for(self, view, base_len):
        """从 `game.fish_views()` 的一项生成图元。"""
        shape = {
            "length": view.get("body_len", 1.0),
            "height_ratio": view.get("body_ratio", 0.4),
            "tail": view.get("tail", "fork"),
        }
        return geometry(
            shape,
            str(view.get("stage", "adult")),
            float(view.get("tail_phase", 0.0)) / (2.0 * math.pi),
            base_len=base_len,
            stage_scale=self.stage_scale,
            pattern=str(view.get("pattern", "none")),
            outline=int(view.get("outline", 0) or 0),
        )

    def to_canvas_coords(self, prim, ox, oy, flip):
        """把图元的局部坐标换算成画布坐标。

        :param ox, oy: 鱼中心在画布上的像素坐标
        :param flip: True 时水平镜像（鱼朝左）
        :returns: 供 `coords()` 用的扁平坐标列表
        """
        sx = -1.0 if flip else 1.0
        if prim.points:
            flat = []
            for (px, py) in prim.points:
                flat.append(ox + px * sx)
                flat.append(oy + py)
            return flat
        x0 = ox + (prim.cx - prim.rx) * sx
        x1 = ox + (prim.cx + prim.rx) * sx
        if x0 > x1:
            x0, x1 = x1, x0
        return [x0, oy + prim.cy - prim.ry, x1, oy + prim.cy + prim.ry]

    def create_item(self, prim, coords, color, tag):
        """按图元类型建 canvas item，返回 item id。"""
        cv = self.canvas
        if prim.kind == KIND_POLYGON:
            return cv.create_polygon(*coords, fill=color, outline="", tags=tag)
        if prim.kind == KIND_OUTLINE:
            return cv.create_oval(*coords, fill="", outline=color,
                                  width=max(1.0, prim.width), tags=tag)
        if prim.kind == KIND_ELLIPSE_HALF:
            return cv.create_arc(*coords, start=180, extent=180,
                                 style="chord", fill=color, outline="", tags=tag)
        return cv.create_oval(*coords, fill=color, outline="", tags=tag)
