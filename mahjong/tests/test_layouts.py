"""布局生成校验 —— 无头运行。

验证:
  - 四种布局均生成正好 144 个槽位
  - 乌龟/金字塔为交叉堆叠，每张上层牌正下方 4 张下层牌均存在 (不悬空)
    （矩形布局为柱状兼容布局，README 已注明不严格保证交叉支撑，故跳过支撑校验）

运行：python tests/test_layouts.py   （在 G:/mahjong 根目录下）
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from services.layouts import LayoutKind, generate_layout  # noqa: E402


def _support_legal(slots) -> bool:
    """交叉堆叠支撑：每张 (l>0) 牌正下方 4 张下层牌必须存在。"""
    present = set(slots)
    for (l, r, c) in slots:
        if l == 0:
            continue
        for dr in (0, 1):
            for dc in (0, 1):
                if (l - 1, r + dr, c + dc) not in present:
                    return False
    return True


def test_all_layouts_have_144_slots():
    for kind in LayoutKind:
        slots = generate_layout(kind)
        assert len(slots) == 144, f"{kind.value} 槽位数应为144, 实际 {len(slots)}"
        # 槽位互不重复
        assert len(set(slots)) == 144, f"{kind.value} 存在重复槽位"
    print("PASS [L1] 四种布局均生成 144 个互不重复槽位")


def test_cross_stack_support():
    for kind in (LayoutKind.TURTLE, LayoutKind.PYRAMID):
        slots = generate_layout(kind)
        assert _support_legal(slots), f"{kind.value} 交叉堆叠支撑不合法 (存在悬空上层牌)"
    print("PASS [L2] 乌龟/金字塔 交叉堆叠支撑合法 (无悬空)")


if __name__ == "__main__":
    test_all_layouts_have_144_slots()
    test_cross_stack_support()
    print("LAYOUT_TESTS_PASS")
