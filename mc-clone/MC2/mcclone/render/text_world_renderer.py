"""
text_world_renderer — 文字向世界渲染器（无硬依赖）。

提供：
  - TextWorldRenderer: 将 BlockWorld 以 ANSI 彩色字符绘制为侧面地形。

坐标约定（屏幕）：
  - 行 r 对应 world y = viewport.max_y - r
  - 列 c 对应 world x = viewport.min_x + c

本模块依赖本地模块：geometry / block_registry / block_world。
"""

from __future__ import annotations

from typing import Dict

from mcclone.core.geometry import AABB2D
from mcclone.core.block_registry import BlockRegistry
from mcclone.core.block_world import BlockWorld


# ANSI 颜色名 → 转义码（兼容常见终端 16/256 色）。
_ANSI_COLORS: Dict[str, str] = {
    "black": "\033[30m",
    "red": "\033[31m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "blue": "\033[34m",
    "magenta": "\033[35m",
    "cyan": "\033[36m",
    "white": "\033[37m",
    "gray": "\033[90m",             # 亮灰
    "grey": "\033[90m",
    "brown": "\033[38;5;94m",       # 256 色棕
    "reset": "\033[0m",
}


def _ansi(color_name: str) -> str:
    """将颜色名映射为 ANSI 转义前缀；未知颜色回退到 white。"""
    return _ANSI_COLORS.get(color_name, _ANSI_COLORS["white"])


class TextWorldRenderer:
    """文字向世界渲染器。

    把指定视口范围内的方块按「行在最上、y 最大」的方式绘制成字符画。
    空气（air）渲染为空格（glyph=" "），其余按注册表定义着色。

    use_ansi 控制是否加 ANSI 颜色：
      - False：每行仅含 glyph（长度 == 视口宽度，便于纯文本断言）
      - True ：每格加颜色前缀，并在每行末尾追加一次 ``\\033[0m`` 重置
    """

    def __init__(self, registry: BlockRegistry) -> None:
        """初始化渲染器。

        参数：
            registry: 方块注册表（用于查询方块字形与颜色）
        """
        self.registry = registry

    def render_line(self, world: BlockWorld, viewport: AABB2D,
                    y: int, use_ansi: bool = False) -> str:
        """渲染视口内某一 world y 行的单行字符串。

        参数：
            world: 待渲染的方块世界
            viewport: 视口矩形（world 坐标），仅使用其 x 范围 [min_x, max_x]
            y: 要渲染的 world y（行对应的世界纵坐标）
            use_ansi: 是否加 ANSI 颜色前缀（默认 False → 纯 glyph）

        返回：
            单行字符串，长度等于视口宽度（max_x - min_x + 1）。
            当 use_ansi=True 时，每行各格含颜色前缀，并在末尾追加 ``\\033[0m``。
        """
        reg = self.registry
        min_x, max_x = viewport.min_x, viewport.max_x

        cells: list[str] = []
        for c in range(0, (max_x - min_x) + 1):
            world_x = min_x + c
            block_id = world.get(world_x, y, 0)
            try:
                block = reg.get(block_id)
            except KeyError:
                # 注册表缺失该 id 时退化为安全占位（空格）
                cells.append(" ")
                continue
            glyph = block.glyph if block.glyph else " "
            if use_ansi:
                cells.append(f"{_ansi(block.color)}{glyph}")
            else:
                cells.append(glyph)

        line = "".join(cells)
        if use_ansi:
            line += "\033[0m"
        return line

    def render_to_string(self, world: BlockWorld, viewport: AABB2D,
                         use_ansi: bool = True) -> str:
        """将视口范围内的世界渲染为字符串（支持 ANSI 透传）。

        参数：
            world: 待渲染的方块世界
            viewport: 视口矩形（world 坐标），
                      min=(min_x, min_y)，max=(max_x, max_y)
            use_ansi: 是否加 ANSI 颜色（默认 True）

        返回：
            多行字符串，每行以 ``\\n`` 结尾（最后一行也含 ``\\n``），可直接 print。
        """
        min_y, max_y = viewport.min_y, viewport.max_y
        lines: list[str] = []
        for r in range(0, (max_y - min_y) + 1):
            world_y = max_y - r  # 第 0 行对应最大 world y（屏幕顶部）
            lines.append(self.render_line(world, viewport, world_y, use_ansi=use_ansi))
        return "\n".join(lines) + "\n"

    # 公开 API 别名：render 与 render_to_string 行为一致。
    def render(self, world: BlockWorld, viewport: AABB2D,
               use_ansi: bool = True) -> str:
        """渲染世界（等价于 render_to_string，支持 use_ansi 参数）。

        参数：
            world: 待渲染的方块世界
            viewport: 视口矩形（world 坐标）
            use_ansi: 是否加 ANSI 颜色（默认 True）

        返回：
            多行字符串，每行以 ``\\n`` 结尾。
        """
        return self.render_to_string(world, viewport, use_ansi=use_ansi)
