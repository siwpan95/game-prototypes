"""
ECS Components for Russian Roulette game.
Pure data containers — no logic here.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional
import enum
from ecs import Component


# ── Enums ─────────────────────────────────────────────────────────────

class BulletType(enum.IntEnum):
    BLANK = 0      # 空包弹 - 无害但有特殊效果
    LIVE = 1       # 实弹 - 致命
    RUBBER = 2     # 橡胶弹 - 不致命，造成眩晕效果
    INCENDIARY = 3 # 燃烧弹 - 造成火焰伤害标记


class DiceResult(enum.IntEnum):
    NORMAL = 0      # 普通成功/失败
    CRITICAL_FAIL = 1   # 大失败 (3个1 或 3个6且总和≤6 等规则可自定义)
    CRITICAL_SUCCESS = 2 # 大成功


class TurnPhase(enum.IntEnum):
    PLAYER_TURN_START = 0
    ROLL_1 = 1          # 丢第一颗骰子
    ROLL_2 = 2          # 丢第二颗骰子
    SHOOT = 3           # 开枪阶段
    OPPONENT_TURN = 4
    GAME_OVER = 5


class ShotTarget(enum.IntEnum):
    SELF = 0
    OPPONENT = 1


# ── Components ─────────────────────────────────────────────────────────

@dataclass
class ChamberComponent(Component):
    """Left side: chamber (弹巢). Stores bullets."""
    max_slots: int = 6
    bullets: List[int] = field(default_factory=list)  # list of BulletType values

    def fill_random(self, live_count: Optional[int] = None):
        """Fill chamber randomly with various bullet types."""
        import random
        if live_count is None:
            # Random ratio: at least 1, at most max_slots-1
            live_count = random.randint(1, self.max_slots - 1)
        
        # 子弹分配：实弹、空包弹、橡胶弹、燃烧弹
        special_count = random.randint(0, 1)  # 0-1个特殊子弹
        bullet_pool = [BulletType.LIVE] * live_count + \
                      [BulletType.BLANK] * max(1, (self.max_slots - live_count - special_count) // 2) + \
                      [BulletType.RUBBER] * max(0, special_count // 2) + \
                      [BulletType.INCENDIARY] * max(0, special_count - special_count // 2)
        self.bullets = bullet_pool + [BulletType.BLANK] * (self.max_slots - len(bullet_pool))
        random.shuffle(self.bullets)

    def shoot(self) -> int:
        """
        Shoot one bullet from chamber (pop from front).
        Returns BulletType or raises if empty.
        """
        if not self.bullets:
            return BulletType.BLANK  # should not happen if refill works
        return self.bullets.pop(0)

    def refill_one(self):
        """After shooting, add one random bullet to keep chamber full."""
        import random
        if len(self.bullets) < self.max_slots:
            # 按概率补充子弹
            choices = [BulletType.BLANK, BulletType.BLANK, BulletType.LIVE, 
                      BulletType.RUBBER, BulletType.INCENDIARY]
            self.bullets.append(random.choice(choices))
            random.shuffle(self.bullets)

    def spin(self):
        """Randomize bullet order (spin the chamber)."""
        import random
        random.shuffle(self.bullets)

    @property
    def is_empty(self) -> bool:
        return len(self.bullets) == 0

    @property
    def live_count(self) -> int:
        return sum(1 for b in self.bullets if b == BulletType.LIVE)

    @property
    def blank_count(self) -> int:
        return sum(1 for b in self.bullets if b == BulletType.BLANK)


@dataclass
class HealthComponent(Component):
    """Entity health. 0 = dead."""
    hp: int = 3  # 俄罗斯轮盘赌：3点生命值


@dataclass
class TurnComponent(Component):
    """Tracks whose turn it is and the current phase."""
    current_turn_entity: Optional[Entity] = None
    phase: TurnPhase = TurnPhase.PLAYER_TURN_START
    turn_number: int = 0


@dataclass
class DiceComponent(Component):
    """Tracks dice roll results."""
    # Last roll results (3d6)
    roll_1_results: List[int] = field(default_factory=list)  # 3 dice for first roll
    roll_2_results: List[int] = field(default_factory=list)  # 3 dice for second roll
    roll_1_total: int = 0
    roll_2_total: int = 0
    roll_1_result: DiceResult = DiceResult.NORMAL
    roll_2_result: DiceResult = DiceResult.NORMAL
    # Critical combo tracking (for explosion)
    last_crit_type: Optional[str] = None  # "fail_fail", "fail_success", "success_fail", "success_success"
    explosion_pending: bool = False


@dataclass
class ShotComponent(Component):
    """Data about the current/last shot."""
    target: ShotTarget = ShotTarget.SELF
    bullet_type: int = BulletType.BLANK
    was_shot: bool = False
    hit_live: bool = False  # True if live round hit someone
    # 特殊状态效果
    stunned: bool = False    # 眩晕状态（橡胶弹造成）
    burning: bool = False    # 燃烧状态（燃烧弹造成）


@dataclass
class AsciiArtComponent(Component):
    """Stores ASCII / kaomoji art for an entity."""
    body_art: str = ""
    face_normal: str = ""
    face_hit: str = ""
    face_dead: str = ""
    current_face: str = ""


@dataclass
class AchievementComponent(Component):
    """Tracks achievements for an entity."""
    unlocked: List[str] = field(default_factory=list)
    stats: dict = field(default_factory=lambda: {
        "shots_fired": 0,
        "live_shots_survived": 0,
        "blank_shots": 0,
        "spins": 0,
        "critical_fails": 0,
        "critical_successes": 0,
        "wins": 0,
        "losses": 0,
        "shots_at_opponent": 0,
        "shots_at_self": 0,
        "consecutive_blanks": 0,
        "max_consecutive_blanks": 0,
    })


@dataclass
class RenderComponent(Component):
    """Position and rendering info for pygame."""
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0
    visible: bool = True
    dirty: bool = True  # needs re-render


@dataclass
class AnimationComponent(Component):
    """Tracks active animations (e.g. '砰' flash)."""
    active: bool = False
    anim_type: str = ""   # "bang", "explosion", "hit"
    timer: float = 0.0    # seconds remaining
    duration: float = 0.0
