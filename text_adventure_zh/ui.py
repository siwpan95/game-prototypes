"""pygame_ce user interface layer for the puzzle game."""

from __future__ import annotations

import pygame
import sys
import time

from engine import Engine
from gameplay_pool import (
    BasePuzzle, MathPuzzle, RiddlePuzzle, CrosswordPuzzle, SudokuPuzzle,
    GuessNumberPuzzle, WordLadderPuzzle, MinesweeperPuzzle, NonogramPuzzle,
    AnagramPuzzle, MemoryPuzzle, PatternPuzzle, HangmanPuzzle, Puzzle2048,
    ColorSequencePuzzle,
)
from gameplay_pool.color_sequence import COLOR_RGB, COLOR_BRIGHT, COLOR_CN, CN_TO_EN

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
WIDTH, HEIGHT = 960, 720
FPS = 60
HEADER_H = 50
FOOTER_H = 50

# Colors
C_BG        = (30, 30, 46)
C_PANEL     = (45, 45, 65)
C_WHITE     = (235, 235, 245)
C_GRAY      = (120, 120, 145)
C_DARK      = (20, 20, 30)
C_ACCENT    = (137, 100, 234)
C_ACCENT2   = (80, 200, 170)
C_GREEN     = (80, 200, 120)
C_RED       = (220, 80, 80)
C_YELLOW    = (230, 200, 70)
C_BLUE      = (80, 140, 230)
C_ORANGE    = (230, 150, 60)
C_CELL_BG   = (55, 55, 78)
C_CELL_SEL  = (80, 70, 130)
C_BTN       = (65, 65, 95)
C_BTN_HOV   = (85, 85, 115)
C_FLAGGED   = (220, 80, 80)
C_CROSS     = (100, 100, 120)

# Puzzle-specific symbol colors for memory
SYMBOL_COLORS: dict[str, tuple] = {
    "star":  C_YELLOW,
    "heart": C_RED,
    "moon":  (180, 180, 220),
    "sun":   C_ORANGE,
    "bolt":  C_YELLOW,
    "drop":  C_BLUE,
    "leaf":  C_GREEN,
    "fire":  C_ORANGE,
    "rock":  C_GRAY,
    "wind":  (180, 200, 220),
    "snow":  C_WHITE,
    "wave":  C_BLUE,
    "gem":   C_ACCENT,
    "ring":  C_YELLOW,
    "bell":  C_ORANGE,
    "key":   C_YELLOW,
}


def _load_font(size: int) -> pygame.font.Font:
    """跨平台加载 CJK 字体 — 用 SysFont 替代硬编码路径"""
    from shared.font_utils import load_cjk_font
    return load_cjk_font(size)


# ---------------------------------------------------------------------------
# Button helper
# ---------------------------------------------------------------------------
class Button:
    def __init__(self, rect: pygame.Rect, text: str, font: pygame.font.Font,
                 color: tuple = C_BTN, hover_color: tuple = C_BTN_HOV,
                 text_color: tuple = C_WHITE, border_radius: int = 6):
        self.rect = rect
        self.text = text
        self.font = font
        self.color = color
        self.hover_color = hover_color
        self.text_color = text_color
        self.border_radius = border_radius
        self._hovered = False

    def update(self, mouse_pos: tuple[int, int]) -> None:
        self._hovered = self.rect.collidepoint(mouse_pos)

    def draw(self, surface: pygame.Surface) -> None:
        c = self.hover_color if self._hovered else self.color
        pygame.draw.rect(surface, c, self.rect, border_radius=self.border_radius)
        txt = self.font.render(self.text, True, self.text_color)
        tx = self.rect.x + (self.rect.width - txt.get_width()) // 2
        ty = self.rect.y + (self.rect.height - txt.get_height()) // 2
        surface.blit(txt, (tx, ty))

    def clicked(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            return self.rect.collidepoint(event.pos)
        return False


# ---------------------------------------------------------------------------
# Main UI class
# ---------------------------------------------------------------------------
class UI:
    def __init__(self, engine: Engine):
        self.engine = engine
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("解谜游戏")
        self.clock = pygame.time.Clock()

        self.font_lg = _load_font(32)
        self.font_md = _load_font(22)
        self.font_sm = _load_font(17)
        self.font_xs = _load_font(14)

        self.screen_state = "menu"  # menu | playing | result
        self._puzzle: BasePuzzle | None = None

        # Selections
        self._sel_row: int = -1
        self._sel_col: int = -1

        # Minesweeper right-click flag
        self._ms_first_click = True

        # Memory game mismatch delay
        self._mem_mismatch_time: float = 0.0
        self._mem_mismatch_pending = False

        # Guess number input
        self._guess_input: str = ""

        # Anagram selection
        self._anagram_sel: int = -1

        # Word ladder input
        self._wl_input: str = ""

        # Hangman state
        self._hangman_msg: str = ""
        self._hangman_msg_until: float = 0.0

        # 2048 state
        self._2048_key_cooldown: float = 0.0

        # Color sequence flash timing
        self._cs_flash_timer: float = 0.0
        self._cs_flash_index: int = -1
        self._cs_phase_shown: bool = False
        self._cs_feedback_msg: str = ""
        self._cs_feedback_until: float = 0.0
        self._last_result: dict = {}
        self._show_result_until: float = 0.0

        # Menu buttons (built in draw)
        self._menu_buttons: list[Button] = []
        self._footer_buttons: list[Button] = []
        self._puzzle_buttons: list[Button] = []

        # Mode/difficulty
        self._mode_options = ["random"]
        self._diff_options = ["easy", "medium", "hard", "random"]
        self._mode_idx = 0
        self._diff_idx = 1

    # -----------------------------------------------------------------------
    # Main loop
    # -----------------------------------------------------------------------
    def run(self) -> None:
        running = True
        while running:
            dt = self.clock.tick(FPS) / 1000.0
            events = pygame.event.get()
            for ev in events:
                if ev.type == pygame.QUIT:
                    running = False
                    break

            mouse_pos = pygame.mouse.get_pos()

            if self.screen_state == "menu":
                self._handle_menu(events, mouse_pos)
                self._draw_menu(mouse_pos)
            elif self.screen_state == "playing":
                self._handle_playing(events, mouse_pos)
                self._draw_playing(mouse_pos, dt)
            elif self.screen_state == "result":
                self._handle_result(events, mouse_pos)
                self._draw_result(mouse_pos)

            pygame.display.flip()

        pygame.quit()
        sys.exit()

    # -----------------------------------------------------------------------
    # Menu
    # -----------------------------------------------------------------------
    def _build_menu_buttons(self) -> None:
        cx = WIDTH // 2
        self._menu_buttons = []

        # Mode selector
        y = 250
        for i, mode in enumerate(self._mode_options):
            mode_map = {
                "content_heavy": "内容为主",
                "balanced": "均衡模式",
                "generated_heavy": "生成为主",
                "random": "随机",
            }
            label = mode_map.get(mode, mode)
            if i == self._mode_idx:
                label = f"[ {label} ]"
            btn = Button(pygame.Rect(cx - 140, y + i * 44, 280, 38), label, self.font_sm,
                         color=C_ACCENT if i == self._mode_idx else C_BTN)
            self._menu_buttons.append(("mode", i, btn))

        # Difficulty selector
        y = 470
        for i, diff in enumerate(self._diff_options):
            diff_map = {
                "easy": "简单",
                "medium": "中等",
                "hard": "困难",
                "random": "随机",
            }
            label = diff_map.get(diff, diff)
            if i == self._diff_idx:
                label = f"[ {label} ]"
            btn = Button(pygame.Rect(cx - 140, y + i * 40, 280, 34), label, self.font_sm,
                         color=C_ACCENT2 if i == self._diff_idx else C_BTN)
            self._menu_buttons.append(("diff", i, btn))

        # Start & Quit buttons
        btn_start = Button(pygame.Rect(cx - 160, 640, 140, 48), "开始", self.font_md,
                           color=C_GREEN, hover_color=(100, 220, 140))
        self._menu_buttons.append(("start", 0, btn_start))
        btn_quit = Button(pygame.Rect(cx + 20, 640, 140, 48), "退出", self.font_md,
                          color=C_RED, hover_color=(240, 100, 100))
        self._menu_buttons.append(("quit", 0, btn_quit))

    def _handle_menu(self, events: list, mouse_pos: tuple) -> None:
        for btn_type, idx, btn in self._menu_buttons:
            btn.update(mouse_pos)
        for ev in events:
            for btn_type, idx, btn in self._menu_buttons:
                if btn.clicked(ev):
                    if btn_type == "mode":
                        self._mode_idx = idx
                    elif btn_type == "diff":
                        self._diff_idx = idx
                    elif btn_type == "start":
                        mode = self._mode_options[self._mode_idx]
                        diff = self._diff_options[self._diff_idx]
                        self.engine.reset()
                        self.engine.configure(mode, diff)
                        self._start_puzzle()
                    elif btn_type == "quit":
                        pygame.event.post(pygame.event.Event(pygame.QUIT))

    def _draw_menu(self, mouse_pos: tuple) -> None:
        self.screen.fill(C_BG)
        self._build_menu_buttons()

        title = self.font_lg.render("解谜游戏", True, C_ACCENT)
        self.screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 60))

        sub = self.font_sm.render("脑筋急转弯合集", True, C_GRAY)
        self.screen.blit(sub, (WIDTH // 2 - sub.get_width() // 2, 105))

        # Section labels
        ml = self.font_md.render("模式", True, C_WHITE)
        self.screen.blit(ml, (WIDTH // 2 - ml.get_width() // 2, 218))
        dl = self.font_md.render("难度", True, C_WHITE)
        self.screen.blit(dl, (WIDTH // 2 - dl.get_width() // 2, 440))

        for _, _, btn in self._menu_buttons:
            btn.draw(self.screen)

    # -----------------------------------------------------------------------
    # Start / next puzzle
    # -----------------------------------------------------------------------
    def _start_puzzle(self) -> None:
        self._puzzle = self.engine.start_new_puzzle()
        self._sel_row = -1
        self._sel_col = -1
        self._ms_first_click = True
        self._mem_mismatch_pending = False
        self._guess_input = ""
        self._anagram_sel = -1
        self._wl_input = ""
        self._hangman_msg = ""
        self._hangman_msg_until = 0.0
        self._2048_key_cooldown = 0.0
        self._cs_flash_timer = 0.0
        self._cs_flash_index = -1
        self._cs_phase_shown = False
        self._cs_feedback_msg = ""
        self._cs_feedback_until = 0.0
        self.screen_state = "playing"

    # -----------------------------------------------------------------------
    # Playing screen — dispatch
    # -----------------------------------------------------------------------
    def _handle_playing(self, events: list, mouse_pos: tuple) -> None:
        # Handle memory mismatch delay
        if self._mem_mismatch_pending and time.time() - self._mem_mismatch_time > 0.8:
            if isinstance(self._puzzle, MemoryPuzzle):
                self._puzzle.hide_unmatched()
            self._mem_mismatch_pending = False

        for btn in self._footer_buttons:
            btn.update(mouse_pos)

        # Footer buttons
        for ev in events:
            for btn in self._footer_buttons:
                if btn.clicked(ev):
                    if btn.text == "提示":
                        self._show_hint_popup()
                    elif btn.text == "跳过":
                        self.engine.skip_puzzle()
                        self._start_puzzle()
                        return
                    elif btn.text == "菜单":
                        self.screen_state = "menu"
                        return
                    elif btn.text == "下一题":
                        self._start_puzzle()
                        return

        if isinstance(self._puzzle, MathPuzzle):
            self._handle_math(events, mouse_pos)
        elif isinstance(self._puzzle, RiddlePuzzle):
            self._handle_riddle(events, mouse_pos)
        elif isinstance(self._puzzle, CrosswordPuzzle):
            self._handle_crossword(events, mouse_pos)
        elif isinstance(self._puzzle, SudokuPuzzle):
            self._handle_sudoku(events, mouse_pos)
        elif isinstance(self._puzzle, GuessNumberPuzzle):
            self._handle_guess_number(events, mouse_pos)
        elif isinstance(self._puzzle, WordLadderPuzzle):
            self._handle_word_ladder(events, mouse_pos)
        elif isinstance(self._puzzle, MinesweeperPuzzle):
            self._handle_minesweeper(events, mouse_pos)
        elif isinstance(self._puzzle, NonogramPuzzle):
            self._handle_nonogram(events, mouse_pos)
        elif isinstance(self._puzzle, AnagramPuzzle):
            self._handle_anagram(events, mouse_pos)
        elif isinstance(self._puzzle, MemoryPuzzle):
            self._handle_memory(events, mouse_pos)
        elif isinstance(self._puzzle, PatternPuzzle):
            self._handle_pattern(events, mouse_pos)
        elif isinstance(self._puzzle, HangmanPuzzle):
            self._handle_hangman(events, mouse_pos)
        elif isinstance(self._puzzle, Puzzle2048):
            self._handle_2048(events, mouse_pos)
        elif isinstance(self._puzzle, ColorSequencePuzzle):
            self._handle_color_sequence(events, mouse_pos)

        # Update puzzle-specific buttons
        for btn in self._puzzle_buttons:
            btn.update(mouse_pos)

    def _show_hint_popup(self) -> None:
        hint = self.engine.get_hint()
        self._show_result_until = time.time() + 3.0
        self._last_result = {"hint": hint}

    # -----------------------------------------------------------------------
    # Drawing helpers
    # -----------------------------------------------------------------------
    def _draw_header(self) -> None:
        pygame.draw.rect(self.screen, C_PANEL, (0, 0, WIDTH, HEADER_H))
        if self._puzzle:
            name = self._puzzle.puzzle_name
        else:
            name = ""
        txt = self.font_md.render(f"  {name}", True, C_ACCENT)
        self.screen.blit(txt, (10, 12))

        score_txt = self.font_sm.render(
            f"分数: {self.engine.state.score}  连胜: {self.engine.state.streak}", True, C_WHITE
        )
        self.screen.blit(score_txt, (WIDTH - score_txt.get_width() - 15, 15))

        elapsed = int(self.engine.elapsed)
        time_txt = self.font_sm.render(f"用时: {elapsed}秒", True, C_GRAY)
        self.screen.blit(time_txt, (WIDTH // 2 - time_txt.get_width() // 2, 15))

    def _build_footer(self) -> None:
        self._footer_buttons = []
        labels = ["菜单", "提示", "跳过", "下一题"]
        bw = 100
        gap = 20
        total = len(labels) * bw + (len(labels) - 1) * gap
        sx = (WIDTH - total) // 2
        for i, label in enumerate(labels):
            r = pygame.Rect(sx + i * (bw + gap), HEIGHT - FOOTER_H + 8, bw, 34)
            self._footer_buttons.append(Button(r, label, self.font_sm))

    def _draw_footer(self) -> None:
        pygame.draw.rect(self.screen, C_PANEL, (0, HEIGHT - FOOTER_H, WIDTH, FOOTER_H))
        self._build_footer()
        for btn in self._footer_buttons:
            btn.draw(self.screen)

    def _draw_grid(self, rows: int, cols: int, cell_size: int,
                   offset_x: int, offset_y: int,
                   cell_data_fn, border_color: tuple = C_GRAY) -> None:
        """Generic grid drawer. cell_data_fn(r,c) -> dict with 'text','bg','fg' keys."""
        for r in range(rows):
            for c in range(cols):
                x = offset_x + c * cell_size
                y = offset_y + r * cell_size
                info = cell_data_fn(r, c)
                bg = info.get("bg", C_CELL_BG)
                fg = info.get("fg", C_WHITE)
                text = info.get("text", "")
                rect = pygame.Rect(x, y, cell_size - 1, cell_size - 1)
                pygame.draw.rect(self.screen, bg, rect, border_radius=3)

                if text:
                    rendered = self.font_sm.render(str(text), True, fg)
                    tx = x + (cell_size - 1 - rendered.get_width()) // 2
                    ty = y + (cell_size - 1 - rendered.get_height()) // 2
                    self.screen.blit(rendered, (tx, ty))

                if r == self._sel_row and c == self._sel_col:
                    pygame.draw.rect(self.screen, C_ACCENT, rect, width=2, border_radius=3)

    def _draw_playing(self, mouse_pos: tuple, dt: float) -> None:
        self.screen.fill(C_BG)
        self._draw_header()
        self._draw_footer()

        # Hint / feedback bar — placed just above the footer hint button
        if self._last_result.get("hint") and time.time() < self._show_result_until:
            hint = self._last_result["hint"]
            surf = self.font_md.render(f"提示: {hint}", True, C_YELLOW)
            bx = WIDTH // 2 - surf.get_width() // 2 - 10
            by = HEIGHT - FOOTER_H - 46
            pygame.draw.rect(self.screen, C_DARK, (bx, by, surf.get_width() + 20, 36),
                             border_radius=8)
            self.screen.blit(surf, (bx + 10, by + 6))

        # Draw puzzle-specific UI
        puzzle = self._puzzle
        if isinstance(puzzle, MathPuzzle):
            self._draw_math(puzzle)
        elif isinstance(puzzle, RiddlePuzzle):
            self._draw_riddle(puzzle)
        elif isinstance(puzzle, CrosswordPuzzle):
            self._draw_crossword(puzzle)
        elif isinstance(puzzle, SudokuPuzzle):
            self._draw_sudoku(puzzle)
        elif isinstance(puzzle, GuessNumberPuzzle):
            self._draw_guess_number(puzzle)
        elif isinstance(puzzle, WordLadderPuzzle):
            self._draw_word_ladder(puzzle)
        elif isinstance(puzzle, MinesweeperPuzzle):
            self._draw_minesweeper(puzzle)
        elif isinstance(puzzle, NonogramPuzzle):
            self._draw_nonogram(puzzle)
        elif isinstance(puzzle, AnagramPuzzle):
            self._draw_anagram(puzzle)
        elif isinstance(puzzle, MemoryPuzzle):
            self._draw_memory(puzzle)
        elif isinstance(puzzle, PatternPuzzle):
            self._draw_pattern(puzzle)
        elif isinstance(puzzle, HangmanPuzzle):
            self._draw_hangman(puzzle)
        elif isinstance(puzzle, Puzzle2048):
            self._draw_2048(puzzle)
        elif isinstance(puzzle, ColorSequencePuzzle):
            self._draw_color_sequence(puzzle)

        for btn in self._puzzle_buttons:
            btn.draw(self.screen)

    # -----------------------------------------------------------------------
    # Result screen
    # -----------------------------------------------------------------------
    def _handle_result(self, events: list, mouse_pos: tuple) -> None:
        for ev in events:
            if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                self._start_puzzle()

    def _draw_result(self, mouse_pos: tuple) -> None:
        self.screen.fill(C_BG)
        r = self._last_result
        correct = r.get("correct", False)
        msg = "正确!" if correct else "错误!"
        color = C_GREEN if correct else C_RED

        txt = self.font_lg.render(msg, True, color)
        self.screen.blit(txt, (WIDTH // 2 - txt.get_width() // 2, 200))

        if correct:
            pts = r.get("points", 0)
            pt = self.font_md.render(f"+{pts} 分", True, C_YELLOW)
            self.screen.blit(pt, (WIDTH // 2 - pt.get_width() // 2, 280))
            tb = r.get("time_bonus", 0)
            sb = r.get("streak_bonus", 0)
            detail = self.font_sm.render(f"时间加成: +{tb}  连胜加成: +{sb}", True, C_GRAY)
            self.screen.blit(detail, (WIDTH // 2 - detail.get_width() // 2, 320))

        cont = self.font_md.render("点击任意位置继续", True, C_GRAY)
        self.screen.blit(cont, (WIDTH // 2 - cont.get_width() // 2, 450))

    def _show_result(self, result: dict) -> None:
        self._last_result = result
        self.screen_state = "result"

    # -----------------------------------------------------------------------
    # Math Puzzle
    # -----------------------------------------------------------------------
    def _handle_math(self, events: list, mouse_pos: tuple) -> None:
        for ev in events:
            for btn in self._puzzle_buttons:
                if btn.clicked(ev):
                    digit = btn.text
                    if digit == "删除":
                        self._guess_input = self._guess_input[:-1]
                    elif digit == "确定":
                        if self._guess_input:
                            result = self.engine.submit_answer(int(self._guess_input))
                            if result.get("correct") or self._puzzle is None:
                                self._show_result(result)
                                return
                            else:
                                self._guess_input = ""
                                self._show_hint_inline("错误！再试一次。")
                    else:
                        if len(self._guess_input) < 6:
                            self._guess_input += digit

    def _show_hint_inline(self, msg: str) -> None:
        self._last_result = {"hint": msg}
        self._show_result_until = time.time() + 2.0

    def _draw_math(self, puzzle: MathPuzzle) -> None:
        expr = puzzle.data["expression"]
        txt = self.font_lg.render(f"{expr} = ?", True, C_WHITE)
        self.screen.blit(txt, (WIDTH // 2 - txt.get_width() // 2, 100))

        inp = self.font_md.render(self._guess_input or "_", True, C_ACCENT)
        self.screen.blit(inp, (WIDTH // 2 - inp.get_width() // 2, 170))

        # Number pad
        self._puzzle_buttons = []
        keys = [str(i) for i in range(10)] + ["删除", "确定"]
        cols = 4
        bw, bh = 70, 50
        gap = 8
        sx = WIDTH // 2 - (cols * (bw + gap) - gap) // 2
        sy = 240
        for i, key in enumerate(keys):
            r, c = divmod(i, cols)
            rect = pygame.Rect(sx + c * (bw + gap), sy + r * (bh + gap), bw, bh)
            color = C_RED if key == "删除" else C_GREEN if key == "确定" else C_BTN
            self._puzzle_buttons.append(Button(rect, key, self.font_md, color=color))

    # -----------------------------------------------------------------------
    # Riddle Puzzle
    # -----------------------------------------------------------------------
    def _handle_riddle(self, events: list, mouse_pos: tuple) -> None:
        for ev in events:
            for i, btn in enumerate(self._puzzle_buttons):
                if btn.clicked(ev):
                    result = self.engine.submit_answer(i)
                    self._show_result(result)
                    return

    def _draw_riddle(self, puzzle: RiddlePuzzle) -> None:
        q = puzzle.data["question"]
        # Word-wrap question
        words = q.split()
        lines: list[str] = []
        line = ""
        for w in words:
            test = f"{line} {w}" if line else w
            if self.font_sm.size(test)[0] > WIDTH - 80:
                lines.append(line)
                line = w
            else:
                line = test
        if line:
            lines.append(line)

        y = 80
        for ln in lines:
            t = self.font_sm.render(ln, True, C_WHITE)
            self.screen.blit(t, (40, y))
            y += 26

        self._puzzle_buttons = []
        options = puzzle.data["options"]
        bw = 400
        bh = 44
        sy = y + 20
        for i, opt in enumerate(options):
            rect = pygame.Rect(WIDTH // 2 - bw // 2, sy + i * (bh + 10), bw, bh)
            self._puzzle_buttons.append(Button(rect, opt, self.font_sm))

    # -----------------------------------------------------------------------
    # Crossword Puzzle
    # -----------------------------------------------------------------------
    def _handle_crossword(self, events: list, mouse_pos: tuple) -> None:
        puzzle = self._puzzle
        assert isinstance(puzzle, CrosswordPuzzle)
        size = puzzle.data["size"]
        cell_sz = 38
        ox = WIDTH // 2 - size * cell_sz // 2
        oy = 130

        for ev in events:
            if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                mx, my = ev.pos
                for r in range(size):
                    for c in range(size):
                        x = ox + c * cell_sz
                        y = oy + r * cell_sz
                        if x <= mx < x + cell_sz and y <= my < y + cell_sz:
                            if puzzle.data["grid"][r][c] is not None:
                                self._sel_row = r
                                self._sel_col = c

            if ev.type == pygame.KEYDOWN and self._sel_row >= 0:
                if ev.key == pygame.K_BACKSPACE:
                    puzzle.set_cell(self._sel_row, self._sel_col, "")
                elif ev.unicode.isalpha() and len(ev.unicode) == 1:
                    puzzle.set_cell(self._sel_row, self._sel_col, ev.unicode.upper())

            # Check button — handle inside the event loop
            if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                for btn in self._puzzle_buttons:
                    if btn.clicked(ev):
                        if btn.text == "检查":
                            correct = puzzle.check_answer(None)
                            if correct:
                                result = self.engine.submit_answer(None)
                                self._show_result(result)
                            else:
                                self._show_hint_inline("还没完全正确！")

    def _draw_crossword(self, puzzle: CrosswordPuzzle) -> None:
        size = puzzle.data["size"]
        cell_sz = 38
        ox = WIDTH // 2 - size * cell_sz // 2
        oy = 130

        def cell_fn(r, c):
            if puzzle.data["grid"][r][c] is None:
                return {"text": "", "bg": C_DARK, "fg": C_DARK}
            player = puzzle.data["player_grid"][r][c]
            num_key = (r, c)
            num = puzzle.data["numbers"].get(num_key, "")
            txt = player if player else ""
            return {"text": txt, "bg": C_CELL_BG, "fg": C_WHITE}

        self._draw_grid(size, size, cell_sz, ox, oy, cell_fn)

        # Draw numbers
        for (r, c), num in puzzle.data["numbers"].items():
            x = ox + c * cell_sz + 3
            y = oy + r * cell_sz + 1
            nt = self.font_xs.render(str(num), True, C_ACCENT2)
            self.screen.blit(nt, (x, y))

        # Clues
        clues_y = oy + size * cell_sz + 15
        self.screen.blit(self.font_sm.render("横向", True, C_ACCENT), (40, clues_y))
        for i, clue in enumerate(puzzle.data["clues_across"]):
            ct = self.font_xs.render(clue, True, C_WHITE)
            self.screen.blit(ct, (50, clues_y + 22 + i * 18))

        cx = WIDTH // 2 + 20
        self.screen.blit(self.font_sm.render("纵向", True, C_ACCENT2), (cx, clues_y))
        for i, clue in enumerate(puzzle.data["clues_down"]):
            ct = self.font_xs.render(clue, True, C_WHITE)
            self.screen.blit(ct, (cx + 10, clues_y + 22 + i * 18))

        self._puzzle_buttons = [
            Button(pygame.Rect(WIDTH - 140, HEADER_H + 10, 100, 36), "检查", self.font_sm,
                   color=C_GREEN)
        ]

    # -----------------------------------------------------------------------
    # Sudoku Puzzle
    # -----------------------------------------------------------------------
    def _handle_sudoku(self, events: list, mouse_pos: tuple) -> None:
        puzzle = self._puzzle
        assert isinstance(puzzle, SudokuPuzzle)
        size = puzzle.data["size"]
        cell_sz = min(44, (HEIGHT - HEADER_H - FOOTER_H - 60) // size)
        ox = WIDTH // 2 - size * cell_sz // 2
        oy = HEADER_H + 20

        for ev in events:
            if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                mx, my = ev.pos
                # Grid click
                for r in range(size):
                    for c in range(size):
                        x = ox + c * cell_sz
                        y = oy + r * cell_sz
                        if x <= mx < x + cell_sz and y <= my < y + cell_sz:
                            if puzzle.data["puzzle"][r][c] == 0:
                                self._sel_row = r
                                self._sel_col = c

                # Number buttons
                for btn in self._puzzle_buttons:
                    if btn.clicked(ev):
                        if btn.text == "检查":
                            correct = puzzle.check_answer(None)
                            if correct:
                                result = self.engine.submit_answer(None)
                                self._show_result(result)
                            else:
                                self._show_hint_inline("尚未完成！")
                        elif self._sel_row >= 0 and btn.text.isdigit():
                            puzzle.set_cell(self._sel_row, self._sel_col, int(btn.text))

    def _draw_sudoku(self, puzzle: SudokuPuzzle) -> None:
        size = puzzle.data["size"]
        box_h, box_w = puzzle.data["box_h"], puzzle.data["box_w"]
        cell_sz = min(44, (HEIGHT - HEADER_H - FOOTER_H - 80) // size)
        ox = WIDTH // 2 - size * cell_sz // 2
        oy = HEADER_H + 20

        def cell_fn(r, c):
            val = puzzle.data["player_grid"][r][c]
            if val == 0:
                txt = ""
            else:
                txt = str(val)
            is_given = puzzle.data["puzzle"][r][c] != 0
            bg = (50, 50, 68) if is_given else C_CELL_BG
            fg = C_WHITE if is_given else C_ACCENT
            return {"text": txt, "bg": bg, "fg": fg}

        self._draw_grid(size, size, cell_sz, ox, oy, cell_fn)

        # Draw box borders
        for br in range(size // box_h):
            for bc in range(size // box_w):
                rx = ox + bc * box_w * cell_sz - 1
                ry = oy + br * box_h * cell_sz - 1
                rw = box_w * cell_sz + 1
                rh = box_h * cell_sz + 1
                pygame.draw.rect(self.screen, C_ACCENT2,
                                 (rx, ry, rw, rh), width=2, border_radius=1)

        # Number buttons
        self._puzzle_buttons = []
        nums = list(range(1, size + 1)) + [0]
        btn_sz = 36
        gap = 4
        total_w = len(nums) * (btn_sz + gap) - gap
        sx = WIDTH // 2 - total_w // 2
        sy = oy + size * cell_sz + 15
        for i, n in enumerate(nums):
            label = str(n) if n != 0 else "X"
            rect = pygame.Rect(sx + i * (btn_sz + gap), sy, btn_sz, btn_sz)
            self._puzzle_buttons.append(Button(rect, label, self.font_sm))

        # Check button
        cb = Button(pygame.Rect(WIDTH - 140, HEADER_H + 10, 100, 36), "检查", self.font_sm,
                    color=C_GREEN)
        self._puzzle_buttons.append(cb)

    # -----------------------------------------------------------------------
    # Guess Number Puzzle
    # -----------------------------------------------------------------------
    def _handle_guess_number(self, events: list, mouse_pos: tuple) -> None:
        puzzle = self._puzzle
        assert isinstance(puzzle, GuessNumberPuzzle)

        for ev in events:
            for btn in self._puzzle_buttons:
                if btn.clicked(ev):
                    if btn.text == "确定":
                        if self._guess_input:
                            result = self.engine.submit_answer(int(self._guess_input))
                            if result.get("correct"):
                                self._show_result(result)
                                return
                            else:
                                self._guess_input = ""
                                hint = puzzle.data["last_hint"]
                                self._show_hint_inline(hint)
                                if "次数用完了" in hint:
                                    self.engine.skip_puzzle()
                                    self._show_result({"correct": False})
                                    return
                    elif btn.text == "删除":
                        self._guess_input = self._guess_input[:-1]
                    else:
                        if len(self._guess_input) < 6:
                            self._guess_input += btn.text

    def _draw_guess_number(self, puzzle: GuessNumberPuzzle) -> None:
        data = puzzle.data
        t = self.font_md.render(
            f"猜一个 {data['low']} 到 {data['high']} 之间的数字", True, C_WHITE
        )
        self.screen.blit(t, (WIDTH // 2 - t.get_width() // 2, 80))

        attempts = self.font_sm.render(
            f"尝试次数: {data['attempts']}/{data['max_attempts']}", True, C_GRAY
        )
        self.screen.blit(attempts, (WIDTH // 2 - attempts.get_width() // 2, 120))

        # Visual range bar
        bar_x, bar_y, bar_w, bar_h = 120, 180, WIDTH - 240, 30
        pygame.draw.rect(self.screen, C_CELL_BG, (bar_x, bar_y, bar_w, bar_h), border_radius=6)
        low, high = data["low"], data["high"]
        rng = high - low + 1
        if rng > 0:
            fill_x = bar_x + int((data["low"] - low) / max(rng, 1) * bar_w)
            fill_w = int((data["high"] - data["low"] + 1) / max(rng, 1) * bar_w)
            pygame.draw.rect(self.screen, C_ACCENT, (fill_x, bar_y, fill_w, bar_h), border_radius=6)

        rng_txt = self.font_xs.render(f"{data['low']} — {data['high']}", True, C_WHITE)
        self.screen.blit(rng_txt, (WIDTH // 2 - rng_txt.get_width() // 2, bar_y + bar_h + 4))

        # Guess history
        y = 240
        for g in data["guesses"]:
            gt = self.font_sm.render(f"已猜: {g}", True, C_GRAY)
            self.screen.blit(gt, (WIDTH // 2 - gt.get_width() // 2, y))
            y += 22

        if data["last_hint"]:
            ht = self.font_md.render(data["last_hint"], True, C_YELLOW)
            self.screen.blit(ht, (WIDTH // 2 - ht.get_width() // 2, y + 10))

        # Input
        inp = self.font_md.render(self._guess_input or "_", True, C_ACCENT)
        self.screen.blit(inp, (WIDTH // 2 - inp.get_width() // 2, y + 50))

        # Number pad
        self._puzzle_buttons = []
        keys = [str(i) for i in range(10)] + ["删除", "确定"]
        cols = 4
        bw, bh = 70, 50
        gap = 8
        sx = WIDTH // 2 - (cols * (bw + gap) - gap) // 2
        sy = y + 90
        for i, key in enumerate(keys):
            r, c = divmod(i, cols)
            rect = pygame.Rect(sx + c * (bw + gap), sy + r * (bh + gap), bw, bh)
            color = C_RED if key == "删除" else C_GREEN if key == "确定" else C_BTN
            self._puzzle_buttons.append(Button(rect, key, self.font_md, color=color))

    # -----------------------------------------------------------------------
    # Word Ladder Puzzle
    # -----------------------------------------------------------------------
    def _handle_word_ladder(self, events: list, mouse_pos: tuple) -> None:
        puzzle = self._puzzle
        assert isinstance(puzzle, WordLadderPuzzle)

        for ev in events:
            if ev.type == pygame.KEYDOWN and ev.unicode.isalpha() and len(ev.unicode) == 1:
                self._wl_input += ev.unicode.lower()
            elif ev.type == pygame.KEYDOWN and ev.key == pygame.K_BACKSPACE:
                self._wl_input = self._wl_input[:-1]
            elif ev.type == pygame.KEYDOWN and ev.key == pygame.K_RETURN:
                if self._wl_input:
                    valid = puzzle.set_step(self._wl_input)
                    if valid:
                        self._wl_input = ""
                        if puzzle.check_answer(None):
                            result = self.engine.submit_answer(None)
                            self._show_result(result)
                            return
                    else:
                        self._show_hint_inline("无效步骤！必须改变一个字母。")
                        self._wl_input = ""

            for btn in self._puzzle_buttons:
                if btn.clicked(ev):
                    if btn.text == "提交":
                        if self._wl_input:
                            valid = puzzle.set_step(self._wl_input)
                            if valid:
                                self._wl_input = ""
                                if puzzle.check_answer(None):
                                    result = self.engine.submit_answer(None)
                                    self._show_result(result)
                                    return
                            else:
                                self._show_hint_inline("无效步骤！")
                                self._wl_input = ""
                    elif btn.text == "撤销":
                        path = puzzle.data["player_path"]
                        if len(path) > 1:
                            path.pop()
                            self._wl_input = ""

    def _draw_word_ladder(self, puzzle: WordLadderPuzzle) -> None:
        data = puzzle.data
        t = self.font_md.render(
            f"变换 '{data['start'].upper()}' → '{data['end'].upper()}'", True, C_WHITE
        )
        self.screen.blit(t, (WIDTH // 2 - t.get_width() // 2, 70))

        # Show player path
        y = 130
        for i, word in enumerate(data["player_path"]):
            color = C_ACCENT2 if i == 0 else C_ACCENT if word == data["end"] else C_WHITE
            wt = self.font_md.render(word.upper(), True, color)
            self.screen.blit(wt, (WIDTH // 2 - wt.get_width() // 2, y))
            y += 36
            if i < len(data["player_path"]) - 1:
                arrow = self.font_sm.render("|", True, C_GRAY)
                self.screen.blit(arrow, (WIDTH // 2 - arrow.get_width() // 2, y - 10))

        # Input
        inp_label = self.font_sm.render("输入下一个单词后按回车:", True, C_GRAY)
        self.screen.blit(inp_label, (WIDTH // 2 - inp_label.get_width() // 2, y + 20))
        inp = self.font_md.render(self._wl_input or "_", True, C_ACCENT)
        self.screen.blit(inp, (WIDTH // 2 - inp.get_width() // 2, y + 50))

        self._puzzle_buttons = [
            Button(pygame.Rect(WIDTH // 2 - 120, y + 90, 100, 36), "提交", self.font_sm,
                   color=C_GREEN),
            Button(pygame.Rect(WIDTH // 2 + 20, y + 90, 100, 36), "撤销", self.font_sm,
                   color=C_ORANGE),
        ]

    # -----------------------------------------------------------------------
    # Minesweeper Puzzle
    # -----------------------------------------------------------------------
    def _handle_minesweeper(self, events: list, mouse_pos: tuple) -> None:
        puzzle = self._puzzle
        assert isinstance(puzzle, MinesweeperPuzzle)
        rows, cols = puzzle.data["rows"], puzzle.data["cols"]
        cell_sz = min(36, (HEIGHT - HEADER_H - FOOTER_H - 30) // rows,
                      (WIDTH - 40) // cols)
        ox = WIDTH // 2 - cols * cell_sz // 2
        oy = HEADER_H + 15

        for ev in events:
            if ev.type == pygame.MOUSEBUTTONDOWN:
                mx, my = ev.pos
                for r in range(rows):
                    for c in range(cols):
                        x = ox + c * cell_sz
                        y = oy + r * cell_sz
                        if x <= mx < x + cell_sz and y <= my < y + cell_sz:
                            if ev.button == 1:  # left click - reveal
                                if self._ms_first_click:
                                    puzzle.ensure_safe_first_click(r, c)
                                    self._ms_first_click = False
                                puzzle.reveal(r, c)
                                if puzzle.data["game_over"]:
                                    self._show_hint_inline("轰！游戏结束！")
                                    self.engine.skip_puzzle()
                                elif puzzle.data["win"]:
                                    result = self.engine.submit_answer(None)
                                    self._show_result(result)
                            elif ev.button == 3:  # right click - flag
                                puzzle.toggle_flag(r, c)

    def _draw_minesweeper(self, puzzle: MinesweeperPuzzle) -> None:
        rows, cols = puzzle.data["rows"], puzzle.data["cols"]
        cell_sz = min(36, (HEIGHT - HEADER_H - FOOTER_H - 30) // rows,
                      (WIDTH - 40) // cols)
        ox = WIDTH // 2 - cols * cell_sz // 2
        oy = HEADER_H + 15

        mine_colors = {
            1: C_BLUE, 2: C_GREEN, 3: C_RED, 4: C_ACCENT,
            5: C_ORANGE, 6: C_ACCENT2, 7: C_DARK, 8: C_GRAY
        }

        def cell_fn(r, c):
            if puzzle.data["flagged"][r][c] and not puzzle.data["revealed"][r][c]:
                return {"text": "F", "bg": C_FLAGGED, "fg": C_WHITE}
            if not puzzle.data["revealed"][r][c]:
                return {"text": "", "bg": C_CELL_BG, "fg": C_WHITE}
            val = puzzle.data["grid"][r][c]
            if val == -1:
                return {"text": "*", "bg": C_RED, "fg": C_WHITE}
            elif val == 0:
                return {"text": "", "bg": C_DARK, "fg": C_WHITE}
            else:
                return {"text": str(val), "bg": C_DARK, "fg": mine_colors.get(val, C_WHITE)}

        self._draw_grid(rows, cols, cell_sz, ox, oy, cell_fn)

        mines_left = puzzle.data["mines"] - sum(
            1 for r in range(rows) for c in range(cols) if puzzle.data["flagged"][r][c]
        )
        mt = self.font_sm.render(f"剩余地雷: {mines_left}", True, C_WHITE)
        self.screen.blit(mt, (WIDTH // 2 - mt.get_width() // 2, oy + rows * cell_sz + 8))

        self._puzzle_buttons = []

    # -----------------------------------------------------------------------
    # Nonogram Puzzle
    # -----------------------------------------------------------------------
    def _handle_nonogram(self, events: list, mouse_pos: tuple) -> None:
        puzzle = self._puzzle
        assert isinstance(puzzle, NonogramPuzzle)
        size = puzzle.data["size"]
        cell_sz = min(36, (HEIGHT - HEADER_H - FOOTER_H - 60) // (size + 4),
                      (WIDTH - 200) // (size + 4))
        clue_offset = 4  # max clue rows/cols
        ox = 100 + clue_offset * cell_sz
        oy = HEADER_H + 20 + clue_offset * cell_sz

        for ev in events:
            if ev.type == pygame.MOUSEBUTTONDOWN:
                mx, my = ev.pos
                for r in range(size):
                    for c in range(size):
                        x = ox + c * cell_sz
                        y = oy + r * cell_sz
                        if x <= mx < x + cell_sz and y <= my < y + cell_sz:
                            puzzle.toggle_cell(r, c)

            for btn in self._puzzle_buttons:
                if btn.clicked(ev):
                    if btn.text == "检查":
                        if puzzle.check_answer(None):
                            result = self.engine.submit_answer(None)
                            self._show_result(result)
                        else:
                            self._show_hint_inline("不太对！")

    def _draw_nonogram(self, puzzle: NonogramPuzzle) -> None:
        size = puzzle.data["size"]
        cell_sz = min(36, (HEIGHT - HEADER_H - FOOTER_H - 60) // (size + 4),
                      (WIDTH - 200) // (size + 4))
        clue_offset = 4
        ox = 100 + clue_offset * cell_sz
        oy = HEADER_H + 20 + clue_offset * cell_sz

        def cell_fn(r, c):
            state = puzzle.data["player_grid"][r][c]
            if state == 1:
                return {"text": "", "bg": C_ACCENT, "fg": C_ACCENT}
            elif state == 2:
                return {"text": "X", "bg": C_DARK, "fg": C_CROSS}
            return {"text": "", "bg": C_CELL_BG, "fg": C_WHITE}

        self._draw_grid(size, size, cell_sz, ox, oy, cell_fn)

        # Row clues
        for r in range(size):
            clues = puzzle.data["row_clues"]
            clue_str = " ".join(str(x) for x in clues[r])
            ct = self.font_xs.render(clue_str, True, C_WHITE)
            self.screen.blit(ct, (ox - ct.get_width() - 4, oy + r * cell_sz + cell_sz // 4))

        # Col clues
        for c in range(size):
            clues = puzzle.data["col_clues"]
            for i, v in enumerate(reversed(clues[c])):
                ct = self.font_xs.render(str(v), True, C_WHITE)
                self.screen.blit(ct, (ox + c * cell_sz + cell_sz // 4,
                                      oy - (i + 1) * (cell_sz - 2)))

        self._puzzle_buttons = [
            Button(pygame.Rect(WIDTH - 140, HEADER_H + 10, 100, 36), "检查", self.font_sm,
                   color=C_GREEN)
        ]

    # -----------------------------------------------------------------------
    # Anagram Puzzle
    # -----------------------------------------------------------------------
    def _handle_anagram(self, events: list, mouse_pos: tuple) -> None:
        puzzle = self._puzzle
        assert isinstance(puzzle, AnagramPuzzle)

        for ev in events:
            if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                # Click on letter cards
                letters = puzzle.data["player_letters"]
                card_w = 52
                gap = 10
                total = len(letters) * (card_w + gap) - gap
                sx = WIDTH // 2 - total // 2
                sy = 200
                for i in range(len(letters)):
                    x = sx + i * (card_w + gap)
                    rect = pygame.Rect(x, sy, card_w, 60)
                    if rect.collidepoint(ev.pos):
                        if self._anagram_sel == -1:
                            self._anagram_sel = i
                        else:
                            puzzle.swap_letters(self._anagram_sel, i)
                            self._anagram_sel = -1

            for btn in self._puzzle_buttons:
                if btn.clicked(ev):
                    if btn.text == "检查":
                        if puzzle.check_answer(None):
                            result = self.engine.submit_answer(None)
                            self._show_result(result)
                        else:
                            self._show_hint_inline("还不是正确的单词！")
                    elif btn.text == "打乱":
                        import random
                        random.shuffle(puzzle.data["player_letters"])
                        self._anagram_sel = -1

    def _draw_anagram(self, puzzle: AnagramPuzzle) -> None:
        t = self.font_md.render("拼出正确的单词！", True, C_WHITE)
        self.screen.blit(t, (WIDTH // 2 - t.get_width() // 2, 80))

        letters = puzzle.data["player_letters"]
        card_w = 52
        card_h = 60
        gap = 10
        total = len(letters) * (card_w + gap) - gap
        sx = WIDTH // 2 - total // 2
        sy = 200

        for i, ch in enumerate(letters):
            x = sx + i * (card_w + gap)
            bg = C_CELL_SEL if i == self._anagram_sel else C_CELL_BG
            rect = pygame.Rect(x, sy, card_w, card_h)
            pygame.draw.rect(self.screen, bg, rect, border_radius=6)
            lt = self.font_md.render(ch.upper(), True, C_WHITE)
            self.screen.blit(lt, (x + (card_w - lt.get_width()) // 2,
                                   sy + (card_h - lt.get_height()) // 2))

        # Current attempt
        attempt = "".join(letters).upper()
        at = self.font_sm.render(f"当前: {attempt}", True, C_GRAY)
        self.screen.blit(at, (WIDTH // 2 - at.get_width() // 2, 290))

        self._puzzle_buttons = [
            Button(pygame.Rect(WIDTH // 2 - 120, 330, 100, 36), "检查", self.font_sm,
                   color=C_GREEN),
            Button(pygame.Rect(WIDTH // 2 + 20, 330, 100, 36), "打乱", self.font_sm,
                   color=C_ORANGE),
        ]

        inst = self.font_xs.render("点击两个字母交换位置", True, C_GRAY)
        self.screen.blit(inst, (WIDTH // 2 - inst.get_width() // 2, 160))

    # -----------------------------------------------------------------------
    # Memory Puzzle
    # -----------------------------------------------------------------------
    def _handle_memory(self, events: list, mouse_pos: tuple) -> None:
        puzzle = self._puzzle
        assert isinstance(puzzle, MemoryPuzzle)

        if self._mem_mismatch_pending:
            return

        rows, cols = puzzle.data["rows"], puzzle.data["cols"]
        card_w = min(80, (WIDTH - 80) // cols)
        card_h = min(80, (HEIGHT - HEADER_H - FOOTER_H - 80) // rows)
        gap = 6
        total_w = cols * (card_w + gap) - gap
        total_h = rows * (card_h + gap) - gap
        ox = WIDTH // 2 - total_w // 2
        oy = HEADER_H + 20 + (HEIGHT - HEADER_H - FOOTER_H - 20 - total_h) // 2

        for ev in events:
            if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                mx, my = ev.pos
                for r in range(rows):
                    for c in range(cols):
                        x = ox + c * (card_w + gap)
                        y = oy + r * (card_h + gap)
                        if x <= mx < x + card_w and y <= my < y + card_h:
                            result = puzzle.flip_card(r, c)
                            if result["action"] == "match":
                                if puzzle.check_answer(None):
                                    res = self.engine.submit_answer(None)
                                    self._show_result(res)
                            elif result["action"] == "mismatch":
                                self._mem_mismatch_time = time.time()
                                self._mem_mismatch_pending = True
                            break

    def _draw_memory(self, puzzle: MemoryPuzzle) -> None:
        rows, cols = puzzle.data["rows"], puzzle.data["cols"]
        card_w = min(80, (WIDTH - 80) // cols)
        card_h = min(80, (HEIGHT - HEADER_H - FOOTER_H - 80) // rows)
        gap = 6
        total_w = cols * (card_w + gap) - gap
        total_h = rows * (card_h + gap) - gap
        ox = WIDTH // 2 - total_w // 2
        oy = HEADER_H + 20 + (HEIGHT - HEADER_H - FOOTER_H - 20 - total_h) // 2

        moves_t = self.font_sm.render(
            f"步数: {puzzle.data['moves']}  配对: {puzzle.data['pairs_found']}/{puzzle.data['pairs']}",
            True, C_WHITE
        )
        self.screen.blit(moves_t, (WIDTH // 2 - moves_t.get_width() // 2, HEADER_H + 2))

        for r in range(rows):
            for c in range(cols):
                x = ox + c * (card_w + gap)
                y = oy + r * (card_h + gap)
                rect = pygame.Rect(x, y, card_w, card_h)

                if puzzle.data["matched"][r][c]:
                    pygame.draw.rect(self.screen, C_GREEN, rect, border_radius=6)
                    symbol = puzzle.data["grid"][r][c]
                    color = SYMBOL_COLORS.get(symbol, C_WHITE)
                    st = self.font_md.render(symbol[:3].title(), True, color)
                    self.screen.blit(st, (x + (card_w - st.get_width()) // 2,
                                          y + (card_h - st.get_height()) // 2))
                elif puzzle.data["revealed"][r][c]:
                    pygame.draw.rect(self.screen, C_ACCENT, rect, border_radius=6)
                    symbol = puzzle.data["grid"][r][c]
                    color = SYMBOL_COLORS.get(symbol, C_WHITE)
                    st = self.font_md.render(symbol[:3].title(), True, color)
                    self.screen.blit(st, (x + (card_w - st.get_width()) // 2,
                                          y + (card_h - st.get_height()) // 2))
                else:
                    pygame.draw.rect(self.screen, C_CELL_BG, rect, border_radius=6)
                    q = self.font_md.render("?", True, C_GRAY)
                    self.screen.blit(q, (x + (card_w - q.get_width()) // 2,
                                         y + (card_h - q.get_height()) // 2))

        self._puzzle_buttons = []

    # -----------------------------------------------------------------------
    # Pattern Puzzle
    # -----------------------------------------------------------------------
    def _handle_pattern(self, events: list, mouse_pos: tuple) -> None:
        puzzle = self._puzzle
        assert isinstance(puzzle, PatternPuzzle)

        for ev in events:
            for i, btn in enumerate(self._puzzle_buttons):
                if btn.clicked(ev):
                    option_val = puzzle.data["options"][i]
                    result = self.engine.submit_answer(option_val)
                    self._show_result(result)
                    return

    def _draw_pattern(self, puzzle: PatternPuzzle) -> None:
        seq = puzzle.data["sequence"]
        t = self.font_md.render("下一个是什么？", True, C_WHITE)
        self.screen.blit(t, (WIDTH // 2 - t.get_width() // 2, 80))

        # Show sequence
        seq_str = "  ".join(str(x) for x in seq) + "  ?"
        st = self.font_lg.render(seq_str, True, C_ACCENT)
        self.screen.blit(st, (WIDTH // 2 - st.get_width() // 2, 150))

        # Options
        options = puzzle.data["options"]
        self._puzzle_buttons = []
        bw = 120
        bh = 50
        gap = 20
        total = len(options) * bw + (len(options) - 1) * gap
        sx = WIDTH // 2 - total // 2
        for i, opt in enumerate(options):
            rect = pygame.Rect(sx + i * (bw + gap), 260, bw, bh)
            self._puzzle_buttons.append(Button(rect, str(opt), self.font_md))

    # -----------------------------------------------------------------------
    # Hangman Puzzle
    # -----------------------------------------------------------------------
    def _handle_hangman(self, events: list, mouse_pos: tuple) -> None:
        puzzle = self._puzzle
        assert isinstance(puzzle, HangmanPuzzle)

        for ev in events:
            for btn in self._puzzle_buttons:
                if btn.clicked(ev):
                    letter = btn.text
                    result = puzzle.guess_letter(letter)
                    if result == "correct":
                        self._hangman_msg = f"'{letter}' 在单词中！"
                        self._hangman_msg_until = time.time() + 1.5
                        if self._all_letters_guessed(puzzle):
                            res = self.engine.submit_answer(None)
                            self._show_result(res)
                            return
                    elif result == "wrong":
                        self._hangman_msg = f"'{letter}' 猜错了！({len(puzzle.data['wrong'])}/{puzzle.data['max_wrong']})"
                        self._hangman_msg_until = time.time() + 1.5
                    elif result == "game_over":
                        self._hangman_msg = f"游戏结束！单词: {puzzle.data['word'].upper()}"
                        self._hangman_msg_until = time.time() + 3.0
                        self.engine.skip_puzzle()
                    elif result == "duplicate":
                        self._hangman_msg = f"你已经试过 '{letter}' 了！"
                        self._hangman_msg_until = time.time() + 1.5
                    elif result == "win":
                        res = self.engine.submit_answer(None)
                        self._show_result(res)
                        return

    def _all_letters_guessed(self, puzzle: HangmanPuzzle) -> bool:
        return all(ch in puzzle.data["guessed"] for ch in puzzle.data["word"])

    def _draw_hangman(self, puzzle: HangmanPuzzle) -> None:
        title = self.font_md.render("猜单词！", True, C_WHITE)
        self.screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 70))

        # Display word
        display = puzzle.get_display()
        dt = self.font_lg.render(display, True, C_ACCENT)
        self.screen.blit(dt, (WIDTH // 2 - dt.get_width() // 2, 130))

        # Hangman ASCII art
        wrong_count = len(puzzle.data["wrong"])
        max_wrong = puzzle.data["max_wrong"]
        stages = [
            "   +---+\n       |\n       |\n       |\n      ===",
            "   +---+\n   O   |\n       |\n       |\n      ===",
            "   +---+\n   O   |\n   |   |\n       |\n      ===",
            "   +---+\n   O   |\n  /|   |\n       |\n      ===",
            "   +---+\n   O   |\n  /|\\  |\n       |\n      ===",
            "   +---+\n   O   |\n  /|\\  |\n  /    |\n      ===",
            "   +---+\n   O   |\n  /|\\  |\n  / \\  |\n      ===",
        ]
        idx = min(wrong_count, len(stages) - 1)
        hangman_lines = stages[idx].split("\n")
        y = 160
        for line in hangman_lines:
            ht = self.font_xs.render(line, True, C_RED if wrong_count >= max_wrong else C_WHITE)
            self.screen.blit(ht, (80, y))
            y += 18

        # Wrong letters
        if puzzle.data["wrong"]:
            wrong_str = "已错: " + " ".join(sorted(puzzle.data["wrong"])).upper()
            wt = self.font_sm.render(wrong_str, True, C_RED)
            self.screen.blit(wt, (80, y + 5))

        # Message
        if self._hangman_msg and time.time() < self._hangman_msg_until:
            mt = self.font_sm.render(self._hangman_msg, True, C_YELLOW)
            self.screen.blit(mt, (WIDTH // 2 - mt.get_width() // 2, 300))

        # Remaining guesses
        remaining = max_wrong - wrong_count
        rt = self.font_sm.render(f"剩余猜测次数: {remaining}", True, C_GRAY)
        self.screen.blit(rt, (WIDTH // 2 - rt.get_width() // 2, 280))

        # Letter buttons (A-Z keyboard)
        self._puzzle_buttons = []
        letters = [chr(ord('A') + i) for i in range(26)]
        cols = 9
        bw, bh = 40, 36
        gap = 4
        sx = WIDTH // 2 - (cols * (bw + gap) - gap) // 2
        sy = 350
        for i, letter in enumerate(letters):
            r, c = divmod(i, cols)
            rect = pygame.Rect(sx + c * (bw + gap), sy + r * (bh + gap), bw, bh)
            lower = letter.lower()
            if lower in puzzle.data["guessed"]:
                clr = C_GREEN
                hclr = C_GREEN
            elif lower in puzzle.data["wrong"]:
                clr = C_RED
                hclr = C_RED
            else:
                clr = C_BTN
                hclr = C_BTN_HOV
            self._puzzle_buttons.append(Button(rect, letter, self.font_sm, color=clr, hover_color=hclr))

    # -----------------------------------------------------------------------
    # 2048 Puzzle
    # -----------------------------------------------------------------------
    def _handle_2048(self, events: list, mouse_pos: tuple) -> None:
        puzzle = self._puzzle
        assert isinstance(puzzle, Puzzle2048)

        now = time.time()
        for ev in events:
            if ev.type == pygame.KEYDOWN and now - self._2048_key_cooldown > 0.15:
                direction = None
                if ev.key in (pygame.K_LEFT, pygame.K_a):
                    direction = "left"
                elif ev.key in (pygame.K_RIGHT, pygame.K_d):
                    direction = "right"
                elif ev.key in (pygame.K_UP, pygame.K_w):
                    direction = "up"
                elif ev.key in (pygame.K_DOWN, pygame.K_s):
                    direction = "down"

                if direction:
                    self._2048_key_cooldown = now
                    result = puzzle.move(direction)
                    if result == "win":
                        res = self.engine.submit_answer(None)
                        self._show_result(res)
                        return
                    elif result == "game_over":
                        self.engine.skip_puzzle()
                        self._show_result({"correct": False})
                        return

    def _draw_2048(self, puzzle: Puzzle2048) -> None:
        size = puzzle.data["size"]
        board = puzzle.data["board"]
        cell_sz = min(90, (WIDTH - 60) // size, (HEIGHT - HEADER_H - FOOTER_H - 60) // size)
        ox = WIDTH // 2 - size * cell_sz // 2
        oy = HEADER_H + 40

        # Draw board
        tile_colors = {
            0: C_CELL_BG, 2: (238, 228, 218), 4: (237, 224, 200),
            8: (242, 177, 121), 16: (245, 149, 99), 32: (246, 124, 95),
            64: (246, 94, 59), 128: (237, 207, 114), 256: (237, 204, 97),
            512: (237, 200, 80), 1024: (237, 197, 63), 2048: (237, 194, 46),
        }
        text_colors = {
            0: C_WHITE, 2: (119, 110, 101), 4: (119, 110, 101),
            8: C_WHITE, 16: C_WHITE, 32: C_WHITE, 64: C_WHITE,
            128: C_WHITE, 256: C_WHITE, 512: C_WHITE, 1024: C_WHITE, 2048: C_WHITE,
        }

        # Background
        bg_rect = pygame.Rect(ox - 6, oy - 6, size * cell_sz + 6, size * cell_sz + 6)
        pygame.draw.rect(self.screen, (187, 173, 160), bg_rect, border_radius=6)

        for r in range(size):
            for c in range(size):
                x = ox + c * cell_sz
                y = oy + r * cell_sz
                val = board[r][c]
                bg = tile_colors.get(val, (60, 58, 50))
                fg = text_colors.get(val, C_WHITE)
                rect = pygame.Rect(x + 3, y + 3, cell_sz - 6, cell_sz - 6)
                pygame.draw.rect(self.screen, bg, rect, border_radius=6)
                if val != 0:
                    font = self.font_lg if val < 100 else self.font_md
                    t = font.render(str(val), True, fg)
                    self.screen.blit(t, (x + (cell_sz - t.get_width()) // 2,
                                         y + (cell_sz - t.get_height()) // 2))

        # Score
        st = self.font_md.render(f"分数: {puzzle.data['score']}  |  目标: {puzzle.data['target']}", True, C_WHITE)
        self.screen.blit(st, (WIDTH // 2 - st.get_width() // 2, oy + size * cell_sz + 10))

        # Instructions
        inst = self.font_sm.render("方向键 / WASD 移动方块", True, C_GRAY)
        self.screen.blit(inst, (WIDTH // 2 - inst.get_width() // 2, oy + size * cell_sz + 38))

        if puzzle.data["game_over"]:
            go = self.font_lg.render("游戏结束！", True, C_RED)
            self.screen.blit(go, (WIDTH // 2 - go.get_width() // 2, oy + size * cell_sz + 60))

        self._puzzle_buttons = []

    # -----------------------------------------------------------------------
    # Color Sequence Puzzle
    # -----------------------------------------------------------------------
    def _handle_color_sequence(self, events: list, mouse_pos: tuple) -> None:
        puzzle = self._puzzle
        assert isinstance(puzzle, ColorSequencePuzzle)

        now = time.time()

        # Handle show phase auto-advance
        if puzzle.data["phase"] == "show" and not self._cs_phase_shown:
            self._cs_flash_index = 0
            self._cs_flash_timer = now
            self._cs_phase_shown = True

        if puzzle.data["phase"] == "show":
            show_time = puzzle.data["show_time"]
            elapsed = now - self._cs_flash_timer
            if elapsed >= show_time:
                self._cs_flash_index += 1
                self._cs_flash_timer = now
                if self._cs_flash_index >= puzzle.data["length"]:
                    puzzle.start_input_phase()
                    self._cs_flash_index = -1
                    self._cs_phase_shown = False

        # Handle input phase
        if puzzle.data["phase"] == "input":
            for ev in events:
                if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                    for btn in self._puzzle_buttons:
                        if btn.clicked(ev):
                            color = btn.text
                            color_en = CN_TO_EN.get(color, color)
                            result = puzzle.press_color(color_en)
                            if result == "win":
                                self._cs_feedback_msg = "正确！做得好！"
                                self._cs_feedback_until = now + 1.5
                                res = self.engine.submit_answer(None)
                                self._show_result(res)
                                return
                            elif result == "wrong":
                                self._cs_feedback_msg = "序列错误！当前回合失败。"
                                self._cs_feedback_until = now + 2.0
                                self.engine.skip_puzzle()

        # Handle feedback phase transition
        if puzzle.data["phase"] == "feedback" and puzzle.data["correct"]:
            # Next round - regenerate
            if puzzle.data["round"] >= 3 and puzzle.data["length"] >= 5:
                # Already done well, just show win
                pass

    def _draw_color_sequence(self, puzzle: ColorSequencePuzzle) -> None:
        phase = puzzle.data["phase"]
        seq = puzzle.data["sequence"]
        now = time.time()

        title = self.font_md.render("重复颜色序列！", True, C_WHITE)
        self.screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 70))

        if phase == "show":
            st = self.font_sm.render("观察模式...", True, C_YELLOW)
            self.screen.blit(st, (WIDTH // 2 - st.get_width() // 2, 110))
        elif phase == "input":
            idx = puzzle.data["player_index"]
            done = ", ".join(COLOR_CN.get(c, c) for c in puzzle.data["player_input"])
            st = self.font_sm.render(f"你的输入: {done}  ({idx}/{len(seq)})", True, C_WHITE)
            self.screen.blit(st, (WIDTH // 2 - st.get_width() // 2, 110))

        # Draw color buttons
        colors = ["红色", "绿色", "蓝色", "黄色"]
        colors_en = ["red", "green", "blue", "yellow"]
        bw, bh = 100, 100
        gap = 30
        total = len(colors) * (bw + gap) - gap
        sx = WIDTH // 2 - total // 2
        sy = 200

        self._puzzle_buttons = []
        for i, color in enumerate(colors):
            x = sx + i * (bw + gap)
            rect = pygame.Rect(x, sy, bw, bh)

            # Flash during show phase
            is_flashing = (phase == "show" and i == self._cs_flash_index)
            bg = COLOR_BRIGHT.get(colors_en[i], C_CELL_BG) if is_flashing else COLOR_RGB.get(colors_en[i], C_CELL_BG)
            pygame.draw.rect(self.screen, bg, rect, border_radius=12)

            label = color
            lt = self.font_md.render(label, True, C_WHITE)
            self.screen.blit(lt, (x + (bw - lt.get_width()) // 2,
                                   sy + (bh - lt.get_height()) // 2))

            if phase == "input":
                hover = rect.collidepoint(pygame.mouse.get_pos())
                if hover:
                    pygame.draw.rect(self.screen, C_WHITE, rect, width=3, border_radius=12)
            self._puzzle_buttons.append(Button(rect, color, self.font_md))

        # Feedback message
        if self._cs_feedback_msg and now < self._cs_feedback_until:
            color = C_GREEN if "正确" in self._cs_feedback_msg else C_RED
            mt = self.font_md.render(self._cs_feedback_msg, True, color)
            self.screen.blit(mt, (WIDTH // 2 - mt.get_width() // 2, 350))

        # Sequence length indicator
        sl = self.font_sm.render(f"序列长度: {len(seq)}", True, C_GRAY)
        self.screen.blit(sl, (WIDTH // 2 - sl.get_width() // 2, 390))

    # -----------------------------------------------------------------------
    # Generic grid click detector
    # -----------------------------------------------------------------------
    def _grid_click(self, mx: int, my: int, rows: int, cols: int,
                    cell_sz: int, ox: int, oy: int) -> tuple[int, int] | None:
        for r in range(rows):
            for c in range(cols):
                x = ox + c * cell_sz
                y = oy + r * cell_sz
                if x <= mx < x + cell_sz and y <= my < y + cell_sz:
                    return (r, c)
        return None
