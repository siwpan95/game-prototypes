"""撤销（undo）逆操作正确性测试 —— 无头运行，无需 tkinter。

覆盖三个场景：
  1) 超时判负后撤销：应复活并回滚计时，且不会在下一 tick 瞬间再次判负
  2) 撤销应精确回滚 连击 / 分数 / 计时（真正逆操作，而非仅把 combo 清 0）
  3) 正常胜利后撤销：应复活并恢复棋盘

运行：python tests/test_undo.py   （在 G:/mahjong 根目录下）
"""
from __future__ import annotations

import os
import sys
import types

# ---- 无头环境：用桩对象替换 tkinter.Tk，避免 GUI 依赖 ----
import tkinter as _tk

_STUB = types.SimpleNamespace(
    title=lambda *a, **k: None,
    configure=lambda *a, **k: None,
    bind=lambda *a, **k: None,
    after=lambda *a, **k: None,
    update_idletasks=lambda *a, **k: None,
    minsize=lambda *a, **k: None,
)
_tk.Tk = lambda *a, **k: _STUB  # type: ignore

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from models.game_state import GameMode, GameState  # noqa: E402
from models.tile import Suit, Tile  # noqa: E402
from services.layouts import LayoutKind  # noqa: E402
from allin_engine.core.event_bus import EventBus  # noqa: E402
from viewmodel.game_viewmodel import GameViewModel  # noqa: E402


def build_vm() -> GameViewModel:
    """构造一个不依赖 Tk 的 ViewModel（__init__ 需要 root，这里绕过）。"""
    vm = GameViewModel.__new__(GameViewModel)
    vm._layout = LayoutKind.LINK_FLAT
    vm._time_limit = 300
    vm._init_hints = 3
    vm._init_shuffles = 3
    vm.state = GameState(mode=GameMode.LINK, time_limit=300)
    vm._bus = EventBus()
    vm._legacy_listeners = []
    vm.start_new_game(layout=LayoutKind.LINK_FLAT, mode=GameMode.LINK)
    return vm


def clear_board(vm: GameViewModel) -> None:
    st = vm.state
    for p in list(st.board.occupied_positions()):
        st.board.remove(p)


def wan() -> Tile:
    return Tile(name="一万", short="1万", suit=Suit.CHAR, rank=1)


def test_undo_after_timeout():
    vm = build_vm()
    st = vm.state
    clear_board(vm)
    for c in (0, 1, 3, 4, 6, 7):
        st.board.place((0, 0, c), wan())  # 3 对，避免一次匹配即清空

    vm.select((0, 0, 0))
    vm.select((0, 0, 1))
    assert st.combo == 1, st.combo
    assert st.board.remaining() == 4 and not st.won

    # 模拟超时判负
    st.elapsed = st.time_limit
    vm.tick(0.001)
    assert st.lost and not st.running, "应超时判负"

    # 撤销：应复活 + 回滚计时 + 恢复棋盘
    vm.undo()
    assert st.running and not st.lost, "撤销应复活"
    assert st.elapsed < st.time_limit, f"elapsed 应回滚, got {st.elapsed}"
    assert st.board.remaining() == 6, f"棋盘应恢复6张, got {st.board.remaining()}"

    # 关键：撤销后下一 tick 不应瞬间再次判负
    vm.tick(0.001)
    assert st.running and not st.lost, "撤销后不应瞬间再判负"
    print("PASS [1] 超时撤销复活 + 计时回滚 + 棋盘复原，无瞬间再判负")


def test_undo_exact_rollback():
    vm = build_vm()
    st = vm.state
    clear_board(vm)

    # 预设一段已有的连击/计时状态
    st.combo = 3
    st.last_match_at = 5.0
    st.elapsed = 5.0
    score0 = st.score

    # 放两对，避免一次匹配即清空触发胜利
    st.board.place((0, 0, 3), wan())
    st.board.place((0, 0, 4), wan())
    st.board.place((0, 0, 6), wan())
    st.board.place((0, 0, 7), wan())
    st.elapsed = 5.5  # dt=0.5<窗口 -> combo_lvl=3 -> combo=4
    elapsed_before_match = st.elapsed

    vm.select((0, 0, 3))
    vm.select((0, 0, 4))
    assert st.combo == 4, st.combo
    assert st.score > score0 and not st.won

    vm.undo()
    assert st.combo == 3, f"combo 应回滚到3, got {st.combo}"
    assert st.score == score0, f"score 应回滚, got {st.score}"
    assert abs(st.elapsed - elapsed_before_match) < 1e-9, \
        f"elapsed 应回滚到匹配前, got {st.elapsed}"
    print("PASS [2] 撤销精确回滚 连击/分数/计时")


def test_undo_rolls_back_win_bonus():
    """胜利时加的通关时间奖励，撤销后也应一并回滚。"""
    vm = build_vm()
    st = vm.state
    clear_board(vm)
    st.elapsed = 100.0  # 剩余时间多 -> 奖励分高
    st.board.place((0, 0, 0), wan())
    st.board.place((0, 0, 1), wan())
    vm.select((0, 0, 0))
    vm.select((0, 0, 1))
    assert st.won and not st.running
    assert st.score > 0, "应包含通关时间奖励"

    score_won = st.score
    vm.undo()
    # 撤销后分数回到匹配前（奖励分已扣除），且棋盘恢复2张、重新可玩
    assert st.score == 0, f"撤销后奖励分应回滚, got {st.score} (won时 {score_won})"
    assert st.running and not st.won and st.board.remaining() == 2
    print("PASS [4] 撤销回滚通关时间奖励分")


def test_undo_after_win():
    vm = build_vm()
    st = vm.state
    clear_board(vm)
    st.board.place((0, 0, 0), wan())
    st.board.place((0, 0, 1), wan())
    vm.select((0, 0, 0))
    vm.select((0, 0, 1))
    assert st.won and not st.running

    vm.undo()
    assert st.running and not st.won, "胜利后撤销应复活"
    assert st.board.remaining() == 2, f"棋盘应恢复2张, got {st.board.remaining()}"
    print("PASS [3] 胜利后撤销复活，棋盘恢复2张")


if __name__ == "__main__":
    test_undo_after_timeout()
    test_undo_exact_rollback()
    test_undo_after_win()
    test_undo_rolls_back_win_bonus()
    print("ALL_TESTS_PASS")
