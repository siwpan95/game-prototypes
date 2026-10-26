# -*- coding: utf-8 -*-
"""Endless Highway —— 无头自检（不建窗口、不渲染、不初始化混音）。

    python selfcheck.py

``main.py`` 的 ``main()`` 才 ``pygame.display.set_mode`` / ``mixer.init``，
import 本身安全；本自检复用它自己的装配函数和系统，只跑逻辑帧：

* ``config.json`` + ``main.load_config``      —— 配置读取与自洽
* ``main.build_world``                        —— ECS 装配（玩家/路/边线/状态单例/系统顺序）
* ``ecs/systems.py``                          —— 滚动里程、漂移推挤、出界判负、装饰物生成/回收

SDL 用 dummy 视频驱动，纯粹为了不在无显示环境里碰显卡。
输出保持 ASCII，避免 Windows 控制台代码页差异把中文打成乱码。
"""
from __future__ import annotations

import json
import math
import os
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)                                   # config.json / audio 相对路径
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
sys.path.insert(0, str(ROOT))

from ecs.components import (  # noqa: E402
    DashedLineRender, Decoration, Drift, GameState, LineRender, Position,
    RectRender, RoadSurface, VehicleControl,
)
from ecs.systems import (  # noqa: E402
    CollisionSystem, DecorationScrollSystem, DecorationSpawnSystem, DriftSystem,
    ScrollSystem,
)
from main import build_world, load_config  # noqa: E402


# --------------------------------------------------------------------- 检查项
def check_config() -> str:
    """配置能读、结构自洽，且与磁盘上的 JSON 完全一致（不丢字段）。"""
    raw = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    cfg = load_config("config.json")
    assert cfg == raw, "load_config lost or altered config data"

    for key in ("window", "game", "road", "player", "drift", "decorations", "fonts"):
        assert key in cfg, f"config section missing: {key}"
    win, road, player = cfg["window"], cfg["road"], cfg["player"]
    assert win["width"] > 0 and win["height"] > 0
    assert road["width"] < win["width"], "road wider than window"
    assert player["width"] < road["width"], "player wider than road"
    assert 0 < cfg["drift"]["chance"] < 1, "drift chance out of range"
    assert cfg["drift"]["min_push"] <= cfg["drift"]["max_push"], "drift push range inverted"
    assert cfg["game"]["fps"] > 0
    return (f"config.json parsed ({win['width']}x{win['height']}, road {road['width']}px, "
            f"drift {cfg['drift']['chance']}/frame)")


def check_world_assembly() -> str:
    """build_world 装配出的实体/组件/系统顺序都符合配置。"""
    cfg = load_config("config.json")
    world, screen_w, screen_h = build_world(cfg)

    assert (screen_w, screen_h) == (cfg["window"]["width"], cfg["window"]["height"])

    players = world.get_entities_with(Position, VehicleControl)
    assert len(players) == 1, f"expected exactly one player, got {len(players)}"
    player = players[0]
    pos = world.get_component(player, Position)
    rect = world.get_component(player, RectRender)
    drift = world.get_component(player, Drift)
    assert rect is not None and rect.width == cfg["player"]["width"]
    assert drift is not None and drift.max_push == cfg["drift"]["max_push"]
    expected_x = screen_w // 2 - cfg["player"]["width"] // 2
    assert pos.x == expected_x, f"player not centred: {pos.x} != {expected_x}"
    assert pos.y == screen_h - cfg["player"]["y_screen_offset"]

    state = world.get_singleton(GameState)
    assert state is not None and state.alive and not state.paused
    assert state.distance_km == 0.0 and state.drift_count == 0

    road = world.get_singleton(RoadSurface)
    assert road is not None and road.width == cfg["road"]["width"] + 150

    xs = sorted(world.get_component(e, Position).x
                for e in world.get_entities_with(Position, LineRender))
    road_left = screen_w // 2 - cfg["road"]["width"] // 2
    road_right = screen_w // 2 + cfg["road"]["width"] // 2
    assert xs == [road_left, road_right], f"edge lines misplaced: {xs}"

    dash = world.get_singleton(DashedLineRender)
    assert dash is not None
    assert dash.dash_length == cfg["road"]["center_dash_length"]
    assert dash.gap_length == cfg["road"]["center_gap_length"]

    kinds = [type(s).__name__ for s in world.systems]
    expected = ["InputSystem", "DriftSystem", "CollisionSystem", "ScrollSystem",
                "DecorationSpawnSystem", "DecorationScrollSystem"]
    assert kinds == expected, f"system order changed: {kinds}"
    return (f"world assembled: player@{pos.x:.0f},{pos.y:.0f}, road edges {road_left}/{road_right}, "
            f"{len(world.systems)} systems in order")


def _system(world, cls):
    for system in world.systems:
        if isinstance(system, cls):
            return system
    raise AssertionError(f"{cls.__name__} not registered")


def check_systems_flow() -> str:
    """里程累积、漂移推挤、暂停冻结、出界判负、装饰物生成与回收。"""
    cfg = load_config("config.json")
    world, screen_w, _ = build_world(cfg)
    state = world.get_singleton(GameState)
    player = world.get_entities_with(Position, VehicleControl)[0]
    pos = world.get_component(player, Position)
    drift = world.get_component(player, Drift)
    scroll = _system(world, ScrollSystem)
    drift_sys = _system(world, DriftSystem)
    collision = _system(world, CollisionSystem)

    # 1) 滚动系统：每帧固定累加 scroll_speed * distance_factor，虚线段按周期回绕
    step = cfg["road"]["scroll_speed"] * cfg["road"]["distance_factor"]
    dash = world.get_singleton(DashedLineRender)
    period = dash.dash_length + dash.gap_length
    frames = 10
    for _ in range(frames):
        scroll.update(world, 1 / 60)
        assert 0 <= dash.offset_y < period, f"dash offset out of wrap range: {dash.offset_y}"
    assert math.isclose(state.distance_km, frames * step, rel_tol=1e-9), \
        f"distance mismatch: {state.distance_km} != {frames * step}"

    # 2) 漂移系统：把推挤固定成 1px/帧（paused=False, distance 已归零）后应逐帧可数
    state.distance_km = 0.0
    start_x = pos.x = screen_w / 2
    drift.chance, drift.min_push, drift.max_push = 1.0, 1.0, 1.0
    random.seed(2026)
    drift_frames = 12
    for _ in range(drift_frames):
        before = pos.x
        drift_sys.update(world, 1 / 60)
        assert math.isclose(abs(pos.x - before), 1.0, abs_tol=1e-9), "drift push not 1px"
    assert state.drift_count == drift_frames, f"drift not counted: {state.drift_count}"
    # 方向是随机的，位移会互相抵消，但每帧只应移动 1px
    assert abs(pos.x - start_x) <= drift_frames, "drift moved further than one push per frame"

    # 3) 暂停：滚动与漂移都必须冻结
    snapshot = (state.distance_km, state.drift_count, pos.x, dash.offset_y)
    state.paused = True
    scroll.update(world, 1 / 60)
    drift_sys.update(world, 1 / 60)
    assert (state.distance_km, state.drift_count, pos.x, dash.offset_y) == snapshot, \
        "paused state still advanced"
    state.paused = False

    # 4) 碰撞：贴到任一侧边线即判负（之后系统不再推进）
    road_left = screen_w // 2 - cfg["road"]["width"] // 2
    road_right = screen_w // 2 + cfg["road"]["width"] // 2
    edge_w = cfg["road"]["edge_line_width"]
    pos.x = road_left + edge_w
    collision.update(world, 1 / 60)
    assert not state.alive, "left edge collision not detected"
    state.alive = True
    pos.x = road_right - edge_w - cfg["player"]["width"]
    collision.update(world, 1 / 60)
    assert not state.alive, "right edge collision not detected"
    state.alive = True

    # 5) 装饰物：满一个 spawn_interval 后生成在路外，滚动 140 帧后全部回收
    spawn = _system(world, DecorationSpawnSystem)
    deco_scroll = _system(world, DecorationScrollSystem)
    random.seed(7)
    for _ in range(cfg["decorations"]["spawn_interval"]):
        spawn.update(world, 1 / 60)
    decos = world.get_entities_with(Position, Decoration)
    assert decos, "no decoration spawned after a full interval"
    for entity in decos:
        deco = world.get_component(entity, Decoration)
        deco_pos = world.get_component(entity, Position)
        assert deco.side in ("left", "right")
        if deco.side == "left":
            assert deco_pos.x <= road_left - 50
        else:
            assert deco_pos.x >= road_right + 20
        assert deco_pos.y == -40, "decoration should start above the screen"

    for _ in range(140):
        deco_scroll.update(world, 1 / 60)
    assert not world.get_entities_with(Position, Decoration), \
        "off-screen decorations were not recycled"

    return (f"{frames} scroll frames = {frames * step:.2f} km, "
            f"drift {drift_frames}x1px, pause frozen, both edges lethal, "
            f"{len(decos)} decorations spawned+recycled")


# --------------------------------------------------------------------- 入口
def main() -> int:
    checks = [
        ("config", check_config),
        ("world assembly", check_world_assembly),
        ("systems flow", check_systems_flow),
    ]
    passed: list[str] = []
    for name, fn in checks:
        try:
            passed.append(fn())
        except Exception as exc:  # noqa: BLE001
            print(f"selfcheck FAIL: {name} -> {type(exc).__name__}: {exc}")
            return 1
    print("selfcheck ok: " + "; ".join(passed))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
