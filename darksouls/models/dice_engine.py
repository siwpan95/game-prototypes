"""DiceEngine - d20 attack roll and dice notation parser."""

import random
import re


class DiceResult:
    """Result of a dice roll."""

    def __init__(self, total: int, rolls: list[int], modifier: int = 0, is_crit: bool = False, is_mishap: bool = False) -> None:
        self.total = total
        self.rolls = rolls
        self.modifier = modifier
        self.is_crit = is_crit
        self.is_mishap = is_mishap

    def __repr__(self) -> str:
        parts = [f"rolls={self.rolls}"]
        if self.modifier:
            parts.append(f"mod={self.modifier}")
        return f"DiceResult({', '.join(parts)}) -> {self.total}"


class DiceEngine:
    """Handles all dice-related mechanics.

    d20 attack roll:
        1  = Mishap (negative consequence for the roller)
        2-5 = Miss
        6-19 = Hit
        20  = Critical hit (double damage dice)

    Dice notation parser:
        Supports 'NdS+MOD' format, e.g., '2d6+3', '4d6', '1d6+STR'.
        'STR' and 'DEX' are replaced with the provided stat values.
    """

    # d20 result thresholds
    MISHAP = 1
    MISS_MAX = 5
    HIT_MIN = 6
    CRIT = 20

    @staticmethod
    def roll_d20(stat_modifier: int = 0) -> DiceResult:
        """Roll a d20 for attack determination.

        Args:
            stat_modifier: STR modifier added to the roll.

        Returns:
            DiceResult with the raw roll, is_crit, and is_mishap flags.
        """
        raw = random.randint(1, 20)
        total = raw + stat_modifier
        is_crit = raw == DiceEngine.CRIT
        is_mishap = raw == DiceEngine.MISHAP
        return DiceResult(
            total=total,
            rolls=[raw],
            modifier=stat_modifier,
            is_crit=is_crit,
            is_mishap=is_mishap,
        )

    @staticmethod
    def roll_d6() -> int:
        """Roll a single d6."""
        return random.randint(1, 6)

    @staticmethod
    def roll_3d6() -> DiceResult:
        """Roll 3d6 for damage."""
        rolls = [DiceEngine.roll_d6() for _ in range(3)]
        return DiceResult(total=sum(rolls), rolls=rolls)

    @staticmethod
    def parse_dice_notation(notation: str, str_val: int = 0, dex_val: int = 0) -> DiceResult:
        """Parse and roll dice notation like '2d6+STR' or '4d6'.

        Supported formats:
            NdS       - roll N dice of S sides
            NdS+MOD   - roll N dice of S sides, add MOD
            NdS+STR   - roll N dice of S sides, add STR stat value
            NdS+DEX   - roll N dice of S sides, add DEX stat value
            NdS-MOD   - subtract modifier

        Args:
            notation: Dice notation string.
            str_val: Player's current STR stat.
            dex_val: Player's current DEX stat.

        Returns:
            DiceResult with roll details.
        """
        notation = notation.strip()
        if notation == "0" or notation == "":
            return DiceResult(total=0, rolls=[], modifier=0)

        # Replace stat references with values
        notation_resolved = notation.replace("+STR", f"+{str_val}")
        notation_resolved = notation_resolved.replace("+DEX", f"+{dex_val}")

        # Parse: NdS[+/-MOD]
        pattern = r"^(\d+)d(\d+)([+-]\d+)?$"
        match = re.match(pattern, notation_resolved)
        if not match:
            return DiceResult(total=0, rolls=[], modifier=0)

        num_dice = int(match.group(1))
        die_sides = int(match.group(2))
        modifier = int(match.group(3)) if match.group(3) else 0

        rolls = [random.randint(1, die_sides) for _ in range(num_dice)]
        total = sum(rolls) + modifier
        return DiceResult(total=total, rolls=rolls, modifier=modifier)

    @staticmethod
    def roll_attack_damage(damage_notation: str, is_crit: bool, str_val: int = 0, dex_val: int = 0) -> DiceResult:
        """Roll damage for an attack card.

        On crit, the damage dice are doubled (before modifiers).

        Args:
            damage_notation: Dice notation string from the card.
            is_crit: Whether the d20 attack roll was a critical hit.
            str_val: Player's current STR stat.
            dex_val: Player's current DEX stat.

        Returns:
            DiceResult with the final damage total.
        """
        if damage_notation == "0" or damage_notation == "":
            return DiceResult(total=0, rolls=[], modifier=0)

        # On crit, double the number of dice
        if is_crit:
            notation_resolved = damage_notation.replace("+STR", f"+{str_val}").replace("+DEX", f"+{dex_val}")
            pattern = r"^(\d+)d(\d+)([+-]\d+)?$"
            match = re.match(pattern, notation_resolved)
            if match:
                num_dice = int(match.group(1)) * 2
                die_sides = int(match.group(2))
                modifier = int(match.group(3)) if match.group(3) else 0
                rolls = [random.randint(1, die_sides) for _ in range(num_dice)]
                total = sum(rolls) + modifier
                return DiceResult(total=total, rolls=rolls, modifier=modifier)

        return DiceEngine.parse_dice_notation(damage_notation, str_val, dex_val)
