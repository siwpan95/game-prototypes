#!/usr/bin/env python3
"""Headless self-check for life-reset-simulator (no tkinter, no window).

Covers the pure domain layer:

* the Reigns decision tree: card JSON loads, one decision applies its effects,
  dimensions stay clamped to 0..100 and time advances season/year,
* the save pipeline: ``SaveManager.dump`` -> atomic JSON -> ``SaveManager.load``
  round-trip, v1 -> v2 migration and game-mode normalisation.

Run from the project root:

    python selfcheck.py

Prints ``selfcheck ok: ...`` and returns 0 on success, ``FAIL: ...`` and 1
on failure.  All files are written to a temporary directory.
"""
from __future__ import annotations

import os
import tempfile

from core import constants, jsonio
from core.savegame import SaveManager
from decision_tree import DecisionTree, Dimension
from main import Player

SEASONS = ["\u6625", "\u590f", "\u79cb", "\u51ac"]  # 春夏秋冬
CHECKS: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    if not condition:
        raise AssertionError(f"{name}: {detail or 'condition is false'}")
    CHECKS.append(name)


def selfcheck_card() -> dict:
    return {
        "id": "selfcheck_card",
        "title": "Self Check",
        "description": "synthetic card used by selfcheck",
        "left_choice": {
            "text": "left",
            "effects": {"STRENGTH": 15, "WEALTH": -20, "STABILITY": -10,
                        "COMMONERS": -15},
            "speech": "left speech",
        },
        "right_choice": {
            "text": "right",
            "effects": {"STRENGTH": -5},
            "speech": "right speech",
        },
        "conditions": {"required_traits": []},
        "weight": 1.0,
    }


def check_decision_tree() -> None:
    dt = DecisionTree(Player())

    cards = dt.decision_cards
    usable = [c for c in cards
              if isinstance(c, dict) and c.get("id") and c.get("title")
              and "left_choice" in c and "right_choice" in c]
    check("cards.loaded", len(cards) >= 10, len(cards))
    check("cards.shape", len(usable) == len(cards), f"{len(usable)}/{len(cards)} usable")
    check("season.initial", dt.get_current_season() == SEASONS[0])
    check("dimensions.initial",
          len(dt.dimensions) == len(Dimension)
          and dt.dimensions[Dimension.HEALTH] == 80
          and all(v == 50 for k, v in dt.dimensions.items()
                  if k is not Dimension.HEALTH))

    result = dt.apply_decision(selfcheck_card(), "left_choice")
    check("decision.result", result.get("speech") == "left speech"
          and result.get("effects", {}).get("STRENGTH") == 15, result)
    check("decision.history", len(dt.history) == 1
          and dt.history[0].get("card_title") == "Self Check", dt.history)
    check("decision.effects",
          dt.dimensions[Dimension.STRENGTH] == 65
          and dt.dimensions[Dimension.COMMONERS] == 35
          and dt.dimensions[Dimension.STABILITY] == 40,
          {k.name: v for k, v in dt.dimensions.items()})
    # advance_time() adds the spring->summer seasonal effect (+10 wealth, -5 health)
    check("decision.seasonal",
          dt.dimensions[Dimension.WEALTH] == 40
          and dt.dimensions[Dimension.HEALTH] == 75,
          (dt.dimensions[Dimension.WEALTH], dt.dimensions[Dimension.HEALTH]))
    check("time.advanced", dt.season == 1 and dt.year == 0, (dt.season, dt.year))

    dt.season = 3
    dt.advance_time()
    check("time.year_rollover", dt.season == 4 and dt.year == 1, (dt.season, dt.year))

    dt.dimensions[Dimension.STRENGTH] = 95
    dt.adjust_dimension(Dimension.STRENGTH, 50)
    check("clamp.high", dt.dimensions[Dimension.STRENGTH] == 100)
    dt.dimensions[Dimension.STRENGTH] = 5
    dt.adjust_dimension(Dimension.STRENGTH, -50)
    check("clamp.low", dt.dimensions[Dimension.STRENGTH] == 0)
    check("clamp.player", 0 <= dt.player.strength <= 20, dt.player.strength)


def check_save_roundtrip() -> None:
    player = Player()
    player.name = "selfcheck"
    player.strength = 9
    player.health = 77
    player.wealth = 1234

    data = SaveManager.dump(player, "Reigns")
    check("save.version", data.get("schema_version") == constants.SCHEMA_VERSION,
          data.get("schema_version"))
    check("save.mode", data.get("game_mode") == "traditional", data.get("game_mode"))
    check("save.name", data.get("name") == "selfcheck", data.get("name"))

    with tempfile.TemporaryDirectory(prefix="life-reset-selfcheck-") as tmp:
        path = os.path.join(tmp, "slot.json")
        check("save.write", jsonio.write_json_atomic(path, data))
        loaded, migrated, warnings = SaveManager.load(path)
        check("load.ok", isinstance(loaded, dict) and loaded, loaded)
        check("load.version", loaded.get("schema_version") == constants.SCHEMA_VERSION)
        check("load.mode", loaded.get("game_mode") == "traditional")
        check("load.values",
              loaded.get("name") == "selfcheck"
              and loaded.get("strength") == 9
              and loaded.get("health") == 77
              and loaded.get("wealth") == 1234,
              {k: loaded.get(k) for k in ("name", "strength", "health", "wealth")})
        check("load.flags", migrated is False and warnings == [],
              (migrated, warnings))

    legacy = {"name": "old", "strength": 5}
    migrated_data, changed = SaveManager.migrate_v1_to_v2(legacy)
    check("migrate.changed", changed is True)
    check("migrate.keeps_fields",
          migrated_data.get("name") == "old" and migrated_data.get("strength") == 5)
    check("migrate.version", migrated_data.get("schema_version") == constants.SCHEMA_VERSION)
    check("migrate.mode", migrated_data.get("game_mode") == "traditional")
    check("migrate.no_mutation", "schema_version" not in legacy, legacy)
    check("normalize.mode",
          constants.normalize_mode("TRADITIONAL") == "traditional"
          and constants.normalize_mode(None) == "traditional")


def run() -> None:
    check_decision_tree()
    check_save_roundtrip()


def main() -> int:
    try:
        run()
    except Exception as exc:  # noqa: BLE001 - self-check must report, not traceback
        print(f"FAIL: {type(exc).__name__}: {exc}")
        return 1
    print(f"selfcheck ok: life-reset domain core "
          f"({len(CHECKS)} checks: decision-tree/save)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
