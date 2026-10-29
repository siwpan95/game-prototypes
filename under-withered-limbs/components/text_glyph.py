"""
文字字形组件 — 类型安全版本。

定义实体在文字网格上的渲染外观。
使用 dataclass 实现，类型安全。
"""

from dataclasses import dataclass, field
from typing import Optional, Tuple

from core.ecs import Component


@dataclass
class TextGlyph(Component):
    """
    文字字形组件 — 定义实体在文字网格上的渲染外观。

    属性：
        char: 显示的字符
        fg: 前景色 (R, G, B)
        bg: 背景色 (R, G, B) 或 None
        highlight: 是否高亮显示（相邻可交互时）
        bold: 是否加粗
        blink: 是否闪烁
    """
    char: str = "·"
    fg: Tuple[int, int, int] = field(default=(120, 120, 130))
    bg: Optional[Tuple[int, int, int]] = None
    highlight: bool = False
    bold: bool = False
    blink: bool = False

    def set_color(self, r: int, g: int, b: int) -> None:
        """设置前景色。"""
        self.fg = (r, g, b)

    def set_bg(self, r: int, g: int, b: int) -> None:
        """设置背景色。"""
        self.bg = (r, g, b)

    def clear_bg(self) -> None:
        """清除背景色。"""
        self.bg = None

    @property
    def fg_hex(self) -> str:
        """前景色十六进制表示。"""
        return f"#{self.fg[0]:02x}{self.fg[1]:02x}{self.fg[2]:02x}"

    @property
    def bg_hex(self) -> str:
        """背景色十六进制表示。"""
        if self.bg:
            return f"#{self.bg[0]:02x}{self.bg[1]:02x}{self.bg[2]:02x}"
        return "transparent"

    def __repr__(self) -> str:
        return f"TextGlyph({self.char!r}, fg={self.fg}, highlight={self.highlight})"
