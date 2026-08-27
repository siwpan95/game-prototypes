"""
ECS Systems for Russian Roulette game.
Each system processes entities that have specific component combinations.
"""

from __future__ import annotations
import random
import enum

from ecs import World, System
from components import (
    ChamberComponent, HealthComponent, TurnComponent, DiceComponent,
    ShotComponent, AchievementComponent, AnimationComponent,
    BulletType, DiceResult, TurnPhase, ShotTarget
)


# ── Dice System ────────────────────────────────────────────────────────

class DiceSystem(System):
    """
    Handles 3D6 rolls and interprets results.
    3D6 mechanism:
    - Roll 1: success → roll 2;  fail → spin chamber (end turn)
    - Roll 2: success → shoot opponent; fail → shoot self
    Critical: 3 Sixes = CRITICAL SUCCESS, 3 Ones = CRITICAL FAIL
    """

    def update(self, world: World, dt: float = 0.0, **kwargs):
        pass  # Dice rolls are triggered by events, not auto-update

    @staticmethod
    def roll_3d6() -> tuple[list[int], int]:
        """Return (dice_list, total)."""
        dice = [random.randint(1, 6) for _ in range(3)]
        return dice, sum(dice)

    @staticmethod
    def interpret_3d6(dice: list[int], total: int) -> DiceResult:
        """
        Interpret 3d6 result:
        - 3 Ones (1,1,1) → CRITICAL FAIL
        - 3 Sixes (6,6,6) → CRITICAL SUCCESS
        - total ≥ 14 → success; total ≤ 7 → fail; else normal
        More nuanced: we use threshold + crits
        """
        if dice[0] == dice[1] == dice[2] == 1:
            return DiceResult.CRITICAL_FAIL
        if dice[0] == dice[1] == dice[2] == 6:
            return DiceResult.CRITICAL_SUCCESS

        # Normal: 3d6 mean = 10.5; success ≥ 14 (top ~10%), fail ≤ 7 (bottom ~10%)
        if total >= 14:
            return DiceResult.CRITICAL_SUCCESS  # "strong success"
        elif total <= 7:
            return DiceResult.CRITICAL_FAIL     # "strong fail"
        return DiceResult.NORMAL

    def do_roll_1(self, world: World, entity: object) -> DiceResult:
        """First dice roll: success → roll 2; fail → spin."""
        dc = world.get_component(entity, DiceComponent)
        chamber = world.get_component(entity, ChamberComponent)
        assert dc is not None

        dice, total = self.roll_3d6()
        dc.roll_1_results = dice
        dc.roll_1_total = total
        dc.roll_1_result = self.interpret_3d6(dice, total)

        # Track crits for explosion
        self._update_crit_tracking(dc, dc.roll_1_result, first=True)

        if dc.roll_1_result in (DiceResult.CRITICAL_FAIL, DiceResult.NORMAL):
            # fail or weak success → spin chamber (and end turn)
            if chamber:
                chamber.spin()
            # Mark that we spinned
            dc._spin_this_turn = True

        return dc.roll_1_result

    def do_roll_2(self, world: World, entity: object) -> DiceResult:
        """Second dice roll (only if roll 1 succeeded). Determines target."""
        dc = world.get_component(entity, DiceComponent)
        assert dc is not None

        dice, total = self.roll_3d6()
        dc.roll_2_results = dice
        dc.roll_2_total = total
        dc.roll_2_result = self.interpret_3d6(dice, total)

        self._update_crit_tracking(dc, dc.roll_2_result, first=False)

        # Determine target
        if dc.roll_2_result == DiceResult.CRITICAL_FAIL:
            dc._target = ShotTarget.SELF
        elif dc.roll_2_result == DiceResult.CRITICAL_SUCCESS:
            dc._target = ShotTarget.OPPONENT
        else:
            # Normal: decide by threshold (total >= 11 → opponent, else self)
            dc._target = ShotTarget.OPPONENT if total >= 11 else ShotTarget.SELF

        return dc.roll_2_result

    def _update_crit_tracking(self, dc: DiceComponent, result: DiceResult, first: bool):
        """Track consecutive crit results for explosion mechanic."""
        key = "success" if result == DiceResult.CRITICAL_SUCCESS else \
              "fail" if result == DiceResult.CRITICAL_FAIL else "normal"

        if first:
            dc.last_crit_type = key
        else:
            # Check combo: both rolls were crits
            if dc.last_crit_type in ("fail", "success") and key in ("fail", "success"):
                dc.explosion_pending = True
                dc.last_crit_combo = f"{dc.last_crit_type}_{key}"
            dc.last_crit_type = key

    def get_target(self, world: World, entity: object) -> ShotTarget:
        dc = world.get_component(entity, DiceComponent)
        if dc and hasattr(dc, '_target'):
            return dc._target
        return ShotTarget.SELF  # default: shoot self


# ── Shooting System ────────────────────────────────────────────────────

class ShootingSystem(System):
    """
    Handles shooting: fire a bullet, apply damage if live.
    After shooting, refill chamber to keep it full.
    """
    def update(self, world: World, dt: float = 0.0, **kwargs):
        pass  # Shooting is event-driven

    def shoot(self, world: World, shooter: object, target: object) -> dict:
        """
        Execute a shot from shooter targeting target.
        Returns result dict.
        """
        chamber = world.get_component(shooter, ChamberComponent)
        shot_comp = world.get_component(shooter, ShotComponent)
        target_health = world.get_component(target, HealthComponent)
        shooter_health = world.get_component(shooter, HealthComponent)
        anim_comp = world.get_component(shooter, AnimationComponent)

        if chamber is None or not chamber.bullets:
            return {"error": "No bullets!"}

        # Fire bullet
        bullet = chamber.shoot()
        shot_comp.bullet_type = bullet
        shot_comp.was_shot = True

        result = {
            "bullet_type": "live" if bullet == BulletType.LIVE else "blank",
            "target_hit": target,
            "target_died": False,
            "shooter_died": False,
        }

        # Trigger "砰" animation
        if anim_comp:
            anim_comp.active = True
            anim_comp.anim_type = "bang"
            anim_comp.timer = 1.0   # 1 second
            anim_comp.duration = 1.0

        if bullet == BulletType.LIVE:
            # Live round: damage target
            if target_health:
                target_health.hp -= 1
                if target_health.hp <= 0:
                    result["target_died"] = True
            shot_comp.hit_live = True
        else:
            # Blank: no damage, but trigger blank animation
            shot_comp.hit_live = False
            if anim_comp:
                anim_comp.anim_type = "bang_blank"

        # Refill one bullet to keep chamber full
        chamber.refill_one()

        # Update achievement stats
        self._update_stats(world, shooter, bullet, target, result)

        return result

    def _update_stats(self, world, shooter, bullet, target, result):
        ach = world.get_component(shooter, AchievementComponent)
        if ach is None:
            return
        ach.stats["shots_fired"] += 1
        if bullet == BulletType.BLANK:
            ach.stats["blank_shots"] += 1
            ach.stats["consecutive_blanks"] += 1
            ach.stats["max_consecutive_blanks"] = max(
                ach.stats["max_consecutive_blanks"],
                ach.stats["consecutive_blanks"]
            )
        else:
            ach.stats["consecutive_blanks"] = 0

        # Determine if shooting at opponent or self
        turn = world.get_component(shooter, TurnComponent)
        # Simple heuristic: if target is not shooter, it's opponent
        if target != shooter:
            ach.stats["shots_at_opponent"] += 1
        else:
            ach.stats["shots_at_self"] += 1


# ── Turn System ────────────────────────────────────────────────────────

class TurnSystem(System):
    """
    Manages turn flow:
    Phase 1: Roll 1 → success → Phase 2; fail → spin → end turn
    Phase 2: Roll 2 → determine target → shoot → end turn
    """
    def update(self, world: World, dt: float = 0.0, **kwargs):
        pass

    def start_turn(self, world: World, entity: object):
        turn = world.get_component(entity, TurnComponent)
        if turn:
            turn.phase = TurnPhase.ROLL_1
            turn.turn_number += 1

    def end_turn(self, world: World, current: object, next_entity: object):
        """Switch turn to next entity."""
        turn = world.get_component(current, TurnComponent)
        if turn:
            turn.phase = TurnPhase.PLAYER_TURN_START
        # Set next entity's turn
        next_turn = world.get_component(next_entity, TurnComponent)
        if next_turn:
            next_turn.current_turn_entity = next_entity
            self.start_turn(world, next_entity)

    def check_death(self, world: World) -> object | None:
        """Return dead entity if any, else None."""
        for entity in world.get_entities_with(HealthComponent):
            hc = world.get_component(entity, HealthComponent)
            if hc and hc.hp <= 0:
                return entity
        return None


# ── Animation System ───────────────────────────────────────────────────

class AnimationSystem(System):
    """Updates animation timers each frame."""
    def update(self, world: World, dt: float = 0.0, **kwargs):
        for entity in world.get_entities_with(AnimationComponent):
            ac = world.get_component(entity, AnimationComponent)
            if ac and ac.active:
                ac.timer -= dt
                if ac.timer <= 0:
                    ac.active = False
                    ac.anim_type = ""


# ── Achievement System (ECS version) ──────────────────────────────────

class AchievementSystem(System):
    """
    Checks and unlocks achievements based on entity stats.
    Call manually after events, or auto-check each frame.
    """
    ALL_ACHIEVEMENTS = {
        "first_shot": {
            "name": "初次开火",
            "desc": "发射第一发子弹",
        },
        "survive_live": {
            "name": "死里逃生",
            "desc": "在实弹中幸存（实弹打中自己但没死？不可能...调整规则）",
            # Actually in roulette you die on live, so this is for opponent dying
        },
        "opponent_down": {
            "name": "终结者",
            "desc": "击杀对手",
        },
        "spinner": {
            "name": "旋转大师",
            "desc": "单局旋转弹巢3次",
        },
        "blank_5": {
            "name": "哑弹之王",
            "desc": "连续打出5发空包弹",
        },
        "critical_fail": {
            "name": "倒霉蛋",
            "desc": "连续2次大失败（炸膛）",
        },
        "critical_success": {
            "name": "天选之子",
            "desc": "连续2次大成功（炸膛）",
        },
        "explosion_survivor": {
            "name": "炸膛幸存者",
            "desc": "触发炸膛但幸存（对手炸膛而死）",
        },
        "speed_run": {
            "name": "闪电战",
            "desc": "3回合内获胜",
        },
    }

    def update(self, world: World, dt: float = 0.0, **kwargs):
        """Auto-check achievements each frame."""
        for entity in world.get_entities_with(AchievementComponent):
            self.check_achievements(world, entity)

    def check_achievements(self, world: World, entity: object):
        ach = world.get_component(entity, AchievementComponent)
        if ach is None:
            return

        s = ach.stats
        u = ach.unlocked

        # First shot
        if s["shots_fired"] >= 1 and "first_shot" not in u:
            self._unlock(ach, "first_shot")

        # Opponent down
        if s["wins"] >= 1 and "opponent_down" not in u:
            self._unlock(ach, "opponent_down")

        # Spinner (tracked outside: need to count spins per game)
        # blank_5
        if s["max_consecutive_blanks"] >= 5 and "blank_5" not in u:
            self._unlock(ach, "blank_5")

        # Speed run (checked externally with turn count)
        # critical fail/success tracked via explosion check

    def _unlock(self, ach: AchievementComponent, key: str):
        if key not in ach.unlocked:
            ach.unlocked.append(key)
            ach.stats["_just_unlocked"] = key  # signal for UI

    def get_just_unlocked(self, ach: AchievementComponent) -> str | None:
        return ach.stats.pop("_just_unlocked", None)

    def check_spin_count(self, ach: AchievementComponent, spins_this_game: int):
        if spins_this_game >= 3 and "spinner" not in ach.unlocked:
            self._unlock(ach, "spinner")

    def check_turn_win(self, ach: AchievementComponent, turn_number: int):
        if turn_number <= 3 and "speed_run" not in ach.unlocked:
            self._unlock(ach, "speed_run")
