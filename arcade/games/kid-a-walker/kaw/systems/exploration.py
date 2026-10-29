# -*- coding: utf-8 -*-
"""区块探索追踪。"""
import math

from ..config import CHUNK_SIZE

class ExplorationTracker:
    """区块探索追踪"""
    def __init__(self, explore_radius: int = 10):
        self.explored: dict[tuple, bool] = {}
        self.explore_radius = explore_radius

    def check_and_mark(self, px, py, world):
        """检查玩家是否在区块中心附近，标记已探索"""
        cx, cy = world.world_to_chunk(px, py)
        # 计算区块中心的世界坐标
        center_wx = cx * CHUNK_SIZE + CHUNK_SIZE // 2
        center_wy = cy * CHUNK_SIZE + CHUNK_SIZE // 2
        dist = math.sqrt((px - center_wx)**2 + (py - center_wy)**2)
        if dist <= self.explore_radius:
            self.explored[(cx, cy)] = True

    def is_explored(self, cx, cy) -> bool:
        """指定区块是否已探索"""
        return (cx, cy) in self.explored

    def get_explored_count(self) -> int:
        """获取已探索区块数"""
        return len(self.explored)

    def reset(self):
        """重置探索记录"""
        self.explored.clear()
