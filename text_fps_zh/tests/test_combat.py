"""Critical-path combat unit tests.

Covers:
  * Enemy.take_damage absorbs armor exactly **once** per hit (no double counting).
  * CombatSystem.calculate_damage applies only the +/-20% variance (armor is NOT
    applied here -- that lives in Enemy.take_damage).
  * An integrated "fire at a high-armor enemy" check: after firing, health/armor
    are consistent with a single armor absorption.

Run with pytest (CI):  ``pytest tests/test_combat.py``
Run without pytest:    ``python tests/run_manual.py``

NOTE: This module must never import pygame / main / ui -- it only touches
``models`` and ``systems`` which are pure Python.
"""
import os
import sys

# Make the project root importable whether collected by pytest (conftest does this)
# or run standalone (run_manual.py does this). Idempotent.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from models.enemy import Enemy
from models.player import Player
from models.weapon import Weapon
from systems.combat import CombatSystem


def _make_player_with_pistol(damage=12, accuracy=1.0, ammo=15):
    p = Player(name="TestPlayer")
    p.weapons.append(
        Weapon(name="Pistol", weapon_type="pistol",
               damage=damage, accuracy=accuracy, ammo=ammo, max_ammo=ammo)
    )
    return p


# ---------------------------------------------------------------------------
# Armor absorption: the core "only deducted once" guarantee
# ---------------------------------------------------------------------------
def test_enemy_take_damage_armor_absorbed_once():
    """Armor is subtracted exactly once; the remainder hits health, not both."""
    e = Enemy(name="Heavy", health=100, armor=20)

    # Hit 10 < armor(20): fully absorbed -> armor 10, health untouched.
    remaining = e.take_damage(10)
    assert remaining == 0
    assert e.armor == 10
    assert e.health == 100

    # Hit 15: absorb 10 (remaining armor), 5 carries to health.
    remaining = e.take_damage(15)
    assert remaining == 5
    assert e.armor == 0
    assert e.health == 95


def test_enemy_take_damage_armor_not_double_counted():
    """Health must not also be reduced by the absorbed armor amount."""
    e = Enemy(name="Heavy", health=100, armor=20)
    e.take_damage(8)  # all absorbed
    # Armor dropped by 8, health must be exactly 100 (no double subtraction).
    assert e.armor == 12
    assert e.health == 100


def test_enemy_take_damage_armor_depletes_then_health():
    """Once armor is gone, further damage goes straight to health."""
    e = Enemy(name="Heavy", health=100, armor=20)
    e.take_damage(20)            # armor 20 -> 0, health untouched
    assert e.armor == 0
    assert e.health == 100
    e.take_damage(30)            # full 30 to health
    assert e.armor == 0
    assert e.health == 70


# ---------------------------------------------------------------------------
# Damage variance bounds (+/-20%), armor NOT applied inside calculate_damage
# ---------------------------------------------------------------------------
def test_calculate_damage_within_variance():
    """calculate_damage must stay within +/-20% of the weapon's base damage."""
    cs = CombatSystem()
    w = Weapon(name="Pistol", damage=10, accuracy=1.0)
    base = w.effective_damage()  # 10
    for _ in range(300):
        d = cs.calculate_damage(w)
        # int(base * uniform(0.8, 1.2)) is always within the band.
        assert d >= base * 0.8 - 1e-9
        assert d <= base * 1.2 + 1e-9


def test_calculate_damage_ignores_armor():
    """Armor is a property of the enemy, not the weapon -- verify it is not in the formula."""
    cs = CombatSystem()
    w = Weapon(name="Pistol", damage=20, accuracy=1.0)
    # Damage must be derived purely from the weapon, independent of any enemy.
    samples = {cs.calculate_damage(w) for _ in range(50)}
    # +/-20% of 20 => int band [16, 24]; never includes 0 or negative.
    assert all(16 <= d <= 24 for d in samples)


# ---------------------------------------------------------------------------
# Integrated: fire at a high-armor enemy (armor=20)
# ---------------------------------------------------------------------------
def test_fire_high_armor_enemy_armor_absorbed_once():
    """After firing, health/armor reflect a single armor absorption (no double hit)."""
    cs = CombatSystem()
    p = _make_player_with_pistol(damage=12, accuracy=1.0, ammo=15)
    # accuracy=1.0 always hits (random.random() < 1.0 is guaranteed); damage is
    # 12 * uniform(0.8, 1.2) in [9, 14] -- strictly less than armor 20.
    e = Enemy(name="Heavy", health=100, armor=20, accuracy=1.0, behavior="aggressive")

    result = cs.execute_fire(p, e)
    assert result["success"] is True
    assert result["hit"] is True

    dmg = result["damage"]
    absorbed = min(20, dmg)  # armor fully absorbs the hit
    # Exactly one absorption: armor reduced by `dmg`, health untouched.
    assert e.armor == 20 - absorbed
    assert e.health == 100  # nothing leaked past the armor
    assert e.armor > 0


def test_fire_lethal_does_not_over_subtract_armor():
    """A killing blow should not drive health below 0 or armor below 0."""
    cs = CombatSystem()
    p = _make_player_with_pistol(damage=12, accuracy=1.0, ammo=15)
    e = Enemy(name="Mook", health=5, armor=3, accuracy=1.0, behavior="aggressive")
    result = cs.execute_fire(p, e)
    assert result["hit"] is True
    assert e.is_alive is False
    assert e.health == 0
    assert e.armor >= 0  # armor only goes down by the absorbed amount, never negative
