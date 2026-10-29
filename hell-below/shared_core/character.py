"""Character — NPC/角色定义。"""

from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class Character:
    """一个 NPC 或角色。"""
    char_id: str
    name: str
    description: str
    role: str = "narrator"  # narrator, ally, enemy, merchant, mentor
    dialogues: list[str] = field(default_factory=list)
    is_hostile: bool = False
    is_alive: bool = True
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "char_id": self.char_id, "name": self.name,
            "description": self.description, "role": self.role,
            "dialogues": self.dialogues,
            "is_hostile": self.is_hostile, "is_alive": self.is_alive,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Character":
        return cls(
            char_id=data["char_id"], name=data["name"],
            description=data["description"],
            role=data.get("role", "narrator"),
            dialogues=data.get("dialogues", []),
            is_hostile=data.get("is_hostile", False),
            is_alive=data.get("is_alive", True),
            metadata=data.get("metadata", {}),
        )
