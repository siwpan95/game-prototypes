"""行为树：鱼的游动决策。

🔴 禁止 `from __future__ import annotations`（E6）。
🔴 E14：行为树节点会保存 RUNNING 状态，**绝不能多条鱼共用一棵树**。
   :func:`build_fish_tree` 每次调用都新建一整棵树 + 一块独立黑板。
🔴 零硬编码：所有阈值/速度/概率都来自 :class:`AIConfig`（从 balance.json 烘焙）。

树的形状（Selector 短路，从上到下即优先级）::

    Selector "fish_root"
      ├─ Sequence "edge"    : 靠边?     → 向内推          (state=avoid_edge)
      ├─ Sequence "food"    : 有鱼食?   → 冲向鱼食        (state=seek_food)
      ├─ Sequence "point"   : 有兴趣点? → 游向兴趣点      (state=seek_point)
      ├─ Sequence "idle"    : 发呆中?   → 原地摆尾        (state=idle)
      └─ Action   "wander"  : 兜底随机巡游 / 择机转入发呆 (state=wander)

行为树**只写黑板**（目标点 / 速度倍率 / 尾摆倍率 / 状态标签），
真正的位移积分由 :class:`~fishtank.systems.movement.MovementSystem` 完成。
这样"决策"与"运动"解耦，C++ 端可以只照抄运动部分。
"""

import math
from dataclasses import dataclass, field

from fishtank.constants import (
    AI_AVOID_EDGE, AI_IDLE, AI_SEEK_FOOD, AI_SEEK_POINT, AI_WANDER,
    BB_ATTRACT, BB_BASE_SPEED, BB_CFG, BB_DT, BB_FOOD_X, BB_FOOD_Y,
    BB_HAS_FOOD, BB_HAS_INTEREST, BB_HAS_SCHOOL, BB_HEADING, BB_IDLE_LEFT,
    BB_INTEREST_X, BB_INTEREST_Y, BB_LAYER_Y, BB_NOW, BB_NX, BB_NY, BB_RETARGET_LEFT,
    BB_RNG, BB_SCHOOL_X, BB_SCHOOL_Y, BB_SPEED_MUL, BB_STATE, BB_TAIL_HZ,
    BB_TAIL_MUL, BB_TARGET_X, BB_TARGET_Y, BB_UID, SPEED_NORMAL,
)
from fishtank.engine_bootstrap import (
    Action, BehaviorTree, Blackboard, Condition, Selector, Sequence,
)

_NEUTRAL_MUL = 1.0
"""中性倍率。不是玩法数值 —— 表示"不做任何缩放"。"""


# ══════════════════════════════════════════════════════════════
#  AI 配置（一次性从 balance.json 烘焙，避免每帧点号查表）
# ══════════════════════════════════════════════════════════════

def _as_float(v, default):
    """宽松转 float。"""
    try:
        if v is None:
            return default
        return float(v)
    except (TypeError, ValueError):
        return default


def _pair(bal, path, lo_default, hi_default):
    """读一个 [lo, hi] 区间配置；缺失或格式不对时回退默认。"""
    raw = bal.get(path)
    if isinstance(raw, (list, tuple)) and len(raw) >= 2:
        lo = _as_float(raw[0], lo_default)
        hi = _as_float(raw[1], hi_default)
        if hi < lo:
            lo, hi = hi, lo
        return lo, hi
    return lo_default, hi_default


def _table(bal, path):
    """读一个 dict 表；缺失返回空 dict。"""
    raw = bal.get(path)
    return dict(raw) if isinstance(raw, dict) else {}


@dataclass
class AIConfig:
    """`balance.json` 的 ``ai`` 段烘焙结果。

    只读；由 :meth:`from_balance` 构造一次，随后放进 World 数据与每条鱼的黑板。
    """

    speed: dict = field(default_factory=dict)
    tail_hz: dict = field(default_factory=dict)
    layer_y: dict = field(default_factory=dict)
    school_attract: dict = field(default_factory=dict)
    turn_rate: float = 2.2
    idle_chance: float = 0.06
    idle_lo: float = 1.5
    idle_hi: float = 4.0
    edge_margin: float = 0.08
    edge_push: float = 1.4
    food_speed_mul: float = 1.8
    food_tail_mul: float = 2.0
    idle_speed_mul: float = 0.15
    idle_tail_mul: float = 0.5
    retarget_lo: float = 2.5
    retarget_hi: float = 6.5
    arrive_radius: float = 0.035
    food_life_sec: float = 12.0
    interest_life_sec: float = 3.0
    layer_bias: float = 0.3
    school_radius: float = 0.32
    x_min: float = 0.05
    x_max: float = 0.95
    y_min: float = 0.08
    y_max: float = 0.94

    @classmethod
    def from_balance(cls, bal):
        """从 :class:`~fishtank.data_defs.BalanceTable` 烘焙。

        :param bal: 平衡表
        :returns: AIConfig
        """
        idle_lo, idle_hi = _pair(bal, "ai.idle_sec", 1.5, 4.0)
        re_lo, re_hi = _pair(bal, "ai.wander_retarget_sec", 2.5, 6.5)
        return cls(
            speed=_table(bal, "ai.speed"),
            tail_hz=_table(bal, "ai.tail_hz"),
            layer_y=_table(bal, "ai.layer_y"),
            school_attract=_table(bal, "ai.school_attract"),
            turn_rate=_as_float(bal.get("ai.turn_rate"), 2.2),
            idle_chance=_as_float(bal.get("ai.idle_chance"), 0.06),
            idle_lo=idle_lo, idle_hi=idle_hi,
            edge_margin=_as_float(bal.get("ai.edge_margin"), 0.08),
            edge_push=_as_float(bal.get("ai.edge_push"), 1.4),
            food_speed_mul=_as_float(bal.get("ai.food_speed_mul"), 1.8),
            food_tail_mul=_as_float(bal.get("ai.food_tail_mul"), 2.0),
            idle_speed_mul=_as_float(bal.get("ai.idle_speed_mul"), 0.15),
            idle_tail_mul=_as_float(bal.get("ai.idle_tail_mul"), 0.5),
            retarget_lo=re_lo, retarget_hi=re_hi,
            arrive_radius=_as_float(bal.get("ai.arrive_radius"), 0.035),
            food_life_sec=_as_float(bal.get("ai.food_life_sec"), 12.0),
            interest_life_sec=_as_float(bal.get("ai.interest_life_sec"), 3.0),
            layer_bias=_as_float(bal.get("ai.layer_bias"), 0.3),
            school_radius=_as_float(bal.get("ai.school_radius"), 0.32),
            x_min=_as_float(bal.get("ai.bounds.x_min"), 0.05),
            x_max=_as_float(bal.get("ai.bounds.x_max"), 0.95),
            y_min=_as_float(bal.get("ai.bounds.y_min"), 0.08),
            y_max=_as_float(bal.get("ai.bounds.y_max"), 0.94),
        )

    # ── 按鱼种取值 ──

    def speed_of(self, key):
        """某游速档的基础速度（归一化单位/秒）。未知档回退 normal。"""
        default = _as_float(self.speed.get(SPEED_NORMAL), 0.018)
        return _as_float(self.speed.get(str(key)), default)

    def tail_hz_of(self, key):
        """某游速档的摆尾频率（Hz）。"""
        default = _as_float(self.tail_hz.get(SPEED_NORMAL), 1.8)
        return _as_float(self.tail_hz.get(str(key)), default)

    def layer_of(self, key):
        """把鱼种的水层描述映射成归一化 y。

        鱼种数据里的 layer 可能是 "底" / "中" / "上"，也可能是 "中上" 这类组合，
        所以这里做**子串匹配求平均**，任何情况下都返回 [0,1] 内的一个值。
        """
        key = str(key)
        hits = [_as_float(v, 0.5) for k, v in sorted(self.layer_y.items()) if k and k in key]
        if not hits:
            exact = self.layer_y.get(key)
            if exact is not None:
                return _as_float(exact, 0.5)
            return (self.y_min + self.y_max) * 0.5
        return sum(hits) / float(len(hits))

    def attract_of(self, key):
        """群游倾向强度（0 = 不群游）。"""
        return _as_float(self.school_attract.get(str(key)), 0.0)

    def bounds(self):
        """返回 (x_min, x_max, y_min, y_max)。"""
        return (self.x_min, self.x_max, self.y_min, self.y_max)

    def center(self):
        """返回活动区域中心点。"""
        return ((self.x_min + self.x_max) * 0.5, (self.y_min + self.y_max) * 0.5)


# ══════════════════════════════════════════════════════════════
#  小工具
# ══════════════════════════════════════════════════════════════

# 直接复用 fishtank.economy 的 clamp（含 hi<lo 自动交换防御逻辑）
from fishtank.economy import clamp as _clamp


def _dist(ax, ay, bx, by):
    """两点距离。"""
    return math.hypot(float(ax) - float(bx), float(ay) - float(by))


def _set_output(bb, state, speed_mul, tail_mul):
    """统一写出行为树的三个输出（状态标签 / 速度倍率 / 尾摆倍率）。"""
    bb.set(BB_STATE, state)
    bb.set(BB_SPEED_MUL, float(speed_mul))
    bb.set(BB_TAIL_MUL, float(tail_mul))


def _pick_wander_target(bb, cfg, rng):
    """挑一个新的巡游目标点：随机点 → 向常驻水层收拢 → 向鱼群收拢。

    三步都是**线性插值**，没有分支，双端复现容易。
    """
    tx = rng.uniform(cfg.x_min, cfg.x_max)
    ty = rng.uniform(cfg.y_min, cfg.y_max)

    # ① 向该鱼种的常驻水层收拢
    layer = float(bb.get(BB_LAYER_Y, (cfg.y_min + cfg.y_max) * 0.5))
    bias = _clamp(cfg.layer_bias, 0.0, 1.0)
    ty = ty * (1.0 - bias) + layer * bias

    # ② 向同族鱼群收拢（群游倾向为 0 的鱼这一步是恒等变换）
    attract = _clamp(float(bb.get(BB_ATTRACT, 0.0)), 0.0, 1.0)
    if attract > 0.0 and bb.get(BB_HAS_SCHOOL, False):
        sx = float(bb.get(BB_SCHOOL_X, tx))
        sy = float(bb.get(BB_SCHOOL_Y, ty))
        tx = tx * (1.0 - attract) + sx * attract
        ty = ty * (1.0 - attract) + sy * attract

    bb.set(BB_TARGET_X, _clamp(tx, cfg.x_min, cfg.x_max))
    bb.set(BB_TARGET_Y, _clamp(ty, cfg.y_min, cfg.y_max))


# ══════════════════════════════════════════════════════════════
#  条件节点
# ══════════════════════════════════════════════════════════════

def cond_near_edge(ctx):
    """是否已经贴到活动区边缘（含安全余量）。"""
    bb = ctx.blackboard
    cfg = bb.get(BB_CFG)
    if cfg is None:
        return False
    x = float(bb.get(BB_NX, 0.5))
    y = float(bb.get(BB_NY, 0.5))
    m = cfg.edge_margin
    return (x < cfg.x_min + m or x > cfg.x_max - m
            or y < cfg.y_min + m or y > cfg.y_max - m)


def cond_has_food(ctx):
    """视野里是否有鱼食。"""
    return bool(ctx.blackboard.get(BB_HAS_FOOD, False))


def cond_has_interest(ctx):
    """是否有玩家兴趣点（点击缸壁 / 鼠标停留）。"""
    return bool(ctx.blackboard.get(BB_HAS_INTEREST, False))


def cond_is_idling(ctx):
    """是否正在发呆倒计时中。"""
    return float(ctx.blackboard.get(BB_IDLE_LEFT, 0.0)) > 0.0


# ══════════════════════════════════════════════════════════════
#  动作节点
# ══════════════════════════════════════════════════════════════

def act_push_inward(ctx):
    """贴边时把目标点设到"向内推一段"的位置。

    只改目标点，不直接改位置 —— 位移仍由 MovementSystem 平滑完成，
    所以视觉上是"缓缓掉头"而不是"瞬间弹开"。
    """
    bb = ctx.blackboard
    cfg = bb.get(BB_CFG)
    if cfg is None:
        return False
    x = float(bb.get(BB_NX, 0.5))
    y = float(bb.get(BB_NY, 0.5))
    m = cfg.edge_margin
    push = m * cfg.edge_push

    dx = 0.0
    if x < cfg.x_min + m:
        dx = 1.0
    elif x > cfg.x_max - m:
        dx = -1.0
    dy = 0.0
    if y < cfg.y_min + m:
        dy = 1.0
    elif y > cfg.y_max - m:
        dy = -1.0
    if dx == 0.0 and dy == 0.0:
        return False

    bb.set(BB_TARGET_X, _clamp(x + dx * push, cfg.x_min, cfg.x_max))
    bb.set(BB_TARGET_Y, _clamp(y + dy * push, cfg.y_min, cfg.y_max))
    bb.set(BB_RETARGET_LEFT, 0.0)   # 脱离边缘后立刻重新挑巡游点
    bb.set(BB_IDLE_LEFT, 0.0)       # 贴边时不发呆
    _set_output(bb, AI_AVOID_EDGE, _NEUTRAL_MUL, _NEUTRAL_MUL)
    return True


def act_seek_food(ctx):
    """冲向鱼食：目标点 = 鱼食位置，速度与尾摆都提速。"""
    bb = ctx.blackboard
    cfg = bb.get(BB_CFG)
    if cfg is None:
        return False
    bb.set(BB_TARGET_X, _clamp(float(bb.get(BB_FOOD_X, 0.5)), cfg.x_min, cfg.x_max))
    bb.set(BB_TARGET_Y, _clamp(float(bb.get(BB_FOOD_Y, 0.5)), cfg.y_min, cfg.y_max))
    bb.set(BB_IDLE_LEFT, 0.0)
    bb.set(BB_RETARGET_LEFT, 0.0)
    _set_output(bb, AI_SEEK_FOOD, cfg.food_speed_mul, cfg.food_tail_mul)
    return True


def act_seek_interest(ctx):
    """游向玩家兴趣点（速度不加成 —— 只是好奇，不是抢食）。"""
    bb = ctx.blackboard
    cfg = bb.get(BB_CFG)
    if cfg is None:
        return False
    bb.set(BB_TARGET_X, _clamp(float(bb.get(BB_INTEREST_X, 0.5)), cfg.x_min, cfg.x_max))
    bb.set(BB_TARGET_Y, _clamp(float(bb.get(BB_INTEREST_Y, 0.5)), cfg.y_min, cfg.y_max))
    bb.set(BB_IDLE_LEFT, 0.0)
    bb.set(BB_RETARGET_LEFT, 0.0)
    _set_output(bb, AI_SEEK_POINT, _NEUTRAL_MUL, _NEUTRAL_MUL)
    return True


def act_idle(ctx):
    """原地发呆：目标点锁在当前位置，速度与尾摆降下来。"""
    bb = ctx.blackboard
    cfg = bb.get(BB_CFG)
    if cfg is None:
        return False
    left = float(bb.get(BB_IDLE_LEFT, 0.0)) - float(bb.get(BB_DT, 0.0))
    bb.set(BB_IDLE_LEFT, max(0.0, left))
    bb.set(BB_TARGET_X, float(bb.get(BB_NX, 0.5)))
    bb.set(BB_TARGET_Y, float(bb.get(BB_NY, 0.5)))
    _set_output(bb, AI_IDLE, cfg.idle_speed_mul, cfg.idle_tail_mul)
    return True


def act_wander(ctx):
    """兜底巡游：到点或超时就换一个新目标，并按概率转入发呆。"""
    bb = ctx.blackboard
    cfg = bb.get(BB_CFG)
    rng = bb.get(BB_RNG)
    if cfg is None or rng is None:
        return False

    dt = float(bb.get(BB_DT, 0.0))
    x = float(bb.get(BB_NX, 0.5))
    y = float(bb.get(BB_NY, 0.5))
    tx = float(bb.get(BB_TARGET_X, x))
    ty = float(bb.get(BB_TARGET_Y, y))

    left = float(bb.get(BB_RETARGET_LEFT, 0.0)) - dt
    arrived = _dist(x, y, tx, ty) <= cfg.arrive_radius
    if left <= 0.0 or arrived:
        # 🔴 随机消耗顺序固定：先抽是否发呆，再抽目标点，最后抽下次重选时间。
        if rng.chance(cfg.idle_chance):
            bb.set(BB_IDLE_LEFT, rng.uniform(cfg.idle_lo, cfg.idle_hi))
        _pick_wander_target(bb, cfg, rng)
        left = rng.uniform(cfg.retarget_lo, cfg.retarget_hi)
    bb.set(BB_RETARGET_LEFT, left)
    _set_output(bb, AI_WANDER, _NEUTRAL_MUL, _NEUTRAL_MUL)
    return True


# ══════════════════════════════════════════════════════════════
#  构建
# ══════════════════════════════════════════════════════════════

def build_fish_tree(uid, cfg, rng, x=0.5, y=0.5, heading=1.0,
                    base_speed=0.018, tail_hz=1.8, layer_y=0.5, attract=0.0,
                    now=0):
    """★ 为**一条**鱼构建独立的行为树。

    🔴 E14：每条鱼一棵树 —— 节点内部保存 RUNNING 状态，共用会串味。

    :param uid: 鱼的 uid（写进黑板，便于调试）
    :param cfg: :class:`AIConfig`
    :param rng: 表现层随机源（:class:`~fishtank.rng.DetRandom`，**不是**玩法随机流）
    :param x: 初始归一化 x
    :param y: 初始归一化 y
    :param heading: 初始朝向 ±1
    :param base_speed: 该鱼种的基础速度
    :param tail_hz: 该鱼种的摆尾频率
    :param layer_y: 该鱼种的常驻水层 y
    :param attract: 群游倾向强度
    :param now: 当前 UTC 秒
    :returns: :class:`BehaviorTree`（黑板已初始化并绑定）
    """
    bb = Blackboard({
        BB_UID: int(uid),
        BB_CFG: cfg,
        BB_RNG: rng,
        BB_DT: 0.0,
        BB_NOW: int(now),
        BB_NX: float(x),
        BB_NY: float(y),
        BB_HEADING: float(heading),
        BB_TARGET_X: float(x),
        BB_TARGET_Y: float(y),
        BB_STATE: AI_WANDER,
        BB_SPEED_MUL: _NEUTRAL_MUL,
        BB_TAIL_MUL: _NEUTRAL_MUL,
        BB_BASE_SPEED: float(base_speed),
        BB_TAIL_HZ: float(tail_hz),
        BB_LAYER_Y: float(layer_y),
        BB_ATTRACT: float(attract),
        BB_HAS_FOOD: False,
        BB_FOOD_X: 0.0,
        BB_FOOD_Y: 0.0,
        BB_HAS_INTEREST: False,
        BB_INTEREST_X: 0.0,
        BB_INTEREST_Y: 0.0,
        BB_HAS_SCHOOL: False,
        BB_SCHOOL_X: 0.0,
        BB_SCHOOL_Y: 0.0,
        BB_IDLE_LEFT: 0.0,
        BB_RETARGET_LEFT: 0.0,
    })
    root = Selector("fish_root", [
        Sequence("edge", [
            Condition("near_edge", cond_near_edge),
            Action("push_inward", act_push_inward),
        ]),
        Sequence("food", [
            Condition("has_food", cond_has_food),
            Action("seek_food", act_seek_food),
        ]),
        Sequence("point", [
            Condition("has_interest", cond_has_interest),
            Action("seek_interest", act_seek_interest),
        ]),
        Sequence("idle", [
            Condition("is_idling", cond_is_idling),
            Action("idle", act_idle),
        ]),
        Action("wander", act_wander),
    ])
    tree = BehaviorTree(root, bb)
    # 开局先给一个目标点，避免第一帧原地不动
    _pick_wander_target(bb, cfg, rng)
    bb.set(BB_RETARGET_LEFT, rng.uniform(cfg.retarget_lo, cfg.retarget_hi))
    return tree


def describe_tree(node, depth=0):
    """把树打印成缩进文本（调试 / 测试用）。

    :param node: 根节点或 :class:`BehaviorTree`
    :returns: 多行字符串
    """
    root = getattr(node, "root", node)
    lines = []

    def walk(n, d):
        lines.append("  " * d + "%s(%s)" % (type(n).__name__, n.name))
        for c in getattr(n, "children", []) or []:
            walk(c, d + 1)
        child = getattr(n, "child", None)
        if child is not None:
            walk(child, d + 1)

    walk(root, depth)
    return "\n".join(lines)
