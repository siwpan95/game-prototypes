# -*- coding: utf-8 -*-
"""
smoke_logic —— 玩法逻辑冒烟测试（不开窗口、不碰 GL）。

跑的是与游戏**完全相同**的 ECS 世界装配（``main.build_world``），只把渲染
换成断言，因此可以在无显示环境里验证重构后的玩法是否正确。

    python scripts/smoke_logic.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ecs.components import (Decoration, Drift, GameState, Lateral, Position,
                            VehicleControl)
from main import build_world, load_config

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DT = 1.0 / 60.0


def _check(label, ok, detail=''):
    print(f"[{'PASS' if ok else 'FAIL'}] {label}" + (f"  ({detail})" if detail else ''))
    return ok


def _player(world):
    for entity in world.get_entities_with(Position, VehicleControl):
        return entity
    return None


def main():
    cfg = load_config(os.path.join(BASE, 'config.json'))
    c3 = cfg['threed']
    world = build_world(cfg, world_key_state())
    state = world.get_singleton(GameState)
    ent = _player(world)
    ks = world.systems[0].key_state
    ok = True

    # 漂移关闭（否则无输入时车会被随机推离公路，干扰各项断言）
    drift = world.get_component(ent, Drift)
    saved_chance = drift.chance
    drift.chance = 0.0

    # 1) 空跑 10 秒：里程累计、装饰物生成、车仍存活
    for _ in range(600):
        world.update(DT)
    ok &= _check('里程累计', state.distance_km > 0.0, f'{state.distance_km:.3f} km')
    decos = world.get_entities_with(Position, Decoration)
    ok &= _check('装饰物生成', len(decos) > 0, f'{len(decos)} 个')
    ok &= _check('无输入时存活', state.alive, f'alive={state.alive}')

    # 2) 装饰物回收：把某个装饰物拉到镜头前，应在下一帧被移除
    if decos:
        target = decos[0]
        pos = world.get_component(target, Position)
        pos.z = c3['road_near_z'] + 1.0
        world.update(DT)
        still_there = any(d is target for d in
                           world.get_entities_with(Position, Decoration))
        ok &= _check('装饰物回收', not still_there,
                     f'z={pos.z:.1f} > near_z={c3["road_near_z"]}')

    # 3) 转向：按住右键 0.5 秒，车应右移
    pos = world.get_component(ent, Position)
    lat = world.get_component(ent, Lateral)
    x0 = pos.x
    ks.right = True
    for _ in range(30):
        world.update(DT)
    x1 = pos.x
    ok &= _check('转向右移', x1 > x0, f'{x0:.2f} -> {x1:.2f}')

    # 4) 松手后横向速度被阻尼衰减（车辆回稳）
    ks.right = False
    pos.x, lat.vx = 0.0, 0.0
    lat.vx = 6.0
    for _ in range(120):
        world.update(DT)
    ok &= _check('阻尼衰减', abs(lat.vx) < 0.1, f'vx={lat.vx:.4f}')

    # 5) 漂移：把触发率设为 1，应给横向速度一个冲量并计数
    pos.x, lat.vx = 0.0, 0.0
    drift.chance = 1.0
    before_vx, before_n = lat.vx, state.drift_count
    for _ in range(10):
        world.update(DT)
    ok &= _check('漂移施加冲量', state.drift_count > before_n,
                 f'drifts {before_n} -> {state.drift_count}')
    ok &= _check('漂移改变横向速度', lat.vx != before_vx,
                 f'vx {before_vx:.2f} -> {lat.vx:.2f}')
    drift.chance = saved_chance

    # 6) 碰撞判死：把车推出路肩
    limit = c3['road_half_width'] - c3['car_half_width']
    pos.x = limit + 0.5
    world.update(DT)
    ok &= _check('撞路肩判死', not state.alive, f'x={pos.x:.2f} > limit={limit:.2f}')

    # 7) 死亡后不再累加里程
    km_at_death = state.distance_km
    for _ in range(60):
        world.update(DT)
    ok &= _check('死亡后停止推进', abs(state.distance_km - km_at_death) < 1e-9)

    print('\nRESULT:', 'ALL PASS' if ok else 'HAS FAILURES')
    return 0 if ok else 1


def world_key_state():
    from ecs.components import KeyState
    return KeyState()


if __name__ == '__main__':
    sys.exit(main())
