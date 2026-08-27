"""Enemy template data."""
from typing import List

from models.enemy import Enemy
from models.item import Item


def get_all_enemies() -> List[Dict]:
    """Return all enemy template data."""
    return [
        {"name": "Guard", "health": 40, "armor": 0, "damage": 5, "accuracy": 0.40, "behavior": "patrol"},
        {"name": "Soldier", "health": 55, "armor": 10, "damage": 8, "accuracy": 0.50, "behavior": "aggressive"},
        {"name": "Heavy Trooper", "health": 75, "armor": 20, "damage": 10, "accuracy": 0.35, "behavior": "aggressive"},
        {"name": "Sniper", "health": 30, "armor": 5, "damage": 15, "accuracy": 0.70, "behavior": "aggressive"},
        {"name": "Commander", "health": 90, "armor": 25, "damage": 12, "accuracy": 0.55, "behavior": "boss"},
    ]


def create_enemy(template_name: str, loot: List[Item] = None) -> Enemy:
    """Create an Enemy instance from template data."""
    templates = {e["name"]: e for e in get_all_enemies()}
    t = templates.get(template_name)
    if t is None:
        t = templates["Guard"]
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
    )
