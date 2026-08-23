"""
终端文字渲染器 — ANSI 颜色 + 网格绘制 + 滚动缓冲

支持:
    - ANSI 256 色终端输出
    - 网格化地图/场景绘制
    - 双缓冲滚动显示
    - 打字机效果输出

使用示例:
    from alloy.world.map_data import MapData
    from alloy.render.console_renderer import ConsoleRenderer

    renderer = ConsoleRenderer(cols=80, rows=24)
    renderer.draw_text(0, 0, "Hello World", color="red")
    renderer.draw_grid(map_data)
    renderer.flush()
"""

from __future__ import annotations

import sys
import shutil
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from alloy.world.map_data import MapData


# ================================================================
#  ANSI 颜色映射表
# ================================================================

# 前景色名 → ANSI 代码
ANSI_FOREGROUND: Dict[str, str] = {
    "black":        "\033[30m",
    "red":          "\033[31m",
    "green":        "\033[32m",
    "yellow":       "\033[33m",
    "blue":         "\033[34m",
    "magenta":      "\033[35m",
    "cyan":         "\033[36m",
    "white":        "\033[37m",
    "bright_black": "\033[90m",
    "bright_red":   "\033[91m",
    "bright_green": "\033[92m",
    "bright_yellow":"\033[93m",
    "bright_blue":  "\033[94m",
    "bright_magenta":"\033[95m",
    "bright_cyan":  "\033[96m",
    "bright_white": "\033[97m",
}

# 背景色名 → ANSI 代码
ANSI_BACKGROUND: Dict[str, str] = {
    "black":        "\033[40m",
    "red":          "\033[41m",
    "green":        "\033[42m",
    "yellow":       "\033[43m",
    "blue":         "\033[44m",
    "magenta":      "\033[45m",
    "cyan":         "\033[46m",
    "white":        "\033[47m",
    "bright_black": "\033[100m",
    "bright_red":   "\033[101m",
    "bright_green": "\033[102m",
    "bright_yellow":"\033[103m",
    "bright_blue":  "\033[104m",
    "bright_magenta":"\033[105m",
    "bright_cyan":  "\033[106m",
    "bright_white": "\033[107m",
}

ANSI_RESET = "\033[0m"
ANSI_BOLD = "\033[1m"
ANSI_DIM = "\033[2m"
ANSI_ITALIC = "\033[3m"
ANSI_UNDERLINE = "\033[4m"

# 字符 → 颜色映射（用于网格渲染）
CHAR_COLOR_MAP: Dict[str, str] = {
    "#": "bright_black",  # 墙壁
    ".": "bright_black",  # 地面
    "@": "bright_yellow", # 玩家
    "E": "red",           # 敌人
    "T": "green",         # 宝物
    "D": "bright_magenta",# 门
    "S": "blue",          # 商店
    "~": "cyan",          # 水
    ",": "yellow",        # 沙地
    "^": "red",           # 陷阱
    "*": "bright_green",  # 星星
    "!": "bright_red",    # 重要
    "?": "yellow",        # 未知
    " ": None,            # 空白
}


# ================================================================
#  ConsoleRenderer
# ================================================================

class ConsoleRenderer:
    """终端文字渲染器 — ANSI 颜色 + 双缓冲。

    使用示例:
        renderer = ConsoleRenderer(cols=80, rows=24)

        # 绘制地图
        map_data = MapData.from_string('''
        ############
        #@.........#
        #....E.....#
        ############
        ''')
        renderer.draw_grid(map_data, offset_x=2, offset_y=1)

        # 绘制文字
        renderer.draw_text(0, 22, "HP: 100/100", color="green")
        renderer.draw_text(0, 23, "按 Q 退出")

        # 输出
        renderer.flush()
    """

    # 默认配置
    DEFAULT_COLS: int = 80
    DEFAULT_ROWS: int = 24
    CELL_WIDTH: int = 1   # 每个格子的字符宽度

    def __init__(
        self,
        cols: int = 0,
        rows: int = 0,
        default_fg: str = "white",
        default_bg: str = "black",
        use_colors: bool = True,
        stream=None,
    ):
        """初始化终端渲染器。

        参数:
            cols: 终端列数 (0=自动检测)
            rows: 终端行数 (0=自动检测)
            default_fg: 默认前景色
            default_bg: 默认背景色
            use_colors: 是否使用 ANSI 颜色
            stream: 输出流 (默认 sys.stdout)
        """
        term_size = shutil.get_terminal_size((80, 24))
        self.cols = cols or term_size.columns
        self.rows = rows or term_size.lines
        self.default_fg = default_fg
        self.default_bg = default_bg
        self.use_colors = use_colors
        self.stream = stream or sys.stdout

        # 双缓冲：screen_buf[row][col] = (char, fg, bg, attrs)
        self._buf: List[List[Tuple[str, str, str, List[str]]]] = []
        self._scroll_buffer: List[str] = []  # 滚动历史
        self._max_scroll: int = 1000
        self._clear()

    # ── 缓冲操作 ──

    def _clear(self):
        """清空绘制缓冲。"""
        self._buf = [
            [(" ", self.default_fg, self.default_bg, [])
             for _ in range(self.cols)]
            for _ in range(self.rows)
        ]

    def _set_cell(self, x: int, y: int, char: str, fg: str = "", bg: str = "", attrs: Optional[List[str]] = None):
        """设置缓冲中的单个格子。

        参数:
            x: 列
            y: 行
            char: 字符
            fg: 前景色名
            bg: 背景色名
            attrs: 属性列表 (bold, dim, italic, underline)
        """
        if 0 <= y < self.rows and 0 <= x < self.cols:
            ch = char[0] if char else " "
            fg_name = fg or self.default_fg
            bg_name = bg or self.default_bg
            attr_list = attrs or []
            self._buf[y][x] = (ch, fg_name, bg_name, attr_list)

    # ── 绘制方法 ──

    def draw_text(
        self,
        x: int,
        y: int,
        text: str,
        color: str = "",
        bg: str = "",
        bold: bool = False,
        dim: bool = False,
        italic: bool = False,
        underline: bool = False,
    ):
        """在指定位置绘制文字。

        参数:
            x: 起始列
            y: 行号
            text: 文本
            color: 前景色名
            bg: 背景色名
            bold: 加粗
            dim: 暗淡
            italic: 斜体
            underline: 下划线
        """
        attrs = []
        if bold:
            attrs.append("bold")
        if dim:
            attrs.append("dim")
        if italic:
            attrs.append("italic")
        if underline:
            attrs.append("underline")

        for i, ch in enumerate(text):
            self._set_cell(x + i, y, ch, fg=color, bg=bg, attrs=attrs)

    def draw_centered_text(
        self,
        y: int,
        text: str,
        color: str = "",
        bg: str = "",
        bold: bool = False,
    ):
        """在指定行居中绘制文字。

        参数:
            y: 行号
            text: 文本
            color: 前景色名
            bg: 背景色名
            bold: 加粗
        """
        x = max(0, (self.cols - len(text)) // 2)
        self.draw_text(x, y, text, color=color, bg=bg, bold=bold)

    def draw_grid(
        self,
        map_data: MapData,
        offset_x: int = 0,
        offset_y: int = 0,
        char_color_map: Optional[Dict[str, str]] = None,
    ):
        """绘制网格地图。

        参数:
            map_data: MapData 实例
            offset_x: X 偏移（列）
            offset_y: Y 偏移（行）
            char_color_map: 自定义颜色映射 (覆盖默认映射)
        """
        cmap = {**CHAR_COLOR_MAP, **(char_color_map or {})}

        for row in range(map_data.height):
            for col in range(map_data.width):
                ch = map_data.get(col, row)
                fg = cmap.get(ch)
                self._set_cell(
                    offset_x + col * self.CELL_WIDTH,
                    offset_y + row,
                    ch,
                    fg=fg,
                )

    def draw_rect(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        char: str = " ",
        fg: str = "",
        bg: str = "",
        border: bool = False,
        border_char: str = "#",
    ):
        """绘制矩形。

        参数:
            x, y: 左上角位置
            width, height: 矩形宽高
            char: 填充字符
            fg, bg: 前景色/背景色
            border: 是否绘制边框
            border_char: 边框字符
        """
        for dy in range(height):
            for dx in range(width):
                is_border = border and (
                    dx == 0 or dx == width - 1 or dy == 0 or dy == height - 1
                )
                ch = border_char if is_border else char
                self._set_cell(x + dx, y + dy, ch, fg=fg, bg=bg)

    def draw_progress_bar(
        self,
        x: int,
        y: int,
        current: int,
        total: int,
        width: int = 20,
        fill_color: str = "green",
        empty_color: str = "bright_black",
        filled: str = "█",
        empty: str = "░",
    ):
        """绘制进度条。

        参数:
            x, y: 起始位置
            current: 当前值
            total: 最大值
            width: 进度条字符宽度
            fill_color: 已填充部分颜色
            empty_color: 未填充部分颜色
            filled: 填充字符
            empty: 空白字符
        """
        if total == 0:
            ratio = 0
        else:
            ratio = min(1.0, max(0.0, current / total))

        filled_count = int(width * ratio)
        bar = filled * filled_count + empty * (width - filled_count)
        percent = int(ratio * 100)
        text = f"[{bar}] {percent:3d}%"

        # 填充部分用绿色，空部分用暗色
        idx = 0
        for ch in text:
            if ch == filled:
                color = fill_color
            elif ch == empty:
                color = empty_color
            else:
                color = ""
            self._set_cell(x + idx, y, ch, fg=color)
            idx += 1

    def draw_hline(self, x: int, y: int, width: int, char: str = "─", color: str = ""):
        """绘制水平线。

        参数:
            x, y: 起始位置
            width: 线的长度
            char: 线条字符
            color: 颜色
        """
        for i in range(width):
            self._set_cell(x + i, y, char, fg=color)

    def draw_vline(self, x: int, y: int, height: int, char: str = "│", color: str = ""):
        """绘制竖直线。

        参数:
            x, y: 起始位置
            height: 线的长度
            char: 线条字符
            color: 颜色
        """
        for i in range(height):
            self._set_cell(x, y + i, char, fg=color)

    def clear(self):
        """清空绘制缓冲。"""
        self._clear()

    def clear_screen(self):
        """发送终端清屏序列。"""
        self.stream.write("\033[2J\033[H")
        self.stream.flush()

    # ── 输出 ──

    def flush(self):
        """将缓冲输出到终端。"""
        lines = []
        for row in self._buf:
            line_parts = []
            prev_fg = None
            prev_bg = None
            prev_attrs = None

            for ch, fg, bg, attrs in row:
                if self.use_colors:
                    current_attrs = tuple(sorted(attrs))
                    if fg != prev_fg or bg != prev_bg or current_attrs != prev_attrs:
                        codes = []
                        # 重置
                        codes.append(ANSI_RESET)
                        # 属性
                        if "bold" in attrs:
                            codes.append(ANSI_BOLD)
                        if "dim" in attrs:
                            codes.append(ANSI_DIM)
                        if "italic" in attrs:
                            codes.append(ANSI_ITALIC)
                        if "underline" in attrs:
                            codes.append(ANSI_UNDERLINE)
                        # 颜色
                        fg_code = ANSI_FOREGROUND.get(fg, "")
                        if fg_code:
                            codes.append(fg_code)
                        bg_code = ANSI_BACKGROUND.get(bg, "")
                        if bg_code:
                            codes.append(bg_code)
                        line_parts.append("".join(codes))
                        prev_fg = fg
                        prev_bg = bg
                        prev_attrs = current_attrs

                line_parts.append(ch)

            if self.use_colors:
                line_parts.append(ANSI_RESET)

            line_str = "".join(line_parts).rstrip()
            lines.append(line_str)

            # 保存到滚动缓冲
            self._scroll_buffer.append(line_str)
            if len(self._scroll_buffer) > self._max_scroll:
                self._scroll_buffer.pop(0)

        # 输出
        self.stream.write("\n".join(lines) + "\n")
        self.stream.flush()

        # 清空以供下一帧
        self._clear()

    def scroll_text(self, text: str, color: str = "", bold: bool = False):
        """向滚动缓冲追加文本并立即刷新一行。

        参数:
            text: 文本
            color: 前景色
            bold: 加粗
        """
        line = text[:self.cols]
        self._scroll_buffer.append(line)
        if len(self._scroll_buffer) > self._max_scroll:
            self._scroll_buffer.pop(0)

        # 输出此行
        if self.use_colors:
            codes = [ANSI_RESET]
            if bold:
                codes.append(ANSI_BOLD)
            fg_code = ANSI_FOREGROUND.get(color, "")
            if fg_code:
                codes.append(fg_code)
            self.stream.write("".join(codes) + line + ANSI_RESET + "\n")
        else:
            self.stream.write(line + "\n")
        self.stream.flush()

    def get_scroll_buffer(self) -> List[str]:
        """获取滚动缓冲（最近 N 行）。"""
        return list(self._scroll_buffer)

    # ── 实用方法 ──

    def resize(self, cols: int, rows: int):
        """调整渲染器尺寸。"""
        self.cols = cols
        self.rows = rows
        self._clear()

    @property
    def size(self) -> Tuple[int, int]:
        """返回 (cols, rows)。"""
        return (self.cols, self.rows)

    @staticmethod
    def colorize(text: str, color: str, bold: bool = False) -> str:
        """静态方法：为字符串添加 ANSI 颜色。

        参数:
            text: 文本
            color: 颜色名
            bold: 加粗

        返回:
            带 ANSI 代码的字符串
        """
        codes = []
        if bold:
            codes.append(ANSI_BOLD)
        fg_code = ANSI_FOREGROUND.get(color, "")
        if fg_code:
            codes.append(fg_code)
        if codes:
            return "".join(codes) + text + ANSI_RESET
        return text

    @staticmethod
    def strip_ansi(text: str) -> str:
        """去除 ANSI 转义序列。"""
        import re
        return re.sub(r"\033\[[0-9;]*m", "", text)
