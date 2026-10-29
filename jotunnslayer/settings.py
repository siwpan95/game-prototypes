# -*- coding: utf-8 -*-
"""全局参数：窗口、平衡性数值、颜色。改这里调手感，不用动逻辑代码。"""

# ---- 窗口 / 帧率 ----
WIDTH, HEIGHT = 1280, 720
FPS = 60
DT = 1.0 / FPS          # 固定逻辑步长
MAX_FRAME = 0.1         # 帧耗时上限，防卡顿螺旋

# ---- 局 timing（秒） ----
BOSS_TIME = 180.0       # Boss 出现时间
ELITE_TIMES = (60.0, 120.0, 150.0)
GAME_MAX_SPAWN_T = 180.0  # 难度曲线封顶时间

# ---- 玩家 ----
PLAYER = dict(
    hp=100,
    speed=230.0,        # px/s
    radius=14,
    pickup_radius=90.0, # 经验宝石磁力半径
    iframes=0.6,        # 受击无敌帧
    start_weapon="axe",
)

# ---- 波次 / 性能保护 ----
SPAWN = dict(
    interval_start=1.00,   # 初始出怪间隔(s)
    interval_end=0.30,     # 180s 时的出怪间隔（原 0.25，报告建议放缓前期压力）
    batch_start=1,
    batch_end=3,
    max_enemies=260,       # 同屏敌人上限（性能护栏）
    hp_scale=lambda t: 1.0 + t / 110.0,  # 敌人血量随时间增长（原 /90，报告建议放缓）
    ring_min=760.0,        # 出怪圈：屏幕外沿
    ring_max=900.0,
)

# ---- 经验 / 升级 ----
XP = dict(
    need=lambda lvl: 4 + lvl * 3,   # 升到下一级所需
    gem_cap=400,                    # 场上宝石上限（超出则合并）
)

# ---- 金币（Phase 6：普通敌掉 xp 等量，精英/Boss 固定）----
GOLD = dict(elite=50, boss=200)

# ---- 局内任务（Phase 5）----
QUEST = dict(
    first_at=60.0,          # 首个任务出现时间(s)
    interval_min=60.0,      # 后续任务间隔
    interval_max=90.0,
    duration=40.0,          # 任务期限
    kill_target=(25, 45),   # 歼灭目标数量区间
    collect_target=(20, 35),# 收集宝石目标区间
    hold_target=20.0,       # 守点秒数
    hold_radius=130.0,
    gold_min=100, gold_max=300,
    xp_reward=80,
)

# ---- 宝箱/食物（Phase 5）----
CHEST = dict(gold=100, heal=50, food_count=2)
FOOD = dict(heal=30, drop_chance=0.01, cap=8, lifetime=30.0)

# ---- 难度系数（Phase 7）----
DIFFICULTIES = {
    "easy":   dict(name="轻松", hp=0.80, dmg=0.70, speed=0.90,
                   spawn_mult=0.85, gold_mult=0.8, xp_mult=1.2),
    "normal": dict(name="普通", hp=1.00, dmg=1.00, speed=1.00,
                   spawn_mult=1.00, gold_mult=1.0, xp_mult=1.0),
    "hard":   dict(name="困难", hp=1.50, dmg=1.40, speed=1.10,
                   spawn_mult=1.20, gold_mult=1.5, xp_mult=1.0),
    "insane": dict(name="疯狂", hp=2.20, dmg=1.80, speed=1.25,
                   spawn_mult=1.35, gold_mult=2.2, xp_mult=1.0),  # 报告建议下调
}
DEFAULT_DIFFICULTY = "normal"

# ---- 无尽模式（Phase 7）----
ENDLESS = dict(boss_respawn=60.0, ramp_step=300.0, ramp_amount=0.5)

# ---- 摄像机 ----
CAM_LERP = 8.0

# ---- 敌方弹幕 / 友军 / 机关（Phase 3）----
PHASE3 = dict(
    enemy_bullet_cap=80,       # 敌方弹幕同屏上限
    ally_cap=4,                # 英灵战士上限
    geyser_count=4,            # 熔岩图活跃喷泉数
    geyser_cycle=7.0,          # 喷泉周期
    geyser_warn=0.9,
    geyser_erupt=1.2,
    geyser_radius=65.0,
    geyser_dmg_player=15.0,    # 每 tick 对玩家
    geyser_dmg_enemy=30.0,     # 每 tick 对敌人
    ember_cap=40,              # 熔岩图余烬粒子
)

# ---- 配色（北欧雪夜）----
COL = dict(
    bg=(16, 18, 26),
    ground=(24, 28, 38),
    ground_line=(32, 36, 48),
    snow=(210, 218, 232),
    player=(232, 238, 248),
    player_helm=(180, 190, 210),
    hp_bar=(196, 60, 60),
    hp_back=(40, 20, 24),
    xp_bar=(96, 200, 255),
    xp_back=(16, 32, 44),
    gold=(255, 208, 96),
    text=(226, 230, 240),
    dim=(150, 156, 170),
    card=(28, 32, 46),
    card_sel=(70, 90, 140),
    accent=(96, 200, 255),
    elite_ring=(255, 120, 60),
    boss=(200, 70, 90),
    frost=(140, 210, 255),
    rune=(190, 120, 255),
)
