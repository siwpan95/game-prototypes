"""d20.dice - 骰子系统（纯函数 + DiceService）

融合 D&D 的 d20/d100/d6 与 GURPS 的 3d6 roll-low 检定。
纯函数可直接 import 使用、便于测试；DiceService 挂到 ``ctx.dice`` 提供实例方法。

2026-08-27（R2 反向增强）：纯函数新增可选 ``rng`` 参数（默认全局 random，行为不变；
模拟器/测试可注入独立随机源获得确定性），并新增通用 NdS 伤害骰 ``roll_dice``
（moba_battle_platform 等 D&D 5e 消费方的同构原语）。
"""
import random
from typing import Any

from .context import Service
from .data import WEAPON_DICE


# -----------------------------------------------------------------------------
#  纯函数（可直接 import 使用，便于测试）
# -----------------------------------------------------------------------------
def roll_d20(rng: Any = random) -> int:
    """掷一颗 20 面骰。rng 可注入（默认全局 random）。"""
    return rng.randint(1, 20)


def roll_d100(rng: Any = random) -> int:
    """掷一颗百分骰。rng 可注入（默认全局 random）。"""
    return rng.randint(1, 100)


def roll_d6(num: int, mod: int = 0, rng: Any = random) -> tuple[list[int], int]:
    """掷 num 颗 6 面骰 + 修正，返回 (各骰结果, 总和)。rng 可注入。"""
    rolls = [rng.randint(1, 6) for _ in range(num)]
    return rolls, sum(rolls) + mod


def roll_3d6(rng: Any = random) -> tuple[list[int], int]:
    """掷 3d6（GURPS 主检定骰），返回 (各骰结果, 总和)。rng 可注入。"""
    rolls = [rng.randint(1, 6) for _ in range(3)]
    return rolls, sum(rolls)


def roll_dice(count: int, size: int, rng: Any = random) -> int:
    """掷 count 颗 size 面骰（D&D 伤害骰），返回总和。

    count<=0 返回 0；size<=0 收敛为 1。rng 可注入（模拟器确定性）。
    与 moba_battle_platform 原 roll_dice 语义一致（R2 内核化）。
    """
    count = max(0, int(count))
    size = max(1, int(size))
    return sum(rng.randint(1, size) for _ in range(count))


def gurps_success_chance(skill_level: int) -> int:
    """GURPS 3d6 roll-low 的成功率近似（百分比）。"""
    table = {3: 0.5, 4: 2, 5: 5, 6: 9, 7: 16, 8: 26, 9: 38, 10: 50,
             11: 63, 12: 74, 13: 84, 14: 90, 15: 95, 16: 98, 17: 98, 18: 100}
    if skill_level <= 3:
        return 0
    if skill_level >= 18:
        return 100
    return int(table.get(skill_level, 50))


def roll_weapon_damage(weapon_name: str, rng: Any = random) -> tuple[list[int], str]:
    """掷武器伤害骰，返回 (各骰结果, 骰子描述如 '1d8')。rng 可注入。"""
    num, die = WEAPON_DICE.get(weapon_name, (1, 4))
    rolls = [rng.randint(1, die) for _ in range(num)]
    return rolls, f"{num}d{die}"


# -----------------------------------------------------------------------------
#  DiceService（供 Character 组合，保留老 API）
# -----------------------------------------------------------------------------
class DiceService(Service):
    """骰子相关能力。"""

    inject = ["skills", "feats"]

    def d20_roll(self) -> int:
        """掷 d20 并应用钩子：半身人幸运（掷 1 重掷）、专长幸运（每日 3 次重掷取高）。"""
        roll = self.ctx.waterfall("dice/d20_roll", roll_d20())
        st = self.ctx.state
        if self.ctx.feats.has_feat("幸运") and st.lucky_used < 3:
            roll = max(roll, roll_d20())
            st.lucky_used += 1
        return roll

    def d20_check(self, skill_name: str, dc: int) -> str:
        """D&D 风格 d20 检定：d20 + 技能有效等级 vs DC。"""
        rank = self.ctx.skills.effective_skill_rank(skill_name)
        is_default = self.ctx.state.skills.get(skill_name, 0) == 0
        roll = self.d20_roll()
        result = roll + rank
        success = result >= dc
        default_tag = " [默认值]" if is_default else ""
        return f"d20+{rank}{default_tag} = {roll}+{rank} = {result} vs DC {dc} {'成功' if success else '失败'}"

    def d100_check(self, skill_name: str) -> str:
        """d100 技能成功率检定（CoC 风格）：成功率 = 技能等级×5%。"""
        rank = self.ctx.skills.effective_skill_rank(skill_name)
        is_default = self.ctx.state.skills.get(skill_name, 0) == 0
        target = rank * 5
        roll = roll_d100()
        success = roll <= target
        default_tag = " [默认值]" if is_default else ""
        return f"成功率 {target}%{default_tag}，掷出 {roll} {'成功' if success else '失败'}"

    def gurps_check(self, skill_name: str, modifier: int = 0) -> str:
        """GURPS 风格 3d6 roll-low 检定：≤ 技能等级+修正 即成功。"""
        rank = self.ctx.skills.effective_skill_rank(skill_name)
        target = rank + modifier
        rolls, total = roll_3d6()
        if total <= 4 or (total == 5 and target >= 15) or (total == 6 and target >= 16):
            outcome = "大成功！"
        elif total >= 17 or (total == 17 and target <= 15):
            outcome = "大失败！" if total == 18 or (total == 17 and target <= 15) else "失败"
        else:
            outcome = "成功" if total <= target else "失败"
        mod_str = f"{'+' if modifier >= 0 else ''}{modifier}" if modifier else "0"
        return f"3d6({rolls}={total}) vs {rank}[{mod_str}]={target} → {outcome}"

    def roll_d6(self, num_dice: int, mod: int = 0) -> str:
        """掷伤害骰，返回可读字符串（保留老 API）。"""
        rolls, total = roll_d6(num_dice, mod)
        return f"{num_dice}d6+{mod} = {rolls} = {total}"

    def _roll_weapon_damage(self, weapon_name: str) -> tuple[list[int], str]:
        """掷武器伤害骰（实例方法，保留老 API）。"""
        return roll_weapon_damage(weapon_name)
