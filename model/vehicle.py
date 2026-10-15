"""战车数据模型"""


class Vehicle:
    """战车"""

    def __init__(self, vehicle_data: "VehicleData"):
        self.id = vehicle_data.id
        self.name = vehicle_data.name
        self.hp = vehicle_data.hp
        self.max_hp = vehicle_data.hp
        self.attack = vehicle_data.attack
        self.defense = vehicle_data.defense
        self.speed = vehicle_data.speed
        self.fuel = vehicle_data.fuel_capacity
        self.max_fuel = vehicle_data.fuel_capacity
        self.fuel_consumption = vehicle_data.fuel_consumption
        self.repair_cost = vehicle_data.repair_cost
        self.broken = False
        self.data = vehicle_data

    def is_alive(self) -> bool:
        return self.hp > 0

    def take_damage(self, damage: int) -> int:
        actual_damage = max(1, damage - self.defense // 2)
        self.hp -= actual_damage
        if self.hp < 0:
            self.hp = 0
            self.broken = True
        return actual_damage

    def consume_fuel(self) -> bool:
        """消耗燃料，返回是否还有燃料"""
        self.fuel -= self.fuel_consumption
        if self.fuel <= 0:
            self.fuel = 0
            return False
        return True

    def refuel(self, amount: int):
        self.fuel = min(self.max_fuel, self.fuel + amount)

    def repair(self):
        self.hp = self.max_hp
        self.broken = False

    # ── 存档序列化 ──

    def to_dict(self) -> dict:
        """序列化为可 JSON 存档的字典"""
        return {
            "id": self.id,
            "hp": self.hp,
            "fuel": self.fuel,
            "broken": self.broken,
        }

    @classmethod
    def from_dict(cls, d: dict, config) -> "Vehicle":
        """从存档字典重建战车；config 为 ConfigLoader"""
        vehicle_data = config.get_vehicle_by_id(d["id"])
        if vehicle_data is None:
            raise ValueError(f"存档引用了不存在的战车ID: {d['id']}")
        v = cls(vehicle_data)
        v.hp = d.get("hp", v.max_hp)
        v.fuel = d.get("fuel", v.max_fuel)
        v.broken = d.get("broken", False)
        return v
