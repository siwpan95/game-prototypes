# -*- coding: utf-8 -*-
"""游戏状态引擎 — 存档/读档/状态管理 + 招募 + 消耗品 + 事件"""

import json
import os
import random
import hashlib
from typing import List, Optional, Tuple, Dict

from core.config import SAVE_FILE, MAX_PARTY_SIZE, INN_COST
from core.models import (Adventurer, Dungeon, JobDef, Monster, Skill, Equipment,
                          Race, Consumable, ExploreEvent)
from data.loader import get_loader


class GameEngine:
    """管理游戏运行时状态"""

    def __init__(self):
        self.gold: int = 100
        self.party: List[Adventurer] = []
        self.inventory: List[str] = []           # 装备名列表
        self.consumables: Dict[str, int] = {}    # 消耗品名→数量
        self.current_dungeon: Optional[Dungeon] = None
        self.current_floor: int = 0
        self.exploring: bool = False
        self.between_floors: bool = False         # 楼层间暂停
        self.battle_log: List[str] = []
        self.max_log_lines: int = 150
        self.current_monster_emoji: str = "👾"
        self.unlocked_dungeons: int = 1
        self.total_monsters_killed: int = 0
        self.total_treasures_found: int = 0
        self.total_events_triggered: int = 0
        self.floor_buffs: Dict[str, int] = {}    # 楼层buff(药剂等)
        self.market_multiplier: float = 1.0        # 市场价格波动系数
        self._market_msg: str = ""                  # 市场波动说明

    # ================================================================
    #  招募冒险者
    # ================================================================
    def recruit(self, name: str, job_key: str, race_key: str = "人类",
                stat_overrides: dict = None) -> Optional[Adventurer]:
        """在酒馆招募一名冒险者。返回 Adventurer 或 None(队伍已满)
        stat_overrides: 可选属性覆盖 {"hp":50,"atk":12,...}，来自掷骰结果
        """
        if len(self.party) >= MAX_PARTY_SIZE:
            return None

        loader = get_loader()
        job = loader.jobs.get(job_key)
        if job is None:
            return None

        race = loader.races.get(race_key, loader.races.get("人类"))

        a = Adventurer(
            name=name, job_key=job_key, race_key=race_key, level=1,
            max_hp=job.base_hp, hp=job.base_hp,
            max_mp=50, mp=50,
            atk=job.base_atk, def_=job.base_def, spd=job.base_spd,
        )
        # 应用种族修正
        if race:
            a.max_hp += race.hp_mod
            a.hp = a.max_hp
            a.atk += race.atk_mod
            a.def_ += race.def_mod
            a.spd += race.spd_mod
            a.max_mp += race.mp_mod
            a.mp = a.max_mp

        # 应用掷骰属性覆盖
        if stat_overrides:
            if "hp" in stat_overrides:
                a.max_hp = stat_overrides["hp"]
                a.hp = stat_overrides["hp"]
            if "mp" in stat_overrides:
                a.max_mp = stat_overrides["mp"]
                a.mp = stat_overrides["mp"]
            if "atk" in stat_overrides:
                a.atk = stat_overrides["atk"]
            if "def" in stat_overrides:
                a.def_ = stat_overrides["def"]
            if "spd" in stat_overrides:
                a.spd = stat_overrides["spd"]

        # 初始技能
        a.skills = [sk for sk in job.initial_skills if sk in loader.skills]

        self.party.append(a)
        return a

    def dismiss(self, idx: int) -> bool:
        """解雇冒险者"""
        if 0 <= idx < len(self.party):
            a = self.party.pop(idx)
            # 卸下装备放入背包
            for eq_name in a.equipment.values():
                if eq_name:
                    self.inventory.append(eq_name)
            return True
        return False

    # ================================================================
    #  属性计算
    # ================================================================
    def _recalc_all_stats(self):
        loader = get_loader()
        for a in self.party:
            job = loader.jobs.get(a.job_key)
            race = loader.races.get(a.race_key)
            if job is None:
                continue
            a.max_hp = job.base_hp + (a.level - 1) * 12 + (race.hp_mod if race else 0)
            a.max_mp = 50 + (a.level - 1) * 5 + (race.mp_mod if race else 0)
            a.atk = job.base_atk + (a.level - 1) * 3 + (race.atk_mod if race else 0)
            a.def_ = job.base_def + (a.level - 1) * 2 + (race.def_mod if race else 0)
            a.spd = job.base_spd + (a.level - 1) * 1 + (race.spd_mod if race else 0)
            a.exp_to_next = a.level * 100
            a.hp = min(a.hp, self._full_hp(a))
            a.mp = min(a.mp, a.max_mp)

    def _eq_bonus(self, a: Adventurer, attr: str) -> int:
        loader = get_loader()
        total = 0
        for eq_name in a.equipment.values():
            if eq_name and eq_name in loader.equipment:
                eq = loader.equipment[eq_name]
                total += getattr(eq, attr, 0)
        return total

    def _full_hp(self, a: Adventurer) -> int:
        return a.max_hp + self._eq_bonus(a, "hp_bonus")

    def full_atk(self, a: Adventurer) -> int:
        return a.atk + self._eq_bonus(a, "atk_bonus")

    def full_def(self, a: Adventurer) -> int:
        return a.def_ + self._eq_bonus(a, "def_bonus")

    def full_spd(self, a: Adventurer) -> int:
        return a.spd + self._eq_bonus(a, "spd_bonus")

    def hp_pct(self, a: Adventurer) -> float:
        fh = self._full_hp(a)
        return a.hp / fh if fh > 0 else 0

    # ================================================================
    #  装备操作
    # ================================================================
    def equip(self, char_idx: int, item_name: str) -> bool:
        loader = get_loader()
        a = self.party[char_idx]
        if item_name not in self.inventory:
            return False
        eq = loader.equipment.get(item_name)
        if eq is None:
            return False
        if a.equipment.get(eq.slot):
            self.inventory.append(a.equipment[eq.slot])
        a.equipment[eq.slot] = item_name
        self.inventory.remove(item_name)
        return True

    def unequip(self, char_idx: int, slot: str) -> bool:
        a = self.party[char_idx]
        eq = a.equipment.get(slot)
        if eq:
            self.inventory.append(eq)
            a.equipment[slot] = None
            return True
        return False

    # ================================================================
    #  消耗品
    # ================================================================
    def add_consumable(self, name: str, qty: int = 1):
        self.consumables[name] = self.consumables.get(name, 0) + qty

    def use_consumable(self, name: str, target_idx: int = 0) -> Tuple[bool, str]:
        """使用消耗品。返回 (成功?, 消息)"""
        loader = get_loader()
        c = loader.consumables.get(name)
        if c is None or self.consumables.get(name, 0) <= 0:
            return False, "没有该物品"

        self.consumables[name] -= 1
        if self.consumables[name] <= 0:
            del self.consumables[name]

        if c.item_type == "heal":
            if 0 <= target_idx < len(self.party):
                a = self.party[target_idx]
                max_heal = self._full_hp(a) - a.hp
                if max_heal <= 0:
                    return False, f"{a.name} HP 已满，无需治疗"
                healed = min(c.effect_value, max_heal)
                a.hp += healed
                return True, f"{a.name} 使用 {c.name}，恢复 {healed} HP"
            return False, "无效目标"

        elif c.item_type == "mp_restore":
            if 0 <= target_idx < len(self.party):
                a = self.party[target_idx]
                restored = min(c.effect_value, a.max_mp - a.mp)
                a.mp += restored
                return True, f"{a.name} 使用 {c.name}，恢复 {restored} MP"
            return False, "无效目标"

        elif c.item_type == "revive":
            if 0 <= target_idx < len(self.party):
                a = self.party[target_idx]
                if a.hp > 0 and not a.dead:
                    return False, f"{a.name} 还活着"
                a.dead = False
                a.hp = self._full_hp(a) // 2
                a.mp = a.max_mp // 2
                return True, f"{a.name} 复活了！"
            return False, "无效目标"

        elif c.item_type == "buff":
            self.floor_buffs[name] = c.effect_value
            return True, f"使用 {c.name}：下次战斗全队 ATK+{c.effect_value}%"

        elif c.item_type == "cleanse":
            return True, f"使用 {c.name}，解除异常状态"

        return False, f"未知物品类型: {c.item_type}"

    def clear_floor_buffs(self):
        self.floor_buffs = {}

    # ================================================================
    #  市场价格波动
    # ================================================================
    def refresh_market(self) -> str:
        """刷新市场波动系数。返回市场状态描述"""
        import random as _random

        # 1. 进度波动力: 已解锁地下城越多，物价轻微上涨
        progress_factor = 1.0 + (self.unlocked_dungeons - 1) * 0.04

        # 2. 金币通胀: 玩家金币越多，物价越高 (cap 1.3)
        gold_factor = min(1.3, 1.0 + (self.gold / 5000) * 0.3)

        # 3. 随机波动力: ±18%
        random_factor = _random.uniform(0.82, 1.18)

        self.market_multiplier = round(progress_factor * gold_factor * random_factor, 3)

        # 生成市场状态消息
        if self.market_multiplier > 1.15:
            self._market_msg = "📈 市场繁荣，物价上涨！"
        elif self.market_multiplier > 1.05:
            self._market_msg = "📊 物价轻微走高"
        elif self.market_multiplier > 0.95:
            self._market_msg = "📊 市场稳定，物价正常"
        elif self.market_multiplier > 0.85:
            self._market_msg = "📉 商队剩余物资打折中！"
        else:
            self._market_msg = "📉 商队大清仓！物价暴跌！"

        return self._market_msg

    @staticmethod
    def _item_base_price(item) -> int:
        """获取物品的基础价格（装备用 price 属性，消耗品用 base_price）"""
        return item.base_price if hasattr(item, 'base_price') else item.price

    def get_buy_price(self, item) -> int:
        """动态买入价格 = 基础价格 × 市场波动系数"""
        base = self._item_base_price(item)
        return max(1, int(base * self.market_multiplier))

    def get_sell_price(self, item) -> int:
        """动态卖出价格 = 买入价格 × 60%（市场波动传导到卖出）"""
        return max(1, int(self.get_buy_price(item) * 0.6))

    def get_market_status(self) -> str:
        return self._market_msg

    # ================================================================
    #  旅馆
    # ================================================================
    def inn_rest(self) -> bool:
        if self.gold < INN_COST:
            return False
        self.gold -= INN_COST
        for a in self.party:
            a.hp = self._full_hp(a)
            a.mp = a.max_mp
            a.dead = False
        return True

    # ================================================================
    #  升级
    # ================================================================
    def grant_exp(self, exp: int) -> List[str]:
        msgs = []
        alive = [a for a in self.party if a.is_alive()]
        if not alive:
            return msgs
        per = exp // len(alive)
        for a in alive:
            a.exp += per
            while a.exp >= a.exp_to_next:
                a.exp -= a.exp_to_next
                a.level += 1
                self._recalc_all_stats()
                a.hp = self._full_hp(a)
                a.mp = a.max_mp
                msgs.append(f"⬆ {a.name} 升级到 Lv.{a.level}！")
        return msgs

    # ================================================================
    #  探索事件
    # ================================================================
    def trigger_event(self) -> Optional[Tuple[ExploreEvent, str]]:
        """随机触发探索事件。返回 (事件, 日志消息) 或 None"""
        loader = get_loader()
        dungeon = self.current_dungeon
        if dungeon is None or not loader.events:
            return None

        roll = random.random()
        chance = dungeon.event_chance
        if roll > chance:
            return None

        event = random.choice(list(loader.events.values()))
        self.total_events_triggered += 1
        return event, event.desc

    def resolve_event(self, event: ExploreEvent, choice_idx: int) -> str:
        """处理玩家的事件选择，返回结果信息"""
        if choice_idx < 0 or choice_idx >= len(event.choices):
            return "无效选择"

        choice = event.choices[choice_idx]
        effect = choice["effect_type"]
        value = choice.get("effect_value", 0)
        chance = choice.get("success_chance", 1.0)

        # 检查并扣除消耗品成本
        cost_item = choice.get("cost_item", "")
        if cost_item:
            if self.consumables.get(cost_item, 0) <= 0:
                return f"你没有 [{cost_item}]，无法执行此操作。"

        success = random.random() < chance

        # 扣除成本物品
        if cost_item and success:
            self.consumables[cost_item] -= 1
            if self.consumables[cost_item] <= 0:
                del self.consumables[cost_item]

        if effect == "none":
            return "你选择了无视，继续前进。"

        if effect == "damage":
            if success:
                dmg = value
                alive = [a for a in self.party if a.is_alive()]
                if alive:
                    target = random.choice(alive)
                    target.hp = max(0, target.hp - dmg)
                return f"成功避开！仅受到 {dmg} 点擦伤。"
            else:
                dmg = value * 2
                for a in self.party:
                    if a.is_alive():
                        a.hp = max(0, a.hp - dmg // len(self.party))
                return f"失败了！全队受到 {dmg} 点伤害。"

        if effect == "gold":
            if success:
                self.gold += value
                return f"获得了 {value} G！"
            else:
                return "宝箱是空的……"

        if effect == "gold_cost":
            if self.gold >= value:
                self.gold -= value
                reward_items = ["治疗药水", "魔力药水"]
                reward = random.choice(reward_items)
                self.add_consumable(reward)
                return f"你给予了 {value} G。旅人感激地送给你 [{reward}]。"
            else:
                return "金币不够……旅人失望地离开了。"

        if effect == "item_reward":
            rewards = ["治疗药水", "魔力药水", "力量药剂"]
            reward = random.choice(rewards)
            self.add_consumable(reward)
            if cost_item:
                return f"你用 [{cost_item}] 救助了旅人，对方感激地送给你 [{reward}]！"
            return f"旅人感激涕零，送给你 [{reward}]！"

        if effect == "full_heal":
            if success:
                for a in self.party:
                    a.hp = self._full_hp(a)
                    a.mp = a.max_mp
                    a.dead = False
                return "神龛的光芒笼罩了全队！HP/MP 完全恢复！"
            else:
                return "神龛毫无反应……"

        if effect == "random_buff":
            if success:
                buffs = ["力量药剂", "治疗药水"]
                reward = random.choice(buffs)
                self.add_consumable(reward)
                return f"符文闪烁，你获得了 [{reward}]！"
            else:
                dmg = 15
                for a in self.party:
                    if a.is_alive():
                        a.hp = max(0, a.hp - dmg)
                return f"符文爆发出能量！全队受到 {dmg} 点伤害。"

        return "事件已处理。"

    # ================================================================
    #  存档哈希（借鉴 pq2 的 CalculateHash 防篡改设计）
    # ================================================================
    def _compute_save_hash(self) -> str:
        """计算存档数据 SHA256 哈希，防手动篡改。

        借鉴 pq2: Character::CalculateHash() 对全属性+状态做哈希校验。
        这里对关键字段做确定性序列化后取 SHA256 前 16 位 hex。
        """
        data = {
            "gold": self.gold,
            "party": sorted([
                {
                    "name": a.name,
                    "level": a.level,
                    "exp": a.exp,
                    "hp": a.hp,
                    "mp": a.mp,
                }
                for a in self.party
            ], key=lambda x: x["name"]),
            "inventory_sorted": sorted(self.inventory),
            "consumable_keys": sorted(self.consumables.keys()),
            "unlocked_dungeons": self.unlocked_dungeons,
            "total_monsters_killed": self.total_monsters_killed,
            "total_treasures_found": self.total_treasures_found,
            "total_events_triggered": self.total_events_triggered,
        }
        raw = json.dumps(data, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    # ================================================================
    #  存档
    # ================================================================
    def save(self):
        d = {
            "gold": self.gold,
            "party": [{
                "name": a.name, "job_key": a.job_key, "race_key": a.race_key,
                "level": a.level, "exp": a.exp,
                "hp": a.hp, "max_hp": a.max_hp,
                "mp": a.mp, "max_mp": a.max_mp,
                "atk": a.atk, "def_": a.def_, "spd": a.spd,
                "equipment": a.equipment, "skills": a.skills,
                "dead": a.dead,
            } for a in self.party],
            "inventory": self.inventory,
            "consumables": self.consumables,
            "unlocked_dungeons": self.unlocked_dungeons,
            "total_monsters_killed": self.total_monsters_killed,
            "total_treasures_found": self.total_treasures_found,
            "total_events_triggered": self.total_events_triggered,
            "_hash": self._compute_save_hash(),
        }
        with open(SAVE_FILE, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=2)

    def load(self) -> bool:
        if not os.path.exists(SAVE_FILE):
            return False
        try:
            with open(SAVE_FILE, "r", encoding="utf-8") as f:
                d = json.load(f)
            # ── 哈希校验（借鉴 pq2 存档防篡改）──
            saved_hash = d.pop("_hash", None)
            self.gold = d.get("gold", 100)
            self.inventory = d.get("inventory", [])
            self.consumables = d.get("consumables", {})
            self.unlocked_dungeons = d.get("unlocked_dungeons", 1)
            self.total_monsters_killed = d.get("total_monsters_killed", 0)
            self.total_treasures_found = d.get("total_treasures_found", 0)
            self.total_events_triggered = d.get("total_events_triggered", 0)
            self.party = []
            for pd in d.get("party", []):
                a = Adventurer(
                    name=pd["name"], job_key=pd["job_key"],
                    race_key=pd.get("race_key", "人类"),
                    level=pd["level"], exp=pd.get("exp", 0),
                    exp_to_next=max(100, pd["level"] * 100),
                    hp=pd["hp"], max_hp=pd["max_hp"],
                    mp=pd.get("mp", 50), max_mp=pd.get("max_mp", 50),
                    atk=pd["atk"], def_=pd["def_"], spd=pd["spd"],
                    equipment=pd.get("equipment", {"weapon": None, "armor": None, "accessory": None, "shield": None}),
                    skills=pd.get("skills", []),
                    dead=pd.get("dead", False),
                )
                self.party.append(a)
            self._recalc_all_stats()

            # 校验哈希（老存档无 _hash 字段则跳过）
            if saved_hash is not None:
                current_hash = self._compute_save_hash()
                if current_hash != saved_hash:
                    print(f"[Engine] ⚠ 存档校验失败 — 数据可能被篡改！")
                    print(f"  期望: {saved_hash}")
                    print(f"  实际: {current_hash}")
                    # 校验失败 → 重置关键数值到默认值
                    self.gold = 100
                    self.inventory = []
                    self.consumables = {}
                    self.party = []
                    self.unlocked_dungeons = 1
                    self.total_monsters_killed = 0
                    self.total_treasures_found = 0
                    self.total_events_triggered = 0
                    print("[Engine] 已重置为默认初始状态")
                    return True  # 返回 True 但状态已重置，不保存篡改存档
            return True
        except Exception as e:
            print(f"[Engine] Load error: {e}")
            return False

    def reset_save(self):
        if os.path.exists(SAVE_FILE):
            os.remove(SAVE_FILE)
