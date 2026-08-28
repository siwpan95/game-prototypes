"""Excel loader — import card and enemy definitions from .xlsx files.

Uses openpyxl. Falls back to JSON if Excel is unavailable.
Can also generate template .xlsx files for users to fill in.
"""

from __future__ import annotations
import json
import os

try:
    import openpyxl
    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False


# ── Card Loading ────────────────────────────────────────────────────────────

CARD_COLUMNS = [
    "id", "name", "cost", "type", "rarity",
    "attack", "health", "description", "keywords",
    "target", "damage", "shield", "heal",
    "battlecry_type", "battlecry_value",
    "deathrattle_type", "deathrattle_value",
]


def load_cards_from_excel(path: str) -> list[dict]:
    """Load card definitions from an Excel file.

    Expected columns: id, name, cost, type, rarity, attack, health,
    description, keywords, target, damage, shield, heal,
    battlecry_type, battlecry_value, deathrattle_type, deathrattle_value

    Returns list of card data dicts.
    """
    if not HAS_OPENPYXL:
        raise RuntimeError("openpyxl not installed — pip install openpyxl")

    wb = openpyxl.load_workbook(path, read_only=True)
    ws = wb.active

    rows = list(ws.iter_rows(values_only=True))
    if len(rows) < 2:
        wb.close()
        return []

    header = [str(c).strip().lower() if c else "" for c in rows[0]]
    cards = []

    for row in rows[1:]:
        if not row or not row[0]:
            continue
        data = {}
        for i, col_name in enumerate(header):
            if i < len(row) and col_name in CARD_COLUMNS:
                val = row[i]
                if col_name in ("id", "name", "type", "rarity", "description",
                                "target", "battlecry_type", "deathrattle_type"):
                    data[col_name] = str(val).strip() if val else ""
                elif col_name in ("cost", "attack", "health", "damage",
                                  "shield", "heal", "battlecry_value",
                                  "deathrattle_value"):
                    data[col_name] = int(val) if val is not None else 0
                elif col_name == "keywords":
                    data[col_name] = _parse_keywords_cell(val)
                else:
                    data[col_name] = val

        # Build battlecry/deathrattle dicts
        if data.get("battlecry_type"):
            data["battlecry"] = {
                "type": data.pop("battlecry_type"),
                "value": data.pop("battlecry_value", 0),
            }
        else:
            data.pop("battlecry_type", None)
            data.pop("battlecry_value", None)

        if data.get("deathrattle_type"):
            data["deathrattle"] = {
                "type": data.pop("deathrattle_type"),
                "value": data.pop("deathrattle_value", 0),
            }
        else:
            data.pop("deathrattle_type", None)
            data.pop("deathrattle_value", None)

        cards.append(data)

    wb.close()
    return cards


def load_cards_from_json(path: str) -> list[dict]:
    """Load card definitions from a JSON file."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_cards(config_dir: str, data_dir: str) -> list[dict]:
    """Try Excel first, then JSON fallback."""
    xlsx_path = os.path.join(config_dir, "cards.xlsx")
    json_path = os.path.join(data_dir, "cards.json")

    if os.path.exists(xlsx_path) and HAS_OPENPYXL:
        return load_cards_from_excel(xlsx_path)

    if os.path.exists(json_path):
        return load_cards_from_json(json_path)

    return []


# ── Enemy Loading ───────────────────────────────────────────────────────────

ENEMY_COLUMNS = [
    "id", "name", "hp", "attack", "is_boss", "wave_min",
    "intent_type", "intent_pattern", "keywords",
]


def load_enemies_from_excel(path: str) -> list[dict]:
    """Load enemy definitions from an Excel file."""
    if not HAS_OPENPYXL:
        raise RuntimeError("openpyxl not installed — pip install openpyxl")

    wb = openpyxl.load_workbook(path, read_only=True)
    ws = wb.active

    rows = list(ws.iter_rows(values_only=True))
    if len(rows) < 2:
        wb.close()
        return []

    header = [str(c).strip().lower() if c else "" for c in rows[0]]
    enemies = []

    for row in rows[1:]:
        if not row or not row[0]:
            continue
        data = {}
        for i, col_name in enumerate(header):
            if i < len(row) and col_name in ENEMY_COLUMNS:
                val = row[i]
                if col_name in ("id", "name", "intent_type", "intent_pattern"):
                    data[col_name] = str(val).strip() if val else ""
                elif col_name in ("hp", "attack", "wave_min"):
                    data[col_name] = int(val) if val is not None else 0
                elif col_name == "is_boss":
                    data[col_name] = bool(val) if val is not None else False
                elif col_name == "keywords":
                    data[col_name] = _parse_keywords_cell(val)
                else:
                    data[col_name] = val

        # Map intent_type to intent for EnemyComponent
        if "intent_type" in data:
            data["intent"] = data.pop("intent_type")
        enemies.append(data)

    wb.close()
    return enemies


def load_enemies_from_json(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_enemies(config_dir: str, data_dir: str) -> list[dict]:
    xlsx_path = os.path.join(config_dir, "enemies.xlsx")
    json_path = os.path.join(data_dir, "enemies.json")

    if os.path.exists(xlsx_path) and HAS_OPENPYXL:
        return load_enemies_from_excel(xlsx_path)

    if os.path.exists(json_path):
        return load_enemies_from_json(json_path)

    return []


# ── Template Generation ─────────────────────────────────────────────────────

def generate_card_template(path: str) -> None:
    """Create a template cards.xlsx with headers and one example row."""
    if not HAS_OPENPYXL:
        return
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Cards"
    ws.append(CARD_COLUMNS)
    ws.append([
        "strike", "Strike", 1, "attack", "common",
        0, 0, "Deal 6 damage.", "",
        "enemy", 6, 0, 0,
        "", 0, "", 0,
    ])
    ws.append([
        "defend", "Defend", 1, "skill", "common",
        0, 0, "Gain 5 Shield.", "",
        "self", 0, 5, 0,
        "", 0, "", 0,
    ])
    ws.append([
        "shield_bearer", "Shield Bearer", 1, "minion", "common",
        0, 3, "Taunt", "Taunt",
        "none", 0, 0, 0,
        "", 0, "", 0,
    ])
    wb.save(path)


def generate_enemy_template(path: str) -> None:
    """Create a template enemies.xlsx with headers and example rows."""
    if not HAS_OPENPYXL:
        return
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Enemies"
    ws.append(ENEMY_COLUMNS)
    ws.append(["slime", "Slime", 12, 4, False, 1, "attack", "always_attack", ""])
    ws.append(["goblin", "Goblin", 10, 6, False, 1, "attack", "alternate", ""])
    ws.append(["orc_warlord", "Orc Warlord", 50, 8, True, 5, "attack", "buff_then_attack", "Taunt"])
    wb.save(path)


# ── Helpers ─────────────────────────────────────────────────────────────────

def _parse_keywords_cell(val) -> list[str]:
    """Parse a keywords cell value into a list of keyword strings."""
    if val is None:
        return []
    if isinstance(val, list):
        return val
    text = str(val).strip()
    if not text:
        return []
    # Split by comma or semicolon
    return [k.strip() for k in text.replace(";", ",").split(",") if k.strip()]
