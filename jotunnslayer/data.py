# -*- coding: utf-8 -*-
"""数据表：武器 / 敌人 / 被动 / Boss / 地图主题。

对应原作 StreamingAssets/ActiveItems.csv 的思路——内容全部走明文数据表，
逻辑代码只做通用执行器。想加武器/改数值，只改这个文件。
数值字段含义：
    cooldown  施放间隔(s)      damage   单次伤害
    count     弹体/实体数       pierce   可穿透敌人数(999=无限)
    speed     弹速(px/s)       lifetime 存活(s)
    radius    判定/作用半径     size     渲染尺寸
levels 是逐级增量（叠加到 base 上），index0 对应 1 级（空=无增量）。
敌型的行为字段（ranged/bomber/healer/aura/vampire）触发对应 AI 分支。
"""

# ============================ 武器表（12） ============================
WEAPONS = {
    "axe": dict(
        name="投掷战斧", kind="axe",
        desc="掷出旋切的战斧，直线穿透多个敌人",
        base=dict(cooldown=1.20, damage=12, count=1, pierce=3, speed=430.0,
                  lifetime=1.60, size=15),
        levels=[
            {},
            dict(count=1),
            dict(damage=8, pierce=2),
            dict(count=1, speed=60),
            dict(damage=14, pierce=3, size=4),
        ],
    ),
    "mjolnir": dict(
        name="雷霆之锤", kind="orbit",
        desc="双锤绕身环转，碾过靠近的敌人",
        base=dict(cooldown=0.35, damage=9, count=2, pierce=999, speed=2.6,
                  lifetime=0.0, radius=92.0, size=16),
        levels=[
            {},
            dict(count=1),
            dict(damage=5, radius=12),
            dict(count=1, speed=0.5),
            dict(damage=7, radius=16),
        ],
    ),
    "gungnir": dict(
        name="冈格尼尔", kind="spear",
        desc="锁定最强之敌掷出魔枪，洞穿路径上的一切",
        base=dict(cooldown=2.30, damage=28, count=1, pierce=999, speed=760.0,
                  lifetime=1.20, size=20),
        levels=[
            {},
            dict(damage=14),
            dict(count=1),
            dict(damage=18, speed=80),
            dict(count=1, damage=24, size=5),
        ],
    ),
    "rune_ring": dict(
        name="卢恩法阵", kind="pulse",
        desc="以自身为中心周期性引爆符文冲击",
        base=dict(cooldown=2.50, damage=11, count=0, pierce=999, speed=0.0,
                  lifetime=0.0, radius=120.0, size=0),
        levels=[
            {},
            dict(radius=18, damage=4),
            dict(cooldown=-0.30),
            dict(radius=22, damage=6),
            dict(cooldown=-0.40, damage=8),
        ],
    ),
    "frost_nova": dict(
        name="冰霜新星", kind="frost",
        desc="周期性冻结寒潮，减速并冻伤周围的敌群",
        base=dict(cooldown=4.00, damage=6, count=0, pierce=999, speed=0.0,
                  lifetime=0.0, radius=150.0, size=0),
        levels=[
            {},
            dict(radius=25),
            dict(cooldown=-0.60, damage=3),
            dict(radius=30),
            dict(cooldown=-0.80, damage=5, radius=20),
        ],
    ),
    "raven": dict(
        name="奥丁之鸦", kind="homing",
        desc="放出追踪渡鸦，自动撕咬最近的敌人",
        base=dict(cooldown=0.85, damage=7, count=1, pierce=1, speed=330.0,
                  lifetime=3.20, size=10),
        levels=[
            {},
            dict(count=1),
            dict(damage=4, speed=40),
            dict(count=1, cooldown=-0.15),
            dict(damage=6, count=1),
        ],
    ),
    # ---------------- Phase 3 新增 ----------------
    "bow": dict(
        name="寒冬之弓", kind="arrow",
        desc="凝霜之箭贯穿敌阵，中箭者步履蹒跚",
        base=dict(cooldown=1.50, damage=16, count=1, pierce=2, speed=560.0,
                  lifetime=1.40, size=12, slow_amt=0.35, slow_dur=1.5),
        levels=[
            {},
            dict(damage=6),
            dict(count=1),
            dict(pierce=2, speed=60),
            dict(damage=10, count=1),
        ],
    ),
    "horn": dict(
        name="维京号角", kind="ally",
        desc="吹响号角，唤来英灵战士并肩作战",
        base=dict(cooldown=12.0, damage=8, count=1, pierce=999, speed=210.0,
                  lifetime=10.0, size=12, tick=0.4),
        levels=[
            {},
            dict(damage=4),
            dict(count=1),
            dict(lifetime=3, damage=3),
            dict(count=1, damage=5),
        ],
    ),
    "curseblade": dict(
        name="诅咒之刃", kind="melee",
        desc="身前横斩，饮敌之血疗己之伤",
        base=dict(cooldown=0.95, damage=14, count=0, pierce=999, speed=0.0,
                  lifetime=0.15, radius=95.0, size=0, lifesteal_pct=0.15),
        levels=[
            {},
            dict(radius=15, damage=5),
            dict(cooldown=-0.15),
            dict(lifesteal_pct=0.08),
            dict(damage=10, radius=20),
        ],
    ),
    "quake": dict(
        name="地裂斩", kind="quake",
        desc="大地在敌群脚下崩裂",
        base=dict(cooldown=3.20, damage=22, count=1, pierce=999, speed=0.0,
                  lifetime=0.45, radius=130.0, size=0),
        levels=[
            {},
            dict(damage=8),
            dict(radius=20),
            dict(cooldown=-0.5),
            dict(damage=12, count=1),
        ],
    ),
    "trollhammer": dict(
        name="食人妖重锤", kind="smash",
        desc="巨锤砸地，震退周围的一切",
        base=dict(cooldown=2.80, damage=30, count=0, pierce=999, speed=0.0,
                  lifetime=0.0, radius=110.0, size=0, knockback=90.0),
        levels=[
            {},
            dict(damage=10),
            dict(radius=15),
            dict(cooldown=-0.4),
            dict(damage=16, radius=20),
        ],
    ),
    "scythe": dict(
        name="海拉之镰", kind="scythe",
        desc="收割之环缓缓旋转，触碰者凋零",
        base=dict(cooldown=0.50, damage=12, count=1, pierce=999, speed=1.4,
                  lifetime=0.0, radius=150.0, size=20),
        levels=[
            {},
            dict(damage=6),
            dict(count=1),
            dict(radius=20),
            dict(damage=8, count=1),
        ],
    ),
    # ---------------- Phase 7 剩余：地图限定武器 ----------------
    "dynamite": dict(
        name="炸药桶", kind="boom", map_only="mine",
        desc="掷出点燃的炸药桶，命中轰然爆裂（幽暗矿坑限定）",
        base=dict(cooldown=2.6, damage=26, count=1, pierce=1, speed=340.0,
                  lifetime=1.5, size=13, boom_radius=110.0),
        levels=[
            {},
            dict(damage=8),
            dict(boom_radius=25),
            dict(cooldown=-0.4),
            dict(damage=12, boom_radius=30),
        ],
    ),
    "sun_hammer": dict(
        name="圣辉战锤", kind="orbit", map_only="temple",
        desc="黄金圣锤绕身环转，锤击化为圣光治愈自身（诸神圣殿限定）",
        base=dict(cooldown=0.45, damage=10, count=2, pierce=999, speed=2.4,
                  lifetime=0.0, radius=100.0, size=16, lifesteal=1),
        levels=[
            {},
            dict(count=1),
            dict(damage=4, radius=10),
            dict(lifesteal=1),
            dict(damage=6, radius=14),
        ],
    ),
    "helfire": dict(
        name="冥界余烬", kind="pulse", map_only="hel",
        desc="冥火脉冲周期性扫过战场，灼烧群敌并反哺生命（冥界荒原限定）",
        base=dict(cooldown=2.8, damage=13, count=0, pierce=999, speed=0.0,
                  lifetime=0.0, radius=130.0, size=0, lifesteal=1),
        levels=[
            {},
            dict(radius=20),
            dict(cooldown=-0.3, damage=4),
            dict(lifesteal=1),
            dict(radius=24, damage=6),
        ],
    ),
}
MAX_WEAPONS = 4          # 同时携带武器上限
WEAPON_MAX_LEVEL = 5

# ============================ 武器进化表（12） ============================
# Vampire Survivors 式配方：武器满级 + 指定被动等级 -> 升级卡池出现金色进化卡。
EVOLUTIONS = {
    "axe": dict(
        name="血怒旋斧", passive="might", min_level=3,
        desc="巨斧无限穿透，掷出时附带额外旋斧",
        bonus=dict(damage=18, pierce=996, size=10, speed=80, count=1),
    ),
    "mjolnir": dict(
        name="世界终结者", passive="haste", min_level=3,
        desc="双锤化四锤，轨道更宽更快更重",
        bonus=dict(count=2, speed=1.0, radius=40, damage=10),
    ),
    "gungnir": dict(
        name="永恒之枪·陨落", passive="swift", min_level=3,
        desc="三枪连发，每一击都是陨落",
        bonus=dict(count=2, damage=30, speed=120),
    ),
    "rune_ring": dict(
        name="诸界法环", passive="magnet", min_level=3,
        desc="法阵范围暴涨，轰击更为频密",
        bonus=dict(radius=110, damage=12, cooldown=-0.5),
    ),
    "frost_nova": dict(
        name="绝对零度", passive="vigor", min_level=3,
        desc="寒潮几乎不间断地冻结全场",
        bonus=dict(radius=80, damage=10, cooldown=-0.8),
    ),
    "raven": dict(
        name="福金与雾尼", passive="regen", min_level=3,
        desc="双鸦巡猎，啄噬之伤化作生命",
        bonus=dict(count=2, damage=8, speed=60, lifesteal=2),
    ),
    # ---------------- Phase 3 新增 ----------------
    "bow": dict(
        name="风暴冰弓", passive="swift", min_level=3,
        desc="三连冰矢全穿透，冰缓更强更久",
        bonus=dict(count=2, pierce=996, damage=10, slow_amt=0.15, slow_dur=0.8),
    ),
    "horn": dict(
        name="英灵殿之门", passive="vigor", min_level=3,
        desc="英灵近乎常驻，同袍成列",
        bonus=dict(count=1, lifetime=18, damage=8),
    ),
    "curseblade": dict(
        name="血噬魔刃", passive="might", min_level=3,
        desc="横斩范围与吸血大增",
        bonus=dict(damage=12, radius=40, lifesteal_pct=0.15),
    ),
    "quake": dict(
        name="世界裂隙", passive="magnet", min_level=3,
        desc="双裂隙同时崩开，范围翻倍",
        bonus=dict(count=1, radius=70, damage=12),
    ),
    "trollhammer": dict(
        name="巨人杀手", passive="haste", min_level=3,
        desc="锤震更频更广，震退变为重创",
        bonus=dict(cooldown=-0.8, damage=20, radius=30),
    ),
    "scythe": dict(
        name="死神之拥", passive="regen", min_level=3,
        desc="双镰环抱，收割回复生命",
        bonus=dict(count=1, damage=10, radius=40, lifesteal=1),
    ),
}

# ============================ 角色表（3） ============================
# Phase 4：起始角色。start_weapon 为开局武器，hp 覆盖玩家基础血量，
# skill 为 Q 键主动技（kind 对应 skills.py 的 dispatch）。
CHARS = {
    "berserker": dict(
        name="屠魔", title="Berserker",
        desc="近战狂战：伤口越深，斧刃越快",
        start_weapon="axe", hp=110, color=(208, 84, 62),
        skill=dict(name="狂暴", kind="berserk", cooldown=10.0, dur=5.0,
                   desc="5 秒内攻速 +30%，受到的伤害 +20%"),
    ),
    "seeress": dict(
        name="战巫", title="Seeress",
        desc="远程巫术：凝霜之锥锁杀强者",
        start_weapon="rune_ring", hp=90, color=(110, 170, 255),
        skill=dict(name="冰锥", kind="icespear", cooldown=12.0,
                   dmg=60, slow=0.5, slow_dur=3.0,
                   desc="召唤大冰锥锁定最强之敌，重创并大幅减速"),
    ),
    "warden": dict(
        name="盾卫", title="Warden",
        desc="重装坦克：盾击开路，寸步不退",
        start_weapon="mjolnir", hp=130, color=(120, 200, 160),
        skill=dict(name="盾击", kind="shieldbash", cooldown=9.0,
                   radius=170.0, dash=240.0, dmg=25, stun=0.95, stun_dur=1.2,
                   desc="击晕并震退周围敌人，自身向前猛冲一段"),
    ),
}
DEFAULT_CHAR = "berserker"

# ============================ 被动表 ============================
PASSIVES = {
    "might":  dict(name="力量",   desc="全部伤害 +12%",        stack=0.12, max=5),
    "swift":  dict(name="迅捷",   desc="移动速度 +8%",         stack=0.08, max=5),
    "vigor":  dict(name="活力",   desc="生命上限 +25 并回复",   stack=25,   max=5),
    "haste":  dict(name="急速",   desc="武器冷却 -7%",         stack=0.07, max=5),
    "magnet": dict(name="磁石",   desc="拾取范围 +30%",        stack=0.30, max=5),
    "regen":  dict(name="再生",   desc="每秒回复 0.6 生命",    stack=0.6,  max=5),
}

# ============================ 敌人表（10） ============================
# unlock: 解锁时间(s)  weight: 混合出怪权重
# 行为字段触发对应 AI：ranged(远程) / bomber(自爆) / healer(治疗) / aura(减速光环) / vampire(吸血冲刺)
ENEMIES = {
    "draugr": dict(name="尸鬼",   hp=18,  speed=55.0,  dmg=8,  radius=13,
                   xp=1, color=(96, 116, 88),   unlock=0,   weight=10),
    "wolf":   dict(name="狂狼",   hp=12,  speed=100.0, dmg=6,  radius=11,
                   xp=1, color=(122, 92, 72),   unlock=40,  weight=8),
    "troll":  dict(name="巨魔",   hp=95,  speed=36.0,  dmg=16, radius=22,
                   xp=5, color=(92, 104, 124),  unlock=80,  weight=4),
    "wraith": dict(name="怨灵",   hp=26,  speed=72.0,  dmg=10, radius=12,
                   xp=2, color=(152, 162, 192), unlock=110, weight=6, sine=True),
    "brute":  dict(name="血尸鬼", hp=160, speed=44.0,  dmg=20, radius=26,
                   xp=8, color=(134, 74, 64),   unlock=140, weight=3),
    # ---------------- Phase 3 新增 ----------------
    "goblin_archer": dict(
        name="哥布林射手", hp=14, speed=66.0, dmg=6, radius=10, xp=2,
        color=(112, 152, 82), unlock=55, weight=6,
        ranged=dict(range_=300.0, cd=2.5, bullet_speed=240.0, bullet_dmg=8),
    ),
    "bomber": dict(
        name="自爆尸鬼", hp=22, speed=88.0, dmg=0, radius=12, xp=2,
        color=(202, 122, 52), unlock=70, weight=5,
        bomber=dict(radius=90.0, dmg=22, fuse=1.0, trigger=130.0),
    ),
    "healer": dict(
        name="哀嚎女妖", hp=40, speed=42.0, dmg=6, radius=13, xp=4,
        color=(92, 182, 142), unlock=95, weight=4,
        healer=dict(radius=150.0, heal=10, cd=3.0),
    ),
    "icesnake": dict(
        name="寒冰巨蛇", hp=130, speed=40.0, dmg=14, radius=24, xp=8,
        color=(82, 142, 182), unlock=125, weight=3,
        aura=dict(radius=120.0, slow=0.30),
    ),
    "vampire": dict(
        name="嗜血亲王", hp=110, speed=74.0, dmg=12, radius=15, xp=10,
        color=(152, 52, 72), unlock=160, weight=2,
        vampire=dict(dash_cd=5.0, dash_speed=520.0, lifesteal=0.5),
    ),
    # ---------------- Phase 5 剩余：宝箱怪 ----------------
    "mimic": dict(
        name="宝箱怪", hp=60, speed=30.0, dmg=22, radius=13, xp=15,
        color=(188, 148, 60), unlock=85, weight=1,
        mimic=dict(wake=220.0),   # 潜伏伪装；玩家靠近 220px 内惊醒，击杀必掉宝箱
    ),
}
ELITE = dict(hp_mult=8.0, speed_mult=0.85, size_mult=1.6, xp=20)

# ============================ Boss 表（4） ============================
# pattern 对应 bosses.py 的技能实现；具体技能参数每 Boss 自带。
BOSSES = {
    "jotunn": dict(
        name="霜巨人 尤弥尔",
        hp=3200, speed=46.0, dmg=26, radius=46, xp=120, color=(94, 110, 130),
        stomp_period=6.0, stomp_warn=0.9, stomp_radius=175.0,
        stomp_dmg=24, ring_speed=520.0,
    ),
    "nidhogg": dict(
        name="黑龙 尼德霍格",
        hp=3600, speed=52.0, dmg=24, radius=44, xp=140, color=(120, 60, 50),
        breath_period=7.0, breath_warn=0.8, breath_dur=1.2,
        breath_range=260.0, breath_arc=0.62, breath_dps=55.0,
        dive_period=12.0, dive_charge=1.0, dive_speed=900.0,
        dive_radius=120.0, dive_dmg=30,
    ),
    "jormungandr": dict(
        name="尘世巨蟒 约尔曼冈德",
        hp=3800, speed=40.0, dmg=28, radius=50, xp=150, color=(60, 110, 105),
        blade_period=6.0, blade_count=12, blade_speed=240.0, blade_dmg=18,
        lunge_period=9.0, lunge_speed=520.0,
    ),
    "fenrir": dict(
        name="魔狼 芬里尔",
        hp=3400, speed=64.0, dmg=30, radius=40, xp=150, color=(70, 72, 84),
        bite_period=5.0, bite_speed=760.0,
        phase2_hp=0.66, phase3_hp=0.33, summon_wolves=6,
    ),
}

# ============================ 地图主题表 ============================
# ground/line: 地面砖配色   decor: 装饰种类元组
# boss: 该图的 Boss          geyser: 间歇喷泉机关
# embers: 余烬氛围粒子        enemy_w: 出怪权重覆盖（None=用默认）
MAPS = {
    "snow": dict(
        name="霜雪平原",
        ground=(24, 28, 38), line=(32, 36, 48),
        decor=("rune", "bone", "snow", "rock"),
        boss="jotunn", geyser=False, embers=False, enemy_w=None,
    ),
    "lava": dict(
        name="熔岩废土",
        ground=(40, 24, 20), line=(58, 32, 26),
        decor=("lava", "bones", "charcoal", "rock"),
        boss="nidhogg", geyser=True, embers=True,
        enemy_w={"draugr": 8, "wolf": 5, "goblin_archer": 7, "bomber": 8,
                 "troll": 4, "healer": 3, "brute": 3, "icesnake": 2},
    ),
    # ---------------- Phase 7 新增 ----------------
    "mine": dict(
        name="幽暗矿坑",
        ground=(30, 32, 30), line=(42, 46, 40),
        decor=("rock", "bone", "charcoal"),
        boss="jormungandr", geyser=False, embers=False,
        enemy_w={"draugr": 8, "wolf": 6, "bomber": 7, "troll": 5,
                 "goblin_archer": 5, "wraith": 5, "healer": 3, "vampire": 3},
        carts=dict(period=16.0, speed=420.0, dmg=25, warn=1.2),
    ),
    "temple": dict(
        name="诸神圣殿",
        ground=(52, 46, 30), line=(70, 62, 42),
        decor=("rune", "rock", "bone"),
        boss="jotunn", geyser=False, embers=False,
        enemy_w={"draugr": 7, "wraith": 7, "healer": 6, "brute": 4,
                 "icesnake": 4, "troll": 4, "goblin_archer": 5},
        pillar=dict(period=14.0, radius=420.0, push=140.0, warn=1.0),
    ),
    "hel": dict(
        name="冥界荒原",
        ground=(34, 22, 26), line=(52, 32, 34),
        decor=("lava", "bones", "charcoal"),
        boss="fenrir", geyser=True, embers=True,
        enemy_w={"draugr": 6, "wolf": 7, "bomber": 7, "wraith": 6,
                 "vampire": 5, "brute": 4, "troll": 3, "healer": 3},
    ),
}
DEFAULT_MAP = "snow"

# 升级卡池不足时的填充项
FALLBACK_CARDS = [
    dict(kind="heal", name="急救", desc="立即回复 40 生命"),
    dict(kind="xp",   name="智慧", desc="获得 50 经验"),
]
