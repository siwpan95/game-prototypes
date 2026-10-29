"""Difficulty gradient system for KARD.

Provides:
- 5 difficulty tiers (新手→深渊) with non-linear stat scaling
- Ascension levels 0-5 as global modifiers
- Enemy card pool quality filtering by tier
- Enemy AI pattern selection by tier
- Enemy keyword assignment by tier
- Reward/gold scaling modifiers
"""

from __future__ import annotations
import random
from dataclasses import dataclass
from typing import Any
from debug_probes import probe


# ── Tier Definitions ──────────────────────────────────────────────────────

@dataclass(frozen=True)
class DifficultyTier:
    """Defines the stat scaling and behavior for a difficulty tier."""
    level: int           # 1-5
    name: str            # Display name
    room_range: tuple[int, int]   # Min/max room numbers (inclusive)
    hp_mult: float       # Base HP multiplier at tier start
    atk_mult: float      # Base ATK multiplier at tier start
    hp_growth: float     # Additional HP multiplier per room within tier
    atk_growth: float    # Additional ATK multiplier per room within tier
    ai_pattern: str      # Default enemy AI pattern for this tier
    card_rarity_cap: str  # Max card rarity enemies can use: "common"/"rare"/"epic"
    min_keywords: int    # Min keywords on enemies
    max_keywords: int    # Max keywords on enemies
    enemy_count_min: int # Min enemies per room
    enemy_count_max: int # Max enemies per room
    boss_extra_kw: int   # Extra keywords on bosses


TIERS: tuple[DifficultyTier, ...] = (
    DifficultyTier(1, "新手",  (1, 4),   1.0, 1.0,  0.00, 0.00,
                   "always_attack", "common", 0, 0, 1, 2, 0),
    DifficultyTier(2, "进阶",  (5, 9),   2.0, 1.5,  0.08, 0.05,
                   "alternate", "rare", 0, 1, 1, 3, 1),
    DifficultyTier(3, "困难",  (10, 14), 3.5, 2.2,  0.10, 0.08,
                   "buff_then_attack", "epic", 1, 1, 2, 3, 1),
    DifficultyTier(4, "地狱",  (15, 19), 5.5, 3.0,  0.15, 0.10,
                   "alternate", "epic", 1, 2, 2, 4, 2),
    DifficultyTier(5, "深渊",  (20, 999),8.0, 4.0,  0.20, 0.15,
                   "buff_then_attack", "epic", 2, 2, 2, 4, 2),
)

# ── Ascension Definitions ─────────────────────────────────────────────────

@dataclass(frozen=True)
class AscensionLevel:
    """Global difficulty modifier applied across the entire run."""
    level: int
    name: str
    hp_bonus: float       # Multiplicative HP bonus (e.g. 0.15 = +15%)
    atk_bonus: float      # Multiplicative ATK bonus
    initial_shield: int    # Enemies start with this much shield per tier
    elite_weight_bonus: int # Extra elite room weight (%)
    merchant_price_bonus: float  # Multiplier on merchant prices
    boss_extra_keywords: int     # Extra boss keywords beyond tier default
    campfire_heal_mult: float    # Campfire heal multiplier
    enemy_card_rarity_bonus: int # N% chance to upgrade enemy card rarity


ASCENSION_LEVELS: tuple[AscensionLevel, ...] = (
    AscensionLevel(0, "标准",     0.00, 0.00, 0, 0,  1.00, 0, 1.00, 0),
    AscensionLevel(1, "挑战",     0.15, 0.15, 0, 5,  1.00, 0, 1.00, 0),
    AscensionLevel(2, "噩梦",     0.15, 0.15, 2, 5,  1.20, 0, 0.80, 0),
    AscensionLevel(3, "地狱",     0.30, 0.20, 3, 10, 1.20, 1, 0.80, 0),
    AscensionLevel(4, "炼狱",     0.30, 0.20, 4, 10, 1.30, 1, 0.50, 0),
    AscensionLevel(5, "终焉",     0.50, 0.30, 5, 15, 1.40, 2, 0.50, 15),
)

# Default ascension (used when no selection has been made)
DEFAULT_ASCENSION = 0
MAX_ASCENSION = 5


# ── Difficulty Manager ────────────────────────────────────────────────────

class DifficultyManager:
    """Central difficulty calculator.

    Usage:
        dm = DifficultyManager(ascension=2)
        tier = dm.get_tier(room_number=12)
        hp = dm.scale_enemy_hp(base_hp=20, room_number=12, is_boss=False)
        ai = dm.get_ai_pattern(room_number=12)
        kw_count = dm.get_keyword_count(room_number=12, is_boss=False)
        cards = dm.filter_card_pool(all_cards, room_number=12)
    """

    def __init__(self, ascension: int = DEFAULT_ASCENSION) -> None:
        self.ascension = max(0, min(ascension, MAX_ASCENSION))

    @property
    def asc_data(self) -> AscensionLevel:
        return ASCENSION_LEVELS[self.ascension]

    # ── Tier Resolution ──────────────────────────────────────────────────

    def get_tier(self, room_number: int) -> DifficultyTier:
        """Return the difficulty tier for a given room number."""
        for tier in TIERS:
            lo, hi = tier.room_range
            if lo <= room_number <= hi:
                return tier
        return TIERS[-1]  # fallback: deepest tier

    @property
    def current_tier_label(self) -> str:
        return "深渊"  # placeholder; actual label depends on room_number

    def tier_label(self, room_number: int) -> str:
        tier = self.get_tier(room_number)
        probe("diff::tier", "梯度查询",
              {"room": room_number, "tier": tier.name,
               "hp": round(tier.hp_mult*(1+self.asc_data.hp_bonus),2)},
              module="difficulty")
        return f"T{tier.level}·{tier.name}"

    # ── Stat Scaling ─────────────────────────────────────────────────────

    def scale_enemy_hp(self, base_hp: float, room_number: int,
                        is_boss: bool = False) -> int:
        """Calculate scaled HP for an enemy at the given room."""
        tier = self.get_tier(room_number)
        lo = tier.room_range[0]
        rooms_in = room_number - lo
        mult = tier.hp_mult + rooms_in * tier.hp_growth
        mult *= (1.0 + self.asc_data.hp_bonus)
        if is_boss:
            mult *= 3.0  # Boss gets extra 3x on top of tier scaling
        return max(1, int(base_hp * mult))

    def scale_enemy_atk(self, base_atk: float, room_number: int,
                         is_boss: bool = False) -> int:
        """Calculate scaled ATK for an enemy at the given room."""
        tier = self.get_tier(room_number)
        lo = tier.room_range[0]
        rooms_in = room_number - lo
        mult = tier.atk_mult + rooms_in * tier.atk_growth
        mult *= (1.0 + self.asc_data.atk_bonus)
        if is_boss:
            mult *= 1.8
        return max(1, int(base_atk * mult))

    def scale_enemy_count(self, room_number: int) -> int:
        """Number of enemies to spawn for the given room."""
        tier = self.get_tier(room_number)
        return random.randint(tier.enemy_count_min, tier.enemy_count_max)

    # ── Initial Shield (Ascension bonus) ────────────────────────────────

    def get_initial_shield(self, room_number: int) -> int:
        """Shield enemies start with (from ascension level)."""
        asc_shield = self.asc_data.initial_shield
        if asc_shield <= 0:
            return 0
        tier = self.get_tier(room_number)
        return asc_shield * tier.level

    # ── AI Pattern ───────────────────────────────────────────────────────

    def get_ai_pattern(self, room_number: int, is_boss: bool = False) -> str:
        """Return the AI intent pattern for enemies at this room."""
        tier = self.get_tier(room_number)
        # Bosses get 1 tier upgrade in AI
        if is_boss:
            idx = min(tier.level, len(TIERS) - 1)
            return TIERS[idx].ai_pattern
        return tier.ai_pattern

    # ── Keyword Assignment ───────────────────────────────────────────────

    def get_keyword_count(self, room_number: int, is_boss: bool = False) -> int:
        """Number of keywords to assign to an enemy at this room."""
        tier = self.get_tier(room_number)
        base = random.randint(tier.min_keywords, tier.max_keywords)
        if is_boss:
            base += tier.boss_extra_kw
            base += self.asc_data.boss_extra_keywords
        return base

    AVAILABLE_ENEMY_KEYWORDS = [
        "Taunt", "Rush", "Divine_Shield", "Lifesteal", "Poisonous", "Windfury",
    ]

    def pick_keywords(self, room_number: int, is_boss: bool = False) -> list[str]:
        """Pick random keywords for an enemy based on difficulty."""
        count = self.get_keyword_count(room_number, is_boss)
        if count <= 0:
            return []
        return random.sample(
            self.AVAILABLE_ENEMY_KEYWORDS,
            k=min(count, len(self.AVAILABLE_ENEMY_KEYWORDS)),
        )

    # ── Card Pool Filtering ──────────────────────────────────────────────

    def filter_card_pool(self, all_cards: list[dict], room_number: int) -> list[dict]:
        """Filter card pool by rarity based on current difficulty tier."""
        tier = self.get_tier(room_number)
        rarity_order = {"common": 0, "rare": 1, "epic": 2}
        cap = rarity_order.get(tier.card_rarity_cap, 2)

        filtered = [
            c for c in all_cards
            if rarity_order.get(c.get("rarity", "common"), 0) <= cap
        ]
        if not filtered:
            return all_cards  # fallback

        # Ascension rarity bonus: N% chance to include higher rarity
        bonus = self.asc_data.enemy_card_rarity_bonus
        if bonus > 0:
            for c in all_cards:
                if c not in filtered and random.randint(1, 100) <= bonus:
                    filtered.append(c)

        return filtered

    # ── Elite Config ─────────────────────────────────────────────────────

    def elite_stat_multiplier(self) -> dict[str, float]:
        """Return HP/ATK multipliers for elite enemies."""
        base_hp = 1.5
        base_atk = 1.3
        asc_atk_bonus = self.asc_data.atk_bonus * 0.5
        return {
            "hp_mult": base_hp + self.asc_data.hp_bonus,
            "atk_mult": base_atk + asc_atk_bonus,
        }

    @property
    def elite_weight(self) -> int:
        """Weight of elite rooms in room generation."""
        return 10 + self.asc_data.elite_weight_bonus

    # ── Reward Scaling ───────────────────────────────────────────────────

    def gold_multiplier(self, room_number: int) -> float:
        """Gold reward multiplier based on room progression."""
        tier = self.get_tier(room_number)
        return 1.0 + (tier.level - 1) * 0.25

    def merchant_price_multiplier(self) -> float:
        """Merchant price multiplier from ascension."""
        return self.asc_data.merchant_price_bonus

    def campfire_heal_multiplier(self) -> float:
        """Campfire heal multiplier from ascension."""
        return self.asc_data.campfire_heal_mult

    # ── Display ──────────────────────────────────────────────────────────

    def summary(self, room_number: int = 1) -> dict[str, Any]:
        """Return a summary dict for UI display."""
        tier = self.get_tier(room_number)
        asc = self.asc_data
        return {
            "ascension": self.ascension,
            "ascension_name": asc.name,
            "tier": tier.level,
            "tier_name": tier.name,
            "hp_mult": round(tier.hp_mult * (1 + asc.hp_bonus), 2),
            "atk_mult": round(tier.atk_mult * (1 + asc.atk_bonus), 2),
            "ai": tier.ai_pattern,
            "elite_weight": self.elite_weight,
            "merchant_price": f"{int(asc.merchant_price_bonus * 100)}%",
            "campfire_heal": f"{int(asc.campfire_heal_mult * 100)}%",
        }


# ── Singleton access ──────────────────────────────────────────────────────

_global_difficulty: DifficultyManager | None = None


def get_difficulty() -> DifficultyManager:
    """Return the global DifficultyManager singleton."""
    global _global_difficulty
    if _global_difficulty is None:
        _global_difficulty = DifficultyManager(DEFAULT_ASCENSION)
    return _global_difficulty


def set_difficulty(ascension: int) -> DifficultyManager:
    """Set the global difficulty level and return the manager."""
    global _global_difficulty
    _global_difficulty = DifficultyManager(ascension)
    return _global_difficulty
