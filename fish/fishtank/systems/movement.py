"""MovementSystem（priority=30）：把行为树的决策变成实际位移。

🔴 禁止 `from __future__ import annotations`（E6）。

行为树只写"目标点 + 速度倍率 + 尾摆倍率"，本系统负责：

1. 求期望速度（朝目标点，模长 = 基础速度 × 倍率）；
2. 按 `turn_rate` 做一阶平滑转向（所以鱼是"划弧"而不是"折线"）；
3. 积分位移并钳进活动区；
4. 掉头检测（写 `WD_TURNS` 供粒子系统生成转身气泡）；
5. 推进摆尾相位；
6. **回写 FishState** —— 存档才是唯一真相，组件只是它的投影。
"""

import math

from fishtank.components import AIState, Animation, FishTag, Motion, Transform
from fishtank.constants import (
    BB_SPEED_MUL, BB_STATE, BB_TAIL_MUL, BB_TARGET_X, BB_TARGET_Y,
    WD_CFG, WD_DT, WD_STATE, WD_TURNS,
)
from fishtank.engine_bootstrap import BlackboardComponent, System

_TWO_PI = math.pi * 2.0
_EPS = 1e-9
_HEADING_DEADZONE = 1e-4
"""速度小于这个量级时不改朝向，免得原地发呆的鱼疯狂翻面。"""


class MovementSystem(System):
    """转向 → 积分 → 边界 → 回写。"""

    priority = 30

    def __init__(self, logger=None):
        """:param logger: 可选日志器。"""
        self._log = logger
        self.turns = 0
        """本次会话累计掉头次数（诊断用）。"""

    def update(self, world, dt):
        """执行一帧运动。

        :param world: ECS World
        :param dt: 帧时长（这里用 `WD_DT`，已由 TickSystem 钳过）
        """
        cfg = world.get_data(WD_CFG)
        state = world.get_data(WD_STATE)
        if cfg is None or state is None:
            return
        dt = float(world.get_data(WD_DT, dt) or 0.0)
        if dt <= 0.0:
            return

        turns = world.get_data(WD_TURNS)
        if turns is None:
            turns = []
            world.set_data(WD_TURNS, turns)

        # 转向平滑系数：一阶低通，dt 大时自动收敛到 1（不会过冲）
        blend = cfg.turn_rate * dt
        if blend > 1.0:
            blend = 1.0

        for ent in world.each(FishTag, Transform, Motion, BlackboardComponent):
            self._step_one(ent, world, state, cfg, dt, blend, turns)

    # ── 单条鱼 ──

    def _step_one(self, ent, world, state, cfg, dt, blend, turns):
        """推进一条鱼。"""
        tag = ent.get(FishTag)
        tr = ent.get(Transform)
        mo = ent.get(Motion)
        bb = ent.get(BlackboardComponent).blackboard

        # ① 行为树输出 → Motion / AIState
        mo.target_x = float(bb.get(BB_TARGET_X, tr.x))
        mo.target_y = float(bb.get(BB_TARGET_Y, tr.y))
        speed_mul = float(bb.get(BB_SPEED_MUL, 1.0))
        tail_mul = float(bb.get(BB_TAIL_MUL, 1.0))

        ai = ent.get(AIState)
        if ai is not None:
            ai.state = str(bb.get(BB_STATE, ai.state))
            ai.speed_mul = speed_mul
            ai.tail_mul = tail_mul

        # ② 期望速度
        dx = mo.target_x - tr.x
        dy = mo.target_y - tr.y
        dist = math.hypot(dx, dy)
        want = mo.base_speed * speed_mul
        if dist > _EPS:
            # 接近目标时线性减速，避免在目标点附近来回抖动
            if dist < cfg.arrive_radius:
                want *= dist / cfg.arrive_radius
            desired_vx = dx / dist * want
            desired_vy = dy / dist * want
        else:
            desired_vx = 0.0
            desired_vy = 0.0

        # ③ 平滑转向
        mo.vx += (desired_vx - mo.vx) * blend
        mo.vy += (desired_vy - mo.vy) * blend
        mo.speed = math.hypot(mo.vx, mo.vy)

        # ④ 积分 + 边界
        nx = tr.x + mo.vx * dt
        ny = tr.y + mo.vy * dt
        if nx < cfg.x_min:
            nx = cfg.x_min
            mo.vx = abs(mo.vx)
        elif nx > cfg.x_max:
            nx = cfg.x_max
            mo.vx = -abs(mo.vx)
        if ny < cfg.y_min:
            ny = cfg.y_min
            mo.vy = abs(mo.vy)
        elif ny > cfg.y_max:
            ny = cfg.y_max
            mo.vy = -abs(mo.vy)
        tr.x = nx
        tr.y = ny

        # ⑤ 掉头检测
        if mo.vx > _HEADING_DEADZONE:
            new_heading = 1.0
        elif mo.vx < -_HEADING_DEADZONE:
            new_heading = -1.0
        else:
            new_heading = tr.heading
        if new_heading != tr.heading:
            tr.heading = new_heading
            self.turns += 1
            turns.append((tr.x, tr.y))

        # ⑥ 摆尾相位
        anim = ent.get(Animation)
        if anim is not None:
            anim.tail_phase = (anim.tail_phase + anim.tail_hz * tail_mul * dt * _TWO_PI) % _TWO_PI

        # ⑦ 回写存档（唯一真相）
        fish = state.get_fish(tag.uid)
        if fish is not None:
            fish.x = tr.x
            fish.y = tr.y
            fish.heading = tr.heading
