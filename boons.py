# -*- coding: utf-8 -*-
"""众神赐福系统（Boons）——哈迪斯式赐福的北欧化实现。

设计对照（调研结论落地）：
- 稀有度三档：普通 ×1.0 / 稀有 ×1.7 / 史诗 ×2.6（Hades: Common/Rare/Epic）
- 每神一个专精方向（Hades: Zeus=连锁闪电 / Artemis=暴击 …）
- 同一赐福重复获得 = 叠层（Hades: Pom of Power 的简化）
- 持有某神 3 种不同赐福 -> 触发该神「眷顾」（Hades: Legendary 的前置理念）
- 周期型赐福（天雷/治疗/寒风）在 BoonState.tick 里驱动

数值语义：per = 每层普通稀有度的增量；实际值 = per * stacks * rarity_mult。
"""
import math
import random

from settings import COL

RARITIES = [
    dict(name="普通", mult=1.0, color=(210, 214, 224)),
    dict(name="稀有", mult=1.7, color=(96, 170, 255)),
    dict(name="史诗", mult=2.6, color=(190, 120, 255)),
]
RARITY_WEIGHTS = (62, 28, 10)      # roll 权重


def roll_rarity():
    return random.choices(range(len(RARITIES)), weights=RARITY_WEIGHTS)[0]


GODS = {
    "odin": dict(
        name="奥丁", title="全知之父", color=(150, 168, 255), sym="ᚨ",
        boons=dict(
            ravens_eye=dict(name="渡鸦之眼", per=0.040,
                            desc="暴击率 +{pct}%（暴击伤害翻倍）"),
            sage_blood=dict(name="贤者之血", per=0.15,
                            desc="经验获取 +{pct}%"),
            runes=dict(name="符文精通", per=0.10,
                       desc="全部武器伤害 +{pct}%"),
        ),
        favor=dict(name="诸神黄昏", desc="暴击伤害由 ×2 升至 ×2.5"),
    ),
    "thor": dict(
        name="托尔", title="雷霆之主", color=(255, 208, 96), sym="ᚦ",
        boons=dict(
            chain_light=dict(name="连锁闪电", per=0.08,
                             desc="命中时 {pct}% 概率劈出跳 3 次的连锁闪电"),
            thunder_wrath=dict(name="雷霆震怒", per=1.0,
                               desc="每 {sec}s 一道天雷轰击最强之敌（伤害随层）"),
            hammer_bless=dict(name="神锤祝福", per=0.08,
                              desc="对精英与巨人的伤害 +{pct}%"),
        ),
        favor=dict(name="雷神降临", desc="连锁闪电跳 6 次，天雷一次劈 3 个目标"),
    ),
    "freya": dict(
        name="芙蕾雅", title="巫后", color=(255, 130, 190), sym="ᚠ",
        boons=dict(
            life_spring=dict(name="生命之泉", per=1.0,
                             desc="周期性回复生命（量随层）"),
            love_ward=dict(name="爱之护盾", per=5.0,
                           desc="获得吸收伤害的护盾，破碎后 8s 重铸"),
            fragrant_wind=dict(name="芬芳之风", per=0.06,
                               desc="移动速度 +{pct}%，拾取范围翻倍增长"),
        ),
        favor=dict(name="女神之吻", desc="护盾与治疗效果翻倍"),
    ),
    "loki": dict(
        name="洛基", title="诡计之神", color=(140, 235, 160), sym="ᛚ",
        boons=dict(
            doom_mark=dict(name="厄运标记", per=0.08,
                           desc="命中时 {pct}% 概率施加厄运，3 秒后爆炸"),
            shadow_trick=dict(name="诡计之影", per=0.05,
                              desc="受击时 {pct}% 概率完全闪避"),
            laughing_kill=dict(name="嬉笑杀戮", per=0.12,
                               desc="击杀时 {pct}% 概率散落 3 颗额外宝石"),
        ),
        favor=dict(name="千面神", desc="厄运爆炸范围近乎翻倍，闪避 +10%"),
    ),
    "heimdall": dict(
        name="海姆达尔", title="守望者", color=(255, 240, 180), sym="ᚺ",
        boons=dict(
            horn=dict(name="加拉尔号角", per=0.05,
                      desc="全部武器冷却 -{pct}%"),
            bifrost=dict(name="虹桥", per=0.05,
                         desc="移动速度 +{pct}%，受击时寒光迟滞周围敌人"),
            hawk_eye=dict(name="鹰眼", per=0.08,
                          desc="投射物速度 +{pct}%，体积增大"),
        ),
        favor=dict(name="守望者之誓", desc="冷却额外 -15%"),
    ),
    "skadi": dict(
        name="斯卡蒂", title="寒冬女猎手", color=(150, 220, 255), sym="ᛊ",
        boons=dict(
            winter_grasp=dict(name="寒冬之拥", per=0.08,
                              desc="冰霜新星的减速更强、更持久"),
            shatter=dict(name="碎冰之击", per=0.10,
                         desc="对被减速敌人的伤害 +{pct}%"),
            winter=dict(name="凛冬将至", per=1.0,
                        desc="周期性寒风扫过全场，冻伤并减速一切"),
        ),
        favor=dict(name="绝对凛冬", desc="寒风间隔减半"),
    ),
}

# 赐福叠层上限
BOON_MAX_STACKS = 3
# 触发神眷所需的不同赐福数
FAVER_NEED = 3


class BoonState:
    """game.boons：持有状态 + 加成聚合 + 周期效果驱动。"""

    def __init__(self):
        self.taken = {}          # (god, key) -> stacks
        self.rarity = {}         # (god, key) -> 首次获得的稀有度 mult（展示用）
        self.favors = set()      # 已触发的神眷
        self.timers = {}         # 周期计时器
        self.shield = 0.0
        self.shield_cd = 0.0

    # ---------------- 持有查询 ----------------
    def god_count(self, god):
        return sum(1 for (g, _) in self.taken if g == god)

    def total(self, god, key):
        """per * stacks * rarity_mult 之后的实际总量。"""
        st = self.taken.get((god, key), 0)
        if not st:
            return 0.0
        return _PER[(god, key)] * st * self.rarity.get((god, key), 1.0)

    def bonus(self, name):
        """跨神聚合某类加成（如 crit_chance 涉及多个来源时用映射表）。"""
        return sum(self.total(g, k) for (g, k) in _AGG.get(name, ()))

    # ---------------- 获得 ----------------
    def add(self, god, key, rarity_mult):
        """返回 (叠了层数, 是否首次, 是否触发神眷)。"""
        tk = (god, key)
        first = tk not in self.taken
        if first:
            self.taken[tk] = 1
            self.rarity[tk] = rarity_mult
        else:
            self.taken[tk] = min(BOON_MAX_STACKS, self.taken[tk] + 1)
        favor_on = False
        if god not in self.favors and self.god_count(god) >= FAVER_NEED:
            self.favors.add(god)
            favor_on = True
        return self.taken[tk], first, favor_on

    def candidates(self, god):
        """该神当前可选赐福（含可叠层的）。"""
        out = []
        for key in GODS[god]["boons"]:
            st = self.taken.get((god, key), 0)
            if st < BOON_MAX_STACKS:
                out.append(key)
        return out

    # ---------------- 周期效果 ----------------
    def tick(self, game, dt):
        p = game.player

        # 芙蕾雅·生命之泉
        per = self.total("freya", "life_spring")
        if per > 0:
            t = self.timers.get("heal", 0.0) + dt
            if t >= 6.0:
                t = 0.0
                mult = 2.0 if "freya" in self.favors else 1.0
                p.hp = min(p.hp_max, p.hp + per * 3.0 * mult)
                game.particles.ring(p.x, p.y, (120, 235, 160), n=10,
                                    speed=120, life=0.4, size=3)
            self.timers["heal"] = t

        # 芙蕾雅·爱之护盾
        ward = self.total("freya", "love_ward")
        if ward > 0:
            mult = 2.0 if "freya" in self.favors else 1.0
            cap = ward * 3.0 * mult
            if self.shield_cd > 0:
                self.shield_cd -= dt
                if self.shield_cd <= 0:
                    self.shield = cap
                    game.particles.ring(p.x, p.y, (255, 130, 190), n=12,
                                        speed=140, life=0.4, size=3)
            elif self.shield < cap:
                self.shield = cap      # 首次/重铸

        # 托尔·雷霆震怒：天雷劈最强敌人
        wr = self.total("thor", "thunder_wrath")
        if wr > 0:
            period = max(2.5, 9.0 - self.taken.get(("thor", "thunder_wrath"), 1) * 1.1)
            t = self.timers.get("skybolt", 0.0) + dt
            if t >= period:
                t = 0.0
                n_tg = 3 if "thor" in self.favors else 1
                targets = sorted((e for e in game.enemies if e.hp > 0),
                                 key=lambda e: -e.hp)[:n_tg]
                for e in targets:
                    game.skybolt(e, 40.0 * wr)
            self.timers["skybolt"] = t

        # 斯卡蒂·凛冬将至：全场寒风
        wv = self.total("skadi", "winter")
        if wv > 0:
            base = max(4.0, 10.0 - self.taken.get(("skadi", "winter"), 1) * 0.9)
            period = base * 0.5 if "skadi" in self.favors else base
            t = self.timers.get("blizzard", 0.0) + dt
            if t >= period:
                t = 0.0
                for e in game.enemies:
                    game.deal_damage(e, 6.0 * wv, flat=True)
                    e.apply_slow(0.30, 2.0)
                game.particles.ring(p.x, p.y, COL["frost"], n=26,
                                    speed=330, life=0.55, size=4)
                game.pulses.append([p.x, p.y, 20.0, 620.0, COL["frost"], 3, 0.5])
            self.timers["blizzard"] = t

        # 海姆达尔·虹桥：受击反制（由 game 在受击时调用 _bifrost_retaliate）

    # ---------------- 受击结算 ----------------
    def absorb_hit(self, dmg):
        """返回实际扣血量（先扣盾）。"""
        if self.shield > 0:
            if dmg <= self.shield:
                self.shield -= dmg
                return 0.0
            dmg -= self.shield
            self.shield = 0.0
            self.shield_cd = 8.0
        return dmg

    def try_dodge(self):
        """洛基·诡计之影：完全闪避判定。"""
        return random.random() < self.bonus("dodge")

    def bifrost_retaliate(self, game):
        st = self.taken.get(("heimdall", "bifrost"), 0)
        if st:
            dur = 1.5 + 0.5 * st
            for e in game.hash.query(game.player.x, game.player.y, 260):
                if math.hypot(e.x - game.player.x, e.y - game.player.y) <= 250 + e.radius:
                    e.apply_slow(0.5, dur)
            game.pulses.append([game.player.x, game.player.y, 20.0, 250.0,
                                (255, 240, 180), 3, 0.35])

    # ---------------- 结算展示 ----------------
    def summary(self):
        rows = []
        for (g, k), st in self.taken.items():
            gd = GODS[g]["boons"][k]
            rar = self.rarity.get((g, k), 1.0)
            tag = next(r["name"] for r in RARITIES if r["mult"] == rar)
            rows.append(f"{GODS[g]['name']}·{gd['name']} {tag}×{st}")
        for g in sorted(self.favors):
            rows.append(f"★{GODS[g]['favor']['name']}（{GODS[g]['name']}眷顾）")
        return rows


# ---------------- 聚合映射表 ----------------
_PER = {}
_AGG = {}
for _g, _gd in GODS.items():
    for _k, _bd in _gd["boons"].items():
        _PER[(_g, _k)] = _bd["per"]

_AGG = dict(
    crit_chance=(("odin", "ravens_eye"),),
    xp_gain=(("odin", "sage_blood"),),
    dmg_all=(("odin", "runes"),),
    chain_chance=(("thor", "chain_light"),),
    elite_dmg=(("thor", "hammer_bless"),),
    speed=(("freya", "fragrant_wind"), ("heimdall", "bifrost")),
    pickup=(("freya", "fragrant_wind"),),
    doom_chance=(("loki", "doom_mark"),),
    dodge=(("loki", "shadow_trick"),),
    gem_burst=(("loki", "laughing_kill"),),
    cdr=(("heimdall", "horn"),),
    proj_speed=(("heimdall", "hawk_eye"),),
    proj_size=(("heimdall", "hawk_eye"),),
    slow_bonus=(("skadi", "winter_grasp"),),
    slow_dmg=(("skadi", "shatter"),),
)


def boon_desc(god, key, rarity_mult):
    """按稀有度渲染描述文本。"""
    bd = GODS[god]["boons"][key]
    v = bd["per"] * rarity_mult * 100
    txt = bd["desc"].replace("{pct}", f"{v:.0f}")
    if key == "thunder_wrath":
        secs = max(2.5, 9.0 - 1.1 * rarity_mult)
        txt = f"每 {secs:.1f}s 一道天雷轰击最强之敌（伤害 {40 * rarity_mult:.0f}）"
    return txt
