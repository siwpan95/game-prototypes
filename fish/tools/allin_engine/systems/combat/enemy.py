"""
敌人系统 — 敌人定义、战斗实例与意图轮转。

支持从 JSON 数据驱动加载敌人定义。
包含敌人模板（Enemy）、战斗实例（EnemyInstance）和意图系统。

使用方式:

    template = Enemy("goblin", "哥布林", hp=30, max_hp=30)
    instance = EnemyInstance(template)
    intent = instance.choose_intent()  # 循环获取意图
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any, Optional

from allin_engine.core.data_library import DataLibrary


# ---------------------------------------------------------------
# IntentType — 意图类型枚举
# ---------------------------------------------------------------

class IntentType(Enum):
    """敌人行动意图类型。"""

    # 基础
    ATTACK = "attack"           # 普通攻击
    BLOCK = "block"             # 防御/格挡
    BUFF = "buff"               # 自我强化

    # 特殊
    SWIFT = "swift"             # 迅捷（额外伤害）
    IGNORE_RING = "ignore_ring" # 无视蓝环
    COPY = "copy"               # 复制玩家上一张牌
    HIGH_PRESS = "high_press"   # 高压（AP 惩罚）
    STAGGER = "stagger"         # 踉跄（格挡减半）

    # 扩展
    HEAL = "heal"               # 治疗
    SUMMON = "summon"           # 召唤
    AOE = "aoe"                 # AOE 伤害
    DEBUFF = "debuff"           # 施加负面效果


# ---------------------------------------------------------------
# Intent — 单个意图
# ---------------------------------------------------------------

@dataclass
class Intent:
    """敌人行动意图。

    Attributes:
        name: 显示名称
        description: 意图描述
        damage: 造成的伤害
        effect_tag: 特殊效果标签
        metadata: 扩展属性
    """

    name: str = "攻击"
    description: str = ""
    damage: int = 5
    effect_tag: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict) -> "Intent":
        """从字典构建。"""
        return cls(
            name=data.get("name", "攻击"),
            description=data.get("description", ""),
            damage=data.get("damage", 5),
            effect_tag=data.get("effect_tag", ""),
            metadata=data.get("metadata", {}),
        )

    def to_dict(self) -> dict:
        """序列化为字典。"""
        return {
            "name": self.name,
            "description": self.description,
            "damage": self.damage,
            "effect_tag": self.effect_tag,
            "metadata": self.metadata,
        }


# ---------------------------------------------------------------
# Enemy — 敌人模板
# ---------------------------------------------------------------

@dataclass
class Enemy:
    """敌人模板定义。

    描述敌人的基础属性、意图列表等。
    通过 EnemyInstance 实例化后在战斗中使用。

    Attributes:
        id: 唯一标识符
        name: 显示名称
        hp: 生命值
        max_hp: 最大生命值
        armor: 护甲值
        is_boss: 是否为 Boss
        intents: 意图列表（战斗中将循环使用）
        metadata: 扩展属性
    """

    id: str
    name: str
    hp: int = 50
    max_hp: int = 50
    armor: int = 0
    is_boss: bool = False
    intents: list[Intent] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """序列化为字典。"""
        return {
            "id": self.id,
            "name": self.name,
            "hp": self.hp,
            "max_hp": self.max_hp,
            "armor": self.armor,
            "is_boss": self.is_boss,
            "intents": [i.to_dict() for i in self.intents],
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Enemy":
        """从字典反序列化。"""
        intents_data = data.get("intents", [])
        intents = [Intent.from_dict(i) for i in intents_data] if intents_data else []
        return cls(
            id=data["id"],
            name=data["name"],
            hp=data.get("hp", 50),
            max_hp=data.get("max_hp", 50),
            armor=data.get("armor", 0),
            is_boss=data.get("is_boss", False),
            intents=intents,
            metadata=data.get("metadata", {}),
        )

    def __repr__(self) -> str:
        boss_tag = "[BOSS]" if self.is_boss else ""
        return f"Enemy({self.id}: {self.name} HP={self.hp}/{self.max_hp} {boss_tag})"


# ---------------------------------------------------------------
# EnemyInstance — 敌人战斗实例
# ---------------------------------------------------------------

@dataclass
class EnemyInstance:
    """敌人在单场战斗中的实例。

    封装敌人 HP、意图轮转等战斗状态。
    意图按顺序循环使用。

    使用方式:

        template = EnemyLibrary().get_enemy("goblin")
        instance = EnemyInstance(template)
        intent = instance.choose_intent()
    """

    id: str
    name: str
    hp: int
    max_hp: int
    armor: int = 0
    is_boss: bool = False
    _intents: list[Intent] = field(default_factory=list)
    _intent_idx: int = 0

    def __init__(self, template: Enemy):
        """
        :param template: 敌人模板
        """
        self.id = template.id
        self.name = template.name
        self.hp = template.hp
        self.max_hp = template.max_hp
        self.armor = template.armor
        self.is_boss = template.is_boss
        # 意图列表（循环使用）
        self._intents: list[Intent] = list(template.intents)
        if not self._intents:
            self._intents = [Intent(name="攻击", damage=5)]
        self._intent_idx: int = 0

    # ---- 意图 ----

    def choose_intent(self) -> Intent:
        """选择本轮意图（循环推进）。"""
        intent = self._intents[self._intent_idx % len(self._intents)]
        self._intent_idx += 1
        return intent

    def peek_intent(self) -> Intent:
        """窥视下一轮意图（不推进指针）。"""
        return self._intents[self._intent_idx % len(self._intents)]

    def reset_intents(self) -> None:
        """重置意图指针到开头。"""
        self._intent_idx = 0

    @property
    def intents(self) -> list[Intent]:
        """返回所有意图列表。"""
        return list(self._intents)

    @property
    def current_intent_index(self) -> int:
        """当前意图索引。"""
        return self._intent_idx % len(self._intents)

    # ---- 生命值 ----

    @property
    def alive(self) -> bool:
        """敌人是否存活。"""
        return self.hp > 0

    @property
    def hp_percent(self) -> float:
        """当前 HP 百分比。"""
        return self.hp / self.max_hp if self.max_hp > 0 else 0.0

    def take_damage(self, amount: int) -> int:
        """受到伤害并返回实际伤害值。

        :param amount: 原始伤害值
        :returns: 实际造成的伤害（考虑护甲）
        """
        # 先扣护甲
        effective = max(0, amount - self.armor)
        if self.armor > 0:
            absorbed = min(self.armor, amount)
            self.armor -= absorbed
            effective = amount - absorbed
        else:
            effective = amount

        self.hp = max(0, self.hp - effective)
        return effective

    def heal(self, amount: int) -> int:
        """回复生命值。

        :returns: 实际回复量
        """
        before = self.hp
        self.hp = min(self.max_hp, self.hp + amount)
        return self.hp - before

    # ---- 序列化 ----

    def to_dict(self) -> dict:
        """序列化战斗状态（用于存档）。"""
        return {
            "id": self.id,
            "name": self.name,
            "hp": self.hp,
            "max_hp": self.max_hp,
            "armor": self.armor,
            "is_boss": self.is_boss,
            "intent_idx": self._intent_idx % len(self._intents),
        }

    def __repr__(self) -> str:
        status = "存活" if self.alive else "已击败"
        boss_tag = "[BOSS]" if self.is_boss else ""
        return (
            f"EnemyInstance({self.name} HP={self.hp}/{self.max_hp} "
            f"Armor={self.armor} {status} {boss_tag})"
        )


# ---------------------------------------------------------------
# EnemyLibrary — 敌人库（基于 DataLibrary）
# ---------------------------------------------------------------

class EnemyLibrary(DataLibrary[Enemy]):
    """敌人库 — 管理和检索所有可用的敌人模板。

    继承自 DataLibrary，支持从 JSON 文件/目录加载敌人定义。

    使用方式:

        lib = EnemyLibrary()
        lib.load_from_json("data/enemies/")
        template = lib.get_enemy("goblin")
        instance = EnemyInstance(template)
    """

    def __init__(self, logger: Any = None):
        super().__init__(
            factory=Enemy.from_dict,
            item_key="enemies",
            item_name="敌人",
            logger=logger,
        )

    # ── 查询（EnemyLibrary 特有接口） ──

    def get_enemy(self, enemy_id: str) -> Optional[Enemy]:
        """获取敌人模板。"""
        return self.get(enemy_id)

    def get_instance(self, enemy_id: str) -> Optional[EnemyInstance]:
        """直接创建敌人战斗实例。"""
        template = self._items.get(enemy_id)
        if template is None:
            return None
        return EnemyInstance(template)

    def has_enemy(self, enemy_id: str) -> bool:
        """敌人模板是否存在。"""
        return self.has(enemy_id)

    def list_enemies(self, category: str | None = None) -> list[Enemy]:
        """列出所有敌人（或按分类筛选）。

        :param category: 分类筛选（如 "boss", "normal", "elite"）
        """
        enemies = list(self._items.values())
        if category:
            enemies = [
                e for e in enemies
                if e.metadata.get("category") == category
            ]
        return enemies

    def list_bosses(self) -> list[Enemy]:
        """列出所有 Boss 敌人。"""
        return [e for e in self._items.values() if e.is_boss]

    @property
    def all_enemies(self) -> dict[str, Enemy]:
        """返回所有敌人模板（只读）。"""
        return self.all_items

    @classmethod
    def from_json(cls, source: str | Path) -> "EnemyLibrary":
        """从 JSON 创建 EnemyLibrary（兼容旧版 API）。"""
        lib = cls()
        lib.load_from_json(source)
        return lib
