"""QA 独立回归：离线结算 `settle_offline()` 的双端一致性契约。

🔴 禁止 `from __future__ import annotations`（E6）。

这份测试**不复用**工程师 `test_offline_golden.py` 的任何断言，而是从
ARCHITECTURE §离线结算算法 与 PRD 准则 L2/L7 重新独立推导预期值，
用"第二套算法"交叉验证实现。凡是文档里写死的数（17.6 / 68.0 / 3.86），
这里都**自己重算一遍**，不直接抄。

覆盖矩阵见 docs/QA_REPORT.md。
"""

import copy
import math

import pytest

from conftest import T0

from fishtank import offline as off
from fishtank.economy import offline_efficiency, round_half_up
from fishtank.offline import MAX_STEPS, settle_offline
from fishtank.state import FishState, GameState

HOUR = 3600
DAY = 86400


# ══════════════════════════════════════════════════════════════
#  独立参考实现（QA 自己写的第二套算法，用于交叉验证）
# ══════════════════════════════════════════════════════════════

def qa_reference_equiv_minutes(away_sec):
    """QA 独立实现的等效分钟数（硬编码默认分段，不读 balance.json）。

    刻意**不调用**任何被测代码 —— 如果实现和这里对不上，
    要么实现错了，要么 balance.json 被改了，两种都值得报警。
    """
    away = int(away_sec)
    if away <= 0:
        return 0.0
    total = 0.0
    elapsed = 0
    while elapsed < away:
        step = 60 if elapsed < DAY else 3600
        if elapsed + step > away:
            step = away - elapsed
        m = elapsed / 60.0
        if m < 480:
            k = 1.00
        elif m < 1440:
            k = 0.60
        else:
            k = 0.35
        total += (step / 60.0) * k
        elapsed += step
    return total


def qa_expected_step_plan(away_sec, fine_step=60, coarse_step=3600, fine_limit=DAY):
    """QA 独立实现的分步计划，返回 [(起点, 步长), ...]。"""
    plan = []
    elapsed = 0
    while elapsed < away_sec:
        step = fine_step if elapsed < fine_limit else coarse_step
        if elapsed + step > away_sec:
            step = away_sec - elapsed
        plan.append((elapsed, step))
        elapsed += step
    return plan


def make_state(bal, species, fish_specs, when=T0, coins=0):
    """按 (uid, species_id, age_sec) 三元组列表造一份状态。

    :param fish_specs: 插入顺序即列表顺序（用于验证 uid 排序不变性）
    """
    st = GameState(
        schema=1, saved_at_utc=when, coins_milli=coins,
        rng_seed=88172645463325252, next_uid=1, breed_timer=0.0,
    )
    st.tank.water = 100.0
    st.tank.satiety = 1.0
    for uid, sid, age in fish_specs:
        st.add_fish(FishState(uid=uid, species=sid, born_at=when, age_sec=float(age),
                              stage="adult", x=0.5, y=0.5, heading=1.0), when=when)
        st.next_uid = max(st.next_uid, uid + 1)
    return st


# ══════════════════════════════════════════════════════════════
#  A1  双层定步长：不丢步、不重复计步
# ══════════════════════════════════════════════════════════════

class TestStepPlan:
    """S1 分步计划的精确性。"""

    @pytest.mark.parametrize("away", [
        1, 59, 60, 61, 119, 3600,
        DAY - 60, DAY - 1, DAY, DAY + 1, DAY + 60,
        DAY + 3600, DAY + 3601, 2 * DAY, 7 * DAY,
    ])
    def test_steps_sum_exactly_to_away(self, bal, species, decor, away):
        """★ 所有步长之和必须**恰好**等于 away —— 一秒都不能丢、不能多。"""
        plan = qa_expected_step_plan(away)
        assert sum(s for _, s in plan) == away, "QA 参考计划自身就不守恒"

        st = make_state(bal, species, [(1, "neon_tetra", 0.0)])
        _new, rep = settle_offline(st, T0 + away, bal, species, decor)
        assert rep.away_sec == away
        assert rep.steps == len(plan), (
            "步数不符：实现 %d 步，QA 参考 %d 步（away=%d）" % (rep.steps, len(plan), away))

    def test_no_step_straddles_the_24h_boundary(self, bal):
        """★ 24h 是 fine→coarse 的切换点，不能有任何一步跨过它。"""
        plan = qa_expected_step_plan(3 * DAY)
        for start, step in plan:
            end = start + step
            assert not (start < DAY < end), (
                "步 [%d, %d) 跨越了 24h 边界" % (start, end))

    def test_no_step_straddles_efficiency_edges(self, bal):
        """★ 8h / 24h 两个效率分段边界都不能被任何一步跨过。

        这是"效率按块起点取值即精确值"的前提；一旦步长改成非 60 的约数
        （比如 90s），这个前提就会破，本测试会立刻变红。
        """
        edges = (480 * 60, 1440 * 60)  # 28800s / 86400s
        for start, step in qa_expected_step_plan(3 * DAY):
            end = start + step
            for e in edges:
                assert not (start < e < end), (
                    "步 [%d, %d) 跨越效率边界 %d" % (start, end, e))

    def test_fine_then_coarse_counts(self, bal, species, decor):
        """7 天离线 = 1440 个 60s 细步 + 144 个 3600s 粗步 = 1584 步。"""
        plan = qa_expected_step_plan(7 * DAY)
        fine = [p for p in plan if p[1] == 60]
        coarse = [p for p in plan if p[1] == 3600]
        assert len(fine) == 1440
        assert len(coarse) == 144
        assert len(plan) == 1584

        st = make_state(bal, species, [(1, "neon_tetra", 0.0)])
        _new, rep = settle_offline(st, T0 + 7 * DAY, bal, species, decor)
        assert rep.steps == 1584


# ══════════════════════════════════════════════════════════════
#  A2  效率按块起点取值（8h / 24h 边界的归属）
# ══════════════════════════════════════════════════════════════

class TestEfficiencySegments:
    """分段效率的边界归属 —— 左闭右开。"""

    @pytest.mark.parametrize("elapsed,expect", [
        (0, 1.00),
        (28799, 1.00),          # 8h 前最后一秒
        (28800, 0.60),          # ★ 恰好 8h → 归入第二段
        (28860, 0.60),
        (86399, 0.60),          # 24h 前最后一秒
        (86400, 0.35),          # ★ 恰好 24h → 归入第三段
        (10 * 365 * DAY, 0.35),  # 永久 0.35，不封顶为 0（L7）
    ])
    def test_boundary_belongs_to_the_later_segment(self, bal, elapsed, expect):
        """★ 边界值归属后一段（区间左闭右开）。"""
        assert offline_efficiency(elapsed, bal) == pytest.approx(expect)

    def test_efficiency_never_zero_or_negative(self, bal):
        """★ 准则 L7：离线越久边际效率递减，但**绝不为 0**。"""
        for days in (0, 1, 7, 30, 365, 3650):
            k = offline_efficiency(days * DAY, bal)
            assert k > 0.0, "离线 %d 天效率归零，违反 L7" % days
            assert math.isfinite(k)

    def test_efficiency_is_monotonically_non_increasing(self, bal):
        """效率随时长单调不增（不能出现"离线越久反而更快"的套利）。"""
        prev = 2.0
        for elapsed in range(0, 3 * DAY, 600):
            k = offline_efficiency(elapsed, bal)
            assert k <= prev + 1e-12, "效率在 %ds 处回升：%s > %s" % (elapsed, k, prev)
            prev = k


# ══════════════════════════════════════════════════════════════
#  A3  L7 金标准：QA 亲自算一遍，不信文档
# ══════════════════════════════════════════════════════════════

class TestL7GoldenNumbers:
    """长离线不惩罚的量化验收。"""

    def test_one_day_equals_17_6_equivalent_hours(self, bal, species, decor):
        """★ 1 天 = 480×1.00 + 960×0.60 = 1056 分 = 17.6 等效小时。"""
        # QA 手算
        manual = 480 * 1.00 + 960 * 0.60
        assert manual == 1056.0
        assert manual / 60.0 == 17.6
        # QA 参考实现
        assert qa_reference_equiv_minutes(DAY) == pytest.approx(1056.0, abs=1e-9)
        # 被测实现
        st = make_state(bal, species, [(1, "neon_tetra", 0.0)])
        _new, rep = settle_offline(st, T0 + DAY, bal, species, decor)
        assert rep.equivalent_min == pytest.approx(1056.0, abs=1e-6)
        assert rep.equivalent_hours() == pytest.approx(17.6, abs=1e-9)

    def test_seven_days_equals_68_equivalent_hours(self, bal, species, decor):
        """★ 7 天 = 1056 + 144×60×0.35 = 4080 分 = 68.0 等效小时。"""
        manual = 480 * 1.00 + 960 * 0.60 + (144 * 60) * 0.35
        assert manual == 4080.0
        assert manual / 60.0 == 68.0
        assert qa_reference_equiv_minutes(7 * DAY) == pytest.approx(4080.0, abs=1e-9)
        st = make_state(bal, species, [(1, "neon_tetra", 0.0)])
        _new, rep = settle_offline(st, T0 + 7 * DAY, bal, species, decor)
        assert rep.equivalent_min == pytest.approx(4080.0, abs=1e-6)
        assert rep.equivalent_hours() == pytest.approx(68.0, abs=1e-9)

    def test_ratio_is_3_86_and_at_least_3(self, bal, species, decor):
        """★ 7 天 / 1 天 收益比 = 3.86，必须 ≥ 3（PRD L7 硬指标）。"""
        st1 = make_state(bal, species, [(1, "neon_tetra", 0.0)])
        st7 = make_state(bal, species, [(1, "neon_tetra", 0.0)])
        _a, r1 = settle_offline(st1, T0 + DAY, bal, species, decor)
        _b, r7 = settle_offline(st7, T0 + 7 * DAY, bal, species, decor)
        ratio = r7.equivalent_min / r1.equivalent_min
        assert ratio == pytest.approx(3.8636363636, abs=1e-6)
        assert round(ratio, 2) == 3.86
        assert ratio >= 3.0, "7 天/1 天 收益比 %.4f < 3，违反 L7" % ratio

    def test_longer_offline_always_yields_more_coins(self, bal, species, decor):
        """★ L2/L7：离线越久，到手金币**单调不减**（绝不出现"回来晚了反而少"）。"""
        prev = -1
        for hours in (1, 4, 8, 12, 24, 48, 24 * 7, 24 * 30, 24 * 365):
            st = make_state(bal, species, [(1, "neon_tetra", 0.0), (2, "guppy", 0.0)])
            _new, rep = settle_offline(st, T0 + hours * HOUR, bal, species, decor)
            assert rep.coins_gained_milli >= prev, (
                "离线 %dh 收益 %d < 更短时长的 %d" % (hours, rep.coins_gained_milli, prev))
            prev = rep.coins_gained_milli


# ══════════════════════════════════════════════════════════════
#  A4  鱼按 uid 升序累加（浮点顺序敏感性）
# ══════════════════════════════════════════════════════════════

class TestUidOrderInvariance:
    """同一鱼群、不同插入顺序 → 结果必须逐位相同。"""

    SPECS = [
        (3, "guppy", 5000.0),
        (1, "neon_tetra", 100.0),
        (7, "goldfish", 20000.0),
        (2, "guppy", 300.0),
        (5, "neon_tetra", 90000.0),
    ]

    def _settle(self, order, bal, species, decor, away=3 * HOUR):
        st = make_state(bal, species, order)
        new, rep = settle_offline(st, T0 + away, bal, species, decor)
        return new, rep

    def test_insertion_order_does_not_change_coins(self, bal, species, decor):
        """★ 打乱插入顺序，金币必须**逐厘相同**（不是 approx，是 ==）。"""
        base_new, base_rep = self._settle(list(self.SPECS), bal, species, decor)
        for shift in range(1, len(self.SPECS)):
            shuffled = self.SPECS[shift:] + self.SPECS[:shift]
            new, rep = self._settle(shuffled, bal, species, decor)
            assert rep.coins_gained_milli == base_rep.coins_gained_milli, (
                "插入顺序 shift=%d 改变了金币：%d != %d"
                % (shift, rep.coins_gained_milli, base_rep.coins_gained_milli))
            assert new.coins_milli == base_new.coins_milli

    def test_insertion_order_does_not_change_full_state(self, bal, species, decor):
        """★ 更强：整份序列化状态（含水质/饱食/鱼龄）必须逐字节相同。"""
        base_new, _ = self._settle(list(self.SPECS), bal, species, decor)
        reverse_new, _ = self._settle(list(reversed(self.SPECS)), bal, species, decor)
        assert base_new.to_dict() == reverse_new.to_dict()

    def test_fishes_sorted_is_actually_sorted(self, bal, species):
        """`fishes_sorted()` 的排序保证本身。"""
        st = make_state(bal, species, list(reversed(self.SPECS)))
        uids = [f.uid for f in st.fishes_sorted()]
        assert uids == sorted(uids)
        assert uids != [f.uid for f in st.fishes], "样本没打乱，测试无效"


# ══════════════════════════════════════════════════════════════
#  A5  整数厘 + round_half_up（禁用银行家舍入）
# ══════════════════════════════════════════════════════════════

class TestRoundingContract:
    """C++ 端 `floor(x+0.5)` 的对齐验证。"""

    @pytest.mark.parametrize("x,expect", [
        (0.5, 1), (1.5, 2), (2.5, 3), (3.5, 4), (4.5, 5),
        (-0.5, 0), (-1.5, -1), (-2.5, -2),
        (0.49999999, 0), (0.50000001, 1),
        (0.0, 0), (1.0, 1), (999999.5, 1000000),
    ])
    def test_round_half_up_matches_cpp_floor_x_plus_half(self, x, expect):
        """★ round_half_up(x) 必须等于 C++ 的 floor(x+0.5)。"""
        assert round_half_up(x) == expect
        assert round_half_up(x) == int(math.floor(float(x) + 0.5))

    @pytest.mark.parametrize("x", [0.5, 2.5, 4.5, 6.5, 100.5])
    def test_round_half_up_differs_from_builtin_round(self, x):
        """★ 证明"用内置 round 会出错"不是纸上谈兵 —— 这些值两者确实不同。

        ⚠️ QA 自查记录：最初把 -0.5 / -2.5 也放进了样本，实测两者**相同**
        （floor(-0.5+0.5)=0 == round(-0.5)=0；floor(-2.0)=-2 == round(-2.5)=-2），
        即负半整数没有鉴别力。差异只出现在**正的偶数+0.5**上，故收敛到这组样本。
        """
        assert round_half_up(x) != round(x), (
            "样本 %s 下 round_half_up 与内置 round 恰好相同，该样本无鉴别力" % x)

    @pytest.mark.parametrize("x,half_up,bankers", [
        (-0.5, 0, 0),      # floor(0.0)=0   ；round → -0 → 0        一致
        (-1.5, -1, -2),    # floor(-1.0)=-1 ；round → -2（偶数）    不一致
        (-2.5, -2, -2),    # floor(-2.0)=-2 ；round → -2（偶数）    一致
        (-3.5, -3, -4),    # floor(-3.0)=-3 ；round → -4（偶数）    不一致
    ])
    def test_negative_half_rounding_table(self, x, half_up, bankers):
        """负半整数上两种舍入的完整对照表。

        规律：`round_half_up` 在负半整数上一律**朝 +∞**（floor(x+0.5)），
        而银行家舍入朝最近偶数。二者只在 |x| 为偶数+0.5 时偶然一致。
        本表把这个易错点钉死，避免后人拿 -0.5 当鉴别样本（我第一版就踩了）。
        """
        assert round_half_up(x) == half_up
        assert round(x) == bankers

    def test_exact_half_milli_rounds_up_in_settlement(self, bal, species, decor):
        """★ 构造收益恰好为 x.5 厘的一步，验证进位方向是**向上**。

        做法：直接调 `step_gain_milli` 并反推。这里用一条鱼 + 精心挑的步长，
        让 rate × step/60 落在 .5 上。
        """
        from fishtank.economy import net_rate_milli, step_gain_milli
        st = make_state(bal, species, [(1, "neon_tetra", 0.0)])
        st.fishes[0].stage = "adult"
        rate = net_rate_milli(st, bal, species, decor)
        assert rate > 0
        # 找一个让 rate*(step/60) 恰好是 .5 的 step
        step = 0.5 * 60.0 / rate
        raw = rate * (step / 60.0)
        assert raw == pytest.approx(0.5, abs=1e-12)
        got = step_gain_milli(st, bal, species, decor, step)
        assert got == 1, "恰好 0.5 厘应向上进位为 1，实得 %d（疑似银行家舍入）" % got

    def test_coins_are_always_integers(self, bal, species, decor):
        """金币在任何路径下都必须是 int（不能漏出浮点）。"""
        st = make_state(bal, species, [(1, "neon_tetra", 0.0), (2, "guppy", 0.0)])
        new, rep = settle_offline(st, T0 + 5 * DAY, bal, species, decor)
        assert isinstance(new.coins_milli, int)
        assert isinstance(rep.coins_gained_milli, int)
        assert isinstance(rep.upkeep_milli, int)


# ══════════════════════════════════════════════════════════════
#  A6  极端输入（时钟回拨 / 空缸 / 满缸 / 10 年）
# ══════════════════════════════════════════════════════════════

class TestExtremeInputs:
    """不崩、不产生 NaN/Inf、不丢币。"""

    def test_zero_seconds_offline(self, bal, species, decor):
        """离线 0 秒：不结算、不给币、不弹卡片。"""
        st = make_state(bal, species, [(1, "neon_tetra", 0.0)], coins=12345)
        new, rep = settle_offline(st, T0, bal, species, decor)
        assert rep.clock_rollback is True     # raw_away == 0 走回拨分支
        assert rep.steps == 0
        assert new.coins_milli == 12345
        assert rep.has_content() is False

    @pytest.mark.parametrize("back", [1, 60, 3600, DAY, 365 * DAY])
    def test_clock_rollback_keeps_anchor_and_coins(self, bal, species, decor, back):
        """★ 时钟回拨（用户改系统时间）：不结算、**不动锚点**、不丢币。

        锚点不动是关键 —— 等时钟走回来玩家仍能拿到这段收益（L2��。
        """
        st = make_state(bal, species, [(1, "neon_tetra", 0.0)], coins=999)
        new, rep = settle_offline(st, T0 - back, bal, species, decor)
        assert rep.clock_rollback is True
        assert new.saved_at_utc == T0, "回拨时锚点被改动，玩家会永久丢失这段收益"
        assert new.coins_milli == 999
        assert rep.coins_gained_milli == 0
        assert rep.steps == 0

    def test_rollback_then_recovery_loses_nothing(self, bal, species, decor):
        """★ L2 端到端：回拨 1 天 → 时钟走回正常 → 收益一分不少。"""
        st = make_state(bal, species, [(1, "neon_tetra", 0.0)])
        # 第一次：时钟被拨回 1 天，什么都不该发生
        mid, _ = settle_offline(st, T0 - DAY, bal, species, decor)
        # 第二次：时钟修好了，真实离线 2 天
        after_rollback, rep_a = settle_offline(mid, T0 + 2 * DAY, bal, species, decor)
        # 对照：从未回拨，直接离线 2 天
        clean = make_state(bal, species, [(1, "neon_tetra", 0.0)])
        after_clean, rep_b = settle_offline(clean, T0 + 2 * DAY, bal, species, decor)
        assert rep_a.coins_gained_milli == rep_b.coins_gained_milli
        assert after_rollback.to_dict() == after_clean.to_dict()

    def test_empty_tank(self, bal, species, decor):
        """空鱼缸：不崩、收益 0、水质只受过滤影响。"""
        st = make_state(bal, species, [])
        new, rep = settle_offline(st, T0 + 7 * DAY, bal, species, decor)
        assert rep.coins_gained_milli == 0
        assert new.fish_count() == 0
        assert math.isfinite(new.tank.water)
        assert bal.water_min() <= new.tank.water <= bal.water_max()

    def test_single_fish(self, bal, species, decor):
        """单条鱼：能正常产出。"""
        st = make_state(bal, species, [(1, "neon_tetra", 0.0)])
        _new, rep = settle_offline(st, T0 + 8 * HOUR, bal, species, decor)
        assert rep.coins_gained_milli > 0

    def test_full_tank_24_fish(self, bal, species, decor):
        """★ 24 条鱼满缸：不崩、不溢出、鱼数不变（繁殖被容量挡住）。"""
        ids = sorted(species.ids())
        specs = [(i + 1, ids[i % len(ids)], 100000.0) for i in range(24)]
        st = make_state(bal, species, specs)
        st.tank.capacity_level = 3   # capacity[3] == 24
        assert st.capacity(bal) == 24
        assert st.is_full(bal)
        new, rep = settle_offline(st, T0 + 3 * DAY, bal, species, decor)
        assert new.fish_count() == 24, "满缸时仍然繁殖出了鱼，突破了容量上限"
        assert rep.coins_gained_milli > 0
        assert isinstance(new.coins_milli, int)

    def test_ten_years_offline_does_not_hang_or_overflow(self, bal, species, decor):
        """★ 超大值（10 年 = hard_cap）：步数在保险丝内、数值有限、不为负。"""
        ten_years = 10 * 365 * DAY
        st = make_state(bal, species, [(1, "neon_tetra", 0.0), (2, "guppy", 0.0)])
        new, rep = settle_offline(st, T0 + ten_years, bal, species, decor)
        assert rep.steps < MAX_STEPS, "步数触到保险丝 %d，说明结算被截断" % MAX_STEPS
        assert rep.coins_gained_milli > 0
        assert new.coins_milli >= 0
        assert math.isfinite(new.tank.water)
        assert math.isfinite(new.tank.satiety)
        for f in new.fishes:
            assert math.isfinite(f.age_sec) and f.age_sec >= 0.0

    def test_beyond_hard_cap_is_capped_not_crashed(self, bal, species, decor):
        """超过 hard_cap（10 年）的离线被钳制，并如实标记 capped。"""
        st = make_state(bal, species, [(1, "neon_tetra", 0.0)])
        huge = bal.hard_cap_sec() + 100 * DAY
        _new, rep = settle_offline(st, T0 + huge, bal, species, decor)
        assert rep.capped is True
        assert rep.away_sec == bal.hard_cap_sec()
        assert rep.raw_away_sec == huge

    def test_one_second_offline(self, bal, species, decor):
        """离线 1 秒：单步、不报告（< MIN_REPORT_SEC）。"""
        st = make_state(bal, species, [(1, "neon_tetra", 0.0)])
        _new, rep = settle_offline(st, T0 + 1, bal, species, decor)
        assert rep.steps == 1
        assert rep.away_sec == 1
        assert rep.has_content() is False, "1 秒离线也弹卡片，违反 L6（不打扰）"


# ══════════════════════════════════════════════════════════════
#  A7  纯函数性 & 残留秒（多次短离线 vs 一次长离线）
# ══════════════════════════════════════════════════════════════

class TestPurityAndCarry:
    """settle_offline 不得修改入参；分段结算不得系统性吞收益。"""

    def test_settle_does_not_mutate_input_state(self, bal, species, decor):
        """★ 纯函数性：入参 state 必须**一个字节都没变**。"""
        st = make_state(bal, species, [(1, "neon_tetra", 0.0), (2, "guppy", 500.0)],
                        coins=7777)
        before = copy.deepcopy(st.to_dict())
        settle_offline(st, T0 + 3 * DAY, bal, species, decor)
        assert st.to_dict() == before, "settle_offline 污染了调用方的 state"

    def test_settle_is_deterministic_across_repeated_calls(self, bal, species, decor):
        """同一入参调 5 次，结果必须完全相同（无隐藏全局状态）。"""
        results = []
        for _ in range(5):
            st = make_state(bal, species, [(1, "neon_tetra", 0.0), (2, "guppy", 0.0)])
            new, rep = settle_offline(st, T0 + 2 * DAY, bal, species, decor)
            results.append((new.to_dict(), rep.to_dict()))
        for r in results[1:]:
            assert r == results[0]

    def test_chained_60s_settles_lose_nothing_vs_one_long_settle(
            self, bal, species, decor):
        """★ L2 关键：连续 10 次 60 秒结算 ≈ 一次 600 秒结算。

        步长边界对齐（都是 60s 细步、都在 8h 内 k=1.0），因此**不允许**有
        任何取整损耗；一旦实现里加了额外取整，这里会立刻变红。
        """
        chunk, times = 60, 10
        st = make_state(bal, species, [(1, "neon_tetra", 0.0), (2, "guppy", 0.0)])
        chained = st
        for i in range(times):
            chained, _ = settle_offline(chained, T0 + (i + 1) * chunk,
                                        bal, species, decor)
        one_shot = make_state(bal, species, [(1, "neon_tetra", 0.0), (2, "guppy", 0.0)])
        one_shot, _ = settle_offline(one_shot, T0 + chunk * times, bal, species, decor)
        assert chained.coins_milli == one_shot.coins_milli, (
            "分 %d 次结算得 %d 厘，一次性结算得 %d 厘 —— 分段结算在吞收益（违反 L2）"
            % (times, chained.coins_milli, one_shot.coins_milli))

    def test_chained_settles_never_lose_more_than_rounding(self, bal, species, decor):
        """★ 非对齐分段（每次 90 秒 × 8）的损耗必须 ≤ 每段 0.5 厘。"""
        chunk, times = 90, 8
        st = make_state(bal, species, [(1, "neon_tetra", 0.0)])
        chained = st
        for i in range(times):
            chained, _ = settle_offline(chained, T0 + (i + 1) * chunk,
                                        bal, species, decor)
        one = make_state(bal, species, [(1, "neon_tetra", 0.0)])
        one, _ = settle_offline(one, T0 + chunk * times, bal, species, decor)
        # 每次结算最多 2 步、每步最多差 0.5 厘
        budget = times * 2
        assert abs(chained.coins_milli - one.coins_milli) <= budget, (
            "非对齐分段损耗 %d 厘，超出取整预算 %d 厘"
            % (abs(chained.coins_milli - one.coins_milli), budget))

    def test_no_seconds_are_swallowed_by_the_anchor(self, bal, species, decor):
        """★ 锚点推进必须精确到秒：结算后 saved_at_utc == now，不留残秒。"""
        for away in (1, 7, 59, 61, 3599, DAY + 7):
            st = make_state(bal, species, [(1, "neon_tetra", 0.0)])
            new, _ = settle_offline(st, T0 + away, bal, species, decor)
            assert new.saved_at_utc == T0 + away


# ══════════════════════════════════════════════════════════════
#  A8  ★ 发现的问题：offline.py:272 使用了内置 round()
# ══════════════════════════════════════════════════════════════

class TestIronRuleNoBuiltinRound:
    """铁律：结算路径禁用 Python 内置 round（银行家舍入）。"""

    def test_upkeep_milli_uses_round_half_up_not_bankers(self, bal, species, decor):
        """★ BUG-01：`offline.advance_step` 第③段用了内置 `round()`。

        源码 fishtank/offline.py:272::

            out["upkeep_milli"] = int(round(... * (step_sec/60.0) * efficiency))

        内置 round 是银行家舍入：恰好 .5 时向偶数靠。C++ 端照抄
        `floor(x+0.5)` 会得到不同的 upkeep 数字，双端离线报告对不上。

        本用例构造 upkeep 恰好为 x.5 厘的一步来暴露方向差异。
        """
        from fishtank.economy import feeder_upkeep_rate_milli
        from fishtank.rng import DetRandom

        st = make_state(bal, species, [(1, "neon_tetra", 0.0), (2, "guppy", 0.0)])
        st.tank.feeder_owned = True
        st.tank.feeder_on = True
        rate = feeder_upkeep_rate_milli(st.fish_count(), bal)
        assert rate > 0

        # 让 rate * step/60 * k 恰好落在 2.5（内置 round → 2，正确应为 3）
        step = 2.5 * 60.0 / rate
        raw = rate * (step / 60.0)
        assert raw == pytest.approx(2.5, abs=1e-12), "构造失败，raw=%r" % raw

        out = off.advance_step(st, step, T0 + 1, bal, species, decor,
                               DetRandom(1), efficiency=1.0, offline=True,
                               do_breed=False)
        assert out["upkeep_milli"] == round_half_up(raw), (
            "upkeep_milli = %d，但 round_half_up(%.6f) = %d —— "
            "源码用了内置 round（银行家舍入），违反双端一致性铁律"
            % (out["upkeep_milli"], raw, round_half_up(raw)))

    def test_no_bare_round_in_settlement_modules(self):
        """★ 静态守门：结算路径的源码里不得出现裸 `round(`。

        白名单：`round_half_up` 自身的文档字符串。
        """
        import ast
        import os

        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        targets = [
            os.path.join(root, "fishtank", "offline.py"),
            os.path.join(root, "fishtank", "economy.py"),
            os.path.join(root, "fishtank", "systems", "income.py"),
            os.path.join(root, "fishtank", "systems", "growth.py"),
            os.path.join(root, "fishtank", "systems", "water.py"),
            os.path.join(root, "fishtank", "systems", "feeder.py"),
        ]
        offenders = []
        for path in targets:
            if not os.path.isfile(path):
                continue
            with open(path, "r", encoding="utf-8") as f:
                src = f.read()
            tree = ast.parse(src, filename=path)
            for node in ast.walk(tree):
                if (isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Name)
                        and node.func.id == "round"):
                    offenders.append("%s:%d" % (os.path.basename(path), node.lineno))
        assert not offenders, (
            "结算路径出现内置 round() 调用：%s —— 必须改用 round_half_up()"
            % ", ".join(offenders))
