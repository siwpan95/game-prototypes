# -*- coding: utf-8 -*-
"""creatures.drops — 掉落表与驯服/繁殖占位（M4，T-M4-08 / R5 / R7）。

提供：
  - DROP_TABLE: 各生物死亡掉落（block_id → 数量），对应 M4 新增方块
    beef=9 / pork=10 / rotten_flesh=11。
  - roll_drops(kind): 返回该生物掉落（M4 固定，预留可扩展为加权随机）。
  - TAMING: 驯服/繁殖占位（enabled=False，接口预留，本里程碑不接入主循环）。

设计要点（架构 §7.6 / §7.8 / O12）：
  - 掉落物方块经 data/blocks.m4.json 注册（R4 约束 #2 模式），不改动地基 json。
  - 仅依赖 creatures.entity.CreatureKind；纯标准库，headless 可断言。
"""

from __future__ import annotations

from mcclone.creatures.entity import CreatureKind


# 掉落表：kind → [(block_id, count), ...]
DROP_TABLE: dict = {
    CreatureKind.COW: [(9, 2)],      # beef × 2
    CreatureKind.PIG: [(10, 2)],     # pork × 2
    CreatureKind.ZOMBIE: [(11, 1)],  # rotten_flesh × 1
}


def roll_drops(kind: CreatureKind) -> list:
    """返回某生物死亡时的掉落列表 [(block_id, count), ...]（稳定返回，无 RNG）。"""
    return list(DROP_TABLE.get(kind, []))


class _Taming:
    """驯服/繁殖占位（R7，P2）。

    本里程碑不接入主循环、不 emit CREATURE_TAMED；仅留接口扩展点。
    """

    enabled: bool = False

    @staticmethod
    def tame(creature) -> None:
        """驯服占位接口（未实现）。"""
        raise NotImplementedError("R7 驯服为占位功能，本里程碑未实现")

    @staticmethod
    def breed(a, b) -> None:
        """繁殖占位接口（未实现）。"""
        raise NotImplementedError("R7 繁殖为占位功能，本里程碑未实现")


# 对外占位对象（enabled=False）
TAMING = _Taming()
