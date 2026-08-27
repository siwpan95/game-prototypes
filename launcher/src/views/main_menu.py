"""Main menu view — platform title screen with styled buttons."""

from __future__ import annotations

import tkinter as tk

from src.core.constants import (
    COLOR_BG, COLOR_GOLD, COLOR_DIM, COLOR_TEXT,
    COLOR_CHOICE_BG, COLOR_CHOICE_HOVER, COLOR_CHOICE_BORDER,
    COLOR_HIGHLIGHT, FONT_FAMILY,
)
from src.core.i18n import I18n
from src.views.base_view import BaseView


class _StyledButton(tk.Frame):
    """A custom styled button widget using Frame + Label.

    Provides hover highlight effects consistent with the dark theme.
    """

    def __init__(
        self,
        master,
        text: str,
        command=None,
        width: int = 24,
        font_size: int = 18,
        **kwargs,
    ) -> None:
        super().__init__(
            master,
            bg=COLOR_CHOICE_BG,
            highlightbackground=COLOR_CHOICE_BORDER,
            highlightthickness=1,
            cursor="hand2",
            **kwargs,
        )
        self._command = command
        self._text = text
        self._font_size = font_size

        self._label = tk.Label(
            self,
            text=text,
            bg=COLOR_CHOICE_BG,
            fg=COLOR_TEXT,
            font=(FONT_FAMILY, font_size),
            width=width,
            pady=8,
            cursor="hand2",
        )
        self._label.pack(fill=tk.BOTH, expand=True)

        # Bind events on both the frame and label
        for widget in (self, self._label):
            widget.bind("<Enter>", self._on_enter)
            widget.bind("<Leave>", self._on_leave)
            widget.bind("<Button-1>", self._on_click)

    def _on_enter(self, _event=None) -> None:
        """Highlight on hover."""
        self.configure(bg=COLOR_CHOICE_HOVER, highlightbackground=COLOR_HIGHLIGHT)
        self._label.configure(bg=COLOR_CHOICE_HOVER, fg=COLOR_HIGHLIGHT)

    def _on_leave(self, _event=None) -> None:
        """Restore default style."""
        self.configure(bg=COLOR_CHOICE_BG, highlightbackground=COLOR_CHOICE_BORDER)
        self._label.configure(bg=COLOR_CHOICE_BG, fg=COLOR_TEXT)

    def _on_click(self, _event=None) -> None:
        """Execute the button command."""
        if self._command:
            self._command()

    def update_text(self, text: str) -> None:
        """Update the button label text."""
        self._text = text
        self._label.configure(text=text)


class MainMenuView(BaseView):
    """Main menu with platform title and entry button."""

    def build(self) -> None:
        """Construct the main menu UI."""
        i18n = I18n.instance()

        # ── Center container ────────────────────────────────────────────
        center = tk.Frame(self, bg=COLOR_BG)
        center.place(relx=0.5, rely=0.45, anchor=tk.CENTER)

        # ── Title ──────────────────────────────────────────────────────
        title_text = i18n.t("menu_title")
        self._title_label = tk.Label(
            center,
            text=title_text,
            bg=COLOR_BG,
            fg=COLOR_GOLD,
            font=(FONT_FAMILY, 52, "bold"),
        )
        self._title_label.pack(pady=(0, 4))

        # ── Subtitle ───────────────────────────────────────────────────
        subtitle_text = i18n.t("menu_subtitle")
        self._subtitle_label = tk.Label(
            center,
            text=subtitle_text,
            bg=COLOR_BG,
            fg=COLOR_DIM,
            font=(FONT_FAMILY, 16),
        )
        self._subtitle_label.pack(pady=(0, 30))

        # ── Decorative separator line ──────────────────────────────────
        sep_frame = tk.Frame(center, bg=COLOR_GOLD, height=1, width=200)
        sep_frame.pack(pady=(0, 30))

        # ── Buttons ────────────────────────────────────────────────────
        btn_container = tk.Frame(center, bg=COLOR_BG)
        btn_container.pack()

        self._btn_enter = _StyledButton(
            btn_container,
            text=i18n.t("menu_enter"),
            command=self._on_enter,
            font_size=18,
        )
        self._btn_enter.pack(pady=6)

        self._btn_quit = _StyledButton(
            btn_container,
            text=i18n.t("menu_quit"),
            command=self._on_quit,
            font_size=18,
        )
        self._btn_quit.pack(pady=6)

        # ── Footer ─────────────────────────────────────────────────────
        footer_text = i18n.t("footer")
        self._footer_label = tk.Label(
            self,
            text=footer_text,
            bg=COLOR_BG,
            fg="#50463C",
            font=(FONT_FAMILY, 11),
        )
        self._footer_label.place(relx=0.5, rely=0.95, anchor=tk.CENTER)

    # ── Actions ────────────────────────────────────────────────────────

    def _on_enter(self) -> None:
        """Navigate to game grid."""
        if self._controller:
            self._controller.dispatch("enter")

    def _on_quit(self) -> None:
        """Quit the application."""
        if self._controller:
            self._controller.dispatch("quit")

    # ── Refresh ─────────────────────────────────────────────────────

    def refresh(self) -> None:
        """Update all labels."""
        i18n = I18n.instance()
        self._title_label.configure(text=i18n.t("menu_title"))
        self._subtitle_label.configure(text=i18n.t("menu_subtitle"))
        self._btn_enter.update_text(i18n.t("menu_enter"))
        self._btn_quit.update_text(i18n.t("menu_quit"))
        self._footer_label.configure(text=i18n.t("footer"))
