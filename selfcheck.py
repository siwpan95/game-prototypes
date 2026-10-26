"""Headless self-check for the Mahjong Solitaire game logic.

Only the pure Model/Service/ViewModel layers are imported; ``views`` and
``tkinter`` are never touched, so no window is opened.

Checks:
  1. Standard 144-tile deck composition and season/flower grouping.
  2. All four layouts produce 144 unique slots with the documented layer counts.
  3. Free-tile blocking and the <=2-turn link rule (including the blocked case).
  4. ViewModel state advance: match -> score/move/history, then undo restores.

Run from the project root::

    python selfcheck.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models.board import Board
from models.game_state import GameMode, GameState
from models.tile import Suit, Tile
from services.deck import build_standard_deck
from services.layouts import LayoutKind, generate_layout
from services.matcher import can_link, is_free, tile_match
from viewmodel.game_viewmodel import GameViewModel


def t(name, short, suit, rank=0, group=""):
    return Tile(name=name, short=short, suit=suit, rank=rank, group=group)


def check_deck():
    deck = build_standard_deck()
    if len(deck) != 144:
        raise AssertionError("deck size is %d, expected 144" % len(deck))

    counts = {}
    for tile in deck:
        counts[tile.name] = counts.get(tile.name, 0) + 1
    for suit_cn in ("筒", "条", "万"):
        for rank in range(1, 10):
            name = "零一二三四五六七八九"[rank] + suit_cn
            if counts.get(name) != 4:
                raise AssertionError("%s should have 4 copies" % name)
    for name in ("东", "南", "西", "北", "中", "发", "白"):
        if counts.get(name) != 4:
            raise AssertionError("%s should have 4 copies" % name)
    for name in ("春", "夏", "秋", "冬", "梅", "兰", "菊", "竹"):
        if counts.get(name) != 1:
            raise AssertionError("%s should have exactly 1 copy" % name)

    spring = next(x for x in deck if x.name == "春")
    winter = next(x for x in deck if x.name == "冬")
    plum = next(x for x in deck if x.name == "梅")
    orchid = next(x for x in deck if x.name == "兰")
    one_dot = next(x for x in deck if x.name == "一筒")
    two_dot = next(x for x in deck if x.name == "二筒")
    if not spring.matches(winter) or not plum.matches(orchid):
        raise AssertionError("season/flower group matching is broken")
    if spring.matches(plum):
        raise AssertionError("season and flower groups must not cross-match")
    if not one_dot.matches(one_dot) or one_dot.matches(two_dot):
        raise AssertionError("same/different tile matching is broken")


def check_layouts():
    expected_layer_counts = {
        LayoutKind.TURTLE: {0: 86, 1: 40, 2: 14, 3: 4},
        LayoutKind.PYRAMID: {0: 96, 1: 32, 2: 12, 3: 4},
        LayoutKind.RECTANGLE: {0: 80, 1: 36, 2: 20, 3: 8},
    }
    for kind in LayoutKind:
        slots = generate_layout(kind)
        if len(slots) != 144:
            raise AssertionError("%s layout has %d slots" % (kind, len(slots)))
        if len(set(slots)) != 144:
            raise AssertionError("%s layout has duplicate slots" % kind)
        if kind in expected_layer_counts:
            counts = {}
            for layer, _r, _c in slots:
                counts[layer] = counts.get(layer, 0) + 1
            if counts != expected_layer_counts[kind]:
                raise AssertionError("%s layer counts are %s" % (kind, counts))
        if kind is LayoutKind.LINK_FLAT:
            if any(layer != 0 for layer, _r, _c in slots):
                raise AssertionError("link layout is not single-layer")


def check_free_tiles():
    board = Board()
    tiles = [t("一万", "1万", Suit.CHAR, 1) for _ in range(4)]
    for c, tile in enumerate(tiles[:3]):
        board.place((0, 0, c), tile)
    if not is_free(board, (0, 0, 0)) or not is_free(board, (0, 0, 2)):
        raise AssertionError("edge tiles should be free")
    if is_free(board, (0, 0, 1)):
        raise AssertionError("a tile with both neighbours occupied is not free")

    # A tile covered from above must not be free even at the row edge.
    board.place((1, 0, 0), t("二万", "2万", Suit.CHAR, 2))
    if is_free(board, (0, 0, 0)):
        raise AssertionError("tile under an upper-layer tile was reported free")


def check_link_rule():
    empty = Board()
    empty.place((0, 0, 0), t("一万", "1万", Suit.CHAR, 1))
    empty.place((0, 0, 3), t("一万", "1万", Suit.CHAR, 1))
    if not can_link(empty, (0, 0, 0), (0, 0, 3)):
        raise AssertionError("0-turn link on an empty row should be valid")
    empty.place((0, 0, 2), t("二万", "2万", Suit.CHAR, 2))
    empty.place((0, 1, 2), t("二万", "2万", Suit.CHAR, 2))
    empty.place((0, 2, 0), t("二万", "2万", Suit.CHAR, 2))
    if not can_link(empty, (0, 0, 0), (0, 0, 3)):
        raise AssertionError("a <=2-bend detour around an obstacle should work")

    # Fully packed board: the two endpoints are boxed in on every side.
    packed = Board()
    a_pos, b_pos = (0, 2, 1), (0, 2, 3)
    for r in range(5):
        for c in range(5):
            pos = (0, r, c)
            if pos in (a_pos, b_pos):
                tile = t("东", "东", Suit.WIND, 1)
            else:
                tile = t("南", "南", Suit.WIND, 2)
            packed.place(pos, tile)
    if can_link(packed, a_pos, b_pos):
        raise AssertionError("surrounded tiles should not be linkable")

    free_board = Board()
    free_board.place((0, 0, 0), t("东", "东", Suit.WIND, 1))
    free_board.place((0, 2, 2), t("东", "东", Suit.WIND, 1))
    if not can_link(free_board, (0, 0, 0), (0, 2, 2)):
        raise AssertionError("1-turn link on an empty board should be valid")


def check_viewmodel_progress():
    board = Board()
    a = t("一万", "1万", Suit.CHAR, 1)
    b = t("一万", "1万", Suit.CHAR, 1)
    c = t("二万", "2万", Suit.CHAR, 2)
    d = t("二万", "2万", Suit.CHAR, 2)
    board.place((0, 0, 0), a)
    board.place((0, 0, 1), b)
    board.place((0, 1, 0), c)
    board.place((0, 1, 1), d)

    vm = GameViewModel(mode=GameMode.LINK)
    vm.state = GameState(board=board, mode=GameMode.LINK, running=True)
    vm.select((0, 0, 0))
    vm.select((0, 0, 1))

    st = vm.state
    if st.remaining_tiles != 2:
        raise AssertionError("match did not remove two tiles")
    if st.moves != 1 or st.score != 10:
        raise AssertionError("match did not advance moves/score (score=%d)" % st.score)
    if len(st.history) != 1 or st.selected is not None:
        raise AssertionError("match did not record history / clear selection")

    vm.undo()
    if st.remaining_tiles != 4 or st.moves != 0 or st.score != 0:
        raise AssertionError("undo did not restore board/score/moves")
    if len(st.history) != 0:
        raise AssertionError("undo did not pop the history record")

    if not tile_match(a, b) or tile_match(a, c):
        raise AssertionError("tile_match helper is inconsistent")


def main():
    try:
        check_deck()
        check_layouts()
        check_free_tiles()
        check_link_rule()
        check_viewmodel_progress()
    except Exception as exc:  # noqa: BLE001 - report, never traceback-crash
        print("FAIL: %s: %s" % (type(exc).__name__, exc))
        return 1
    print("selfcheck ok: 144-tile deck & match groups, 4 layouts x 144 unique "
          "slots, free-tile blocking, <=2-turn link rule, ViewModel match/undo")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
