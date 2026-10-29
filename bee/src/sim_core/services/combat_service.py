# -*- coding: utf-8 -*-
"""战斗服务 - 处理战斗逻辑 + DPS追踪 + 状态机

变更说明：
  新增 DPS 追踪能力：
    - _fight_damage: Dict[id(member), int] 记录当前战斗中每个队员造成的伤害
    - reset_damage_tracker(): 开始新战斗时重置
    - record_damage(member, amount): 记录单次伤害
    - get_damage_distribution(): 获取伤害分布，用于按DPS分配经验/金币
  新增 回合状态机：
    - tick_status_effects(): 每回合处理词缀效果 + 种族技能
    - 驱动机理：词缀→状态标记 → 每tick施加效果 + 叙事
    - 种族技能：亡语/狂暴/分裂/喷吐/结网/眩晕 在回合中触发
"""
from __future__ import annotations
import random
from dataclasses import dataclass, field
from typing import List, Dict, Optional, TYPE_CHECKING
from ..models.item import Weapon, EquipmentSlot

if TYPE_CHECKING:
    from .difficulty_service import DifficultyService


class CombatService:
    """战斗服务 — 解耦战斗逻辑与数据"""

    # ── 元素交互叙事模板 ──
    ELEMENT_NARRATIVES = {
        ("fire_damage",): [
            "烈焰舔舐着{name}的身躯！", "{name}被火焰包裹，发出痛苦的嘶吼！",
            "炽热的火光在{name}身上炸裂！",
        ],
        ("poison",): [
            "毒素在{name}的血管中蔓延……", "{name}的伤口渗出暗绿色的脓液！",
            "剧毒让{name}的动作变得迟缓而痛苦。",
        ],
        ("shock",): [
            "电弧在{name}身上噼啪作响！", "{name}被闪电击中，浑身抽搐！",
        ],
        ("slow",): [
            "寒气侵蚀着{name}，它的动作明显变慢了。",
            "冰霜在{name}的关节处凝结，发出刺耳的嘎吱声。",
        ],
        ("regen",): [
            "{name}的伤口以肉眼可见的速度愈合着……",
        ],
        ("life_steal",): [
            "{name}贪婪地汲取着生命之力！",
        ],
    }

    # ── 种族技能叙事模板 ──
    RACIAL_NARRATIVES = {
        "death_rattle": [
            "{name}临死前发出最后的尖啸！一股黑暗能量向你袭来！",
            "{name}的身躯崩解，但残存的怨念化作一道诅咒！",
        ],
        "frenzy": [
            "{name}双眼血红，陷入狂暴！攻击变得疯狂而毫无章法！",
            "{name}发出愤怒的咆哮，不顾一切地扑了上来！",
        ],
        "breath": [
            "{name}深吸一口气，喷吐出毁灭性的龙息！",
            "龙炎从{name}口中倾泻而出！",
        ],
        "web": [
            "{name}喷出粘稠的蛛网，缠绕住了你的手脚！",
        ],
        "stomp": [
            "{name}抬起巨脚猛踏地面！整个房间都在震动！",
            "轰——！{name}的重踏让你站立不稳！",
        ],
        "split": [
            "{name}分裂成了两个！现在你要面对双倍的麻烦！",
        ],
    }

    # ── 环境叙事模板 ──
    ENV_NARRATIVES = {
        "高温": ["热浪扑面而来，空气都在扭曲。", "地面烫得能煎蛋——如果你有蛋的话。"],
        "严寒": ["刺骨的寒气穿透铠甲，直钻骨髓。", "呼出的气息瞬间凝结成霜。"],
        "雷暴": ["空气中弥漫着电离的味道，头发都竖起来了。", "远处传来隆隆雷声，闪电不时照亮房间。"],
        "毒雾": ["淡绿色的雾气弥漫在房间中，呼吸变得困难。", "空气中飘浮着可疑的孢子。"],
        "死灵": ["墙壁上渗出暗色的液体，空气中回荡着低语。", "地上的骸骨似乎在微微颤动。"],
        "暗影": ["阴影在角落里蠕动，似乎有东西在窥视。", "光线仿佛被吞噬，黑暗浓得化不开。"],
        "诅咒": ["一股无形的压迫感笼罩着整个房间。", "你感到一股寒意从脊背升起，仿佛被什么东西盯上了。"],
        "血域": ["地面粘稠湿滑，空气中弥漫着铁锈味。", "暗红色的血迹覆盖了每一寸墙面。"],
    }

    # ── 元素交互规则表（三元匹配：元素×环境×种族 → 叙事+效果）──
    ELEMENT_REACTIONS = [
        # (element_key, env_tags, race_tags, narrative, effect_dict)
        ("fire_damage", ["毒雾"], [],
         "{name}身上的火焰引爆了弥漫的毒雾！轰——！", {"bonus_dmg": 15}),
        ("fire_damage", ["严寒"], [],
         "冰火交融，{name}周围的空气发出刺耳的嘶嘶声——蒸汽弥漫！", {"debuff_def": -2}),
        ("shock", [], ["机械系"],
         "闪电在{name}的金属身躯上弹跳，电弧四溅！", {"bonus_dmg": 10, "stun_bonus": 0.05}),
        ("shock", ["雷暴"], [],
         "雷暴环境放大了闪电的威力！{name}浑身火花四溅！", {"bonus_dmg": 12}),
        ("poison", ["毒雾"], [],
         "毒雾与{name}身上渗出的毒素混合，空气中弥漫着致命的绿色！", {"dot_bonus": 3}),
        ("slow", ["高温"], [],
         "{name}身上的冰霜在高温中嘶嘶蒸发，减速效果大打折扣！", {"slow_penalty": -1}),
        ("slow", ["死灵"], ["亡灵系"],
         "寒气冻结了{name}的腐肉，它发出刺耳的咯吱声！", {"bonus_dmg": 8}),
        ("life_steal", ["血域"], [],
         "血域滋养了{name}的吸血欲望！它的眼中闪烁着贪婪的红光！", {"ls_bonus": 0.05}),
        ("regen", ["暗影"], ["亡灵系"],
         "暗影能量涌入{name}的躯体，腐朽的血肉开始蠕动重生！", {"regen_bonus": 5}),
    ]

    def __init__(self, data_service, difficulty_service: "DifficultyService" = None):
        self.data_service = data_service
        self.difficulty_service = difficulty_service  # 动态缩放服务
        self.HIT_LOCATIONS = ["头部", "胸部", "手臂", "腿部", "手部", "脚部"]
        self.HIT_WEIGHTS = [0.1, 0.35, 0.2, 0.2, 0.1, 0.05]
        self.in_combat = False
        self.current_enemy = None

        # ── DPS 追踪 ───────────────────────────────
        self._fight_damage: Dict[int, int] = {}

    def create_enemy_from_template(self, template: dict, party=None) -> dict:
        """
        从模板创建敌人数据。
        如果提供了 party，则根据队伍强度自动缩放敌人属性。
        """
        scaled = template.copy()

        # ── 动态缩放：队伍越强，敌人越强 ──
        if self.difficulty_service and party:
            scaled = self.difficulty_service.scale_enemy_template(template, party)

        return {
            "name": f"{scaled['name']} Lv.{scaled.get('level', 1)}",
            "base_name": scaled.get("base_name", scaled.get("name", "?")),
            "tags": scaled.get("tags", []),
            "rarity": scaled.get("rarity", "普通"),
            "level": scaled.get("level", 1),
            "max_hp": scaled.get("hp", 30),
            "hp": scaled.get("hp", 30),
            "damage": scaled.get("damage", 5),
            "defense": scaled.get("defense", 0),
            "exp_reward": scaled.get("exp", 10),
            "gold_reward": scaled.get("gold", 5),
            "loot_table": scaled.get("loot_table", "normal"),
            "race": scaled.get("race", "未知"),
            "description": scaled.get("description", ""),
            "alive": True,
            # 词缀和种族被动
            "evasion":       scaled.get("evasion", 0),
            "thorns":        scaled.get("thorns", 0),
            "regen":         scaled.get("regen", 0),
            "life_steal":    scaled.get("life_steal", 0),
            "fire_damage":   scaled.get("fire_damage", 0),
            "poison":        scaled.get("poison", 0),
            "shock":         scaled.get("shock", 0),
            "slow":          scaled.get("slow", 0),
            "freeze_chance": scaled.get("freeze_chance", 0),
            "shield":        scaled.get("shield", 0),
            "stun_chance":   scaled.get("stun_chance", 0),
            "crit_chance":   scaled.get("crit_chance", 0.05),
            "death_save":    scaled.get("death_save", 0),
            "affixes":       scaled.get("affixes", []),
            "affix_effects": scaled.get("affix_effects", {}),
            "racial_abilities": scaled.get("racial_abilities", {}),
            "body_parts": {
                "头部": 0.15, "躯干": 0.40, "手臂": 0.20,
                "腿部": 0.20, "要害": 0.05,
            },
            "buffs": {},
            "buff_durations": {},
        }

    # ── DPS 追踪方法 ─────────────────────────────────

    def reset_damage_tracker(self):
        """开始新战斗前重置伤害追踪"""
        self._fight_damage.clear()

    def record_damage(self, attacker, damage_amount: int):
        """记录某成员对当前敌人造成的伤害"""
        key = id(attacker)
        self._fight_damage[key] = self._fight_damage.get(key, 0) + damage_amount

    def get_damage_distribution(self) -> Dict[int, int]:
        """
        获取本场战斗的伤害分布。
        返回 {id(member): total_damage}
        调用后内部自动重置，准备下一场战斗。
        """
        result = dict(self._fight_damage)
        self._fight_damage.clear()
        return result

    def get_total_fight_damage(self) -> int:
        """获取本场战斗总伤害（用于验证）"""
        return sum(self._fight_damage.values())

    # ── 战斗计算方法（原有逻辑不变）──────────────────────

    def calculate_player_damage(self, character, weapon, is_crit=False):
        """计算玩家伤害"""
        base_dmg = character.get_attack_power()

        if is_crit:
            damage = int(base_dmg * (1.5 + random.random() * 0.5))
        else:
            damage = int(base_dmg * (0.85 + random.random() * 0.3))

        return max(1, damage)

    def calculate_enemy_damage(self, enemy_data: dict) -> int:
        """计算敌人伤害"""
        return max(1, enemy_data["damage"] + random.randint(-2, 3))

    def apply_damage_to_enemy(self, enemy_data: dict, damage: int, location: str = "躯干") -> int:
        """对敌人造成伤害，返回实际伤害"""
        location_mult = enemy_data["body_parts"].get(location, 1.0)
        actual = max(0, int(damage * location_mult) - enemy_data["defense"] // 3)
        if actual <= 0:
            actual = random.randint(1, max(1, damage // 4))

        enemy_data["hp"] = max(0, enemy_data["hp"] - actual)
        if enemy_data["hp"] <= 0:
            enemy_data["alive"] = False

        return actual

    def apply_damage_to_character(self, character, raw_damage: int) -> int:
        """对角色造成伤害，返回实际伤害"""
        actual = character.take_damage(raw_damage)
        return actual

    def check_dodge(self, character) -> bool:
        """检查是否闪避"""
        dodge_chance = character.stats.dexterity * 0.01
        return random.random() < dodge_chance

    def check_block(self, character) -> bool:
        """检查是否格挡"""
        block_chance = 0.05 + character.constitution * 0.003
        return random.random() < block_chance

    def get_hit_location(self) -> str:
        """获取命中部位"""
        return random.choices(self.HIT_LOCATIONS, weights=self.HIT_WEIGHTS)[0]

    def get_enemy_template(self, region_data: dict) -> Optional[dict]:
        """根据区域获取敌人模板"""
        enemies = self.data_service.get_enemies_by_level(region_data.get("danger_level", 1))
        if enemies:
            return random.choice(enemies)
        return None

    # ======== 组队战斗方法 ========

    def party_attack_cycle(self, party, enemy_data: dict) -> List[str]:
        """单人攻击循环"""
        messages = []
        if not enemy_data or not enemy_data.get("alive", True):
            return messages

        member = party.hero
        if member.hp <= 0:
            return messages

        is_crit = random.random() < 0.1
        damage = self.calculate_player_damage(member, None, is_crit)
        location = self.get_hit_location()
        actual = self.apply_damage_to_enemy(enemy_data, damage, location)

        # ★ DDA 反馈回路：记录每次造成的伤害
        self.record_damage(member, actual)

        name_tag = f"[{member.char_class.value[0]}·{member.name}]"
        crit_text = "【暴击！】" if is_crit else ""
        messages.append(
            f"[战斗] {name_tag} 攻击{enemy_data['name']}的{location}，造成{actual}伤害 {crit_text}"
        )

        return messages

    def party_defend_cycle(self, party, enemy_data: dict, dt: float) -> List[str]:
        """敌人攻击主角"""
        messages = []
        if not enemy_data or not enemy_data.get("alive", True):
            return messages

        target = party.hero
        if target.hp <= 0:
            return messages

        if not self.check_dodge(target):
            dmg = self.calculate_enemy_damage(enemy_data)
            actual = self.apply_damage_to_character(target, dmg)
            name_tag = f"{target.char_class.value[0]}·{target.name}"
            messages.append(
                f"[战斗] {enemy_data['name']} 攻击 {name_tag}，造成 {actual} 伤害"
            )
            if target.hp <= 0:
                messages.append(f"[系统] {name_tag} 阵亡！")
        else:
            name_tag = f"{target.char_class.value[0]}·{target.name}"
            messages.append(f"[战斗] {name_tag} 躲开了攻击！")

        return messages

    def resurrect_fallen(self, party) -> List[str]:
        """单人模式下，主角阵亡即游戏结束，无复活"""
        return []

    # ═══════════════════════════════════════════════════════
    #  回合状态机 — 词缀效果 + 种族技能 + 环境交互
    # ═══════════════════════════════════════════════════════

    def tick_status_effects(self, enemy_data: dict, character,
                            environment: str = "", round_num: int = 0,
                            dt: float = 0.0) -> List[str]:
        """每帧执行：处理敌人状态 + 种族技能 + 环境效果 → 返回叙事文本列表

        Args:
            dt: 本帧时间间隔（秒），用于 regen 等效果的时间缩放
        """
        narratives = []

        if not enemy_data or not enemy_data.get("alive", True):
            return narratives

        base_name = enemy_data.get("base_name", enemy_data.get("name", "它"))

        # ── 1. 处理持续性状态效果 ──
        narratives += self._tick_dot_effects(enemy_data, base_name)
        narratives += self._tick_buff_effects(enemy_data, base_name, dt)

        # ── 2. 种族技能触发 ──
        narratives += self._tick_racial_abilities(enemy_data, character, base_name, round_num)

        # ── 3. 环境效果 ──
        if environment and round_num == 1:
            narratives += self._tick_environment(environment, enemy_data, base_name)

        # ── 4. 元素交互反应 ──
        narratives += self._check_element_reactions(enemy_data, environment, base_name)

        return narratives

    def _tick_dot_effects(self, enemy_data: dict, name: str) -> List[str]:
        """持续性伤害/负面效果"""
        msgs = []

        # 灼烧 (fire_damage)
        fd = enemy_data.get("fire_damage", 0)
        if fd > 0:
            dot = max(1, int(fd * 10))
            enemy_data["hp"] = max(0, enemy_data["hp"] - dot)
            if enemy_data.get("_fire_tick", 0) == 0:
                msgs.append(f"[状态] {random.choice(self.ELEMENT_NARRATIVES[('fire_damage',)]).format(name=name)} (-{dot}HP)")

        # 中毒
        poison = enemy_data.get("poison", 0)
        if poison > 0:
            dot = max(1, int(poison * 3))
            enemy_data["hp"] = max(0, enemy_data["hp"] - dot)
            if enemy_data.get("_poison_tick", 0) % 2 == 0:
                msgs.append(f"[状态] {random.choice(self.ELEMENT_NARRATIVES[('poison',)]).format(name=name)} (-{dot}HP)")

        # 感电 (额外伤害加值，非DOT)
        shock = enemy_data.get("shock", 0)
        if shock > 0:
            enemy_data["_shock_bonus"] = shock  # 本回合受到的伤害增加

        # 减速 (降低敌人攻击频率)
        slow = enemy_data.get("slow", 0)
        if slow > 0:
            enemy_data["_slow_stacks"] = enemy_data.get("_slow_stacks", 0) + 1
            if enemy_data["_slow_stacks"] == 1:
                msgs.append(f"[状态] {random.choice(self.ELEMENT_NARRATIVES[('slow',)]).format(name=name)}")

        # 击晕
        if enemy_data.get("stun_chance", 0) > 0 and random.random() < enemy_data["stun_chance"]:
            enemy_data["_stunned"] = True
            msgs.append(f"[状态] {random.choice(self.RACIAL_NARRATIVES['stomp']).format(name=name)}")

        # 冰冻
        if enemy_data.get("freeze_chance", 0) > 0 and random.random() < enemy_data["freeze_chance"]:
            enemy_data["_frozen"] = True
            msgs.append(f"[状态] 寒气将{name}冻在原地！")

        # 检查死亡
        if enemy_data["hp"] <= 0:
            enemy_data["alive"] = False
            msgs.append(f"[击杀] {name} 在持续伤害中倒下！")

        return msgs

    def _tick_buff_effects(self, enemy_data: dict, name: str, dt: float = 0.0) -> List[str]:
        """正面效果/回复

        Args:
            dt: 本帧时间间隔（秒），regen 按 dt 缩放（每秒回 regen 点）
        """
        msgs = []

        # 回复 — regen 为每秒回血量，按 dt 缩放
        regen = enemy_data.get("regen", 0)
        if regen > 0 and enemy_data["hp"] < enemy_data["max_hp"]:
            # 用累积器避免浮点丢失：每秒恢复 regen 点 HP
            acc = enemy_data.get("_regen_acc", 0.0) + regen * max(dt, 0.016)
            to_heal = int(acc)
            if to_heal > 0:
                healed = min(to_heal, enemy_data["max_hp"] - enemy_data["hp"])
                enemy_data["hp"] += healed
                enemy_data["_regen_acc"] = acc - to_heal
                if healed > 2:
                    msgs.append(f"[状态] {random.choice(self.ELEMENT_NARRATIVES[('regen',)]).format(name=name)} (+{healed}HP)")
            else:
                enemy_data["_regen_acc"] = acc

        # 护盾
        shield = enemy_data.get("shield", 0)
        if shield > 0:
            enemy_data["_shield"] = enemy_data.get("_shield", 0) + shield

        # 吸血 (在伤害计算时生效，此处仅标记；每场战斗只播报一次)
        ls = enemy_data.get("life_steal", 0)
        if ls > 0 and enemy_data.get("_life_steal_narrative", True):
            enemy_data["_life_steal_narrative"] = False
            msgs.append(f"[状态] {random.choice(self.ELEMENT_NARRATIVES[('life_steal',)]).format(name=name)}")

        return msgs

    def _tick_racial_abilities(self, enemy_data: dict, character,
                                name: str, round_num: int) -> List[str]:
        """种族技能触发"""
        msgs = []
        racial = enemy_data.get("racial_abilities", {})
        hp_pct = enemy_data["hp"] / max(1, enemy_data["max_hp"])

        # ── 野兽/恶魔狂暴：血量低于30% ──
        frenzy_threshold = racial.get("frenzy_hp_pct", 0)
        if frenzy_threshold > 0 and hp_pct <= frenzy_threshold and not enemy_data.get("_frenzied"):
            enemy_data["_frenzied"] = True
            enemy_data["damage"] = int(enemy_data["damage"] * 1.5)
            enemy_data["defense"] = max(0, enemy_data["defense"] - 3)
            enemy_data["attack_interval"] = max(0.3, enemy_data.get("attack_interval", 2.0) * 0.6)
            msgs.append(f"[狂暴] {random.choice(self.RACIAL_NARRATIVES['frenzy']).format(name=name)} "
                        f"(伤害+50%, 防御-3, 攻速+40%)")

        # ── 龙族喷吐：每N回合 ──
        breath_interval = racial.get("breath", 0)
        if breath_interval > 0 and round_num > 0 and round_num % breath_interval == 0:
            dmg = int(enemy_data["damage"] * 1.8)
            msgs.append(f"[龙息] {random.choice(self.RACIAL_NARRATIVES['breath']).format(name=name)} "
                        f"(伤害×1.8={dmg})")
            if character:
                character.take_damage(dmg)

        # ── 昆虫结网 ──
        web_chance = racial.get("web", 0)
        if web_chance > 0 and random.random() < web_chance and not enemy_data.get("_webbed_player"):
            enemy_data["_webbed_player"] = True
            msgs.append(f"[结网] {random.choice(self.RACIAL_NARRATIVES['web']).format(name=name)} "
                        "攻击间隔+50%")

        # ── 巨人眩晕 ──
        stomp = racial.get("stomp", 0)
        if stomp > 0 and random.random() < stomp and not enemy_data.get("_stomped"):
            enemy_data["_stomped"] = True
            msgs.append(f"[重踏] {random.choice(self.RACIAL_NARRATIVES['stomp']).format(name=name)} "
                        "你被眩晕一回合！")

        return msgs

    def _tick_environment(self, env_tag: str, enemy_data: dict, name: str) -> List[str]:
        """房间环境效果 — 每场战斗只播报一次（标记防每帧刷屏）"""
        msgs = []
        if enemy_data.get("_env_narrated"):
            return msgs
        template = self.ENV_NARRATIVES.get(env_tag)
        if template:
            enemy_data["_env_narrated"] = True
            msgs.append(f"[环境] {random.choice(template)}")
        return msgs

    def on_enemy_death_rattle(self, enemy_data: dict, character) -> List[str]:
        """敌人死亡时检查亡语效果"""
        msgs = []
        racial = enemy_data.get("racial_abilities", {})
        if racial.get("death_rattle"):
            remaining_hp = enemy_data.get("hp", 0)
            dmg = max(1, int(remaining_hp * 0.5 + 2))
            if character:
                character.take_damage(dmg)
            msgs.append(
                f"[亡语] {random.choice(self.RACIAL_NARRATIVES['death_rattle']).format(name=enemy_data.get('base_name', '它'))} (-{dmg}HP)"
            )
        return msgs

    def apply_env_combat_modifiers(self, enemy_data: dict, env_tag: str):
        """应用环境战斗修正（在战斗开始时调用一次）"""
        if not env_tag:
            return

        from .dungeon_service import ENVIRONMENT_EFFECTS
        effects = ENVIRONMENT_EFFECTS.get(env_tag, {})
        if not effects:
            return

        # 火焰环境增强
        if effects.get("fire_bonus", 0) != 0:
            enemy_data["fire_damage"] = enemy_data.get("fire_damage", 0) + effects["fire_bonus"]
        # 冰霜环境
        if effects.get("ice_bonus", 0) != 0:
            enemy_data["slow"] = enemy_data.get("slow", 0) + 2
        # 亡灵环境
        if effects.get("undead_regen", 0) != 0 and "亡灵系" in enemy_data.get("tags", []):
            enemy_data["regen"] = enemy_data.get("regen", 0) + effects["undead_regen"]
        # 暗影环境
        if effects.get("evasion_bonus", 0) != 0:
            enemy_data["evasion"] = enemy_data.get("evasion", 0) + effects["evasion_bonus"]
        # 血域
        if effects.get("life_steal_bonus", 0) != 0:
            enemy_data["life_steal"] = enemy_data.get("life_steal", 0) + effects["life_steal_bonus"]

    def _check_element_reactions(self, enemy_data: dict, env_tag: str,
                                  name: str) -> List[str]:
        """检查元素 × 环境 × 种族 三元交互反应"""
        msgs = []
        affix_effects = enemy_data.get("affix_effects", {})
        tags = enemy_data.get("tags", [])

        for element, env_tags, race_tags, narrative, effects in self.ELEMENT_REACTIONS:
            # 检查元素激活
            if affix_effects.get(element, 0) <= 0:
                continue
            # 检查环境
            if env_tags and env_tag not in env_tags:
                continue
            # 检查种族标签
            if race_tags and not any(t in tags for t in race_tags):
                continue
            # 触发反应！（仅首次）
            reaction_key = f"_reacted_{element}_{env_tag}"
            if enemy_data.get(reaction_key):
                continue
            enemy_data[reaction_key] = True

            msgs.append(f"[反应] {narrative.format(name=name)}")
            # 应用效果
            if effects.get("bonus_dmg"):
                enemy_data["hp"] = max(0, enemy_data["hp"] - effects["bonus_dmg"])
            if effects.get("debuff_def"):
                enemy_data["defense"] = max(0, enemy_data["defense"] + effects["debuff_def"])
            if effects.get("stun_bonus"):
                enemy_data["stun_chance"] = enemy_data.get("stun_chance", 0) + effects["stun_bonus"]
            if effects.get("ls_bonus"):
                enemy_data["life_steal"] = enemy_data.get("life_steal", 0) + effects["ls_bonus"]
            if effects.get("regen_bonus"):
                enemy_data["regen"] = enemy_data.get("regen", 0) + effects["regen_bonus"]
            if effects.get("slow_penalty"):
                enemy_data["slow"] = max(0, enemy_data.get("slow", 0) + effects["slow_penalty"])
            if effects.get("dot_bonus"):
                enemy_data["poison"] = enemy_data.get("poison", 0) + effects["dot_bonus"]

        return msgs
