"""游戏数值常量（#14：从 game.py 抽取的魔法数字，集中调参）。

改动本文件即可调整游戏手感，无需翻动游戏主逻辑。所有取值与原始
硬编码值保持一致，确保行为完全等价（仅做命名化，不改数值）。
"""

# ── 时间 / 进度单位 ───────────────────────────────────────────────
TICK_MS = 100                 # 单次 tick 推进的毫秒步长
MS_PER_UNIT = 1000            # 进度/经验换算单位（ms -> 抽象单位）

# ── 初始 / 各行动进度上限（ms） ───────────────────────────────
INITIAL_MAX_PROGRESS = 2000
MARKET_MAX_PROGRESS = 4000
BUYING_MAX_PROGRESS = 5000
HEADING_MAX_PROGRESS = 4000
SELLING_MAX_PROGRESS = 1000

# ── 升级经验曲线：exp = (BASE + GROWTH**Level) * MULT ───────────
LEVEL_EXP_BASE = 20
LEVEL_EXP_GROWTH = 1.15
LEVEL_EXP_MULT = 60

# ── 剧情进度上限 ───────────────────────────────────────────────────
PLOT_PROLOGUE_MAX = 26
PLOT_MAX_SECONDS = 60 * 60       # 单章基础秒数
PLOT_MAX_PER_CHAPTER = 5        # 每章叠加系数

# ── 生命 / 魔法成长（升级时） ───────────────────────────────
HP_GROWTH_BASE = 1
HP_GROWTH_PER_CON = 3
MP_GROWTH_BASE = 1
MP_GROWTH_PER_INT = 3
GROWTH_DICE = 4                  # integers(0, GROWTH_DICE)

# ── 装备价格：A*lvl^2 + B*lvl + C ───────────────────────────
EQUIP_PRICE_A = 5
EQUIP_PRICE_B = 10
EQUIP_PRICE_C = 20

# ── 背包 / 任务队列上限 ──────────────────────────────────────
INVENTORY_COPY_THRESHOLD = 250    # 超过此值有概率复制已有物品
QUEST_KEEP_MAX = 99              # 任务队列软上限（超出弹出最旧，保留 100）
ENCUMBRANCE_BASE = 10            # 背包负重上限基数（+= STR）

# ── 怪物生成概率 (命中数, 总数) ─────────────────────────────
MONSTER_ODDS_PASS = (2, 5)      # 等级微调命中
MONSTER_ODDS_NPC = (1, 25)     # 使用 NPC
MONSTER_ODDS_QUEST = (1, 4)     # 使用任务怪物
MONSTER_BIG_GAP = 10             # level-lev 超过该值视为“成群”

# ── 自动存盘节流（#10） ─────────────────────────────────────
AUTO_SAVE_MIN_INTERVAL_S = 5.0
