# -*- coding: utf-8 -*-
"""事件链服务 — 旅商/传送门/流浪剑客等挂机间隙随机事件

设计原则：不打断自动化，事件以叙事日志形式呈现，可附带简单效果。
事件模板支持 {name} {region} {item} 等变量替换。
"""
from __future__ import annotations
import json
import os
import random
from typing import List, Dict, Optional


class EventService:
    """随机事件引擎"""

    def __init__(self, data_dir: str = None):
        if data_dir is None:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            src_dir = os.path.dirname(os.path.dirname(current_dir))
            data_dir = os.path.join(src_dir, "resources", "data")
        self.data_dir = data_dir
        self._events: List[dict] = []
        self._loaded = False
        self._last_event_tick = 0.0
        self._event_cooldown = 120.0  # 每2分钟最多一次事件

    def _load_events(self) -> List[dict]:
        if self._loaded:
            return self._events
        path = os.path.join(self.data_dir, "event_templates.json")
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as f:
                self._events = json.load(f)
        else:
            self._events = self._default_events()
        self._loaded = True
        return self._events

    @staticmethod
    def _default_events() -> List[dict]:
        return [
            {
                "event_id": "evt_merchant",
                "type": "narrative",
                "weight": 30,
                "template": "一个背着巨大包裹的旅商出现在路口。『嘿，冒险者！我这有件{random_item}，只要{gold_cost}金币，要不要？』",
                "effect": "offer_item",
                "effect_value": 150,
            },
            {
                "event_id": "evt_portal",
                "type": "narrative",
                "weight": 15,
                "template": "空气中突然裂开一道紫色的裂缝——一座传送门！门的那边隐约能看到{random_region}的景象……但传送门在几秒后消失了。",
                "effect": "none",
            },
            {
                "event_id": "evt_wanderer",
                "type": "narrative",
                "weight": 20,
                "template": "一位满身伤疤的流浪剑客拦住了你的去路。『我曾是{random_region}最强的剑士。来吧，让我看看你的实力！』",
                "effect": "duel",
                "effect_value": 50,
            },
            {
                "event_id": "evt_shrine",
                "type": "narrative",
                "weight": 15,
                "template": "你发现了一座被遗忘的古老神龛。石台上放着一枚散发着{random_element}光芒的徽章。",
                "effect": "blessing",
                "effect_value": 10,
            },
            {
                "event_id": "evt_campfire",
                "type": "narrative",
                "weight": 20,
                "template": "路边有一处熄灭的篝火，旁边丢着几个空瓶子和一本翻烂的日记。日记最后一页写着：『下一个地牢里，藏着{random_element}的秘密……』",
                "effect": "rest_bonus",
                "effect_value": 5,
            },
            {
                "event_id": "evt_rat_king",
                "type": "narrative",
                "weight": 10,
                "template": "一大群老鼠从墙角的裂缝中涌出——为首的一只戴着小小的王冠！鼠王叽叽喳喳叫了几声，鼠群又消失在黑暗中。",
                "effect": "gold_drop",
                "effect_value": 30,
            },
            {
                "event_id": "evt_ghost",
                "type": "narrative",
                "weight": 8,
                "template": "一个半透明的幽灵从墙壁中飘出，向你微微鞠躬。『勇者啊……请带着我的遗愿继续前进……』幽灵将一件物品放在地上，消散了。",
                "effect": "ghost_gift",
                "effect_value": 0,
            },
        ]

    def _resolve_template(self, template: str, context: dict) -> str:
        """模板字符串替换"""
        result = template
        for key, value in context.items():
            result = result.replace(f"{{{key}}}", str(value))
        return result

    def should_trigger(self, dt: float) -> bool:
        """是否触发事件（CD检查）"""
        self._last_event_tick += dt
        if self._last_event_tick < self._event_cooldown:
            return False
        self._last_event_tick = 0.0
        return random.random() < 0.15  # 15%概率

    def roll_event(self, context: dict) -> Optional[dict]:
        """摇一个随机事件

        context 需包含:
          - random_item: 随机物品名
          - random_region: 随机区域名
          - random_element: 随机元素/前缀
          - gold_cost: 随机金币数
          - char_name: 角色名
          - current_region: 当前区域名
        """
        events = self._load_events()
        if not events:
            return None

        weights = [e.get("weight", 10) for e in events]
        chosen = random.choices(events, weights=weights, k=1)[0]
        narrative = self._resolve_template(chosen.get("template", ""), context)
        return {
            "event_id": chosen.get("event_id", ""),
            "narrative": narrative,
            "effect": chosen.get("effect", ""),
            "effect_value": chosen.get("effect_value", 0),
        }

    def process_event(self, event: dict, character, item_service=None) -> List[str]:
        """处理事件效果，返回日志列表"""
        msgs = [f"[事件] {event['narrative']}"]
        effect = event.get("effect", "")
        value = event.get("effect_value", 0)

        if effect == "offer_item" and character and item_service:
            loot = item_service.generate_loot(character.level)
            if loot and character.gold >= value:
                character.gold -= value
                msgs.append(f"[事件] 你买下了{loot.get_display_name()}！花费{value}G")
                if character.try_auto_equip(loot):
                    msgs.append(f"[装备] 已装备: {loot.get_display_name()}")
            else:
                msgs.append("[事件] 可惜钱不够，旅商摇摇头走远了……")

        elif effect == "duel" and character:
            character.gain_exp(value)
            msgs.append(f"[事件] 经过一番较量，你赢得了尊重。+{value}EXP")

        elif effect == "blessing" and character:
            character.hp = min(character.max_hp, character.hp + value)
            msgs.append(f"[事件] 神龛赐予你力量！+{value}HP")

        elif effect == "rest_bonus" and character:
            character.gain_exp(value)
            msgs.append(f"[事件] 你从日记中获得了一些经验。+{value}EXP")

        elif effect == "gold_drop" and character:
            character.gold += value
            msgs.append(f"[事件] 地上散落着金币！+{value}G")

        elif effect == "ghost_gift" and character and item_service:
            loot = item_service.generate_loot(character.level)
            if loot:
                msgs.append(f"[事件] 获得幽灵的馈赠: {loot.get_display_name()}")
                if character.try_auto_equip(loot):
                    msgs.append(f"[装备] 已装备: {loot.get_display_name()}")

        return msgs
