"""
3D6 Dice System for Russian Roulette.
Handles dice rolling, crit detection, and explosion (炸膛) mechanics.
"""

import random
from typing import List, Tuple, Optional
from enum import IntEnum


class DiceResult(IntEnum):
    NORMAL = 0
    CRITICAL_FAIL = 1
    CRITICAL_SUCCESS = 2


class ExplosionType(IntEnum):
    NONE = 0
    FAIL_FAIL = 1      # 大失败+大失败 → 炸膛
    FAIL_SUCCESS = 2    # 大失败+大成功 → 炸膛
    SUCCESS_FAIL = 3    # 大成功+大失败 → 炸膛
    SUCCESS_SUCCESS = 4 # 大成功+大成功 → 炸膛


# All combos result in explosion per user spec:
# 大失败+大失败，大失败+大成功，大成功+大失败，大成功+大成功
EXPLOSION_COMBOS = {
    ("fail", "fail"),
    ("fail", "success"),
    ("success", "fail"),
    ("success", "success"),
}


def roll_3d6() -> Tuple[List[int], int]:
    """Roll 3 six-sided dice. Returns (dice_list, total)."""
    dice = [random.randint(1, 6) for _ in range(3)]
    return dice, sum(dice)


def interpret_3d6(dice: List[int], total: int) -> Tuple[DiceResult, str]:
    """
    Interpret 3d6 result.
    Returns (DiceResult, label_string).

    Rules (Per user spec):
    - total == 3  → 大失败 (固定值)
    - total == 18 → 大成功 (固定值)
    - total 4-7   → 失败 (旋转弹巢)
    - total 8-15  → 普通成功 (开枪)
    - total 16-17 → 普通成功 (开枪)
    """
    d = dice
    # 固定值判定
    if total == 3:
        return DiceResult.CRITICAL_FAIL, "critical_fail"
    if total == 18:
        return DiceResult.CRITICAL_SUCCESS, "critical_success"
    # 普通失败
    if total <= 7:
        return DiceResult.NORMAL, "fail"
    # 普通成功
    return DiceResult.NORMAL, "success"


def check_explosion(prev_label: Optional[str], curr_label: str) -> bool:
    """
    Check if two consecutive rolls trigger explosion (炸膛).
    Per user spec: ANY two consecutive crits (fail or success) → explosion.
    """
    if prev_label is None:
        return False
    combo = (prev_label, curr_label)
    return combo in EXPLOSION_COMBOS


def format_dice(dice: List[int], label: str) -> str:
    """Format dice roll for display."""
    return f"[{dice[0]} {dice[1]} {dice[2]}] = {sum(dice)}  → {label}"


class DiceManager:
    """
    Manages the two-stage dice rolling for the game.
    
    Stage 1 (Roll 1): 决定行动
        - 3 = 大失败 (炸膛自爆)
        - 4-7 = 失败 (旋转弹巢，结束回合)
        - 8-17 = 普通成功 (开枪)
        - 18 = 大成功 (精准射击 - 下一发必中实弹且不消耗)
    
    Stage 2 (Roll 2): 决定射击目标
        - 3-10 = 朝自己开枪
        - 11-18 = 朝对手开枪
    """

    def __init__(self):
        self.roll_1: List[int] = []
        self.roll_1_total: int = 0
        self.roll_1_result: DiceResult = DiceResult.NORMAL
        self.roll_1_label: str = ""
        self.roll_2: List[int] = []
        self.roll_2_total: int = 0
        self.roll_2_result: DiceResult = DiceResult.NORMAL
        self.roll_2_label: str = ""
        self.explosion: bool = False
        self.explosion_type: str = ""
        # 精准射击状态 - 大成功后触发
        self.precise_shot: bool = False

    def reset(self):
        self.roll_1 = []
        self.roll_1_label = ""
        self.roll_2 = []
        self.roll_2_label = ""
        self.explosion = False
        self.explosion_type = ""
        self.precise_shot = False

    def do_roll_1(self) -> Tuple[DiceResult, str, List[int]]:
        """第一颗骰子 - 决定行动：开枪/旋转弹巢/炸膛"""
        self.roll_1, self.roll_1_total = roll_3d6()
        self.roll_1_result, self.roll_1_label = interpret_3d6(self.roll_1, self.roll_1_total)
        
        # 大成功时标记精准射击状态
        if self.roll_1_label == "critical_success":
            self.precise_shot = True
        
        # 大失败时触发炸膛
        if self.roll_1_label == "critical_fail":
            self.explosion = True
            self.explosion_type = "self_explosion"
        
        return self.roll_1_result, self.roll_1_label, self.roll_1

    def do_roll_2(self) -> Tuple[DiceResult, str, List[int], bool]:
        """第二颗骰子 - 决定射击目标"""
        self.roll_2, self.roll_2_total = roll_3d6()
        self.roll_2_result, self.roll_2_label = interpret_3d6(self.roll_2, self.roll_2_total)
        
        return self.roll_2_result, self.roll_2_label, self.roll_2, False

    def get_action_from_roll_1(self) -> str:
        """
        根据第一颗骰子决定行动。
        Returns: "shoot" / "spin" / "explode"
        """
        if self.roll_1_label == "critical_fail":
            return "explode"
        if self.roll_1_label == "fail":
            return "spin"
        return "shoot"  # success or critical_success

    def get_target_from_roll_2(self) -> str:
        """
        根据第二颗骰子决定射击目标。
        - 3-10 (总和3-10) → 朝自己开枪
        - 11-18 (总和11-18) → 朝对手开枪
        """
        if self.roll_2_total <= 10:
            return "self"
        return "opponent"

    def is_precise_shot(self) -> bool:
        """检查是否是精准射击（大成功后）"""
        return self.precise_shot
