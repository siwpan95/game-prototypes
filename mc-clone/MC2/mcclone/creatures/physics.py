# -*- coding: utf-8 -*-
"""creatures.physics — 生物移动碰撞（M4，T-M4-02）。

提供：
  - _is_solid(registry, world, x, y): 查询 (x,y,z=0) 是否 solid（AIR→False，未知 id 保守 True）。
  - move_with_collision(c, world, registry, dt): 仿 player._move_x/_move_y 的轴分离扫掠
    + 重力 + 落地 on_ground + 水平/垂直边界钳制 + c.sync_aabb()。

设计要点（架构 §2.4）：
  - 与 Player 碰撞**完全相同的思路**重写（player.py 的碰撞是实例方法，无法直接复用），
    因此独立实现于此；**不修改 player.py / geometry / block_world**。
  - 仅 z=0 层（与玩家一致）。
  - 纯标准库（math）+ 地基模块，headless 可断言。
"""

from __future__ import annotations

import math

from mcclone.core.block_registry import AIR


def _is_solid(registry, world, x: int, y: int) -> bool:
    """查询某格 (x, y, z=0) 是否为 solid 方块。

    AIR→False；未知 id 按 solid 保守处理（与 player._is_solid 同款）。
    """
    bid = world.get(x, y, 0)
    if bid == AIR:
        return False
    try:
        return registry.get(bid).solid
    except KeyError:
        return True


def move_with_collision(c, world, registry, dt: float) -> None:
    """轴分离扫掠移动 + 重力 + 落地，就地更新 c 的物理状态与 AABB。

    参数：
        c: Creature（含 _fx/_fy/width_f/height_f/vx/vy/on_ground/cfg/_sync_aabb）。
        world: BlockWorld（z=0 层）。
        registry: BlockRegistry。
        dt: 固定时间步长（秒）。
    """
    # 1) 重力（用生物自身 cfg，与玩家同值）
    c.vy -= c.cfg.gravity * dt
    if c.vy < -c.cfg.max_fall:
        c.vy = -c.cfg.max_fall

    # 2) 水平移动 + 扫掠碰撞（先 x）
    c._fx += c.vx * dt
    if c.vx > 0:
        xr = int(math.floor(c._fx + c.width_f - 1e-6))
        y0 = int(math.floor(c._fy))
        y1 = int(math.floor(c._fy + c.height_f - 1e-6))
        for y in range(y0, y1 + 1):
            if _is_solid(registry, world, xr, y):
                c._fx = xr - c.width_f
                c.vx = 0
                break
    elif c.vx < 0:
        xl = int(math.floor(c._fx))
        y0 = int(math.floor(c._fy))
        y1 = int(math.floor(c._fy + c.height_f - 1e-6))
        for y in range(y0, y1 + 1):
            if _is_solid(registry, world, xl, y):
                c._fx = xl + 1
                c.vx = 0
                break

    # 3) 垂直移动 + 扫掠碰撞（后 y，落地置 on_ground）
    c._fy += c.vy * dt
    c.on_ground = False
    x0 = int(math.floor(c._fx))
    x1 = int(math.floor(c._fx + c.width_f - 1e-6))
    if c.vy < 0:
        yb = int(math.floor(c._fy))
        for x in range(x0, x1 + 1):
            if _is_solid(registry, world, x, yb):
                c._fy = yb + 1
                c.vy = 0
                c.on_ground = True
                break
    elif c.vy > 0:
        yt = int(math.floor(c._fy + c.height_f - 1e-6))
        for x in range(x0, x1 + 1):
            if _is_solid(registry, world, x, yt):
                c._fy = yt - c.height_f
                c.vy = 0
                break

    # 4) 世界水平/底部边界钳制
    c._fx = max(0.0, min(c._fx, world.width - c.width_f))
    if c._fy < 0.0:
        c._fy = 0.0
        c.vy = 0

    # 5) 派生整数 AABB
    c._sync_aabb()
