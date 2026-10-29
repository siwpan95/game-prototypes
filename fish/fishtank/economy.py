"""经济与成长的**纯函数**内核（双端同源的第一块基石）。

🔴 禁止 `from __future__ import annotations`（E6）。
🔴 本模块**没有任何硬编码玩法数值**：每一个数都从 `BalanceTable` 读。
🔴 本模块所有函数都是纯函数：不读全局、不改参数、不做 IO。
   XJ380 C++ 端只要照抄这些公式即可得到逐位一致的结果。

数值约定（ARCHITECTURE §2）：

* 金币一律用整数"厘"（milli）表示，`1 金币 = coin_scale 厘`（默认 1000）。
* 取整一律用 :func:`round_half_up`，**禁用内置 round**
  （内置 round 是"银行家舍入"，0.5 → 0，与 C++ 的 floor(x+0.5) 不一致）。
* 遍历鱼一律按 uid 升序，保证浮点求和顺序确定。
"""

import math
from typing import Dict, List, Optional, Tuple

from fishtank.constants import (
    RARITIES, STAGE_ADULT, STAGE_FRY, STAGE_JUVENILE, STAGE_MATURE, STAGES,
)
from fishtank.data_defs import BalanceTable, DecorLibrary, FishLibrary
from fishtank.state import GameState


# ══════════════════════════════════════════════════════════════
#  基础工具
# ══════════════════════════════════════════════════════════════

def round_half_up(x: float) -> int:
    """四舍五入到整数（0.5 一律向上）。

    🔴 **禁用内置 `round`**：CPython 的 `round` 是 banker's rounding，
    `round(0.5) == 0`、`round(2.5) == 2`，与 C++ 端的 `floor(x+0.5)` 不一致，
    会造成双端金币慢慢漂移。

    :param x: 任意实数
    :returns: int
    """
    return int(math.floor(float(x) + 0.5))


def clamp(v: float, lo: float, hi: float) -> float:
    """把 v 钳制到 [lo, hi]。hi < lo 时自动交换（防御 balance.json 写反上下限）。"""
    v = float(v)
    lo = float(lo)
    hi = float(hi)
    if hi < lo:
        lo, hi = hi, lo
    if v < lo:
        return lo
    if v > hi:
        return hi
    return v


def lerp(a: float, b: float, t: float) -> float:
    """线性插值，t 会先被钳到 [0,1]。"""
    t = clamp(t, 0.0, 1.0)
    return float(a) + (float(b) - float(a)) * t


def rarity_index(rarity: str) -> int:
    """R1..R5 → 0..4；未知稀有度返回 0。"""
    try:
        return RARITIES.index(str(rarity))
    except ValueError:
        return 0


def rarity_at(index: int) -> str:
    """0..4 → R1..R5；越界钳到端点。"""
    i = max(0, min(int(index), len(RARITIES) - 1))
    return RARITIES[i]


# ══════════════════════════════════════════════════════════════
#  成长阶段
# ══════════════════════════════════════════════════════════════

def growth_progress(age_sec: float, cycle_sec: float) -> float:
    """成长进度 p = age / cycle（可以 > 1）。cycle <= 0 时返回 0。"""
    cycle_sec = float(cycle_sec)
    if cycle_sec <= 0.0:
        return 0.0
    return float(age_sec) / cycle_sec


def stage_of(age_sec: float, cycle_sec: float, thresholds: dict) -> str:
    """由累计成长秒数判定成长阶段。

    `thresholds` 是每个阶段的**进度上界**（左闭右开）::

        p < thresholds["fry"]        -> "fry"       （默认 0.15）
        p < thresholds["juvenile"]   -> "juvenile"  （默认 0.45）
        p < thresholds["adult"]      -> "adult"     （默认 1.45）
        否则                          -> "mature"

    :param age_sec: 累计成长秒数（离线也照常累加，准则 L7：不惩罚离线）
    :param cycle_sec: 该稀有度的成长周期秒数
    :param thresholds: dict，来自 ``growth.thresholds``
    :returns: "fry" / "juvenile" / "adult" / "mature"
    """
    p = growth_progress(age_sec, cycle_sec)
    th = thresholds or {}
    fry = float(th.get(STAGE_FRY, 0.15))
    juv = float(th.get(STAGE_JUVENILE, 0.45))
    adu = float(th.get(STAGE_ADULT, 1.45))
    if p < fry:
        return STAGE_FRY
    if p < juv:
        return STAGE_JUVENILE
    if p < adu:
        return STAGE_ADULT
    return STAGE_MATURE


def stage_index(stage: str) -> int:
    """阶段名 → 序号（fry=0 … mature=3）；未知返回 0。"""
    try:
        return STAGES.index(str(stage))
    except ValueError:
        return 0


def stage_reached(stage: str, min_stage: str) -> bool:
    """判断 stage 是否已达到 min_stage（含）。"""
    return stage_index(stage) >= stage_index(min_stage)


def stage_coef(stage: str, table: dict) -> float:
    """阶段产出系数（fry 0.30 / juvenile 0.60 / adult 1.00 / mature 1.25）。"""
    t = table or {}
    try:
        return float(t.get(str(stage), 1.0))
    except (TypeError, ValueError):
        return 1.0


def stage_scale(stage: str, table: dict) -> float:
    """阶段渲染缩放（fry 0.45 … mature 1.10）。"""
    t = table or {}
    try:
        return float(t.get(str(stage), 1.0))
    except (TypeError, ValueError):
        return 1.0


def next_stage_seconds(age_sec: float, cycle_sec: float, thresholds: dict) -> int:
    """距离下一阶段还差多少秒；已是 mature 返回 -1。

    仅用于 UI 展示（"再过 X 分钟长大"），不参与结算。
    """
    cycle_sec = float(cycle_sec)
    if cycle_sec <= 0.0:
        return -1
    th = thresholds or {}
    bounds = [
        float(th.get(STAGE_FRY, 0.15)),
        float(th.get(STAGE_JUVENILE, 0.45)),
        float(th.get(STAGE_ADULT, 1.45)),
    ]
    p = growth_progress(age_sec, cycle_sec)
    for b in bounds:
        if p < b:
            return max(0, round_half_up((b - p) * cycle_sec))
    return -1


# ══════════════════════════════════════════════════════════════
#  水质
# ══════════════════════════════════════════════════════════════

def quality_factor(water: float, bal: BalanceTable) -> float:
    """水质 → 产出系数，线性映射到 ``[quality_floor, 1.0]``。

    准则 L4（负反馈只减速、绝不倒退）：即使水质掉到下限，系数也不会低于
    ``water.quality_floor``（默认 0.5），鱼**永远不会死**、收益**永远不归零**。

    :param water: 当前水质（50~100）
    :param bal: BalanceTable
    :returns: float，落在 [quality_floor, 1.0]
    """
    lo = bal.water_min()
    hi = bal.water_max()
    floor = bal.quality_floor()
    if hi <= lo:
        return 1.0
    t = clamp((float(water) - lo) / (hi - lo), 0.0, 1.0)
    return floor + (1.0 - floor) * t


def water_band(water: float, bal: BalanceTable) -> int:
    """把连续水质离散成档位序号。

    🔴 E11：引擎的 `ReactiveTracker` 对**任何 float 变化**都会触发回调，
    直接订阅 `water` 会导致每帧刷新 UI。因此 UI 层只订阅本函数的整数输出。

    :returns: int，bands 列表中的档位下标（0 = 最差）
    """
    bands = bal.get("water.bands")
    if not isinstance(bands, list) or not bands:
        bands = [50, 60, 70, 80, 90, 100]
    w = float(water)
    idx = 0
    for i, edge in enumerate(bands):
        try:
            if w >= float(edge):
                idx = i
        except (TypeError, ValueError):
            continue
    return idx


def water_delta_per_min(fish_count: int, filter_level: int, bal: BalanceTable, 
                        offline: bool = False) -> float:
    """每分钟的水质变化量（正 = 变好）。

    ``净变化 = 过滤增益 - 每鱼衰减 × 鱼数``；离线时整体乘 ``water.offline_scale``。

    🔴 说明：`offline_scale` 缩放的是**净变化**而不仅仅是衰减项。
    这样在线/离线的平衡点（净变化为 0 的水位）完全相同 —— 既不惩罚离线
    （准则 L7），也不会产生"挂机刷水质"的套利空间。C++ 端须照此实现。

    :param fish_count: 当前鱼数
    :param filter_level: 过滤器等级（0 = 无）
    :param bal: BalanceTable
    :param offline: 是否处于离线结算
    :returns: float，点/分钟
    """
    decay = float(bal.get("water.decay_per_fish", 0.03)) * max(0, int(fish_count))
    gain = bal.filter_gain(filter_level)
    delta = gain - decay
    if offline:
        delta *= float(bal.get("water.offline_scale", 0.5))
    return delta


def step_water(water: float, fish_count: int, filter_level: int, step_sec: float,
               bal: BalanceTable, offline: bool = False) -> float:
    """推进水质一个时间步，并钳制在 [water.min, water.max]。"""
    delta = water_delta_per_min(fish_count, filter_level, bal, offline=offline)
    nxt = float(water) + delta * (float(step_sec) / 60.0)
    return clamp(nxt, bal.water_min(), bal.water_max())


# ══════════════════════════════════════════════════════════════
#  饱食度（自动投食器）
# ══════════════════════════════════════════════════════════════

def satiety_factor(satiety: float, bal: BalanceTable) -> float:
    """饱食度 → 产出系数，线性映射到 ``[feeder.output_floor, 1.0]``。

    准则 L4：饿肚子最多让产出降到 85%，**不会死鱼、不会归零**。
    """
    floor = float(bal.get("feeder.output_floor", 0.85))
    s_min = float(bal.get("feeder.satiety_min", 0.0))
    s_max = float(bal.get("feeder.satiety_max", 1.0))
    if s_max <= s_min:
        return 1.0
    t = clamp((float(satiety) - s_min) / (s_max - s_min), 0.0, 1.0)
    return floor + (1.0 - floor) * t


def step_satiety(satiety: float, step_sec: float, bal: BalanceTable) -> float:
    """饱食度自然衰减一个时间步（不含自动投食）。"""
    dec = float(bal.get("feeder.decay_per_min", 0.012)) * (float(step_sec) / 60.0)
    return clamp(float(satiety) - dec,
                 float(bal.get("feeder.satiety_min", 0.0)),
                 float(bal.get("feeder.satiety_max", 1.0)))


def feeder_upkeep_rate_milli(fish_count: int, bal: BalanceTable) -> float:
    """自动投食器的维护费速率（厘/分钟）。"""
    per = float(bal.get("feeder.upkeep_per_fish_per_min", 0.05))
    return per * max(0, int(fish_count)) * bal.coin_scale()


def feeder_upkeep_milli(fish_count: int, step_sec: float, bal: BalanceTable) -> float:
    """自动投食器在一个时间步内的维护费（厘，未取整）。"""
    return feeder_upkeep_rate_milli(fish_count, bal) * (float(step_sec) / 60.0)


def auto_feed(satiety: float, bal: BalanceTable) -> Tuple[float, bool]:
    """自动投食器的喂食判定。

    :returns: (新的饱食度, 是否真的喂了)
    """
    level = float(bal.get("feeder.auto_feed_level", 0.6))
    s_max = float(bal.get("feeder.satiety_max", 1.0))
    s_min = float(bal.get("feeder.satiety_min", 0.0))
    if float(satiety) >= level:
        return float(satiety), False
    gain = float(bal.get("feeder.feed_gain", 0.5))
    return clamp(float(satiety) + gain, s_min, s_max), True


# ══════════════════════════════════════════════════════════════
#  加成
# ══════════════════════════════════════════════════════════════

def decor_bonus(decor_ids: list, decor_lib: DecorLibrary) -> float:
    """装饰加成之和（未封顶）。按 id 升序求和以固定浮点顺序。"""
    total = 0.0
    for did in sorted(set(str(d) for d in (decor_ids or []))):
        total += decor_lib.bonus_of(did)
    return total


def completed_groups(owned_species: list, species_lib: FishLibrary) -> list:
    """返回已集齐的族群名列表（升序）。

    :param owned_species: 已拥有/已解锁的鱼种 id 集合
    :param species_lib: FishLibrary
    """
    owned = set(str(s) for s in (owned_species or []))
    done = []
    for g in species_lib.groups():
        members = species_lib.group_members(g)
        if members and members.issubset(owned):
            done.append(g)
    return sorted(done)


def codex_bonus(owned_species: list, species_lib: FishLibrary, bal: BalanceTable) -> float:
    """图鉴族群加成（未封顶）= 已集齐族群数 × ``codex.group_bonus``。"""
    return len(completed_groups(owned_species, species_lib)) * bal.group_bonus()


def total_bonus(decor_ids: list, owned_species: list, decor_lib: DecorLibrary,
                species_lib: FishLibrary, bal: BalanceTable) -> float:
    """装饰 + 图鉴的总加成，封顶 ``economy.bonus_cap``。

    :returns: float，落在 [0, bonus_cap]
    """
    raw = decor_bonus(decor_ids, decor_lib) + codex_bonus(owned_species, species_lib, bal)
    return clamp(raw, 0.0, bal.bonus_cap())


class BonusCache:
    """总加成的记忆化包装（**纯性能优化，不改变任何数值**）。

    加成只在"装饰集合"或"图鉴条目数"变化时才会变，而离线结算最多要跑 8.9 万步，
    每步重扫图鉴会让 10 年硬上限的极端存档卡住好几秒。

    正确性依据：`GameState.codex` 是**只增不减**的（卖鱼不会删图鉴记录），
    所以"条目数 + 装饰元组"足以唯一标识加成状态。
    """

    def __init__(self, bal: BalanceTable, species_lib: FishLibrary, decor_lib: DecorLibrary):
        self._bal = bal
        self._species = species_lib
        self._decor = decor_lib
        self._key: Optional[tuple] = None
        self._val: float = 0.0

    def value(self, state: GameState) -> float:
        """返回当前状态的总加成（命中缓存则不重算）。"""
        key = (tuple(sorted(state.tank.decors)), len(state.codex))
        if key != self._key:
            self._val = total_bonus(state.tank.decors, state.codex_species(),
                                    self._decor, self._species, self._bal)
            self._key = key
        return self._val

    def invalidate(self) -> None:
        """强制下次重算（装饰被移除等罕见路径调用）。"""
        self._key = None


# ══════════════════════════════════════════════════════════════
#  产出速率
# ══════════════════════════════════════════════════════════════

def fish_base_per_min(rarity: str, stage: str, bal: BalanceTable) -> float:
    """单条鱼的裸产出（金币/分钟，未乘水质/加成）。"""
    return bal.base_income(rarity) * stage_coef(stage, bal.stage_coef_table())


def tank_base_per_min(fishes: list, species_lib: FishLibrary, bal: BalanceTable) -> float:
    """全缸裸产出（金币/分钟）。

    :param fishes: FishState 列表；**调用方须保证已按 uid 升序**
    :returns: float
    """
    total = 0.0
    coef_tbl = bal.stage_coef_table()
    for f in fishes:
        sp = species_lib.get(f.species)
        rarity = sp.rarity if sp else "R1"
        total += bal.base_income(rarity) * stage_coef(f.stage, coef_tbl)
    return total


def income_rate_milli(state: GameState, bal: BalanceTable, species_lib: FishLibrary,
                      decor_lib: DecorLibrary, bonus: Optional[float] = None) -> float:
    """当前每分钟产出（**厘**，浮点，未取整）。

    公式（C++ 端须逐项照抄，含运算顺序）::

        base   = Σ base_income[rarity] × stage_coef[stage]     # 按 uid 升序求和
        rate   = base × coin_scale
               × quality_factor(water)
               × satiety_factor(satiety)
               × (1 + total_bonus)

    :param bonus: 预先算好的总加成；None 表示现算（离线逐步结算时由调用方
                  缓存复用，避免每步重扫图鉴 —— 数值完全一致，只是省 CPU）
    :returns: float，厘/分钟
    """
    fishes = state.fishes_sorted()
    base = tank_base_per_min(fishes, species_lib, bal)
    rate = base * bal.coin_scale()
    rate *= quality_factor(state.tank.water, bal)
    rate *= satiety_factor(state.tank.satiety, bal)
    if bonus is None:
        # 🔴 图鉴加成看的是**图鉴**（曾经拥有）而不是当前在缸的鱼：
        #    卖掉一条鱼不该让已解锁的族群加成消失（准则 L1/L2：进度只增不减）。
        bonus = total_bonus(state.tank.decors, state.codex_species(),
                            decor_lib, species_lib, bal)
    rate *= (1.0 + bonus)
    return rate


def net_rate_milli(state: GameState, bal: BalanceTable, species_lib: FishLibrary,
                   decor_lib: DecorLibrary, bonus: Optional[float] = None) -> float:
    """扣掉投食器维护费后的净产出速率（厘/分钟）。

    准则 L2（收益永不为负）：净速率下限钳到 0，维护费**绝不会**吃掉本金。
    """
    gross = income_rate_milli(state, bal, species_lib, decor_lib, bonus=bonus)
    upkeep = 0.0
    if state.tank.feeder_active():
        upkeep = feeder_upkeep_rate_milli(state.fish_count(), bal)
    return max(0.0, gross - upkeep)


def step_gain_milli(state: GameState, bal: BalanceTable, species_lib: FishLibrary,
                    decor_lib: DecorLibrary, step_sec: float, efficiency: float = 1.0,
                    bonus: Optional[float] = None) -> int:
    """一个时间步的净收益（**整数厘**，已四舍五入）。

    🔴 全流程只在这里取整一次；上游一律用浮点，避免逐步取整累积误差。
    🔴 在线与离线共用本函数，唯一区别是 ``efficiency``（在线恒为 1.0）。

    :param step_sec: 步长秒数
    :param efficiency: 离线效率系数
    :returns: int，厘（>= 0）
    """
    rate = net_rate_milli(state, bal, species_lib, decor_lib, bonus=bonus)
    return max(0, round_half_up(rate * (float(step_sec) / 60.0) * float(efficiency)))


def income_step_milli(state: GameState, bal: BalanceTable, species_lib: FishLibrary,
                      decor_lib: DecorLibrary, step_sec: float,
                      efficiency: float = 1.0) -> int:
    """一个时间步的**毛**产出（整数厘），不扣维护费。仅供对照/测试。"""
    rate = income_rate_milli(state, bal, species_lib, decor_lib)
    return round_half_up(rate * (float(step_sec) / 60.0) * float(efficiency))


# ══════════════════════════════════════════════════════════════
#  离线效率分段
# ══════════════════════════════════════════════════════════════

def offline_efficiency(elapsed_sec: float, bal: BalanceTable) -> float:
    """按"已离线时长"查分段效率系数。

    分段表 ``offline.segments`` 形如 ``[[lo_min, hi_min|null, k], ...]``，
    区间左闭右开，最后一段 hi 为 null 表示无穷。默认::

        [0, 480)   → 1.00      前 8 小时全速
        [480,1440) → 0.60      8~24 小时六折
        [1440, ∞)  → 0.35      24 小时以后三五折

    ⚠️ 该系数按**已流逝时长**取值，不是对总时长取一个系数 ——
    所以 1 天离线 = 480×1.00 + 960×0.60 = 1056 等效分钟 = 17.6 等效小时。

    :param elapsed_sec: 从离线起点算起已流逝的秒数（取步的**起点**）
    :param bal: BalanceTable
    :returns: float
    """
    minutes = float(elapsed_sec) / 60.0
    segs = bal.offline_segments()
    last_k = 1.0
    for seg in segs:
        if not isinstance(seg, (list, tuple)) or len(seg) < 3:
            continue
        lo = float(seg[0]) if seg[0] is not None else 0.0
        hi = seg[1]
        try:
            k = float(seg[2])
        except (TypeError, ValueError):
            k = 1.0
        last_k = k
        if minutes < lo:
            continue
        if hi is None or minutes < float(hi):
            return k
    return last_k


def offline_equivalent_minutes(away_sec: float, bal: BalanceTable) -> float:
    """把真实离线秒数换算成"等效满速分钟数"（解析解，仅用于展示/自检）。

    ⚠️ 这是**闭式积分**，不参与实际结算（实际结算按步累加）。
    两者在步长能整除分段边界时结果一致，用于金标准回归测试。
    """
    minutes = float(away_sec) / 60.0
    segs = bal.offline_segments()
    total = 0.0
    for seg in segs:
        if not isinstance(seg, (list, tuple)) or len(seg) < 3:
            continue
        lo = float(seg[0]) if seg[0] is not None else 0.0
        hi = float(seg[1]) if seg[1] is not None else float("inf")
        try:
            k = float(seg[2])
        except (TypeError, ValueError):
            k = 1.0
        span = min(minutes, hi) - lo
        if span > 0.0:
            total += span * k
    return total


# ══════════════════════════════════════════════════════════════
#  商店价格
# ══════════════════════════════════════════════════════════════

def fry_price(rarity: str, bal: BalanceTable) -> int:
    """鱼苗售价（**金币**，整数）。未知稀有度回退 R1。"""
    p = bal.get("shop.fry_price." + str(rarity))
    if p is None:
        p = bal.get("shop.fry_price.R1", 50)
    try:
        return int(p)
    except (TypeError, ValueError):
        return 50


def fry_price_milli(rarity: str, bal: BalanceTable) -> int:
    """鱼苗售价（厘）。"""
    return fry_price(rarity, bal) * bal.coin_scale()


def auto_sell_price_milli(rarity: str, stage: str, age_sec: float,
                          bal: BalanceTable) -> int:
    """自动卖出价格（厘）。

    公式：fish_price × stage_multiplier × (1 + min(age_hours × age_bonus_per_hour, max_age_bonus))

    :param rarity: 稀有度 "R1"~"R5"
    :param stage: 成长阶段 "fry"/"juvenile"/"adult"/"mature"
    :param age_sec: 鱼当前年龄（秒）
    :param bal: BalanceTable 实例
    :returns: 卖出价格（厘，整数）
    """
    cfg = bal.get("autosell") or {}
    if not cfg.get("enabled", False):
        return 0
    base = fry_price_milli(rarity, bal)
    sm = (cfg.get("stage_multiplier") or {}).get(str(stage), 1.0)
    abph = float(cfg.get("age_bonus_per_hour", 0.02) or 0)
    max_ab = float(cfg.get("max_age_bonus", 3.0) or 0)
    age_hours = float(age_sec) / 3600.0
    age_bonus = 1.0 + min(age_hours * abph, max_ab)
    return int(round_half_up(float(base) * float(sm) * float(age_bonus)))


def upgrade_price(kind: str, next_level: int, bal: BalanceTable) -> int:
    """升级价格（**金币**）。已满级返回 -1。

    :param kind: "capacity" / "filter" / "feeder"
    :param next_level: 目标等级（capacity/filter 用；feeder 忽略）
    """
    kind = str(kind)
    if kind == "feeder":
        return int(bal.get("shop.feeder_price", 300) or 300)
    key = "shop.capacity_price" if kind == "capacity" else "shop.filter_price"
    table = bal.get(key)
    if not isinstance(table, list) or not table:
        return -1
    lv = int(next_level)
    if lv <= 0 or lv >= len(table):
        return -1
    try:
        return int(table[lv])
    except (TypeError, ValueError):
        return -1


def upgrade_price_milli(kind: str, next_level: int, bal: BalanceTable) -> int:
    """升级价格（厘）。已满级返回 -1。"""
    p = upgrade_price(kind, next_level, bal)
    return -1 if p < 0 else p * bal.coin_scale()


def max_level(kind: str, bal: BalanceTable) -> int:
    """某升级项的最高等级下标。"""
    kind = str(kind)
    if kind == "feeder":
        return 1
    key = "shop.capacity_price" if kind == "capacity" else "shop.filter_price"
    table = bal.get(key)
    if not isinstance(table, list) or not table:
        return 0
    return len(table) - 1


def format_coins(coins_milli: int, bal: BalanceTable) -> str:
    """厘 → 展示用金币字符串（保留 1 位小数，去掉多余的 .0）。

    仅用于 UI，不参与任何计算。
    """
    scale = bal.coin_scale() or 1000
    v = float(coins_milli) / float(scale)
    if abs(v) >= 10000.0:
        return "%.1fw" % (v / 10000.0)
    if abs(v - int(v)) < 0.05:
        return "%d" % int(v)
    return "%.1f" % v
