"""
ECS Components — 纯数据组件，不含逻辑
"""

# ── 标签组件（无数据，仅用于查询过滤）──────────────────────────

class PlayerTag:
    """标记实体为玩家"""
    pass


class MonsterTag:
    """标记实体为怪物"""
    pass


# ── 数据组件 ───────────────────────────────────────────────────

class HPComponent:
    __slots__ = ("hp", "max_hp", "alive")

    def __init__(self, hp: int, max_hp: int | None = None) -> None:
        self.hp: int = hp
        self.max_hp: int = max_hp if max_hp is not None else hp
        self.alive: bool = True


class AttackComponent:
    __slots__ = ("atk_base", "crit_chance", "dodge_chance")

    def __init__(self, atk_base: int, crit_chance: float = 0.12,
                 dodge_chance: float = 0.08) -> None:
        self.atk_base: int = atk_base
        self.crit_chance: float = crit_chance
        self.dodge_chance: float = dodge_chance


class ExpComponent:
    __slots__ = ("exp", "exp_pool", "level", "level_threshold_fn", "rest_cost")

    def __init__(self, level: int = 1, exp: int = 0,
                 exp_pool: int = 0, rest_cost: int = 5) -> None:
        self.exp: int = exp
        self.exp_pool: int = exp_pool
        self.level: int = level
        # 升级所需经验函数，默认 level * 30
        self.level_threshold_fn = lambda lv: lv * 30
        self.rest_cost: int = rest_cost

    def threshold(self) -> int:
        return self.level_threshold_fn(self.level)


class RespawnComponent:
    __slots__ = ("respawn_timer", "respawn_time")

    def __init__(self, respawn_time: int = 5) -> None:
        self.respawn_timer: int = 0
        self.respawn_time: int = respawn_time


class MonsterComponent:
    __slots__ = ("name", "exp_reward", "affix")

    def __init__(self, name: str, exp_reward: int, affix: str | None = None) -> None:
        self.name: str = name
        self.exp_reward: int = exp_reward
        self.affix: str | None = affix


class NameComponent:
    """通用名称组件（玩家/怪物共用）"""
    __slots__ = ("name",)

    def __init__(self, name: str) -> None:
        self.name: str = name


# ── 装备组件 ───────────────────────────────────────────────────

class EquipmentComponent:
    """装备槽组件：挂在玩家实体上，存储已装备物品列表"""
    __slots__ = ("equipped", "max_slots")

    def __init__(self, max_slots: int = 4) -> None:
        self.equipped: list[dict] = []   # [equip_dict, ...]
        self.max_slots: int = max_slots

    def equip(self, equip: dict) -> bool:
        if len(self.equipped) >= self.max_slots:
            return False
        self.equipped.append(equip)
        return True

    def unequip(self, idx: int) -> dict | None:
        """卸下第 idx 件装备，返回装备 dict 或 None"""
        if 0 <= idx < len(self.equipped):
            return self.equipped.pop(idx)
        return None

    def swap(self, idx: int, new_equip: dict) -> dict | None:
        """替换第 idx 件装备，返回被替换的旧装备"""
        if 0 <= idx < len(self.equipped):
            old = self.equipped[idx]
            self.equipped[idx] = new_equip
            return old
        return None

    def total_bonus(self, key: str) -> float:
        """计算所有装备的某个属性加成总和"""
        total = 0.0
        for eq in self.equipped:
            total += eq.get(key, 0)
        return total


class BackpackComponent:
    """背包组件：挂在玩家实体上，存储未装备的备用物品"""
    __slots__ = ("items", "max_slots")

    def __init__(self, max_slots: int = 12) -> None:
        self.items: list[dict] = []  # [equip_dict, ...]
        self.max_slots: int = max_slots

    def add(self, equip: dict) -> bool:
        """放入背包，成功返回 True，满则 False"""
        if len(self.items) >= self.max_slots:
            return False
        self.items.append(equip)
        return True

    def take(self, idx: int) -> dict | None:
        """取出第 idx 件物品"""
        if 0 <= idx < len(self.items):
            return self.items.pop(idx)
        return None


# ── 状态效果组件 ──────────────────────────────────────────────

class StatusEffectComponent:
    """临时状态效果：挂在怪物或玩家实体上"""
    __slots__ = ("effects",)

    def __init__(self) -> None:
        # effects: list[dict] — {"type": str, "damage": int, "turns": int, "label": str}
        self.effects: list[dict] = []

    def add(self, effect_type: str, damage: int = 0,
            turns: int = 1, label: str = "") -> None:
        self.effects.append({
            "type": effect_type,
            "damage": damage,
            "turns": turns,
            "label": label,
        })

    def tick(self) -> list[dict]:
        """递减回合数，返回已过期效果列表"""
        expired: list[dict] = []
        for ef in self.effects:
            ef["turns"] -= 1
            if ef["turns"] <= 0:
                expired.append(ef)
        # 移除已过期
        self.effects = [e for e in self.effects if e["turns"] > 0]
        return expired


class BuffComponent:
    """增益/减益组件：临时属性调整"""
    __slots__ = ("dodge_bonus", "atk_bonus", "damage_reduction",
                 "turns_remaining")

    def __init__(self) -> None:
        self.dodge_bonus: float = 0.0
        self.atk_bonus: float = 0.0
        self.damage_reduction: int = 0
        self.turns_remaining: int = 0

    def apply(self, dodge: float = 0.0, atk: float = 0.0,
              dr: int = 0, turns: int = 1) -> None:
        self.dodge_bonus = dodge
        self.atk_bonus = atk
        self.damage_reduction = dr
        self.turns_remaining = turns

    def tick(self) -> bool:
        """递减回合，返回是否已过期"""
        if self.turns_remaining > 0:
            self.turns_remaining -= 1
        if self.turns_remaining <= 0:
            self.reset()
            return True
        return False

    def reset(self) -> None:
        self.dodge_bonus = 0.0
        self.atk_bonus = 0.0
        self.damage_reduction = 0
        self.turns_remaining = 0
