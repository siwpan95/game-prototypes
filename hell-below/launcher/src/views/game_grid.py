"""Game grid view — displays all 11 games in a selectable 4-column grid."""

from __future__ import annotations

import tkinter as tk

from src.core.constants import (
    COLOR_BG, COLOR_TEXT, COLOR_DIM, COLOR_GOLD,
    COLOR_CARD_BG, COLOR_CARD_HOVER,
    COLOR_CARD_BORDER, COLOR_CARD_BORDER_HOVER,
    COLOR_VOLUME, COLOR_GENRE, COLOR_SUBTITLE,
    COLOR_CHOICE_BG, COLOR_CHOICE_HOVER, COLOR_CHOICE_BORDER,
    COLOR_HIGHLIGHT, FONT_FAMILY, FONT_FAMILY_MONO,
)
from src.core.i18n import I18n
from src.models.game_registry import GAMES
from src.views.base_view import BaseView


class _GameCard(tk.Frame):
    """A single game card widget with hover effect and launch callback."""

    def __init__(
        self,
        master,
        game,
        on_launch=None,
        **kwargs,
    ) -> None:
        super().__init__(
            master,
            bg=COLOR_CARD_BG,
            highlightbackground=COLOR_CARD_BORDER,
            highlightthickness=2,
            cursor="hand2",
            width=200,
            height=140,
            **kwargs,
        )
        self._game = game
        self._on_launch = on_launch
        self._hovered = False

        i18n = I18n.instance()
        self._available = game.exists_zh()

        # Prevent shrinking
        self.pack_propagate(False)
        self.grid_propagate(False)

        # ── Top row: volume + availability ─────────────────────────────
        top = tk.Frame(self, bg=COLOR_CARD_BG)
        top.pack(fill=tk.X, padx=8, pady=(8, 0))

        vol_label = tk.Label(
            top,
            text=f"第{game.volume:02d}卷",
            bg=COLOR_CARD_BG,
            fg=COLOR_VOLUME,
            font=(FONT_FAMILY_MONO, 10),
            anchor=tk.W,
        )
        vol_label.pack(side=tk.LEFT)

        if not self._available:
            na_label = tk.Label(
                top,
                text=i18n.t("not_available"),
                bg=COLOR_CARD_BG,
                fg=COLOR_DIM,
                font=(FONT_FAMILY, 9),
                anchor=tk.E,
            )
            na_label.pack(side=tk.RIGHT)
            self._na_label = na_label
        else:
            self._na_label = None

        # ── Title ──────────────────────────────────────────────────────
        title = game.title_zh
        self._title_label = tk.Label(
            self,
            text=title,
            bg=COLOR_CARD_BG,
            fg=COLOR_GOLD if self._available else COLOR_DIM,
            font=(FONT_FAMILY, 15, "bold"),
        )
        self._title_label.pack(pady=(10, 2))

        # ── Subtitle (English name) ──────────────────────────────────────
        subtitle = game.title_en
        self._sub_label = tk.Label(
            self,
            text=subtitle,
            bg=COLOR_CARD_BG,
            fg=COLOR_SUBTITLE,
            font=(FONT_FAMILY_MONO, 10),
        )
        self._sub_label.pack(pady=(0, 2))

        # ── Genre tag ───────────────────────────────────────────────────
        genre = game.genre_zh
        self._genre_label = tk.Label(
            self,
            text=genre,
            bg=COLOR_CARD_BG,
            fg=COLOR_GENRE,
            font=(FONT_FAMILY, 10),
        )
        self._genre_label.pack(pady=(0, 8))

        # ── Update cursor based on availability ────────────────────────
        self.configure(cursor="hand2" if self._available else "arrow")

        # ── Bind hover / click on all children ─────────────────────────
        self._bind_hover()

    def _bind_hover(self) -> None:
        """Bind Enter/Leave/Click on this frame and all descendant widgets."""
        widgets = [self]
        self._collect_children(self, widgets)
        for w in widgets:
            w.bind("<Enter>", self._on_enter)
            w.bind("<Leave>", self._on_leave)
            if self._available:
                w.bind("<Button-1>", self._on_click)

    @staticmethod
    def _collect_children(widget, out: list) -> None:
        """Recursively collect all descendant widgets."""
        for child in widget.winfo_children():
            out.append(child)
            _GameCard._collect_children(child, out)

    def _on_enter(self, _event=None) -> None:
        """Hover highlight."""
        if not self._available:
            return
        self._hovered = True
        self.configure(
            bg=COLOR_CARD_HOVER,
            highlightbackground=COLOR_CARD_BORDER_HOVER,
        )
        for child in self.winfo_children():
            child.configure(bg=COLOR_CARD_HOVER)
        self._title_label.configure(fg=COLOR_GOLD, bg=COLOR_CARD_HOVER)

    def _on_leave(self, _event=None) -> None:
        """Restore default."""
        self._hovered = False
        self.configure(
            bg=COLOR_CARD_BG,
            highlightbackground=COLOR_CARD_BORDER,
        )
        for child in self.winfo_children():
            child.configure(bg=COLOR_CARD_BG)
        fg = COLOR_GOLD if self._available else COLOR_DIM
        self._title_label.configure(fg=fg, bg=COLOR_CARD_BG)

    def _on_click(self, _event=None) -> None:
        """Launch the game."""
        if self._available and self._on_launch:
            self._on_launch(self._game.game_id)

    def update_texts(self) -> None:
        """Refresh card texts and availability."""
        i18n = I18n.instance()
        self._available = self._game.exists_zh()
        self.configure(cursor="hand2" if self._available else "arrow")

        self._title_label.configure(text=self._game.title_zh)
        self._sub_label.configure(text=self._game.title_en)
        self._genre_label.configure(text=self._game.genre_zh)

        fg = COLOR_GOLD if self._available else COLOR_DIM
        self._title_label.configure(fg=fg)

        # Update "N/A" label visibility
        if self._na_label is not None:
            if self._available:
                self._na_label.pack_forget()
            else:
                self._na_label.pack(side=tk.RIGHT)

        # Re-bind click handlers based on new availability
        self._bind_hover()


class _BackButton(tk.Frame):
    """A styled back button at the bottom of the game grid."""

    def __init__(self, master, command=None, **kwargs) -> None:
        super().__init__(
            master,
            bg=COLOR_CHOICE_BG,
            highlightbackground=COLOR_CHOICE_BORDER,
            highlightthickness=1,
            cursor="hand2",
            **kwargs,
        )
        self._command = command
        self._label = tk.Label(
            self,
            text="",
            bg=COLOR_CHOICE_BG,
            fg=COLOR_TEXT,
            font=(FONT_FAMILY, 13),
            padx=24,
            pady=6,
            cursor="hand2",
        )
        self._label.pack()
        for w in (self, self._label):
            w.bind("<Enter>", self._on_enter)
            w.bind("<Leave>", self._on_leave)
            w.bind("<Button-1>", self._on_click)

    def _on_enter(self, _e=None) -> None:
        self.configure(bg=COLOR_CHOICE_HOVER, highlightbackground=COLOR_HIGHLIGHT)
        self._label.configure(bg=COLOR_CHOICE_HOVER, fg=COLOR_HIGHLIGHT)

    def _on_leave(self, _e=None) -> None:
        self.configure(bg=COLOR_CHOICE_BG, highlightbackground=COLOR_CHOICE_BORDER)
        self._label.configure(bg=COLOR_CHOICE_BG, fg=COLOR_TEXT)

    def _on_click(self, _e=None) -> None:
        if self._command:
            self._command()

    def update_text(self, text: str) -> None:
        self._label.configure(text=text)


class GameGridView(BaseView):
    """Game selection grid showing all available games."""

    COLS = 4
    CARD_W = 200
    CARD_H = 150
    GAP_X = 14
    GAP_Y = 14

    def build(self) -> None:
        """Construct the game grid UI."""
        i18n = I18n.instance()

        # ── Header ─────────────────────────────────────────────────────
        header_frame = tk.Frame(self, bg=COLOR_BG)
        header_frame.pack(fill=tk.X, pady=(18, 0))

        self._header_label = tk.Label(
            header_frame,
            text=i18n.t("grid_title"),
            bg=COLOR_BG,
            fg=COLOR_GOLD,
            font=(FONT_FAMILY, 28, "bold"),
        )
        self._header_label.pack()

        self._subheader_label = tk.Label(
            header_frame,
            text=i18n.t("grid_subtitle"),
            bg=COLOR_BG,
            fg=COLOR_DIM,
            font=(FONT_FAMILY, 12),
        )
        self._subheader_label.pack(pady=(2, 12))

        # ── Grid container ─────────────────────────────────────────────
        grid_outer = tk.Frame(self, bg=COLOR_BG)
        grid_outer.pack(fill=tk.BOTH, expand=True)

        # Center the grid
        grid_container = tk.Frame(grid_outer, bg=COLOR_BG)
        grid_container.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

        self._cards: list[_GameCard] = []
        for i, game in enumerate(GAMES):
            row = i // self.COLS
            col = i % self.COLS
            card = _GameCard(
                grid_container,
                game=game,
                on_launch=self._on_launch,
            )
            card.grid(
                row=row,
                column=col,
                padx=self.GAP_X // 2,
                pady=self.GAP_Y // 2,
                sticky="nsew",
            )
            self._cards.append(card)

        # ── Footer area with back button ──────────────────────────────
        footer_frame = tk.Frame(self, bg=COLOR_BG)
        footer_frame.pack(fill=tk.X, pady=(8, 14))

        self._back_btn = _BackButton(
            footer_frame,
            command=self._on_back,
        )
        self._back_btn.update_text(i18n.t("back"))
        self._back_btn.pack()

        self._footer_label = tk.Label(
            footer_frame,
            text=i18n.t("grid_footer"),
            bg=COLOR_BG,
            fg=COLOR_DIM,
            font=(FONT_FAMILY, 10),
        )
        self._footer_label.pack(pady=(6, 0))

    # ── Actions ────────────────────────────────────────────────────────

    def _on_launch(self, game_id: str) -> None:
        """Launch the selected game."""
        if self._controller:
            self._controller.dispatch("launch_game", game_id=game_id)

    def _on_back(self) -> None:
        """Navigate back to main menu."""
        if self._controller:
            self._controller.dispatch("back")

    # ── Refresh ──────────────────────────────────────────────────────

    def refresh(self) -> None:
        """Update all labels and card availability."""
        i18n = I18n.instance()
        self._header_label.configure(text=i18n.t("grid_title"))
        self._subheader_label.configure(text=i18n.t("grid_subtitle"))
        self._footer_label.configure(text=i18n.t("grid_footer"))
        self._back_btn.update_text(i18n.t("back"))
        for card in self._cards:
            card.update_texts()
