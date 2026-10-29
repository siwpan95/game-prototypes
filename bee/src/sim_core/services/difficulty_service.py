# -*- coding: utf-8 -*-
"""
动态难度调整服务 (DDA — Dynamic Difficulty Adjustment)

设计理念：怪物等级 = 玩家等级，只保留基础属性模板。
DDA 在此基础上做百分比缩放，实现真正的动态难度。

核心公式（无界幂函数，无理论上限）：
    D(level) = M * [max(0, level - L_safe)] ** p

    level <= L_safe  →  D = 0（新手保护，无缩放）
    level >  L_safe  →  D 随等级持续增长

词缀系统（集成到 DDA 中）：
    每个怪物生成时随机附加词缀（来自 enemy_affixes.json）
    词缀数量和品质 → 计算 level_bonus → 有效等级 = 玩家等级 + level_bonus
    DDA 用有效等级计算难度系数，词缀不再是额外乘区
"""
from __future__ import annotations
import math
import random
from typing import List, Optional


class DifficultyService:
    """
    DDA 动态难度服务 — 幂函数无界缩放 + 词缀系统集成
    核心：D(level) = M * [max(0, level - L_safe)] ** p
    """

    # ══════════════════════════════════════════════════
    #  D(level) 幂函数参数（无理论上限，增速渐缓）
    #    L_safe 以下：D=0（新手保护，无缩放）
    #    L_safe 以上：D 持续增长，导数 ~ p*M*(lv-L_safe)^(p-1)
    # ══════════════════════════════════════════════════
    M       = 1.50    # 整体缩放系数（控制 D 绝对值大小）
    L_SAFE  = 3.0     # 新手保护等级（低于此等级 D=0）
    P       = 0.55    # 曲率指数（0<p<1，越小后期越平缓）

    # ══════════════════════════════════════════════════
    #  强化系数 alpha — p=+1（怪物属性随等级增强）
    # ══════════════════════════════════════════════════
    ATK_COEFF  = 0.45   # 攻击力系数
    HP_COEFF   = 0.55   # 生命值系数
    DEF_COEFF  = 0.35   # 防御力系数
    FREQ_COEFF = 0.50   # 攻击频率系数

    # ════════════════════════════════════════════════
    #  1级怪物基准值（取现有数值的最低值）
    #  所有怪物共用同一套基准值，DDA 负责按等级缩放
    # ════════════════════════════════════════════════
    BASE_HP      = 42   # 1级基准HP
    BASE_DAMAGE  = 1    # 1级基准伤害（与 BASE_DEFENSE 对齐）
    BASE_DEFENSE = 1    # 1级基准防御
    BASE_EXP     = 11   # 1级基准经验
    BASE_GOLD    = 6    # 1级基准金币


    # ══════════════════════════════════════════════════
    #  衰减系数 beta — p=-1（奖励随等级衰减）
    # ══════════════════════════════════════════════════
    LOOT_PENALTY = 0.15  # 掉落率衰减
    EXP_PENALTY  = 0.10  # 经验/金币衰减

    BASE_ATTACK_INTERVAL = 3.0

    # ══════════════════════════════════════════════════
    #  反馈回路：自适应 regen 抑制
    #  当近期战斗显示玩家 DPS 不足时，自动降低敌人回血
    # ══════════════════════════════════════════════════
    FEEDBACK_WINDOW        = 15        # 追踪最近 15 场战斗
    REGEN_THREAT_THRESHOLD = 0.30      # enemy_regen > 30% * party_dps 视为威胁
    SUPPRESSION_RAMP_UP    = 0.25      # 每次威胁战斗增加 25% 抑制
    SUPPRESSION_DECAY      = 0.05      # 每次正常战斗衰减 5% 抑制
    STALEMATE_TIMEOUT      = 45.0      # 战斗超过 45 秒无进展 → 判定为僵局

    # ── 词缀数量随等级动态增长 ──
    #  低等级 0~2，高等级最多 5 个，让任何怪物都能当 Boss
    # ───────────────────────────────────

    def _max_affixes(self, level: float) -> int:
        """根据玩家等级返回词缀上限"""
        if level <= 20:
            return 2
        if level <= 50:
            return 3
        if level <= 80:
            return 4
        return 5

    # ── 稀有度变体系统 ──
    RARITY_TABLE = [
        ("普通", 1.0,  1, 3,  0.80, ""),           # 80%
        ("精英", 1.5,  3, 5,  0.95, "【精英】"),    # 15%
        ("稀有", 2.5,  5, 7,  0.99, "【稀有】"),    # 4%
        ("传说", 5.0,  7, 10, 1.0,  "【传说】"),    # 1%
    ]

    # ── 词缀关键词 → 战斗效果映射 ──
    AFFIX_EFFECTS = {
        # 物理伤害系
        "锋利":   ("crit_up",     0.03),  "破甲":   ("armor_pen",   0.15),
        "残酷":   ("damage_up",   0.10),  "重创":   ("crit_up",     0.05),
        "穿刺":   ("armor_pen",   0.10),  "致命":   ("crit_up",     0.06),
        "撕裂":   ("crit_up",     0.05),  "连击":   ("attack_speed",0.20),
        "弧光":   ("attack_speed",0.15),
        # 火焰系
        "灼热":   ("fire_damage", 0.08),  "烈焰":   ("fire_damage", 0.12),
        "熔岩":   ("fire_damage", 0.10),  "炎":     ("fire_damage", 0.06),
        "太阳":   ("fire_damage", 0.10),  "凤凰":   ("fire_damage", 0.10),
        "辉光":   ("fire_damage", 0.06),
        # 冰霜系
        "冰霜":   ("slow",        1),     "寒冰":   ("slow",         1),
        "冻结":   ("freeze_chance",0.03), "霜冻":   ("slow",         1),
        "霜":     ("slow",        0),
        # 闪电系
        "闪电":   ("shock",       1),     "震击":   ("shock",        1),
        "雷鸣":   ("shock",       1),     "暴风":   ("attack_speed", 0.10),
        # 毒素系
        "剧毒":   ("poison",      2),     "毒":     ("poison",       1),
        # 吸血系
        "吸血":   ("life_steal",  0.10),  "虹吸":   ("life_steal",   0.08),
        "噬魂":   ("life_steal",  0.08),  "血族":   ("life_steal",   0.12),
        "血怒":   ("life_steal",  0.08),  "血":     ("life_steal",   0.05),
        # 加速系
        "迅捷":   ("attack_speed",0.30),  "灵巧":   ("attack_speed", 0.20),
        "暴走":   ("attack_speed",0.25),
        # 防御/坦克系
        "坚固":   ("defense_up",  0.50),  "铁壁":   ("defense_up",   0.50),
        "金刚":   ("defense_up",  0.60),  "龙甲":   ("defense_up",   0.40),
        "壁垒":   ("defense_up",  0.40),  "铜肤":   ("defense_up",   0.30),
        "龙鳞":   ("defense_up",  0.35),  "磐石":   ("defense_up",   0.55),
        "魂甲":   ("defense_up",  0.35),  "护盾":   ("shield",       5),
        "血盾":   ("shield",      3),     "圣盾":   ("shield",       5),
        "重铸":   ("defense_up",  0.20),
        # 反伤系
        "荆棘":   ("thorns",      0.08),  "反射":   ("thorns",       0.10),
        "反伤":   ("thorns",      0.10),
        # 回复系
        "不朽":   ("hp_up",       0.30),  "回生":   ("regen",        3),
        "再生":   ("regen",       5),     "守护":   ("regen",        2),
        "活力":   ("hp_up",       0.20),
        # 魔法/灵能系
        "符文":   ("damage_up",   0.10),  "魔纹":   ("damage_up",    0.15),
        "魔力":   ("damage_up",   0.10),  "灵能":   ("damage_up",    0.15),
        # 狂暴/毁灭系
        "狂暴":   ("damage_up",   0.30),  "毁灭":   ("damage_up",    0.40),
        "天罚":   ("crit_up",     0.08),  "巨人之力":("damage_up",   0.25),
        "天启":   ("damage_up",   0.20),  "战意":   ("damage_up",    0.15),
        # 亡魂/诅咒系
        "亡魂":   ("death_save_up",0.05), "灵魂":   ("life_steal",   0.05),
        "诅咒":   ("all_down",     0.10), "灵体":   ("evasion",      0.05),
        # 闪避系
        "暗影":   ("evasion",      0.10), "幻影":   ("evasion",      0.15),
        "星光":   ("evasion",      0.05), "月光":   ("evasion",      0.05),
        "虚无":   ("evasion",      0.08), "暗":     ("evasion",      0.05),
        # 元素系
        "元素":   ("all_up",       0.05), "大地":   ("defense_up",   0.30),
        "海洋":   ("regen",        2),    "时空":   ("attack_speed", 0.15),
        # 体型系
        "巨型":   ("hp_up",        0.40), "微小":   ("attack_speed", 0.40),
        # 特殊猎杀
        "恶魔猎手":("species_dmg_demon",0.20), "屠龙":  ("species_dmg_dragon",0.20),
        # 组合型
        "深渊":   ("damage_up",    0.25), "祝福":   ("regen",        2),
        "神谕":   ("all_up",       0.08), "禁咒":   ("all_up",       0.10),
    }

    # ── 种族标签 → 固有技能 ──
    RACIAL_ABILITIES = {
        "亡灵":    {"death_rattle": True},    # 死亡时对玩家造成剩余HP伤害
        "不死族":  {"death_rattle": True},
        "龙族":    {"breath": 5},              # 每N回合范围喷吐
        "构造体":  {"thorns_mod": 0.10},       # 反伤加成
        "吸血鬼":  {"life_steal_mod": 0.15},   # 吸血加成
        "昆虫":    {"web": 0.03},              # 概率结网减速
        "野兽":    {"frenzy_hp_pct": 0.30},    # 低血量狂暴
        "恶魔":    {"frenzy_hp_pct": 0.30},
        "元素":    {"elemental_immune": True}, # 免疫同元素伤害
        "史莱姆":  {"split_chance": 0.05},     # 概率分裂
        "虚空":    {"evasion_mod": 0.08},      # 额外闪避
        "暗影":    {"evasion_mod": 0.05},
        "天使":    {"regen_mod": 2},            # 每秒回血（降低原5→2）
        "巨人":    {"stomp": 0.10},             # 概率眩晕
        "巨魔":    {"regen_mod": 1},          # 每秒回血（降低原3→1）
    }

    def _roll_affixes(self, level: float = 1.0, min_n: int = 1, max_n: int = 3) -> List[str]:
        """随等级和稀有度动态摇前缀"""
        if not self._enemy_affixes:
            return []
        n = random.randint(min_n, max_n)
        k = min(n, len(self._enemy_affixes))
        return random.sample(self._enemy_affixes, k=k)

    def _roll_rarity(self, level: float = 1.0) -> tuple:
        """摇稀有度 → (名称, 属性倍率, min词缀, max词缀)

        低等级保护：Lv<5 仅普通、Lv<10 解锁精英、Lv<20 解锁稀有、
        传说仅 Lv≥20 出现，避免新手角色撞上 5 倍属性怪。
        """
        if level < 5:
            table = self.RARITY_TABLE[:1]
        elif level < 10:
            table = self.RARITY_TABLE[:2]
        elif level < 20:
            table = self.RARITY_TABLE[:3]
        else:
            table = self.RARITY_TABLE
        roll = random.random()
        for name, mult, min_a, max_a, threshold, prefix in table:
            if roll < threshold:
                return (name, mult, min_a, max_a, prefix)
        return (table[-1][0], table[-1][1], table[-1][2], table[-1][3], table[-1][5])

    def _parse_affix_effects(self, affixes: List[str]) -> dict:
        """解析词缀关键词 → 战斗效果字典"""
        effects = {}
        for affix in affixes:
            for keyword, (effect_type, value) in self.AFFIX_EFFECTS.items():
                if keyword in affix:
                    effects.setdefault(effect_type, 0)
                    effects[effect_type] = round(effects[effect_type] + value, 3)
        # 上限保护
        for key in effects:
            if key in ("fire_damage", "damage_up", "hp_up", "defense_up",
                       "evasion", "life_steal", "thorns", "attack_speed",
                       "crit_up", "all_up", "armor_pen", "death_save_up",
                       "species_dmg_demon", "species_dmg_dragon"):
                effects[key] = min(effects[key], 0.75)
            elif key in ("poison", "shock", "slow", "regen", "shield"):
                effects[key] = min(effects[key], 15)
            elif key == "freeze_chance":
                effects[key] = min(effects[key], 0.15)
        return effects

    def _parse_racial_abilities(self, tags: list) -> dict:
        """解析种族标签 → 固有技能配置"""
        abilities = {}
        for tag in tags:
            if tag in self.RACIAL_ABILITIES:
                abilities.update(self.RACIAL_ABILITIES[tag])
        return abilities

    def __init__(self):
        self._enemy_affixes: list = []
        self._current_player_level: float = 1.0
        self._tick_accumulator = 0.0

        # ── 反馈回路：DPS 追踪 + regen 自适应抑制 ──
        self._combat_history: list = []     # [{dps, duration, success, regen, max_hp, threat}, ...]
        self._regen_suppression: float = 0.0  # 0.0~1.0，当前 regen 抑制比例
        self._feedback_hint: str = ""          # UI 提示文本

    def set_affix_pool(self, affixes: list):
        """注入前缀池（由外部数据源提供，不做文件 I/O）"""
        self._enemy_affixes = affixes

    def update_player_level(self, level: float):
        """更新当前玩家等级（供渲染 UI 查询 DDA 状态）"""
        self._current_player_level = level

    @property
    def dda_level(self) -> int:
        """DDA 难度等级 0-5（用于 UI 进度条显示）"""
        D = self._difficulty(self._current_player_level)
        if D <= 0:
            return 0
        if D <= 3:
            return 1
        if D <= 6:
            return 2
        if D <= 10:
            return 3
        if D <= 18:
            return 4
        return 5

    def get_enemy_attribute_multiplier(self) -> float:
        """返回敌人属性综合倍率 = 1 + avg_coeff * D"""
        D = self._difficulty(self._current_player_level)
        avg_coeff = (self.ATK_COEFF + self.HP_COEFF + self.DEF_COEFF) / 3.0
        return 1.0 + avg_coeff * D

    def get_reward_multiplier(self) -> float:
        """返回奖励倍率 = 1 / (1 + beta * D)"""
        D = self._difficulty(self._current_player_level)
        return 1.0 / (1.0 + self.EXP_PENALTY * D)

    def get_loot_drop_rate_multiplier(self) -> float:
        """返回战利品掉落率倍率 = 1 / (1 + LOOT_PENALTY * D)"""
        D = self._difficulty(self._current_player_level)
        return 1.0 / (1.0 + self.LOOT_PENALTY * D)

    def on_combat_end(self, combat_duration: float, success: bool,
                      total_damage: int = 0, enemy_max_hp: int = 1,
                      enemy_regen: float = 0.0):
        """战斗结束通知 — 收集 DPS 数据用于反馈回路

        Args:
            combat_duration: 战斗持续时间（秒）
            success: 是否成功击杀
            total_damage: 本场战斗玩家造成的总伤害
            enemy_max_hp: 敌人最大生命值
            enemy_regen: 敌人每秒回血量
        """
        if combat_duration <= 0:
            return

        party_dps = total_damage / combat_duration if combat_duration > 0 else 0

        # 计算 regen 威胁系数：regen 占 DPS 的比例
        threat = enemy_regen / max(1, party_dps) if enemy_regen > 0 else 0.0

        # 如果战斗失败(未击杀)或僵局，视作重大威胁
        if not success:
            # 战斗失败(逃跑/死亡) → 全额威胁
            threat = max(threat, 1.0)
        elif combat_duration > self.STALEMATE_TIMEOUT:
            # 超长时间战斗 → 僵局惩罚
            threat = max(threat, 0.8)

        self._combat_history.append({
            "dps": party_dps, "duration": combat_duration,
            "success": success, "regen": enemy_regen,
            "max_hp": enemy_max_hp, "threat": threat,
        })

        # 保持窗口大小
        while len(self._combat_history) > self.FEEDBACK_WINDOW:
            self._combat_history.pop(0)

        # 更新抑制参数
        self._update_regen_suppression()

    def _update_regen_suppression(self):
        """根据近期战斗历史更新 regen 抑制强度

        策略：
        - 每场威胁战斗（threat > 阈值）：+25% 抑制
        - 每场正常战斗（threat < 阈值）：-5% 抑制（缓慢恢复）
        - 抑制在 0%~100% 之间平滑变化
        """
        if not self._combat_history:
            return

        # 只对最近 K 场做增量修正（避免窗口内全部重新计算）
        latest = self._combat_history[-1]
        threat = latest.get("threat", 0.0)

        if threat > self.REGEN_THREAT_THRESHOLD:
            # 有威胁 → 增加抑制
            self._regen_suppression = min(1.0, self._regen_suppression + self.SUPPRESSION_RAMP_UP)
            if self._regen_suppression > 0.5:
                self._feedback_hint = "⚡回血抑制中"
            elif self._regen_suppression > 0.1:
                self._feedback_hint = "△回血微调中"
            else:
                self._feedback_hint = ""
        else:
            # 无威胁 → 缓慢衰减
            self._regen_suppression = max(0.0, self._regen_suppression - self.SUPPRESSION_DECAY)
            if self._regen_suppression <= 0.02:
                self._regen_suppression = 0.0
                self._feedback_hint = ""

    def report_stalemate(self, enemy_regen: float):
        """报告僵局：战斗长时间无进展（敌人血条不动）"""
        # 直接视为高威胁事件
        self._combat_history.append({
            "dps": 0, "duration": self.STALEMATE_TIMEOUT,
            "success": False, "regen": enemy_regen,
            "max_hp": 1, "threat": 1.5,
        })
        while len(self._combat_history) > self.FEEDBACK_WINDOW:
            self._combat_history.pop(0)
        self._update_regen_suppression()

    @property
    def regen_suppression(self) -> float:
        """当前 regen 抑制比例（0~1），供 scale_enemy_template 使用"""
        return self._regen_suppression

    @property
    def feedback_hint(self) -> str:
        """反馈状态提示文本，供 UI 显示"""
        return self._feedback_hint

    def get_feedback_status(self) -> dict:
        """返回反馈回路完整状态（供 UI / 存档使用）"""
        return {
            "suppression": round(self._regen_suppression, 3),
            "hint": self._feedback_hint,
            "history_count": len(self._combat_history),
        }

    def tick(self, dt: float) -> list:
        """DDA 长期评估（每约 120 秒检测一次，当前为纯等级驱动，暂不输出）"""
        self._tick_accumulator += dt
        if self._tick_accumulator < 120.0:
            return []
        self._tick_accumulator = 0.0
        return []

    # ================================================================
    #  核心公式：幂函数（无界，纯等级驱动）
    # ================================================================

    def _difficulty(self, level: float) -> float:
        """
        世界动态难度系数 D（幂函数，仅与玩家等级挂钩）：

            D(level) = M * [max(0, level - L_safe)] ** P

        无理论上限，增速随等级升高逐渐放缓。
        """
        above = max(0.0, level - self.L_SAFE)
        return self.M * (above ** self.P)

    # ================================================================
    #  公开查询
    # ================================================================

    @property
    def enemy_affixes_loaded(self) -> int:
        """已加载的敌人词缀数量（探针用）"""
        return len(self._enemy_affixes)

    def get_monster_attack_interval(self, player_level: float) -> float:
        """
        怪物攻击间隔 = T0 / (1 + k_freq * D)
        玩家等级越高、DDA 难度越高 → 攻击间隔越短
        """
        D = self._difficulty(player_level)
        return max(0.3, self.BASE_ATTACK_INTERVAL / (1.0 + self.FREQ_COEFF * D))

    # ================================================================
    #  统一缩放工具
    # ================================================================

    @staticmethod
    def _apply(base: float, coeff: float, D: float, direction: int) -> float:
        """
        统一缩放公式（无保底/封顶）：

          direction=+1 → V = V0 * (1 + coeff * D)   增强
          direction=-1 → V = V0 / (1 + coeff * D)   衰减
        """
        denom = 1.0 + coeff * D
        if direction > 0:
            return base * max(0.1, denom)
        else:
            return base / max(0.5, denom)

    # ================================================================
    #  生成缩放后的敌人（词缀仅花里胡哨，不影响数值）
    # ================================================================

    def scale_enemy_template(self, template: dict, party) -> dict:
        """
        根据队伍平均等级生成缩放后的敌人模板。

        流程：
          1. 计算队伍平均等级 → D(avg_lv)
          2. 摇稀有度 → 属性倍率 + 词缀数量区间
          3. 摇词缀 → 解析战斗效果
          4. 解析种族技能
          5. 用 D + 稀有度倍率 + 词缀效果 缩放属性
          6. 组装最终敌人字典
        """
        avg_lv = self.party_avg_level(party)
        display_lv = int(avg_lv)
        D = self._difficulty(avg_lv)

        base_name = template.get("name", "未知")
        enemy_tags = list(template.get("tags", []))

        # ── 稀有度 ──
        rarity_name, rarity_mult, min_affix, max_affix, rarity_prefix = self._roll_rarity(avg_lv)

        # ── 词缀（低等级收敛词缀数，避免回复词缀堆叠成死亡螺旋）──
        level_affix_cap = self._max_affixes(avg_lv)
        min_affix = min(min_affix, level_affix_cap)
        max_affix = min(max_affix, level_affix_cap)
        rolled = self._roll_affixes(avg_lv, min_affix, max_affix)
        affix_effects = self._parse_affix_effects(rolled)

        # ── 种族技能 ──
        racial_abilities = self._parse_racial_abilities(enemy_tags)

        # ── 基础属性缩放（DDA × 稀有度）× ──
        base_hp    = max(5,  int(self._apply(self.BASE_HP,     self.HP_COEFF,  D, +1) * rarity_mult))
        base_dmg   = max(1,  int(self._apply(self.BASE_DAMAGE, self.ATK_COEFF, D, +1) * rarity_mult))
        base_def   = max(0,  int(self._apply(self.BASE_DEFENSE,self.DEF_COEFF, D, +1) * rarity_mult))
        base_exp   = max(1,  int(self._apply(self.BASE_EXP,    self.EXP_PENALTY,D, -1) * rarity_mult))
        base_gold  = max(1,  int(self._apply(self.BASE_GOLD,   self.EXP_PENALTY,D, -1) * rarity_mult))

        # ── 词缀属性修正 ──
        # arm_pen / species_dmg_* 折算为 damage_up；all_down 反向修正
        bonus_dmg = (affix_effects.get("armor_pen", 0)
                     + affix_effects.get("species_dmg_demon", 0)
                     + affix_effects.get("species_dmg_dragon", 0))
        all_down = affix_effects.get("all_down", 0)

        hp_mod    = 1.0 + affix_effects.get("hp_up", 0) + affix_effects.get("all_up", 0) - all_down
        dmg_mod   = 1.0 + affix_effects.get("damage_up", 0) + affix_effects.get("all_up", 0) + bonus_dmg - all_down
        def_mod   = 1.0 + affix_effects.get("defense_up", 0) + affix_effects.get("all_up", 0) - all_down
        atk_spd   = max(0.3, 1.0 + affix_effects.get("attack_speed", 0))

        # ── 种族修正叠加 ──
        life_steal = affix_effects.get("life_steal", 0) + racial_abilities.get("life_steal_mod", 0)
        evasion    = affix_effects.get("evasion", 0) + racial_abilities.get("evasion_mod", 0)
        thorns     = affix_effects.get("thorns", 0) + racial_abilities.get("thorns_mod", 0)
        regen      = affix_effects.get("regen", 0) + racial_abilities.get("regen_mod", 0)

        # ── 反馈回路：regen 自适应抑制 ──
        # 当近期战斗显示玩家 DPS 不足时，按比例削弱敌人回血
        if self._regen_suppression > 0.01 and regen > 0:
            original_regen = regen
            regen = int(regen * (1.0 - self._regen_suppression))
            regen = max(1, regen)  # 至少保留 1，不完全移除
            # 高抑制时直接移除词缀来源的 regen（保留种族基础）
            if self._regen_suppression > 0.6 and affix_effects.get("regen", 0) > 0:
                affix_effects["regen"] = 0
                regen = max(1, racial_abilities.get("regen_mod", 0))

        # ── 组装最终敌人 ──
        enemy = {
            "name":            base_name,
            "base_name":       base_name,
            "tags":            enemy_tags,
            "level":           display_lv,
            "rarity":          rarity_name,
            "rarity_prefix":   rarity_prefix,
            "hp":              max(5,  int(base_hp * hp_mod)),
            "damage":          max(1,  int(base_dmg * dmg_mod)),
            "defense":         max(0,  int(base_def * def_mod)),
            "exp":             base_exp,
            "gold":            base_gold,
            "loot_table":      template.get("loot_table", "normal"),
            "race":            template.get("race", "?"),
            "description":     template.get("description", ""),
            "max_hp":          max(5,  int(base_hp * hp_mod)),
            "attack_interval": max(0.2, self.get_monster_attack_interval(avg_lv) / max(0.3, atk_spd)),
            "evasion":         min(0.30, evasion),
            "thorns":          min(0.50, thorns),
            "regen":           min(8,    regen),     # 每秒回血上限（降低原20→8）
            "life_steal":      min(0.50, life_steal),
            "death_save":      affix_effects.get("death_save_up", 0),
            "fire_damage":     affix_effects.get("fire_damage", 0),
            "poison":          affix_effects.get("poison", 0),
            "shock":           affix_effects.get("shock", 0),
            "slow":            affix_effects.get("slow", 0),
            "freeze_chance":   affix_effects.get("freeze_chance", 0),
            "crit_chance":     0.05 + affix_effects.get("crit_up", 0),
            "shield":          int(affix_effects.get("shield", 0)),
            "affixes":         rolled,
            "affix_effects":   affix_effects,
            "racial_abilities": racial_abilities,
            "auras":           [],
            "stun_chance":     racial_abilities.get("stomp", 0),
            "size_multiplier": 1.0 + (0.5 if "大型" in enemy_tags else 0),
        }

        # ── 拼接显示名称：稀有度标识 + 词缀 + 基础名 ──
        display = base_name
        if rolled:
            display = "".join(rolled) + display
        if rarity_prefix:
            display = rarity_prefix + display
        enemy["name"] = display

        return enemy

    def scale_enemy_in_place(self, enemy: dict, party) -> dict:
        """战斗开始时对已有敌人重新缩放（以队伍当前等级为准，词缀不影响数值）"""
        avg_lv = self.party_avg_level(party)
        D = self._difficulty(avg_lv)

        hp_pct = enemy.get("hp", 1) / max(1, enemy.get("max_hp", 1))
        enemy["max_hp"] = max(5,  int(self._apply(enemy.get("max_hp", 30), self.HP_COEFF,   D, +1)))
        enemy["hp"]      = max(1,  int(enemy["max_hp"] * hp_pct))
        enemy["damage"]  = max(1,  int(self._apply(enemy.get("damage", 5),  self.ATK_COEFF,  D, +1)))
        enemy["defense"] = max(0,  int(self._apply(enemy.get("defense", 0), self.DEF_COEFF,  D, +1)))
        return enemy

    # ================================================================
    #  队伍等级工具
    # ================================================================

    @staticmethod
    def party_avg_level(party) -> float:
        """计算队伍平均等级"""
        if not party or not hasattr(party, "members") or not party.members:
            return 1.0
        levels = [m.level for m in party.members if hasattr(m, "level")]
        if not levels:
            return 1.0
        return sum(levels) / len(levels)

    # ================================================================
    #  冒烟测试辅助：统计快照
    # ================================================================

    def probe_snapshot(self) -> dict:
        """返回当前 DDA 状态快照（供冒烟测试收集）"""
        return {
            "affixes_loaded": len(self._enemy_affixes),
        }

    # ================================================================
    #  序列化
    # ================================================================

    def to_dict(self) -> dict:
        return {
            "combat_count":     0,
            "regen_suppression": round(self._regen_suppression, 3),
            # 历史记录仅保留摘要（避免存档膨胀）
            "recent_threats":   [round(h.get("threat", 0), 2) for h in self._combat_history[-10:]],
        }

    def load_dict(self, data: dict):
        if "regen_suppression" in data:
            self._regen_suppression = float(data["regen_suppression"])
            if self._regen_suppression > 0.01:
                self._feedback_hint = "⚡回血抑制中" if self._regen_suppression > 0.5 else "△回血微调中"
