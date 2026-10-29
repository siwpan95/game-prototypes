"""economy.py 纯函数测试。

覆盖：取整语义、成长阶段边界、水质/饱食系数下限、加成封顶、产出速率、
离线分段效率、商店价格。
"""

import math

import pytest

from fishtank.constants import (
    STAGE_ADULT, STAGE_FRY, STAGE_JUVENILE, STAGE_MATURE,
)
from fishtank import economy as ec
from fishtank.state import FishState


# ══════════════════════════════════════════════════════════════
#  round_half_up：与内置 round 的差异是双端一致性的关键
# ══════════════════════════════════════════════════════════════

@pytest.mark.parametrize("x,expected", [
    (0.0, 0), (0.4, 0), (0.5, 1), (0.6, 1),
    (1.5, 2), (2.5, 3), (3.5, 4),          # 🔴 内置 round 在这里会给 2/2/4
    (-0.5, 0), (-1.5, -1), (-0.6, -1),
    (99.4999, 99), (99.5, 100),
])
def test_round_half_up(x, expected):
    assert ec.round_half_up(x) == expected


def test_round_half_up_differs_from_builtin():
    """显式记录差异，防止有人"顺手"改回内置 round。"""
    diffs = [x for x in (0.5, 1.5, 2.5, 3.5, 4.5)
             if ec.round_half_up(x) != round(x)]
    assert diffs == [0.5, 2.5, 4.5]


def test_round_half_up_matches_floor_formula():
    for i in range(-500, 500):
        x = i / 7.0
        assert ec.round_half_up(x) == math.floor(x + 0.5)


# ══════════════════════════════════════════════════════════════
#  成长阶段
# ══════════════════════════════════════════════════════════════

def test_stage_boundaries(bal):
    th = bal.thresholds()
    cycle = 1000.0
    assert ec.stage_of(0.0, cycle, th) == STAGE_FRY
    assert ec.stage_of(149.0, cycle, th) == STAGE_FRY
    assert ec.stage_of(150.0, cycle, th) == STAGE_JUVENILE      # 左闭右开
    assert ec.stage_of(449.0, cycle, th) == STAGE_JUVENILE
    assert ec.stage_of(450.0, cycle, th) == STAGE_ADULT
    assert ec.stage_of(1449.0, cycle, th) == STAGE_ADULT
    assert ec.stage_of(1450.0, cycle, th) == STAGE_MATURE
    assert ec.stage_of(999999.0, cycle, th) == STAGE_MATURE


def test_stage_never_regresses(bal):
    """成长单调：年龄递增时阶段序号绝不下降（准则 L4）。"""
    th = bal.thresholds()
    last = -1
    for age in range(0, 3000, 7):
        idx = ec.stage_index(ec.stage_of(age, 1000.0, th))
        assert idx >= last
        last = idx


def test_stage_of_zero_cycle_is_safe(bal):
    assert ec.stage_of(100.0, 0.0, bal.thresholds()) == STAGE_FRY


def test_stage_coef_monotonic(bal):
    tbl = bal.stage_coef_table()
    vals = [ec.stage_coef(s, tbl)
            for s in (STAGE_FRY, STAGE_JUVENILE, STAGE_ADULT, STAGE_MATURE)]
    assert vals == sorted(vals)
    assert all(v > 0 for v in vals)


def test_stage_reached():
    assert ec.stage_reached(STAGE_MATURE, STAGE_ADULT)
    assert ec.stage_reached(STAGE_ADULT, STAGE_ADULT)
    assert not ec.stage_reached(STAGE_JUVENILE, STAGE_ADULT)


def test_next_stage_seconds(bal):
    th = bal.thresholds()
    assert ec.next_stage_seconds(0.0, 1000.0, th) == 150
    assert ec.next_stage_seconds(150.0, 1000.0, th) == 300
    assert ec.next_stage_seconds(2000.0, 1000.0, th) == -1


# ══════════════════════════════════════════════════════════════
#  水质
# ══════════════════════════════════════════════════════════════

def test_quality_factor_range(bal):
    """准则 L4：最差水质也不会低于 quality_floor，收益永不归零。"""
    assert ec.quality_factor(bal.water_max(), bal) == pytest.approx(1.0)
    assert ec.quality_factor(bal.water_min(), bal) == pytest.approx(bal.quality_floor())
    assert ec.quality_factor(-9999, bal) == pytest.approx(bal.quality_floor())
    assert ec.quality_factor(9999, bal) == pytest.approx(1.0)
    for w in range(0, 201, 3):
        q = ec.quality_factor(w, bal)
        assert bal.quality_floor() - 1e-12 <= q <= 1.0 + 1e-12


def test_quality_factor_monotonic(bal):
    prev = -1.0
    for w in range(50, 101):
        q = ec.quality_factor(w, bal)
        assert q >= prev
        prev = q


def test_water_band_is_discrete(bal):
    """E11：UI 只能订阅这个整数档位，不能订阅连续的 water。"""
    assert ec.water_band(50.0, bal) == 0
    assert ec.water_band(59.9, bal) == 0
    assert ec.water_band(60.0, bal) == 1
    assert ec.water_band(100.0, bal) == 5
    bands = {ec.water_band(w / 10.0, bal) for w in range(500, 1001)}
    assert bands == {0, 1, 2, 3, 4, 5}


def test_water_delta_offline_scaled(bal):
    on = ec.water_delta_per_min(6, 0, bal, offline=False)
    off = ec.water_delta_per_min(6, 0, bal, offline=True)
    assert on < 0
    assert off == pytest.approx(on * bal.get("water.offline_scale"))
    # 平衡点不变：净变化为 0 时，在线/离线都为 0（不给挂机套利空间）
    assert ec.water_delta_per_min(0, 0, bal, offline=True) == pytest.approx(0.0)


def test_step_water_clamped(bal):
    assert ec.step_water(100.0, 0, 3, 60, bal) <= bal.water_max()
    assert ec.step_water(50.0, 36, 0, 60, bal) >= bal.water_min()


# ══════════════════════════════════════════════════════════════
#  饱食度
# ══════════════════════════════════════════════════════════════

def test_satiety_factor_floor(bal):
    floor = float(bal.get("feeder.output_floor"))
    assert ec.satiety_factor(1.0, bal) == pytest.approx(1.0)
    assert ec.satiety_factor(0.0, bal) == pytest.approx(floor)
    assert ec.satiety_factor(-5.0, bal) == pytest.approx(floor)
    assert floor > 0.0, "准则 L4：饿肚子只能减速，不能让产出归零"


def test_auto_feed(bal):
    level = float(bal.get("feeder.auto_feed_level"))
    s, fed = ec.auto_feed(level + 0.01, bal)
    assert not fed and s == pytest.approx(level + 0.01)
    s, fed = ec.auto_feed(0.1, bal)
    assert fed and s > 0.1
    assert s <= float(bal.get("feeder.satiety_max"))


def test_step_satiety_decays_but_bounded(bal):
    s = 1.0
    for _ in range(100000):
        s = ec.step_satiety(s, 60, bal)
    assert s == pytest.approx(float(bal.get("feeder.satiety_min")))


# ══════════════════════════════════════════════════════════════
#  加成
# ══════════════════════════════════════════════════════════════

def test_decor_bonus_sums(bal, decor):
    ids = decor.ids()[:3]
    expect = sum(decor.bonus_of(i) for i in ids)
    assert ec.decor_bonus(ids, decor) == pytest.approx(expect)
    assert ec.decor_bonus([], decor) == 0.0
    assert ec.decor_bonus(["__no_such_decor__"], decor) == 0.0


def test_decor_bonus_ignores_duplicates(decor):
    one = decor.ids()[0]
    assert ec.decor_bonus([one, one, one], decor) == pytest.approx(decor.bonus_of(one))


def test_codex_bonus(bal, species):
    groups = species.groups()
    assert groups, "鱼种数据必须有族群"
    owned = set(species.group_members(groups[0]))
    assert ec.codex_bonus(owned, species, bal) == pytest.approx(bal.group_bonus())
    partial = set(list(owned)[:-1]) if len(owned) > 1 else set()
    assert ec.codex_bonus(partial, species, bal) == pytest.approx(0.0)


def test_total_bonus_capped(bal, species, decor):
    all_decor = decor.ids()
    all_species = species.ids()
    b = ec.total_bonus(all_decor, all_species, decor, species, bal)
    assert b == pytest.approx(bal.bonus_cap())
    raw = ec.decor_bonus(all_decor, decor) + ec.codex_bonus(all_species, species, bal)
    assert raw > bal.bonus_cap(), "全收集的裸加成应该超过上限，才能验证封顶生效"


# ══════════════════════════════════════════════════════════════
#  产出
# ══════════════════════════════════════════════════════════════

def test_income_rate_formula(bal, species, decor, new_state):
    st = new_state
    st.tank.water = bal.water_max()
    st.tank.satiety = float(bal.get("feeder.satiety_max"))
    expect = 0.0
    for f in st.fishes_sorted():
        sp = species.get(f.species)
        expect += bal.base_income(sp.rarity) * ec.stage_coef(f.stage, bal.stage_coef_table())
    expect *= bal.coin_scale()
    assert ec.income_rate_milli(st, bal, species, decor) == pytest.approx(expect)


def test_income_rate_scales_with_water(bal, species, decor, new_state):
    st = new_state
    st.tank.water = bal.water_max()
    hi = ec.income_rate_milli(st, bal, species, decor)
    st.tank.water = bal.water_min()
    lo = ec.income_rate_milli(st, bal, species, decor)
    assert lo == pytest.approx(hi * bal.quality_floor())
    assert lo > 0.0, "准则 L4：水质触底也必须有正收益"


def test_step_gain_never_negative(bal, species, decor, new_state):
    """准则 L2：投食器维护费再贵也不能倒扣本金。"""
    st = new_state
    st.tank.feeder_owned = True
    st.tank.feeder_on = True
    st.tank.water = bal.water_min()
    st.tank.satiety = 0.0
    for _ in range(50):
        assert ec.step_gain_milli(st, bal, species, decor, 60, 1.0) >= 0


def test_empty_tank_earns_zero(bal, species, decor, new_state):
    st = new_state
    st.fishes = []
    assert ec.income_rate_milli(st, bal, species, decor) == pytest.approx(0.0)
    assert ec.step_gain_milli(st, bal, species, decor, 3600, 1.0) == 0


def test_income_order_independent(bal, species, decor, new_state):
    """鱼在列表里的顺序不能影响结果（内部一律按 uid 升序求和）。"""
    st = new_state
    a = ec.income_rate_milli(st, bal, species, decor)
    st.fishes.reverse()
    b = ec.income_rate_milli(st, bal, species, decor)
    assert a == b


# ══════════════════════════════════════════════════════════════
#  离线分段效率
# ══════════════════════════════════════════════════════════════

def test_offline_efficiency_segments(bal):
    assert ec.offline_efficiency(0, bal) == pytest.approx(1.00)
    assert ec.offline_efficiency(28799, bal) == pytest.approx(1.00)
    assert ec.offline_efficiency(28800, bal) == pytest.approx(0.60)
    assert ec.offline_efficiency(86399, bal) == pytest.approx(0.60)
    assert ec.offline_efficiency(86400, bal) == pytest.approx(0.35)
    assert ec.offline_efficiency(10 ** 9, bal) == pytest.approx(0.35)


def test_offline_efficiency_never_zero(bal):
    """准则 L7：离线再久也不会停止产出。"""
    for sec in (0, 1, 3600, 86400, 864000, 8640000, 86400000):
        assert ec.offline_efficiency(sec, bal) > 0.0


def test_offline_efficiency_non_increasing(bal):
    prev = 2.0
    for sec in range(0, 200000, 137):
        k = ec.offline_efficiency(sec, bal)
        assert k <= prev + 1e-12
        prev = k


# ══════════════════════════════════════════════════════════════
#  商店
# ══════════════════════════════════════════════════════════════

def test_fry_price_increases_with_rarity(bal):
    prices = [ec.fry_price(r, bal) for r in ("R1", "R2", "R3", "R4", "R5")]
    assert prices == sorted(prices)
    assert prices[0] > 0


def test_upgrade_price_and_max_level(bal):
    assert ec.upgrade_price("capacity", 0, bal) == -1        # 0 级是初始，不可购买
    assert ec.upgrade_price("capacity", 1, bal) > 0
    top = ec.max_level("capacity", bal)
    assert ec.upgrade_price("capacity", top + 1, bal) == -1
    assert ec.upgrade_price("feeder", 1, bal) == int(bal.get("shop.feeder_price"))
    assert ec.upgrade_price_milli("capacity", 1, bal) == \
        ec.upgrade_price("capacity", 1, bal) * bal.coin_scale()


def test_capacity_grows_with_level(bal):
    caps = [bal.capacity_of(i) for i in range(ec.max_level("capacity", bal) + 1)]
    assert caps == sorted(caps)
    assert caps[0] >= 2


def test_format_coins(bal):
    assert ec.format_coins(0, bal) == "0"
    assert ec.format_coins(1000, bal) == "1"
    assert ec.format_coins(1500, bal) == "1.5"
    assert ec.format_coins(100000000, bal).endswith("w")


# ══════════════════════════════════════════════════════════════
#  平衡表自身
# ══════════════════════════════════════════════════════════════

def test_balance_validate_clean(bal):
    assert bal.validate() == []


def test_balance_get_missing_is_safe(bal):
    assert bal.get("no.such.path", 42) == 42
    assert bal.get("no.such.path") is None
    assert bal.get("water.filter_gain.1") == pytest.approx(0.2)


def test_no_formula_sandbox(bal):
    """E10：引擎没有 formula_engine，配置里也不许留公式沙盒开关。"""
    assert bal.get("economy._experimental_formula") is None


# ══════════════════════════════════════════════════════════════
#  clamp：钳制与边界交换
# ══════════════════════════════════════════════════════════════

def test_clamp_inside_range():
    """v 在 [lo, hi] 内时原样返回。"""
    assert ec.clamp(5.0, 0.0, 10.0) == 5.0
    assert ec.clamp(0.0, 0.0, 10.0) == 0.0
    assert ec.clamp(10.0, 0.0, 10.0) == 10.0


def test_clamp_below_range():
    """v < lo 时钳到 lo。"""
    assert ec.clamp(-5.0, 0.0, 10.0) == 0.0


def test_clamp_above_range():
    """v > hi 时钳到 hi。"""
    assert ec.clamp(15.0, 0.0, 10.0) == 10.0


def test_clamp_auto_swaps_reversed_bounds():
    """hi < lo 时自动交换上下限（防御 balance.json 写反）。"""
    # 交换后等价于 clamp(v, 0, 10)
    assert ec.clamp(5.0, 10.0, 0.0) == 5.0       # v 在有效区间内
    assert ec.clamp(-1.0, 10.0, 0.0) == 0.0       # v < 有效下限
    assert ec.clamp(15.0, 10.0, 0.0) == 10.0      # v > 有效上限
    # 更多交换组合：确保 swap 后钳制逻辑不受影响
    assert ec.clamp(-1.0, 7.0, 3.0) == 3.0        # swap → lo=3,hi=7, -1 < 3 → 3
    assert ec.clamp(99.0, 7.0, 3.0) == 7.0        # swap → lo=3,hi=7, 99 > 7 → 7
    assert ec.clamp(5.0, 7.0, 3.0) == 5.0         # swap → lo=3,hi=7, 5∈[3,7] → 5


# ══════════════════════════════════════════════════════════════
#  lerp：线性插值（t 自动钳制到 [0,1]）
# ══════════════════════════════════════════════════════════════

def test_lerp_t_zero():
    """t=0 返回 a。"""
    assert ec.lerp(10.0, 20.0, 0.0) == 10.0


def test_lerp_t_one():
    """t=1 返回 b。"""
    assert ec.lerp(10.0, 20.0, 1.0) == 20.0


def test_lerp_t_half():
    """t=0.5 返回中点。"""
    assert ec.lerp(10.0, 20.0, 0.5) == 15.0
    assert ec.lerp(0.0, 100.0, 0.5) == 50.0


def test_lerp_t_clamped_below():
    """t < 0 时被钳到 0，返回 a。"""
    assert ec.lerp(10.0, 20.0, -0.5) == 10.0
    assert ec.lerp(10.0, 20.0, -100.0) == 10.0


def test_lerp_t_clamped_above():
    """t > 1 时被钳到 1，返回 b。"""
    assert ec.lerp(10.0, 20.0, 1.5) == 20.0
    assert ec.lerp(10.0, 20.0, 100.0) == 20.0


# ══════════════════════════════════════════════════════════════
#  growth_progress：成长进度
# ══════════════════════════════════════════════════════════════

def test_growth_progress_normal():
    """标准进度 = age / cycle。"""
    assert ec.growth_progress(300.0, 1000.0) == pytest.approx(0.3)
    assert ec.growth_progress(0.0, 1000.0) == 0.0
    assert ec.growth_progress(1000.0, 1000.0) == 1.0


def test_growth_progress_cycle_zero():
    """cycle_sec <= 0 时兜底返回 0。"""
    assert ec.growth_progress(100.0, 0.0) == 0.0


def test_growth_progress_cycle_negative():
    """cycle_sec 为负时兜底返回 0。"""
    assert ec.growth_progress(100.0, -5.0) == 0.0


def test_growth_progress_exceeds_one():
    """age > cycle 时进度可以 > 1（mature 阶段）。"""
    assert ec.growth_progress(2000.0, 1000.0) == 2.0


# ══════════════════════════════════════════════════════════════
#  rarity_index / rarity_at：稀有度与序号互转
# ══════════════════════════════════════════════════════════════

@pytest.mark.parametrize("rarity,expected", [
    ("R1", 0), ("R2", 1), ("R3", 2), ("R4", 3), ("R5", 4),
])
def test_rarity_index(rarity, expected):
    """R1-R5 正确映射到 0-4。"""
    assert ec.rarity_index(rarity) == expected


def test_rarity_index_unknown():
    """无效稀有度返回 0（R1）。"""
    assert ec.rarity_index("R999") == 0
    assert ec.rarity_index("") == 0
    assert ec.rarity_index("unknown") == 0


@pytest.mark.parametrize("idx,expected", [
    (0, "R1"), (1, "R2"), (2, "R3"), (3, "R4"), (4, "R5"),
])
def test_rarity_at(idx, expected):
    """序号 0-4 正确映射到 R1-R5。"""
    assert ec.rarity_at(idx) == expected


def test_rarity_at_out_of_bounds():
    """越界序号钳到端点。"""
    assert ec.rarity_at(-1) == "R1"
    assert ec.rarity_at(-100) == "R1"
    assert ec.rarity_at(5) == "R5"
    assert ec.rarity_at(100) == "R5"


def test_rarity_roundtrip():
    """R → index → R 往返一致。"""
    for r in ("R1", "R2", "R3", "R4", "R5"):
        assert ec.rarity_at(ec.rarity_index(r)) == r


# ══════════════════════════════════════════════════════════════
#  BonusCache：加成缓存
# ══════════════════════════════════════════════════════════════

def test_bonus_cache_hit(bal, species, decor, new_state):
    """两次调用 value() 且状态不变时 — 缓存命中，返回相同值。"""
    cache = ec.BonusCache(bal, species, decor)
    v1 = cache.value(new_state)
    v2 = cache.value(new_state)
    assert v1 == v2
    assert cache._key is not None, "首次调用应填充缓存键"


def test_bonus_cache_invalidation_on_decor_change(bal, species, decor, new_state):
    """装饰集合变化后 value() 重新计算（缓存键变化）。"""
    cache = ec.BonusCache(bal, species, decor)
    cache.value(new_state)
    old_key = cache._key

    # 改变装饰集合
    ids = decor.ids()
    if ids:
        new_state.tank.decors.append(ids[0])
        cache.value(new_state)
        assert cache._key != old_key, "装饰变化后缓存键应不同 → 确实重算了"


def test_bonus_cache_invalidate_method(bal, species, decor, new_state):
    """invalidate() 强制清空缓存键，下次 value() 走重算路径。"""
    cache = ec.BonusCache(bal, species, decor)
    v1 = cache.value(new_state)
    assert cache._key is not None
    cache.invalidate()
    assert cache._key is None, "invalidate() 应清空缓存键"
    v2 = cache.value(new_state)
    assert v2 == v1, "状态未变，重算结果应与缓存时一致"
