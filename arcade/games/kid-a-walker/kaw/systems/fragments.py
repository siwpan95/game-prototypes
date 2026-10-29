# -*- coding: utf-8 -*-
"""碎片收集系统（含跨局图鉴）。"""
from dataclasses import dataclass

from ..config import FRAGMENT_TYPES

@dataclass
class FragmentSystem:
    """碎片收集系统"""
    collected: dict = None        # {deco_type: count}
    interacted: dict = None       # {(cx,cy,lx,ly): True}
    codex: dict = None            # 图鉴跨局保留 {deco_type: True}
    total_types: int = FRAGMENT_TYPES  # 10种碎片（类型2-11）

    def __post_init__(self):
        if self.collected is None:
            self.collected = {}
        if self.interacted is None:
            self.interacted = {}
        if self.codex is None:
            self.codex = {}

    def collect(self, deco_type: int, key: tuple) -> bool:
        """拾取碎片并标记已互动，返回是否成功"""
        if key in self.interacted:
            return False  # 已拾取过
        self.interacted[key] = True
        self.collected[deco_type] = self.collected.get(deco_type, 0) + 1
        # 图鉴记录（跨局保留）
        self.codex[deco_type] = True
        return True

    def has_interacted(self, key: tuple) -> bool:
        """是否已互动过"""
        return key in self.interacted

    def get_count(self, deco_type: int) -> int:
        """获取指定类型碎片数量"""
        return self.collected.get(deco_type, 0)

    def get_total(self) -> int:
        """获取碎片总数"""
        return sum(self.collected.values())

    def get_unique_types(self) -> int:
        """获取已收集的不同类型数"""
        return len(self.collected)

    def is_all_types_collected(self) -> bool:
        """是否收集齐所有类型"""
        return self.get_unique_types() >= self.total_types

    def reset(self):
        """重置（保留图鉴）"""
        self.collected.clear()
        self.interacted.clear()
        # 注意：codex 不清除，跨局保留
