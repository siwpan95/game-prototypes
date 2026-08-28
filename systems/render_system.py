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


class RenderSystem(System):
    """Draws everything each frame."""

    def __init__(self, screen, game_state) -> None:
        self.screen = screen
        self.gs = game_state
        # Fonts
        self.f_large = pygame.font.Font(None, FONT_LARGE_SIZE)
        self.f_med = pygame.font.Font(None, FONT_MEDIUM_SIZE)
        self.f_small = pygame.font.Font(None, FONT_SMALL_SIZE)
        self.f_tiny = pygame.font.Font(None, FONT_TINY_SIZE)
        # Store button rects for input system
        self.btn_end_turn = None
        self.btn_next_wave = None

    # ── Main draw ────────────────────────────────────────────────

    def update(self, world: World, dt: float, events=None) -> None:
        self.screen.fill(BG_COLOR)
        self._draw_zones(world)
        self._draw_enemies(world)
        self._draw_board(world)
        self._draw_hand(world)
        self._draw_player_hud(world)
        self._draw_overlays(world, dt)
        self._draw_floats(world, dt)
        self._tick_render(world, dt)

    # ── Zone backgrounds ────────────────────────────────────────

    def _draw_zones(self, world) -> None:
        # Enemy zone
        r = pygame.Rect(0, ENEMY_ZONE_TOP, SCREEN_WIDTH, ENEMY_ZONE_HEIGHT)
        pygame.draw.rect(self.screen, BG_ENEMY_ZONE, r)
        pygame.draw.line(self.screen, DIVIDER_COLOR,
                        (0, ENEMY_ZONE_TOP + ENEMY_ZONE_HEIGHT),
                        (SCREEN_WIDTH, ENEMY_ZONE_TOP + ENEMY_ZONE_HEIGHT), 2)
        lbl = self.f_tiny.render("ENEMIES  —  WAVE " + str(self._wave(world)),
                                   True, TEXT_DIM)
        self.screen.blit(lbl, (10, ENEMY_ZONE_TOP + 4))

        # Board zone
        r2 = pygame.Rect(0, BOARD_ZONE_TOP, SCREEN_WIDTH, BOARD_ZONE_HEIGHT)
        pygame.draw.rect(self.screen, BG_BOARD, r2)
        pygame.draw.line(self.screen, DIVIDER_COLOR,
                        (0, BOARD_ZONE_TOP), (SCREEN_WIDTH, BOARD_ZONE_TOP), 2)
        lbl2 = self.f_tiny.render("YOUR BOARD", True, TEXT_DIM)
        self.screen.blit(lbl2, (10, BOARD_ZONE_TOP + 4))

    # ── Enemies ─────────────────────────────────────────────────

    def _draw_enemies(self, world) -> None:
        ents = list(world.get_entities_with(EnemyComponent, HealthComponent))
        if not ents:
            return
        total_w = len(ents) * (ENEMY_WIDTH + ENEMY_SPACING) - ENEMY_SPACING
        start_x = (SCREEN_WIDTH - total_w) // 2
        for i, e in enumerate(ents):
            x = start_x + i * (ENEMY_WIDTH + ENEMY_SPACING)
            y = ENEMY_Y
            self._draw_one_enemy(world, e, x, y)

    def _draw_one_enemy(self, world, entity, x, y) -> None:
        render = world.get_component(entity, RenderComponent)
        h = world.get_component(entity, HealthComponent)
        atk = world.get_component(entity, AttackComponent)
        enemy = world.get_component(entity, EnemyComponent)
        kw = world.get_component(entity, KeywordComponent)
        if not h or not enemy:
            return

        rect = pygame.Rect(x, y, ENEMY_WIDTH, ENEMY_HEIGHT)
        color = ENEMY_BOSS_BG if enemy.is_boss else ENEMY_NORMAL_BG
        # Glow
        if render and (render.selected or render.targetable):
            gc = CARD_TARGET_GLOW if render.targetable else CARD_SELECTED_GLOW
            g = pygame.Rect(x - 3, y - 3, ENEMY_WIDTH + 6, ENEMY_HEIGHT + 6)
            pygame.draw.rect(self.screen, gc, g, 3, ENEMY_RADIUS + 2)
        elif render and render.hovered:
            g = pygame.Rect(x - 2, y - 2, ENEMY_WIDTH + 4, ENEMY_HEIGHT + 4)
            pygame.draw.rect(self.screen, CARD_HOVER_GLOW, g, 2, ENEMY_RADIUS + 1)

        pygame.draw.rect(self.screen, color, rect, 0, ENEMY_RADIUS)

        # Flash
        if render and render.flash_timer > 0:
            alpha = int(180 * render.flash_timer / FLASH_DURATION)
            s = pygame.Surface((ENEMY_WIDTH, ENEMY_HEIGHT), pygame.SRCALPHA)
            s.fill((255, 80, 80, alpha))
            self.screen.blit(s, (x, y))

        # Name
        ns = self.f_tiny.render(enemy.name[:14], True, TEXT_COLOR)
        self.screen.blit(ns, (x + 3, y + 3))

        # Intent
        ic = ENEMY_INTENT_ATTACK
        itxt = str(enemy.intent_value) if enemy.intent == "attack" else "?"
        if enemy.intent == "defend":
            ic = ENEMY_INTENT_DEFEND
            itxt = f"+{enemy.intent_value} Shield"
        elif enemy.intent == "buff":
            ic = ENEMY_INTENT_BUFF
            itxt = f"+{enemy.intent_value} ATK"
        its = self.f_tiny.render(itxt, True, ic)
        self.screen.blit(its, (x + 3, y + 18))

        # ATK / HP
        if atk:
            a = self.f_med.render(str(atk.attack), True, MINION_ATTACK_COLOR)
            self.screen.blit(a, (x + 5, y + ENEMY_HEIGHT - 28))
        hp = self.f_med.render(str(h.hp), True, MINION_HEALTH_COLOR)
        self.screen.blit(hp, (x + ENEMY_WIDTH - hp.get_width() - 5, y + ENEMY_HEIGHT - 28))

        # Boss label
        if enemy.is_boss:
            bs = self.f_tiny.render("BOSS", True, (255, 220, 80))
            self.screen.blit(bs, (x + ENEMY_WIDTH // 2 - bs.get_width() // 2,
                               y + ENEMY_HEIGHT + 2))
        # Divine shield icon
        if kw and kw.divine_shield:
            ds = self.f_tiny.render("DS", True, (200, 220, 255))
            self.screen.blit(ds, (x + ENEMY_WIDTH - ds.get_width() - 2, y + 2))
        # Poisonous
        if kw and kw.poisonous:
            ps = self.f_tiny.render("P", True, (50, 200, 100))
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
        total_w = len(board.minions) * (MINION_WIDTH + BOARD_MINION_SPACING) - BOARD_MINION_SPACING
        start_x = (SCREEN_WIDTH - total_w) // 2
        for i, m in enumerate(board.minions):
            x = start_x + i * (MINION_WIDTH + BOARD_MINION_SPACING)
            y = BOARD_Y
            self._draw_one_minion(world, m, x, y)

    def _draw_one_minion(self, world, entity, x, y) -> None:
        render = world.get_component(entity, RenderComponent)
        h = world.get_component(entity, HealthComponent)
        atk = world.get_component(entity, AttackComponent)
        kw = world.get_component(entity, KeywordComponent)
        mcomp = world.get_component(entity, MinionComponent)
        if not h:
            return

        rect = pygame.Rect(x, y, MINION_WIDTH, MINION_HEIGHT)
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

        # Name
        nm = (mcomp.name if mcomp else "?")[:10]
        ns = self.f_tiny.render(nm, True, TEXT_COLOR)
        self.screen.blit(ns, (x + 3, y + 3))

        # ATK / HP
        if atk:
            a = self.f_med.render(str(atk.attack), True, MINION_ATTACK_COLOR)
            self.screen.blit(a, (x + 5, y + MINION_HEIGHT - 28))
        hp = self.f_med.render(str(h.hp), True, MINION_HEALTH_COLOR)
        self.screen.blit(hp, (x + MINION_WIDTH - hp.get_width() - 5,
                               y + MINION_HEIGHT - 28))
        # Shield
        if h.shield > 0:
            ss = self.f_tiny.render(f"S:{h.shield}", True, SHIELD_COLOR)
            self.screen.blit(ss, (x + MINION_WIDTH // 2 - ss.get_width() // 2,
                                y + MINION_HEIGHT + 2))
        # Icons
        if kw and kw.divine_shield:
            ds = self.f_tiny.render("DS", True, (200, 220, 255))
            self.screen.blit(ds, (x + MINION_WIDTH - ds.get_width() - 2, y + 2))
        if kw and kw.poisonous:
            ps = self.f_tiny.render("P", True, (50, 200, 100))
            self.screen.blit(ps, (x + 2, y + MINION_HEIGHT - 42))
        if kw and kw.windfury:
            wf = self.f_tiny.render("W", True, (50, 160, 230))
            self.screen.blit(wf, (x + MINION_WIDTH - wf.get_width() - 2,
                               y + MINION_HEIGHT - 42))
        if kw and kw.lifesteal:
            ls = self.f_tiny.render("L", True, (160, 70, 200))
            self.screen.blit(ls, (x + 2, y + 14))

        if render:
            render.rect = (x, y, MINION_WIDTH, MINION_HEIGHT)

    # ── Hand ────────────────────────────────────────────────────

    def _draw_hand(self, world) -> None:
        ents = list(world.get_entities_with(HandComponent))
        if not ents:
            return
        hand = world.get_component(ents[0], HandComponent)
        if not hand or not hand.cards:
            return

        # Layout
        n = len(hand.cards)
        total_w = n * (CARD_WIDTH + HAND_CARD_SPACING) - HAND_CARD_SPACING
        if total_w > SCREEN_WIDTH - 40:
            # Scroll: show last N fits
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

        # Glow
        if render and render.selected:
            g = pygame.Rect(x - 2, y - 2, CARD_WIDTH + 4, CARD_HEIGHT + 4)
            pygame.draw.rect(self.screen, CARD_SELECTED_GLOW, g, 2, CARD_RADIUS + 1)
        elif render and render.hovered and playable:
            g = pygame.Rect(x - 2, y - 2, CARD_WIDTH + 4, CARD_HEIGHT + 4)
            pygame.draw.rect(self.screen, CARD_HOVER_GLOW, g, 2, CARD_RADIUS + 1)

        # Body color
        if card.card_type == "attack":
            bg = CARD_ATTACK_BG
        elif card.card_type == "skill":
            bg = CARD_SKILL_BG
        else:
            bg = CARD_MINION_BG
        if not playable:
            bg = tuple(max(0, c - 80) for c in bg)

        pygame.draw.rect(self.screen, bg, rect, 0, CARD_RADIUS)
        pygame.draw.rect(self.screen, CARD_FRAME, rect, 2, CARD_RADIUS)

        # Rarity border
        rc = {"common": RARITY_COMMON, "rare": RARITY_RARE,
              "epic": RARITY_EPIC, "legendary": RARITY_LEGENDARY}
        pygame.draw.rect(self.screen, rc.get(card.rarity, RARITY_COMMON), rect, 1, CARD_RADIUS)

        # Cost
        cs = self.f_med.render(str(card.cost), True, ENERGY_COLOR)
        self.screen.blit(cs, (x + 4, y + 4))

        # Name
        ns = self.f_tiny.render(card.name[:14], True, TEXT_COLOR)
        self.screen.blit(ns, (x + 4, y + 24))

        # Type
        ts = self.f_tiny.render(card.card_type.upper(), True, (200, 200, 220))
        self.screen.blit(ts, (x + 4, y + 40))

        # Minion stats
        if card.card_type == "minion":
            a = self.f_med.render(str(card.attack), True, MINION_ATTACK_COLOR)
            self.screen.blit(a, (x + 4, y + CARD_HEIGHT - 30))
            h = self.f_med.render(str(card.health), True, MINION_HEALTH_COLOR)
            self.screen.blit(h, (x + CARD_WIDTH - h.get_width() - 4,
                               y + CARD_HEIGHT - 30))

        # Description (wrapped)
        words = card.description.split()
        lines, cur = [], ""
        for w in words:
            test = (cur + " " + w) if cur else w
            if self.f_tiny.size(test)[0] <= CARD_WIDTH - 8:
                cur = test
            else:
                lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
        for li, line in enumerate(lines[:3]):
            ls = self.f_tiny.render(line, True, TEXT_COLOR)
            self.screen.blit(ls, (x + 4, y + 58 + li * 14))

        # Keywords
        if card.keywords:
            ktxt = ", ".join(card.keywords[:2])
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
        hp_txt = f"HP: {hp_comp.hp}/{hp_comp.max_hp}" if hp_comp else "HP: ?"
        ht = self.f_small.render(hp_txt, True, TEXT_COLOR)
        self.screen.blit(ht, (bx + 5, by + 3))

        # Shield
        if hp_comp and hp_comp.shield > 0:
            st = self.f_small.render(f"Shield: {hp_comp.shield}", True, SHIELD_COLOR)
            self.screen.blit(st, (bx + bw + 10, by + 3))

        # Energy
        if energy:
            ex = SCREEN_WIDTH - 150
            ey = by
            ew = 120
            pygame.draw.rect(self.screen, ENERGY_BG, (ex, ey, ew, bh))
            ratio = max(0.0, energy.current / energy.max_energy)
            pygame.draw.rect(self.screen, ENERGY_COLOR, (ex, ey, int(ew * ratio), bh))
            et = self.f_small.render(f"Energy: {energy.current}/{energy.max_energy}",
                                      True, TEXT_COLOR)
            self.screen.blit(et, (ex + 5, ey + 3))

        # Buttons
        self.btn_end_turn = pygame.Rect(SCREEN_WIDTH - 160, SCREEN_HEIGHT - 90, 140, 36)
        self.btn_next_wave = pygame.Rect(SCREEN_WIDTH - 160, SCREEN_HEIGHT - 135, 140, 36)
        self._btn(self.btn_end_turn, "END TURN", self.gs.is_player_turn)
        self._btn(self.btn_next_wave, "NEXT WAVE", True)

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
        if gs.phase == Phase.WAVE_CLEAR:
            self._overlay(180)
            t = self.f_large.render(f"WAVE {self._wave(world)} CLEARED!",
                                     True, (255, 220, 80))
            self.screen.blit(t, (SCREEN_WIDTH // 2 - t.get_width() // 2,
                               SCREEN_HEIGHT // 2 - 40))
        elif gs.phase == Phase.GAME_OVER:
            self._overlay(220)
            t = self.f_large.render("GAME OVER", True, (255, 60, 60))
            self.screen.blit(t, (SCREEN_WIDTH // 2 - t.get_width() // 2,
                               SCREEN_HEIGHT // 2 - 60))
            info = self.f_med.render(f"Reached Wave {self._wave(world)}", True, TEXT_COLOR)
            self.screen.blit(info, (SCREEN_WIDTH // 2 - info.get_width() // 2,
                                 SCREEN_HEIGHT // 2))
            rst = self.f_med.render("Press ENTER to restart", True, (200, 200, 100))
            self.screen.blit(rst, (SCREEN_WIDTH // 2 - rst.get_width() // 2,
                              SCREEN_HEIGHT // 2 + 50))
        elif gs.phase == Phase.REWARD:
            self._draw_reward(world)

        if gs.message and gs.message_timer > 0:
            m = self.f_med.render(gs.message, True, (255, 220, 80))
            self.screen.blit(m, (SCREEN_WIDTH // 2 - m.get_width() // 2, 200))

    def _draw_reward(self, world) -> None:
        self._overlay(160)
        title = self.f_large.render("REWARD — Choose a Card!", True, (255, 220, 80))
        self.screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, 120))
        cards = getattr(self.gs, "reward_cards", [])
        if not cards:
            return
        rw, rh = 160, 200
        sp = 40
        total = len(cards) * (rw + sp) - sp
        sx = (SCREEN_WIDTH - total) // 2
        for i, c in enumerate(cards):
            x = sx + i * (rw + sp)
            y = 250
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
        # Description
        words = card.description.split()
        lines, cur = [], ""
        for w in words:
            test = (cur + " " + w) if cur else w
            if self.f_tiny.size(test)[0] <= 144:
                cur = test
            else:
                lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
        for li, line in enumerate(lines[:5]):
            ls = self.f_tiny.render(line, True, TEXT_COLOR)
            self.screen.blit(ls, (x + 8, y + 60 + li * 14))
        if render:
            render.rect = (x, y, 160, 200)

    def _overlay(self, alpha) -> None:
        s = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        s.fill((10, 10, 25, alpha))
        self.screen.blit(s, (0, 0))

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

    # ── Helpers ──────────────────────────────────────────────────

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
