"""monster_ai.py — 用 alloy.ai.decision 的通用状态机驱动怪物 AI。

每个怪物持有自己的 GenericStateMachine 实例，状态在 idle / chase / attack
之间随与玩家的距离转移；decide() 依据状态机当前态 + Dijkstra 距离场给出动作。

导航核心改用 Dijkstra 地图（见 pathfinding.py）：每回合游戏层从玩家位置
洪水填充一次距离场，怪物「下坡」走向玩家、受伤「上坡」逃跑，能自然绕墙、
穿门、过走廊，优于逐格贪心。
"""
from __future__ import annotations

from alloy.ai.decision.state_machine import GenericStateMachine
from alloy.ai.decision import build_behavior_tree, Blackboard
from pathfinding import (
    compute_dijkstra, step_downhill, step_uphill, UNREACHABLE,
)


# 状态机配置：状态 + 事件转移（guard 可省略）
MONSTER_FSM = {
    "state_machines": {
        "monster": {
            "initial": "idle",
            "states": {
                "idle": {
                    "transitions": {"see": "chase", "adjacent": "attack"},
                    "content": "游荡",
                },
                "chase": {
                    "transitions": {"lost": "idle", "adjacent": "attack"},
                    "content": "追击玩家",
                },
                "attack": {
                    "transitions": {"lost": "idle", "see": "chase"},
                    "content": "撕咬玩家",
                },
            },
        }
    }
}


def make_brain() -> GenericStateMachine:
    """为一只怪物创建一个独立的状态机实例。"""
    return GenericStateMachine("monster", MONSTER_FSM)


# 视野半径（曼哈顿距离）
SIGHT = 6


def decide(brain: GenericStateMachine, mx: int, my: int, px: int, py: int):
    """根据状态机 + 距离（贪心回退，已不主用；主路径见 decide_dijkstra）。

    保留以兼容无距离场的场景；主循环调用 decide_dijkstra。
    """
    dist = abs(mx - px) + abs(my - py)

    if dist <= 1:
        brain.trigger("adjacent")
        return ("attack",)

    if dist <= SIGHT:
        brain.trigger("see")
        dx = 0 if mx == px else (1 if px > mx else -1)
        dy = 0 if my == py else (1 if py > my else -1)
        return ("move", dx, dy)

    brain.trigger("lost")
    return ("idle",)


def build_distance_field(px: int, py: int, walkable,
                         width: int, height: int):
    """从玩家位置构建 Dijkstra 距离场（每回合调用一次）。"""
    return compute_dijkstra(px, py, walkable, width, height)


def decide_dijkstra(brain: GenericStateMachine, mx: int, my: int,
                    dist_map, width: int, height: int,
                    occupied: set, player_pos: tuple,
                    wounded: bool = False, sight: int = SIGHT) -> tuple:
    """用 Dijkstra 距离场决定普通怪本回合动作（主 AI 路径）。

    参数：
        brain:       该怪的状态机（仅用于 flavor：触发 see/adjacent/lost）
        mx,my:       怪物坐标
        dist_map:    距离场 dist_map[y][x]
        width,height:地图尺寸
        occupied:    其它怪物占据的格集合（禁止踏足）
        player_pos:  玩家坐标（禁止踏足，贴脸改为攻击）
        wounded:     是否受伤（HP<1/3 时「上坡」逃跑）

    返回：
        ("attack",) / ("move", dx, dy) / ("idle",)
    """
    dist = dist_map[my][mx]

    if dist == 1:
        brain.trigger("adjacent")
        return ("attack",)

    if dist == UNREACHABLE or dist > sight:
        # 不可达或超出感知半径：失去目标，游荡/发呆
        brain.trigger("lost")
        return ("idle",)

    brain.trigger("see")
    forbidden = occupied | {player_pos}
    step = step_uphill(mx, my, dist_map, width, height, forbidden) \
        if wounded else step_downhill(mx, my, dist_map, width, height, forbidden)
    if step is None:
        return ("idle",)
    return ("move", step[0], step[1])


# ── Boss 行为树（打通 alloy 行为树 + 黑板 决策范式）────────
BOSS_BT_SPEC = {
    "name": "BossAI",
    "root": {
        "type": "selector", "name": "Boss根",
        "children": [
            {"type": "sequence", "name": "近身攻击", "children": [
                {"type": "condition", "key": "dist", "op": "le", "value": 1},
                {"type": "action", "kind": "set", "key": "action", "value": "attack"},
            ]},
            {"type": "sequence", "name": "狂暴追击", "children": [
                {"type": "condition", "key": "php", "op": "lt", "value": 0.4},
                {"type": "action", "kind": "set", "key": "action", "value": "rush"},
            ]},
            {"type": "sequence", "name": "视野追击", "children": [
                {"type": "condition", "key": "dist", "op": "le", "value": 6},
                {"type": "action", "kind": "set", "key": "action", "value": "move"},
            ]},
            {"type": "action", "kind": "set", "key": "action", "value": "idle"},
        ],
    },
}


def make_boss_brain():
    """为 Boss(巨龙) 构造行为树 + 黑板决策器。"""
    bb = Blackboard({"dist": 99, "php": 1.0, "hp": 1.0, "action": "idle"})
    tree = build_behavior_tree(BOSS_BT_SPEC, blackboard=bb)
    return tree, bb


def decide_boss(bt, bb, mx, my, px, py, boss_hp_ratio, player_hp_ratio,
                dist_map=None, width: int = 0, height: int = 0,
                occupied: set | None = None, sight: int = SIGHT):
    """用行为树 + Dijkstra 距离场决定 Boss 本回合动作。

    Boss 作为最终守关者拥有「全图感知」：始终沿距离场「下坡」追击玩家，
    贴脸则攻击；玩家残血(php<0.4)时行为树置 rush，但移动仍走最短路径。
    返回与 decide_dijkstra 同构的元组。
    """
    bb.set("dist", abs(mx - px) + abs(my - py))
    bb.set("php", player_hp_ratio)
    bb.set("hp", boss_hp_ratio)
    bt.run()
    action = bb.get("action", "idle")

    if dist_map is not None and width and height:
        dist = dist_map[my][mx]
        if dist == 1:
            return ("attack",)
        # 狂暴阶段：自身血量 <50% 时强制激进追击（AI Director 不在此压低 Boss）
        if boss_hp_ratio < 0.5:
            bb.set("action", "rush")
        if dist != UNREACHABLE and dist <= sight:
            forbidden = (occupied or set()) | {(px, py)}
            step = step_downhill(mx, my, dist_map, width, height, forbidden)
            if step is not None:
                return ("move", step[0], step[1])
        # 距离场不可达：退回贪心
    dx = 0 if mx == px else (1 if px > mx else -1)
    dy = 0 if my == py else (1 if py > my else -1)
    if action == "attack" or dist == 1:
        return ("attack",)
    if action in ("move", "rush"):
        return ("move", dx, dy)
    return ("idle",)
