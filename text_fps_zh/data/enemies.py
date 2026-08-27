"""Enemy template data.

The five legacy templates (守卫/士兵/重装兵/狙击手/指挥官) MUST keep their
exact stats — integration tests assert Guard=40hp/0armor and Soldier=55hp/10armor.
New tactical archetypes (突击兵/机枪手/医疗兵/神射手) are appended and use the
utility-scored AI brain added to ``models.enemy.Enemy``.
"""
from typing import Dict, List

from models.enemy import Enemy
from models.item import Item


def get_all_enemies() -> List[Dict]:
    """Return all enemy template data."""
    return [
        {"name": "守卫", "health": 40, "armor": 0, "damage": 5, "accuracy": 0.40, "behavior": "patrol"},
        {"name": "士兵", "health": 55, "armor": 10, "damage": 8, "accuracy": 0.50, "behavior": "aggressive"},
        {"name": "重装兵", "health": 75, "armor": 20, "damage": 10, "accuracy": 0.35, "behavior": "aggressive"},
        {"name": "狙击手", "health": 30, "armor": 5, "damage": 15, "accuracy": 0.70, "behavior": "aggressive"},
        {"name": "指挥官", "health": 90, "armor": 25, "damage": 12, "accuracy": 0.55, "behavior": "boss"},
        # --- New tactical archetypes (utility AI) ---
        {"name": "突击兵", "health": 45, "armor": 5, "damage": 9, "accuracy": 0.55, "behavior": "rusher"},
        {"name": "机枪手", "health": 70, "armor": 15, "damage": 12, "accuracy": 0.50, "behavior": "suppressor"},
        {"name": "医疗兵", "health": 50, "armor": 10, "damage": 6, "accuracy": 0.50,
         "behavior": "medic", "support_power": 18},
        {"name": "神射手", "health": 35, "armor": 5, "damage": 16, "accuracy": 0.78, "behavior": "marksman"},
    ]


def create_enemy(template_name: str, loot: List[Item] = None) -> Enemy:
    """Create an Enemy instance from template data."""
    templates = {e["name"]: e for e in get_all_enemies()}
    t = templates.get(template_name)
    if t is None:
        t = templates["守卫"]
    is_boss = t["behavior"] == "boss"
    return Enemy(
        name=t["name"],
        health=t["health"],
        armor=t["armor"],
        damage=t["damage"],
        accuracy=t["accuracy"],
        behavior=t["behavior"],
        is_boss=is_boss,
        loot=loot if loot is not None else [],
        support_power=t.get("support_power", 0),
    )
