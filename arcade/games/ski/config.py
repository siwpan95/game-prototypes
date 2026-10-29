"""游戏配置中心 - 集中管理所有可调参数与常量。

设计原则：
- 游戏逻辑常量（尺寸/障碍物/雪人/跳跃/加速）集中于此，便于平衡性调参
- UI 主题色与渲染常量也放这里，统一一处修改
- 所有数值经过 SkiFree 原版机制 + tkinter 性能实测权衡
"""

from __future__ import annotations

# ========== 画布尺寸 ==========
WIDTH = 80
HEIGHT = 30

# ========== 字符资源（统一单宽，保证 Text 网格对齐）==========
# 障碍物
TREE_CHAR = "♣"        # 树
ROCK_CHAR = "●"        # 岩石
FLAG_CHAR = "¶"        # 旗子（可收集）
RAMP_CHAR = "♦"        # 跳台（触发跳跃）

# 雪人
YETI_CHAR = "☃"        # 雪人 / Abominable Snow Monster

# 道路背景
ROAD_CHAR = "·"
SNOW_CHAR = " "

# 滑雪者方向字符（沿用原版方向键 -2..+2）
SKIER_CHARS = {
    -2: "◀◀",   # 向左急转
    -1: "◀",    # 向左转
    0: "▲",     # 向前
    1: "▶",     # 向右转
    2: "▶▶",    # 向右急转
}
SKIER_JUMP_CHAR = "⬆"     # 跳跃中
SKIER_BOOST_CHAR = "⚡"    # 加速中
SKIER_CRASH_CHAR = "✗"     # 撞击

# ========== 障碍物类型配置 ==========
# 每种障碍物：字符、颜色、对分数的影响、是否可被跳跃越过
OBSTACLE_TYPES = {
    "tree": {
        "char": TREE_CHAR,
        "color": "green",
        "score": -50,       # 撞树重罚
        "blockable": True,  # 可被跳跃越过
        "weight": 40,       # 生成权重
    },
    "rock": {
        "char": ROCK_CHAR,
        "color": "gray",
        "score": -30,
        "blockable": True,
        "weight": 25,
    },
    "flag": {
        "char": FLAG_CHAR,
        "color": "red",
        "score": 10,        # 收集旗子加分
        "collectible": True,
        "weight": 25,
    },
    "ramp": {
        "char": RAMP_CHAR,
        "color": "magenta",
        "action": "jump",   # 触发跳跃
        "weight": 10,
    },
}

# ========== 颜色标签（tkinter Text tag）==========
# 主题：雪地白底 + 高对比度角色
COLOR_TAGS = {
    "red":     "#e53935",
    "blue":    "#1e88e5",
    "green":   "#2e7d32",
    "gray":    "#9e9e9e",
    "black":   "#212121",
    "yellow":  "#fdd835",
    "magenta": "#8e24aa",
    "cyan":    "#00838f",
    "orange":  "#fb8c00",
    "white":   "#ffffff",
}

# ========== 游戏参数 ==========
GAME_OVER_SCORE = -100        # 分数低于此值游戏结束

# 雪人（Yeti / Abominable Snow Monster）
YETI_TRIGGER_DISTANCE = 200   # 滑行到此距离触发雪人（原版 2000，缩放便于体验）
YETI_BASE_SPEED = 1.0        # 雪人绝对速度（行/帧）
YETI_BOOST_SPEED = 0.1       # 玩家加速时雪人仍缓慢逼近（几乎停滞）

# 加速冲刺（F 键，源自原版 Fast Mode）
BOOST_DURATION = 30           # 加速持续帧数（约 3 秒 @100ms/帧）
BOOST_COOLDOWN = 60           # 冷却帧数（约 6 秒）
BOOST_SPEED_MULTIPLIER = 2.0  # 加速时滚动倍率

# 跳跃（踩中跳台触发）
JUMP_DURATION = 6              # 跳跃持续帧数
JUMP_STYLE_BONUS = 15         # 完成跳跃的风格分

# 难度递增
DIFFICULTY_INTERVAL = 50      # 每 N 距离提升一档难度
MAX_DIFFICULTY = 8             # 难度上限

# 帧调度
TICK_INTERVAL_MS = 100        # 主循环间隔（毫秒）
OBSTACLE_SCROLL_DIVISOR = 2   # 障碍物每 N 帧滚动一次（降低速度但保持流畅）

# ========== 游戏模式 ==========
MODE_ENDLESS = "endless"      # 无尽：雪人追击，看能撑多远
MODE_SLALOM = "slalom"       # 回转：聚焦旗子，限时计分
MODE_FREESTYLE = "freestyle"  # 自由式：跳跃做特技赚风格分

MODE_NAMES = {
    MODE_ENDLESS: "无尽模式",
    MODE_SLALOM: "回转模式",
    MODE_FREESTYLE: "自由式",
}

MODE_DESCRIPTIONS = {
    MODE_ENDLESS: "躲避障碍物，雪人将在 200m 处追击你",
    MODE_SLALOM: "尽可能多地穿越旗门，限时挑战",
    MODE_FREESTYLE: "踩跳台做特技，风格分至上",
}

# ========== 高分存储 ==========
HIGHSCORE_FILE = "highscores.json"
HIGHSCORE_KEY_FORMAT = "{mode}_best"

# ========== 调试 ==========
DEBUG = False
