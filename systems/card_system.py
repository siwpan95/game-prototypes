import json
from pathlib import Path

import pygame
from core.ecs import System
from core.paths import ROOT
from core.utils import _load_font
from components.card_collectible import CardCollectible


class CardSystem(System):
    """卡牌系统：收集、查询、右侧只读进度面板。
    支持从 Mod 动态加载卡牌定义。"""

    PANEL_WIDTH = 160
    CARD_H = 44

    def __init__(self, screen, event_bus):
        self.screen = screen
        self.bus = event_bus
        self.font = _load_font(13)
        self.font_small = _load_font(11)

        # 加载 Base 卡牌定义
        self.cards_def = {}
        self._loaded_mods = set()  # 已加载卡牌的 mod_id 集合
        self._load_cards_from_dir(ROOT / "data" / "cards")

        # 已收集的卡牌 ID 集合
        self.collected = set()

        # 排序 ID 列表
        self._sorted_ids = list(self.cards_def.keys())

        self.bus.subscribe("CARD_COLLECTED", self._on_card_collected)

    def _load_cards_from_dir(self, cards_dir: Path):
        """从目录加载所有 .json 卡牌定义。"""
        if not cards_dir.exists():
            return
        for f in sorted(cards_dir.glob("*.json")):
            with open(f, encoding="utf-8") as fp:
                data = json.load(fp)
                cid = data["id"]
                if cid not in self.cards_def:
                    self.cards_def[cid] = data

    def load_mod_cards(self, mod):
        """加载 Mod 的卡牌定义（幂等，每个 Mod 只加载一次）。
        参数 mod 为 ModManifest 对象。"""
        if mod.mod_id in self._loaded_mods:
            return
        self._loaded_mods.add(mod.mod_id)

        cards_dir = mod.root_dir / "cards"
        if cards_dir.exists():
            self._load_cards_from_dir(cards_dir)
            self._sorted_ids = list(self.cards_def.keys())

    def init_collection(self, world):
        """扫描世界中已预收集的卡牌。"""
        for e in world.entities.values():
            cc = e.get(CardCollectible)
            if cc and cc.collected:
                self.collected.add(cc.card_id)

    def _on_card_collected(self, data):
        card_id = data["card_id"]
        self.collected.add(card_id)
        if len(self.collected) >= self.total_cards:
            self.bus.emit("GAME_WIN", {"all_collected": True})

    def has_card(self, card_id):
        return card_id in self.collected

    def get_card_def(self, card_id):
        return self.cards_def.get(card_id)

    @property
    def total_cards(self):
        return len(self.cards_def)

    @property
    def collected_count(self):
        return len(self.collected)

    def _collected_ids(self):
        return [cid for cid in self._sorted_ids if cid in self.collected]

    def update(self, world, dt):
        self._render_panel()

    def _render_panel(self):
        sw = self.screen.get_width()
        sh = self.screen.get_height()
        px = sw - self.PANEL_WIDTH
        py = 0

        panel = pygame.Surface((self.PANEL_WIDTH, sh), pygame.SRCALPHA)
        panel.fill((10, 8, 12, 220))
        pygame.draw.line(panel, (50, 45, 55), (0, 0), (0, sh), 2)

        title = self.font.render("\u25b8 卡牌收藏", True, (200, 190, 170))
        panel.blit(title, (8, 8))
        count_text = self.font_small.render(
            f"{self.collected_count}/{self.total_cards}", True, (140, 130, 120)
        )
        panel.blit(count_text, (118, 10))

        pygame.draw.line(panel, (40, 35, 45), (8, 30), (150, 30), 1)

        y = 36
        for card_id in self._sorted_ids:
            if y > sh - 20:
                break
            card_def = self.cards_def[card_id]
            collected = card_id in self.collected

            if collected:
                glyph_color = (220, 200, 150)
                name_color = (200, 190, 170)
            else:
                glyph_color = (60, 55, 65)
                name_color = (50, 45, 55)

            glyph = self.font.render(card_def["glyph"], True, glyph_color)
            panel.blit(glyph, (8, y + 10))
            name = self.font_small.render(card_def["name"], True, name_color)
            panel.blit(name, (30, y + 12))

            rarity_colors = {
                "key": (200, 160, 40), "story": (120, 140, 180),
                "secret": (180, 100, 160), "common": (100, 100, 100),
            }
            rc = rarity_colors.get(card_def.get("rarity", "common"), (100, 100, 100))
            pygame.draw.circle(panel, rc, (148, y + 20), 3)

            y += self.CARD_H

        tab_hint = self.font_small.render("Tab 设置", True, (80, 75, 85))
        panel.blit(tab_hint, (8, sh - 20))

        self.screen.blit(panel, (px, py))
