"""Render system — draws all game visuals using pygame."""

from __future__ import annotations
import pygame
from ecs import System, World
from components import (
    HealthComponent, AttackComponent, CardComponent,
    MinionComponent, EnemyComponent, RenderComponent,
    FloatingTextComponent, BoardComponent,
    HandComponent, WaveComponent, KeywordComponent,
    EnergyComponent, PlayerComponent,
)
from game_state import GameState, Phase
from constants import *
from rooms.room_system import campfire_heal_percent
from card_factory import translate_keyword


class RenderSystem(System):
    """Draws everything each frame."""

    def __init__(self, screen, game_state) -> None:
        self.screen = screen
        self.gs = game_state
        self.f_large = get_font(FONT_LARGE_SIZE)
        self.f_med = get_font(FONT_MEDIUM_SIZE)
        self.f_small = get_font(FONT_SMALL_SIZE)
        self.f_tiny = get_font(FONT_TINY_SIZE)
        self.btn_end_turn = None

    # ── Main draw ────────────────────────────────────────────────

    def update(self, world: World, dt: float, events=None) -> None:
        self.screen.fill(BG_COLOR)
        self._draw_zones(world)
        self._draw_enemies(world)
        self._draw_enemy_board(world)
        self._draw_board(world)
        self._draw_hand(world)
        self._draw_player_hud(world)
        self._draw_overlays(world, dt)
        self._draw_floats(world, dt)
        self._tick_render(world, dt)

    # ── Zone backgrounds ────────────────────────────────────────

    def _draw_zones(self, world) -> None:
        r = pygame.Rect(0, ENEMY_ZONE_TOP, SCREEN_WIDTH, ENEMY_ZONE_HEIGHT)
        pygame.draw.rect(self.screen, BG_ENEMY_ZONE, r)
        pygame.draw.line(self.screen, DIVIDER_COLOR,
                        (0, ENEMY_ZONE_TOP + ENEMY_ZONE_HEIGHT),
                        (SCREEN_WIDTH, ENEMY_ZONE_TOP + ENEMY_ZONE_HEIGHT), 2)

        # Room indicator
        label = f"第 {self.gs.room_number} 层"
        if self.gs.is_elite_room:
            label += "  ⚔精英⚔"
        elif self.gs.is_battle_room:
            label += "  ⚔战斗"
        lbl = self.f_tiny.render(label, True, TEXT_DIM)
        self.screen.blit(lbl, (10, ENEMY_ZONE_TOP + 2))

        # Enemy board zone
        r_eb = pygame.Rect(0, ENEMY_BOARD_ZONE_TOP, SCREEN_WIDTH, ENEMY_BOARD_ZONE_HEIGHT)
        pygame.draw.rect(self.screen, (35, 35, 55), r_eb)
        pygame.draw.line(self.screen, DIVIDER_COLOR,
                        (0, ENEMY_BOARD_ZONE_TOP + ENEMY_BOARD_ZONE_HEIGHT),
                        (SCREEN_WIDTH, ENEMY_BOARD_ZONE_TOP + ENEMY_BOARD_ZONE_HEIGHT), 2)
        lbl3 = self.f_tiny.render("敌人战场", True, TEXT_DIM)
        self.screen.blit(lbl3, (10, ENEMY_BOARD_ZONE_TOP + 2))

        r2 = pygame.Rect(0, BOARD_ZONE_TOP, SCREEN_WIDTH, BOARD_ZONE_HEIGHT)
        pygame.draw.rect(self.screen, BG_BOARD, r2)
        pygame.draw.line(self.screen, DIVIDER_COLOR,
                        (0, BOARD_ZONE_TOP), (SCREEN_WIDTH, BOARD_ZONE_TOP), 2)
        lbl2 = self.f_tiny.render("你的战场", True, TEXT_DIM)
        self.screen.blit(lbl2, (10, BOARD_ZONE_TOP + 4))

    # ── Enemies ─────────────────────────────────────────────────

    def _draw_enemies(self, world) -> None:
        """Draw base enemies (EnemyComponent) in the enemy zone."""
        base_ents = [e for e in world.get_entities_with(EnemyComponent, HealthComponent)
                     if world.get_component(e, HealthComponent)
                     and world.get_component(e, HealthComponent).alive]
        if not base_ents:
            return

        total_w = len(base_ents) * (ENEMY_WIDTH + ENEMY_SPACING) - ENEMY_SPACING
        start_x = (SCREEN_WIDTH - total_w) // 2
        for i, e in enumerate(base_ents):
            x = start_x + i * (ENEMY_WIDTH + ENEMY_SPACING)
            y = ENEMY_Y
            self._draw_one_enemy(world, e, x, y)

        # ── Enemy hand indicator ────────────────────────────
        enemy_hand = None
        for e in world.get_entities_with(HandComponent):
            h = world.get_component(e, HandComponent)
            if h and h.owner == "enemy":
                enemy_hand = h
                break
        if enemy_hand and enemy_hand.cards:
            count_text = self.f_tiny.render(f"敌人手牌: {len(enemy_hand.cards)}张",
                                            True, (255, 120, 80))
            self.screen.blit(count_text, (SCREEN_WIDTH - 160, ENEMY_ZONE_TOP + 2))

    def _draw_enemy_board(self, world) -> None:
        """Draw enemy minions (card-spawned) in the enemy board zone."""
        minion_ents = [e for e in world.get_entities_with(MinionComponent, HealthComponent)
                       if world.get_component(e, MinionComponent)
                       and world.get_component(e, MinionComponent).owner == "enemy"
                       and not world.get_component(e, EnemyComponent)
                       and world.get_component(e, HealthComponent).alive]
        if not minion_ents:
            return

        total_w = len(minion_ents) * (MINION_WIDTH + BOARD_MINION_SPACING) - BOARD_MINION_SPACING
        start_x = (SCREEN_WIDTH - total_w) // 2
        for i, e in enumerate(minion_ents):
            x = start_x + i * (MINION_WIDTH + BOARD_MINION_SPACING)
            y = ENEMY_BOARD_Y
            self._draw_one_minion(world, e, x, y, is_enemy=True)

    def _draw_enemy_minion(self, world, entity, x, y) -> None:
        """Draw a card-spawned enemy minion in enemy zone."""
        render = world.get_component(entity, RenderComponent)
        h = world.get_component(entity, HealthComponent)
        atk = world.get_component(entity, AttackComponent)
        mcomp = world.get_component(entity, MinionComponent)
        kw = world.get_component(entity, KeywordComponent)
        if not h:
            return

        rect = pygame.Rect(x, y, ENEMY_WIDTH, ENEMY_HEIGHT)
        color = (140, 60, 60)  # Dark red for enemy card minions

        if render and (render.selected or render.targetable):
            gc = CARD_TARGET_GLOW if render.targetable else CARD_SELECTED_GLOW
            g = pygame.Rect(x - 3, y - 3, ENEMY_WIDTH + 6, ENEMY_HEIGHT + 6)
            pygame.draw.rect(self.screen, gc, g, 3, 10)
        elif render and render.hovered:
            g = pygame.Rect(x - 2, y - 2, ENEMY_WIDTH + 4, ENEMY_HEIGHT + 4)
            pygame.draw.rect(self.screen, CARD_HOVER_GLOW, g, 2, 10)

        pygame.draw.rect(self.screen, color, rect, 0, ENEMY_RADIUS)

        if render and render.flash_timer > 0:
            alpha = int(180 * render.flash_timer / FLASH_DURATION)
            s = pygame.Surface((ENEMY_WIDTH, ENEMY_HEIGHT), pygame.SRCALPHA)
            s.fill((255, 80, 80, alpha))
            self.screen.blit(s, (x, y))

        nm = (mcomp.name if mcomp else "?")[:14]
        ns = self.f_tiny.render(nm, True, TEXT_COLOR)
        self.screen.blit(ns, (x + 3, y + 3))

        if atk:
            a = self.f_med.render(str(atk.attack), True, MINION_ATTACK_COLOR)
            self.screen.blit(a, (x + 5, y + ENEMY_HEIGHT - 28))
        hp = self.f_med.render(str(h.hp), True, MINION_HEALTH_COLOR)
        self.screen.blit(hp, (x + ENEMY_WIDTH - hp.get_width() - 5, y + ENEMY_HEIGHT - 28))

        if h.shield > 0:
            ss = self.f_tiny.render(f"S:{h.shield}", True, SHIELD_COLOR)
            self.screen.blit(ss, (x + ENEMY_WIDTH // 2 - ss.get_width() // 2, y + ENEMY_HEIGHT + 2))
        if kw and kw.divine_shield:
            ds = self.f_tiny.render("神盾", True, (200, 220, 255))
            self.screen.blit(ds, (x + ENEMY_WIDTH - ds.get_width() - 2, y + 2))
        if kw and kw.poisonous:
            ps = self.f_tiny.render("剧毒", True, (50, 200, 100))
            self.screen.blit(ps, (x + 2, y + ENEMY_HEIGHT - 42))

        # "召唤" label
        sl = self.f_tiny.render("召唤物", True, (255, 180, 60))
        self.screen.blit(sl, (x + ENEMY_WIDTH // 2 - sl.get_width() // 2,
                            y + ENEMY_HEIGHT + 2))

        if render:
            render.rect = (x, y, ENEMY_WIDTH, ENEMY_HEIGHT)

    def _draw_one_enemy(self, world, entity, x, y) -> None:
        render = world.get_component(entity, RenderComponent)
        h = world.get_component(entity, HealthComponent)
        atk = world.get_component(entity, AttackComponent)
        enemy = world.get_component(entity, EnemyComponent)
        kw = world.get_component(entity, KeywordComponent)
        if not h or not enemy:
            return

        rect = pygame.Rect(x, y, ENEMY_WIDTH, ENEMY_HEIGHT)
        if self.gs.is_elite_room:
            color = (160, 40, 160)  # Elite purple
        else:
            color = ENEMY_BOSS_BG if enemy.is_boss else ENEMY_NORMAL_BG

        if render and (render.selected or render.targetable):
            gc = CARD_TARGET_GLOW if render.targetable else CARD_SELECTED_GLOW
            g = pygame.Rect(x - 3, y - 3, ENEMY_WIDTH + 6, ENEMY_HEIGHT + 6)
            pygame.draw.rect(self.screen, gc, g, 3, ENEMY_RADIUS + 2)
        elif render and render.hovered:
            g = pygame.Rect(x - 2, y - 2, ENEMY_WIDTH + 4, ENEMY_HEIGHT + 4)
            pygame.draw.rect(self.screen, CARD_HOVER_GLOW, g, 2, ENEMY_RADIUS + 1)

        pygame.draw.rect(self.screen, color, rect, 0, ENEMY_RADIUS)

        if render and render.flash_timer > 0:
            alpha = int(180 * render.flash_timer / FLASH_DURATION)
            s = pygame.Surface((ENEMY_WIDTH, ENEMY_HEIGHT), pygame.SRCALPHA)
            s.fill((255, 80, 80, alpha))
            self.screen.blit(s, (x, y))

        ns = self.f_tiny.render(enemy.name[:14], True, TEXT_COLOR)
        self.screen.blit(ns, (x + 3, y + 3))

        ic = ENEMY_INTENT_ATTACK
        itxt = str(enemy.intent_value) if enemy.intent == "attack" else "?"
        if enemy.intent == "defend":
            ic = ENEMY_INTENT_DEFEND
            itxt = f"+{enemy.intent_value} 护盾"
        elif enemy.intent == "buff":
            ic = ENEMY_INTENT_BUFF
            itxt = f"+{enemy.intent_value} 攻击"
        its = self.f_tiny.render(itxt, True, ic)
        self.screen.blit(its, (x + 3, y + 18))

        if atk:
            a = self.f_med.render(str(atk.attack), True, MINION_ATTACK_COLOR)
            self.screen.blit(a, (x + 5, y + ENEMY_HEIGHT - 28))
        hp_text = f"{h.hp}/{h.max_hp}"
        hp = self.f_med.render(hp_text, True, MINION_HEALTH_COLOR)
        self.screen.blit(hp, (x + ENEMY_WIDTH - hp.get_width() - 5, y + ENEMY_HEIGHT - 28))

        # Shield display
        if h.shield > 0:
            ss = self.f_tiny.render(f"护盾:{h.shield}", True, SHIELD_COLOR)
            self.screen.blit(ss, (x + ENEMY_WIDTH // 2 - ss.get_width() // 2,
                               y + ENEMY_HEIGHT + 2))

        if enemy.is_boss:
            bs = self.f_tiny.render("首领", True, (255, 220, 80))
            y_boss = y + ENEMY_HEIGHT + (4 if h.shield > 0 else 2)
            self.screen.blit(bs, (x + ENEMY_WIDTH // 2 - bs.get_width() // 2,
                               y_boss + 14))
        if kw and kw.divine_shield:
            ds = self.f_tiny.render("神盾", True, (200, 220, 255))
            self.screen.blit(ds, (x + ENEMY_WIDTH - ds.get_width() - 2, y + 2))
        if kw and kw.poisonous:
            ps = self.f_tiny.render("剧毒", True, (50, 200, 100))
            self.screen.blit(ps, (x + 2, y + ENEMY_HEIGHT - 42))

        if render:
            render.rect = (x, y, ENEMY_WIDTH, ENEMY_HEIGHT)

    # ── Board (player minions) ─────────────────────────────────

    def _draw_board(self, world) -> None:
        ents = list(world.get_entities_with(BoardComponent))
        if not ents:
            return
        board = world.get_component(ents[0], BoardComponent)
        if not board or not board.minions:
            return
        # Only draw player-owned minions on player board
        player_minions = [m for m in board.minions
                         if world.get_component(m, MinionComponent)
                         and world.get_component(m, MinionComponent).owner == "player"]
        if not player_minions:
            return
        total_w = len(player_minions) * (MINION_WIDTH + BOARD_MINION_SPACING) - BOARD_MINION_SPACING
        start_x = (SCREEN_WIDTH - total_w) // 2
        for i, m in enumerate(player_minions):
            x = start_x + i * (MINION_WIDTH + BOARD_MINION_SPACING)
            y = BOARD_Y
            self._draw_one_minion(world, m, x, y)

    def _draw_one_minion(self, world, entity, x, y, is_enemy: bool = False) -> None:
        render = world.get_component(entity, RenderComponent)
        h = world.get_component(entity, HealthComponent)
        atk = world.get_component(entity, AttackComponent)
        kw = world.get_component(entity, KeywordComponent)
        mcomp = world.get_component(entity, MinionComponent)
        card = world.get_component(entity, CardComponent)
        if not h:
            return

        rect = pygame.Rect(x, y, MINION_WIDTH, MINION_HEIGHT)
        if is_enemy:
            color = (140, 60, 60)  # Dark red for enemy minions
        else:
            color = MINION_BG
            if kw and kw.taunt:
                color = (60, 90, 70)
            if kw and kw.divine_shield:
                color = (70, 110, 200)

        if render and (render.selected or render.targetable):
            gc = CARD_TARGET_GLOW if render.targetable else CARD_SELECTED_GLOW
            g = pygame.Rect(x - 3, y - 3, MINION_WIDTH + 6, MINION_HEIGHT + 6)
            pygame.draw.rect(self.screen, gc, g, 3, MINION_RADIUS + 2)
        elif render and render.hovered:
            g = pygame.Rect(x - 2, y - 2, MINION_WIDTH + 4, MINION_HEIGHT + 4)
            pygame.draw.rect(self.screen, CARD_HOVER_GLOW, g, 2, MINION_RADIUS + 1)

        pygame.draw.rect(self.screen, color, rect, 0, MINION_RADIUS)

        if render and render.flash_timer > 0:
            alpha = int(180 * render.flash_timer / FLASH_DURATION)
            s = pygame.Surface((MINION_WIDTH, MINION_HEIGHT), pygame.SRCALPHA)
            s.fill((255, 80, 80, alpha))
            self.screen.blit(s, (x, y))

        nm = (mcomp.name if mcomp else "?")[:10]
        ns = self.f_tiny.render(nm, True, TEXT_COLOR)
        self.screen.blit(ns, (x + 3, y + 3))

        if atk:
            a = self.f_med.render(str(atk.attack), True, MINION_ATTACK_COLOR)
            self.screen.blit(a, (x + 5, y + MINION_HEIGHT - 28))
        hp_text = f"{h.hp}/{h.max_hp}"
        hp = self.f_med.render(hp_text, True, MINION_HEALTH_COLOR)
        self.screen.blit(hp, (x + MINION_WIDTH - hp.get_width() - 5,
                               y + MINION_HEIGHT - 28))
        if h.shield > 0:
            ss = self.f_tiny.render(f"S:{h.shield}", True, SHIELD_COLOR)
            self.screen.blit(ss, (x + MINION_WIDTH // 2 - ss.get_width() // 2,
                                y + MINION_HEIGHT + 2))
        if kw and kw.divine_shield:
            ds = self.f_tiny.render("神盾", True, (200, 220, 255))
            self.screen.blit(ds, (x + MINION_WIDTH - ds.get_width() - 2, y + 2))
        if kw and kw.poisonous:
            ps = self.f_tiny.render("剧毒", True, (50, 200, 100))
            self.screen.blit(ps, (x + 2, y + MINION_HEIGHT - 42))
        if kw and kw.windfury:
            wf = self.f_tiny.render("风怒", True, (50, 160, 230))
            self.screen.blit(wf, (x + MINION_WIDTH - wf.get_width() - 2,
                               y + MINION_HEIGHT - 42))
        if kw and kw.lifesteal:
            ls = self.f_tiny.render("吸血", True, (160, 70, 200))
            self.screen.blit(ls, (x + 2, y + 14))
        if card and card.upgraded:
            up = self.f_tiny.render("★", True, (255, 220, 80))
            self.screen.blit(up, (x + MINION_WIDTH // 2 - up.get_width() // 2, y + 2))

        if render:
            render.rect = (x, y, MINION_WIDTH, MINION_HEIGHT)

    # ── Hand ────────────────────────────────────────────────────

    def _draw_hand(self, world) -> None:
        # Only draw player hand
        hand = None
        for e in world.get_entities_with(HandComponent):
            h = world.get_component(e, HandComponent)
            if h and h.owner == "player":
                hand = h
                break
        if not hand or not hand.cards:
            return

        n = len(hand.cards)
        total_w = n * (CARD_WIDTH + HAND_CARD_SPACING) - HAND_CARD_SPACING
        if total_w > SCREEN_WIDTH - 40:
            fit = (SCREEN_WIDTH - 40) // (CARD_WIDTH + HAND_CARD_SPACING)
            show = hand.cards[-fit:]
        else:
            show = hand.cards
        start_x = (SCREEN_WIDTH - (len(show) * (CARD_WIDTH + HAND_CARD_SPACING)
                    - HAND_CARD_SPACING)) // 2
        for i, c in enumerate(show):
            x = start_x + i * (CARD_WIDTH + HAND_CARD_SPACING)
            y = HAND_Y
            render = world.get_component(c, RenderComponent)
            hover = render and render.hovered
            lift = HAND_HOVER_LIFT if hover else 0
            self._draw_one_card(world, c, x, y - lift, i)

    def _draw_one_card(self, world, entity, x, y, idx) -> None:
        render = world.get_component(entity, RenderComponent)
        card = world.get_component(entity, CardComponent)
        if not card:
            return
        energy = self._energy(world)
        playable = energy and energy.current >= card.cost and self.gs.is_player_turn

        rect = pygame.Rect(x, y, CARD_WIDTH, CARD_HEIGHT)

        if render and render.selected:
            g = pygame.Rect(x - 2, y - 2, CARD_WIDTH + 4, CARD_HEIGHT + 4)
            pygame.draw.rect(self.screen, CARD_SELECTED_GLOW, g, 2, CARD_RADIUS + 1)
        elif render and render.hovered and playable:
            g = pygame.Rect(x - 2, y - 2, CARD_WIDTH + 4, CARD_HEIGHT + 4)
            pygame.draw.rect(self.screen, CARD_HOVER_GLOW, g, 2, CARD_RADIUS + 1)

        if card.card_type == "attack":
            bg = CARD_ATTACK_BG
        elif card.card_type == "skill":
            bg = CARD_SKILL_BG
        else:
            bg = CARD_MINION_BG
        if not playable:
            bg = tuple(max(0, c - 80) for c in bg)
        # Upgraded cards get a golden tint
        if card.upgraded:
            bg = tuple(min(255, c + 20) for c in bg)

        pygame.draw.rect(self.screen, bg, rect, 0, CARD_RADIUS)
        pygame.draw.rect(self.screen, CARD_FRAME, rect, 2, CARD_RADIUS)

        rc = {"common": RARITY_COMMON, "rare": RARITY_RARE,
              "epic": RARITY_EPIC, "legendary": RARITY_LEGENDARY}
        pygame.draw.rect(self.screen, rc.get(card.rarity, RARITY_COMMON), rect, 1, CARD_RADIUS)

        cs = self.f_med.render(str(card.cost), True, ENERGY_COLOR)
        self.screen.blit(cs, (x + 4, y + 4))

        name_display = card.name[:14]
        if card.upgraded:
            name_display = name_display[:12] + "★"
        ns = self.f_tiny.render(name_display, True, TEXT_COLOR)
        self.screen.blit(ns, (x + 4, y + 24))

        ts = self.f_tiny.render(card.card_type.upper(), True, (200, 200, 220))
        self.screen.blit(ts, (x + 4, y + 40))

        if card.card_type == "minion":
            a = self.f_med.render(str(card.attack), True, MINION_ATTACK_COLOR)
            self.screen.blit(a, (x + 4, y + CARD_HEIGHT - 30))
            h = self.f_med.render(str(card.health), True, MINION_HEALTH_COLOR)
            self.screen.blit(h, (x + CARD_WIDTH - h.get_width() - 4,
                               y + CARD_HEIGHT - 30))

        # 根据卡牌类型决定最大行数（minion 卡需要给攻/血留空间）
        max_desc_lines = 4 if card.card_type == "minion" else 6
        line_height = 14
        desc_start_y = y + 58
        lines = self._wrap_and_truncate(card.description, CARD_WIDTH - 8,
                                        self.f_tiny, max_desc_lines)
        for li, line in enumerate(lines):
            ls = self.f_tiny.render(line, True, TEXT_COLOR)
            self.screen.blit(ls, (x + 4, desc_start_y + li * line_height))

        if card.keywords:
            # 关键词转为中文显示
            kw_cn = [translate_keyword(k) for k in card.keywords[:2]]
            ktxt = ", ".join(kw_cn)
            ks = self.f_tiny.render(ktxt[:18], True, (200, 180, 50))
            self.screen.blit(ks, (x + 4, y + CARD_HEIGHT - 14))

        if render:
            render.rect = (x, y, CARD_WIDTH, CARD_HEIGHT)

    # ── Player HUD ──────────────────────────────────────────────

    def _draw_player_hud(self, world) -> None:
        hp_comp = self._hp(world)
        energy = self._energy(world)

        # HP bar
        bw, bh = 200, 24
        bx, by = 20, SCREEN_HEIGHT - 50
        pygame.draw.rect(self.screen, HP_BG, (bx, by, bw, bh))
        if hp_comp:
            ratio = max(0.0, hp_comp.hp / hp_comp.max_hp)
            pygame.draw.rect(self.screen, HP_COLOR, (bx, by, int(bw * ratio), bh))
        hp_txt = f"生命: {hp_comp.hp}/{hp_comp.max_hp}" if hp_comp else "生命: ?"
        ht = self.f_small.render(hp_txt, True, TEXT_COLOR)
        self.screen.blit(ht, (bx + 5, by + 3))

        if hp_comp and hp_comp.shield > 0:
            st = self.f_small.render(f"护盾: {hp_comp.shield}", True, SHIELD_COLOR)
            self.screen.blit(st, (bx + bw + 10, by + 3))

        # Gold display
        gt = self.f_small.render(f"金币: {self.gs.gold}", True, (255, 215, 0))
        self.screen.blit(gt, (bx + bw + 10, by + 24))

        # ── Difficulty HUD ────────────────────────────────────────
        from systems.difficulty_system import get_difficulty
        dm = get_difficulty()
        tier = dm.get_tier(self.gs.room_number)
        asc = self.gs.ascension_level
        tier_color = DIFFICULTY_TIER_COLORS.get(tier.level, (200, 200, 200))
        asc_color = ASCENSION_COLORS.get(asc, (200, 200, 200))

        # Room number + tier label
        room_text = f"房间 {self.gs.room_number} | {tier.name}"
        rt = self.f_tiny.render(room_text, True, tier_color)
        self.screen.blit(rt, (SCREEN_WIDTH // 2 - rt.get_width() // 2, by + 2))

        # Ascension label
        asc_text = f"进阶 {asc}"
        at = self.f_tiny.render(asc_text, True, asc_color)
        self.screen.blit(at, (SCREEN_WIDTH // 2 - at.get_width() // 2, by + 16))

        # Energy
        if energy:
            ex = SCREEN_WIDTH - 150
            ey = by
            ew = 120
            pygame.draw.rect(self.screen, ENERGY_BG, (ex, ey, ew, bh))
            ratio = max(0.0, energy.current / energy.max_energy)
            pygame.draw.rect(self.screen, ENERGY_COLOR, (ex, ey, int(ew * ratio), bh))
            et = self.f_small.render(f"能量: {energy.current}/{energy.max_energy}",
                                      True, TEXT_COLOR)
            self.screen.blit(et, (ex + 5, ey + 3))

        # Buttons
        self.btn_end_turn = pygame.Rect(SCREEN_WIDTH - 160, SCREEN_HEIGHT - 90, 140, 36)
        self._btn(self.btn_end_turn, "结束回合", self.gs.is_player_turn)

    def _btn(self, rect, text, enabled) -> None:
        mouse = pygame.mouse.get_pos()
        hover = rect.collidepoint(mouse)
        color = BUTTON_COLOR if enabled else BUTTON_DISABLED
        if hover and enabled:
            color = BUTTON_HOVER
        pygame.draw.rect(self.screen, color, rect, 0, 6)
        t = self.f_small.render(text, True, BUTTON_TEXT)
        self.screen.blit(t, (rect.x + rect.width // 2 - t.get_width() // 2,
                            rect.y + rect.height // 2 - t.get_height() // 2))

    # ── Overlays ─────────────────────────────────────────────────

    def _draw_overlays(self, world, dt) -> None:
        gs = self.gs

        if gs.phase == Phase.ROOM_COMPLETE:
            self._draw_room_clear(world)
        elif gs.phase == Phase.GAME_OVER:
            self._draw_game_over(world)
        elif gs.phase == Phase.REWARD:
            self._draw_reward(world)
        elif gs.phase == Phase.EVENT:
            self._draw_event(world)
        elif gs.phase == Phase.MERCHANT:
            self._draw_merchant(world)
        elif gs.phase == Phase.CAMPFIRE:
            self._draw_campfire(world)

        if gs.message and gs.message_timer > 0:
            m = self.f_med.render(gs.message, True, (255, 220, 80))
            self.screen.blit(m, (SCREEN_WIDTH // 2 - m.get_width() // 2, 200))

    # ── Room Clear Overlay ─────────────────────────────────────

    def _draw_room_clear(self, world) -> None:
        self._overlay(180)
        label = "精英" if self.gs.is_elite_room else ""
        t = self.f_large.render(f"第 {self.gs.room_number} 层 {label} 通关！",
                                 True, (255, 220, 80))
        self.screen.blit(t, (SCREEN_WIDTH // 2 - t.get_width() // 2,
                           SCREEN_HEIGHT // 2 - 40))
        sub = self.f_med.render("即将进入下一层…", True, TEXT_DIM)
        self.screen.blit(sub, (SCREEN_WIDTH // 2 - sub.get_width() // 2,
                             SCREEN_HEIGHT // 2 + 10))

    # ── Game Over Overlay ──────────────────────────────────────

    def _draw_game_over(self, world) -> None:
        self._overlay(220)
        t = self.f_large.render("游戏结束", True, (255, 60, 60))
        self.screen.blit(t, (SCREEN_WIDTH // 2 - t.get_width() // 2,
                           SCREEN_HEIGHT // 2 - 60))
        info = self.f_med.render(f"到达第 {self.gs.room_number} 层", True, TEXT_COLOR)
        self.screen.blit(info, (SCREEN_WIDTH // 2 - info.get_width() // 2,
                             SCREEN_HEIGHT // 2))
        gold_info = self.f_med.render(f"金币: {self.gs.gold}", True, (255, 215, 0))
        self.screen.blit(gold_info, (SCREEN_WIDTH // 2 - gold_info.get_width() // 2,
                                  SCREEN_HEIGHT // 2 + 30))
        rst = self.f_med.render("按 ENTER 重新开始", True, (200, 200, 100))
        self.screen.blit(rst, (SCREEN_WIDTH // 2 - rst.get_width() // 2,
                              SCREEN_HEIGHT // 2 + 70))

    # ── Reward Overlay ─────────────────────────────────────────

    def _draw_reward(self, world) -> None:
        self._overlay(160)
        label = "精英奖励 — 选择一张卡牌！" if self.gs.is_elite_room else "奖励 — 选择一张卡牌！"
        title = self.f_large.render(label, True, (255, 220, 80))
        self.screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, 100))
        cards = getattr(self.gs, "reward_cards", [])
        if not cards:
            return
        rw, rh = 160, 200
        sp = 30
        total = len(cards) * (rw + sp) - sp
        sx = (SCREEN_WIDTH - total) // 2
        for i, c in enumerate(cards):
            x = sx + i * (rw + sp)
            y = 230
            self._draw_reward_card(world, c, x, y)

    def _draw_reward_card(self, world, entity, x, y) -> None:
        render = world.get_component(entity, RenderComponent)
        card = world.get_component(entity, CardComponent)
        if not card:
            return
        hover = render and render.hovered
        rect = pygame.Rect(x, y, 160, 200)
        bg = CARD_ATTACK_BG if card.card_type == "attack" else (
               CARD_SKILL_BG if card.card_type == "skill" else CARD_MINION_BG)
        if hover:
            bg = tuple(min(255, c + 40) for c in bg)
        pygame.draw.rect(self.screen, bg, rect, 0, 10)
        pygame.draw.rect(self.screen, CARD_FRAME, rect, 2, 10)
        ns = self.f_small.render(card.name[:16], True, TEXT_COLOR)
        self.screen.blit(ns, (x + 8, y + 10))
        cs = self.f_med.render(str(card.cost), True, ENERGY_COLOR)
        self.screen.blit(cs, (x + 8, y + 30))
        lines = self._wrap_and_truncate(card.description, 144, self.f_tiny, 7)
        for li, line in enumerate(lines):
            ls = self.f_tiny.render(line, True, TEXT_COLOR)
            self.screen.blit(ls, (x + 8, y + 60 + li * 14))
        if card.keywords:
            kw_cn = [translate_keyword(k) for k in card.keywords[:2]]
            ktxt = ", ".join(kw_cn)
            ks = self.f_tiny.render(ktxt[:18], True, (200, 180, 50))
            self.screen.blit(ks, (x + 8, y + rect.height - 18))
        if render:
            render.rect = (x, y, 160, 200)

    # ── Event Overlay ──────────────────────────────────────────

    def _draw_event(self, world) -> None:
        event = self.gs.current_event
        if not event:
            return
        self._overlay(200)

        # Title
        title = self.f_large.render(f"事件房 — {event['title']}", True, (200, 140, 255))
        self.screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, 100))

        # Event image/icon area
        icon_rect = pygame.Rect(SCREEN_WIDTH // 2 - 60, 160, 120, 80)
        pygame.draw.rect(self.screen, (80, 40, 100), icon_rect, 0, 10)
        ic = self.f_large.render("?", True, (200, 160, 255))
        self.screen.blit(ic, (icon_rect.centerx - ic.get_width() // 2,
                            icon_rect.centery - ic.get_height() // 2))

        # Description
        desc = self._wrap_text(event["description"], SCREEN_WIDTH - 200, self.f_med)
        for li, line in enumerate(desc[:4]):
            ls = self.f_med.render(line, True, TEXT_COLOR)
            self.screen.blit(ls, (SCREEN_WIDTH // 2 - ls.get_width() // 2, 260 + li * 28))

        if self.gs.event_resolved:
            done = self.f_med.render("按 ENTER 继续", True, (255, 220, 80))
            self.screen.blit(done, (SCREEN_WIDTH // 2 - done.get_width() // 2, 500))
            return

        # Choices
        choices = event.get("choices", [])
        start_y = 280
        for i, ch in enumerate(choices):
            rect = pygame.Rect(SCREEN_WIDTH // 2 - 260, start_y + i * 55, 520, 45)
            mouse = pygame.mouse.get_pos()
            hover = rect.collidepoint(mouse)
            color = (60, 80, 140) if hover else (45, 55, 100)
            pygame.draw.rect(self.screen, color, rect, 0, 8)
            pygame.draw.rect(self.screen, (120, 140, 200), rect, 1, 8)
            label = self.f_small.render(ch["label"], True, (255, 255, 255))
            self.screen.blit(label, (rect.x + 15, rect.y + 5))
            desc_text = self.f_tiny.render(ch["description"], True, TEXT_DIM)
            self.screen.blit(desc_text, (rect.x + 15, rect.y + 26))

    # ── Merchant Overlay ───────────────────────────────────────

    def _draw_merchant(self, world) -> None:
        self._overlay(200)

        # Title
        title = self.f_large.render("商人", True, (255, 200, 50))
        self.screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, 40))

        gold_text = self.f_med.render(f"你的金币: {self.gs.gold}", True, (255, 215, 0))
        self.screen.blit(gold_text, (SCREEN_WIDTH // 2 - gold_text.get_width() // 2, 85))

        # Hint
        hint = self.f_tiny.render("点击卡牌购买  |  也可以移除一张牌", True, TEXT_DIM)
        self.screen.blit(hint, (SCREEN_WIDTH // 2 - hint.get_width() // 2, 115))

        # Cards for sale
        cards = self.gs.merchant_cards
        if cards:
            total = len(cards) * 300
            sx = (SCREEN_WIDTH - total) // 2 + 20
            for i, c_ent in enumerate(cards):
                card = world.get_component(c_ent, CardComponent)
                if not card:
                    continue
                price = self.gs.merchant_prices.get(id(c_ent), 50)
                x = sx + i * 300
                y = 160
                self._draw_merchant_card(world, c_ent, x, y, price, card)

        # Remove card button
        rem_rect = pygame.Rect(SCREEN_WIDTH // 2 - 100, 480, 200, 40)
        mouse = pygame.mouse.get_pos()
        h_rem = rem_rect.collidepoint(mouse)
        rc = (200, 80, 60) if h_rem else (160, 55, 40)
        pygame.draw.rect(self.screen, rc, rem_rect, 0, 8)
        rem_txt = self.f_small.render(f"移除卡牌 ({self.gs.merchant_remove_cost}G)", True, BUTTON_TEXT)
        self.screen.blit(rem_txt, (rem_rect.centerx - rem_txt.get_width() // 2,
                                 rem_rect.centery - rem_txt.get_height() // 2))

        # Leave button
        leave_rect = pygame.Rect(SCREEN_WIDTH // 2 - 80, 540, 160, 40)
        h_leave = leave_rect.collidepoint(mouse)
        lc = (45, 130, 200) if h_leave else BUTTON_COLOR
        pygame.draw.rect(self.screen, lc, leave_rect, 0, 8)
        leave_txt = self.f_small.render("离开商店", True, BUTTON_TEXT)
        self.screen.blit(leave_txt, (leave_rect.centerx - leave_txt.get_width() // 2,
                                   leave_rect.centery - leave_txt.get_height() // 2))

    def _draw_merchant_card(self, world, entity, x, y, price, card) -> None:
        render = world.get_component(entity, RenderComponent)
        hover = render and render.hovered
        rect = pygame.Rect(x, y, 260, 200)
        bg = CARD_ATTACK_BG if card.card_type == "attack" else (
               CARD_SKILL_BG if card.card_type == "skill" else CARD_MINION_BG)
        if hover:
            bg = tuple(min(255, c + 30) for c in bg)
        pygame.draw.rect(self.screen, bg, rect, 0, 10)
        pygame.draw.rect(self.screen, CARD_FRAME, rect, 2, 10)

        ns = self.f_small.render(card.name[:18], True, TEXT_COLOR)
        self.screen.blit(ns, (x + 10, y + 10))
        cs = self.f_med.render(str(card.cost), True, ENERGY_COLOR)
        self.screen.blit(cs, (x + 10, y + 32))

        price_text = self.f_med.render(f"{price} G", True,
                                       (255, 215, 0) if self.gs.gold >= price else (255, 80, 80))
        self.screen.blit(price_text, (x + rect.width - price_text.get_width() - 10, y + 10))

        lines = self._wrap_and_truncate(card.description, rect.width - 20,
                                        self.f_tiny, 6)
        for li, line in enumerate(lines):
            ls = self.f_tiny.render(line, True, TEXT_COLOR)
            self.screen.blit(ls, (x + 10, y + 60 + li * 16))

        rarity_text = self.f_tiny.render(card.rarity.upper(), True,
                                          {"common": RARITY_COMMON, "rare": RARITY_RARE,
                                           "epic": RARITY_EPIC, "legendary": RARITY_LEGENDARY}.get(
                                           card.rarity, RARITY_COMMON))
        self.screen.blit(rarity_text, (x + 10, y + rect.height - 20))

        if card.keywords:
            kw_cn = [translate_keyword(k) for k in card.keywords[:2]]
            ktxt = ", ".join(kw_cn)
            ks = self.f_tiny.render(ktxt[:18], True, (200, 180, 50))
            self.screen.blit(ks, (x + rect.width - ks.get_width() - 10,
                                 y + rect.height - 20))

        if render:
            render.rect = (x, y, 260, 200)

    # ── Campfire Overlay ───────────────────────────────────────

    def _draw_campfire(self, world) -> None:
        self._overlay(200)

        title = self.f_large.render("篝火", True, (255, 160, 50))
        self.screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, 80))

        desc = self.f_med.render("围坐在篝火旁，你可以锻造卡牌或休息回复。", True, TEXT_DIM)
        self.screen.blit(desc, (SCREEN_WIDTH // 2 - desc.get_width() // 2, 140))

        mouse = pygame.mouse.get_pos()

        if self.gs.campfire_done:
            done = self.f_large.render("休息完毕 — 继续前进！", True, (255, 220, 80))
            self.screen.blit(done, (SCREEN_WIDTH // 2 - done.get_width() // 2, 400))
            return

        # Upgrade button
        up_rect = pygame.Rect(SCREEN_WIDTH // 2 - 300, 240, 280, 60)
        h_up = up_rect.collidepoint(mouse)
        color_up = (45, 130, 200) if h_up else (35, 100, 160)
        pygame.draw.rect(self.screen, color_up, up_rect, 0, 10)
        up_txt = self.f_med.render("锻造升级", True, (255, 255, 255))
        self.screen.blit(up_txt, (up_rect.centerx - up_txt.get_width() // 2, up_rect.y + 8))
        up_sub = self.f_tiny.render("随机升级牌组中一张可升级的卡牌", True, TEXT_DIM)
        self.screen.blit(up_sub, (up_rect.centerx - up_sub.get_width() // 2, up_rect.y + 34))

        # Rest button
        rest_rect = pygame.Rect(SCREEN_WIDTH // 2 + 20, 240, 280, 60)
        h_rest = rest_rect.collidepoint(mouse)
        color_rest = (40, 160, 70) if h_rest else (30, 120, 50)
        pygame.draw.rect(self.screen, color_rest, rest_rect, 0, 10)
        rest_txt = self.f_med.render("休息回复", True, (255, 255, 255))
        self.screen.blit(rest_txt, (rest_rect.centerx - rest_txt.get_width() // 2, rest_rect.y + 8))
        hp = self._hp(world)
        heal_pct = campfire_heal_percent()
        heal_amt = int(hp.max_hp * heal_pct) if hp else 0
        rest_sub = self.f_tiny.render(f"回复 {int(heal_pct*100)}% 最大生命 (~{heal_amt} HP)", True, TEXT_DIM)
        self.screen.blit(rest_sub, (rest_rect.centerx - rest_sub.get_width() // 2, rest_rect.y + 34))

    # ── Floating text ─────────────────────────────────────────────

    def _draw_floats(self, world, dt) -> None:
        for e in world.get_entities_with(FloatingTextComponent):
            ft = world.get_component(e, FloatingTextComponent)
            ft.timer += dt
            if ft.timer >= ft.duration:
                world.destroy_entity(e)
                continue
            alpha = max(0, 255 - int(255 * ft.timer / ft.duration))
            ft.y = ft.start_y - FLOAT_TEXT_SPEED * ft.timer
            surf = self.f_med.render(ft.text, True, ft.color)
            surf.set_alpha(alpha)
            self.screen.blit(surf, (ft.x - surf.get_width() // 2, ft.y))

    def _tick_render(self, world, dt) -> None:
        for e in world.get_entities_with(RenderComponent):
            r = world.get_component(e, RenderComponent)
            if r.flash_timer > 0:
                r.flash_timer -= dt
            if r.shake_timer > 0:
                r.shake_timer -= dt

    # ── Utils ────────────────────────────────────────────────────

    @staticmethod
    def _char_split(text: str) -> list[str]:
        """按字符分割文本，英文单词保持完整。"""
        result: list[str] = []
        cur = ""
        for ch in text:
            if ch.isspace():
                if cur:
                    result.append(cur)
                    cur = ""
                continue
            # 中文字符、标点单独分割
            if '\u4e00' <= ch <= '\u9fff' or '\u3000' <= ch <= '\u303f' or \
               '\uff00' <= ch <= '\uffef' or ch in '，。！？；：""''（）【】《》':
                if cur:
                    result.append(cur)
                    cur = ""
                result.append(ch)
            else:
                cur += ch
        if cur:
            result.append(cur)
        return result

    def _wrap_text(self, text: str, max_width: int, font) -> list[str]:
        """Wrap text to fit within max_width. Handles Chinese characters."""
        chars = self._char_split(text)
        lines, cur = [], ""
        for ch in chars:
            test = cur + ch
            if font.size(test)[0] <= max_width:
                cur = test
            else:
                lines.append(cur)
                cur = ch
        if cur:
            lines.append(cur)
        return lines

    def _wrap_and_truncate(self, text: str, max_width: int, font,
                           max_lines: int) -> list[str]:
        """换行文本并在超出最大行数时在最后一行末尾添加省略号。
        正确处理中文字符。"""
        chars = self._char_split(text)
        lines, cur = [], ""
        for ch in chars:
            test = cur + ch
            if font.size(test)[0] <= max_width:
                cur = test
            else:
                if len(lines) >= max_lines - 1:
                    lines.append(cur.rstrip("，。") + "…")
                    return lines[:max_lines]
                lines.append(cur)
                cur = ch
        if cur:
            if len(lines) < max_lines:
                lines.append(cur)
            elif lines:
                # 最后一行放不下了，替换为省略号
                lines[-1] = lines[-1].rstrip("，。") + "…"
        return lines[:max_lines]

    def _overlay(self, alpha) -> None:
        s = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        s.fill((10, 10, 25, alpha))
        self.screen.blit(s, (0, 0))

    def _hp(self, world):
        for e in world.entities:
            h = world.get_component(e, HealthComponent)
            p = world.get_component(e, PlayerComponent)
            if h and p:
                return h
        for e in world.entities:
            h = world.get_component(e, HealthComponent)
            if h:
                return h
        return None

    def _energy(self, world):
        for e in world.entities:
            en = world.get_component(e, EnergyComponent)
            if en:
                return en
        return None

    def _wave(self, world):
        for e in world.entities:
            w = world.get_component(e, WaveComponent)
            if w:
                return w.wave_number
        return 0
