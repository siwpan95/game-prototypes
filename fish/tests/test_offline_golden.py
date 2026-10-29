"""★ 离线结算金标准测试 —— 双端一致性的验收基准。

本文件里的每一条断言都是 **XJ380 C++ 端必须同样通过的契约**。
任何一条挂掉，都意味着 Python 端改动破坏了双端一致性，必须同步改 C++ 或回滚。
"""

import json
import os

import pytest

from fishtank.data_defs import load_all
from fishtank.economy import offline_equivalent_minutes, round_half_up
from fishtank.offline import (
    MIN_REPORT_SEC, settle_offline, stepped_equivalent_minutes,
)
from fishtank.rng import DetRandom
from fishtank.state import FishState, GameState, TankState
from tests.conftest import GOLDEN_DIR, T0

GOLDEN_FILE = os.path.join(GOLDEN_DIR, "offline_cases.json")


@pytest.fixture(scope="module")
def golden():
    """加载金标准文件。"""
    assert os.path.isfile(GOLDEN_FILE), \
        "缺少金标准文件，请先跑 `python tools/gen_golden.py`"
    with open(GOLDEN_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _case_ids(data):
    return [c["name"] for c in data["cases"]]


# ══════════════════════════════════════════════════════════════
#  ★ 金标准比值（架构文档里写死的三个数）
# ══════════════════════════════════════════════════════════════

def test_golden_ratio_one_day(bal):
    """★ 离线 1 天 = 17.6 等效小时。"""
    eq = stepped_equivalent_minutes(86400, bal)
    assert eq == pytest.approx(1056.0)
    assert eq / 60.0 == pytest.approx(17.6)


def test_golden_ratio_seven_days(bal):
    """★ 离线 7 天 = 68.0 等效小时。"""
    eq = stepped_equivalent_minutes(604800, bal)
    assert eq == pytest.approx(4080.0)
    assert eq / 60.0 == pytest.approx(68.0)


def test_golden_ratio_7d_over_1d(bal):
    """★ 7 天 / 1 天 = 3.86（7 倍时长只换 3.86 倍收益）。"""
    r = stepped_equivalent_minutes(604800, bal) / stepped_equivalent_minutes(86400, bal)
    assert round(r, 2) == 3.86


def test_stepped_equals_closed_form(bal):
    """步进累加 == 闭式积分：证明没有任何一步跨越分段边界。"""
    for sec in (0, 1, 60, 3599, 3600, 28799, 28800, 28801,
                86399, 86400, 86401, 100000, 604800, 2592000, 31536000):
        assert stepped_equivalent_minutes(sec, bal) == \
            pytest.approx(offline_equivalent_minutes(sec, bal), abs=1e-9), \
            "away=%ds 时步进与闭式解不一致" % sec


def test_efficiency_boundaries_are_step_aligned(bal):
    """分段边界必须能被细步长整除，否则步进会失真。"""
    fine = int(bal.get("offline.fine_step_sec"))
    for seg in bal.offline_segments():
        for edge in (seg[0], seg[1]):
            if edge is None:
                continue
            assert (float(edge) * 60.0) % fine == 0, \
                "分段边界 %s 分钟不能被 %ds 的细步长整除" % (edge, fine)
    assert int(bal.get("offline.fine_limit_sec")) % fine == 0


# ══════════════════════════════════════════════════════════════
#  金标准逐用例回归
# ══════════════════════════════════════════════════════════════

def test_golden_cases_replay(golden, bal, species, decor):
    """把金标准里的每条 input 重新跑一遍，expect 必须逐字段吻合。"""
    failures = []
    for case in golden["cases"]:
        st = GameState.from_dict(case["input"])
        away = int(case["away_sec_requested"])
        new_st, rep = settle_offline(st, T0 + away, bal, species, decor)
        got = {
            "away_sec": rep.away_sec,
            "capped": rep.capped,
            "clock_rollback": rep.clock_rollback,
            "steps": rep.steps,
            "equivalent_min": round(rep.equivalent_min, 6),
            "coins_gained_milli": rep.coins_gained_milli,
            "coins_after_milli": new_st.coins_milli,
            "water_after": round(new_st.tank.water, 6),
            "satiety_after": round(new_st.tank.satiety, 6),
            "fish_count_after": new_st.fish_count(),
            "rng_seed_after": new_st.rng_seed,
            "next_uid_after": new_st.next_uid,
            "stages_after": {str(f.uid): f.stage for f in new_st.fishes_sorted()},
            "born_species": [b["species"] for b in rep.born],
            "grown_count": len(rep.grown),
        }
        want = case["expect"]
        for key in sorted(want.keys()):
            if got[key] != want[key]:
                failures.append("[%s] %s: got=%r want=%r"
                                % (case["name"], key, got[key], want[key]))
    assert not failures, "金标准回归失败：\n  " + "\n  ".join(failures)


def test_golden_meta_documents_contract(golden):
    """金标准头部必须写清 C++ 端要复现的三件事。"""
    meta = golden["_meta"]
    assert meta["step_order"] == ["growth", "water", "satiety", "income", "breeding"]
    assert "floor(x + 0.5)" in meta["rounding"]
    assert "6364136223846793005" in meta["rng"]


# ══════════════════════════════════════════════════════════════
#  纯函数性 / 确定性
# ══════════════════════════════════════════════════════════════

def test_settle_is_pure(new_state, bal, species, decor):
    """★ settle_offline 绝不修改入参 —— 双端一致性的基石。"""
    before = json.dumps(new_state.to_dict(), sort_keys=True, ensure_ascii=False)
    settle_offline(new_state, T0 + 604800, bal, species, decor)
    after = json.dumps(new_state.to_dict(), sort_keys=True, ensure_ascii=False)
    assert before == after


def test_settle_returns_new_object(new_state, bal, species, decor):
    st2, _ = settle_offline(new_state, T0 + 3600, bal, species, decor)
    assert st2 is not new_state
    assert st2.tank is not new_state.tank
    if new_state.fishes:
        assert st2.fishes[0] is not new_state.fishes[0]


def test_settle_is_deterministic(new_state, bal, species, decor):
    """同样输入跑 5 次，结果必须逐字段一致（含 RNG 种子）。"""
    results = []
    for _ in range(5):
        st, rep = settle_offline(new_state, T0 + 259200, bal, species, decor)
        results.append((json.dumps(st.to_dict(), sort_keys=True, ensure_ascii=False),
                        json.dumps(rep.to_dict(), sort_keys=True, ensure_ascii=False)))
    assert len(set(results)) == 1


# ══════════════════════════════════════════════════════════════
#  8 个边界条件（架构文档 §8）
# ══════════════════════════════════════════════════════════════

def test_boundary_zero_elapsed(new_state, bal, species, decor):
    """① 离线 0 秒：不产币、不推进。"""
    st, rep = settle_offline(new_state, T0, bal, species, decor)
    assert rep.away_sec == 0
    assert rep.coins_gained_milli == 0
    assert st.coins_milli == new_state.coins_milli
    assert not rep.has_content()


def test_boundary_clock_rollback(new_state, bal, species, decor):
    """② 时钟回拨：不结算、不扣币、**锚点不后退**（准则 L2）。"""
    st, rep = settle_offline(new_state, T0 - 86400, bal, species, decor)
    assert rep.clock_rollback
    assert rep.coins_gained_milli == 0
    assert st.coins_milli == new_state.coins_milli
    assert st.saved_at_utc == new_state.saved_at_utc, "锚点不能被回拨的时钟带走"
    # 时钟走回来后仍然能拿到完整收益
    st2, rep2 = settle_offline(st, T0 + 3600, bal, species, decor)
    assert rep2.away_sec == 3600
    assert rep2.coins_gained_milli > 0


def test_boundary_hard_cap(new_state, bal, species, decor):
    """③ 超长离线：被 hard_cap 截断，且不溢出、不为负。"""
    st, rep = settle_offline(new_state, T0 + bal.hard_cap_sec() * 3, bal, species, decor)
    assert rep.capped
    assert rep.away_sec == bal.hard_cap_sec()
    assert rep.coins_gained_milli > 0
    assert st.coins_milli > 0


def test_boundary_empty_tank(new_state, bal, species, decor):
    """④ 空缸：不崩溃、不产币、水质不变差到非法值。"""
    new_state.fishes = []
    st, rep = settle_offline(new_state, T0 + 604800, bal, species, decor)
    assert rep.coins_gained_milli == 0
    assert st.fish_count() == 0
    assert bal.water_min() <= st.tank.water <= bal.water_max()


def test_boundary_full_tank_no_breeding(bal, species, decor):
    """⑤ 缸满：不再繁殖，也不会挤掉已有的鱼（准则 L1：鱼永不消失）。"""
    cap = bal.capacity_of(0)
    fishes = [FishState(uid=i, species="neon_tetra", born_at=T0,
                        age_sec=7200 * 3, stage="mature", last_bred_at=0,
                        x=0.5, y=0.5)
              for i in range(1, cap + 1)]
    st0 = GameState(schema=1, saved_at_utc=T0, coins_milli=0,
                    rng_seed=12345, next_uid=cap + 1,
                    tank=TankState(water=100.0), fishes=fishes,
                    codex={"neon_tetra": T0})
    st, rep = settle_offline(st0, T0 + 604800, bal, species, decor)
    assert st.fish_count() == cap
    assert rep.born == []


def test_boundary_water_floor(bal, species, decor):
    """⑥ 水质触底：钳在 water.min，收益打折但**绝不归零**（准则 L4）。"""
    fishes = [FishState(uid=i, species="zebra_danio", born_at=T0,
                        age_sec=21600 * 3, stage="mature", x=0.5, y=0.5)
              for i in range(1, 7)]
    st0 = GameState(schema=1, saved_at_utc=T0, coins_milli=0, rng_seed=7,
                    next_uid=99, tank=TankState(water=100.0, filter_level=0),
                    fishes=fishes, codex={"zebra_danio": T0})
    st, rep = settle_offline(st0, T0 + 604800, bal, species, decor)
    assert st.tank.water == pytest.approx(bal.water_min())
    assert rep.coins_gained_milli > 0


def test_boundary_coins_never_negative(bal, species, decor):
    """⑦ 投食器维护费再高也不能把金币扣成负数（准则 L2）。"""
    fishes = [FishState(uid=i, species="neon_tetra", born_at=T0,
                        age_sec=0.0, stage="fry", x=0.5, y=0.5)
              for i in range(1, 7)]
    st0 = GameState(schema=1, saved_at_utc=T0, coins_milli=0, rng_seed=3,
                    next_uid=99,
                    tank=TankState(water=bal.water_min(), filter_level=0,
                                   feeder_owned=True, feeder_on=True, satiety=0.0),
                    fishes=fishes, codex={"neon_tetra": T0})
    st, rep = settle_offline(st0, T0 + 604800, bal, species, decor)
    assert st.coins_milli >= 0
    assert rep.coins_gained_milli >= 0


def test_boundary_unknown_species_is_survivable(bal, species, decor):
    """⑧ 存档里有已下线的鱼种：按 R1 兜底，不崩溃、不丢鱼（准则 L1）。"""
    st0 = GameState(schema=1, saved_at_utc=T0, coins_milli=0, rng_seed=5,
                    next_uid=9,
                    tank=TankState(water=100.0),
                    fishes=[FishState(uid=1, species="__ghost_fish__",
                                      born_at=T0, age_sec=0.0, stage="fry",
                                      x=0.5, y=0.5)],
                    codex={})
    st, rep = settle_offline(st0, T0 + 86400, bal, species, decor)
    assert st.fish_count() == 1
    assert st.coins_milli >= 0


# ══════════════════════════════════════════════════════════════
#  单调性与"不亏"保证
# ══════════════════════════════════════════════════════════════

def test_longer_offline_never_earns_less(new_state, bal, species, decor):
    """离线越久，收益单调不减（准则 L7：多离线一秒也不能变亏）。"""
    prev = -1
    for sec in (0, 60, 600, 3600, 28800, 86400, 172800, 604800, 2592000):
        _st, rep = settle_offline(new_state, T0 + sec, bal, species, decor)
        assert rep.coins_gained_milli >= prev, "away=%d 反而变少了" % sec
        prev = rep.coins_gained_milli


def test_split_settlement_is_not_better_than_one_shot(new_state, bal, species, decor):
    """把一段离线拆成两段结算，不会拿到明显更多的钱（防"存档刷币"）。

    ⚠️ 分段结算天然略优（第二段从 0 重新计效率），这里只要求差距在合理范围内，
    并且**不会亏**（准则 L2）。
    """
    one, rep1 = settle_offline(new_state, T0 + 172800, bal, species, decor)
    mid, repa = settle_offline(new_state, T0 + 86400, bal, species, decor)
    two, repb = settle_offline(mid, T0 + 172800, bal, species, decor)
    assert repa.coins_gained_milli + repb.coins_gained_milli >= 0
    assert rep1.coins_gained_milli > 0
    # 一次结算不应该比分两次亏太多（<= 2 倍）
    split = repa.coins_gained_milli + repb.coins_gained_milli
    assert split <= rep1.coins_gained_milli * 2 + 1


def test_report_has_content_threshold(new_state, bal, species, decor):
    """准则 L6：短暂离开不弹卡片，不打扰玩家。"""
    _st, rep = settle_offline(new_state, T0 + MIN_REPORT_SEC - 1, bal, species, decor)
    assert not rep.has_content()
    _st, rep = settle_offline(new_state, T0 + 7200, bal, species, decor)
    assert rep.has_content()


def test_growth_not_penalized_offline(new_state, bal, species, decor):
    """准则 L7：成长按真实时间推进，离线不打折。"""
    st, _rep = settle_offline(new_state, T0 + 3600, bal, species, decor)
    for f in st.fishes_sorted():
        assert f.age_sec == pytest.approx(3600.0)


def test_fish_never_disappear(new_state, bal, species, decor):
    """准则 L1：无论离线多久，原有的鱼一条都不能少。"""
    before = {f.uid for f in new_state.fishes}
    for sec in (3600, 86400, 604800, 31536000):
        st, _ = settle_offline(new_state, T0 + sec, bal, species, decor)
        assert before.issubset({f.uid for f in st.fishes})


# ══════════════════════════════════════════════════════════════
#  确定性随机数
# ══════════════════════════════════════════════════════════════

def test_lcg_sequence_is_fixed():
    """LCG 前 8 个输出写死在测试里 —— C++ 端必须一模一样。"""
    r = DetRandom(1)
    got = [r.next_u32() for _ in range(8)]
    expect = []
    seed = 1
    for _ in range(8):
        seed = (seed * 6364136223846793005 + 1442695040888963407) % (1 << 64)
        expect.append((seed >> 32) & 0xFFFFFFFF)
    assert got == expect
    # 写死头 4 个值：C++ 端第一件事就是对这 4 个数
    assert got[:4] == [1817669548, 2187888307, 2784682393, 1644385741]


def test_lcg_reproducible():
    a = DetRandom(42)
    b = DetRandom(42)
    assert [a.next_u32() for _ in range(100)] == [b.next_u32() for _ in range(100)]


def test_lcg_random_in_range():
    r = DetRandom(99)
    for _ in range(10000):
        v = r.random()
        assert 0.0 <= v < 1.0


def test_lcg_randint_bounds():
    r = DetRandom(7)
    seen = set()
    for _ in range(5000):
        v = r.randint(3, 7)
        assert 3 <= v <= 7
        seen.add(v)
    assert seen == {3, 4, 5, 6, 7}


def test_lcg_chance_edges():
    r = DetRandom(11)
    before = r.calls
    assert r.chance(0.0) is False
    assert r.chance(1.0) is True
    assert r.calls == before, "0 / 1 概率不该消耗随机数"


def test_lcg_state_roundtrip():
    r = DetRandom(1234)
    for _ in range(37):
        r.next_u32()
    snapshot = r.state()
    tail_a = [r.next_u32() for _ in range(10)]
    r2 = DetRandom(0)
    r2.restore(snapshot)
    assert [r2.next_u32() for _ in range(10)] == tail_a


def test_round_half_up_is_the_only_rounding_used(bal, species, decor, new_state):
    """收益取整必须与 floor(x+0.5) 一致（抽样验证）。"""
    from fishtank.economy import net_rate_milli
    st = new_state
    rate = net_rate_milli(st, bal, species, decor)
    for step in (1, 7, 60, 3600):
        for eff in (1.0, 0.6, 0.35):
            from fishtank.economy import step_gain_milli
            assert step_gain_milli(st, bal, species, decor, step, eff) == \
                max(0, round_half_up(rate * step / 60.0 * eff))
