"""happy-childrens-day 无头自检 —— 不创建 Tk 窗口 / 不跑游戏主循环。

只 import 纯逻辑与数据模块：ecs / components / data_loader / entities / systems。
不 import main（Game(tk.Tk) 会真的开窗口）。

验证点：
1. snacks.xlsx -> SnackConfig -> SnackData 的数据往返（93 行逐行核对字段）；
2. 稀有度分档 _score_to_rarity 的边界与单调性；
3. ECS 组件存取 / 查询 / 死亡清理，MovementSystem 状态推进（含反向控制与边界钳制）；
4. 数据驱动零食实体生成、SpawnerSystem 补货、SnakeSystem 轨迹与增长。

运行：python selfcheck.py
"""

import os
import random
import sys
import traceback

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from components import (
    Collider, GameState, Health, Movement, Render, Score,
    SnackData, StatusEffect, Transform,
)
from data_loader import SnackConfig, _score_to_rarity
from ecs import World
from entities import create_snack
from systems import (
    CANVAS_H, CANVAS_W, MovementSystem, SnakeSystem, SpawnerSystem,
)

SEED = 20261026


def check_snack_config():
    """功能点 1：Excel 配置逐行往返到 SnackData，字段不得丢失或串位。"""
    cfg = SnackConfig()
    rows = cfg.df
    if len(rows) == 0:
        return "snacks.xlsx 没有有效数据行"

    checked = 0
    for snack_id in cfg.config_map:
        expected = cfg.config_map[snack_id]
        data = cfg.get_snack_by_id(snack_id)
        if data is None:
            return "id=%r 无法转换成 SnackData" % (snack_id,)
        fields = {
            "name": (data.name, expected["name"]),
            "shape": (data.shape, expected["shape"]),
            "label": (data.label, expected["label"]),
            "type": (data.type, expected["type"]),
            "color": (data.color, expected["color"]),
            "hp_change": (data.hp_change, int(expected["hp_change"])),
            "score_value": (data.score_value, int(expected["score"])),
            "duration": (data.duration, int(expected["duration"])),
            "value": (data.value, int(expected["value"])),
        }
        for field, (got, want) in fields.items():
            if got != want:
                return "id=%r 字段 %s 往返不一致：%r != %r" % (
                    snack_id, field, got, want)
        checked += 1

    if checked < 10:
        return "只校验了 %d 条零食配置，数据量异常" % checked
    return ""


def check_rarity_tiers():
    """功能点 2：分数 -> 稀有度/解锁等级的分档边界与单调性。"""
    cases = [
        (0, ("common", 1)),
        (60, ("common", 1)),
        (61, ("uncommon", 2)),
        (120, ("uncommon", 2)),
        (121, ("rare", 4)),
        (200, ("rare", 4)),
        (201, ("epic", 6)),
        (399, ("epic", 6)),
        (400, ("legendary", 8)),
        (500, ("legendary", 8)),
    ]
    for score, want in cases:
        got = _score_to_rarity(score)
        if got != want:
            return "score=%d 分档 %r != %r" % (score, got, want)

    prev = 0
    for score in range(0, 520, 7):
        unlock = _score_to_rarity(score)[1]
        if unlock < prev:
            return "score=%d 解锁等级回退：%d < %d" % (score, unlock, prev)
        prev = unlock
    return ""


def check_ecs_and_movement():
    """功能点 3：ECS 存取/查询/清理 + MovementSystem 的位移、反向与钳制。"""
    world = World()
    eid = world.create_entity()
    if world.component_for_entity(eid, Transform) is not None:
        return "新实体不应已有 Transform"

    world.add_component(eid, Transform(400, 300))
    world.add_component(eid, Movement(speed=5))
    world.add_component(eid, StatusEffect())
    world.add_component(eid, GameState())
    world.add_component(eid, Collider(20))

    trans = world.component_for_entity(eid, Transform)
    move = world.component_for_entity(eid, Movement)
    status = world.component_for_entity(eid, StatusEffect)

    matched = list(world.get_components(Transform, Movement))
    if len(matched) != 1 or len(matched[0][1]) != 2:
        return "get_components(Transform, Movement) 查询结果异常：%r" % (matched,)
    if list(world.get_components(Transform, Health)):
        return "get_components 不应匹配缺少组件的实体"

    move.vx = 1
    world.update(MovementSystem())
    if (trans.x, trans.y) != (405, 300):
        return "MovementSystem 前进一格后位置为 (%r, %r)，期望 (405, 300)" % (
            trans.x, trans.y)

    status.is_reversed = True
    world.update(MovementSystem())
    if trans.x != 400:
        return "反向控制未生效：x=%r，期望 400" % (trans.x,)
    status.is_reversed = False

    trans.x, trans.y = CANVAS_W - 10, CANVAS_H - 10
    world.update(MovementSystem())
    if (trans.x, trans.y) != (CANVAS_W - 16, CANVAS_H - 16):
        return "边界钳制失败：(%r, %r)，期望 (%d, %d)" % (
            trans.x, trans.y, CANVAS_W - 16, CANVAS_H - 16)

    world.remove_component(eid, Collider)
    if world.component_for_entity(eid, Collider) is not None:
        return "remove_component 后组件仍然存在"

    world.delete_entity(eid)
    world.clear_dead_entities()
    if world.component_for_entity(eid, Transform) is not None:
        return "死亡实体在 clear_dead_entities 后仍可访问"
    return ""


def check_snacks_spawner_snake():
    """功能点 4：数据驱动零食实体 + 补货系统 + 贪吃蛇轨迹/增长。"""
    random.seed(SEED)
    world = World()

    player = world.create_entity()
    world.add_component(player, Transform(400, 300))
    world.add_component(player, Render(color="#FFDD00", label="P"))
    world.add_component(player, Health(100))
    world.add_component(player, GameState())
    world.add_component(player, StatusEffect())
    world.add_component(player, Score())

    created = 0
    for i in range(5):
        eid = create_snack(world, 100 + i * 10, 100)
        if eid is None:
            return "create_snack 未能创建实体（Excel 配置取数失败）"
        snack = world.component_for_entity(eid, SnackData)
        render = world.component_for_entity(eid, Render)
        collider = world.component_for_entity(eid, Collider)
        if snack is None or render is None or collider is None:
            return "零食实体缺少 SnackData/Render/Collider 组件"
        if not snack.name:
            return "零食实体名称为空"
        if (render.color, render.shape, render.label) != (
                snack.color, snack.shape, snack.label):
            return "Render 组件与 SnackData 不一致：%r vs %r" % (
                (render.color, render.shape, render.label),
                (snack.color, snack.shape, snack.label))
        created += 1

    spawner = SpawnerSystem()
    before = len(list(world.get_components(SnackData)))
    if before >= spawner.min_snacks:
        return "测试前置不成立：已存在 %d 个零食" % before
    spawner.update(world)
    after = len(list(world.get_components(SnackData)))
    if after < spawner.min_snacks:
        return "SpawnerSystem 补货后仍只有 %d 个零食（min=%d）" % (
            after, spawner.min_snacks)
    if after != before + spawner.spawn_batch:
        return "SpawnerSystem 一次补货 %d 个，期望 %d 个" % (
            after - before, spawner.spawn_batch)

    snake = SnakeSystem(player)
    if snake.segment_count != 3:
        return "SnakeSystem 初始段数 %r，期望 3" % (snake.segment_count,)

    trans = world.component_for_entity(player, Transform)
    trans.x, trans.y = 400.0, 300.0
    snake.update(world)
    trans.x, trans.y = 420.0, 300.0
    snake.update(world)
    if snake.history[:2] != [(420.0, 300.0), (400.0, 300.0)]:
        return "SnakeSystem 轨迹记录错误：%r" % (snake.history[:2],)

    snake.grow(2)
    if snake.segment_count != 5:
        return "SnakeSystem.grow(2) 后段数 %r，期望 5" % (snake.segment_count,)
    snake.grow()
    if snake.segment_count != 6:
        return "SnakeSystem.grow() 默认增长 1 段失败：%r" % (snake.segment_count,)

    state = world.component_for_entity(player, GameState)
    state.is_over = True
    before_hist = len(snake.history)
    snake.update(world)
    if len(snake.history) != before_hist:
        return "游戏结束后 SnakeSystem 仍继续记录轨迹"
    return ""


def main():
    checks = [
        ("snacks.xlsx -> SnackData round-trip", check_snack_config),
        ("_score_to_rarity tiers", check_rarity_tiers),
        ("ECS store/query/cleanup + MovementSystem advance", check_ecs_and_movement),
        ("snack entities + SpawnerSystem + SnakeSystem", check_snacks_spawner_snake),
    ]
    for label, func in checks:
        try:
            err = func()
        except Exception:
            print("FAIL: %s raised" % label)
            traceback.print_exc()
            return 1
        if err:
            print("FAIL: %s: %s" % (label, err))
            return 1

    print("selfcheck ok: validated %d things -- %s" % (
        len(checks), "; ".join(label for label, _ in checks)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
