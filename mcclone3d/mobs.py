# -*- coding: utf-8 -*-
"""生物表与实体状态（纯数据 + 纯函数，零 GL）。

## 为什么生物要单独一份表

生物与方块/物品一样，是**数据**：加一种生物不该改 AI、加一段 AI 不该改生物数值。
所以这里只有"生物长什么样、跑多快、掉什么"，**没有任何"它下一步做什么"的逻辑** ——
那些在 `ai.py`。

## 实体是什么

一个生物 = 一个 `Mob` 实例（**普通对象，不是 Service**）：

```
Mob(id, kind, pos, vel, yaw, health, state, target, ...)
```

刻意**不引 ECS**：本项目一次最多几百个生物，ECS 的收益抵不过它带来的间接层。
判据也很直接 —— 几百个生物每帧的开销在 demo 里要能跑满 60fps（见 `ai.py` 的说明）。

## 盒模型（渲染用）

每种生物给一组 `parts`：`(相对位置, 尺寸, 颜色)`。渲染端把它们当**六个面的方块**画
（复用 `mesh.box_faces`），所以生物的外观是**数据**，加一种生物不用碰渲染代码。
"""
from __future__ import annotations

import math

__all__ = ['MobKind', 'MOBS', 'mob_kind', 'all_kinds', 'passive_kinds',
           'hostile_kinds', 'Mob', 'AI_IDLE', 'AI_WANDER', 'AI_CHASE', 'AI_FLEE',
           'STATE_NAMES', 'spawn_allowed']

# ---------------------------------------------------------------- AI 状态
AI_IDLE = 'idle'          # 站着（偶尔换朝向）
AI_WANDER = 'wander'      # 随机游荡
AI_CHASE = 'chase'        # 追目标（敌对）
AI_FLEE = 'flee'          # 逃开（被动被打之后）

STATE_NAMES = {AI_IDLE: '停留', AI_WANDER: '游荡', AI_CHASE: '追击', AI_FLEE: '逃跑'}


class MobKind:
    """一种生物的定义。**只有数据**。"""

    __slots__ = ('name', 'title', 'hostile', 'health', 'speed', 'chase_speed',
                 'sight', 'reach', 'attack', 'attack_cd', 'fall_safe',
                 'drops', 'parts', 'width', 'height', 'spawn_light_max',
                 'spawn_weight')

    def __init__(self, name, title, *, hostile=False, health=10.0, speed=1.6,
                 chase_speed=None, sight=12.0, reach=1.2, attack=0.0,
                 attack_cd=1.0, fall_safe=3.5, drops=(), parts=(),
                 width=0.6, height=0.9, spawn_light_max=15, spawn_weight=1.0):
        self.name = name
        self.title = title
        self.hostile = bool(hostile)
        self.health = float(health)
        self.speed = float(speed)
        #: 追击时速度（敌对比游荡快，否则追不上玩家）
        self.chase_speed = float(chase_speed if chase_speed is not None else speed * 1.35)
        self.sight = float(sight)
        self.reach = float(reach)
        self.attack = float(attack)
        self.attack_cd = float(attack_cd)
        self.fall_safe = float(fall_safe)
        #: 掉落：`((物品名, 数量下限, 数量上限), ...)` —— 与方块掉落同口径（按名字）
        self.drops = tuple(drops)
        #: 盒模型：`((dx,dy,dz), (sx,sy,sz), (r,g,b))`，坐标以**脚底中心**为原点
        self.parts = tuple(parts)
        self.width = float(width)
        self.height = float(height)
        #: 刷新时"这一格的方块光不超过多少" —— 敌对生物靠它做到"只在暗处出现"
        self.spawn_light_max = int(spawn_light_max)
        self.spawn_weight = float(spawn_weight)

    def __repr__(self):
        return f'<MobKind {self.name}>'


def _quadruped(body, head, leg, *, body_len=3.0):
    """四足生物的盒模型（羊/猪/牛都用它，只换颜色）。

    ⚠ **尺寸单位是"格"，而且必须能取整到 ≥1**：网格生成按整数角落放盒子
    （UV 投影要求跨格连续），所以 0.6 这种尺寸会被 `round` 成 0 厚度 ⇒ 部件消失。
    本项目的生物模型刻意用**整数格**（块状感，与方块世界一致）。
    布局：腿占 y∈[0,1)、身体 y∈[1,2)、头 y∈[2,3)。
    """
    return (
        ((0.0, 0.0, 0.0), (1.0, 1.0, 1.0), leg),                       # 腿
        ((0.0, 1.0, 0.0), (1.0, 1.0, body_len), body),                 # 身体
        ((0.0, 2.0, 0.0), (1.0, 1.0, 1.0), head),                      # 头
    )


def _humanoid(robe, skin):
    """人形生物的盒模型（僵尸/玩家体型）。**整数格**，见 `_quadruped` 的说明。

    布局：腿 y∈[0,2)、躯干 y∈[2,4)、头 y∈[4,5)。总高 5 格，比玩家略高
    （`MobKind.height` 必须与它一致，否则碰撞与渲染会对不上）。
    """
    return (
        ((0.0, 0.0, 0.0), (1.0, 2.0, 1.0), robe),    # 腿
        ((0.0, 2.0, 0.0), (1.0, 2.0, 1.0), robe),    # 躯干
        ((0.0, 4.0, 0.0), (1.0, 1.0, 1.0), skin),    # 头
    )


def _defs():
    from . import items as I                       # 延迟导入：避免与 items 的循环
    _ = I
    out = []

    # --- 被动：羊 ---
    out.append(MobKind(
        'sheep', '羊', health=8.0, speed=1.1, sight=8.0,
        drops=(('cooked_meat', 1, 2),),
        parts=_quadruped((0.90, 0.90, 0.88), (0.95, 0.94, 0.92), (0.52, 0.50, 0.48),
                         body_len=3.0),
        width=1.0, height=3.0, spawn_light_max=15, spawn_weight=1.0))
    # --- 被动：猪 ---
    out.append(MobKind(
        'pig', '猪', health=8.0, speed=1.2, sight=8.0,
        drops=(('cooked_meat', 1, 3),),
        parts=_quadruped((0.88, 0.58, 0.58), (0.94, 0.64, 0.62), (0.58, 0.36, 0.36),
                         body_len=3.0),
        width=1.0, height=3.0, spawn_light_max=15, spawn_weight=1.0))
    # --- 敌对：僵尸（只在暗处刷、会追、贴上来就打） ---
    out.append(MobKind(
        'zombie', '僵尸', hostile=True, health=14.0, speed=1.3, chase_speed=1.9,
        sight=16.0, reach=1.3, attack=2.0, attack_cd=1.0,
        drops=(('rotten_flesh', 1, 2),),
        parts=_humanoid((0.24, 0.46, 0.28), (0.44, 0.56, 0.40)),
        width=1.0, height=5.0, spawn_light_max=7, spawn_weight=1.0))
    return out


MOBS = {mk.name: mk for mk in _defs()}
assert len(MOBS) == len(_defs()), '生物名重复'


def mob_kind(name: str) -> MobKind:
    try:
        return MOBS[name]
    except KeyError:
        raise KeyError(f'未知生物 {name!r}；合法：{sorted(MOBS)}') from None


def all_kinds():
    return [MOBS[k] for k in sorted(MOBS)]


def passive_kinds():
    return [mk for mk in all_kinds() if not mk.hostile]


def hostile_kinds():
    return [mk for mk in all_kinds() if mk.hostile]


# ---------------------------------------------------------------- 实体
class Mob:
    """一个生物实例。位置是**脚底中心**（与玩家的 `pos` 同口径）。"""

    __slots__ = ('kind', 'pos', 'vel', 'yaw', 'pitch', 'health', 'state',
                 'target', 'cd', 'on_ground', 'age', 'flee_t', 'wander_t',
                 'wish', 'hurt_t', 'id')

    _next_id = 1

    def __init__(self, kind, x: float, y: float, z: float, yaw: float = 0.0):
        self.id = Mob._next_id
        Mob._next_id += 1
        self.kind = kind if isinstance(kind, MobKind) else mob_kind(kind)
        self.pos = [float(x), float(y), float(z)]
        self.vel = [0.0, 0.0, 0.0]
        self.yaw = float(yaw)
        self.pitch = 0.0
        self.health = self.kind.health
        self.state = AI_IDLE
        self.target = None                # 追击/逃跑的目标（目前只有玩家）
        self.cd = 0.0                     # 攻击冷却
        self.on_ground = False
        self.age = 0.0
        self.flee_t = 0.0                 # 逃跑剩余时间
        self.wander_t = 0.0               # 当前游荡方向的剩余时间
        self.wish = [0.0, 0.0]            # 本帧的期望水平方向（已归一化）
        self.hurt_t = 0.0                 # 受击闪烁计时（表现层用）

    # ---------------------------------------------------------------- 便捷
    @property
    def alive(self) -> bool:
        return self.health > 0.0

    @property
    def name(self) -> str:
        return self.kind.name

    def eye_y(self) -> float:
        return self.pos[1] + self.kind.height * 0.85

    def hurt(self, amount: float, cause: str = '') -> bool:
        """受伤；返回**是否因此死亡**。"""
        if amount <= 0 or not self.alive:
            return False
        self.health -= float(amount)
        self.hurt_t = 0.35
        # 被动生物被打就跑（MC 的手感；也让"打猎"有反馈）
        if not self.kind.hostile and self.alive:
            self.state = AI_FLEE
            self.flee_t = 6.0
        elif self.kind.hostile and self.alive:
            self.state = AI_CHASE          # 被打的敌对生物立刻锁定
        return self.health <= 0.0

    def dist_to(self, x: float, z: float) -> float:
        """到自己到某点的**水平**距离（AI 里调用非常频繁，所以单独一个方法）。

        命名就叫 `dist_to`：早先叫 `ray_to`，而它并不做射线检测 ——
        在一个满是 `raycast` 的代码库里这个名字会被读错（实测踩过一次调用签名不匹配）。
        """
        return math.hypot(x - self.pos[0], z - self.pos[2])

    def dist3_to(self, x: float, y: float, z: float) -> float:
        """三维距离（攻击判定/视线判断用）。"""
        return math.sqrt((x - self.pos[0]) ** 2 + (y - self.pos[1]) ** 2
                         + (z - self.pos[2]) ** 2)

    def dump(self) -> dict:
        return {'kind': self.kind.name, 'pos': [round(v, 3) for v in self.pos],
                'yaw': round(self.yaw, 1), 'health': round(self.health, 2),
                'state': self.state}

    def __repr__(self):
        return (f'<Mob #{self.id} {self.kind.name} {self.state} '
                f'{self.health:.0f}hp @{tuple(round(v, 1) for v in self.pos)}>')


def spawn_allowed(kind: MobKind, block_light: int, sky_brightness: int,
                  night: bool) -> bool:
    """这一格现在允许这种生物刷新吗（**纯函数**，单测逐条穷举）。

    * 敌对生物：**方块光与天光折算值都不超过 `spawn_light_max`** ⇒ 只在暗处/夜里出现；
    * 被动生物：不挑光（白天到处走），但**夜里刷得少**（`night` 时概率减半由调用方处理）。
    """
    light = max(int(block_light), int(sky_brightness))
    if kind.hostile:
        return light <= kind.spawn_light_max and (night or light <= kind.spawn_light_max)
    return True
