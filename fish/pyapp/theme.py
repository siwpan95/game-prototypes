"""配色与字体（全部取自 `balance.json` 的 `ui` 段，代码里不写死颜色）。

🔴 禁止 `from __future__ import annotations`（E6，全项目统一）。

色键陷阱（ARCHITECTURE §7.2 末尾警告）
--------------------------------------
`-transparentcolor` 抠掉的像素**同时会失去鼠标命中**。
所以水体颜色必须与色键**不同**，否则整个鱼缸都点不中、拖不动。
:func:`Theme.validate` 会把这条约束当成断言来查。
"""

_FALLBACK = {
    "chroma": "#010203",
    "water_top": "#0A3A52",
    "water_bottom": "#062434",
    "glass_edge": "#12506E",
    "hud_text": "#DDEAF2",
    "hud_bar_bg": "#0E3346",
    "hud_bar_good": "#57C7A0",
    "hud_bar_mid": "#E8C05A",
    "hud_bar_low": "#D98A6A",
    "card_bg": "#0C2634",
    "card_fg": "#E4F0F6",
    "card_accent": "#7FD0E0",
}
"""balance.json 缺字段时的兜底色（仅防崩溃，正常路径不会用到）。"""


def clamp01(v):
    """把数值夹到 [0, 1]。"""
    v = float(v)
    if v < 0.0:
        return 0.0
    return 1.0 if v > 1.0 else v


def parse_hex(color):
    """`#RRGGBB` → (r, g, b)；解析失败返回黑色。"""
    s = str(color or "").strip()
    if s.startswith("#"):
        s = s[1:]
    if len(s) == 3:
        s = "".join(ch * 2 for ch in s)
    if len(s) != 6:
        return (0, 0, 0)
    try:
        return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))
    except ValueError:
        return (0, 0, 0)


def to_hex(rgb):
    """(r, g, b) → `#RRGGBB`，分量自动夹到 0..255。"""
    out = []
    for c in rgb:
        c = int(round(float(c)))
        c = 0 if c < 0 else (255 if c > 255 else c)
        out.append(c)
    return "#%02X%02X%02X" % (out[0], out[1], out[2])


def mix(color_a, color_b, t):
    """线性混合两个颜色，`t=0` 取 A，`t=1` 取 B。

    HUD 淡出靠它模拟透明度：Canvas 图元没有 per-item alpha，
    只能把前景色朝背景色混过去（§7.2 表格 "HUD 淡出" 行）。
    """
    t = clamp01(t)
    ra, ga, ba = parse_hex(color_a)
    rb, gb, bb = parse_hex(color_b)
    return to_hex((ra + (rb - ra) * t, ga + (gb - ga) * t, ba + (bb - ba) * t))


def shade(color, factor):
    """按比例调亮(>1)/调暗(<1)一个颜色。"""
    r, g, b = parse_hex(color)
    f = max(0.0, float(factor))
    return to_hex((r * f, g * f, b * f))


class Theme(object):
    """一份从 `balance.ui` 烘焙出来的配色 + 尺寸表。"""

    def __init__(self, bal=None):
        """:param bal: :class:`~fishtank.data_defs.BalanceTable`，可为 None（走兜底）"""
        self._bal = bal
        for key, dflt in _FALLBACK.items():
            setattr(self, key, self._color("ui." + key, dflt))

        self.tank_w, self.tank_h = self._pair("ui.tank_size", 360, 220)
        self.panel_w, self.panel_h = self._pair("ui.panel_size", 720, 480)
        self.mini_w, self.mini_h = self._pair("ui.mini_size", 48, 48)
        self.strip_height = int(self._num("ui.strip_height", 120))
        self.snap_px = int(self._num("ui.snap_px", 24))
        self.hud_fade_sec = float(self._num("ui.hud_fade_sec", 2.0))
        self.hud_dim_alpha = clamp01(self._num("ui.hud_dim_alpha", 0.3))
        self.fish_card_sec = float(self._num("ui.fish_card_sec", 3.0))
        self.font_family = "TkDefaultFont"

    # ── 取值helpers ──

    def _raw(self, path, dflt):
        if self._bal is None:
            return dflt
        v = self._bal.get(path)
        return dflt if v is None else v

    def _color(self, path, dflt):
        v = self._raw(path, dflt)
        return str(v) if isinstance(v, str) and v.strip() else dflt

    def _num(self, path, dflt):
        try:
            return float(self._raw(path, dflt))
        except (TypeError, ValueError):
            return float(dflt)

    def _pair(self, path, dw, dh):
        v = self._raw(path, None)
        if isinstance(v, (list, tuple)) and len(v) >= 2:
            try:
                return int(v[0]), int(v[1])
            except (TypeError, ValueError):
                return dw, dh
        return dw, dh

    # ── 派生色 ──

    def water_at(self, t):
        """缸内 y=t（0=水面, 1=缸底）处的水体颜色，用于伪渐变。"""
        return mix(self.water_top, self.water_bottom, clamp01(t))

    def bar_color(self, ratio):
        """水质条颜色：高=good / 中=mid / 低=low。

        阈值是**纯表现**分档，不参与任何玩法计算。
        """
        r = clamp01(ratio)
        if r >= 0.66:
            return self.hud_bar_good
        return self.hud_bar_mid if r >= 0.33 else self.hud_bar_low

    def dim(self, color, alpha):
        """把颜色朝水体背景混，模拟 alpha（Canvas 无 per-item alpha）。"""
        return mix(self.water_bottom, color, clamp01(alpha))

    def pick_font(self, candidates, size=10, weight="normal"):
        """从候选字体名里挑第一个系统装了的，返回 tkinter 字体元组。

        :param candidates: :func:`fishtank.engine_bootstrap.engine_font_candidates` 的结果
        """
        try:
            import tkinter.font as tkfont
            available = set(tkfont.families())
        except (ImportError, RuntimeError):
            available = set()
        for name in (candidates or []):
            if name in available or name == "TkDefaultFont":
                self.font_family = name
                return (name, int(size), weight)
        return ("TkDefaultFont", int(size), weight)

    # ── 自检 ──

    def validate(self):
        """返回配色问题列表（空 = 没问题）。

        目前只有一条硬约束，但它是致命的：水体色 == 色键 会让鱼缸整体
        失去鼠标命中，窗口再也拖不动。
        """
        bad = []
        ck = parse_hex(self.chroma)
        for name in ("water_top", "water_bottom", "glass_edge"):
            if parse_hex(getattr(self, name)) == ck:
                bad.append("ui.%s 与 ui.chroma 相同，该区域会失去鼠标命中" % name)
        return bad
