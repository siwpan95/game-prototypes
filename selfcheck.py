# -*- coding: utf-8 -*-
"""无头自检（不开窗口）：3D6 判定 / 弹巢装填与射击 / ECS 组件往返。

用法：python selfcheck.py    （退出 0 = 通过）
GUI 入口仍是 `python main.py`；本文件只验证核心逻辑。
"""
from __future__ import annotations

import random

from components import BulletType, ChamberComponent, DiceResult, HealthComponent
from ecs import Entity, World
from systems import DiceSystem


def main() -> int:
    random.seed(20261026)

    # 1) 3d6：每颗 1..6、点数与总和一致
    for _ in range(2000):
        dice, total = DiceSystem.roll_3d6()
        if len(dice) != 3 or any(value < 1 or value > 6 for value in dice) or total != sum(dice):
            print("FAIL 3d6 invariant", dice, total)
            return 1

    # 2) 暴击判定
    if DiceSystem.interpret_3d6([1, 1, 1], 3) != DiceResult.CRITICAL_FAIL:
        print("FAIL critical-fail not detected")
        return 1
    if DiceSystem.interpret_3d6([6, 6, 6], 18) != DiceResult.CRITICAL_SUCCESS:
        print("FAIL critical-success not detected")
        return 1

    # 3) 弹巢：装填满槽、射击后减一、子弹类型合法
    chamber = ChamberComponent()
    chamber.fill_random(live_count=2)
    if len(chamber.bullets) != chamber.max_slots:
        print("FAIL chamber not filled", len(chamber.bullets))
        return 1
    if not all(isinstance(bullet, int) and bullet in set(BulletType) for bullet in chamber.bullets):
        print("FAIL chamber holds an unknown bullet type")
        return 1
    chamber.shoot()
    if len(chamber.bullets) != chamber.max_slots - 1:
        print("FAIL shoot did not consume one bullet")
        return 1

    # 4) ECS 组件往返与可变性
    world = World()
    entity = Entity("selfcheck")
    health = HealthComponent(hp=3)
    world.add_component(entity, health)
    world.add_component(entity, chamber)
    if not world.has_component(entity, HealthComponent):
        print("FAIL component not registered")
        return 1
    world.get_component(entity, HealthComponent).hp -= 1
    if world.get_component(entity, HealthComponent).hp != 2:
        print("FAIL component mutation not visible")
        return 1

    print("russia selfcheck ok: 3d6 x2000 / crits / chamber / ecs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
