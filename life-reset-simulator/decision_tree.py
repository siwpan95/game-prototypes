#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
王权风格决策树模块
实现类似《王权》(Reigns)的决策系统
玩家通过选择影响多个维度的平衡，决策有连锁反应
"""

import random
import json
import os
from typing import Dict, List, Tuple, Any, Optional
from enum import Enum


class Dimension(Enum):
    """王权风格的维度"""
    STRENGTH = "力量"
    INTELLIGENCE = "智慧"
    CHARISMA = "民心"
    WEALTH = "财政"
    MORALITY = "道德"
    STABILITY = "稳定"
    CHURCH = "教会"
    NOBLES = "贵族"
    COMMONERS = "平民"
    HEALTH = "健康"
    HAPPINESS = "幸福"


class DecisionTree:
    """
    王权风格决策树
    每个决策影响多个维度的平衡，维度间相互关联
    """

    def __init__(self, player):
        self.player = player
        self.dimensions = self._initialize_dimensions()
        self.history = []
        self.year = 0
        self.season = 0
        self.crisis_imminent = False
        self.crisis_type = None

        self.dimension_to_player = {
            Dimension.STRENGTH: "strength",
            Dimension.INTELLIGENCE: "intelligence",
            Dimension.CHARISMA: "charisma",
            Dimension.WEALTH: "wealth",
            Dimension.HEALTH: "health",
            Dimension.HAPPINESS: "happiness"
        }

        self.decision_cards = self._load_decision_cards()

    def _initialize_dimensions(self) -> Dict[Dimension, int]:
        """初始化王权维度"""
        return {
            Dimension.STRENGTH: 50,
            Dimension.INTELLIGENCE: 50,
            Dimension.CHARISMA: 50,
            Dimension.WEALTH: 50,
            Dimension.MORALITY: 50,
            Dimension.STABILITY: 50,
            Dimension.CHURCH: 50,
            Dimension.NOBLES: 50,
            Dimension.COMMONERS: 50,
            Dimension.HEALTH: 80,
            Dimension.HAPPINESS: 50
        }

    def _load_decision_cards(self) -> List[Dict]:
        """加载决策卡牌"""
        try:
            card_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "decision_cards.json")
            with open(card_path, "r", encoding="utf-8") as f:
                return json.load(f)["cards"]
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            return self._get_default_cards()

    def _get_default_cards(self) -> List[Dict]:
        """获取默认决策卡牌"""
        return [
            {
                "id": "war_declaration",
                "title": "边境冲突",
                "description": "邻国在边境集结军队，是战是和？",
                "left_choice": {
                    "text": "主动出击，展示武力",
                    "effects": {"STRENGTH": 15, "WEALTH": -20, "STABILITY": -10, "NOBLES": 10, "COMMONERS": -15},
                    "speech": "让他们知道我们的厉害！"
                },
                "right_choice": {
                    "text": "谈判和解，赠送礼物",
                    "effects": {"STRENGTH": -10, "WEALTH": -15, "STABILITY": 10, "NOBLES": -5, "COMMONERS": 5},
                    "speech": "战争是最后的手段。"
                },
                "conditions": {"required_traits": [], "min_strength": 0},
                "weight": 1.0
            },
            {
                "id": "famine",
                "title": "粮食危机",
                "description": "今年收成不好，粮仓空虚。",
                "left_choice": {
                    "text": "开仓放粮，赈济灾民",
                    "effects": {"WEALTH": -25, "COMMONERS": 20, "NOBLES": -10, "CHARISMA": 15, "MORALITY": 10},
                    "speech": "百姓的性命最重要。"
                },
                "right_choice": {
                    "text": "提高粮价，维持财政",
                    "effects": {"WEALTH": 15, "COMMONERS": -25, "STABILITY": -20, "CHARISMA": -20},
                    "speech": "国家需要资金运转。"
                },
                "conditions": {"required_traits": [], "min_wealth": 0},
                "weight": 1.0
            }
        ]

    def get_current_season(self) -> str:
        """获取当前季节"""
        seasons = ["春", "夏", "秋", "冬"]
        return seasons[self.season % 4]

    def advance_time(self):
        """推进时间"""
        self.season += 1
        if self.season % 4 == 0:
            self.year += 1

        seasonal_effects = {
            0: {"WEALTH": 5, "HAPPINESS": 5},
            1: {"WEALTH": 10, "HEALTH": -5},
            2: {"WEALTH": 15, "STABILITY": 5},
            3: {"WEALTH": -10, "STABILITY": -5}
        }

        effects = seasonal_effects.get(self.season % 4, {})
        for dim, delta in effects.items():
            self.adjust_dimension(Dimension[dim], delta)

    def get_available_cards(self) -> List[Dict]:
        """获取当前可用的决策卡牌"""
        available = []

        for card in self.decision_cards:
            if self._check_card_conditions(card):
                weight = card.get("weight", 1.0)

                for trait in self.player.traits:
                    if trait in ["仁慈", "慷慨"] and "赈济" in card.get("description", ""):
                        weight *= 1.5
                    elif trait in ["残暴", "吝啬"] and "镇压" in card.get("description", ""):
                        weight *= 1.5

                if self.crisis_imminent and "危机" in card.get("title", ""):
                    weight *= 2.0

                available.append((card, weight))

        if not available:
            return []

        selected = []
        pool = list(available)
        total_weight = sum(w for _, w in pool)

        for _ in range(min(3, len(pool))):
            r = random.uniform(0, total_weight)
            for card, weight in pool:
                r -= weight
                if r <= 0:
                    selected.append(card)
                    pool.remove((card, weight))
                    total_weight -= weight
                    break

        return selected

    def _check_card_conditions(self, card: Dict) -> bool:
        """检查卡牌条件是否满足"""
        conditions = card.get("conditions", {})

        required_traits = conditions.get("required_traits", [])
        for trait in required_traits:
            if trait not in self.player.traits:
                return False

        for dim_name, min_value in conditions.items():
            if dim_name.startswith("min_"):
                dim = dim_name[4:].upper()
                try:
                    dimension = Dimension[dim]
                    if self.dimensions[dimension] < min_value:
                        return False
                except (KeyError, AttributeError):
                    continue

        return True

    def apply_decision(self, card: Dict, choice: str) -> Dict[str, Any]:
        """应用决策结果"""
        choice_data = card[choice]
        effects = choice_data.get("effects", {})

        decision_record = {
            "year": self.year,
            "season": self.get_current_season(),
            "card_title": card["title"],
            "choice": choice_data["text"],
            "effects": effects.copy()
        }
        self.history.append(decision_record)

        for dim_name, delta in effects.items():
            try:
                dimension = Dimension[dim_name]
                self.adjust_dimension(dimension, delta)
            except KeyError:
                pass

        chain_reactions = self._check_chain_reactions(card, choice)

        self.advance_time()

        self._check_crisis()

        return {
            "speech": choice_data.get("speech", ""),
            "effects": effects,
            "chain_reactions": chain_reactions
        }

    def adjust_dimension(self, dimension: Dimension, delta: int):
        """调整维度值"""
        if dimension in self.dimensions:
            self.dimensions[dimension] = max(0, min(100, self.dimensions[dimension] + delta))

            if dimension in self.dimension_to_player:
                attr = self.dimension_to_player[dimension]
                if hasattr(self.player, attr):
                    player_delta = delta / 5
                    setattr(self.player, attr,
                           max(0, min(20, getattr(self.player, attr) + player_delta)))

    def _check_chain_reactions(self, card: Dict, choice: str) -> List[Dict]:
        """检查连锁反应"""
        reactions = []

        if card.get("id") == "war_declaration":
            if choice == "left_choice":
                if self.dimensions[Dimension.STRENGTH] > 70:
                    reactions.append({
                        "title": "胜利的代价",
                        "description": "虽然战争胜利了，但阵亡士兵的家属充满怨恨。",
                        "effects": {"COMMONERS": -10, "STABILITY": -5}
                    })
        elif card.get("id") == "famine":
            if choice == "right_choice":
                if self.dimensions[Dimension.COMMONERS] < 30:
                    reactions.append({
                        "title": "民怨沸腾",
                        "description": "饥饿的民众开始聚集抗议。",
                        "effects": {"STABILITY": -15, "CHARISMA": -10}
                    })
        elif card.get("id") == "noble_revolt":
            if choice == "left_choice":
                if self.dimensions[Dimension.NOBLES] < 20:
                    reactions.append({
                        "title": "贵族离心",
                        "description": "更多贵族暗中策划反对你。",
                        "effects": {"STABILITY": -10, "NOBLES": -10}
                    })
        elif card.get("id") == "economic_reform":
            if choice == "right_choice":
                if self.dimensions[Dimension.COMMONERS] < 25:
                    reactions.append({
                        "title": "民变前兆",
                        "description": "加税引发了小规模骚乱。",
                        "effects": {"STABILITY": -10, "COMMONERS": -5}
                    })

        for reaction in reactions:
            for dim_name, delta in reaction["effects"].items():
                try:
                    dimension = Dimension[dim_name]
                    self.adjust_dimension(dimension, delta)
                except KeyError:
                    pass

        # ─────────────────────────────────────────────────────────────
        # [B2a 纯追加] 数据驱动连锁反应
        # 读取卡牌可选字段 chain_reactions[]，按规则触发。
        # 上方 4 个存量硬编码分支与其效果结算循环一行未动，行为完全保持。
        # 卡牌未声明 chain_reactions 时本段是空转，零回归。
        #
        # chain_reactions 规则字段（全部可选，除 effects 外）：
        #   when_choice     : "left_choice" / "right_choice"，缺省=任意选择均可触发
        #   conditions      : {"min_STRENGTH": 70, "max_WEALTH": 30,
        #                      "required_traits": [...], "forbidden_traits": [...]}
        #   chance          : 0.0-1.0 触发概率，缺省 1.0
        #   title           : 连锁标题
        #   description     : 连锁描述
        #   effects         : {"COMMONERS": -10, ...} 维度增减
        # ─────────────────────────────────────────────────────────────
        data_rules = card.get("chain_reactions") or []
        if isinstance(data_rules, list):
            for rule in data_rules:
                if not isinstance(rule, dict):
                    continue
                rule = self._normalize_chain_rule(rule)
                try:
                    if not self._data_chain_rule_matches(rule, choice):
                        continue
                    effects = rule.get("effects", {}) or {}
                    if not isinstance(effects, dict):
                        effects = {}
                    reaction = {
                        "title": rule.get("title", "连锁反应"),
                        "description": rule.get("description", ""),
                        "effects": dict(effects)
                    }
                    for dim_name, delta in reaction["effects"].items():
                        try:
                            dimension = Dimension[str(dim_name).upper()]
                            self.adjust_dimension(dimension, delta)
                        except (KeyError, TypeError):
                            pass
                    reactions.append(reaction)
                except Exception:
                    # 数据驱动分支永不因坏数据阻断主流程
                    continue

        return reactions

    def _normalize_chain_rule(self, rule: Dict) -> Dict:
        """[B3 容错] 兼容两种 chain_reactions 写法：
        - 简化版（内容批次采用）：{"condition": {...}, "text": "...", "effects": {...}}
        - 全量版（引擎契约）：{"conditions": {...}, "title": "...", "description": "...", "effects": {...}}
        统一归一到引擎消费的 conditions / title / description，
        使两种写法都能被 _data_chain_rule_matches 正确解析与触发。
        """
        if "condition" in rule and "conditions" not in rule:
            rule["conditions"] = rule.pop("condition")
        if "text" in rule and "description" not in rule:
            rule["description"] = rule.pop("text")
        if "title" not in rule:
            desc = rule.get("description") or ""
            rule["title"] = (desc[:12] if desc else "连锁反应")
        return rule

    def _data_chain_rule_matches(self, rule: Dict, choice: str) -> bool:
        """[B2a 纯追加] 判断一条数据驱动连锁规则是否命中。

        任何异常/坏数据一律判为不命中，绝不抛出到主流程。
        """
        try:
            when_choice = rule.get("when_choice")
            if when_choice and when_choice != choice:
                return False

            conditions = rule.get("conditions", {}) or {}
            if isinstance(conditions, dict):
                owned = set(getattr(self.player, "traits", None) or [])
                for trait in conditions.get("required_traits", []) or []:
                    if trait not in owned:
                        return False
                for trait in conditions.get("forbidden_traits", []) or []:
                    if trait in owned:
                        return False
                for key, threshold in conditions.items():
                    if not isinstance(key, str):
                        continue
                    if key.startswith("min_"):
                        dim_name = key[4:].upper()
                    elif key.startswith("max_"):
                        dim_name = key[4:].upper()
                    else:
                        continue
                    try:
                        dimension = Dimension[dim_name]
                    except KeyError:
                        continue
                    value = self.dimensions.get(dimension, 0)
                    if key.startswith("min_") and value < threshold:
                        return False
                    if key.startswith("max_") and value > threshold:
                        return False

            chance = rule.get("chance", 1.0)
            try:
                chance = float(chance)
            except (TypeError, ValueError):
                chance = 1.0
            if chance < 1.0 and random.random() >= chance:
                return False

            return True
        except Exception:
            return False

    def _check_crisis(self):
        """检查是否即将发生危机"""
        self.crisis_imminent = False
        self.crisis_type = None

        if self.dimensions[Dimension.STRENGTH] < 20:
            self.crisis_imminent = True
            self.crisis_type = "军事危机"
        elif self.dimensions[Dimension.WEALTH] < 20:
            self.crisis_imminent = True
            self.crisis_type = "财政危机"
        elif self.dimensions[Dimension.STABILITY] < 20:
            self.crisis_imminent = True
            self.crisis_type = "叛乱危机"
        elif self.dimensions[Dimension.HEALTH] < 20:
            self.crisis_imminent = True
            self.crisis_type = "健康危机"
        elif self.dimensions[Dimension.COMMONERS] < 20 and self.dimensions[Dimension.NOBLES] < 20:
            self.crisis_imminent = True
            self.crisis_type = "全面危机"

    def get_crisis_warning(self) -> Optional[str]:
        """获取危机警告"""
        if not self.crisis_imminent:
            return None

        warnings = {
            "军事危机": "⚠️ 军力薄弱！边境不稳，外敌虎视眈眈。",
            "财政危机": "💰 国库空虚！国家运转困难。",
            "叛乱危机": "⚔️ 民怨沸腾！叛乱一触即发。",
            "健康危机": "🏥 龙体欠安！御医束手无策。",
            "全面危机": "💀 四面楚歌！国家危在旦夕。"
        }

        return warnings.get(self.crisis_type, "危机临近！")

    def get_dimension_status(self, dimension: Dimension) -> Tuple[str, str]:
        """获取维度状态描述"""
        value = self.dimensions[dimension]

        if value >= 80:
            status, emoji = "极好", "🌟"
        elif value >= 60:
            status, emoji = "良好", "✅"
        elif value >= 40:
            status, emoji = "一般", "➖"
        elif value >= 20:
            status, emoji = "堪忧", "⚠️"
        else:
            status, emoji = "危险", "💀"

        return status, emoji

    def display_status(self):
        """显示当前状态"""
        print("\n" + "=" * 60)
        print(f"         👑 第{self.year}年 {self.get_current_season()}季 👑")
        print("=" * 60)

        if self.crisis_imminent:
            warning = self.get_crisis_warning()
            if warning:
                print(f"\n{warning}")

        print("\n【国家状态】")
        dimensions_display = [
            (Dimension.STRENGTH, "军力"),
            (Dimension.INTELLIGENCE, "智慧"),
            (Dimension.CHARISMA, "民心"),
            (Dimension.WEALTH, "财政"),
            (Dimension.MORALITY, "道德"),
            (Dimension.STABILITY, "稳定"),
            (Dimension.CHURCH, "教会"),
            (Dimension.NOBLES, "贵族"),
            (Dimension.COMMONERS, "平民"),
            (Dimension.HEALTH, "健康"),
            (Dimension.HAPPINESS, "幸福")
        ]

        for i in range(0, len(dimensions_display), 3):
            line = ""
            for dim, name in dimensions_display[i:i+3]:
                value = self.dimensions[dim]
                _, emoji = self.get_dimension_status(dim)
                bar = "█" * (value // 10) + "░" * (10 - value // 10)
                line += f"{emoji}{name}:{value:3d} {bar} "
            print(line)

        print("=" * 60)

    def is_game_over(self) -> Tuple[bool, str]:
        """检查游戏是否结束"""
        if self.dimensions[Dimension.HEALTH] <= 0:
            return True, "💀 你因病逝世，游戏结束。"
        elif self.dimensions[Dimension.STABILITY] <= 0:
            return True, "⚔️ 国家崩溃，叛军推翻了你的统治。"
        elif (self.dimensions[Dimension.NOBLES] <= 0 and
              self.dimensions[Dimension.COMMONERS] <= 0):
            return True, "👥 众叛亲离，无人再支持你的统治。"
        elif self.dimensions[Dimension.STRENGTH] <= 0:
            return True, "🏰 外敌入侵，国家灭亡。"

        if (self.year >= 20 and
            self.dimensions[Dimension.STABILITY] >= 80 and
            self.dimensions[Dimension.WEALTH] >= 80 and
            self.dimensions[Dimension.CHARISMA] >= 80):
            return True, "👑 伟大的统治者！你创造了太平盛世，名垂青史！"

        return False, ""

    def get_ending_based_on_history(self) -> str:
        """根据决策历史生成结局"""
        if not self.history:
            return "平淡无奇的统治。"

        war_count = sum(1 for h in self.history if "战争" in h["card_title"] or "武力" in h["choice"] or "出击" in h["choice"] or "镇压" in h["choice"])
        peace_count = sum(1 for h in self.history if "和平" in h["card_title"] or "谈判" in h["choice"] or "和解" in h["choice"])
        people_count = sum(1 for h in self.history if "赈济" in h["choice"] or "减税" in h["choice"] or "救灾" in h["choice"] or "放粮" in h["choice"])
        noble_count = sum(1 for h in self.history if "贵族" in h["card_title"] or "权力" in h["choice"] or "镇压" in h["choice"])

        if war_count > peace_count + 3:
            if self.dimensions[Dimension.STRENGTH] > 70:
                return "你是一位征服者，用铁与血扩展了领土，但树敌无数。"
            else:
                return "你好战但无能，频繁的战争耗尽了国力。"
        elif peace_count > war_count + 3:
            if self.dimensions[Dimension.WEALTH] > 70:
                return "你是一位和平的统治者，经济发展，人民安居乐业。"
            else:
                return "你过于软弱，外交上的让步让国家蒙羞。"
        elif people_count > noble_count + 3:
            return "你是一位明君，心系百姓，深受爱戴。"
        elif noble_count > people_count + 3:
            return "你维护贵族利益，但忽视了平民的苦难。"

        return "你是一位平衡的统治者，在各种势力间周旋。"
