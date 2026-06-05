"""Combat system — handles all damage, healing, and combat resolution."""

from __future__ import annotations
from ecs import System, World
from components import (
    HealthComponent, AttackComponent, CardComponent,
    MinionComponent, EnemyComponent, RenderComponent,
    FloatingTextComponent, WaveComponent,
    EnergyComponent, PlayerComponent, BoardComponent,
    KeywordComponent, HandComponent, PositionComponent,
)
from game_state import GameState, Phase
from constants import (
    FLOAT_DAMAGE, FLOAT_HEAL, FLOAT_SHIELD,
    FLASH_DURATION, FLOAT_TEXT_SPEED, MINION_BG,
    ELEMENT_COLORS, ELEMENT_NAMES,
)
from audio.audio_components import AudioEventComponent, AudioEventType
from systems.status_system import StatusSystem
import random
from debug_probes import probe


class CombatSystem(System):
    """Processes combat: attacks, damage, healing, death."""

    def __init__(self, game_state: GameState) -> None:
        self.gs = game_state

    def update(self, world: World, dt: float, events: list | None = None) -> None:
        pass  # Combat is event-driven, not per-frame

    # ── Card Play Resolution ─────────────────────────────────────────────

    def resolve_card(self, world: World, card_entity, target_entity=None) -> None:
        """Execute a played card's effect."""
        card = world.get_component(card_entity, CardComponent)
        if card is None:
            return

        probe("combat::resolve_card", f"出牌: {card.name}",
              {"type": card.card_type, "cost": card.cost, "dmg": card.damage,
               "element": card.element}, module="combat")

        player_health = self._get_player_health(world)
        player_atk = self._get_player_attack(world)

        if card.card_type == "attack":
            self._resolve_attack_card(world, card, target_entity)
        elif card.card_type == "skill":
            self._resolve_skill_card(world, card, target_entity, player_health)
        elif card.card_type == "minion":
            self._resolve_minion_card(world, card_entity, card)

        # Track card play
        player_comp = self._get_player_component(world)
        if player_comp:
            player_comp.cards_played += 1

    # ── Attack Card ─────────────────────────────────────────────────────

    def _resolve_attack_card(self, world: World, card: CardComponent, target) -> None:
        damage = card.damage or 0

        # Lifesteal (only for single-target)
        lifesteal = "Lifesteal" in (card.keywords or [])

        # 元素伤害颜色
        elem_color = FLOAT_DAMAGE
        if card.element and card.element != "none":
            elem_color = ELEMENT_COLORS.get(card.element, FLOAT_DAMAGE)

        # ── AOE attack cards (target="none") ──
        if target == "none" and damage > 0:
            enemy_entities = world.get_entities_with(EnemyComponent, HealthComponent)
            for target_ent in enemy_entities:
                target_health = world.get_component(target_ent, HealthComponent)
                if target_health and target_health.alive:
                    actual_dmg = target_health.take_damage(damage)
                    if card.element and card.element != "none":
                        elem_name = ELEMENT_NAMES.get(card.element, "")
                        self._spawn_float(world, target_ent, f"-{actual_dmg} {elem_name}", elem_color)
                    else:
                        self._spawn_float(world, target_ent, f"-{actual_dmg}", FLOAT_DAMAGE)
                    self._flash_entity(world, target_ent)
                    # 触发敌人受伤音效
                    for ent in world.get_entities_with(AudioEventComponent):
                        ae = world.get_component(ent, AudioEventComponent)
                        if ae:
                            ae.add(AudioEventType.COMBAT_DAMAGE_ENEMY)
                        break
                    self._check_death(world, target_ent)
                    # ── 施加状态效果 ──
                    if card.status_effect and actual_dmg > 0:
                        status_sys = StatusSystem(self.gs)
                        se = card.status_effect
                        status_sys.apply_status(
                            world, target_ent,
                            se.get("type", "burn"),
                            se.get("turns", 1),
                            se.get("value", 0),
                        )
            # Hellfire: also damage player minions
            if card.name.lower() == "hellfire":
                minion_ents = world.get_entities_with(MinionComponent, HealthComponent)
                for m in minion_ents:
                    m_comp = world.get_component(m, MinionComponent)
                    if m_comp and m_comp.owner == "player":
                        mh = world.get_component(m, HealthComponent)
                        if mh and mh.alive:
                            mh.take_damage(damage)
                            self._spawn_float(world, m, f"-{damage}", FLOAT_DAMAGE)
                            self._check_death(world, m)

            # ── AOE attack 自带护盾/治疗 ──
            if card.shield > 0:
                player_h = self._get_player_health(world)
                if player_h:
                    player_h.shield += card.shield
                    self._spawn_float(world, None, f"+{card.shield} 护盾", FLOAT_SHIELD)
            if card.heal > 0:
                player_h = self._get_player_health(world)
                if player_h:
                    healed = player_h.heal(card.heal)
                    self._spawn_float(world, None, f"+{healed} HP", FLOAT_HEAL)
            return  # AOE resolved, skip single-target path

        # Apply damage to single target
        if target is not None:
            target_health = world.get_component(target, HealthComponent)
            if target_health:
                actual_dmg = target_health.take_damage(damage)
                # 元素伤害浮动文字（带元素名）
                if card.element and card.element != "none":
                    elem_name = ELEMENT_NAMES.get(card.element, "")
                    self._spawn_float(world, target, f"-{actual_dmg} {elem_name}", elem_color)
                else:
                    self._spawn_float(world, target, f"-{actual_dmg}", FLOAT_DAMAGE)
                self._flash_entity(world, target)
                # 触发敌人受伤音效
                for ent in world.get_entities_with(AudioEventComponent):
                    ae = world.get_component(ent, AudioEventComponent)
                    if ae:
                        ae.add(AudioEventType.COMBAT_DAMAGE_ENEMY)
                    break
                self._check_death(world, target)

                if lifesteal and actual_dmg > 0:
                    player_h = self._get_player_health(world)
                    if player_h:
                        healed = player_h.heal(actual_dmg)
                        self._spawn_float(world, None, f"+{healed} HP", FLOAT_HEAL)

                # ── 施加状态效果（TEW 新增）─────────────────────
                if card.status_effect and actual_dmg > 0:
                    status_sys = StatusSystem(self.gs)
                    se = card.status_effect
                    status_sys.apply_status(
                        world, target,
                        se.get("type", "burn"),
                        se.get("turns", 1),
                        se.get("value", 0),
                    )

        # Apply shield to self
        if card.shield > 0:
            player_h = self._get_player_health(world)
            if player_h:
                player_h.shield += card.shield
                self._spawn_float(world, None, f"+{card.shield} 护盾", FLOAT_SHIELD)

        # Apply heal to self
        if card.heal > 0:
            player_h = self._get_player_health(world)
            if player_h:
                healed = player_h.heal(card.heal)
                self._spawn_float(world, None, f"+{healed} HP", FLOAT_HEAL)

    # ── Skill Card ──────────────────────────────────────────────────────

    def _resolve_skill_card(self, world: World, card: CardComponent,
                            target, player_health: HealthComponent) -> None:
        # Shield
        if card.shield > 0:
            if player_health:
                player_health.shield += card.shield
                self._spawn_float(world, None, f"+{card.shield} 护盾", FLOAT_SHIELD)

        # Heal
        if card.heal > 0:
            if player_health:
                healed = player_health.heal(card.heal)
                self._spawn_float(world, None, f"+{healed} 生命", FLOAT_HEAL)

        # AOE damage (Holy Nova, Hellfire)
        if card.damage > 0 and card.target == "none":
            # Damage all enemies + enemy minions
            enemy_entities = world.get_entities_with(EnemyComponent, HealthComponent)
            for e in enemy_entities:
                eh = world.get_component(e, HealthComponent)
                if eh:
                    dmg = card.damage
                    # Hellfire also hits player minions
                    if card.name.lower() == "hellfire":
                        pass  # handled separately
                    eh.take_damage(dmg)
                    self._spawn_float(world, e, f"-{dmg}", FLOAT_DAMAGE)
                    self._flash_entity(world, e)
                    self._check_death(world, e)

            # Hellfire damages player minions too
            if card.name.lower() == "hellfire":
                minion_ents = world.get_entities_with(MinionComponent, HealthComponent)
                for m in minion_ents:
                    m_comp = world.get_component(m, MinionComponent)
                    if m_comp and m_comp.owner == "player":
                        mh = world.get_component(m, HealthComponent)
                        if mh:
                            mh.take_damage(card.damage)
                            self._spawn_float(world, m, f"-{card.damage}", FLOAT_DAMAGE)
                            self._check_death(world, m)

            # Heal self for Holy Nova
            if card.heal > 0 and player_health:
                healed = player_health.heal(card.heal)
                self._spawn_float(world, None, f"+{healed} 生命", FLOAT_HEAL)

    # ── Minion Card ─────────────────────────────────────────────────────

    def _resolve_minion_card(self, world: World, card_entity, card: CardComponent) -> None:
        from card_factory import create_minion_from_card
        from components import BoardComponent

        # Check board space
        board_ents = world.get_entities_with(BoardComponent)
        board = None
        if board_ents:
            board_ent = next(iter(board_ents))
            board = world.get_component(board_ent, BoardComponent)

        if board and board.is_full:
            self.gs.show_message("战场已满！")
            return

        # Spawn minion
        minion_ent = create_minion_from_card(world, card_entity)

        # Execute battlecry BEFORE destroying card (card data still needed)
        if card.battlecry:
            self._execute_battlecry(world, minion_ent, card.battlecry)

        # Destroy the card entity — minion cards are consumed on play
        world.destroy_entity(card_entity)

        # Place on board
        if board and minion_ent:
            board.minions.append(minion_ent)

    # ── Battlecry / Deathrattle ───────────────────────────────────────

    def _execute_battlecry(self, world: World, minion_entity, battlecry: dict) -> None:
        bt = battlecry.get("type", "")
        val = battlecry.get("value", 0)

        if bt == "damage_self":
            h = world.get_component(minion_entity, HealthComponent)
            if h:
                h.take_damage(val)
                self._spawn_float(world, minion_entity, f"-{val} HP", FLOAT_DAMAGE)

        elif bt == "freeze":
            from components import KeywordComponent
            kw = world.get_component(minion_entity, KeywordComponent)
            if not kw:
                kw = KeywordComponent()
                world.add_component(minion_entity, kw)
            setattr(minion_entity, "_frozen_turns", val)

        elif bt == "damage_equal_attack":
            atk = world.get_component(minion_entity, AttackComponent)
            if atk:
                enemy_ents = list(world.get_entities_with(EnemyComponent, HealthComponent))
                if enemy_ents:
                    import random
                    target = random.choice(enemy_ents)
                    eh = world.get_component(target, HealthComponent)
                    if eh:
                        eh.take_damage(atk.attack)
                        self._spawn_float(world, target, f"-{atk.attack}", FLOAT_DAMAGE)
                        self._check_death(world, target)

        elif bt == "draw":
            from components import DeckComponent, HandComponent
            player_deck = None
            player_hand = None
            for e in world.get_entities_with(DeckComponent):
                d = world.get_component(e, DeckComponent)
                if d and d.owner == "player":
                    player_deck = d
                    break
            for e in world.get_entities_with(HandComponent):
                h = world.get_component(e, HandComponent)
                if h and h.owner == "player":
                    player_hand = h
                    break
            if player_deck and player_hand:
                for _ in range(val):
                    if len(player_hand.cards) >= 10:
                        break
                    card = player_deck.draw_one()
                    if card:
                        player_hand.cards.append(card)
                self.gs.show_message(f"战吼：抽了 {val} 张牌！", 1.5)

        elif bt == "buff_attack":
            atk = world.get_component(minion_entity, AttackComponent)
            if atk:
                atk.attack += val

        elif bt == "buff_health_per_card":
            h = world.get_component(minion_entity, HealthComponent)
            if h:
                h.hp += val
                h.max_hp += val

        elif bt == "set_stats":
            h = world.get_component(minion_entity, HealthComponent)
            a = world.get_component(minion_entity, AttackComponent)
            if h:
                h.hp = val
                h.max_hp = val
            if a:
                a.attack = val

        # ── TEW 新增战吼类型 ──────────────────────────────────
        elif bt == "damage_aoe":
            # 对所有敌人造成 val 点伤害
            enemy_ents = list(world.get_entities_with(EnemyComponent, HealthComponent))
            for target in enemy_ents:
                eh = world.get_component(target, HealthComponent)
                if eh and eh.alive:
                    eh.take_damage(val)
                    self._spawn_float(world, target, f"-{val}", FLOAT_DAMAGE)
                    self._flash_entity(world, target)
                    self._check_death(world, target)
            # 也打敌方随从
            minion_ents = [e for e in world.get_entities_with(MinionComponent, HealthComponent)
                          if world.get_component(e, MinionComponent)
                          and world.get_component(e, MinionComponent).owner == "enemy"
                          and world.get_component(e, EnemyComponent) is None]
            for m in minion_ents:
                mh = world.get_component(m, HealthComponent)
                if mh and mh.alive:
                    mh.take_damage(val)
                    self._spawn_float(world, m, f"-{val}", FLOAT_DAMAGE)

        elif bt == "apply_status":
            # 向随机敌人施加状态: value = {"type":"burn","turns":2,"damage":3}
            if isinstance(val, dict):
                enemy_ents = list(world.get_entities_with(EnemyComponent, HealthComponent))
                if enemy_ents:
                    import random
                    target = random.choice(enemy_ents)
                    status_sys = StatusSystem(self.gs)
                    status_sys.apply_status(
                        world, target,
                        val.get("type", "burn"),
                        val.get("turns", 1),
                        val.get("damage", 0),
                    )

        elif bt == "shield_all":
            # 给所有友方随从 +val 护盾
            for e in world.get_entities_with(MinionComponent, HealthComponent):
                m = world.get_component(e, MinionComponent)
                if m and m.owner == "player":
                    h = world.get_component(e, HealthComponent)
                    if h:
                        h.shield += val
            # 也给玩家
            player_h = self._get_player_health(world)
            if player_h:
                player_h.shield += val
            self._spawn_float(world, None, f"全体 +{val} 护盾", FLOAT_SHIELD)

        elif bt == "heal_all":
            # 回复所有友方随从 val 点生命
            for e in world.get_entities_with(MinionComponent, HealthComponent):
                m = world.get_component(e, MinionComponent)
                if m and m.owner == "player":
                    h = world.get_component(e, HealthComponent)
                    if h:
                        h.heal(val)
            player_h = self._get_player_health(world)
            if player_h:
                player_h.heal(val)
            self._spawn_float(world, None, f"全体回复 +{val}", FLOAT_HEAL)

    def execute_deathrattle(self, world: World, entity) -> None:
        """Called when a minion dies."""
        card_comp = world.get_component(entity, CardComponent)
        if not card_comp or not card_comp.deathrattle:
            return
        dr = card_comp.deathrattle
        bt = dr.get("type", "")
        val = dr.get("value", 0)

        if bt == "draw":
            # Signal to game logic to draw `val` cards
            self.gs._pending_draw = getattr(self.gs, "_pending_draw", 0) + val

        elif bt == "damage":
            # Deal damage to ALL enemies (AOE explosion on death)
            enemy_ents = list(world.get_entities_with(EnemyComponent, HealthComponent))
            enemy_minions = [e for e in world.get_entities_with(MinionComponent, HealthComponent)
                           if world.get_component(e, MinionComponent)
                           and world.get_component(e, MinionComponent).owner == "enemy"
                           and world.get_component(e, EnemyComponent) is None]
            for target in enemy_ents + enemy_minions:
                h = world.get_component(target, HealthComponent)
                if h and h.alive:
                    h.take_damage(val)
                    self._spawn_float(world, target, f"-{val}", FLOAT_DAMAGE)
                    self._flash_entity(world, target)
                    self._check_death(world, target)

        elif bt == "damage_target":
            # Deal damage to a random enemy
            enemy_ents = list(world.get_entities_with(EnemyComponent, HealthComponent))
            if enemy_ents:
                import random
                target = random.choice(enemy_ents)
                h = world.get_component(target, HealthComponent)
                if h:
                    h.take_damage(val)
                    self._spawn_float(world, target, f"-{val}", FLOAT_DAMAGE)
                    self._flash_entity(world, target)
                    self._check_death(world, target)

        elif bt == "heal":
            # Heal player
            player_h = self._get_player_health(world)
            if player_h:
                healed = player_h.heal(val)
                self._spawn_float(world, None, f"+{healed} 生命", FLOAT_HEAL)

    # ── Minion Combat (Enemy Turn) ────────────────────────────────────

    def minion_attack(self, world: World, attacker_entity, target_entity) -> None:
        """A minion attacks a target."""
        atk_comp = world.get_component(attacker_entity, AttackComponent)
        if not atk_comp or not atk_comp.can_attack:
            return

        # Check Taunt redirection
        actual_target = self._resolve_taunt(world, target_entity)

        # Deal damage
        dmg = atk_comp.effective_attack
        target_h = world.get_component(actual_target, HealthComponent)
        if target_h:
            actual_dmg = target_h.take_damage(dmg)
            self._spawn_float(world, actual_target, f"-{dmg}", FLOAT_DAMAGE)
            self._flash_entity(world, actual_target)

            # Poisonous
            kw = world.get_component(attacker_entity, KeywordComponent)
            if kw and kw.poisonous and actual_dmg > 0:
                target_h.hp = 0
                self._spawn_float(world, actual_target, "POISON!", (50, 200, 100))

        # Take damage back (if target is a minion with attack)
        target_atk = world.get_component(actual_target, AttackComponent)
        if target_atk and target_atk.attack > 0:
            atk_h = world.get_component(attacker_entity, HealthComponent)
            if atk_h:
                back_dmg = target_atk.effective_attack
                atk_h.take_damage(back_dmg)
                self._spawn_float(world, attacker_entity, f"-{back_dmg}", FLOAT_DAMAGE)
                self._flash_entity(world, attacker_entity)

        # Lifesteal
        kw = world.get_component(attacker_entity, KeywordComponent)
        if kw and kw.lifesteal and actual_dmg > 0:
            player_h = self._get_player_health(world)
            if player_h:
                healed = player_h.heal(actual_dmg)
                self._spawn_float(world, None, f"+{healed} HP", FLOAT_HEAL)

        # Mark attack used
        atk_comp.attacks_this_turn += 1

        # Check deaths
        self._check_death(world, actual_target)
        self._check_death(world, attacker_entity)

    def _resolve_taunt(self, world: World, intended_target, attacker_owner: str = "player") -> object:
        """If any opposing taunt minions exist, redirect attack to one of them.

        Args:
            attacker_owner: "player" or "enemy" — who's attacking.
                If player attacks → only ENEMY taunters redirect.
                If enemy attacks → only PLAYER taunters redirect.
        """
        taunters = []
        target_owner = "enemy" if attacker_owner == "player" else "player"
        minion_ents = world.get_entities_with(MinionComponent, KeywordComponent, HealthComponent)
        for e in minion_ents:
            kw = world.get_component(e, KeywordComponent)
            m_comp = world.get_component(e, MinionComponent)
            h = world.get_component(e, HealthComponent)
            if kw and kw.taunt and h and h.alive and m_comp:
                if m_comp.owner == target_owner:
                    taunters.append(e)
        return random.choice(taunters) if taunters else intended_target

    # ── Enemy Attacks Player ─────────────────────────────────────────────

    def enemy_attack_player(self, world: World, enemy_entity) -> None:
        atk_comp = world.get_component(enemy_entity, AttackComponent)
        if not atk_comp:
            return

        dmg = atk_comp.attack

        # Check if player has taunt minions — redirect to one of them
        actual_target = self._resolve_taunt(world, None, attacker_owner="enemy")
        if actual_target is not None:
            # A player taunt minion took the hit
            target_h = world.get_component(actual_target, HealthComponent)
            if target_h:
                absorbed = min(target_h.shield, dmg)
                target_h.shield -= absorbed
                remaining = dmg - absorbed
                target_h.hp -= remaining
                self._spawn_float(world, actual_target, f"-{dmg} (嘲讽)", FLOAT_DAMAGE)
                self._check_death(world, actual_target)
                return

        player_h = self._get_player_health(world)
        if player_h:
            absorbed = min(player_h.shield, dmg)
            player_h.shield -= absorbed
            remaining = dmg - absorbed
            player_h.hp -= remaining
            self._spawn_float(world, None, f"-{dmg} (enemy)", FLOAT_DAMAGE)
            # 触发玩家受伤音效
            for ent in world.get_entities_with(AudioEventComponent):
                ae = world.get_component(ent, AudioEventComponent)
                if ae:
                    ae.add(AudioEventType.COMBAT_DAMAGE_PLAYER)
                break

        # Check game over
        if player_h and player_h.hp <= 0:
            self.gs.phase = Phase.GAME_OVER

    # ── Death Checking ──────────────────────────────────────────────────

    def _check_death(self, world: World, entity) -> None:
        h = world.get_component(entity, HealthComponent)
        if h and not h.alive:
            # ── 区分基础敌人(EnemyComponent) 与 敌方随从(MinionComponent, owner="enemy") ──
            # 只有基础敌人死亡才可能触发房间清场。
            # 敌方随从死亡不影响战斗是否结束。
            was_enemy = world.get_component(entity, EnemyComponent) is not None
            is_enemy_minion = (world.get_component(entity, MinionComponent) is not None
                               and world.get_component(entity, MinionComponent).owner == "enemy"
                               and not was_enemy)

            probe("combat::death", "实体死亡",
                  {"enemy": str(was_enemy), "minion": str(is_enemy_minion)},
                  module="combat")

            # 触发死亡音效
            for ent in world.get_entities_with(AudioEventComponent):
                ae = world.get_component(ent, AudioEventComponent)
                if ae:
                    if was_enemy:
                        ae.add(AudioEventType.COMBAT_DEATH)
                    break
            self.execute_deathrattle(world, entity)
            # Remove from board
            from components import BoardComponent
            board_ents = world.get_entities_with(BoardComponent)
            for be in board_ents:
                board = world.get_component(be, BoardComponent)
                if entity in board.minions:
                    board.minions.remove(entity)
            world.destroy_entity(entity)

            # 玩家回合内，基础敌人死亡 → 检查是否清场
            # 敌方随从(MinionComponent)死亡不会触发此检查
            if was_enemy and self.gs.is_player_turn:
                self._check_room_cleared(world)

    def _check_room_cleared(self, world: World) -> None:
        """Check if all base enemies are dead — if so, clear the room immediately.

        重要区分：
        - 基础敌人 (EnemyComponent)：如果全部死亡 → 战斗结束，清场。
        - 敌方随从 (MinionComponent, owner="enemy")：不影响战斗是否结束，
          会在 _handle_room_clear() 中随整体清场一起清理。
        """
        # 守卫：防止 AOE / 多目标死亡时重复触发清场
        # 一旦房间已切换至 ROOM_COMPLETE，后续调用直接跳过
        if self.gs.phase != Phase.PLAYER_TURN:
            return

        # 只检查基础敌人 (EnemyComponent)，敌方随从不影响房间清场判定
        enemy_ents = list(world.get_entities_with(EnemyComponent, HealthComponent))
        alive = [e for e in enemy_ents
                 if world.get_component(e, HealthComponent)
                 and world.get_component(e, HealthComponent).alive]
        if len(alive) == 0:
            # 所有基础敌人死亡 → 立即清场，跳过敌方回合
            from main import _handle_room_clear
            _handle_room_clear(world, self.gs)

    # ── Helpers ─────────────────────────────────────────────────────────

    def _get_player_health(self, world: World) -> HealthComponent | None:
        for e in world.entities:
            h = world.get_component(e, HealthComponent)
            p = world.get_component(e, PlayerComponent)
            if h and p:
                return h
        # Fallback: first HealthComponent
        for e in world.entities:
            h = world.get_component(e, HealthComponent)
            if h:
                return h
        return None

    def _get_player_component(self, world: World):
        for e in world.entities:
            p = world.get_component(e, PlayerComponent)
            if p:
                return p
        return None

    def _get_player_attack(self, world: World) -> int:
        return 0  # Player doesn't have base attack in this game

    def _spawn_float(self, world: World, entity, text: str, color: tuple) -> None:
        x = 640
        y = 360
        if entity:
            pos = world.get_component(entity, PositionComponent)
            if pos:
                x = pos.x
                y = pos.y
        ft = FloatingTextComponent(text, x, y, color)
        e = world.create_entity()
        world.add_component(e, ft)

    def _flash_entity(self, world: World, entity) -> None:
        render = world.get_component(entity, RenderComponent)
        if render:
            render.flash_timer = FLASH_DURATION

    def end_player_turn(self, world: World) -> None:
        """Clean up after player turn: reset attacks, clear buffs."""
        probe("combat::end_player_turn", "玩家回合结束",
              {"phase": str(self.gs.phase)}, module="combat")
        # Reset minion attacks
        for e in world.get_entities_with(AttackComponent):
            atk = world.get_component(e, AttackComponent)
            atk.attacks_this_turn = 0
            atk.temp_attack_buff = 0

        # Reset just_played flag
        for e in world.get_entities_with(MinionComponent):
            m = world.get_component(e, MinionComponent)
            if m:
                m.just_played = False

        # Remove temp keywords (Rush can't attack after summon turn unless Rush)
        # Charge minions already handled

        # Refresh energy
        energy_ents = world.get_entities_with(EnergyComponent)
        for e in energy_ents:
            eng = world.get_component(e, EnergyComponent)
            if eng:
                eng.refresh()

        # Draw 1 card (player deck only)
        from components import DeckComponent, HandComponent
        player_deck = None
        player_hand = None
        for e in world.get_entities_with(DeckComponent):
            d = world.get_component(e, DeckComponent)
            if d and d.owner == "player":
                player_deck = d
                break
        for e in world.get_entities_with(HandComponent):
            h = world.get_component(e, HandComponent)
            if h and h.owner == "player":
                player_hand = h
                break
        if player_deck and player_hand:
            card = player_deck.draw_one()
            if card:
                player_hand.cards.append(card)

        # ── 状态效果回合结算（TEW — 敌人回合结束时处理敌人状态）──
        status_sys = StatusSystem(self.gs)
        status_sys.process_turn_end(world, owner="enemy")

        self.gs.phase = Phase.ENEMY_TURN
        self.gs.clear_selection()
        # 触发敌人回合开始音效
        for ent in world.get_entities_with(AudioEventComponent):
            ae = world.get_component(ent, AudioEventComponent)
            if ae:
                ae.add(AudioEventType.ENEMY_TURN_START)
            break
