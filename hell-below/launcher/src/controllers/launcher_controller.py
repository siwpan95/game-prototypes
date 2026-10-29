"""Launcher controller — state machine, game launching, and view dispatch."""

from __future__ import annotations

import subprocess
import sys
import tkinter as tk

from src.core.constants import LauncherState, COLOR_BG
from src.core.i18n import I18n
from src.models.game_registry import get_game_by_id
from src.views.main_menu import MainMenuView
from src.views.game_grid import GameGridView


class LauncherController:
    """Central controller for the Hell Below launcher platform.

    Manages view switching and game launching
    using Tkinter's event loop instead of pygame.
    """

    def __init__(self, root: tk.Tk) -> None:
        self._root = root
        self._state = LauncherState.MAIN_MENU
        self._i18n = I18n.instance()
        self._game_process: subprocess.Popen | None = None

        # Initialize i18n — Chinese only
        self._i18n.load("zh")
        self._i18n.current_lang = "zh"

        # Views
        self._main_menu = MainMenuView(root)
        self._main_menu.set_controller(self)

        self._game_grid = GameGridView(root)
        self._game_grid.set_controller(self)

        # Keyboard bindings
        self._root.bind("<Escape>", self._on_escape)
        self._root.bind("<F11>", self._on_f11)
        self._root.bind("<Return>", self._on_return)

        # Start at main menu
        self._show_view(self._main_menu)

    # ── View Management ────────────────────────────────────────────────

    def _show_view(self, view) -> None:
        """Hide all views, then show the given one."""
        self._main_menu.hide()
        self._game_grid.hide()
        view.show()

    def _current_view(self):
        """Return the currently visible view."""
        if self._state == LauncherState.MAIN_MENU:
            return self._main_menu
        elif self._state == LauncherState.GAME_GRID:
            return self._game_grid
        return None

    # ── Action Dispatch ────────────────────────────────────────────────

    def dispatch(self, action: str, **kwargs) -> None:
        """Route an action to the appropriate handler."""
        if action == "enter":
            self._go_to_game_grid()
        elif action == "launch_game":
            game_id = kwargs.get("game_id", "")
            self._launch_game(game_id)
        elif action == "back":
            self._go_back()
        elif action == "quit":
            self._root.destroy()

    # ── Navigation ─────────────────────────────────────────────────────

    def _go_to_game_grid(self) -> None:
        """Navigate to the game selection grid."""
        self._state = LauncherState.GAME_GRID
        self._show_view(self._game_grid)

    def _go_back(self) -> None:
        """Navigate back based on current state."""
        if self._state == LauncherState.GAME_GRID:
            self._state = LauncherState.MAIN_MENU
            self._show_view(self._main_menu)

    # ── Game Launching ─────────────────────────────────────────────────

    def _launch_game(self, game_id: str) -> None:
        """Launch a game as a subprocess, hiding the launcher until it exits.

        Always uses the Chinese version (ch/).
        """
        game = get_game_by_id(game_id)
        if game is None:
            return

        if not game.exists_zh():
            print(f"Game not found: {game.main_file_zh}")
            return

        python_exe = sys.executable
        game_dir = str(game.game_dir_zh)
        main_py = str(game.main_file_zh)

        self._state = LauncherState.GAME_RUNNING

        # Hide the launcher window
        self._root.withdraw()

        try:
            self._game_process = subprocess.Popen(
                [python_exe, main_py],
                cwd=game_dir,
            )
        except Exception as e:
            print(f"Failed to launch game: {e}")
            self._root.deiconify()
            self._state = LauncherState.GAME_GRID
            self._show_view(self._game_grid)
            return

        # Poll for game exit using root.after()
        self._wait_for_game()

    def _wait_for_game(self) -> None:
        """Non-blocking poll for game subprocess to exit."""
        if self._game_process is not None and self._game_process.poll() is None:
            # Game still running — check again in 200ms
            self._root.after(200, self._wait_for_game)
        else:
            # Game has exited — restore launcher
            self._game_process = None
            self._root.deiconify()
            self._state = LauncherState.GAME_GRID
            self._show_view(self._game_grid)

    # ── Global Key Bindings ────────────────────────────────────────────

    def _on_escape(self, _event=None) -> None:
        """Handle Escape key — navigate back or quit."""
        if self._state == LauncherState.GAME_GRID:
            self._go_back()
        elif self._state == LauncherState.MAIN_MENU:
            self._root.destroy()

    def _on_f11(self, _event=None) -> None:
        """Toggle fullscreen on F11."""
        is_fullscreen = self._root.attributes("-fullscreen")
        self._root.attributes("-fullscreen", not is_fullscreen)

    def _on_return(self, _event=None) -> None:
        """Handle Enter key — navigate to game grid from main menu."""
        if self._state == LauncherState.MAIN_MENU:
            self._go_to_game_grid()
