"""MainPanel - Main text log area showing game messages."""
from typing import List, Tuple

try:
    import pygame_ce as pygame
except ImportError:
    import pygame

from ui.panel import Panel
from ui import colors as C
from core.constants import FONT_SIZE_BODY


class MainPanel(Panel):
    """Left-side text log panel that displays game messages."""

    MAX_VISIBLE_LINES = 100
    LINE_SPACING = 2

    def __init__(self, rect: pygame.Rect) -> None:
        super().__init__(rect, bg_color=C.BG_PANEL)
        self.scroll_offset: int = 0
        self.max_scroll: int = 0
        self.font: pygame.font.Font = pygame.font.Font(None, FONT_SIZE_BODY)

    def set_font(self, font: pygame.font.Font) -> None:
        """Set the font used for rendering text."""
        self.font = font

    def _wrap_text(self, text: str, max_width: int) -> List[str]:
        """将文本按像素宽度拆分成多行。"""
        if not text:
            return [""]
        words = text.split(" ")
        lines: List[str] = []
        current_line = ""
        for word in words:
            test_line = current_line + (" " if current_line else "") + word
            test_width, _ = self.font.size(test_line)
            if test_width <= max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                # 如果单词本身超过最大宽度，逐字符拆分
                if self.font.size(word)[0] > max_width:
                    current_line = ""
                    for ch in word:
                        if self.font.size(current_line + ch)[0] <= max_width:
                            current_line += ch
                        else:
                            if current_line:
                                lines.append(current_line)
                            current_line = ch
                else:
                    current_line = word
        if current_line:
            lines.append(current_line)
        return lines if lines else [""]

    def _build_wrapped_lines(self, logs: list) -> List[Tuple[str, tuple]]:
        """将所有日志消息预计算为带颜色的换行列表。"""
        max_text_width = self.rect.width - 20  # 左右各留 8px 边距 + 滚动条预留
        wrapped: List[Tuple[str, tuple]] = []
        for msg in logs:
            color = self._get_line_color(msg)
            for line_text in self._wrap_text(msg, max_text_width):
                wrapped.append((line_text, color))
        return wrapped

    def render(self, surface: pygame.Surface, game_state) -> None:
        """Render the text log with auto-scroll and color coding."""
        super().render(surface, game_state)
        if not game_state:
            return

        logs = game_state.log
        if not logs:
            return

        line_height = self.font.get_height() + self.LINE_SPACING
        visible_lines = (self.rect.height - 8) // line_height

        # 预计算所有换行后的行
        wrapped_lines = self._build_wrapped_lines(logs)
        total_lines = len(wrapped_lines)
        self.max_scroll = max(0, total_lines - visible_lines)

        # Auto-scroll to bottom unless user has scrolled up
        if self.scroll_offset > self.max_scroll:
            self.scroll_offset = self.max_scroll

        # Determine start index
        start = max(0, total_lines - visible_lines - self.scroll_offset)
        end = min(total_lines, start + visible_lines)

        # Clip rendering to panel rect
        surface.set_clip(self.rect)

        y = self.rect.y + 4
        for i in range(start, end):
            if y + line_height > self.rect.y + self.rect.height:
                break
            line_text, color = wrapped_lines[i]
            text_surf = self.font.render(line_text, True, color)
            surface.blit(text_surf, (self.rect.x + 8, y))
            y += line_height

        surface.set_clip(None)

        # Draw scrollbar if needed
        if self.max_scroll > 0:
            self._draw_scrollbar(surface, visible_lines, total_lines)

    def _get_line_color(self, msg: str) -> tuple:
        """Determine text color based on message content."""
        if msg.startswith("===") or msg.startswith("---"):
            return C.TEXT_PRIMARY
        if msg.startswith("!") or "damage" in msg.lower() or "hits" in msg.lower():
            return C.HP_RED
        if msg.startswith("[Event]"):
            return C.NOISE_YELLOW
        if "picked up" in msg.lower() or "healed" in msg.lower() or "restored" in msg.lower():
            return C.AMMO_GREEN
        if "miss" in msg.lower():
            return C.TEXT_DIM
        if "eliminated" in msg.lower() or "killed" in msg.lower():
            return C.HP_RED
        return C.TEXT_WHITE

    def _draw_scrollbar(self, surface: pygame.Surface, visible: int, total: int) -> None:
        """Draw a minimal scrollbar on the right edge."""
        bar_height = max(20, int(self.rect.height * visible / total))
        bar_y = self.rect.y + int(
            (self.rect.height - bar_height) *
            (1.0 - self.scroll_offset / max(1, self.max_scroll))
        )
        bar_rect = pygame.Rect(
            self.rect.x + self.rect.width - 6,
            bar_y,
            4,
            bar_height,
        )
        pygame.draw.rect(surface, C.DIVIDER, bar_rect, border_radius=2)

    def handle_click(self, pos, game_state) -> bool:
        """Consume clicks within the panel area (no action)."""
        if self.rect.collidepoint(pos):
            return True
        return False

    def handle_scroll(self, dy: int) -> None:
        """Handle mouse wheel scroll. dy > 0 = scroll up, dy < 0 = scroll down."""
        self.scroll_offset = max(0, min(self.max_scroll, self.scroll_offset - dy))
