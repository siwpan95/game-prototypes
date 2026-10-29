# -*- coding: utf-8 -*-
"""inventory — 本地背包数据模型（M2 生存基底）。

提供：
  - Inventory: 槽位数组 [(block_id, count)]，前 hotbar_size 槽 = 快捷栏；
    add/remove（跨栈并入/扣减、受 STACK_MAX 限制、空槽复用）/ count /
    select / held_block / hotbar_blocks / as_list / slot。

设计要点（架构 §7.3 / §7.7）：
  - 零依赖（仅标准库），可在 headless 下断言。
  - 前 hotbar_size 个槽是手持切换与放置的唯一数据源；Player 在构造时预填。
  - 增/删受 STACK_MAX 限制；跨多栈合并；空槽自动复用。

本模块不依赖 allin_engine，与 M1 风格一致（扁平本地 import）。
"""

from __future__ import annotations

from typing import List, Optional, Tuple

# 整合：把本地方块背包投影为引擎 StackableInventory（跨玩法层资源核算）。
# 本地方块背包仍是权威存储（热栏/放置依赖其定长槽位模型）。
from allin_engine.systems.stackable_inventory import (  # noqa: E402
    StackableInventory,
    ItemRegistry,
)

# 单栈最大数量（与 main_gui.STACK_MAX / 架构 §7.1 一致）。
STACK_MAX: int = 64
# 快捷栏槽数（与 Player.hotbar 长度一致）。
HOTBAR_SIZE: int = 6
# 空气方块 id（空手 / 空槽语义用）。
AIR: int = 0

# 单个槽位类型：(block_id, count)
Slot = Optional[Tuple[int, int]]


class Inventory:
    """本地背包：定长槽位数组，前 hotbar_size 槽为快捷栏。

    约定：
      - 槽位存 (block_id, count)；空槽为 None。
      - add 先并入同 id 现有栈（不超过 STACK_MAX），余量进首个空槽；
        返回实际加入数（受 STACK_MAX 与空槽数限制）。
      - remove 从同 id 栈扣减，返回实际移除数（不足则尽量移除）。
      - 所有数量操作均钳制在 [0, STACK_MAX]，不会为负或溢出。
    """

    #: 单栈最大数量（类级常量，便于引用）。
    STACK_MAX: int = STACK_MAX
    #: 快捷栏槽数。
    HOTBAR_SIZE: int = HOTBAR_SIZE

    def __init__(self, slots: int = 36, hotbar_size: int = HOTBAR_SIZE) -> None:
        """构造空背包。

        参数：
            slots: 总槽位数（默认 36）。
            hotbar_size: 快捷栏槽数（默认 6，必须 <= slots）。
        """
        if hotbar_size > slots:
            raise ValueError("hotbar_size 不能超过总槽位数")
        self.slots: int = slots
        self.hotbar_size: int = hotbar_size
        # 每个槽位 = (block_id, count) 或 None（空）。
        self._items: List[Slot] = [None] * slots
        # 当前选中的快捷栏槽索引（0..hotbar_size-1）。
        self._selected: int = 0

    # ── 增删 ──
    def add(self, block_id: int, n: int) -> int:
        """加入 n 个 block_id；先并入同 id 栈，余量进空槽。

        参数：
            block_id: 方块 id（AIR 也允许，但通常不入库）。
            n: 希望加入的数量（>=0）。

        返回：
            实际加入的数量（受 STACK_MAX 与空槽数限制，0 <= 返回值 <= n）。
        """
        if n <= 0:
            return 0
        remaining = n
        # 1) 并入现有同 id 栈（不超过 STACK_MAX）
        for i in range(self.slots):
            if remaining <= 0:
                break
            it = self._items[i]
            if it is not None and it[0] == block_id:
                space = self.STACK_MAX - it[1]
                if space > 0:
                    take = min(space, remaining)
                    self._items[i] = (block_id, it[1] + take)
                    remaining -= take
        # 2) 余量进首个空槽
        for i in range(self.slots):
            if remaining <= 0:
                break
            if self._items[i] is None:
                take = min(self.STACK_MAX, remaining)
                self._items[i] = (block_id, take)
                remaining -= take
        # 实际加入 = 期望 - 剩余未加入
        return n - remaining

    def remove(self, block_id: int, n: int) -> int:
        """移除 n 个 block_id（跨多栈扣减）。

        参数：
            block_id: 方块 id。
            n: 希望移除的数量（>=0）。

        返回：
            实际移除的数量（不足时尽量移除，0 <= 返回值 <= n）。
            调用方应比较返回值与 n 判断是否满足消耗。
        """
        if n <= 0:
            return 0
        remaining = n
        for i in range(self.slots):
            if remaining <= 0:
                break
            it = self._items[i]
            if it is not None and it[0] == block_id:
                cur = it[1]
                take = min(cur, remaining)
                cur -= take
                remaining -= take
                if cur == 0:
                    self._items[i] = None
                else:
                    self._items[i] = (block_id, cur)
        return n - remaining

    # ── 查询 ──
    def count(self, block_id: int) -> int:
        """统计背包中某 block_id 的总数量。"""
        total = 0
        for it in self._items:
            if it is not None and it[0] == block_id:
                total += it[1]
        return total

    def slot(self, i: int) -> Slot:
        """返回第 i 槽的内容：(block_id, count) 或 None。"""
        if 0 <= i < self.slots:
            return self._items[i]
        return None

    def select(self, slot: int) -> None:
        """选中某快捷栏槽（0..slots-1；越界忽略）。"""
        if 0 <= slot < self.slots:
            self._selected = slot

    def held_block(self) -> int:
        """返回当前选中槽的 block_id；空槽返回 AIR(0)。"""
        it = self._items[self._selected]
        if it is None:
            return AIR
        return it[0]

    def hotbar_blocks(self) -> List[int]:
        """返回前 hotbar_size 槽的 block_id 列表（空槽记 AIR）。

        供 Player.hotbar 同步（架构 §7.7）。
        """
        result: List[int] = []
        for i in range(self.hotbar_size):
            it = self._items[i]
            result.append(AIR if it is None else it[0])
        return result

    def as_list(self) -> List[Slot]:
        """返回完整槽位数组副本（长度 = slots）。"""
        return list(self._items)

    def get_selected(self) -> int:
        """返回当前选中槽索引。"""
        return self._selected

    def load_list(self, items: list) -> None:
        """由快照列表还原槽位（供存档/读档使用）。
        
        items: 元素为 [block_id, count] 或 None。
        """
        restored = [None] * self.slots
        for i, item in enumerate(items):
            if i >= self.slots:
                break
            if item is None:
                restored[i] = None
            elif isinstance(item, (list, tuple)) and len(item) == 2:
                restored[i] = (int(item[0]), int(item[1]))
            else:
                restored[i] = None
        self._items = restored
        if self._selected >= self.slots:
            self._selected = 0

    def to_engine_inventory(self, registry: "ItemRegistry") -> "StackableInventory":
        """把本地方块背包投影为引擎 StackableInventory（跨玩法层资源打通）。

        整合：MC2 的方块 id 通过统一产品内核共享 ItemRegistry 的 ``mc2_block_<id>``
        映射到引擎物品，从而可在统一产品里用引擎 StackableInventory 做跨模式资源核算
        （与 MC1 的 StackableInventory 站在同一引擎子系统上）。
        本地方块背包仍是其权威存储（热栏/放置依赖其定长槽位模型）；
        此投影是「引擎子系统真正承担库存核算」的整合点，而非影子副本。
        """
        from allin_engine.systems.stackable_inventory import StackableInventory as _SI
        eng = _SI(registry)
        for it in self._items:
            if it is None:
                continue
            bid, count = it
            eng.add_item(f"mc2_block_{bid}", count)
        return eng
