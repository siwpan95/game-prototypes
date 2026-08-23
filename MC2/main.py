"""
main — Minecraft 复刻版（2D 文字向）命令行入口（无游戏逻辑）。

职责：
  - 自举注入 sys.path（example/），使 mcclone（含内联 _engine）可导入
  - 加载默认方块注册表（内置 6 块 + data/blocks.default.json 叠加）
  - 用确定性 Perlin 噪声生成侧视地形
  - 以 ANSI 彩色字符渲染并打印

坐标：x 向右，y 向上。
屏幕行 r ↔ world y = max_y - r；列 c ↔ world x = min_x + c。
"""

from __future__ import annotations

import os
import sys

# 自举：注入 example/ 自身，使 ``mcclone.*`` 可导入。
#   整合后 mcclone._engine 直接复用 alloy，需让 alloy 可导入
#   （引擎位于 example 的父目录 D:/allin/MCclone）。
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)
_ENGINE_PARENT = os.path.dirname(_THIS_DIR)
if _ENGINE_PARENT not in sys.path:
    sys.path.insert(0, _ENGINE_PARENT)

# 冒烟期静态验证：纯净版引擎可用（不含 MC 专属 PerlinNoise 等）。
from mcclone._engine import JSONLoader, Serializable  # noqa: F401

from mcclone.core.geometry import AABB2D
from mcclone.core.noise import PerlinNoise
from mcclone.core.block_registry import BlockRegistry
from mcclone.core.block_world import BlockWorld
from mcclone.core.terrain import TerrainGenerator
from mcclone.render.text_world_renderer import TextWorldRenderer


def main() -> None:
    """命令行入口：生成并渲染一个确定性侧视地形。"""
    # 1) 方块注册表（加载默认 + data/blocks.default.json）
    registry: BlockRegistry = BlockRegistry.from_json()

    # 2) 确定性地形：固定种子保证可复现
    seed: int = 12345
    width: int = 64
    height: int = 24
    noise = PerlinNoise(seed)
    generator = TerrainGenerator(registry, seed, noise)
    world: BlockWorld = generator.generate(width, height)

    # 3) ANSI 彩色渲染（视口覆盖整张世界）
    viewport = AABB2D(0, 0, width - 1, height - 1)
    renderer = TextWorldRenderer(registry)
    picture: str = renderer.render(world, viewport)

    # 4) 输出到终端
    print(picture, end="")
    print("MC 复刻版（2D 文字向）就绪：地形已生成并渲染。", flush=True)


if __name__ == "__main__":
    main()
