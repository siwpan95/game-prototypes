# -*- coding: utf-8 -*-
"""随机地牢重构后的测试（无第三方依赖，标准库自跑）。

    python -m tests.run_tests

钉的核心：**默认路径与旧版行为等价**（同种子逐格一致），
以及**超级引擎路径可用**（真实地牢图 / 骰系规则），且引擎缺失时**优雅回退**。
"""

from __future__ import annotations

import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dungeon import engine as eng  # noqa: E402
from dungeon.game import Game  # noqa: E402
from dungeon.rules import (LOOT_TABLE, BuiltinRules, make_rules)  # noqa: E402
from dungeon.ui import Printer  # noqa: E402
from dungeon.world import (ROOM_EMPTY, ROOM_EXIT, BuiltinWorldSource,  # noqa: E402
                           make_world_source)


# ------------------------------------------------------------ 参照实现 --
def legacy_create_map(size=4, seed=None):
    """旧版 create_map 的**逐字复刻**（用来证明重构没破坏行为契约）。"""
    rng = random.Random(seed) if seed is not None else random
    room_types = [ROOM_EMPTY, "怪物", "宝藏", "陷阱"]
    dungeon = [[rng.choice(room_types) for _ in range(size)] for _ in range(size)]
    exit_pos = (rng.randint(0, size - 1), rng.randint(0, size - 1))
    dungeon[exit_pos[0]][exit_pos[1]] = ROOM_EXIT
    start_pos = (0, 0)
    dungeon[start_pos[0]][start_pos[1]] = ROOM_EMPTY
    while exit_pos == start_pos:
        exit_pos = (rng.randint(0, size - 1), rng.randint(0, size - 1))
        dungeon[exit_pos[0]][exit_pos[1]] = ROOM_EXIT
    return dungeon, start_pos, exit_pos


# ---------------------------------------------------------------- 工具 --
class Scripted:
    """按脚本回放输入、收集输出的 Printer（不打字、不阻塞）。"""

    def __init__(self, answers):
        self.answers = list(answers)
        self.lines = []

    def say(self, text=""):
        self.lines.append(str(text))

    def ask(self, prompt):
        self.say(prompt)
        if not self.answers:
            return "退出"
        return self.answers.pop(0)


def _legacy_is_wellformed(dungeon, start, exit_pos):
    """旧版这一铺是否**自身无 bug**（出生点空地 + 出口恰好一个）。"""
    flat = [c for row in dungeon for c in row]
    return (dungeon[start[0]][start[1]] == ROOM_EMPTY
            and flat.count(ROOM_EXIT) == 1
            and start != exit_pos)


def test_builtin_grid_matches_legacy_exactly():
    """**行为契约**：旧版自身正确的那些种子，内置路径与旧版**逐格一致**。

    旧版有个 latent bug：出口重掷时若又落回 (0,0)，会把出生点覆写成出口并留下
    两个出口（与它自己的注释"出生点设为空地，保证安全"相悖）。新版按注释意图
    修正了，因此这类种子**刻意**不再逐格一致 —— 见下一条测试。
    """
    checked = diverged = 0
    for seed in list(range(200)):
        legacy, lstart, lexit = legacy_create_map(4, seed)
        w = BuiltinWorldSource(size=4).build(seed=seed)
        if not _legacy_is_wellformed(legacy, lstart, lexit):
            diverged += 1
            continue                      # 旧版自身有 bug 的种子，不要求一致
        assert w.meta["grid"] == legacy, f'seed={seed} 网格与旧版不一致'
        assert w.start == f"{lstart[0]},{lstart[1]}", (w.start, lstart)
        assert w.exit_id == f"{lexit[0]},{lexit[1]}", (w.exit_id, lexit)
        checked += 1
    assert checked >= 150, f'可比对的种子太少：{checked}'
    print(f'  ok: 内置路径与旧版逐格一致（{checked} 个种子；'
          f'另有 {diverged} 个种子旧版自身有 bug，已被修正）')


def test_builtin_fixes_legacy_bug():
    """被修正的 bug：出生点**恒为**空地、出口**恰好一个**（旧版在这类种子上不成立）。"""
    bad_seeds = [s for s in range(200)
                 if not _legacy_is_wellformed(*legacy_create_map(4, s))]
    assert bad_seeds, '样本里应存在旧版出错的种子（否则本测试无意义）'
    for seed in bad_seeds:
        w = BuiltinWorldSource(size=4).build(seed=seed)
        assert w.kind_of(w.start) == ROOM_EMPTY, f'seed={seed} 出生点应为空地'
        n_exit = sum(1 for r in w.rooms if w.kind_of(r) == ROOM_EXIT)
        assert n_exit == 1, f'seed={seed} 出口应恰好 1 个，实际 {n_exit}'
    print(f'  ok: 修正旧版 latent bug（{len(bad_seeds)} 个受影响种子，'
          f'出生点恒空地 + 出口唯一）')


def test_builtin_invariants():
    """内置路径不变量：出生点必为空地、出口唯一且不与出生点重合。"""
    for seed in range(30):
        w = BuiltinWorldSource(size=4).build(seed=seed)
        assert w.kind_of(w.start) == ROOM_EMPTY, f'seed={seed} 出生点不是空地'
        exits = [r for r in w.rooms if w.kind_of(r) == ROOM_EXIT]
        assert len(exits) >= 1, f'seed={seed} 没有出口'
        assert w.start != w.exit_id, f'seed={seed} 出生点即出口'
    print('  ok: 内置路径不变量成立（出生点空地 / 有出口 / 不与出生点重合，30 种子）')


def test_builtin_is_deterministic():
    a = BuiltinWorldSource(size=4).build(seed=99)
    b = BuiltinWorldSource(size=4).build(seed=99)
    assert a.meta["grid"] == b.meta["grid"]
    assert a.exit_id == b.exit_id
    print('  ok: 内置路径同种子可复现')


def test_builtin_rules_intervals_match_legacy():
    """内置规则的数值区间与旧版一致（怪 3~8 / 伤 1~atk / 怪伤 2~5 / 陷阱 5~10）。"""
    r = BuiltinRules()
    rng = random.Random(0)
    for _ in range(200):
        assert 3 <= r.monster_hp(rng) <= 8
        assert 1 <= r.player_damage(5, rng) <= 5
        assert 2 <= r.monster_damage(False, rng) <= 5
        assert 0 <= r.monster_damage(True, rng) <= 3
        assert 5 <= r.trap_damage(rng) <= 10
        assert 5 <= r.heal_amount(rng) <= 10
        assert r.pick(LOOT_TABLE, rng) in LOOT_TABLE
        assert r.hits() is True            # 内置无检定层：恒命中
    print('  ok: 内置规则区间与旧版一致，且无检定层（恒命中）')


def test_fallback_when_engine_unavailable():
    """引擎不可用 ⇒ 工厂**回退**内置，不抛异常。"""
    unavailable = eng.SuperEngine(None, "模拟不可用")
    ws = make_world_source("super", unavailable, rooms=6)
    rl = make_rules("super", unavailable)
    assert ws.name == "builtin" and rl.name == "builtin", (ws.name, rl.name)
    print('  ok: 引擎不可用时世界源与规则源都回退内置')


def test_strict_mode_reports_actionable_tip():
    """显式要求却不可用 ⇒ 给出可执行的修复指令（而不是含糊报错）。"""
    unavailable = eng.SuperEngine(None, "模拟不可用")
    ok, tip = eng.ensure(unavailable)
    assert ok is False
    assert "SUPERENGINE_SRC" in tip and "并排" in tip, tip
    print('  ok: strict 模式给出可执行修复指令（含 SUPERENGINE_SRC / 并排放置）')


# ------------------------------------------------- 超级引擎路径（可选）--
def _engine():
    return eng.probe()


def test_super_engine_path_if_available():
    """引擎可用时：真实地牢图（房间数 ≥ 2、出口 ≠ 起点、起点有通路）。"""
    e = _engine()
    if not eng.ready(e):
        print(f'  skip: 超级引擎不可用（{e.error or e.reason}）')
        return
    ws = make_world_source("super", e, rooms=6)
    assert ws.name == "superengine"
    for seed in (0, 7):
        w = ws.build(seed=seed)
        assert len(w.rooms) >= 2, f'seed={seed} 房间太少'
        assert w.start != w.exit_id, f'seed={seed} 起点即出口'
        assert w.kind_of(w.exit_id) == ROOM_EXIT
        assert w.kind_of(w.start) == ROOM_EMPTY
        assert w.neighbors_of(w.start), f'seed={seed} 起点是孤岛'
    print(f'  ok: 超级引擎路径产出真实地牢图（{len(w.rooms)} 房间，起点有通路）')


def test_super_rules_share_builtin_intervals():
    """引擎规则与内置规则**区间重合** —— 换源不导致难度失衡。"""
    e = _engine()
    if not eng.ready(e):
        print(f'  skip: 超级引擎不可用（{e.error or e.reason}）')
        return
    r = make_rules("super", e)
    assert r.name == "superengine"
    for _ in range(200):
        assert 3 <= r.monster_hp() <= 8, '怪物生命应落在内置区间 3~8'
        assert 2 <= r.monster_damage(False) <= 5, '怪物伤害应落在 2~5'
        assert 5 <= r.trap_damage() <= 10
        assert 5 <= r.heal_amount() <= 10
        assert 1 <= r.player_damage(5) <= 5
        assert r.hits() in (True, False)     # 有检定层：可能失手
    print('  ok: 引擎规则区间与内置重合，且带 d20 检定层')


class _FixedWorldSource:
    """把已构造好的 World 直接当源用（测试替身）。"""

    def __init__(self, world):
        self.world = world

    def build(self, seed=None, **kw):
        return self.world


def test_game_runs_to_escape_with_scripted_input():
    """脚本化输入跑完整一局（内置路径），能走到通关。"""
    w = BuiltinWorldSource(size=2).build(seed=5)
    start = w.start
    nb = w.neighbors_of(start)
    w.rooms[nb[0]].kind = ROOM_EXIT
    w.exit_id = nb[0]
    # 网格模式：按邻居相对坐标推出方向词
    sr, sc = w.rooms[start].pos
    tr, tc = w.rooms[nb[0]].pos
    if tr > sr:
        direction = "南"
    elif tr < sr:
        direction = "北"
    elif tc > sc:
        direction = "东"
    else:
        direction = "西"
    ui = Scripted(["n", direction])
    g = Game(_FixedWorldSource(w), BuiltinRules(), ui)
    result = g.play()
    assert result == "escaped", (result, ui.lines[-6:])
    print(f'  ok: 脚本化输入可完整通关（escaped，走{direction}）')


def main() -> int:
    tests = [(n, f) for n, f in sorted(globals().items())
             if n.startswith('test_') and callable(f)]
    failed = []
    for name, fn in tests:
        try:
            fn()
        except AssertionError as exc:
            failed.append((name, exc))
            print(f'  FAIL: {name}: {exc}')
        except Exception as exc:                            # noqa: BLE001
            failed.append((name, exc))
            print(f'  ERROR: {type(exc).__name__}: {exc}')
    print('=' * 60)
    print(f'[random-dungeon] {len(tests) - len(failed)}/{len(tests)} 通过')
    if failed:
        print('ALL_DUNGEON_TESTS_FAILED')
        return 1
    print('ALL_DUNGEON_TESTS_PASSED')
    return 0


if __name__ == '__main__':
    sys.exit(main())
