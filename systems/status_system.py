"""Status effect system — processes TEW-inspired status effects each turn.

支持的状态效果 (来自 TEW 最终物语体系):
  - stun (眩晕):       跳过该实体的下一次行动
  - slow (迟缓):       攻击力临时降低 value 点
  - weaken (虚弱):     造成的伤害减少 value 点
  - freeze (冰冻):     跳过攻击且 value 回合无法行动
  - shaken (动摇):     受到额外 value 点伤害
  - burn (燃烧):       每回合受到 value 点火焰伤害
  - poison (中毒):     每回合受到 value 点伤害（无视护盾）
  - shield_up (护盾增强): 回合结束时获得 value 点护盾
"""

from __future__ import annotations
from ecs import System, World
from components import (
    StatusEffectComponent, HealthComponent, AttackComponent,
    EnemyComponent, MinionComponent, PlayerComponent,
    FloatingTextComponent,
)
from constants import (
    FLOAT_DAMAGE, FLOAT_HEAL, FLOAT_SHIELD, STATUS_COLORS,
    ELEMENT_COLORS,
)
from debug_probes import probe


class StatusSystem(System):
    """每回合结束时处理所有实体的状态效果。"""

    def __init__(self, game_state) -> None:
        self.gs = game_state

    def update(self, world: World, dt: float, events: list | None = None) -> None:
        pass  # 被动触发式，不逐帧执行

    # ── 回合结束时调用 ──────────────────────────────────────────────

    def process_turn_end(self, world: World, owner: str = "enemy") -> None:
        """处理指定阵营 (player/enemy/all) 的状态效果回合结算。

        在玩家回合结束或敌人回合结束时调用。
        """
        entities = list(world.get_entities_with(StatusEffectComponent, HealthComponent))
        for e in entities:
            h = world.get_component(e, HealthComponent)
            if not h or not h.alive:
                continue

            # 按阵营过滤
            is_player = world.get_component(e, PlayerComponent) is not None
            if owner == "player" and not is_player:
                continue
            if owner == "enemy" and is_player:
                continue

            status = world.get_component(e, StatusEffectComponent)
            if not status or not status.effects:
                continue

            self._process_entity(world, e, status, h)

    def _process_entity(self, world: World, entity, status: StatusEffectComponent,
                        health: HealthComponent) -> None:
        """处理单个实体的所有状态效果。"""
        effects_to_remove: list[int] = []  # 按索引标记待移除

        for i, ef in enumerate(status.effects):
            etype = ef["type"]
            value = ef["value"]

            if etype == "burn":
                # 燃烧：每回合受到火焰伤害
                health.take_damage(value)
                self._spawn_float(world, entity, f"-{value} 燃烧🔥", ELEMENT_COLORS.get("fire", (255,80,30)))
                self._check_death_mark(world, entity, health)

            elif etype == "poison":
                # 中毒：无视护盾直接扣血
                health.hp -= value
                self._spawn_float(world, entity, f"-{value} 中毒☠", STATUS_COLORS.get("poison", (80,200,100)))
                self._check_death_mark(world, entity, health)

            elif etype == "shield_up":
                # 护盾增强：回合结束时获得护盾
                health.shield += value
                self._spawn_float(world, entity, f"+{value} 护盾", FLOAT_SHIELD)

            # 扣减回合数
            ef["turns"] -= 1
            if ef["turns"] <= 0:
                effects_to_remove.append(i)

        # 移除过期效果（倒序遍历避免索引错位）
        for i in reversed(effects_to_remove):
            removed = status.effects.pop(i)
            # 冰冻结束时提示
            if removed["type"] == "freeze":
                self._spawn_float(world, entity, "解冻！", STATUS_COLORS.get("freeze", (140,220,255)))

    # ── 攻击前/后拦截 ──────────────────────────────────────────────

    def on_pre_attack(self, world: World, entity) -> int:
        """攻击前检查：眩晕/冰冻跳过攻击，返回应减少的伤害量（若跳过则返回 -1）。"""
        status = world.get_component(entity, StatusEffectComponent)
        if not status:
            return 0

        if status.has("stun"):
            self._spawn_float(world, entity, "眩晕!", STATUS_COLORS["stun"])
            return -1  # 信号：完全跳过此次攻击

        if status.has("freeze"):
            self._spawn_float(world, entity, "冰冻!", STATUS_COLORS["freeze"])
            return -1  # 信号：完全跳过

        return 0

    def on_damage_modify(self, world: World, entity, base_damage: int) -> int:
        """修改最终伤害值（虚弱/迟缓/动摇）。"""
        status = world.get_component(entity, StatusEffectComponent)
        if not status:
            return base_damage

        dmg = base_damage

        # 虚弱：造成的伤害减少
        if status.has("weaken"):
            weaken_val = status.get_value("weaken")
            dmg = max(0, dmg - weaken_val)

        # 迟缓：攻击力降低（通过 AttackComponent 处理，此处仅记录）
        atk = world.get_component(entity, AttackComponent)
        slow_val = status.get_value("slow")
        if slow_val > 0 and hasattr(atk, "attack"):
            dmg = max(0, dmg - slow_val)

        return dmg

    def on_receive_damage_modify(self, world: World, entity, base_damage: int) -> int:
        """修改受到的伤害（动摇：受到额外伤害）。"""
        status = world.get_component(entity, StatusEffectComponent)
        if not status:
            return base_damage

        if status.has("shaken"):
            shaken_val = status.get_value("shaken")
            return base_damage + shaken_val

        return base_damage

    # ── 施加状态效果 ──────────────────────────────────────────────

    def apply_status(self, world: World, target_entity, effect_type: str,
                     turns: int = 1, value: int = 0) -> None:
        """向目标实体施加状态效果。"""
        if target_entity is None:
            return

        probe("status::apply", f"施加状态: {effect_type}",
              {"turns": turns, "value": value}, module="status")

        status = world.get_component(target_entity, StatusEffectComponent)
        if status is None:
            status = StatusEffectComponent()
            world.add_component(target_entity, status)

        status.add(effect_type, turns, value)

        # 视觉反馈
        names = {
            "stun": "眩晕", "slow": "迟缓", "weaken": "虚弱",
            "freeze": "冰冻", "shaken": "动摇", "burn": "燃烧",
            "poison": "中毒", "shield_up": "护盾+",
        }
        label = names.get(effect_type, effect_type)
        color = STATUS_COLORS.get(effect_type, (255,255,255))
        self._spawn_float(world, target_entity, label, color)

    # ── Helpers ─────────────────────────────────────────────────────

    def _spawn_float(self, world: World, entity, text: str, color: tuple) -> None:
        x, y = 640, 360
        from components import PositionComponent
        if entity:
            pos = world.get_component(entity, PositionComponent)
            if pos:
                x, y = pos.x, pos.y
        ft = FloatingTextComponent(text, x, y, color)
        e = world.create_entity()
        world.add_component(e, ft)

    def _check_death_mark(self, world: World, entity, health: HealthComponent) -> None:
        """检查实体是否死亡（仅标记，实际销毁由 combat_system 处理）。"""
        if health.hp <= 0:
            health.hp = 0
