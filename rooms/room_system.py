"""Room system — Slay the Spire style room generation, events, merchant, campfire.
All parameters are configurable via Excel (see excel_loader.py).
Call set_events() / set_room_config() before using any function, or defaults are used.
"""

from __future__ import annotations
from enum import Enum, auto
import random
from dataclasses import dataclass, field
from typing import Any
from debug_probes import probe

# ── Room Types ──────────────────────────────────────────────────────

class RoomType(Enum):
    BATTLE = auto()      # 普通战斗
    ELITE = auto()       # 精英战斗（更强敌人，更好奖励）
    EVENT = auto()       # 随机事件
    MERCHANT = auto()    # 商人
    CAMPFIRE = auto()    # 篝火


@dataclass
class Room:
    room_type: RoomType
    room_number: int = 0
    enemies_alive: int = 0
    completed: bool = False


# ── Module-level config (set externally from main.py) ──────────────

_events: list[dict] | None = None
_room_config: dict | None = None


def set_events(events: list[dict]) -> None:
    """Inject events from an external source (e.g. loaded from Excel)."""
    global _events
    _events = events


def set_room_config(config: dict) -> None:
    """Inject room configuration from an external source."""
    global _room_config
    _room_config = config


# ── Defaults (used when no Excel config is loaded) ──────────────────

def _cfg(key: str, default: Any) -> Any:
    """Get a config value, falling back to default."""
    if _room_config and key in _room_config:
        return _room_config[key]
    return default


def _get_events() -> list[dict]:
    """Return current events (loaded or defaults)."""
    if _events:
        return _events
    return _get_default_events()


def _get_default_events() -> list[dict]:
    """Default event pool — used when no events.xlsx is loaded."""
    return [
        {
            "id": "treasure_chest",
            "title": "宝箱",
            "description": "你发现了一个尘封已久的宝箱。要打开它吗？",
            "choices": [
                {"label": "打开宝箱", "description": "获得 15~35 金币", "action": "gold", "value": {"min": 15, "max": 35}},
                {"label": "仔细检查", "description": "可能获得一张卡牌", "action": "random_card"},
                {"label": "离开", "description": "不冒风险", "action": "nothing"},
            ],
        },
        {
            "id": "mysterious_stranger",
            "title": "神秘陌生人",
            "description": "一个披着斗篷的人向你招手。",
            "choices": [
                {"label": "接受交易", "description": "失去 15 HP，获得 40 金币 + 一张卡牌", "action": "trade_hp_gold_card", "value": {"hp": 15, "gold": 40}},
                {"label": "拒绝", "description": "安全离开", "action": "nothing"},
            ],
        },
        {
            "id": "ancient_shrine",
            "title": "远古神龛",
            "description": "一座散发微光的神龛，上面铭刻着古老的符文。",
            "choices": [
                {"label": "祈祷（移除卡牌）", "description": "从牌组中移除一张牌", "action": "remove_card"},
                {"label": "亵渎（获得金币）", "description": "获得 25 金币，但失去 8 HP", "action": "desecrate", "value": {"gold": 25, "hp": 8}},
                {"label": "离开", "description": "不做任何事", "action": "nothing"},
            ],
        },
        {
            "id": "healing_spring",
            "title": "生命之泉",
            "description": "一汪清澈的泉水散发着温暖的光芒。",
            "choices": [
                {"label": "饮用泉水", "description": "回复 30% 最大生命值", "action": "heal", "value": 0.3},
                {"label": "装满水壶", "description": "获得 20 护盾（永久）", "action": "shield", "value": 20},
                {"label": "离开", "description": "不做任何事", "action": "nothing"},
            ],
        },
        {
            "id": "gambler",
            "title": "赌徒",
            "description": "一个笑嘻嘻的人邀请你玩一局。",
            "choices": [
                {"label": "赌一把！", "description": "50% 概率获得 50 金币，50% 失去 20 金币", "action": "gamble", "value": {"win": 50, "lose": 20}},
                {"label": "不赌", "description": "安全离开", "action": "nothing"},
            ],
        },
        {
            "id": "blacksmith",
            "title": "废弃铁匠铺",
            "description": "一个废弃的铁匠铺，炉火竟然还在燃烧。",
            "choices": [
                {"label": "免费锻造", "description": "免费升级一张卡牌", "action": "upgrade_card_free"},
                {"label": "离开", "description": "不做任何事", "action": "nothing"},
            ],
        },
        {
            "id": "sacrificial_altar",
            "title": "献祭祭坛",
            "description": "一座古老祭坛，上面有干涸的血迹。",
            "choices": [
                {"label": "献祭一张牌", "description": "牺牲一张牌，获得 30 金币", "action": "sacrifice_card", "value": 30},
                {"label": "献祭鲜血", "description": "失去 20 HP，获得一张稀有卡牌", "action": "sacrifice_hp", "value": 20},
                {"label": "离开", "description": "不做任何事", "action": "nothing"},
            ],
        },
        {
            "id": "cursed_book",
            "title": "诅咒之书",
            "description": "一本散发着邪恶气息的古书。",
            "choices": [
                {"label": "翻阅", "description": "受到 10 点伤害，获得一张史诗卡牌", "action": "cursed_card", "value": 10},
                {"label": "合上书本", "description": "安全离开", "action": "nothing"},
            ],
        },
        {
            "id": "angel_statue",
            "title": "天使雕像",
            "description": "一座精美的天使雕像，双手捧着一个发光的球体。",
            "choices": [
                {"label": "触摸光球", "description": "回复 15 HP + 获得 12 护盾", "action": "angel_heal", "value": {"hp": 15, "shield": 12}},
                {"label": "祈祷", "description": "回复 25 HP", "action": "heal", "value": 25},
                {"label": "离开", "description": "不做任何事", "action": "nothing"},
            ],
        },
        {
            "id": "demon_contract",
            "title": "恶魔契约",
            "description": "一个恶魔出现在火焰中，递出一份契约。",
            "choices": [
                {"label": "签署契约", "description": "损失 25% 最大HP → 永久 +3 攻击力", "action": "demon_buff", "value": 0.25},
                {"label": "拒绝", "description": "安全离开", "action": "nothing"},
            ],
        },
    ]


# ── Room Generation ─────────────────────────────────────────────────

def generate_next_room(last_type: RoomType | None, room_number: int) -> Room:
    """Generate the next room type with weighted randomness and constraints.

    - First room always BATTLE
    - No two MERCHANT or CAMPFIRE in a row
    - Every 5th room forces ELITE (like boss wave)
    - Weights are configurable via rooms.xlsx
    """
    if room_number <= 1:
        return Room(RoomType.BATTLE, room_number)

    # Every 5th room is ELITE
    if room_number % 5 == 0:
        return Room(RoomType.ELITE, room_number)

    # Weighted pool with constraints (from config or defaults)
    pool = {
        RoomType.BATTLE: _cfg("battle_weight", 50),
        RoomType.EVENT: _cfg("event_weight", 25),
        RoomType.ELITE: _cfg("elite_weight", 10),
        RoomType.MERCHANT: _cfg("merchant_weight", 10),
        RoomType.CAMPFIRE: _cfg("campfire_weight", 5),
    }

    # ── 难度系统：调整精英概率 ──────────────────────────────
    try:
        from systems.difficulty_system import get_difficulty
        dm = get_difficulty()
        pool[RoomType.ELITE] = dm.elite_weight
    except ImportError:
        pass

    # Constraints: no consecutive MERCHANT or CAMPFIRE
    if last_type == RoomType.MERCHANT:
        pool[RoomType.MERCHANT] = 0
    if last_type == RoomType.CAMPFIRE:
        pool[RoomType.CAMPFIRE] = 0

    types = list(pool.keys())
    weights = [pool[t] for t in types]

    chosen = random.choices(types, weights=weights, k=1)[0]
    room = Room(chosen, room_number)
    probe("room::generate", f"生成房间: {chosen.name}",
          {"number": room_number, "type": chosen.name}, module="room")
    return room


# ── Gold System ─────────────────────────────────────────────────────

def battle_gold_reward(is_elite: bool = False) -> int:
    """Gold rewarded after winning a battle. Configurable via rooms.xlsx."""
    if is_elite:
        lo = _cfg("elite_gold_min", 30)
        hi = _cfg("elite_gold_max", 50)
    else:
        lo = _cfg("battle_gold_min", 12)
        hi = _cfg("battle_gold_max", 25)
    return random.randint(lo, hi)


# ── Elite Enemy Modifier ────────────────────────────────────────────

def elite_stat_multipliers() -> dict:
    """Return HP and ATK multipliers for elite enemies. Uses DifficultyManager if available."""
    try:
        from systems.difficulty_system import get_difficulty
        return get_difficulty().elite_stat_multiplier()
    except ImportError:
        return {
            "hp_mult": _cfg("elite_hp_mult", 1.5),
            "atk_mult": _cfg("elite_atk_mult", 1.3),
        }


# ── Event System ────────────────────────────────────────────────────

class EventChoice:
    """Represents a single choice in an event (for backwards compat)."""
    def __init__(self, label: str, description: str, action: str, value: Any = None):
        self.label = label
        self.description = description
        self.action = action
        self.value = value


class Event:
    """Represents a game event (for backwards compat)."""
    def __init__(self, event_id: str, title: str, description: str, choices: list[EventChoice] | None = None):
        self.event_id = event_id
        self.title = title
        self.description = description
        self.choices = choices or []


def generate_random_event() -> dict:
    """Pick a random event from the pool (loaded from Excel or defaults)."""
    pool = _get_events()
    if not pool:
        return {}
    return random.choice(pool).copy()


# ── Merchant System ─────────────────────────────────────────────────

def merchant_card_price(rarity: str) -> int:
    """Price of a card based on rarity. Configurable via rooms.xlsx."""
    key_map = {
        "common": ("merchant_price_common_min", "merchant_price_common_max"),
        "rare": ("merchant_price_rare_min", "merchant_price_rare_max"),
        "epic": ("merchant_price_epic_min", "merchant_price_epic_max"),
    }
    defaults = {
        "common": (25, 35),
        "rare": (50, 70),
        "epic": (85, 120),
    }
    # legendary uses epic prices as fallback (or fixed high price)
    if rarity == "legendary":
        lo = _cfg("merchant_price_epic_min", 140)
        hi = _cfg("merchant_price_epic_max", 200)
        return random.randint(lo, hi)

    lo_key, hi_key = key_map.get(rarity, ("merchant_price_common_min", "merchant_price_common_max"))
    lo_default, hi_default = defaults.get(rarity, (25, 35))
    lo = _cfg(lo_key, lo_default)
    hi = _cfg(hi_key, hi_default)
    return random.randint(lo, hi)


def merchant_remove_price() -> int:
    """Cost to remove a card from deck. Configurable via rooms.xlsx."""
    return _cfg("merchant_remove_cost", 50)


def merchant_card_count() -> int:
    """Number of cards the merchant offers for sale. Configurable via rooms.xlsx."""
    return _cfg("merchant_card_count", 4)


# ── Campfire System ─────────────────────────────────────────────────

def campfire_heal_percent() -> float:
    """Heal percentage at campfire. Configurable via rooms.xlsx, scaled by difficulty."""
    base = _cfg("campfire_heal_percent", 0.3)
    try:
        from systems.difficulty_system import get_difficulty
        dm = get_difficulty()
        return base * dm.campfire_heal_multiplier()
    except ImportError:
        return base
