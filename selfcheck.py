"""Headless self-check for the Hell Below launcher / shared game core.

No Tk root is created and no game window is opened: the launcher views and
``shared_core.main_win.MainWindow`` are never instantiated (the module-level
``tkinter`` import alone does not start a GUI).

Checks:
  1. Launcher registry: 11 unique games, every main.py present, lookup helpers.
  2. PlayerState clamping / inventory / narrative triggers.
  3. GameState + SaveLoadManager JSON round-trip in a temporary directory.
  4. Card combat turn flow: AP spend, block absorption, enemy turn, victory.

Run from the project root::

    python selfcheck.py
"""
import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "launcher"))

from shared_core.card import Card
from shared_core.combat_engine import CombatState
from shared_core.enemy import Enemy, EnemyInstance, Intent
from shared_core.game_state import (
    Chapter, GameState, ImageryNetwork, ImageryNode, PlayerState,
)
from shared_core.save_load import SaveLoadManager
from src.models.game_registry import GAMES, get_available_games, get_game_by_id


def check_registry():
    if len(GAMES) != 11:
        raise AssertionError("registry has %d games, expected 11" % len(GAMES))
    ids = [g.game_id for g in GAMES]
    if len(set(ids)) != len(ids):
        raise AssertionError("duplicate game ids in registry")
    volumes = [g.volume for g in GAMES]
    if len(set(volumes)) != len(volumes):
        raise AssertionError("duplicate volume numbers in registry")
    if sorted(volumes) != volumes:
        raise AssertionError("registry is not ordered by volume")

    for game in GAMES:
        if not game.game_dir_zh.is_dir():
            raise AssertionError("%s directory is missing" % game.dir_name_zh)
        if not game.main_file_zh.is_file():
            raise AssertionError("%s is missing" % game.main_file_zh)
        if not game.title_zh or not game.genre_zh:
            raise AssertionError("%s has empty metadata" % game.game_id)

    if get_game_by_id("v01") is not GAMES[0]:
        raise AssertionError("get_game_by_id failed for v01")
    if get_game_by_id("nope") is not None:
        raise AssertionError("get_game_by_id should return None for unknown ids")
    if len(get_available_games()) != 11:
        raise AssertionError("not all registered games are available on disk")


def check_player_state():
    ps = PlayerState()
    if ps.adjust_sanity(1000) != ps.max_sanity - 70:
        raise AssertionError("sanity clamping is wrong")
    if ps.sanity != ps.max_sanity:
        raise AssertionError("sanity did not clamp at max")
    ps.adjust_sanity(-1000)
    if ps.sanity != 0:
        raise AssertionError("sanity did not clamp at zero")

    ps.adjust_corruption(150)
    if ps.corruption != 100:
        raise AssertionError("corruption did not clamp at 100")
    ps.adjust_hp(-1000)
    if ps.hp != 0 or not ps.is_critical:
        raise AssertionError("hp floor / critical state is wrong")

    ps.add_item("lamp")
    if not ps.has_item("lamp"):
        raise AssertionError("add_item/has_item failed")
    if ps.remove_item("lamp") is not True or ps.remove_item("lamp") is not False:
        raise AssertionError("remove_item return values are wrong")

    if not ps.trigger_narrative("intro") or ps.trigger_narrative("intro"):
        raise AssertionError("narrative trigger must fire exactly once")
    ps.visit_room("cell")
    if not ps.has_visited("cell"):
        raise AssertionError("visit_room/has_visited failed")


def check_state_roundtrip():
    state = GameState()
    state.player.current_chapter = Chapter.CH2
    state.player.current_room = "cell"
    state.player.add_item("lamp")
    state.player.add_item("key")
    state.player.discover_imagery("mirror")
    state.player.solved_puzzles.append("riddle")
    state.set_flag("door_open", True)
    state.set_var("turn", 7)

    net = ImageryNetwork()
    net.add_node(ImageryNode(id="mirror", name="Mirror", description="a mirror"))
    net.add_node(ImageryNode(id="sea", name="Sea", description="a sea"))
    net.get_node("mirror").connect_to("sea", 0.7)
    net.discover("mirror")
    state.imagery_network = net
    state.record_event("move", "entered the cell")

    # JSON-serialisable (the same guarantee a save file relies on).
    raw = json.loads(json.dumps(state.to_dict(), ensure_ascii=False))
    restored = GameState.from_dict(raw)
    if restored.player.current_chapter is not Chapter.CH2:
        raise AssertionError("chapter did not survive serialization")
    if restored.player.current_room != "cell":
        raise AssertionError("current_room did not survive serialization")
    if restored.player.inventory_items != ["lamp", "key"]:
        raise AssertionError("inventory did not survive serialization")
    if "mirror" not in restored.player.discovered_imagery:
        raise AssertionError("discovered imagery did not survive serialization")
    if restored.get_flag("door_open") is not True or restored.get_var("turn") != 7:
        raise AssertionError("flags/variables did not survive serialization")
    if restored.imagery_network.discovery_count != 1:
        raise AssertionError("imagery network did not survive serialization")

    with tempfile.TemporaryDirectory() as tmp:
        mgr = SaveLoadManager(tmp, version=1)
        if not mgr.save(state, slot=3):
            raise AssertionError("SaveLoadManager.save failed")
        info = mgr.get_slot_info(3)
        if info is None or info["chapter"] != "chapter_2":
            raise AssertionError("slot info is missing/wrong")
        loaded = mgr.load(3)
        if loaded is None:
            raise AssertionError("SaveLoadManager.load failed")
        if loaded.player.inventory_items != ["lamp", "key"]:
            raise AssertionError("loaded inventory differs from saved state")
        if loaded.player.current_chapter is not Chapter.CH2:
            raise AssertionError("loaded chapter differs from saved state")
        if not mgr.delete_save(3) or mgr.load(3) is not None:
            raise AssertionError("delete_save did not remove the slot")


def _strike(card_id):
    return Card(
        id=card_id, name="Strike", ap_cost=1, damage=5,
        effect=lambda s: setattr(s.enemy, "hp", s.enemy.hp - 5),
    )


def _guard(card_id):
    return Card(
        id=card_id, name="Guard", ap_cost=1, block=6,
        effect=lambda s: setattr(s, "player_block", s.player_block + 6),
    )


def check_combat():
    template = Enemy(
        id="selfcheck-enemy", name="Test Wraith", hp=12, max_hp=12,
        intents=[Intent(name="Claw", damage=8)],
    )
    enemy = EnemyInstance(template)
    deck = [_strike("s1"), _strike("s2"), _strike("s3"),
            _guard("g1"), _guard("g2")]
    cs = CombatState.new(50, 50, 20, 20, enemy, deck)
    if cs.turn_number != 1 or cs.ap != 3 or len(cs.hand) != 5:
        raise AssertionError("combat did not start with 3 AP and a 5-card hand")

    def play(card_id):
        for i, card in enumerate(cs.hand):
            if card.id == card_id:
                if not cs.play_card(i):
                    raise AssertionError("play_card returned False for %s" % card_id)
                return
        raise AssertionError("card %s not in hand" % card_id)

    play("s1")
    if cs.enemy.hp != 7 or cs.ap != 2:
        raise AssertionError("strike did not cost 1 AP / deal 5 damage")
    play("g1")
    if cs.player_block != 6 or cs.ap != 1:
        raise AssertionError("guard did not grant 6 block")

    cs.end_player_turn()
    # 8 incoming - 6 block = 2 HP lost; block is consumed, turn 2 starts.
    if cs.player_hp != 48:
        raise AssertionError("block did not absorb damage (hp=%d)" % cs.player_hp)
    if cs.turn_number != 2 or cs.ap != 3 or cs.player_block != 0:
        raise AssertionError("next turn did not reset AP/block")
    if len(cs.hand) != 5 or cs.discard_pile:
        raise AssertionError("discard pile was not reshuffled into a new hand")

    play("s2")
    play("s3")
    if not cs.combat_over or not cs.player_won:
        raise AssertionError("enemy at 0 HP did not end combat as a win")
    if cs.enemy.hp > 0:
        raise AssertionError("enemy HP was not reduced below zero")


def main():
    try:
        check_registry()
        check_player_state()
        check_state_roundtrip()
        check_combat()
    except Exception as exc:  # noqa: BLE001 - report, never traceback-crash
        print("FAIL: %s: %s" % (type(exc).__name__, exc))
        return 1
    print("selfcheck ok: 11-game launcher registry, player state clamps, "
          "GameState/SaveLoad JSON round-trip, card combat turn/AP/block/victory")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
