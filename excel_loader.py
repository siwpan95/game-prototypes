"""Excel loader — import card, enemy, event, and room config from .xlsx files.
uses openpyxl. 数据权威来源为 Excel 文件。
"""

from __future__ import annotations
import json
import os

try:
    import openpyxl
    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False

# ── Utility: parse number from cell ──────────────────────────────────────

def _parse_int(val) -> int:
    if val is None:
        return 0
    if isinstance(val, str):
        val = val.strip()
        if not val:
            return 0
        return int(float(val))
    return int(val)


def _parse_float(val) -> float:
    if val is None:
        return 0.0
    if isinstance(val, str):
        val = val.strip()
        if not val:
            return 0.0
        return float(val)
    return float(val)


def _parse_str(val) -> str:
    if val is None:
        return ""
    return str(val).strip()


# ── Card Loading ────────────────────────────────────────────────────────────

CARD_COLUMNS = [
    "id", "name", "cost", "type", "rarity",
    "attack", "health", "description", "keywords",
    "target", "damage", "shield", "heal",
    "battlecry_type", "battlecry_value",
    "deathrattle_type", "deathrattle_value",
    "element", "status_type", "status_turns", "status_value",
]


def load_cards_from_excel(path: str) -> list[dict]:
    """Load card definitions from an Excel file (reads the first/only sheet).

    Expected columns: id, name, cost, type, rarity,
    attack, health, description, keywords, target, damage, shield, heal,
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
                                "target", "battlecry_type", "deathrattle_type",
                                "element", "status_type"):
                    data[col_name] = str(val).strip() if val else ""
                elif col_name in ("cost", "attack", "health", "damage",
                                  "shield", "heal", "battlecry_value",
                                  "deathrattle_value", "status_turns",
                                  "status_value"):
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

        # Build status_effect dict
        if data.get("status_type"):
            data["status_effect"] = {
                "type": data.pop("status_type"),
                "turns": data.pop("status_turns", 1),
                "value": data.pop("status_value", 0),
            }
        else:
            data.pop("status_type", None)
            data.pop("status_turns", None)
            data.pop("status_value", None)

        cards.append(data)

    wb.close()
    return cards


def load_cards_from_json(path: str) -> list[dict]:
    """Load card definitions from a JSON file."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_cards(config_dir: str, data_dir: str) -> list[dict]:
    """从 Excel 加载卡牌数据。"""
    xlsx_path = os.path.join(config_dir, "cards.xlsx")

    if os.path.exists(xlsx_path) and HAS_OPENPYXL:
        return load_cards_from_excel(xlsx_path)

    return []


def load_cards_by_pool(config_dir: str, data_dir: str) -> dict[str, list[dict]]:
    """从 Excel 文件加载卡牌，按池归类。

      config/cards_B.xlsx → pool = "B"（公共基础卡牌，3张：打击/防御/持盾者）
      config/cards_C.xlsx → pool = "C"（可编辑池，所有可获得的卡牌）

    Pool A 是玩家动态收藏池，初始为空，不需要 Excel 文件。
    当玩家通过奖励/事件获得卡牌时，卡牌的 pool 标记为 "A"。

    Returns: {"B": [...], "C": [...]}
    """
    pools: dict[str, list[dict]] = {"A": [], "B": [], "C": []}

    for pool_name in ("B", "C"):
        xlsx_path = os.path.join(config_dir, f"cards_{pool_name}.xlsx")
        if os.path.exists(xlsx_path) and HAS_OPENPYXL:
            cards = load_cards_from_excel(xlsx_path)
            for c in cards:
                c["pool"] = pool_name
            pools[pool_name] = cards

    return pools


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
    """从 Excel 加载敌人数据。"""
    xlsx_path = os.path.join(config_dir, "enemies.xlsx")

    if os.path.exists(xlsx_path) and HAS_OPENPYXL:
        return load_enemies_from_excel(xlsx_path)

    return []


# ── Event Loading ───────────────────────────────────────────────────────────

EVENT_COLUMNS = [
    "id", "title", "description",
    "choice_1_label", "choice_1_desc", "choice_1_action", "choice_1_value",
    "choice_2_label", "choice_2_desc", "choice_2_action", "choice_2_value",
    "choice_3_label", "choice_3_desc", "choice_3_action", "choice_3_value",
]


def _parse_event_value(val):
    """Parse event choice value. Supports JSON dicts, numbers, and plain strings.
       e.g. '{"gold":25,"hp":8}' → dict
            '25' → int
            '0.3' → float
            'random_card' → str
    """
    if val is None or (isinstance(val, str) and val.strip() == ""):
        return None
    s = str(val).strip()
    if s.startswith("{"):
        try:
            return json.loads(s)
        except json.JSONDecodeError:
            return s
    # Try numeric
    try:
        if "." in s:
            return float(s)
        return int(s)
    except ValueError:
        return s


def load_events_from_excel(path: str) -> list[dict]:
    """Load event definitions from an Excel file.
    Each row = one event with up to 3 choices.
    """
    if not HAS_OPENPYXL:
        raise RuntimeError("openpyxl not installed — pip install openpyxl")

    wb = openpyxl.load_workbook(path, read_only=True)
    ws = wb.active
    rows_list = list(ws.iter_rows(values_only=True))
    if len(rows_list) < 2:
        wb.close()
        return []

    header = [_parse_str(c).lower() for c in rows_list[0]]
    events = []

    for row in rows_list[1:]:
        if not row or not row[0]:
            continue
        data = {}
        for i, col_name in enumerate(header):
            if i < len(row):
                if col_name.startswith("choice_") and col_name.endswith("_value"):
                    data[col_name] = _parse_event_value(row[i])
                else:
                    data[col_name] = _parse_str(row[i])

        # Build event dict with choices list
        event = {
            "id": data.get("id", ""),
            "title": data.get("title", ""),
            "description": data.get("description", ""),
            "choices": [],
        }

        for ci in (1, 2, 3):
            label = data.get(f"choice_{ci}_label", "")
            desc = data.get(f"choice_{ci}_desc", "")
            action = data.get(f"choice_{ci}_action", "")
            value = data.get(f"choice_{ci}_value")
            if label and action:
                event["choices"].append({
                    "label": label,
                    "description": desc,
                    "action": action,
                    "value": value,
                })

        if event["choices"]:
            events.append(event)

    wb.close()
    return events


def load_events(config_dir: str, data_dir: str) -> list[dict]:
    """从 Excel 加载事件数据。"""
    xlsx_path = os.path.join(config_dir, "events.xlsx")
    if os.path.exists(xlsx_path) and HAS_OPENPYXL:
        return load_events_from_excel(xlsx_path)
    return []


# ── Room Config Loading ─────────────────────────────────────────────────────

ROOM_CONFIG_KEYS = [
    "battle_weight", "event_weight", "elite_weight",
    "merchant_weight", "campfire_weight",
    "battle_gold_min", "battle_gold_max",
    "elite_gold_min", "elite_gold_max",
    "elite_hp_mult", "elite_atk_mult",
    "merchant_card_count", "merchant_remove_cost",
    "merchant_price_common_min", "merchant_price_common_max",
    "merchant_price_rare_min", "merchant_price_rare_max",
    "merchant_price_epic_min", "merchant_price_epic_max",
    "campfire_heal_percent",
]


def load_room_config_from_excel(path: str) -> dict:
    """Load room configuration from an Excel file (key-value format).
    Columns: key, value
    """
    if not HAS_OPENPYXL:
        raise RuntimeError("openpyxl not installed — pip install openpyxl")

    wb = openpyxl.load_workbook(path, read_only=True)
    ws = wb.active
    rows_list = list(ws.iter_rows(values_only=True))
    if len(rows_list) < 2:
        wb.close()
        return {}

    config = {}
    for row in rows_list[1:]:
        if not row or not row[0]:
            continue
        key = _parse_str(row[0]).lower()
        val = row[1] if len(row) > 1 else None
        if key in ROOM_CONFIG_KEYS:
            if "mult" in key or "percent" in key:
                config[key] = _parse_float(val)
            else:
                config[key] = _parse_int(val)

    wb.close()
    return config


def load_room_config(config_dir: str, data_dir: str) -> dict:
    """从 Excel 加载房间配置。"""
    xlsx_path = os.path.join(config_dir, "rooms.xlsx")
    if os.path.exists(xlsx_path) and HAS_OPENPYXL:
        return load_room_config_from_excel(xlsx_path)
    return {}


# ── Template Generation ─────────────────────────────────────────────────────

CARD_COLUMNS_TEMPLATE = [
    "id", "name", "cost", "type", "rarity",
    "attack", "health", "description", "keywords",
    "target", "damage", "shield", "heal",
    "battlecry_type", "battlecry_value",
    "deathrattle_type", "deathrattle_value",
    "element", "status_type", "status_turns", "status_value",
]


def generate_card_template(config_dir: str) -> None:
    """在 config 目录生成卡牌模板文件: cards_B.xlsx, cards_C.xlsx 。

    Pool A：玩家动态收藏池，初始为空，不需要Excel配置。
    Pool B：公共基础卡牌（仅3张：打击/防御/持盾者），硬编码。
    Pool C：唯一需要Excel编辑的池子，包含所有可获得的卡牌。
    """
    if not HAS_OPENPYXL:
        return

    # ═════════════════════════════════════════════════════════
    # Pool B — 公共基础卡牌（玩家和敌人共用）仅3张
    # ═════════════════════════════════════════════════════════
    cards_b = [
        ["strike",        "打击",   1, "attack", "common", 0, 0,
         "", "",       "enemy",  6, 0, 0,  "", 0, "", 0, "",  "", 0, 0],
        ["defend",        "防御",   1, "skill",  "common", 0, 0,
         "", "",       "self",    0, 5, 0,  "", 0, "", 0, "",  "", 0, 0],
        ["shield_bearer", "持盾者", 1, "minion", "common", 0, 3,
         "", "Taunt", "none",    0, 0, 0,  "", 0, "", 0, "",  "", 0, 0],
    ]

    path_b = os.path.join(config_dir, "cards_B.xlsx")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "B"
    ws.append(CARD_COLUMNS_TEMPLATE)
    for row in cards_b:
        ws.append(row)
    wb.save(path_b)

    # ═════════════════════════════════════════════════════════
    # Pool C — 可编辑卡池（原有25张 + TEW新增50张 = 75张）
    # ═════════════════════════════════════════════════════════
    cards_c = [
        # ── 原有 Pool A 的卡牌（15张）────────────────────────────
        ["arcane_missiles", "奥术飞弹",   2, "attack", "common",   0, 0,
         "", "",        "none",    3,  0, 0,  "", 0, "", 0, "",  "", 0, 0],
        ["holy_smite",     "神圣惩击",   3, "attack", "rare",   0, 0,
         "", "Lifesteal","enemy", 10, 0, 5,  "", 0, "", 0, "",  "", 0, 0],
        ["blessing",       "祝福",     2, "skill",  "rare",   0, 0,
         "", "",        "self",    0, 12, 0, "draw", 1, "", 0, "",  "", 0, 0],
        ["fireball",       "火球术",   4, "attack", "rare",   0, 0,
         "", "",        "enemy",  15, 0, 0,  "", 0, "", 0, "fire",  "burn", 2, 3],
        ["holy_nova",      "神圣新星",   5, "attack", "rare",   0, 0,
         "", "",        "none",    8,  0, 8,  "", 0, "", 0, "",  "", 0, 0],
        ["divine_protection","神圣护佑", 3, "skill",  "rare",   0, 0,
         "", "Divine_Shield","self", 0, 8, 0,  "", 0, "", 0, "",  "", 0, 0],
        ["blood_knight",   "鲜血骑士",   2, "minion", "rare",   5, 4,
         "", "",        "none",    0, 0, 0, "damage_self", 3, "", 0, "",  "", 0, 0],
        ["war_drummer",    "战鼓手",   3, "minion", "rare",   3, 3,
         "", "",        "none",    0, 0, 0, "buff_attack", 2, "", 0, "",  "", 0, 0],
        ["army_trainer",   "练兵教官",   4, "minion", "rare",   2, 5,
         "", "",        "none",    0, 0, 0, "buff_health_per_card", 3, "", 0, "",  "", 0, 0],
        ["berserker",      "狂战士",     3, "minion", "rare",   2, 3,
         "", "",        "none",    0, 0, 0, "damage_equal_attack", 0, "", 0, "",  "", 0, 0],
        ["giant_growth",   "巨人成长",   2, "minion", "epic",   1, 1,
         "", "",        "none",    0, 0, 0, "set_stats", 4, "", 0, "",  "", 0, 0],
        ["healing_totem",  "治疗图腾",   2, "minion", "rare",   0, 3,
         "", "Taunt,Lifesteal", "none", 0, 0, 0, "", 0, "", 0, "",  "", 0, 0],
        ["wind_walker",    "风行者",   4, "minion", "epic",   3, 3,
         "", "Charge,Windfury","none", 0, 0, 0, "", 0, "", 0, "",  "", 0, 0],
        ["phoenix_egg",    "凤凰蛋",   2, "minion", "epic",   1, 1,
         "", "",        "none",    0, 0, 0,  "", 0, "draw", 1, "",  "", 0, 0],
        ["explosive_sheep","爆裂绵羊",   2, "minion", "epic",   1, 1,
         "", "",        "none",    0, 0, 0,  "", 0, "damage", 3, "",  "", 0, 0],
        # ── 原有 Pool C 的卡牌（10张）────────────────────────────
        ["dark_bolt",       "暗影箭",   2, "attack", "common", 0, 0,
         "", "",        "enemy",   8,  0, 0,  "", 0, "", 0, "dark",  "", 0, 0],
        ["corrupted_shield","腐化护盾",   1, "skill",  "common", 0, 0,
         "", "",        "self",    0,  6, 0,  "", 0, "", 0, "",  "", 0, 0],
        ["cursed_minion",  "诅咒仆从",   2, "minion", "common", 2, 2,
         "", "Poisonous","none",  0,  0, 0,  "", 0, "", 0, "",  "", 0, 0],
        ["hellfire",       "地狱烈焰",   3, "attack", "rare",   0, 0,
         "", "",        "none",    5,  0, 0,  "", 0, "", 0, "fire",  "", 0, 0],
        ["shadow_flame",   "暗影烈焰",   5, "attack", "rare",   0, 0,
         "", "",        "enemy",  20,  0, 0,  "", 0, "", 0, "dark",  "", 0, 0],
        ["corrupted_guard","腐化守卫",   3, "minion", "common", 3, 4,
         "", "Taunt",    "none",    0,  0, 0,  "", 0, "", 0, "",  "", 0, 0],
        ["void_reaper",    "虚空收割者", 4, "minion", "rare",   3, 3,
         "", "Charge,Lifesteal","none", 0, 0, 0, "", 0, "", 0, "",  "", 0, 0],
        ["frozen_horror",  "冰冻恐魔",   3, "minion", "rare",   3, 5,
         "", "Rush,Divine_Shield","none", 0, 0, 0, "", 0, "", 0, "",  "", 0, 0],
        ["blood_mage",     "鲜血法师",   4, "minion", "epic",   4, 2,
         "", "Windfury,Lifesteal","none", 0, 0, 0, "", 0, "", 0, "",  "", 0, 0],
        ["plague_spreader","瘟疫传播者", 2, "minion", "rare",   1, 3,
         "", "Poisonous","none",  0,  0, 0,  "", 0, "draw", 1, "",  "", 0, 0],

        # ══════════════════════════════════════════════════════════
        # TEW 新增 — 元素使 (Elementalist) 法术系卡牌（13张）
        # ══════════════════════════════════════════════════════════
        ["flame_burst",    "炎弹",     3, "attack", "common", 0, 0,
         "", "",        "none",    4,  0, 0,  "", 0, "", 0, "fire",  "burn", 1, 2],
        ["frost_bolt",     "寒霜术",   3, "attack", "common", 0, 0,
         "", "",        "none",    4,  0, 0,  "", 0, "", 0, "ice",   "slow", 2, 1],
        ["lightning_bolt", "闪电击",   3, "attack", "common", 0, 0,
         "", "",        "none",    4,  0, 0,  "", 0, "", 0, "lightning", "stun", 1, 0],
        ["rock_spike",     "巨岩",     4, "attack", "common", 0, 0,
         "", "",        "enemy",  12,  0, 0,  "", 0, "", 0, "earth",  "", 0, 0],
        ["flame_stream",   "焰流",     4, "attack", "rare",   0, 0,
         "", "",        "enemy",  18,  0, 0,  "", 0, "", 0, "fire",  "burn", 2, 4],
        ["iceberg",        "冰山术",   4, "attack", "rare",   0, 0,
         "", "",        "enemy",  16,  0, 0,  "", 0, "", 0, "ice",   "freeze", 2, 0],
        ["thunder_strike", "雷霆击",   4, "attack", "rare",   0, 0,
         "", "",        "enemy",  16,  0, 0,  "", 0, "", 0, "lightning", "stun", 2, 0],
        ["gale_force",     "罡风",     3, "attack", "rare",   0, 0,
         "", "",        "none",    5,  0, 0,  "", 0, "", 0, "wind",  "shaken", 2, 2],
        ["cyclone",        "气旋",     5, "attack", "rare",   0, 0,
         "", "",        "enemy",  18,  0, 0,  "", 0, "", 0, "wind",   "", 0, 0],
        ["earthquake",     "地动",     3, "attack", "rare",   0, 0,
         "", "",        "none",    5,  0, 0,  "", 0, "", 0, "earth", "slow", 2, 2],
        ["elemental_veil", "元素幕障", 2, "skill",  "common", 0, 0,
         "", "",        "self",    0, 10, 0,  "", 0, "", 0, "",  "shield_up", 2, 3],
        ["element_weapon", "元素武器", 2, "skill",  "rare",   0, 0,
         "", "",        "self",    0,  6, 0, "buff_attack", 2, "", 0, "",  "", 0, 0],
        ["soaring_strike", "翱翔击",   3, "attack", "common", 0, 0,
         "", "",        "enemy",  12,  0, 0,  "", 0, "", 0, "wind",  "shaken", 1, 1],

        # ══════════════════════════════════════════════════════════
        # TEW 新增 — 熵术士 (Entropist) 暗影系卡牌（12张）
        # ══════════════════════════════════════════════════════════
        ["accelerate",     "加速术",   2, "skill",  "rare",   0, 0,
         "", "",        "self",    0,  0, 0, "draw", 2, "", 0, "",  "", 0, 0],
        ["dark_weapon",    "黑暗武器", 2, "skill",  "common", 0, 0,
         "", "",        "self",    0,  5, 0, "", 0, "", 0, "dark",  "", 0, 0],
        ["mind_drain",     "精神汲取", 3, "attack", "rare",   0, 0,
         "", "",        "enemy",  10,  0, 0,  "", 0, "", 0, "dark",  "weaken", 2, 2],
        ["life_drain",     "活力汲取", 4, "attack", "rare",   0, 0,
         "", "Lifesteal","enemy", 10,  0, 3,  "", 0, "", 0, "dark",  "", 0, 0],
        ["oblivion",       "终焉降临", 5, "attack", "epic",   0, 0,
         "", "",        "enemy",  25,  0, 0,  "", 0, "", 0, "dark",  "weaken", 2, 3],
        ["time_stasis",    "时空静滞", 3, "skill",  "rare",   0, 0,
         "", "",        "enemy",   0,  0, 0,  "", 0, "", 0, "",  "freeze", 2, 0],
        ["shadow_strike",  "影袭",     3, "attack", "common", 0, 0,
         "", "",        "none",    4,  0, 0,  "", 0, "", 0, "dark",  "", 0, 0],
        ["mirror_reflect", "镜面反射", 2, "skill",  "rare",   0, 0,
         "", "",        "self",    0,  8, 0,  "", 0, "", 0, "",  "shield_up", 3, 2],
        ["dispel_magic",   "驱散魔法", 2, "skill",  "rare",   0, 0,
         "", "",        "self",    0,  0, 8,  "", 0, "", 0, "",  "", 0, 0],
        ["foresight",      "预言术",   2, "skill",  "epic",   0, 0,
         "", "",        "self",    0,  0, 0, "draw", 3, "", 0, "",  "", 0, 0],
        ["twist_nature",   "扭曲性状", 3, "skill",  "rare",   0, 0,
         "", "",        "enemy",   5,  0, 0,  "", 0, "", 0, "dark", "shaken", 2, 3],
        ["entropy_blast",  "熵能爆发", 4, "attack", "epic",   0, 0,
         "", "",        "none",    8,  0, 0,  "", 0, "", 0, "dark",  "weaken", 2, 2],

        # ══════════════════════════════════════════════════════════
        # TEW 新增 — 暗刃骑士/狂怒斗士/守护者（8张）
        # ══════════════════════════════════════════════════════════
        ["shadow_blade",   "暗影击",   3, "attack", "rare",   0, 0,
         "", "",        "enemy",  12,  0, 0,  "", 0, "", 0, "dark",  "", 0, 0],
        ["agony",          "痛楚",     3, "attack", "rare",   0, 0,
         "", "Lifesteal","enemy", 8,   0, 3,  "", 0, "", 0, "dark",  "", 0, 0],
        ["fury_strike",    "狂怒打击", 2, "attack", "common", 0, 0,
         "", "",        "enemy",   9,  0, 0,  "", 0, "", 0, "",  "", 0, 0],
        ["guardian_shield","守护之盾", 2, "skill",  "common", 0, 0,
         "", "",        "self",    0, 10, 0,  "", 0, "", 0, "",  "shield_up", 2, 2],
        ["precise_shot",   "精准射击", 3, "attack", "common", 0, 0,
         "", "",        "enemy",  11,  0, 0,  "", 0, "", 0, "",  "", 0, 0],
        ["soul_scorch",    "灵魂灼烧", 4, "attack", "rare",   0, 0,
         "", "",        "enemy",  14,  0, 0,  "", 0, "", 0, "dark",  "weaken", 1, 2],
        ["nature_power",   "自然之力", 2, "skill",  "common", 0, 0,
         "", "",        "self",    0,  6, 5,  "", 0, "", 0, "",  "", 0, 0],
        ["healing_touch",  "治疗之触", 2, "skill",  "common", 0, 0,
         "", "",        "self",    0,  0, 10,  "", 0, "", 0, "",  "", 0, 0],

        # ══════════════════════════════════════════════════════════
        # TEW 新增 — 随从/召唤系卡牌（17张）
        # ══════════════════════════════════════════════════════════
        ["fire_elemental","火焰元素",  3, "minion", "rare",   2, 4,
         "", "",        "none",    0, 0, 0, "damage_aoe", 2, "", 0, "fire",  "", 0, 0],
        ["ice_giant",     "冰霜巨人",  4, "minion", "rare",   3, 5,
         "", "Taunt",   "none",    0, 0, 0,  "", 0, "", 0, "ice",   "freeze", 1, 0],
        ["shadow_assassin","暗影刺客", 3, "minion", "rare",   4, 2,
         "", "Charge",   "none",    0, 0, 0,  "", 0, "", 0, "dark",  "", 0, 0],
        ["spirit_wolf",   "幽灵狼",    2, "minion", "common", 2, 3,
         "", "Rush",     "none",    0, 0, 0,  "", 0, "", 0, "",  "", 0, 0],
        ["mech_sentry",   "机械哨兵",  3, "minion", "common", 3, 3,
         "", "",        "none",    0, 0, 0,  "", 0, "", 0, "",  "", 0, 0],
        ["guardian_golem","守护石像",  4, "minion", "common", 2, 6,
         "", "Taunt",   "none",    0, 0, 0,  "", 0, "", 0, "",  "", 0, 0],
        ["storm_elemental","风暴元素", 3, "minion", "rare",   2, 3,
         "", "Windfury","none",    0, 0, 0,  "", 0, "", 0, "wind",  "", 0, 0],
        ["earth_elemental","大地元素", 3, "minion", "common", 1, 5,
         "", "Taunt",   "none",    0, 0, 0,  "", 0, "", 0, "earth", "", 0, 0],
        ["lightning_sprite","电光精灵",2, "minion", "rare",   2, 2,
         "", "Charge",  "none",    0, 0, 0, "apply_status", 0, "", 0, "lightning", "", 0, 0],
        ["arcane_spirit", "奥灵",      4, "minion", "epic",   4, 4,
         "", "Divine_Shield","none",0, 0, 0, "shield_all", 3, "", 0, "",  "", 0, 0],
        ["plague_rat",    "瘟疫鼠",    2, "minion", "common", 1, 2,
         "", "Poisonous","none",   0, 0, 0,  "", 0, "", 0, "",  "poison", 2, 1],
        ["warbanner",     "战旗",      2, "minion", "rare",   1, 3,
         "", "",        "none",    0, 0, 0, "buff_attack", 2, "", 0, "",  "", 0, 0],
        ["priestess",     "女祭司",    3, "minion", "rare",   2, 2,
         "", "",        "none",    0, 0, 0, "heal_all", 4, "", 0, "",  "", 0, 0],
        ["doom_sayer",    "末日预言者",2, "minion", "epic",   0, 4,
         "", "",        "none",    0, 0, 0,  "", 0, "damage", 5, "",  "", 0, 0],
        ["chimera",       "奇美拉",    4, "minion", "epic",   5, 4,
         "", "Rush,Poisonous","none", 0, 0, 0, "", 0, "", 0, "",  "", 0, 0],
        ["dark_knight",   "暗刃骑士",  4, "minion", "epic",   5, 3,
         "", "Charge,Lifesteal","none",0, 0, 0, "damage_self", 2, "", 0, "dark", "", 0, 0],
        ["mech_golem",    "机械傀儡",  5, "minion", "epic",   6, 6,
         "", "Taunt,Divine_Shield","none", 0, 0, 0, "", 0, "", 0, "",  "", 0, 0],
    ]

    path_c = os.path.join(config_dir, "cards_C.xlsx")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "C"
    ws.append(CARD_COLUMNS_TEMPLATE)
    for row in cards_c:
        ws.append(row)
    wb.save(path_c)


def generate_enemy_template(path: str) -> None:
    """Create a template enemies.xlsx with headers and example rows."""
    if not HAS_OPENPYXL:
        return
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "敌人"
    ws.append(ENEMY_COLUMNS)
    ws.append(["slime", "史莱姆", 12, 4, False, 1, "attack", "always_attack", ""])
    ws.append(["goblin", "哥布林侦察兵", 10, 6, False, 1, "attack", "alternate", ""])
    ws.append(["orc_warlord", "兽人战领主", 50, 8, True, 5, "attack", "buff_then_attack", "Taunt"])
    wb.save(path)


def generate_events_template(path: str) -> None:
    """Create a template events.xlsx with example events."""
    if not HAS_OPENPYXL:
        return
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "事件"
    ws.append(EVENT_COLUMNS)
    ws.append([
        "treasure_chest", "宝箱", "你发现了一个尘封已久的宝箱。要打开它吗？",
        "打开宝箱", "获得 15~35 金币", "gold", '{"min":15,"max":35}',
        "仔细检查", "可能获得一张卡牌", "random_card", "",
        "离开", "不冒风险", "nothing", "",
    ])
    ws.append([
        "mysterious_stranger", "神秘陌生人", "一个披着斗篷的人向你招手。",
        "接受交易", "失去 15 HP，获得 40 金币 + 一张卡牌", "trade_hp_gold_card", '{"hp":15,"gold":40}',
        "拒绝", "安全离开", "nothing", "",
        "", "", "", "",
    ])
    ws.append([
        "ancient_shrine", "远古神龛", "一座散发微光的神龛，上面铭刻着古老的符文。",
        "祈祷（移除卡牌）", "从牌组中移除一张牌", "remove_card", "",
        "亵渎（获得金币）", "获得 25 金币，但失去 8 HP", "desecrate", '{"gold":25,"hp":8}',
        "离开", "不做任何事", "nothing", "",
    ])
    ws.append([
        "healing_spring", "生命之泉", "一汪清澈的泉水散发着温暖的光芒。",
        "饮用泉水", "回复 30% 最大生命值", "heal", "0.3",
        "装满水壶", "获得 20 护盾（永久）", "shield", "20",
        "离开", "不做任何事", "nothing", "",
    ])
    ws.append([
        "gambler", "赌徒", "一个笑嘻嘻的人邀请你玩一局。",
        "赌一把！", "50% 概率获得 50 金币，50% 失去 20 金币", "gamble", '{"win":50,"lose":20}',
        "不赌", "安全离开", "nothing", "",
        "", "", "", "",
    ])
    ws.append([
        "blacksmith", "废弃铁匠铺", "一个废弃的铁匠铺，炉火竟然还在燃烧。",
        "免费锻造", "免费升级一张卡牌", "upgrade_card_free", "",
        "离开", "不做任何事", "nothing", "",
        "", "", "", "",
    ])
    ws.append([
        "sacrificial_altar", "献祭祭坛", "一座古老祭坛，上面有干涸的血迹。",
        "献祭一张牌", "牺牲一张牌，获得 30 金币", "sacrifice_card", "30",
        "献祭鲜血", "失去 20 HP，获得一张稀有卡牌", "sacrifice_hp", "20",
        "离开", "不做任何事", "nothing", "",
    ])
    ws.append([
        "cursed_book", "诅咒之书", "一本散发着邪恶气息的古书。",
        "翻阅", "受到 10 点伤害，获得一张史诗卡牌", "cursed_card", "10",
        "合上书本", "安全离开", "nothing", "",
        "", "", "", "",
    ])
    ws.append([
        "angel_statue", "天使雕像", "一座精美的天使雕像，双手捧着一个发光的球体。",
        "触摸光球", "回复 15 HP + 获得 12 护盾", "angel_heal", '{"hp":15,"shield":12}',
        "祈祷", "回复 25 HP", "heal", "25",
        "离开", "不做任何事", "nothing", "",
    ])
    ws.append([
        "demon_contract", "恶魔契约", "一个恶魔出现在火焰中，递出一份契约。",
        "签署契约", "损失 25% 最大HP → 永久 +3 攻击力", "demon_buff", "0.25",
        "拒绝", "安全离开", "nothing", "",
        "", "", "", "",
    ])
    wb.save(path)


def generate_room_config_template(path: str) -> None:
    """Create a template rooms.xlsx with key-value config."""
    if not HAS_OPENPYXL:
        return
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "房间配置"
    ws.append(["key", "value"])
    ws.append(["battle_weight", 50])
    ws.append(["event_weight", 25])
    ws.append(["elite_weight", 10])
    ws.append(["merchant_weight", 10])
    ws.append(["campfire_weight", 5])
    ws.append(["battle_gold_min", 12])
    ws.append(["battle_gold_max", 25])
    ws.append(["elite_gold_min", 30])
    ws.append(["elite_gold_max", 50])
    ws.append(["elite_hp_mult", 1.5])
    ws.append(["elite_atk_mult", 1.3])
    ws.append(["merchant_card_count", 4])
    ws.append(["merchant_remove_cost", 50])
    ws.append(["merchant_price_common_min", 25])
    ws.append(["merchant_price_common_max", 35])
    ws.append(["merchant_price_rare_min", 50])
    ws.append(["merchant_price_rare_max", 70])
    ws.append(["merchant_price_epic_min", 85])
    ws.append(["merchant_price_epic_max", 120])
    ws.append(["campfire_heal_percent", 0.3])
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
