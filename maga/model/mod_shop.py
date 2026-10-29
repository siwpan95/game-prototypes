"""战车改造店逻辑（纯业务，零UI依赖）

改造项目（均在城镇改造店花金币进行）：
1. 开炮孔：主炮/副炮/S-E 孔 +1，费用按已开数量翻倍，有上限
2. 底盘防御强化：+10/次，上限为底盘防御上限（defense_max）
3. 装甲片扩容：容量 +10/次
4. 更换引擎：按引擎价格购买（价格 0 的引擎不出售）

改造状态记录在 Vehicle 实例上（extra_*_slots / *_bonus），随存档持久化。
"""
from typing import Optional


class ModShop:
    """改造店 — 静态方法"""

    # 孔位上限
    MAIN_CAP = 2
    SUB_CAP = 3
    SE_CAP = 2

    # 费用基数
    HOLE_COST_BASE = 2000   # 开孔基础价（×2^已有孔数）
    DEF_COST_BASE = 1000    # 防御强化基础价（×等级数）
    PLATE_COST_BASE = 800   # 扩容基础价（×次数）
    DEF_STEP = 10           # 每次防御强化量
    PLATE_STEP = 10         # 每次扩容装甲片数

    # ── 费用查询 ──

    @staticmethod
    def hole_cost(vehicle, kind: str) -> Optional[int]:
        """开孔费用；已满返回 None"""
        count = ModShop._hole_count(vehicle, kind)
        if count is None or count >= ModShop._hole_cap(kind):
            return None
        return ModShop.HOLE_COST_BASE * (2 ** count)

    @staticmethod
    def defense_cost(vehicle) -> Optional[int]:
        """防御强化费用；已满返回 None"""
        levels = vehicle.chassis_defense_bonus // ModShop.DEF_STEP
        if vehicle.chassis.defense + vehicle.chassis_defense_bonus >= vehicle.chassis.defense_max:
            return None
        return ModShop.DEF_COST_BASE * (levels + 1)

    @staticmethod
    def plate_cost(vehicle) -> int:
        """装甲片扩容费用"""
        steps = vehicle.plates_capacity_bonus // ModShop.PLATE_STEP
        return ModShop.PLATE_COST_BASE * (steps + 1)

    # ── 执行改造（返回是否成功；金币由调用方扣） ──

    @staticmethod
    def add_hole(vehicle, kind: str) -> bool:
        cost = ModShop.hole_cost(vehicle, kind)
        if cost is None:
            return False
        if kind == "主炮":
            vehicle.extra_main_slots += 1
        elif kind == "副炮":
            vehicle.extra_sub_slots += 1
        elif kind == "SE":
            vehicle.extra_se_slots += 1
        else:
            return False
        return True

    @staticmethod
    def upgrade_defense(vehicle) -> bool:
        cost = ModShop.defense_cost(vehicle)
        if cost is None:
            return False
        # 不超过上限
        room = vehicle.chassis.defense_max - (vehicle.chassis.defense + vehicle.chassis_defense_bonus)
        vehicle.chassis_defense_bonus += min(ModShop.DEF_STEP, room)
        return True

    @staticmethod
    def expand_plates(vehicle) -> bool:
        vehicle.plates_capacity_bonus += ModShop.PLATE_STEP
        return True

    @staticmethod
    def change_engine(vehicle, engine) -> bool:
        """更换引擎（engine 为 EngineData）"""
        if engine is None:
            return False
        vehicle.engine = engine
        return True

    # ── 内部 ──

    @staticmethod
    def _cost_text(cost) -> str:
        """费用显示：None → 已满"""
        return "已满" if cost is None else f"{cost}G"

    @staticmethod
    def _hole_count(vehicle, kind: str) -> Optional[int]:
        if kind == "主炮":
            return vehicle.extra_main_slots
        if kind == "副炮":
            return vehicle.extra_sub_slots
        if kind == "SE":
            return vehicle.extra_se_slots
        return None

    @staticmethod
    def _hole_cap(kind: str) -> int:
        return {"主炮": ModShop.MAIN_CAP, "副炮": ModShop.SUB_CAP,
                "SE": ModShop.SE_CAP}.get(kind, 0)
