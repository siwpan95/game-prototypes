"""T03 行为树测试。

覆盖：AIConfig 烘焙、五条分支的优先级、E14（一鱼一树）、
黑板输出契约、确定性、异常容错。
"""

import math

import pytest

from fishtank.behaviors import (
    AIConfig, act_idle, act_push_inward, act_seek_food, act_wander,
    build_fish_tree, cond_has_food, cond_has_interest, cond_is_idling,
    cond_near_edge, describe_tree,
)
from fishtank.constants import (
    AI_AVOID_EDGE, AI_IDLE, AI_SEEK_FOOD, AI_SEEK_POINT, AI_WANDER,
    BB_ATTRACT, BB_CFG, BB_DT, BB_FOOD_X, BB_FOOD_Y, BB_HAS_FOOD,
    BB_HAS_INTEREST, BB_HAS_SCHOOL, BB_IDLE_LEFT, BB_INTEREST_X, BB_INTEREST_Y,
    BB_LAYER_Y, BB_NX, BB_NY, BB_RETARGET_LEFT, BB_SCHOOL_X, BB_SCHOOL_Y,
    BB_SPEED_MUL, BB_STATE, BB_TAIL_MUL, BB_TARGET_X, BB_TARGET_Y,
)
from fishtank.engine_bootstrap import Status
from fishtank.rng import DetRandom


# ══════════════════════════════════════════════════════════════
#  AIConfig
# ══════════════════════════════════════════════════════════════

def test_ai_config_from_balance(bal):
    """所有字段都必须从 balance.json 读到，不能落在硬编码默认值上。"""
    cfg = AIConfig.from_balance(bal)
    assert cfg.speed == bal.get("ai.speed")
    assert cfg.tail_hz == bal.get("ai.tail_hz")
    assert cfg.turn_rate == pytest.approx(bal.get("ai.turn_rate"))
    assert cfg.idle_lo == pytest.approx(bal.get("ai.idle_sec")[0])
    assert cfg.idle_hi == pytest.approx(bal.get("ai.idle_sec")[1])
    assert cfg.retarget_lo == pytest.approx(bal.get("ai.wander_retarget_sec")[0])
    assert cfg.x_min == pytest.approx(bal.get("ai.bounds.x_min"))
    assert cfg.y_max == pytest.approx(bal.get("ai.bounds.y_max"))


def test_ai_config_speed_lookup(bal):
    """未知游速档回退到 normal，不抛异常。"""
    cfg = AIConfig.from_balance(bal)
    assert cfg.speed_of("slow") < cfg.speed_of("normal") < cfg.speed_of("fast")
    assert cfg.speed_of("no_such_key") == cfg.speed_of("normal")
    assert cfg.tail_hz_of("no_such_key") == cfg.tail_hz_of("normal")


def test_ai_config_layer_mapping(bal):
    """水层字符串（含组合写法）都能映射到 [0,1] 内。"""
    cfg = AIConfig.from_balance(bal)
    assert cfg.layer_of("底") > cfg.layer_of("中") > cfg.layer_of("上")
    mid = cfg.layer_of("中上")          # 组合 → 取平均
    assert cfg.layer_of("上") <= mid <= cfg.layer_of("中")
    assert 0.0 <= cfg.layer_of("") <= 1.0
    assert 0.0 <= cfg.layer_of("不存在的水层") <= 1.0


def test_ai_config_attract(bal):
    """群游倾向：高 > 中 > 低，未知返回 0。"""
    cfg = AIConfig.from_balance(bal)
    assert cfg.attract_of("高") > cfg.attract_of("中") >= cfg.attract_of("低")
    assert cfg.attract_of("???") == 0.0


def test_ai_config_bounds_and_center(bal):
    """bounds/center 返回合法区间。"""
    cfg = AIConfig.from_balance(bal)
    x0, x1, y0, y1 = cfg.bounds()
    assert x0 < x1 and y0 < y1
    cx, cy = cfg.center()
    assert x0 <= cx <= x1 and y0 <= cy <= y1


# ══════════════════════════════════════════════════════════════
#  E14：一鱼一树
# ══════════════════════════════════════════════════════════════

def test_e14_each_fish_has_own_tree(bal):
    """两条鱼的树对象、根节点、黑板都必须互不相同。"""
    cfg = AIConfig.from_balance(bal)
    t1 = build_fish_tree(1, cfg, DetRandom(1))
    t2 = build_fish_tree(2, cfg, DetRandom(1))
    assert t1 is not t2
    assert t1.root is not t2.root
    assert t1.blackboard is not t2.blackboard
    # 节点也不能共享（否则 RUNNING 状态会串味）
    assert t1.root.children[0] is not t2.root.children[0]


def test_e14_blackboard_isolated(bal):
    """改一条鱼的黑板不影响另一条。"""
    cfg = AIConfig.from_balance(bal)
    t1 = build_fish_tree(1, cfg, DetRandom(7))
    t2 = build_fish_tree(2, cfg, DetRandom(7))
    t1.blackboard.set(BB_NX, 0.111)
    assert t2.blackboard.get(BB_NX) != 0.111


def test_tree_shape(bal):
    """树的形状固定为 5 条分支，顺序即优先级。"""
    cfg = AIConfig.from_balance(bal)
    tree = build_fish_tree(1, cfg, DetRandom(1))
    names = [c.name for c in tree.root.children]
    assert names == ["edge", "food", "point", "idle", "wander"]
    text = describe_tree(tree)
    assert "Selector(fish_root)" in text
    assert "Action(wander)" in text


# ══════════════════════════════════════════════════════════════
#  条件节点
# ══════════════════════════════════════════════════════════════

class _Ctx(object):
    """最小 TickContext 替身。"""

    def __init__(self, bb):
        self.blackboard = bb


def _fresh(bal, x=0.5, y=0.5, seed=42):
    """造一棵树并把鱼放在指定位置。"""
    cfg = AIConfig.from_balance(bal)
    tree = build_fish_tree(1, cfg, DetRandom(seed), x=x, y=y)
    bb = tree.blackboard
    bb.set(BB_NX, x)
    bb.set(BB_NY, y)
    return cfg, tree, bb


@pytest.mark.parametrize("x,y,expect", [
    (0.5, 0.5, False),      # 正中间
    (0.05, 0.5, True),      # 贴左壁
    (0.95, 0.5, True),      # 贴右壁
    (0.5, 0.08, True),      # 贴水面
    (0.5, 0.94, True),      # 贴缸底
])
def test_cond_near_edge(bal, x, y, expect):
    """贴边判定覆盖四条边与中心。"""
    _cfg, _tree, bb = _fresh(bal, x, y)
    assert cond_near_edge(_Ctx(bb)) is expect


def test_cond_missing_cfg_returns_false(bal):
    """黑板里没有 cfg 时条件返回 False 而不是抛异常（容错原则）。"""
    _cfg, _tree, bb = _fresh(bal)
    bb.set(BB_CFG, None)
    assert cond_near_edge(_Ctx(bb)) is False
    assert act_push_inward(_Ctx(bb)) is False
    assert act_seek_food(_Ctx(bb)) is False
    assert act_idle(_Ctx(bb)) is False
    assert act_wander(_Ctx(bb)) is False


def test_cond_food_and_interest_and_idle(bal):
    """三个布尔条件的读取。"""
    _cfg, _tree, bb = _fresh(bal)
    assert cond_has_food(_Ctx(bb)) is False
    bb.set(BB_HAS_FOOD, True)
    assert cond_has_food(_Ctx(bb)) is True

    assert cond_has_interest(_Ctx(bb)) is False
    bb.set(BB_HAS_INTEREST, True)
    assert cond_has_interest(_Ctx(bb)) is True

    assert cond_is_idling(_Ctx(bb)) is False
    bb.set(BB_IDLE_LEFT, 1.0)
    assert cond_is_idling(_Ctx(bb)) is True


# ══════════════════════════════════════════════════════════════
#  分支优先级（整棵树 tick）
# ══════════════════════════════════════════════════════════════

def test_branch_wander_default(bal):
    """什么都没有时走兜底巡游。"""
    _cfg, tree, bb = _fresh(bal)
    bb.set(BB_DT, 0.05)
    assert tree.tick() is Status.SUCCESS
    assert bb.get(BB_STATE) == AI_WANDER
    assert bb.get(BB_SPEED_MUL) == 1.0


def test_branch_edge_beats_everything(bal):
    """贴边优先级最高：即使有鱼食也先脱离边缘。"""
    cfg, tree, bb = _fresh(bal, x=cfgless_x(bal), y=0.5)
    bb.set(BB_DT, 0.05)
    bb.set(BB_HAS_FOOD, True)
    bb.set(BB_FOOD_X, 0.02)
    bb.set(BB_FOOD_Y, 0.5)
    bb.set(BB_HAS_INTEREST, True)
    tree.tick()
    assert bb.get(BB_STATE) == AI_AVOID_EDGE
    # 目标点被推向缸内
    assert bb.get(BB_TARGET_X) > bb.get(BB_NX)
    assert cfg.x_min <= bb.get(BB_TARGET_X) <= cfg.x_max


def cfgless_x(bal):
    """返回一个必然贴左壁的 x。"""
    return float(bal.get("ai.bounds.x_min"))


def test_branch_food_beats_interest_and_idle(bal):
    """鱼食优先于兴趣点与发呆，并且提速。"""
    cfg, tree, bb = _fresh(bal)
    bb.set(BB_DT, 0.05)
    bb.set(BB_IDLE_LEFT, 5.0)
    bb.set(BB_HAS_INTEREST, True)
    bb.set(BB_INTEREST_X, 0.9)
    bb.set(BB_INTEREST_Y, 0.9)
    bb.set(BB_HAS_FOOD, True)
    bb.set(BB_FOOD_X, 0.3)
    bb.set(BB_FOOD_Y, 0.2)
    tree.tick()
    assert bb.get(BB_STATE) == AI_SEEK_FOOD
    assert bb.get(BB_TARGET_X) == pytest.approx(0.3)
    assert bb.get(BB_TARGET_Y) == pytest.approx(0.2)
    assert bb.get(BB_SPEED_MUL) == pytest.approx(cfg.food_speed_mul)
    assert bb.get(BB_TAIL_MUL) == pytest.approx(cfg.food_tail_mul)
    assert bb.get(BB_IDLE_LEFT) == 0.0     # 有食物就不发呆了


def test_branch_interest_beats_idle(bal):
    """兴趣点优先于发呆，但速度不加成。"""
    _cfg, tree, bb = _fresh(bal)
    bb.set(BB_DT, 0.05)
    bb.set(BB_IDLE_LEFT, 5.0)
    bb.set(BB_HAS_INTEREST, True)
    bb.set(BB_INTEREST_X, 0.7)
    bb.set(BB_INTEREST_Y, 0.3)
    tree.tick()
    assert bb.get(BB_STATE) == AI_SEEK_POINT
    assert bb.get(BB_TARGET_X) == pytest.approx(0.7)
    assert bb.get(BB_SPEED_MUL) == 1.0


def test_branch_idle_counts_down_and_expires(bal):
    """发呆会随 dt 递减，减到 0 后自动回到巡游。"""
    cfg, tree, bb = _fresh(bal)
    bb.set(BB_DT, 0.5)
    bb.set(BB_IDLE_LEFT, 1.0)
    tree.tick()
    assert bb.get(BB_STATE) == AI_IDLE
    assert bb.get(BB_IDLE_LEFT) == pytest.approx(0.5)
    assert bb.get(BB_SPEED_MUL) == pytest.approx(cfg.idle_speed_mul)
    tree.tick()
    assert bb.get(BB_IDLE_LEFT) == 0.0
    tree.tick()
    assert bb.get(BB_STATE) in (AI_WANDER, AI_IDLE)


def test_idle_target_locks_position(bal):
    """发呆时目标点锁在当前位置（所以速度会收敛到 0）。"""
    _cfg, tree, bb = _fresh(bal, x=0.42, y=0.37)
    bb.set(BB_DT, 0.1)
    bb.set(BB_IDLE_LEFT, 2.0)
    tree.tick()
    assert bb.get(BB_TARGET_X) == pytest.approx(0.42)
    assert bb.get(BB_TARGET_Y) == pytest.approx(0.37)


# ══════════════════════════════════════════════════════════════
#  巡游细节
# ══════════════════════════════════════════════════════════════

def test_wander_retarget_on_timeout(bal):
    """重选计时器归零后必定换目标。"""
    _cfg, tree, bb = _fresh(bal)
    bb.set(BB_DT, 0.0)
    bb.set(BB_RETARGET_LEFT, 0.0)
    old = (bb.get(BB_TARGET_X), bb.get(BB_TARGET_Y))
    tree.tick()
    new = (bb.get(BB_TARGET_X), bb.get(BB_TARGET_Y))
    assert new != old
    assert bb.get(BB_RETARGET_LEFT) > 0.0


def test_wander_target_always_in_bounds(bal):
    """连续 500 次重选，目标点始终在活动区内。"""
    cfg, tree, bb = _fresh(bal)
    bb.set(BB_DT, 0.0)
    for _ in range(500):
        bb.set(BB_RETARGET_LEFT, 0.0)
        bb.set(BB_IDLE_LEFT, 0.0)
        tree.tick()
        assert cfg.x_min <= bb.get(BB_TARGET_X) <= cfg.x_max
        assert cfg.y_min <= bb.get(BB_TARGET_Y) <= cfg.y_max


def test_wander_respects_layer_bias(bal):
    """常驻水层会把巡游目标整体往该水层拉。"""
    cfg = AIConfig.from_balance(bal)
    if cfg.layer_bias <= 0.0:
        pytest.skip("layer_bias 配成 0，本用例无意义")

    def mean_ty(layer):
        tree = build_fish_tree(1, cfg, DetRandom(2024), layer_y=layer)
        bb = tree.blackboard
        bb.set(BB_LAYER_Y, layer)
        bb.set(BB_DT, 0.0)
        total = 0.0
        n = 300
        for _ in range(n):
            bb.set(BB_RETARGET_LEFT, 0.0)
            bb.set(BB_IDLE_LEFT, 0.0)
            tree.tick()
            total += bb.get(BB_TARGET_Y)
        return total / n

    top = mean_ty(cfg.layer_of("上"))
    bottom = mean_ty(cfg.layer_of("底"))
    assert top < bottom


def test_wander_respects_school(bal):
    """群游倾向 > 0 且有鱼群中心时，目标点会被拉向中心。"""
    cfg = AIConfig.from_balance(bal)
    attract = cfg.attract_of("高")
    if attract <= 0.0:
        pytest.skip("school_attract.高 配成 0，本用例无意义")

    def mean_tx(has_school):
        tree = build_fish_tree(1, cfg, DetRandom(999), attract=attract)
        bb = tree.blackboard
        bb.set(BB_ATTRACT, attract)
        bb.set(BB_HAS_SCHOOL, has_school)
        bb.set(BB_SCHOOL_X, cfg.x_max)
        bb.set(BB_SCHOOL_Y, 0.5)
        bb.set(BB_DT, 0.0)
        total = 0.0
        n = 300
        for _ in range(n):
            bb.set(BB_RETARGET_LEFT, 0.0)
            bb.set(BB_IDLE_LEFT, 0.0)
            tree.tick()
            total += bb.get(BB_TARGET_X)
        return total / n

    assert mean_tx(True) > mean_tx(False)


def test_wander_can_enter_idle(bal):
    """巡游过程中按 idle_chance 概率转入发呆（1000 次内必然出现一次）。"""
    cfg, tree, bb = _fresh(bal, seed=5)
    if cfg.idle_chance <= 0.0:
        pytest.skip("idle_chance 配成 0")
    bb.set(BB_DT, 0.0)
    seen_idle = False
    for _ in range(1000):
        bb.set(BB_RETARGET_LEFT, 0.0)
        tree.tick()
        if bb.get(BB_STATE) == AI_IDLE or bb.get(BB_IDLE_LEFT) > 0.0:
            seen_idle = True
            break
    assert seen_idle


# ══════════════════════════════════════════════════════════════
#  确定性
# ══════════════════════════════════════════════════════════════

def test_deterministic_same_seed(bal):
    """相同种子 → 完全相同的目标点序列（双端复现的基础）。"""
    cfg = AIConfig.from_balance(bal)

    def run(seed):
        tree = build_fish_tree(1, cfg, DetRandom(seed))
        bb = tree.blackboard
        bb.set(BB_DT, 0.05)
        out = []
        for _ in range(60):
            bb.set(BB_RETARGET_LEFT, 0.0)
            tree.tick()
            out.append((round(bb.get(BB_TARGET_X), 9), round(bb.get(BB_TARGET_Y), 9)))
        return out

    assert run(12345) == run(12345)
    assert run(12345) != run(54321)


def test_tick_never_raises_on_garbage(bal):
    """黑板被塞进垃圾值时，tick 不允许抛异常（准则：绝不崩）。"""
    _cfg, tree, bb = _fresh(bal)
    for key in (BB_NX, BB_NY, BB_DT, BB_TARGET_X, BB_TARGET_Y, BB_IDLE_LEFT):
        bb.set(key, "garbage")
    status = tree.tick()
    assert status in (Status.SUCCESS, Status.FAILURE, Status.RUNNING)


def test_outputs_are_finite(bal):
    """连跑 2000 tick，输出全部是有限数（不会 NaN/inf）。"""
    cfg, tree, bb = _fresh(bal)
    bb.set(BB_DT, 1.0 / 20.0)
    for i in range(2000):
        # 模拟鱼在缸里游动
        bb.set(BB_NX, cfg.x_min + (cfg.x_max - cfg.x_min) * ((i % 100) / 100.0))
        bb.set(BB_NY, cfg.y_min + (cfg.y_max - cfg.y_min) * ((i % 37) / 37.0))
        tree.tick()
        for key in (BB_TARGET_X, BB_TARGET_Y, BB_SPEED_MUL, BB_TAIL_MUL):
            v = float(bb.get(key))
            assert math.isfinite(v)
