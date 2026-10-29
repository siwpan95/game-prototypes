"""
装备/升级定义 — 从 JSON raw dict 构建，提供 cost/visibility 计算。
"""


class UpgradeDef:
    __slots__ = (
        "key", "name", "description_tpl", "tip",
        "costs", "visibilities", "limit",
        "per_second", "callback",
        "category", "era", "requires",
        "multiplier", "synergy_unlocked", "synergy_building",
        "power_gear", "empowers",
    )

    def __init__(self, raw: dict):
        self.key = raw["key"]
        self.name = raw["name"]
        self.description_tpl = raw["description"]
        self.tip = raw["tip"]
        self.costs = raw["costs"]
        self.visibilities = raw["visibilities"]
        self.limit = raw.get("limit", 0)
        self.per_second = raw.get("per_second", 0)
        self.callback = raw.get("callback", None)
        self.category = raw.get("category", "dps")
        self.era = raw.get("era", "stone")
        req = raw.get("requires")
        self.requires = (req["key"], req["level"]) if req else None
        # 引用暂存字符串，_load_defs 中解析
        self.multiplier = raw.get("multiplier", None)
        self.synergy_unlocked = raw.get("synergy_unlocked", None)
        self.synergy_building = raw.get("synergy_building", None)
        self.power_gear = raw.get("power_gear", None)
        self.empowers = raw.get("empowers", None)

    def get_cost(self, quantity: int) -> int:
        if self.limit and quantity < len(self.costs):
            return self.costs[quantity]
        if len(self.costs) == 1:
            return int(self.costs[0] * 1.15 ** quantity)
        return self.costs[-1]

    def is_visible(self, cumulative: float, quantity: int) -> bool:
        idx = min(quantity, len(self.visibilities) - 1)
        return cumulative >= self.visibilities[idx]

    def can_buy(self, quantity: int) -> bool:
        return self.limit == 0 or quantity < self.limit
