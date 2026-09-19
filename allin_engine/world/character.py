"""
角色系统 — NPC/角色定义，含对话、战斗属性与交互状态。

支持叙事型（narrator）、盟友（ally）、敌人（enemy）、商人（merchant）、导师（mentor）等角色类型。
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Character:
    """一个 NPC 或角色。

    属性:
        char_id: 唯一标识
        name: 显示名称
        description: 角色描述
        role: 角色类型
        is_hostile: 是否敌对
        is_alive: 是否存活
        hp: 当前生命值
        max_hp: 最大生命值
        dialogues: 对话列表
        stats: 战斗/属性字典 { "attack": 10, "defense": 5, "speed": 3 }
        metadata: 扩展元数据
    """

    char_id: str
    name: str = ""
    description: str = ""
    role: str = "narrator"  # narrator | ally | enemy | merchant | mentor
    is_hostile: bool = False
    is_alive: bool = True
    hp: int = 50
    max_hp: int = 50
    dialogues: list[str] = field(default_factory=list)
    stats: dict[str, int] = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)

    # ================================================================
    # 角色类型判断
    # ================================================================

    @property
    def is_enemy(self) -> bool:
        """是否为敌人。"""
        return self.role == "enemy" or self.is_hostile

    @property
    def is_merchant(self) -> bool:
        """是否为商人。"""
        return self.role == "merchant"

    @property
    def is_mentor(self) -> bool:
        """是否为导师。"""
        return self.role == "mentor"

    @property
    def is_ally(self) -> bool:
        """是否为盟友。"""
        return self.role == "ally"

    # ================================================================
    # 状态操作
    # ================================================================

    def take_damage(self, amount: int) -> int:
        """受到伤害，返回实际扣血量。"""
        if not self.is_alive:
            return 0
        old = self.hp
        self.hp = max(0, self.hp - amount)
        actual = old - self.hp
        if self.hp <= 0:
            self.is_alive = False
        return actual

    def heal(self, amount: int) -> int:
        """恢复生命，返回实际回复量。"""
        if not self.is_alive:
            return 0
        old = self.hp
        self.hp = min(self.max_hp, self.hp + amount)
        return self.hp - old

    def get_stat(self, key: str) -> int:
        """获取指定属性值，不存在返回 0。"""
        return self.stats.get(key, 0)

    def set_stat(self, key: str, value: int) -> None:
        """设置指定属性值。"""
        self.stats[key] = value

    # ================================================================
    # 对话
    # ================================================================

    def get_dialogue(self, index: int) -> str | None:
        """获取指定索引的对话文本。"""
        if 0 <= index < len(self.dialogues):
            return self.dialogues[index]
        return None

    # ================================================================
    # 序列化
    # ================================================================

    def to_dict(self) -> dict:
        """序列化为字典。"""
        return {
            "char_id": self.char_id,
            "name": self.name,
            "description": self.description,
            "role": self.role,
            "is_hostile": self.is_hostile,
            "is_alive": self.is_alive,
            "hp": self.hp,
            "max_hp": self.max_hp,
            "dialogues": self.dialogues,
            "stats": self.stats,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Character":
        """从字典反序列化。"""
        return cls(
            char_id=data["char_id"],
            name=data.get("name", ""),
            description=data.get("description", ""),
            role=data.get("role", "narrator"),
            is_hostile=data.get("is_hostile", False),
            is_alive=data.get("is_alive", True),
            hp=data.get("hp", 50),
            max_hp=data.get("max_hp", 50),
            dialogues=data.get("dialogues", []),
            stats=data.get("stats", {}),
            metadata=data.get("metadata", {}),
        )

    def __repr__(self) -> str:
        alive = "存活" if self.is_alive else "死亡"
        return f"Character({self.char_id}, role={self.role}, {alive})"
