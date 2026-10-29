# -*- coding: utf-8 -*-
"""E 键交互系统。"""
import math
from typing import Optional

from ..config import CHUNK_SIZE

class InteractionSystem:
    """E键交互系统"""
    def __init__(self, interact_range: float = 2.0):
        self.interact_range = interact_range

    def find_nearest_deco(self, px, py, world, fragments) -> Optional[tuple]:
        """扫描玩家周围，找到最近的未互动装饰物
        返回 (wx, wy, deco_type, interact_key) 或 None
        """
        scan_r = int(self.interact_range) + 1
        best_dist = self.interact_range
        best = None
        for dy in range(-scan_r, scan_r + 1):
            for dx in range(-scan_r, scan_r + 1):
                wx = int(px) + dx
                wy = int(py) + dy
                ct = world.cell(wx + 0.5, wy + 0.5)
                if ct < 2 or ct >= 12:  # 传送门(12)不可交互收集
                    continue
                cx, cy = world.world_to_chunk(wx + 0.5, wy + 0.5)
                lx = int(wx + 0.5) % CHUNK_SIZE
                ly = int(wy + 0.5) % CHUNK_SIZE
                key = (cx, cy, lx, ly)
                if fragments.has_interacted(key):
                    continue
                dist = math.sqrt((wx + 0.5 - px)**2 + (wy + 0.5 - py)**2)
                if dist < best_dist:
                    best_dist = dist
                    best = (wx, wy, ct, key)
        return best

    def is_in_range(self, px, py, world, fragments) -> bool:
        """是否有可交互的装饰物在范围内"""
        return self.find_nearest_deco(px, py, world, fragments) is not None

    def interact(self, px, py, world, fragments, energy) -> Optional[dict]:
        """执行交互，返回交互结果字典"""
        result = self.find_nearest_deco(px, py, world, fragments)
        if result is None:
            return None
        wx, wy, deco_type, key = result
        # 传送门等非碎片类型不可交互
        if deco_type >= 12:
            return None
        # 拾取碎片
        fragments.collect(deco_type, key)
        # 根据类型执行特殊效果
        effects = {"type": deco_type}
        if deco_type == 2:   # 青绿发光柱 → 恢复20能量
            energy.recover(20)
            effects["energy_recover"] = 20
        elif deco_type == 4: # 金色宝库 → 高分碎片
            effects["bonus_score"] = True
        elif deco_type == 6: # 紫色能量核心 → 临时护盾10秒
            energy.activate_shield(10.0)
            effects["shield"] = 10.0
        elif deco_type == 7: # 橙色光源 → 恢复少量+标记
            energy.recover(5)
            effects["energy_recover"] = 5
            effects["marker"] = (wx, wy)
        return effects
