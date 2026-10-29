# -*- coding: utf-8 -*-
"""城镇被动交互服务 — 全自动不打断挂机

每经过一个地牢周期，城镇商店刷新商品。
全自动化：日志告知有新品，自动购买最优装备。
"""
from __future__ import annotations
import random
from typing import List, Dict, Optional


class TownService:
    """城镇被动交互"""

    MERCHANT_NAMES = [
        "独眼格鲁姆", "铁匠老陈", "流浪商人莉亚",
        "矮人锻造大师巴林", "神秘炼金术士", "精灵商贩艾琳",
        "退役冒险者汉克", "猫人商会的菲力克斯",
    ]

    def __init__(self):
        self._current_merchant = ""
        self._stock: List[dict] = []
        self._refresh_timer = 0.0
        self._refresh_interval = 300.0  # 每5分钟刷新一次
        self._shop_level = 1
        self._reputation = {"混沌阵营": 0, "自然阵营": 0, "秩序阵营": 0, "中立阵营": 0}

    def add_reputation(self, faction: str, amount: int = 1):
        """增加阵营声望（击杀该阵营敌人时调用）"""
        if faction in self._reputation:
            self._reputation[faction] += amount

    def get_discount(self, faction: str) -> float:
        """根据声望返回折扣率"""
        rep = self._reputation.get(faction, 0)
        return min(0.30, rep * 0.01)  # 最高30%折扣

    def should_refresh(self, dt: float) -> bool:
        self._refresh_timer += dt
        if self._refresh_timer >= self._refresh_interval:
            self._refresh_timer = 0.0
            return True
        return False

    def refresh_shop(self, character, item_service) -> List[str]:
        """刷新商店，返回日志列表"""
        msgs = []
        self._current_merchant = random.choice(self.MERCHANT_NAMES)
        self._stock = []

        # 根据等级生成商品（高级别=好品质）
        for _ in range(random.randint(2, 4)):
            loot = item_service.generate_loot(character.level)
            if loot:
                price = self._estimate_price(loot)
                self._stock.append({"item": loot, "price": price})

        msgs.append(f"[城镇] {self._current_merchant} 的商店上新了！")
        for s in self._stock:
            msgs.append(f"  → {s['item'].get_display_name()} — {s['price']}G")

        # 自动购买最优装备
        self._auto_buy(character, msgs)
        return msgs

    @staticmethod
    def _estimate_price(loot) -> int:
        """按物品类型估算商店价格。

        物品模型（Weapon/Armor/Accessory）没有统一的 stats 字典：
        武器看伤害、护甲看防御、饰品看加成总和，再叠加品质系数。
        """
        attack = getattr(loot, "damage", 0)
        defense = getattr(loot, "defense", 0)
        bonuses = getattr(loot, "bonuses", None)
        bonus_sum = sum(int(v) for v in bonuses.values()) if isinstance(bonuses, dict) else 0
        quality_tier = loot.quality.value[1] if hasattr(loot, "quality") else 0
        return max(10, int(attack * 15 + defense * 12 + bonus_sum * 10 + quality_tier * 20))

    def _auto_buy(self, character, msgs: list):
        """自动购买能穿的装备（不打断）"""
        for stock in self._stock:
            item = stock["item"]
            price = stock["price"]
            if character.gold >= price:
                if character.try_auto_equip(item):
                    character.gold -= price
                    msgs.append(f"[购买] 自动购入: {item.get_display_name()} (-{price}G)")

    def tick(self, dt: float, character, item_service) -> List[str]:
        """主 tick，返回日志列表"""
        msgs = []
        if self.should_refresh(dt) and character:
            msgs = self.refresh_shop(character, item_service)
            self._shop_level = max(1, character.level // 20 + 1)
        return msgs

    def to_dict(self) -> dict:
        return {
            "reputation": self._reputation,
            "shop_level": self._shop_level,
            "current_merchant": self._current_merchant,
        }

    def from_dict(self, data: dict):
        self._reputation = data.get("reputation", {})
        self._shop_level = data.get("shop_level", 1)
        self._current_merchant = data.get("current_merchant", "")
