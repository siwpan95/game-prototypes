"""角色与敌人数据模型（纯数据+业务逻辑，零UI依赖）"""
from typing import Optional

from .item import Item
from .skill import Skill


class Character:
    """玩家角色 / 基础角色类"""

    # 装备槽位顺序（物品栏/面板展示用）
    EQUIP_SLOTS = ("武器", "头", "身", "手", "鞋")

    def __init__(self, name: str, hp: int, max_hp: int,
                 attack: int, defense: int, speed: int):
        self.name = name
        self.hp = hp
        self.max_hp = max_hp
        self._base_attack = attack
        self._base_defense = defense
        self._base_speed = speed
        self.level = 1
        self.exp = 0
        self.exp_to_next = 100
        self.skills = []  # list[Skill]
        self.equipment = {}  # dict[槽位名 -> Item]，人类装备
        # 当前乘坐的战车引用（由外部设置）
        self.vehicle: Optional["Vehicle"] = None

    @property
    def attack(self):
        """攻击力 = 基础攻击 + 战车加成 + 武器加成"""
        total = self._base_attack
        if self.vehicle and self.vehicle.is_alive():
            total += self.vehicle.attack
        weapon = self.equipment.get("武器")
        if weapon is not None:
            total += weapon.effect_value
        return total

    @attack.setter
    def attack(self, value):
        self._base_attack = value

    @property
    def defense(self):
        """防御力 = 基础防御 + 战车加成 + 各防具加成"""
        total = self._base_defense
        if self.vehicle and self.vehicle.is_alive():
            total += self.vehicle.defense
        for slot, item in self.equipment.items():
            if slot != "武器":
                total += item.effect_value
        return total

    @defense.setter
    def defense(self, value):
        self._base_defense = value

    @property
    def speed(self):
        """速度 = 基础速度 + 战车加成"""
        if self.vehicle and self.vehicle.is_alive():
            return self._base_speed + self.vehicle.speed
        return self._base_speed

    @speed.setter
    def speed(self, value):
        self._base_speed = value

    def learn_skill(self, skill: "Skill"):
        """学习技能（不重复学习）"""
        if skill.id not in [s.id for s in self.skills]:
            self.skills.append(skill)

    # ── 装备 ──

    def equip(self, item: "Item") -> Optional["Item"]:
        """装备物品，返回被换下的旧装备（没有则 None）

        非装备类物品返回 None 且不装入槽位。
        """
        slot = getattr(item.data, "equip_slot", "") if item.data else ""
        if not slot:
            return None
        old = self.equipment.get(slot)
        self.equipment[slot] = item
        return old

    def unequip(self, slot: str) -> Optional["Item"]:
        """卸下指定槽位的装备，返回卸下的物品（没有则 None）"""
        return self.equipment.pop(slot, None)

    def equipped_slots(self) -> list:
        """按固定顺序返回已装备的 (槽位, Item) 列表"""
        return [(slot, self.equipment[slot])
                for slot in self.EQUIP_SLOTS if slot in self.equipment]

    def is_alive(self) -> bool:
        return self.hp > 0

    def take_damage(self, damage: int) -> int:
        """造成伤害，返回实际伤害值（战车先承受伤害）"""
        actual_damage = max(1, damage - self.defense // 2)
        # 如果有战车且战车存活，战车先承受伤害
        if self.vehicle and self.vehicle.is_alive():
            vehicle_dmg = actual_damage // 2
            self.vehicle.take_damage(vehicle_dmg)
            actual_damage -= vehicle_dmg
        self.hp -= actual_damage
        if self.hp < 0:
            self.hp = 0
        return actual_damage

    def heal(self, amount: int):
        self.hp = min(self.max_hp, self.hp + amount)

    def gain_exp(self, exp: int) -> bool:
        """获得经验值，返回是否升级"""
        self.exp += exp
        if self.exp >= self.exp_to_next:
            self.level_up()
            return True
        return False

    def level_up(self):
        self.level += 1
        self.exp -= self.exp_to_next
        self.exp_to_next = int(self.exp_to_next * 1.5)
        self.max_hp += 10
        self._base_attack += 3
        self._base_defense += 2
        self._base_speed += 1
        self.hp = self.max_hp

    # ── 存档序列化 ──

    def to_dict(self) -> dict:
        """序列化为可 JSON 存档的字典"""
        return {
            "name": self.name,
            "hp": self.hp,
            "max_hp": self.max_hp,
            "base_attack": self._base_attack,
            "base_defense": self._base_defense,
            "base_speed": self._base_speed,
            "level": self.level,
            "exp": self.exp,
            "exp_to_next": self.exp_to_next,
            "skills": [s.id for s in self.skills],
            "equipment": {slot: it.id for slot, it in self.equipment.items()},
        }

    @classmethod
    def from_dict(cls, d: dict, config) -> "Character":
        """从存档字典重建角色；config 为 ConfigLoader"""
        c = cls(
            d["name"], d["max_hp"], d["max_hp"],
            d["base_attack"], d["base_defense"], d["base_speed"],
        )
        c.hp = d.get("hp", c.max_hp)
        c.level = d.get("level", 1)
        c.exp = d.get("exp", 0)
        c.exp_to_next = d.get("exp_to_next", 100)
        for skill_id in d.get("skills", []):
            skill_data = config.get_skill_by_id(skill_id)
            if skill_data is not None:
                c.learn_skill(Skill(skill_data))
        for slot, item_id in d.get("equipment", {}).items():
            item_data = config.get_item_by_id(item_id)
            if item_data is not None:
                c.equipment[slot] = Item(item_data)
        return c


class Enemy(Character):
    """敌人角色"""

    def __init__(self, enemy_data: "EnemyData"):
        super().__init__(
            enemy_data.name,
            enemy_data.hp,
            enemy_data.hp,
            enemy_data.attack,
            enemy_data.defense,
            enemy_data.speed,
        )
        self.exp_reward = enemy_data.exp_reward
        self.gold_reward = enemy_data.gold_reward
        self.data = enemy_data
