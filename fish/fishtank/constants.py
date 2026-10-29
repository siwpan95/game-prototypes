"""非数值常量：键名、枚举字符串、文件名。

🔴 本文件只放**字符串键名与枚举**，任何玩法数值都必须留在 data/balance.json。
🔴 禁止 `from __future__ import annotations`。
"""

# ── 存档 ──
SCHEMA_VERSION = 1
"""state_data 载荷版本（与引擎信封 version 独立）。"""

SAVE_SLOT_AUTO = "autosave"
BACKUP_SUFFIX = ".bak"
TEMP_SUFFIX = ".tmp"

# ── 数据文件名 ──
FILE_BALANCE = "balance.json"
FILE_FISH = "fish_data.json"
FILE_DECOR = "decor_data.json"
FILE_UI_TEXT = "ui_text.json"

# ── 稀有度 ──
RARITIES = ("R1", "R2", "R3", "R4", "R5")

# ── 成长阶段 ──
STAGE_FRY = "fry"
STAGE_JUVENILE = "juvenile"
STAGE_ADULT = "adult"
STAGE_MATURE = "mature"
STAGES = (STAGE_FRY, STAGE_JUVENILE, STAGE_ADULT, STAGE_MATURE)

# ── 尾鳍形状 ──
TAIL_FAN = "fan"
TAIL_FORK = "fork"
TAIL_ROUND = "round"
TAIL_LONG = "long"
TAILS = (TAIL_FAN, TAIL_FORK, TAIL_ROUND, TAIL_LONG)

# ── 游速档 ──
SPEED_SLOW = "slow"
SPEED_NORMAL = "normal"
SPEED_FAST = "fast"

# ── 行为树状态标签（写入黑板 "state"，供渲染与测试读取）──
AI_WANDER = "wander"
AI_SEEK_FOOD = "seek_food"
AI_AVOID_EDGE = "avoid_edge"
AI_SEEK_POINT = "seek_point"
AI_IDLE = "idle"
AI_STATES = (AI_WANDER, AI_SEEK_FOOD, AI_AVOID_EDGE, AI_SEEK_POINT, AI_IDLE)

# ── 黑板键名 ──
#
# 消费者关系（谁写 → 谁读）：
#   TickSystem 写入：dt, now, nx, ny, heading, bounds, cfg
#   行为树 Action 写入：target_x, target_y, state, speed_mul, tail_mul,
#                      food_x/y, has_food, interest_x/y, has_interest,
#                      idle_left, retarget_left, turned
#   行为树 Condition 读取：has_food, has_interest, idle_left, retarget_left
#   MovementSystem 读取：speed_mul, tail_mul, base_speed, tail_hz, layer_y,
#                       attract, school_x/y, has_school, target_x/y, uid, rng
#   黑板键需与 behaviors.py 的 _set_output / AIConfig 烘焙值保持一致。
BB_DT = "dt"
BB_NOW = "now"
BB_NX = "nx"
BB_NY = "ny"
BB_HEADING = "heading"
BB_TARGET_X = "target_x"
BB_TARGET_Y = "target_y"
BB_STATE = "state"
BB_SPEED_MUL = "speed_mul"
BB_TAIL_MUL = "tail_mul"
BB_FOOD_X = "food_x"
BB_FOOD_Y = "food_y"
BB_HAS_FOOD = "has_food"
BB_INTEREST_X = "interest_x"
BB_INTEREST_Y = "interest_y"
BB_HAS_INTEREST = "has_interest"
BB_IDLE_LEFT = "idle_left"
BB_RETARGET_LEFT = "retarget_left"
BB_BOUNDS = "bounds"
BB_CFG = "cfg"
BB_RNG = "rng"
BB_TURNED = "turned"
BB_UID = "uid"
BB_BASE_SPEED = "base_speed"
BB_TAIL_HZ = "tail_hz"
BB_LAYER_Y = "layer_y"
BB_ATTRACT = "attract"
BB_SCHOOL_X = "school_x"
BB_SCHOOL_Y = "school_y"
BB_HAS_SCHOOL = "has_school"

# ── World 共享数据键（world.set_data / get_data）──
WD_STATE = "fishtank.state"
WD_BALANCE = "fishtank.balance"
WD_SPECIES = "fishtank.species"
WD_DECOR = "fishtank.decor"
WD_BUS = "fishtank.bus"
WD_FOOD = "fishtank.food"
WD_RNG = "fishtank.rng"
WD_AI_RNG = "fishtank.ai_rng"
"""表现层随机源。🔴 与 WD_RNG（玩法随机、入档）**必须分开**：
渲染帧率不同不能影响繁殖等玩法随机流，否则双端结果发散。"""
WD_CFG = "fishtank.cfg"
WD_DT = "fishtank.dt"
WD_NOW = "fishtank.now"
WD_STEP = "fishtank.step"
"""本帧应推进的**固定模拟步长**（秒）。0 表示这一帧不推进玩法。"""
WD_STEPS = "fishtank.steps"
WD_BONUS = "fishtank.bonus"
WD_PARTICLES = "fishtank.particles"
WD_GAME = "fishtank.game"
WD_TURNS = "fishtank.turns"
"""本帧掉头的鱼列表 [(x, y), ...]，供粒子桥接生成转身气泡。"""
WD_AUTOSELL = "fishtank.autosell"
"""自动卖出队列：待移除实体的鱼 uid 列表 [uid, ...]"""

# ── 升级种类 ──
UPGRADE_CAPACITY = "capacity"
UPGRADE_FILTER = "filter"
UPGRADE_FEEDER = "feeder"
UPGRADES = (UPGRADE_CAPACITY, UPGRADE_FILTER, UPGRADE_FEEDER)

# ── 窗口形态 ──
MODE_TANK = "tank"
MODE_STRIP = "strip"
MODE_PANEL = "panel"

# ── 绘制图元类型（FishGeometry 输出，双端共享）──
PRIM_ELLIPSE = "ELLIPSE"
PRIM_ELLIPSE_HALF = "ELLIPSE_HALF"
PRIM_POLYGON = "POLYGON"
PRIM_CIRCLE = "CIRCLE"
PRIM_OUTLINE = "OUTLINE"

# ── 部件名（渲染差分 item_map 的 key 后缀）──
PART_GLOW = "glow"
PART_TAIL = "tail"
PART_DORSAL = "dorsal"
PART_BODY = "body"
PART_BELLY = "belly"
PART_PATTERN = "pattern"
PART_EYE = "eye"
PART_EYE_HL = "eye_hl"
