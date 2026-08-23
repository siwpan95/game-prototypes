# -*- coding: utf-8 -*-
"""test_qa_m1_boundary — 严过关独立边界测试（fresh eyes 补充 M1 验收边界）。

目的：不轻信实现者自测，用独立视角补充其未充分覆盖的边界与互逆性，
以独立证明 M1 逻辑正确、可交付。不删除实现者的任何测试。

覆盖：
  - 跳跃高度精确断言（落点比起点高 ≥3 格并落回）
  - 极小世界（视口双向 > 世界）下相机钳制为整世界且不越界
  - 放置到玩家占用格被拒（含跨两列的边界情形）
  - 相邻空气 / 水格可被覆盖（water 被 solid 替换）
  - 屏幕像素 → 世界格 → 屏幕 互逆（top-left 像素精确）
  - 瓦片-文字几何一致性（多格扰动世界，非空格集合一一对应）
  - 高速下落不穿 solid（逐帧断言 AABB 不与任何 solid 重叠）
  - 真实地形 + spawn_player 落地（端到端集成，headless）
  - air 从稀疏表移除（set(...,AIR) 后 get 返回 0）
"""

from __future__ import annotations

import math

from mcclone.core.geometry import AABB2D
from mcclone.core.block_registry import BlockRegistry, AIR, STONE, WATER
from mcclone.core.block_world import BlockWorld
from mcclone.player.player import Player
from mcclone.core.camera import Camera, TILE_SIZE, HUD_TOP, VIEW_OFFSET_X
from mcclone.render.tile_world_renderer import TileWorldRenderer
from mcclone.render.text_world_renderer import TextWorldRenderer
from mcclone.core.event_bus import EventBus, EventTypes
from mcclone.core.terrain import TerrainGenerator
from mcclone.core.noise import PerlinNoise
from mcclone.main_gui import spawn_player


VIEWPORT_TILES = (80, 24)


def _reg():
    reg = BlockRegistry()
    reg.load_defaults()
    return reg


def _ground(w, top_y):
    """填充 x∈[0,w) 的 y∈[0,top_y] 为 stone（地表 top_y）。"""
    world = BlockWorld(w, top_y + 6)
    for x in range(w):
        for y in range(0, top_y + 1):
            world.set(x, y, 0, STONE)
    return world


# ── 1) 跳跃高度精确断言 ────────────────────────────────────────────────
def test_qa_jump_height_precise():
    reg = _reg()
    world = _ground(10, 2)        # 地表 top_y=2，玩家落稳于 fy=3
    p = Player(5.0, 4.0, reg)

    class _FI:
        def __init__(self):
            self.jump = False
        def left(self):
            return False
        def right(self):
            return False
        def jump_pressed(self):
            j = self.jump
            self.jump = False
            return j

    inp = _FI()
    for _ in range(120):           # 先落稳
        p.update(1 / 60, world, inp)
    assert p.on_ground, "落稳后应着地"
    base_y = p.fy

    inp.jump = True                # 触发一次跳跃
    max_y = base_y
    for _ in range(200):
        p.update(1 / 60, world, inp)
        max_y = max(max_y, p.fy)

    jump_h = max_y - base_y
    # 验收 M1-R2④：跳跃约 3–4 格，落点比起点高 ≥3 格
    assert 3.0 <= jump_h <= 4.0, f"跳跃高度应 3–4 格，实际 {jump_h:.3f}"

    # 落回起点附近（同一地面，应精确落回 base_y）
    for _ in range(120):
        p.update(1 / 60, world, inp)
    assert p.on_ground, "跳跃后应落回地面"
    assert abs(p.fy - base_y) < 0.01, f"应落回 fy={base_y}，实际 {p.fy}"


# ── 2) 极小世界相机钳制（视口双向 > 世界）──────────────────────────────
def test_qa_camera_clamp_tiny_world_both_axes():
    reg = _reg()
    world = BlockWorld(10, 8)      # 世界仅 10×8
    bounds = world.bounds()        # min=(0,0) max=(9,7)
    vp = AABB2D(0, 0, VIEWPORT_TILES[0] - 1, VIEWPORT_TILES[1] - 1)  # 79×23
    cam = Camera(vp)
    cam.follow(AABB2D(5, 4, 6, 6))          # 任意目标（中心）
    cam.clamp_to(bounds)
    # 不越界
    assert cam.viewport.min_x >= 0
    assert cam.viewport.max_x <= bounds.max_x
    assert cam.viewport.min_y >= 0
    assert cam.viewport.max_y <= bounds.max_y
    # 视口比世界大 → 钳制为整世界（双向）
    assert cam.viewport.max_x - cam.viewport.min_x == bounds.max_x - bounds.min_x
    assert cam.viewport.max_y - cam.viewport.min_y == bounds.max_y - bounds.min_y


# ── 3) 放置到玩家占用格被拒（含跨两列）────────────────────────────────
def test_qa_place_rejected_on_player_cells():
    reg = _reg()
    world = BlockWorld(10, 10)
    p = Player(5.0, 3.0, reg)      # 占用列 5，行 3,4
    # 正下方占用格
    assert p.try_place(world, 5, 3) is False
    assert p.try_place(world, 5, 4) is False
    # 非占用（脚下 1 格外、水平 1 格外）应可放
    assert p.try_place(world, 3, 6) is True

    # 跨两列情形：fx=5.5 → 占用列 5 与 6
    p2 = Player(5.5, 3.0, reg)
    occ = set(p2._occupied_cells())
    assert (5, 3) in occ and (6, 3) in occ and (5, 4) in occ and (6, 4) in occ
    for (cx, cy) in [(5, 3), (5, 4), (6, 3), (6, 4)]:
        assert p2.try_place(world, cx, cy) is False, f"应拒绝占用格 {cx,cy}"


# ── 4) 相邻空气 / 水格可被覆盖 ────────────────────────────────────────
def test_qa_place_overwrites_water_and_air():
    reg = _reg()
    world = BlockWorld(10, 10)
    world.set(4, 3, 0, WATER)
    p = Player(6.0, 3.0, reg)
    # 覆盖水格
    assert p.try_place(world, 4, 3) is True
    assert world.get(4, 3, 0) == p.held_id
    # 覆盖相邻空气格
    assert p.try_place(world, 3, 3) is True
    assert world.get(3, 3, 0) == p.held_id


# ── 5) 屏幕像素 ↔ 世界格 互逆（top-left 像素精确）─────────────────────
def test_qa_screen_world_inverse_from_pixels():
    reg = _reg()
    vp = AABB2D(10, 5, 89, 28)     # 80×24 瓦片
    renderer = TileWorldRenderer(None, reg)
    cam = Camera(AABB2D(vp.min_x, vp.min_y, vp.max_x, vp.max_y))

    tiles = [(10, 5), (89, 28), (50, 15), (10, 28), (89, 5)]
    for (tx, ty) in tiles:
        px, py = renderer._world_to_screen(tx, ty, vp)
        # 取瓦片左上角像素 → 应反算回同格（精确）
        wx, wy = cam.screen_to_world_cell(px, py)
        assert (wx, wy) == (tx, ty), f"像素({px},{py})反算得 ({wx},{wy})，应为 ({tx},{ty})"
        # 再映射回屏幕，应回到左上角像素（精确）
        px2, py2 = renderer._world_to_screen(wx, wy, vp)
        assert (px2, py2) == (px, py), "互逆应精确回到原像素"


# ── 6) 瓦片-文字几何一致性（多格扰动世界）────────────────────────────
def test_qa_tile_text_geometry_random():
    reg = _reg()
    world = BlockWorld(24, 16)
    # 确定性扰动：按 (x*y)%3 放置不同方块，制造非平凡非空格集合
    for x in range(24):
        for y in range(16):
            m = (x * y) % 3
            if m == 0:
                world.set(x, y, 0, STONE)
            elif m == 1:
                world.set(x, y, 0, WATER)
            # m==2 留空
    vp = AABB2D(0, 0, 23, 15)

    renderer = TileWorldRenderer(None, reg)
    tiles = {(wx, wy) for (wx, wy, _b) in renderer.collect_tiles(world, vp)}

    text = TextWorldRenderer(reg)
    lines = text.render(world, vp, use_ansi=False).rstrip("\n").split("\n")
    text_cells = set()
    for r, line in enumerate(lines):
        world_y = vp.max_y - r
        for c, ch in enumerate(line):
            if ch != " ":
                text_cells.add((vp.min_x + c, world_y))

    assert tiles == text_cells, (
        f"几何不一致: tile-only={tiles - text_cells}, "
        f"text-only={text_cells - tiles}"
    )


# ── 7) 高速下落不穿 solid（逐帧断言）────────────────────────────────
def test_qa_high_fall_no_tunnel():
    reg = _reg()
    world = _ground(12, 3)         # 地表 top_y=3，落点 fy=4
    p = Player(6.0, 80.0, reg)     # 高空下落（远 > MAX_FALL*dt，验证不穿地）

    class _FI:
        def left(self):
            return False
        def right(self):
            return False
        def jump_pressed(self):
            return False

    for _ in range(2000):
        p.update(1 / 60, world, _FI())
        for (cx, cy) in p._occupied_cells():
            assert not p._is_solid(world, cx, cy), f"第{cx},{cy}格进入 solid"
    assert p.on_ground is True
    assert p.fy == 4.0, f"应精确停在 fy=4，实际 {p.fy}"


# ── 8) 真实地形 + spawn_player 落地（端到端集成，headless）────────────
def test_qa_spawn_player_lands_on_real_terrain():
    reg = _reg()
    noise = PerlinNoise(12345)
    gen = TerrainGenerator(reg, 12345, noise)
    world = gen.generate(256, 96, 1)

    p = spawn_player(world, reg)

    class _FI:
        def left(self):
            return False
        def right(self):
            return False
        def jump_pressed(self):
            return False

    landed = False
    for _ in range(1200):
        p.update(1 / 60, world, _FI())
        for (cx, cy) in p._occupied_cells():
            assert not p._is_solid(world, cx, cy), f"spawn 后进入 solid ({cx},{cy})"
        if p.on_ground:
            landed = True
            break
    assert landed, "spawn 后玩家应在合理帧数内落地"
    assert 0.0 <= p.fx < world.width
    assert 0.0 <= p.fy < world.height


# ── 9) air 从稀疏表移除（set(...,AIR) 后 get 返回 0）─────────────────
def test_qa_air_removed_from_sparse():
    reg = _reg()
    world = BlockWorld(10, 10)
    world.set(3, 3, 0, STONE)
    assert world.get(3, 3, 0) == STONE
    world.set(3, 3, 0, AIR)        # 破坏 = 置 0
    assert world.get(3, 3, 0) == 0, "air 应从稀疏表移除（get 返回 0）"


# ── 10) 四类事件均可被订阅者接收（集成）──────────────────────────────
def test_qa_all_events_emitted():
    reg = _reg()
    world = BlockWorld(12, 20)
    for x in range(12):
        for y in range(0, 5):
            world.set(x, y, 0, STONE)
    p = Player(5.0, 12.0, reg)

    bus = EventBus()
    seen = {EventTypes.PLAYER_MOVED: 0, EventTypes.BLOCK_BROKEN: 0,
            EventTypes.BLOCK_PLACED: 0, EventTypes.PLAYER_LANDED: 0}

    def _h(t, d):
        seen[t] += 1

    for et in seen:
        bus.subscribe(et, _h)
    p.event_bus = bus

    class _FI:
        def __init__(self):
            self._right = False
            self._jump = False
        def left(self):
            return False
        def right(self):
            return self._right
        def jump_pressed(self):
            j = self._jump
            self._jump = False
            return j

    inp = _FI()
    # 向右移动触发 MOVED
    inp._right = True
    for _ in range(30):
        p.update(1 / 60, world, inp)
    inp._right = False
    # 落地触发 LANDED（已在下落中）
    for _ in range(600):
        p.update(1 / 60, world, inp)
    # 破坏 / 放置（均选非脚下、非玩家占用的方块格，避免被保护逻辑拒绝）
    p.try_break(world, 1, 4)       # 列1 的 stone（非玩家占用、非脚下支撑格）
    p.try_place(world, 10, 12)     # 远处空气格

    assert seen[EventTypes.PLAYER_MOVED] > 0, "MOVED 应被发出"
    assert seen[EventTypes.PLAYER_LANDED] > 0, "LANDED 应被发出"
    assert seen[EventTypes.BLOCK_BROKEN] > 0, "BROKEN 应被发出"
    assert seen[EventTypes.BLOCK_PLACED] > 0, "PLACED 应被发出"
