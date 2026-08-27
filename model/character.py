"""角色与敌人数据模型（纯数据+业务逻辑，零UI依赖）"""
from typing import Optional


class Character:
    """玩家角色 / 基础角色类"""

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
        # 当前乘坐的战车引用（由外部设置）
        self.vehicle: Optional["Vehicle"] = None

    @property
    def attack(self):
        """攻击力 = 基础攻击 + 战车加成"""
        if self.vehicle and self.vehicle.is_alive():
            return self._base_attack + self.vehicle.attack
        return self._base_attack

    @attack.setter
    def attack(self, value):
        self._base_attack = value

    @property
    def defense(self):
        """防御力 = 基础防御 + 战车加成"""
        if self.vehicle and self.vehicle.is_alive():
            return self._base_defense + self.vehicle.defense
        return self._base_defense

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
