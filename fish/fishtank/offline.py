"""★ 离线结算：全项目**唯一**的时间推进权威实现。

🔴 禁止 `from __future__ import annotations`（E6）。
🔴 :func:`settle_offline` 是**纯函数**：深拷贝入参、返回新状态，绝不修改调用方
   传入的 `state`。这是"双端一致性"的基石 —— XJ380 C++ 端只要照抄本文件的
   步进顺序与公式，就能对同一份存档算出**逐厘相同**的结果。

═══ 算法总览 ═══

S0 准备
    深拷贝 state；`raw = now - saved_at_utc`；
    `raw <= 0`（时钟回拨）→ 不结算、不动锚点、不丢币，直接返回；
    `away = min(raw, offline.hard_cap_sec)`。

S1 分步
    `elapsed < offline.fine_limit_sec` 用 `fine_step_sec`（60s），之后用
    `coarse_step_sec`（3600s）；最后一步截断到 `away`。
    ⚠️ 60 能整除全部分段边界（28800s / 86400s），所以**没有任何一步会跨段**，
    分段效率按步起点取值即是精确值。

S2 单步推进（🔴 顺序固定，C++ 端必须一致）
    ① 成长：`age_sec += step`，重算 stage（成长**不打折**，准则 L7）
    ② 水质：`water += net_delta × step/60`，钳到 [min, max]
    ③ 饱食：自然衰减；有投食器且低于阈值则自动投食
    ④ 收益：`gain = round_half_up((毛速率 - 维护费速率) × step/60 × k)`
    ⑤ 繁殖：`breed_timer += step`，每满 `check_interval_sec` 判定一次

S3 汇总
    `saved_at_utc = now`；统计成长/新生/图鉴解锁，生成 :class:`OfflineReport`。

S4 返回
    `(新 state, report)`。

═══ 金标准 ═══

分段表 `[[0,480,1.0],[480,1440,0.6],[1440,null,0.35]]` 下：

* 离线 1 天  = 480×1.00 + 960×0.60                = 1056 分 = **17.6 等效小时**
* 离线 7 天  = 480×1.00 + 960×0.60 + 8640×0.35    = 4080 分 = **68.0 等效小时**
* 比值 68.0 / 17.6 = **3.86**（7 倍真实时长只换来 3.86 倍收益，
  既保证长期离线不亏，也避免"关机刷钱"成为最优解）
"""

from dataclasses import dataclass, field

from fishtank.constants import STAGE_FRY, STAGE_MATURE
from fishtank.economy import (
    BonusCache, auto_feed, auto_sell_price_milli, feeder_upkeep_rate_milli,
    offline_efficiency, rarity_at, rarity_index, round_half_up, stage_of,
    stage_reached, step_gain_milli, step_satiety, step_water,
)
from fishtank.engine_bootstrap import get_logger
from fishtank.rng import DetRandom
from fishtank.state import FishState, r6

_log = get_logger(__name__)

MAX_STEPS = 200000
"""步数保险丝。hard_cap（10 年）下理论步数约 8.9 万，这里留 2 倍余量。"""

MIN_REPORT_SEC = 60
"""少于这个时长就不弹离线卡片（准则 L6：不打扰）。"""


# ══════════════════════════════════════════════════════════════
#  结算报告
# ══════════════════════════════════════════════════════════════

@dataclass
class OfflineReport:
    """一次离线结算的结果摘要（只读，供 UI 与日志使用）。"""

    now_utc: int = 0
    anchor_utc: int = 0
    raw_away_sec: int = 0
    away_sec: int = 0
    capped: bool = False
    clock_rollback: bool = False
    steps: int = 0
    equivalent_min: float = 0.0
    coins_gained_milli: int = 0
    upkeep_milli: int = 0
    water_before: float = 0.0
    water_after: float = 0.0
    satiety_before: float = 0.0
    satiety_after: float = 0.0
    grown: list = field(default_factory=list)
    born: list = field(default_factory=list)
    new_codex: list = field(default_factory=list)

    def has_content(self):
        """是否值得向玩家展示（准则 L6：没内容就不弹窗）。"""
        if self.away_sec < MIN_REPORT_SEC:
            return False
        return bool(self.coins_gained_milli > 0 or self.grown or self.born)

    def away_hours(self):
        """真实离线小时数。"""
        return self.away_sec / 3600.0

    def equivalent_hours(self):
        """等效满速小时数。"""
        return self.equivalent_min / 60.0

    def to_dict(self):
        """转字典（写日志 / 传给 UI 层）。"""
        return {
            "now_utc": int(self.now_utc),
            "anchor_utc": int(self.anchor_utc),
            "raw_away_sec": int(self.raw_away_sec),
            "away_sec": int(self.away_sec),
            "capped": bool(self.capped),
            "clock_rollback": bool(self.clock_rollback),
            "steps": int(self.steps),
            "equivalent_min": r6(self.equivalent_min),
            "coins_gained_milli": int(self.coins_gained_milli),
            "upkeep_milli": int(self.upkeep_milli),
            "water_before": r6(self.water_before),
            "water_after": r6(self.water_after),
            "satiety_before": r6(self.satiety_before),
            "satiety_after": r6(self.satiety_after),
            "grown": list(self.grown),
            "born": list(self.born),
            "new_codex": list(self.new_codex),
        }


# ══════════════════════════════════════════════════════════════
#  繁殖（在线 / 离线共用的唯一实现）
# ══════════════════════════════════════════════════════════════

def _rarity_up_candidate(base_species, species_lib, rng):
    """在同族群里找一个高一档稀有度的鱼种；没有则返回 None。

    候选按 id 升序排列后再抽，保证双端一致。
    """
    base = species_lib.get(base_species)
    if base is None:
        return None
    nxt = rarity_at(rarity_index(base.rarity) + 1)
    if nxt == base.rarity:
        return None  # 已是最高档
    pool = sorted(f.id for f in species_lib.by_group(base.group) if f.rarity == nxt)
    if not pool:
        return None
    return rng.choice(pool)


def attempt_breed(state, bal, species_lib, rng, now):
    """尝试繁殖一次（**就地修改** state）。

    🔴 随机数消耗顺序即分支顺序，C++ 端必须照抄分支结构，否则种子会错位：

    1. 若存在"同种且都过冷却"的配对 → 抽 `same_species_chance`
    2. 否则 → 抽 `cross_species_chance`（异种）
    3. 命中后：异种再抽 1 次选亲本鱼种（randint 0/1）
    4. 抽 `rarity_up_chance`；命中且同族有高一档鱼种则再抽 1 次选具体鱼种
    5. 抽 `variant_chance`

    :returns: (新生 FishState 或 None, 是否首次解锁该鱼种)
    """
    if state.is_full(bal):
        return None, False

    min_stage = str(bal.get("breeding.min_parent_stage", "adult"))
    cooldown = int(bal.get("breeding.same_species_cooldown_sec", 10800) or 0)
    eligible = [f for f in state.fishes_sorted()
                if stage_reached(f.stage, min_stage)
                and (int(now) - int(f.last_bred_at)) >= cooldown]
    if len(eligible) < 2:
        return None, False

    # 同种配对：按鱼种 id 升序，取每种里 uid 最小的两条
    by_species = {}
    for f in eligible:
        by_species.setdefault(f.species, []).append(f)
    same_pairs = [(v[0], v[1]) for _k, v in sorted(by_species.items()) if len(v) >= 2]

    pair = None
    cross = False
    if same_pairs:
        if rng.chance(float(bal.get("breeding.same_species_chance", 0.12))):
            pair = same_pairs[0]
    if pair is None:
        if rng.chance(float(bal.get("breeding.cross_species_chance", 0.03))):
            a = eligible[0]
            b = None
            for f in eligible[1:]:
                if f.species != a.species:
                    b = f
                    break
            if b is not None:
                pair = (a, b)
                cross = True
    if pair is None:
        return None, False

    p1, p2 = pair
    if cross:
        child_species = p1.species if rng.randint(0, 1) == 0 else p2.species
    else:
        child_species = p1.species

    if rng.chance(float(bal.get("breeding.rarity_up_chance", 0.15))):
        up = _rarity_up_candidate(child_species, species_lib, rng)
        if up:
            child_species = up

    variant = rng.chance(float(bal.get("breeding.variant_chance", 0.05)))

    child = FishState(
        uid=state.alloc_uid(),
        species=child_species,
        born_at=int(now),
        age_sec=0.0,
        stage=STAGE_FRY,
        variant=variant,
        nickname="",
        last_bred_at=int(now),
        x=r6((p1.x + p2.x) * 0.5),
        y=r6((p1.y + p2.y) * 0.5),
        heading=p1.heading,
    )
    p1.last_bred_at = int(now)
    p2.last_bred_at = int(now)
    first = state.add_fish(child, when=int(now))
    state.bump_stat("bred", 1)
    state.bump_stat("born", 1)
    return child, first


def attempt_autosell(state, bal, species_lib):
    """尝试自动卖出一条最老的鱼。

    准则 L1：只增不减 —— 此函数**仅当鱼缸接近满载时才触发**。
    卖出策略：选年龄最大的鱼（即 ``age_sec`` 最大）。

    :param state: GameState（就地修改）
    :param bal: BalanceTable
    :param species_lib: SpeciesLibrary（用于查询稀有度）
    :returns: (sold_uid: int|None, sold_milli: int)
    """
    cfg = bal.get("autosell") or {}
    if not cfg.get("enabled", False):
        return None, 0

    # 最少保留数量
    min_fish = int(cfg.get("min_fish_before_sell", 3) or 3)
    if state.fish_count() <= min_fish:
        return None, 0

    # 只在鱼缸"够满"时触发
    cap = state.capacity(bal)
    threshold_pct = float(cfg.get("sell_threshold_pct", 0.80))
    if state.fish_count() < int(cap * threshold_pct):
        return None, 0

    # 前置条件：所有鱼都已进入最终阶段（mature），不再成长后才允许卖出
    for f in state.fishes:
        if f.stage != STAGE_MATURE:
            return None, 0

    # 找最老的鱼
    oldest = None
    oldest_age = -1.0
    for f in state.fishes:
        if f.age_sec > oldest_age:
            oldest_age = f.age_sec
            oldest = f
    if oldest is None:
        return None, 0

    # 查稀有度
    sp = species_lib.get(oldest.species) if species_lib else None
    rarity = sp.rarity if sp and sp.rarity else "R1"

    # 计算售价（stage 由增长系统维护，直接使用）
    sold_milli = auto_sell_price_milli(
        rarity, str(oldest.stage), oldest.age_sec, bal)

    # 移除 + 到账
    uid = oldest.uid
    state.remove_fish(uid)
    state.add_coins_milli(sold_milli)
    state.bump_stat("sold", 1)

    return uid, sold_milli


# ══════════════════════════════════════════════════════════════
#  单步推进（在线 / 离线共用）
# ══════════════════════════════════════════════════════════════

def advance_step(state, step_sec, now, bal, species_lib, decor_lib, rng,
                 efficiency=1.0, offline=True, do_breed=True, bonus_cache=None):
    """把 state **就地**推进一个时间步。

    🔴 五个阶段的顺序是双端契约的一部分，不得调整：
    成长 → 水质 → 饱食 → 收益 → 繁殖。

    :param step_sec: 步长秒数
    :param now: 该步**结束时刻**的 UTC 秒
    :param efficiency: 离线效率系数（在线传 1.0）
    :param offline: 水质是否走 offline_scale
    :param do_breed: 是否执行繁殖判定
    :param bonus_cache: 可选的 :class:`~fishtank.economy.BonusCache`（纯提速）
    :returns: dict，本步的增量摘要
    """
    step_sec = float(step_sec)
    out = {"gain_milli": 0, "upkeep_milli": 0,
           "grown": [], "born": [], "new_codex": [], "sold": []}

    # ① 成长（不打折：准则 L7 —— 离线也照常长大）
    th = bal.thresholds()
    for f in state.fishes_sorted():
        f.age_sec += step_sec
        sp = species_lib.get(f.species)
        cycle = bal.growth_cycle_sec(sp.rarity if sp else "R1")
        new_stage = stage_of(f.age_sec, cycle, th)
        if new_stage != f.stage:
            out["grown"].append({"uid": f.uid, "species": f.species,
                                 "from": f.stage, "to": new_stage})
            f.stage = new_stage

    # ② 水质
    state.tank.water = step_water(state.tank.water, state.fish_count(),
                                  state.tank.filter_level, step_sec, bal,
                                  offline=offline)

    # ③ 饱食度 + 自动投食
    state.tank.satiety = step_satiety(state.tank.satiety, step_sec, bal)
    if state.tank.feeder_active():
        state.tank.satiety, _fed = auto_feed(state.tank.satiety, bal)
        out["upkeep_milli"] = int(round_half_up(
            feeder_upkeep_rate_milli(state.fish_count(), bal)
            * (step_sec / 60.0) * float(efficiency)))

    # ④ 收益（全流程唯一一次取整）
    bonus = bonus_cache.value(state) if bonus_cache is not None else None
    gain = step_gain_milli(state, bal, species_lib, decor_lib, step_sec, efficiency,
                           bonus=bonus)
    state.add_coins_milli(gain)
    out["gain_milli"] = gain

    # ⑤ 繁殖
    if do_breed:
        interval = max(1, int(bal.get("breeding.check_interval_sec", 600) or 600))
        state.breed_timer += step_sec
        while state.breed_timer >= interval:
            state.breed_timer -= interval
            child, first = attempt_breed(state, bal, species_lib, rng, now)
            if child is not None:
                out["born"].append({"uid": child.uid, "species": child.species,
                                    "variant": child.variant})
                if first:
                    out["new_codex"].append(child.species)

    # ⑥ 自动卖出（准则 L1 的"减"由卖出实现，仅在满载时触发）
    interval = max(1, int(bal.get("autosell.check_interval_sec", 300) or 300))
    state.autosell_timer += step_sec
    while state.autosell_timer >= interval:
        state.autosell_timer -= interval
        uid, sold_milli = attempt_autosell(state, bal, species_lib)
        if uid is not None:
            out["sold"].append({"uid": uid, "sold_milli": sold_milli})
    return out


# ══════════════════════════════════════════════════════════════
#  ★ 离线结算主函数
# ══════════════════════════════════════════════════════════════

def settle_offline(state, now, bal, species_lib, decor_lib):
    """★ 纯函数离线结算。

    :param state: 读档得到的 GameState（**不会被修改**）
    :param now: 当前 UTC 整秒
    :param bal: BalanceTable
    :param species_lib: FishLibrary
    :param decor_lib: DecorLibrary
    :returns: (新的 GameState, OfflineReport)
    """
    # ── S0 准备 ──────────────────────────────────────────────
    st = state.deep_copy()
    now = int(now)
    anchor = int(st.saved_at_utc)
    rep = OfflineReport(now_utc=now, anchor_utc=anchor)
    rep.water_before = st.tank.water
    rep.satiety_before = st.tank.satiety

    if anchor <= 0:
        # 新档 / 无锚点：只补锚点，不结算
        st.saved_at_utc = now
        rep.water_after = st.tank.water
        rep.satiety_after = st.tank.satiety
        return st, rep

    raw_away = now - anchor
    rep.raw_away_sec = raw_away
    if raw_away <= 0:
        # 🔴 边界：系统时钟被回拨。既不结算也**不动锚点** ——
        #    等时钟走回来时玩家仍能拿到这段时间的收益（准则 L2：收益永不丢失）。
        rep.clock_rollback = True
        rep.water_after = st.tank.water
        rep.satiety_after = st.tank.satiety
        return st, rep

    hard_cap = max(1, bal.hard_cap_sec())
    away = min(raw_away, hard_cap)
    rep.capped = away < raw_away
    rep.away_sec = away

    # ── S1 分步 ──────────────────────────────────────────────
    fine_step = max(1, int(bal.get("offline.fine_step_sec", 60) or 60))
    coarse_step = max(fine_step, int(bal.get("offline.coarse_step_sec", 3600) or 3600))
    fine_limit = max(0, int(bal.get("offline.fine_limit_sec", 86400) or 0))

    rng = DetRandom(st.rng_seed)
    bonus_cache = BonusCache(bal, species_lib, decor_lib)
    stage_before = {f.uid: f.stage for f in st.fishes}
    coins_before = st.coins_milli

    elapsed = 0
    steps = 0
    equivalent_min = 0.0
    upkeep_total = 0
    born = []
    new_codex = []

    while elapsed < away and steps < MAX_STEPS:
        step = fine_step if elapsed < fine_limit else coarse_step
        if elapsed + step > away:
            step = away - elapsed
        k = offline_efficiency(elapsed, bal)

        # ── S2 单步推进 ──
        out = advance_step(st, step, anchor + elapsed + step, bal,
                           species_lib, decor_lib, rng,
                           efficiency=k, offline=True, do_breed=True,
                           bonus_cache=bonus_cache)
        upkeep_total += out["upkeep_milli"]
        born.extend(out["born"])
        new_codex.extend(out["new_codex"])
        equivalent_min += (step / 60.0) * k

        elapsed += step
        steps += 1

    if steps >= MAX_STEPS:
        remaining = away - elapsed
        _log.error(
            "离线结算达步数上限 MAX_STEPS=%d，剩余 %d 秒未结算", MAX_STEPS, remaining)

    # ── S3 汇总 ──────────────────────────────────────────────
    st.rng_seed = rng.state()
    st.saved_at_utc = now

    grown = []
    for f in st.fishes_sorted():
        old = stage_before.get(f.uid)
        if old is not None and old != f.stage:
            grown.append({"uid": f.uid, "species": f.species, "from": old, "to": f.stage})

    rep.steps = steps
    rep.equivalent_min = equivalent_min
    rep.coins_gained_milli = st.coins_milli - coins_before
    rep.upkeep_milli = upkeep_total
    rep.water_after = st.tank.water
    rep.satiety_after = st.tank.satiety
    rep.grown = grown
    rep.born = born
    rep.new_codex = sorted(set(new_codex))
    st.bump_stat("offline_sec", away)

    # ── S4 返回 ──────────────────────────────────────────────
    return st, rep


# ══════════════════════════════════════════════════════════════
#  自检工具（金标准回归用）
# ══════════════════════════════════════════════════════════════

def stepped_equivalent_minutes(away_sec, bal):
    """按**真实步进计划**累加等效分钟数（不涉及状态，纯算术）。

    与 :func:`fishtank.economy.offline_equivalent_minutes` 的闭式解对照，
    可验证"步长不会跨越分段边界"这一前提是否仍然成立。
    """
    away = max(0, int(away_sec))
    fine_step = max(1, int(bal.get("offline.fine_step_sec", 60) or 60))
    coarse_step = max(fine_step, int(bal.get("offline.coarse_step_sec", 3600) or 3600))
    fine_limit = max(0, int(bal.get("offline.fine_limit_sec", 86400) or 0))
    elapsed = 0
    total = 0.0
    steps = 0
    while elapsed < away and steps < MAX_STEPS:
        step = fine_step if elapsed < fine_limit else coarse_step
        if elapsed + step > away:
            step = away - elapsed
        total += (step / 60.0) * offline_efficiency(elapsed, bal)
        elapsed += step
        steps += 1
    return total
