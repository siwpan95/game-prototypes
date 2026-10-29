"""Inventory core unit tests (add / use / capacity limit).

Uses InventorySystem (the real add path is ``pickup`` from a room into the player's
inventory; "use" is ``use_item``; capacity is enforced at ``MAX_INVENTORY``).

Run with pytest (CI):  ``pytest tests/test_inventory.py``
Run without pytest:    ``python tests/run_manual.py``

No pygame / main / ui imports.
"""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from core.constants import MAX_INVENTORY
from models.item import MedKit, Item
from models.player import Player
from models.room import Room
from models.weapon import Weapon
from systems.inventory import InventorySystem


def _make_player_with_pistol():
    p = Player(name="TestPlayer")
    p.weapons.append(
        Weapon(name="Pistol", weapon_type="pistol",
               damage=12, accuracy=0.75, ammo=15, max_ammo=15)
    )
    return p


def _make_inv():
    return InventorySystem()


def test_inventory_add_item():
    """pickup adds an item to the player's inventory and removes it from the room."""
    inv = _make_inv()
    p = _make_player_with_pistol()
    r = Room(room_id="r", name="Room")
    mk = MedKit(heal_amount=25)
    r.items.append(mk)

    res = inv.pickup(p, r, 0)
    assert res["success"] is True
    assert mk in p.inventory
    assert mk not in r.items
    assert len(p.inventory) == 1


def test_inventory_use_item_medkit():
    """use_item consumes a MedKit and heals the player."""
    inv = _make_inv()
    p = _make_player_with_pistol()
    p.health = 50
    mk = MedKit(heal_amount=25)
    p.inventory.append(mk)

    res = inv.use_item(p, 0)
    assert res["success"] is True
    assert p.health == 75          # 50 + 25
    assert len(p.inventory) == 0   # item consumed


def test_inventory_use_item_invalid_index():
    inv = _make_inv()
    p = _make_player_with_pistol()
    res = inv.use_item(p, 99)
    assert res["success"] is False


def test_inventory_capacity_limit():
    """Once the inventory is full, pickup refuses and reports 'full'."""
    inv = _make_inv()
    p = _make_player_with_pistol()
    r = Room(room_id="r", name="Room")

    # Fill to capacity.
    for _ in range(MAX_INVENTORY):
        p.inventory.append(Item(name="Junk"))
    assert len(p.inventory) == MAX_INVENTORY

    extra = Item(name="Extra")
    r.items.append(extra)
    res = inv.pickup(p, r, 0)
    assert res["success"] is False
    assert "已满" in res["message"]  # 背包已满 (capacity full)
    assert len(p.inventory) == MAX_INVENTORY  # unchanged


def test_inventory_capacity_constant_is_ten():
    """Sanity guard: the documented capacity limit is 10."""
    assert MAX_INVENTORY == 10
