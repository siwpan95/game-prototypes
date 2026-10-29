# -*- coding: utf-8 -*-
"""test_m2_crafting — 配方表 + 合成逻辑：can_craft / craft / 消耗产出 / STACK_MAX（headless，T-M2-06）。"""

from __future__ import annotations

import os

from mcclone.core.block_registry import BlockRegistry
from mcclone.player.inventory import Inventory, STACK_MAX
from mcclone.player.crafting import Crafting, Recipe

_THIS = os.path.dirname(os.path.abspath(__file__))
_EXAMPLE = os.path.normpath(os.path.join(_THIS, ".."))
_RECIPES = os.path.join(_EXAMPLE, "data", "recipes.default.json")


def _reg():
    reg = BlockRegistry()
    reg.load_defaults()
    return reg


def _crafting() -> Crafting:
    return Crafting.from_json(_reg(), _RECIPES)


def test_loads_three_recipes():
    c = _crafting()
    assert len(c.recipes) == 3
    ids = {r.id for r in c.recipes}
    assert ids == {"stone_brick", "glass", "sand_to_dirt_demo"}
    assert c.get("glass") is not None
    assert c.get("nope") is None


def test_can_craft_true_and_false():
    c = _crafting()
    inv = Inventory()
    assert c.can_craft("glass", inv) is False      # 无 sand
    inv.add(5, 4)
    assert c.can_craft("glass", inv) is True
    inv.remove(5, 4)
    assert c.can_craft("glass", inv) is False


def test_craft_consumes_and_produces():
    c = _crafting()
    inv = Inventory()
    inv.add(5, 4)
    ok = c.craft("glass", inv)
    assert ok is True
    assert inv.count(5) == 0
    assert inv.count(7) == 1     # glass 产出


def test_craft_stone_brick():
    c = _crafting()
    inv = Inventory()
    inv.add(1, 4)
    assert c.craft("stone_brick", inv) is True
    assert inv.count(1) == 0
    assert inv.count(6) == 1


def test_craft_fails_when_insufficient():
    c = _crafting()
    inv = Inventory()
    inv.add(5, 2)                # 仅 2 sand，需 4
    assert c.craft("glass", inv) is False
    assert inv.count(5) == 2     # 未消耗


def test_craft_respects_stack_max():
    c = _crafting()
    inv = Inventory()
    inv.add(5, 4 * (STACK_MAX + 5))   # 充足 sand
    for _ in range(200):
        if not c.can_craft("glass", inv):
            break
        if not c.craft("glass", inv):
            break
    # 每个槽数量不超过 STACK_MAX（跨栈允许超过总量，但单栈有上限）
    for it in inv.as_list():
        if it is not None:
            assert it[1] <= STACK_MAX


def test_recipe_get_and_listing():
    c = _crafting()
    r = c.get("sand_to_dirt_demo")
    assert isinstance(r, Recipe)
    assert r.inputs == {5: 1}
    assert r.output == {2: 1}
    assert len(c.recipes) == len({r.id for r in c.recipes})
