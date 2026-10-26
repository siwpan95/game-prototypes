# -*- coding: utf-8 -*-
"""卡瑞玛拉：枯肢之下 —— 无头自检（不初始化 pygame、不开窗口）。

    python selfcheck.py

``main.py`` 顶层就 ``pygame.init()`` + ``set_mode()``，不能 import；本自检只用
不依赖 pygame 的纯逻辑层：

* ``core/map_data.py``      —— 字符网格地图（加载/替换/区域替换/越界填充）
* ``core/event_bus.py``     —— 事件总线（顺序、异常隔离、递归保护）
* ``core/mod_loader.py``    —— Mod/地图目录扫描（base + 3 个 DLC）
* ``components/sanity.py`` + ``systems/sanity_system.py`` —— 理智值钳制与 GAME_OVER

注意：系统 Python 的 site-packages 里装过另一个仓（bloodmusic）的普通包 ``core``，
会抢在本仓 ``core/``（无 ``__init__.py`` 的命名空间包）前面。这里显式把 ``core``
钉到本仓目录，保证用系统 Python 或本仓 ``venv`` 跑，导入的都是本项目的模块。
输出保持 ASCII，避免 Windows 控制台代码页差异把中文打成乱码。
"""
from __future__ import annotations

import contextlib
import io
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


def _pin_local_package(name: str, directory: Path) -> None:
    """把顶层包名钉到本仓目录（对抗 site-packages 里的同名包）。"""
    module = types.ModuleType(name)
    module.__path__ = [str(directory)]
    sys.modules[name] = module


_pin_local_package("core", ROOT / "core")

from components.sanity import Sanity  # noqa: E402
from core.config import COLS, FILL_CHAR, ROWS  # noqa: E402
from core.event_bus import EventBus  # noqa: E402
from core.map_data import MapData  # noqa: E402
from core.mod_loader import ModManager  # noqa: E402
from systems.sanity_system import SanitySystem  # noqa: E402


# --------------------------------------------------------------------- 检查项
def check_map_and_mods() -> str:
    """地图加载/替换语义 + Mod 目录扫描 + 切图后网格仍然自洽。"""
    mods = ModManager()
    mod_ids = sorted(mods.mods)
    assert "base" in mod_ids, f"base mod missing: {mod_ids}"
    assert len(mod_ids) >= 2, f"no DLC mod discovered: {mod_ids}"
    for mod_id in mod_ids:
        mod = mods.get_mod(mod_id)
        assert mod is not None and mod.maps, f"{mod_id} has no map"
        for mdef in mod.maps.values():
            map_path = Path(mod.root_dir) / mdef.map_file
            assert map_path.is_file(), f"{mod_id}/{mdef.map_id}: map file missing ({map_path})"

    card_dirs = mods.all_card_dirs()
    memory_paths = mods.all_memory_paths()
    assert len(card_dirs) >= len(mod_ids), f"too few card dirs: {card_dirs}"
    assert len(memory_paths) >= len(mod_ids), f"too few memory paths: {memory_paths}"
    for path in list(card_dirs) + list(memory_paths):
        assert Path(path).is_dir(), f"mod asset dir missing: {path}"

    found = mods.get_map(None, "mansion")
    assert found, "base mansion map not registered"
    _, mansion = found
    assert mansion.map_file, "mansion MapDef has no map_file"

    grid = MapData()
    assert (len(grid.grid), len(grid.grid[0])) == (ROWS, COLS), "mansion grid size wrong"
    assert grid.get(-1, -1) == FILL_CHAR and grid.get(COLS, ROWS) == FILL_CHAR, \
        "out-of-bounds should read as FILL_CHAR"

    # 替换语义：只改命中 old 的格子，且不越界
    col, row = 3, 5
    original = grid.get(col, row)
    grid.set(col, row, "X")
    assert grid.get(col, row) == "X"
    grid.replace_at(col, row, "墙", "不该生效")
    assert grid.get(col, row) == "X", "replace_at replaced a non-matching tile"
    grid.replace_at(col, row, "X", original)
    assert grid.get(col, row) == original, "replace_at failed to restore tile"
    grid.set(-1, -1, "X")   # 越界写入必须被忽略
    assert grid.get(-1, -1) == FILL_CHAR, "set() wrote out of bounds"

    # 区域替换：矩形内命中才改，矩形外一格都不许动
    snapshot = [row[:] for row in grid.grid]
    base_col, base_row = 2, 2
    for r in range(base_row, base_row + 3):
        for c in range(base_col, base_col + 3):
            grid.set(c, r, "R")
    grid.replace_region(base_col, base_col + 1, base_row, base_row + 1, "R", "S")
    block = [[grid.get(c, r) for c in range(base_col, base_col + 3)]
             for r in range(base_row, base_row + 3)]
    assert block == [["S", "S", "R"], ["S", "S", "R"], ["R", "R", "R"]], \
        f"replace_region touched the wrong cells: {block}"
    for r in range(ROWS):
        for c in range(COLS):
            inside = base_row <= r < base_row + 3 and base_col <= c < base_col + 3
            if not inside:
                assert grid.get(c, r) == snapshot[r][c], \
                    f"replace_region leaked outside its rect at {(c, r)}"

    # 切图：换一张 DLC 地图后网格必须真的不同（且尺寸仍合法）
    dlc = [mid for mid in mod_ids if mid != "base"]
    if dlc:
        mod = mods.get_mod(dlc[0])
        mdef = next(iter(mod.maps.values()))
        switched = MapData(Path(mod.root_dir) / mdef.map_file)
        assert (len(switched.grid), len(switched.grid[0])) == (ROWS, COLS), "DLC grid size wrong"
        assert switched.grid != snapshot, "switching map did not change the grid"

    return (f"{len(mod_ids)} mods discovered, mansion {ROWS}x{COLS} loaded, "
            f"replace_at/region + map reload ok")


def check_event_bus() -> str:
    """事件总线：按序派发、单回调异常不影响其他、递归保护、可退订。"""
    bus = EventBus()
    order: list[tuple[str, object]] = []
    bus.subscribe("E", lambda data: order.append(("a", data)))

    def boom(_data):
        raise RuntimeError("listener exploded")

    bus.subscribe("E", boom)
    bus.subscribe("E", lambda data: order.append(("b", data)))
    # 总线会用 print 报「回调失败」（带 emoji），先接住它：
    # 既避免污染自检输出，也顺带验证失败日志确实打出来了。
    captured = io.StringIO()
    with contextlib.redirect_stdout(captured):
        bus.emit("E", 1)
    assert order == [("a", 1), ("b", 1)], f"dispatch order/isolation broken: {order}"
    assert "E" in captured.getvalue(), "bus did not report the failing listener"

    calls = [0]

    def reentrant(_data):
        calls[0] += 1
        bus.emit("R", "again")  # 同类事件重入必须被递归保护挡掉

    bus.subscribe("R", reentrant)
    bus.emit("R", "first")
    assert calls[0] == 1, f"recursion guard failed, handler ran {calls[0]}x"

    bus.unsubscribe("E", boom)
    assert bus.listener_count("E") == 2, "unsubscribe did not remove the listener"
    bus.clear("E")
    assert not bus.has_listeners("E"), "clear() left listeners behind"
    return "dispatch order, exception isolation, recursion guard, unsubscribe/clear"


class _Player:
    def __init__(self, sanity: Sanity) -> None:
        self._sanity = sanity

    def get(self, comp_type):
        return self._sanity if comp_type is Sanity else None


class _World:
    def __init__(self, player: _Player) -> None:
        self.entities = {"player": player}


def check_sanity_system() -> str:
    """理智组件钳制 + 系统归零判负 + 卡牌恢复接线。"""
    sanity = Sanity(value=100, max_value=100)
    assert sanity.drain(30) == 30 and sanity.value == 70
    assert sanity.recover(10) == 10 and sanity.value == 80
    assert sanity.drain(500) == 80 and sanity.value == 0, "drain should clamp at 0"
    assert sanity.is_depleted and sanity.ratio == 0.0
    assert sanity.recover(500) == 100 and sanity.value == 100, "recover should clamp at max"

    bus = EventBus()
    game_over: list[dict] = []
    bus.subscribe("GAME_OVER", lambda data: game_over.append(data))
    recovers: list[dict] = []
    bus.subscribe("SANITY_RECOVER", lambda data: recovers.append(data))

    sanity.value = 150                      # 越界值必须被系统拉回 [0, max]
    system = SanitySystem(bus)
    system.update(_World(_Player(sanity)), 0.016)
    assert sanity.value == 100, f"system did not clamp value: {sanity.value}"

    sanity.value = 0
    system.update(_World(_Player(sanity)), 0.016)
    system.update(_World(_Player(sanity)), 0.016)
    assert len(game_over) == 1, f"GAME_OVER should fire once, got {len(game_over)}"
    assert game_over[0]["reason"] == "sanity_zero"

    bus.emit("CARD_COLLECTED", {"card_id": "lavender_01"})
    assert recovers and recovers[-1]["amount"] == 15, f"card recovery not wired: {recovers}"
    return "sanity clamp/recover, GAME_OVER once at zero, card->SANITY_RECOVER wiring"


# --------------------------------------------------------------------- 入口
def main() -> int:
    checks = [
        ("map / mods", check_map_and_mods),
        ("event bus", check_event_bus),
        ("sanity system", check_sanity_system),
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
