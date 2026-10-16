"""战车数据模型（MM1 式部件化）

一辆战车 = 底盘 + 引擎 + C装置 + 武器（主炮/副炮/S-E）+ 装甲片。
- 攻击力 = 全部武器攻击之和
- 防御力 = 底盘防御 + 引擎防御 + C装置防御
- 载重由引擎决定；超重无法移动
- 受击先消耗装甲片（SP），归零后才扣底盘耐久
"""
import math


# 装甲片常量：每片重量（吨）与吸收伤害
PLATE_WEIGHT = 0.1
PLATE_ABSORB = 10


class Vehicle:
    """战车（部件化运行时实例）"""

    def __init__(self, vehicle_data: "VehicleData", config):
        self.data = vehicle_data
        self.id = vehicle_data.id
        self.name = vehicle_data.name

        chassis = config.get_chassis_by_id(vehicle_data.chassis_id)
        engine = config.get_engine_by_id(vehicle_data.engine_id)
        cunit = config.get_cunit_by_id(vehicle_data.cunit_id)
        if chassis is None or engine is None or cunit is None:
            raise ValueError(
                f"战车 {vehicle_data.name} 的部件引用缺失"
                f"（底盘 {vehicle_data.chassis_id} / 引擎 {vehicle_data.engine_id}"
                f" / C装置 {vehicle_data.cunit_id}）"
            )
        self.chassis = chassis
        self.engine = engine
        self.cunit = cunit

        self.main_weapons = [config.get_weapon_by_id(i)
                             for i in vehicle_data.main_weapon_ids]
        self.sub_weapons = [config.get_weapon_by_id(i)
                            for i in vehicle_data.sub_weapon_ids]
        self.se_weapons = [config.get_weapon_by_id(i)
                           for i in vehicle_data.se_weapon_ids]
        # 过滤掉配置里不存在的武器 ID
        self.main_weapons = [w for w in self.main_weapons if w is not None]
        self.sub_weapons = [w for w in self.sub_weapons if w is not None]
        self.se_weapons = [w for w in self.se_weapons if w is not None]

        self.armor_plates = vehicle_data.armor_plates
        self.max_plates = vehicle_data.armor_plates
        # 防御姿态倍率（战斗中临时提升，1.0 = 常态）
        self.defense_multiplier = 1.0
        # 战斗攻击倍率（雷达等道具，战斗结束后重置）
        self.battle_atk_mult = 1.0

        # ── 改造状态（改造店升级，随存档持久化） ──
        self.extra_main_slots = 0   # 额外主炮孔
        self.extra_sub_slots = 0    # 额外副炮孔
        self.extra_se_slots = 0     # 额外 S-E 孔
        self.chassis_defense_bonus = 0  # 底盘防御强化值
        self.plates_capacity_bonus = 0  # 装甲片扩容值

        self.max_hp = chassis.durability
        self.hp = chassis.durability
        self.fuel = vehicle_data.fuel_capacity
        self.max_fuel = vehicle_data.fuel_capacity
        self.fuel_consumption = vehicle_data.fuel_consumption
        self.repair_cost = vehicle_data.repair_cost
        self.broken = False

    # ── 派生属性 ──

    @property
    def attack(self) -> int:
        """攻击力 = 全部武器攻击之和 × 战斗倍率（雷达等道具）"""
        return int(sum(w.attack for w in self.all_weapons())
                   * self.battle_atk_mult)

    @property
    def defense(self) -> int:
        """防御力 =（底盘 + 强化值 + 引擎 + C装置）× 防御姿态倍率"""
        base = (self.chassis.defense + self.chassis_defense_bonus
                + self.engine.defense + self.cunit.defense)
        return int(base * self.defense_multiplier)

    # ── 孔位（底盘基础孔 + 改造开孔） ──

    @property
    def main_slots(self) -> int:
        return self.chassis.main_slots + self.extra_main_slots

    @property
    def sub_slots(self) -> int:
        return self.chassis.sub_slots + self.extra_sub_slots

    @property
    def se_slots(self) -> int:
        return self.chassis.se_slots + self.extra_se_slots

    def can_equip(self, weapon) -> bool:
        """武器是否能装上（孔位是否足够）"""
        if weapon is None:
            return False
        if weapon.type == "主炮":
            return len(self.main_weapons) < self.main_slots
        if weapon.type == "副炮":
            return len(self.sub_weapons) < self.sub_slots
        if weapon.type == "SE":
            return len(self.se_weapons) < self.se_slots
        return False

    def equip_weapon(self, weapon) -> bool:
        """安装武器（孔位不足返回 False）"""
        if not self.can_equip(weapon):
            return False
        if weapon.type == "主炮":
            self.main_weapons.append(weapon)
        elif weapon.type == "副炮":
            self.sub_weapons.append(weapon)
        elif weapon.type == "SE":
            self.se_weapons.append(weapon)
        else:
            return False
        return True

    def unequip_weapon(self, kind: str, index: int):
        """卸下武器，返回卸下的 WeaponData（没有则 None）"""
        bucket = {"主炮": self.main_weapons, "副炮": self.sub_weapons,
                  "SE": self.se_weapons}.get(kind)
        if bucket is None or not (0 <= index < len(bucket)):
            return None
        return bucket.pop(index)

    @property
    def speed(self) -> int:
        """机动性：底盘越轻、引擎动力越足越快（影响逃跑成功率）"""
        return max(1, int(60 - self.chassis.weight + self.engine.load / 2))

    @property
    def sp(self) -> int:
        """当前装甲片总吸收量"""
        return self.armor_plates * PLATE_ABSORB

    @property
    def max_sp(self) -> int:
        """装甲片容量总吸收量"""
        return self.max_plates * PLATE_ABSORB

    @property
    def max_plates(self) -> int:
        return self._base_max_plates + self.plates_capacity_bonus

    @max_plates.setter
    def max_plates(self, value):
        self._base_max_plates = value

    def all_weapons(self) -> list:
        return list(self.main_weapons) + list(self.sub_weapons) + list(self.se_weapons)

    def weapon_summary(self) -> str:
        parts = []
        if self.main_weapons:
            parts.append("主炮: " + "/".join(w.name for w in self.main_weapons))
        if self.sub_weapons:
            parts.append("副炮: " + "/".join(w.name for w in self.sub_weapons))
        if self.se_weapons:
            parts.append("SE: " + "/".join(w.name for w in self.se_weapons))
        return "，".join(parts) if parts else "无武器"

    # ── 重量 / 载重 ──

    def total_weight(self) -> float:
        """战斗全重（吨）"""
        weight = (self.chassis.weight + self.engine.weight + self.cunit.weight
                  + sum(w.weight for w in self.all_weapons())
                  + self.armor_plates * PLATE_WEIGHT)
        return round(weight, 2)

    def load_capacity(self) -> float:
        return self.engine.load

    def is_overweight(self) -> bool:
        """超重（无法移动）"""
        return self.total_weight() > self.load_capacity()

    # ── 战斗 / 消耗 ──

    def is_alive(self) -> bool:
        return self.hp > 0

    def take_damage(self, damage: int) -> int:
        """受到伤害：先耗装甲片，归零后扣耐久（防御减伤）。

        返回实际吃掉的总伤害（装甲片吸收 + 耐久损失）。
        """
        if not self.is_alive() or damage <= 0:
            return 0

        sp = self.sp
        if damage <= sp:
            # 只耗装甲片
            remaining_sp = sp - damage
            self.armor_plates = math.ceil(remaining_sp / PLATE_ABSORB)
            return damage

        # SP 耗尽，防御开始减伤
        self.armor_plates = 0
        actual = max(1, damage - sp - self.defense // 2)
        self.hp -= actual
        if self.hp <= 0:
            self.hp = 0
            self.broken = True
        return sp + actual

    def consume_fuel(self) -> bool:
        """消耗燃料，返回是否还有燃料"""
        self.fuel -= self.fuel_consumption
        if self.fuel <= 0:
            self.fuel = 0
            return False
        return True

    def refuel(self, amount):
        self.fuel = min(self.max_fuel, self.fuel + amount)

    def repair(self):
        """修理：恢复耐久、清除损坏、补满装甲片"""
        self.hp = self.max_hp
        self.broken = False
        self.armor_plates = self.max_plates

    def missing_plates(self) -> int:
        return max(0, self.max_plates - self.armor_plates)

    # ── 存档序列化 ──

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "engine_id": self.engine.id,  # 改造店可能更换过引擎
            "hp": self.hp,
            "fuel": self.fuel,
            "armor_plates": self.armor_plates,
            "broken": self.broken,
            "extra_main_slots": self.extra_main_slots,
            "extra_sub_slots": self.extra_sub_slots,
            "extra_se_slots": self.extra_se_slots,
            "chassis_defense_bonus": self.chassis_defense_bonus,
            "plates_capacity_bonus": self.plates_capacity_bonus,
        }

    @classmethod
    def from_dict(cls, d: dict, config) -> "Vehicle":
        vehicle_data = config.get_vehicle_by_id(d["id"])
        if vehicle_data is None:
            raise ValueError(f"存档引用了不存在的战车ID: {d['id']}")
        v = cls(vehicle_data, config)
        # 改造店更换过的引擎优先于配置默认值
        engine_id = d.get("engine_id")
        if engine_id is not None and engine_id != v.engine.id:
            engine = config.get_engine_by_id(engine_id)
            if engine is not None:
                v.engine = engine
        v.hp = d.get("hp", v.max_hp)
        v.fuel = d.get("fuel", v.max_fuel)
        v.armor_plates = d.get("armor_plates", v.max_plates)
        v.broken = d.get("broken", False)
        v.extra_main_slots = d.get("extra_main_slots", 0)
        v.extra_sub_slots = d.get("extra_sub_slots", 0)
        v.extra_se_slots = d.get("extra_se_slots", 0)
        v.chassis_defense_bonus = d.get("chassis_defense_bonus", 0)
        v.plates_capacity_bonus = d.get("plates_capacity_bonus", 0)
        return v
