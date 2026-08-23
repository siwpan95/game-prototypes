# -*- coding: utf-8 -*-
"""
test_engine_foundation — 「我的世界复刻(2D 文字向)」引擎地基独立单元测试。

自包含、可用纯 `python` 运行（不依赖 pytest）。

运行方式（任一）：
  - PYTHONPATH=D:\\allin\\tools python D:\\allin\\example\\tests\\test_engine_foundation.py
  - 直接：python D:\\allin\\example\\tests\\test_engine_foundation.py   (文件顶部已注入 sys.path)

断言基准：严格对照 team-lead 给出的「关键约定」与实现者提供的「实现微调」记录。
所有测试用极简自定义运行器执行：每个用例独立 try/except 计数，互不阻断。
"""

import sys
import os
import importlib

# ── 路径注入与 pygame 模拟交给公共工具（去除硬编码绝对路径）──
import _testutil  # noqa: E402  (导入即把 example/ 与 tools/ 注入 sys.path)
from _testutil import (
    EXAMPLE_DIR, TOOLS_DIR,
    simulate_no_pygame, restore_pygame, _fresh_registry,
)

# ── 导入安全性模拟：强制 pygame 不可用（顶层不得 import pygame）──
# 通过把 sys.modules['pygame'] 设为 None，使任何 `import pygame` 抛 ImportError，
# 验证本例模块与 alloy 在无 pygame 时能正常导入。
sys.modules.pop("pygame", None)
sys.modules["pygame"] = None

# ── 被测模块导入（无 pygame 时必须成功）──
from mcclone.core import geometry# noqa: E402
from mcclone.core.geometry import Vec2i, AABB2D, clamp, lerp  # noqa: E402

from mcclone.core.noise import PerlinNoise        # noqa: E402

from mcclone.core.block_registry import (         # noqa: E402
    BlockRegistry, BlockDef,
    AIR, STONE, DIRT, GRASS, WATER, SAND,
)
from mcclone.core.block_world import BlockWorld   # noqa: E402
from mcclone.core.terrain import TerrainGenerator # noqa: E402

from mcclone.render import text_world_renderer# noqa: E402
from mcclone.render.text_world_renderer import TextWorldRenderer  # noqa: E402

from mcclone.input import input_realtime# noqa: E402
import mcclone._engine as alloy  # noqa: E402  (内联引擎，验证可导入)


# =====================================================================
# 极简运行器
# =====================================================================

_PASSED = 0
_FAILED = 0
_FAILURES = []


def _run(name, fn):
    """执行单个测试用例，捕获异常并计数。"""
    global _PASSED, _FAILED
    try:
        fn()
        _PASSED += 1
        print(f"  [PASS] {name}")
    except Exception as exc:  # noqa: BLE001
        _FAILED += 1
        msg = f"{type(exc).__name__}: {exc}"
        _FAILURES.append((name, msg))
        print(f"  [FAIL] {name} -> {msg}")


# =====================================================================
# 1) geometry 基础（地基，附带覆盖）
# =====================================================================

def test_geometry_clamp():
    assert clamp(5, 0, 10) == 5
    assert clamp(-1, 0, 10) == 0
    assert clamp(11, 0, 10) == 10
    assert clamp(3.5, 0, 10) == 3.5


def test_geometry_lerp():
    assert lerp(0, 10, 0) == 0
    assert lerp(0, 10, 1) == 10
    assert abs(lerp(0, 10, 0.5) - 5.0) < 1e-9


def test_geometry_vec2i():
    a = Vec2i(1, 2)
    b = Vec2i(3, 4)
    assert (a + b) == Vec2i(4, 6)
    assert (b - a) == Vec2i(2, 2)
    assert a == Vec2i(1, 2)
    assert hash(a) == hash(Vec2i(1, 2))
    assert a.as_tuple() == (1, 2)
    assert Vec2i.from_tuple((7, 8)) == Vec2i(7, 8)


def test_geometry_aabb():
    box = AABB2D(0, 0, 10, 20)
    assert box.contains(0, 0) and box.contains(10, 20) and box.contains(5, 10)
    assert not box.contains(-1, 0) and not box.contains(11, 0)
    assert box.clamp_point(-5, 30) == (0, 20)
    assert box.width == 10 and box.height == 20
    assert box.intersects(AABB2D(5, 5, 15, 25))
    assert not box.intersects(AABB2D(11, 0, 20, 5))


# =====================================================================
# 2) noise — PerlinNoise 确定性 / 范围
# =====================================================================

def test_noise_deterministic_same_seed():
    p1 = PerlinNoise(42)
    p2 = PerlinNoise(42)
    for x in range(0, 20):
        for y in range(0, 20):
            v1 = p1.noise(x * 0.13 + 0.5, y * 0.27 + 0.3)
            v2 = p2.noise(x * 0.13 + 0.5, y * 0.27 + 0.3)
            assert v1 == v2, f"noise differs at ({x},{y}) for same seed"
            f1 = p1.fbm(x * 0.13 + 0.5, y * 0.27 + 0.3)
            f2 = p2.fbm(x * 0.13 + 0.5, y * 0.27 + 0.3)
            assert f1 == f2, f"fbm differs at ({x},{y}) for same seed"


def test_noise_different_seed_differs():
    p0 = PerlinNoise(0)
    p1 = PerlinNoise(1)
    differs = False
    for x in range(0, 30):
        for y in range(0, 30):
            if p0.noise(x * 0.13 + 0.5, y * 0.27 + 0.3) != \
               p1.noise(x * 0.13 + 0.5, y * 0.27 + 0.3):
                differs = True
                break
        if differs:
            break
    assert differs, "noise for seed 0 and seed 1 should differ somewhere"


def test_noise_range_within_bounds():
    tol = 1e-6
    for seed in range(0, 5):
        p = PerlinNoise(seed)
        for x in range(0, 50):
            for y in range(0, 50):
                v = p.noise(x * 0.13 + 0.5, y * 0.27 + 0.3)
                assert -1.0 - tol <= v <= 1.0 + tol, f"noise out of [-1,1]: {v} seed={seed}"
                f = p.fbm(x * 0.13 + 0.5, y * 0.27 + 0.3)
                assert -1.0 - tol <= f <= 1.0 + tol, f"fbm out of [-1,1]: {f} seed={seed}"


# =====================================================================
# 3) block_registry
# =====================================================================

def test_registry_load_defaults_six_blocks():
    reg = _fresh_registry()
    ids = reg.ids()
    assert ids == [0, 1, 2, 3, 4, 5], f"expected ids 0..5, got {ids}"


def test_registry_air_properties():
    reg = _fresh_registry()
    air = reg.get(0)
    assert air.solid is False, "air must be non-solid"
    assert air.transparent is True, "air must be transparent"


def test_registry_get_by_name():
    reg = _fresh_registry()
    grass = reg.get_by_name("grass")
    assert grass.id == 3, f"grass id expected 3, got {grass.id}"
    assert grass.glyph == '"', "grass glyph expected '\"'"


def test_registry_from_json_matches_defaults():
    json_path = os.path.join(EXAMPLE_DIR, "data", "blocks.default.json")
    reg_json = BlockRegistry.from_json(json_path)
    reg_def = _fresh_registry()
    assert reg_json.ids() == reg_def.ids(), "from_json ids mismatch with load_defaults"
    # 逐块核对关键属性一致
    for bid in reg_def.ids():
        a = reg_def.get(bid)
        b = reg_json.get(bid)
        assert a.name == b.name and a.glyph == b.glyph and a.color == b.color, \
            f"block {bid} differs between from_json and load_defaults"


# =====================================================================
# 4) block_world
# =====================================================================

def test_world_set_get_roundtrip():
    w = BlockWorld(16, 16)
    w.set(3, 4, 0, SAND)
    assert w.get(3, 4, 0) == SAND
    w.set(3, 4, 0, 0)  # 空气从稀疏表移除
    assert w.get(3, 4, 0) == AIR


def test_world_out_of_bounds_returns_air():
    w = BlockWorld(16, 16)
    assert w.get(-1, 0, 0) == AIR
    assert w.get(16, 0, 0) == AIR
    assert w.get(0, 16, 0) == AIR
    assert w.get(0, 0, 5) == AIR  # z 越界（depth=1）
    w.set(100, 100, 0, STONE)     # 越界 set 静默忽略
    assert w.get(100, 100, 0) == AIR


def test_world_in_bounds():
    w = BlockWorld(64, 24)
    assert w.in_bounds(0, 0, 0) is True
    assert w.in_bounds(63, 23, 0) is True
    assert w.in_bounds(64, 0, 0) is False
    assert w.in_bounds(0, 24, 0) is False


def test_world_fill_rect():
    w = BlockWorld(16, 16)
    w.fill_rect(0, 0, 3, 3, DIRT)
    for x in range(4):
        for y in range(4):
            assert w.get(x, y, 0) == DIRT
    assert w.get(4, 4, 0) == AIR
    # 反向坐标
    w.fill_rect(7, 7, 5, 5, STONE)
    for x in range(5, 8):
        for y in range(5, 8):
            assert w.get(x, y, 0) == STONE


def test_world_to_from_dict_roundtrip():
    w = BlockWorld(16, 16)
    w.set(1, 1, 0, STONE)
    w.set(2, 3, 0, GRASS)
    w.set(5, 5, 0, WATER)
    d = w.to_dict()
    assert d["width"] == 16 and d["height"] == 16 and d["depth"] == 1
    w2 = BlockWorld.from_dict(d)
    assert w2.to_dict() == d, "to_dict/from_dict roundtrip mismatch"
    assert w2.get(1, 1, 0) == STONE
    assert w2.get(2, 3, 0) == GRASS
    assert w2.get(5, 5, 0) == WATER


def test_world_chunk_serialize_roundtrip():
    w = BlockWorld(64, 64)
    # 在 chunk(0,0) size=8 内填一个可识别图案
    for r in range(8):
        for c in range(8):
            bid = (r + c) % 6
            w.set(c, 63 - r, 0, bid)  # 第0行对应最大 world y
    data1 = w.serialize_chunk(0, 0, 8)
    assert set(data1.keys()) == {"cx", "cy", "size", "blocks"}
    assert data1["size"] == 8 and len(data1["blocks"]) == 8 and len(data1["blocks"][0]) == 8
    w2 = BlockWorld(64, 64)
    w2.load_chunk(0, 0, 8, data1)
    data2 = w2.serialize_chunk(0, 0, 8)
    assert data1 == data2, "serialize_chunk -> load_chunk -> serialize_chunk mismatch"


def test_world_bounds_aabb():
    w = BlockWorld(64, 24)
    b = w.bounds()
    assert isinstance(b, AABB2D)
    assert (b.min_x, b.min_y, b.max_x, b.max_y) == (0, 0, 63, 23)
    assert b.width == 63 and b.height == 23


# =====================================================================
# 5) terrain — 确定性 / 分层 / 水面
# =====================================================================

def _land_surface_top(w, x, height):
    """返回某列最高处的『陆地表层』方块 y（grass 或 sand），无则 -1。"""
    for y in range(height - 1, -1, -1):
        bid = w.get(x, y, 0)
        if bid in (GRASS, SAND):
            return y
    return -1


def test_terrain_deterministic():
    reg = _fresh_registry()
    g1 = TerrainGenerator(reg, seed=7)
    w1 = g1.generate(64, 24)
    g2 = TerrainGenerator(reg, seed=7)
    w2 = g2.generate(64, 24)
    assert w1.to_dict() == w2.to_dict(), "generate(64,24) not deterministic for same seed"


def test_terrain_has_water():
    reg = _fresh_registry()
    g = TerrainGenerator(reg, seed=7)
    w = g.generate(64, 24)
    water = sum(1 for x in range(64) for y in range(24) if w.get(x, y, 0) == WATER)
    assert water >= 1, "expected at least one water(4) block (low columns should be flooded)"


def test_terrain_layering():
    reg = _fresh_registry()
    g = TerrainGenerator(reg, seed=7)
    w = g.generate(64, 24)
    grass_tops = 0
    sand_tops = 0
    for x in range(64):
        top = _land_surface_top(w, x, 24)
        if top < 0:
            continue
        tid = w.get(x, top, 0)
        if tid == GRASS:
            grass_tops += 1
            assert w.get(x, top - 1, 0) == DIRT, f"grass col {x}: y={top}-1 should be dirt"
            assert w.get(x, top - 2, 0) == DIRT, f"grass col {x}: y={top}-2 should be dirt"
            assert w.get(x, top - 3, 0) == STONE, f"grass col {x}: y={top}-3 should be stone"
        elif tid == SAND:
            sand_tops += 1
            assert w.get(x, top - 1, 0) == DIRT, f"sand col {x}: y={top}-1 should be dirt"
            assert w.get(x, top - 3, 0) == STONE, f"sand col {x}: y={top}-3 should be stone"
        else:
            raise AssertionError(f"unexpected land-top id {tid} at col {x}, y={top}")
    assert grass_tops >= 1, "expected at least one grass-topped column"
    assert sand_tops >= 1, "expected at least one sand(beach)-topped column near water"


def test_terrain_large_no_crash():
    reg = _fresh_registry()
    g = TerrainGenerator(reg, seed=1)
    w = g.generate(128, 48)
    assert w.width == 128 and w.height == 48, "generate(128,48) world size mismatch"


# =====================================================================
# 6) text_world_renderer — 按「关键约定」断言
#    （当前实现 render 无 use_ansi 参数、且无 render_line 方法 → 失败将路由工程师）
# =====================================================================

def test_renderer_render_no_ansi_24x64():
    reg = _fresh_registry()
    w = BlockWorld(64, 24)
    r = TextWorldRenderer(reg)
    out = r.render(w, AABB2D(0, 0, 63, 23), use_ansi=False)
    lines = out.rstrip("\n").split("\n")
    assert len(lines) == 24, f"use_ansi=False expected 24 lines, got {len(lines)}"
    for i, ln in enumerate(lines):
        assert len(ln) == 64, f"use_ansi=False line {i} expected 64 chars, got {len(ln)}"


def test_renderer_no_ansi_glyph_matches_registry():
    reg = _fresh_registry()
    w = BlockWorld(64, 24)
    w.set(5, 5, 0, STONE)  # 已知方块
    r = TextWorldRenderer(reg)
    out = r.render(w, AABB2D(0, 0, 63, 23), use_ansi=False)
    assert "\033[" not in out, "use_ansi=False output must not contain ANSI escapes"
    lines = out.rstrip("\n").split("\n")
    row = 23 - 5   # viewport 顶部 = max_y(23)，向下递减
    col = 5 - 0
    ch = lines[row][col]
    expected = reg.get(STONE).glyph
    assert ch == expected, f"glyph at world(5,5) expected {expected!r}, got {ch!r}"


def test_renderer_render_line_width():
    reg = _fresh_registry()
    w = BlockWorld(64, 24)
    r = TextWorldRenderer(reg)
    line = r.render_line(w, AABB2D(0, 0, 63, 23), 23)
    assert len(line) == 64, f"render_line length expected 64 (viewport width), got {len(line)}"


def test_renderer_render_ansi_contains_escape():
    reg = _fresh_registry()
    w = BlockWorld(64, 24)
    w.set(0, 0, 0, GRASS)
    r = TextWorldRenderer(reg)
    out = r.render(w, AABB2D(0, 0, 63, 23), use_ansi=True)
    assert "\033[" in out, "use_ansi=True output must contain ANSI escape sequence"


# =====================================================================
# 7) input_realtime — 导入安全 / 报错分支 / 成功路径
# =====================================================================

def test_import_safety_without_pygame():
    # 顶层已模拟 pygame=None，下列模块必须可成功（重新 import 不抛异常）
    for mod in ["mcclone.core.geometry", "mcclone.core.noise", "mcclone.core.block_registry",
                "mcclone.core.block_world", "mcclone.core.terrain",
                "mcclone.render.text_world_renderer", "mcclone.input.input_realtime"]:
        importlib.import_module(mod)
    import mcclone._engine as alloy  # 必须成功
    assert alloy is not None


def test_input_pygame_key_source_raises_without_pygame():
    saved = simulate_no_pygame()
    try:
        try:
            input_realtime.PygameKeyStateSource()
            raise AssertionError("PygameKeyStateSource() must raise when pygame unavailable")
        except RuntimeError as e:
            assert "pygame" in str(e).lower(), \
                f"RuntimeError message should mention 'pygame', got: {e!r}"
    finally:
        restore_pygame(saved)


def test_realtime_manager_success_or_skip():
    importlib.reload(input_realtime)
    if input_realtime.pygame is None:
        # pygame 不可用 → 按规格仅验证报错分支（已由上一用例覆盖），此处视为通过
        return
    # pygame 可用：构造并调用 is_down/update 不应报错
    from mcclone._engine import InputManager
    base = InputManager()
    key_source = input_realtime.PygameKeyStateSource()
    mgr = input_realtime.RealtimeInputManager(base, key_source)
    assert mgr.is_down(65) is False
    mgr.update()
    assert mgr.pressed_this_frame(65) is False
    # 保留基类文本命令能力不应报错
    cmd = mgr.get_command()
    assert isinstance(cmd, tuple)


# =====================================================================
# 主入口
# =====================================================================

def main():
    print("=" * 70)
    print(" MC-Clone 引擎地基单元测试  (纯 python 运行，无 pytest 依赖)")
    print("=" * 70)

    # 1) geometry
    print("\n[geometry]")
    _run("geometry.clamp", test_geometry_clamp)
    _run("geometry.lerp", test_geometry_lerp)
    _run("geometry.Vec2i", test_geometry_vec2i)
    _run("geometry.AABB2D", test_geometry_aabb)

    # 2) noise
    print("\n[noise]")
    _run("noise.deterministic_same_seed", test_noise_deterministic_same_seed)
    _run("noise.different_seed_differs", test_noise_different_seed_differs)
    _run("noise.range_within_bounds", test_noise_range_within_bounds)

    # 3) block_registry
    print("\n[block_registry]")
    _run("registry.load_defaults_six", test_registry_load_defaults_six_blocks)
    _run("registry.air_properties", test_registry_air_properties)
    _run("registry.get_by_name", test_registry_get_by_name)
    _run("registry.from_json_matches", test_registry_from_json_matches_defaults)

    # 4) block_world
    print("\n[block_world]")
    _run("world.set_get_roundtrip", test_world_set_get_roundtrip)
    _run("world.out_of_bounds_air", test_world_out_of_bounds_returns_air)
    _run("world.in_bounds", test_world_in_bounds)
    _run("world.fill_rect", test_world_fill_rect)
    _run("world.to_from_dict", test_world_to_from_dict_roundtrip)
    _run("world.chunk_roundtrip", test_world_chunk_serialize_roundtrip)
    _run("world.bounds", test_world_bounds_aabb)

    # 5) terrain
    print("\n[terrain]")
    _run("terrain.deterministic", test_terrain_deterministic)
    _run("terrain.has_water", test_terrain_has_water)
    _run("terrain.layering", test_terrain_layering)
    _run("terrain.large_no_crash", test_terrain_large_no_crash)

    # 6) text_world_renderer
    print("\n[text_world_renderer]")
    _run("renderer.render_no_ansi_24x64", test_renderer_render_no_ansi_24x64)
    _run("renderer.no_ansi_glyph", test_renderer_no_ansi_glyph_matches_registry)
    _run("renderer.render_line_width", test_renderer_render_line_width)
    _run("renderer.render_ansi_escape", test_renderer_render_ansi_contains_escape)

    # 7) input_realtime
    print("\n[input_realtime]")
    _run("input.import_safety", test_import_safety_without_pygame)
    _run("input.key_source_raises", test_input_pygame_key_source_raises_without_pygame)
    _run("input.manager_success_or_skip", test_realtime_manager_success_or_skip)

    # 汇总
    total = _PASSED + _FAILED
    print("\n" + "=" * 70)
    print(f" 总计 {total} | 通过 {_PASSED} | 失败 {_FAILED}")
    print("=" * 70)
    if _FAILURES:
        print("\n失败用例明细:")
        for name, msg in _FAILURES:
            print(f"  - {name}: {msg}")
    return _FAILED


if __name__ == "__main__":
    failed = main()
    sys.exit(1 if failed else 0)
