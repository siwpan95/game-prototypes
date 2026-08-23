"""
block_world — 方块世界存储（无硬依赖）。

提供：
  - BlockWorld: 稀疏存储方块的三维（z=depth，默认 1）世界。
    支持越界安全访问、矩形填充、分块序列化与整世界序列化。

坐标约定：x 向右，y 向上，z 为层（depth，默认 1）。
越界或缺失方块一律返回 air(0)。

本模块依赖：
  - 本地 geometry（Vec2i/AABB2D/clamp/lerp）
  - 纯净版 alloy.core.serializable.Serializable
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from mcclone.core.geometry import AABB2D
from mcclone._engine import Serializable


def _key(x: int, y: int, z: int) -> Tuple[int, int, int]:
    """构造方块存储键（元组，可哈希）。"""
    return (x, y, z)


class BlockWorld(Serializable):
    """方块世界。

    内部以 dict[(x,y,z)] -> block_id 稀疏存储（仅存非 air 以省内存）。
    越界或缺失方块一律返回 air(0)。实现 to_dict()/from_dict() 以支持存档。
    """

    def __init__(self, width: int, height: int, depth: int = 1) -> None:
        self.width = width
        self.height = height
        self.depth = depth
        # 稀疏存储：键为 (x,y,z)，值为 block_id（非 0）
        self._blocks: Dict[Tuple[int, int, int], int] = {}

    # ── 访问 ──

    def in_bounds(self, x: int, y: int, z: int = 0) -> bool:
        """判断坐标是否在世界范围内。"""
        return 0 <= x < self.width and 0 <= y < self.height and 0 <= z < self.depth

    def get(self, x: int, y: int, z: int = 0) -> int:
        """获取方块 id；越界或缺失返回 0 (air)。"""
        if not self.in_bounds(x, y, z):
            return 0
        return self._blocks.get(_key(x, y, z), 0)

    def set(self, x: int, y: int, z: int, block_id: int) -> None:
        """设置方块 id。

        越界则静默忽略；block_id == 0 表示空气，会从稀疏表中移除该格。
        """
        if not self.in_bounds(x, y, z):
            return
        key = _key(x, y, z)
        if block_id == 0:
            self._blocks.pop(key, None)
        else:
            self._blocks[key] = block_id

    def fill_rect(self, x0: int, y0: int, x1: int, y1: int,
                  block_id: int, z: int = 0) -> None:
        """矩形填充（自动处理 min/max），越界部分静默忽略。"""
        xa, xb = (x0, x1) if x0 <= x1 else (x1, x0)
        ya, yb = (y0, y1) if y0 <= y1 else (y1, y0)
        for y in range(ya, yb + 1):
            for x in range(xa, xb + 1):
                self.set(x, y, z, block_id)

    def bounds(self) -> AABB2D:
        """返回世界包围盒（min=(0,0), max=(width-1, height-1)）。"""
        return AABB2D(0, 0, self.width - 1, self.height - 1)

    # ── 分块序列化 ──

    def serialize_chunk(self, cx: int, cy: int, size: int) -> Dict[str, Any]:
        """序列化一个 chunk 为二维网格。

        返回结构：``{"cx","cy","size","blocks":[[id,...],...]}``
        blocks 行序从上到下（第 0 行 = chunk 内最大 world y），
        列序从左到右（x 递增）。

        参数：
            cx, cy: chunk 坐标（左上角 world 坐标 = (cx*size, cy*size)）
            size: chunk 边长（方块数）
        """
        ox = cx * size
        oy = cy * size
        grid: List[List[int]] = []
        for r in range(size):
            row: List[int] = []
            world_y = oy + (size - 1 - r)  # 第 0 行对应最大 world y
            for c in range(size):
                world_x = ox + c
                row.append(self.get(world_x, world_y, 0))
            grid.append(row)
        return {"cx": cx, "cy": cy, "size": size, "blocks": grid}

    def load_chunk(self, cx: int, cy: int, size: int, data: Dict[str, Any]) -> None:
        """从 serialize_chunk() 的产出还原一个 chunk。

        参数：
            cx, cy: chunk 坐标
            size: chunk 边长
            data: serialize_chunk() 返回的字典
        """
        grid = data.get("blocks", [])
        ox = cx * size
        oy = cy * size
        for r, row in enumerate(grid):
            world_y = oy + (size - 1 - r)
            for c, block_id in enumerate(row):
                world_x = ox + c
                self.set(world_x, world_y, 0, int(block_id))

    # ── 整世界序列化 ──

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典：含 width/height/depth + 稀疏 blocks。

        blocks 以 ``"x,y,z"`` 字符串为键、block_id 为值（仅存非 air）。
        """
        blocks: Dict[str, int] = {}
        for (x, y, z), bid in self._blocks.items():
            blocks[f"{x},{y},{z}"] = bid
        return {
            "width": self.width,
            "height": self.height,
            "depth": self.depth,
            "blocks": blocks,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BlockWorld":
        """从 to_dict() 的产出重建世界。"""
        width = int(data.get("width", 0))
        height = int(data.get("height", 0))
        depth = int(data.get("depth", 1))
        world = cls(width, height, depth)
        blocks = data.get("blocks", {})
        for key, bid in blocks.items():
            parts = key.split(",")
            if len(parts) == 3:
                x, y, z = int(parts[0]), int(parts[1]), int(parts[2])
                world.set(x, y, z, int(bid))
        return world
