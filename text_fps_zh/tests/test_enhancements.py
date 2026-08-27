"""Enhancement tests (T1) — content + tactical mechanics added in the
comprehensive upgrade pass.

These tests deliberately import ONLY pygame-free modules (models / systems /
data / core) so the suite stays green under the ``test_combat.py`` hard rule of
"no pygame / main / ui imports". They verify:

  * Ballistics: armor-piercing penetration reduces armor absorption.
  * New enemy archetypes use the utility-scored AI (valid actions, medic heal).
  * New items: flashbang suppression, breaching charge destruction, stim buff.
  * Combat layers: exposure damage bonus + suppressive fire (LMG).
  * F1 cover toggle (enter / leave) via StealthSystem.
  * F4 seed-reproducible, connected campaign generation with a boss room.
  * Data catalog expansion (weapons / mods / archetypes) with legacy stats kept.
"""
import os
import sys

# Make the project root importable (mirrors conftest.py bootstrap).
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from models.player import Player
from models.enemy import Enemy
from models.room import Room
from models.item import Flashbang, BreachingCharge, Stim, HeavyArmor
from data.enemies import create_enemy, get_all_enemies
from data.items import (
    create_flashbang,
    create_breaching_charge,
    create_stim,
    create_heavy_armor,
)
from data.weapons import get_all_weapons, get_all_mods, create_weapon
from systems.combat import CombatSystem
from systems.stealth import StealthSystem
from systems.level_generator import generate_campaign
from core.game_state import GameState
from core.constants import EXPOSED_DAMAGE_BONUS


# ----------------------------------------------------------------------
# Ballistics: armor-piercing penetration
# ----------------------------------------------------------------------
def test_penetration_reduces_armor_absorption():
    e = create_enemy("重装兵")  # armor 20, health 75
    dealt_no_pen = e.take_damage(30, penetration=0.0)
    assert dealt_no_pen == 10  # 20 absorbed by armor, 10 to health
    assert e.health == 65

    e2 = create_enemy("重装兵")
    dealt_full_pen = e2.take_damage(30, penetration=1.0)
    assert dealt_full_pen == 30  # armor fully bypassed
    assert e2.health == 45


def test_weapon_effective_penetration_includes_mods():
    w = create_weapon("amr")  # penetration 0.70
    assert w.effective_penetration() == 0.70
    # Adding AP rounds stacks on top (capped at 1.0).
    from data.items import create_weapon_mod_item
    ap = create_weapon_mod_item("ap_rounds")  # mod_type key; penetration_bonus 0.35
    w.add_mod(ap.mod)
    assert w.effective_penetration() == 1.0


# ----------------------------------------------------------------------
# Enemy AI: utility-scored archetypes
# ----------------------------------------------------------------------
def test_utility_ai_returns_valid_action():
    rusher = create_enemy("突击兵")
    player = Player()
    room = Room(room_id="r", cover_objects=["沙袋"])
    # decide_action routes attack/flank decisions through _attack(), whose
    # outcome dict uses "attack" / "miss"; retreat/heal/take_cover are returned
    # directly. All are valid, sane outcomes.
    valid = {"attack", "miss", "retreat", "heal", "take_cover"}
    for _ in range(25):
        action = rusher.decide_action(player, room)
        assert isinstance(action, dict)
        assert action["action"] in valid


def test_medic_heals_wounded_ally():
    medic = create_enemy("医疗兵")  # support_power 18
    ally = create_enemy("士兵")  # health 55
    ally.health = 10
    player = Player()
    room = Room(room_id="r", enemies=[medic, ally])
    result = medic.decide_action(player, room)
    assert result["action"] == "heal"
    assert ally.health == 28  # 10 + min(18, 55-10)


def test_marksman_uses_utility_brain():
    marksman = create_enemy("神射手")
    player = Player()
    room = Room(room_id="r", cover_objects=["沙袋"])
    action = marksman.decide_action(player, room)
    assert isinstance(action, dict)
    assert action["action"] in {"attack", "miss", "retreat", "take_cover", "heal"}


# ----------------------------------------------------------------------
# New items
# ----------------------------------------------------------------------
def test_flashbang_suppresses_enemies():
    fb = create_flashbang(2)
    enemy = create_enemy("士兵")
    msg = fb.use(Player(), enemies=[enemy])
    assert enemy.status_effects["suppressed"] == 2
    assert "压制" in msg


def test_breaching_charge_destroys_destructible():
    room = Room(room_id="r", destructibles=["木箱"], enemies=[])
    bc = create_breaching_charge(45)
    enemy = create_enemy("守卫")  # health 40
    msg = bc.use(Player(), enemies=[enemy], room=room)
    assert room.destructibles == []
    assert enemy.health < 40
    assert "摧毁" in msg


def test_stim_applies_buffs():
    player = Player()
    player.weapons.append(create_weapon("pistol"))
    player.health = 50
    stim = create_stim(25, 3)
    msg = stim.use(player)
    assert player.buffs["stim_turns"] == 3
    assert "stim_acc" in player.buffs
    assert "stim_dmg" in player.buffs
    assert player.health == 75  # 50 + 25 heal


def test_heavy_armor_serializes_under_own_type():
    ha = create_heavy_armor(50)
    assert isinstance(ha, HeavyArmor)
    assert ha.item_type == "heavy_armor"
    restored = HeavyArmor.from_dict(ha.to_dict())
    assert restored.armor_amount == 50


# ----------------------------------------------------------------------
# Combat layers: exposure + suppression
# ----------------------------------------------------------------------
def test_exposed_target_takes_bonus_damage():
    player = Player()
    w = create_weapon("rifle")  # damage 18
    player.weapons.append(w)
    player.current_weapon_idx = 0
    # Force a guaranteed hit so the test is deterministic.
    w.fire = lambda accuracy_bonus=0.0: {"hit": True, "damage": w.damage}

    cs = CombatSystem()
    exposed = create_enemy("守卫")
    exposed.exposed = True
    res = cs.execute_fire(player, exposed, None)
    assert res["hit"] is True
    assert res["damage"] == w.damage + EXPOSED_DAMAGE_BONUS

    # A non-exposed target takes only base damage.
    not_exposed = create_enemy("守卫")
    res2 = cs.execute_fire(player, not_exposed, None)
    assert res2["damage"] == w.damage


def test_lmg_applies_suppression_on_fire():
    player = Player()
    player.weapons.append(create_weapon("lmg"))  # suppression 0.55
    player.current_weapon_idx = 0
    enemy = create_enemy("重装兵")  # 75 hp, survives a 16-dmg hit
    room = Room(room_id="r", enemies=[enemy])
    cs = CombatSystem()
    cs.execute_fire(player, enemy, room)
    assert enemy.status_effects["suppressed"] > 0


# ----------------------------------------------------------------------
# F1: cover toggle
# ----------------------------------------------------------------------
def test_stealth_toggle_cover_enter_leave():
    stealth = StealthSystem()
    player = Player()
    room = Room(room_id="r", cover_objects=["水泥柱"])
    r1 = stealth.toggle_cover(player, room)
    assert player.in_cover is True
    assert r1["now_in_cover"] is True
    r2 = stealth.toggle_cover(player, room)
    assert player.in_cover is False
    assert r2["now_in_cover"] is False


# ----------------------------------------------------------------------
# F4: procedural campaign generation
# ----------------------------------------------------------------------
def test_generate_campaign_reproducible():
    a = generate_campaign(20260725)
    b = generate_campaign(20260725)
    assert a.name == b.name
    assert list(a.rooms.keys()) == list(b.rooms.keys())
    assert a.start_room == b.start_room
    assert a.boss_room == b.boss_room
    for rid in a.rooms:
        ra, rb = a.rooms[rid], b.rooms[rid]
        assert ra.name == rb.name
        assert ra.exits == rb.exits
        assert [e.name for e in ra.enemies] == [e.name for e in rb.enemies]
        assert len(ra.items) == len(rb.items)


def test_generate_campaign_variety():
    layouts = {
        (generate_campaign(s).name, len(generate_campaign(s).rooms))
        for s in range(1, 26)
    }
    # 25 distinct seeds must yield more than one distinct layout.
    assert len(layouts) > 1


def test_generate_campaign_connected():
    level = generate_campaign(777)
    visited = set()
    stack = [level.start_room]
    while stack:
        cur = stack.pop()
        if cur in visited:
            continue
        visited.add(cur)
        room = level.get_room(cur)
        assert room is not None
        for nb in room.exits.values():
            if nb not in visited:
                stack.append(nb)
    assert visited == set(level.rooms.keys())


def test_generate_campaign_has_boss_and_reachable_entrance():
    level = generate_campaign(42)
    assert level.start_room in level.rooms
    assert level.boss_room in level.rooms
    boss = level.get_room(level.boss_room)
    assert any(e.name == "指挥官" for e in boss.enemies)
    entrance = level.get_room(level.start_room)
    assert len(entrance.exits) >= 1  # player can always leave the entrance


def test_generated_level_loads_in_gamestate():
    gs = GameState()
    level = generate_campaign(5)
    gs.load_level(level)
    assert gs.current_room is not None
    assert gs.current_room.room_id == level.start_room
    assert gs.player is not None
    assert gs.player.current_weapon() is not None


# ----------------------------------------------------------------------
# Data catalog expansion (legacy stats preserved)
# ----------------------------------------------------------------------
def test_weapon_catalog_expanded():
    assert len(get_all_weapons()) >= 13
    assert len(get_all_mods()) >= 6
    amr = next(w for w in get_all_weapons() if w["weapon_type"] == "amr")
    assert amr["penetration"] > 0.5


def test_enemy_archetypes_present_and_legacy_stats_kept():
    names = [e["name"] for e in get_all_enemies()]
    for n in ["突击兵", "机枪手", "医疗兵", "神射手"]:
        assert n in names
    guard = next(e for e in get_all_enemies() if e["name"] == "守卫")
    assert guard["health"] == 40 and guard["armor"] == 0
    soldier = next(e for e in get_all_enemies() if e["name"] == "士兵")
    assert soldier["health"] == 55 and soldier["armor"] == 10
