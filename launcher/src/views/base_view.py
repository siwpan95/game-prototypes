"""Base view class — Tkinter Frame with show/hide lifecycle."""

from __future__ import annotations

import tkinter as tk


class BaseView(tk.Frame):
    """Abstract base for all launcher views.

    Subclasses must implement ``build()`` which is called once when the
    view is first shown.  The controller is injected via ``set_controller``
    before ``build()`` is called.
    """

    def __init__(self, master: tk.Tk, **kwargs) -> None:
        super().__init__(master, bg=kwargs.pop("bg", "#0C0814"), **kwargs)
        self._controller = None
        self._built: bool = False

    # ── Lifecycle ──────────────────────────────────────────────────────

    def set_controller(self, controller) -> None:
        """Inject the launcher controller."""
        self._controller = controller

    def build(self) -> None:
        """Construct child widgets. Called once on first ``show()``."""
        # Default: nothing to build. Subclasses override.

    def refresh(self) -> None:
        """Refresh dynamic content (e.g. after language toggle)."""

    # ── Visibility ─────────────────────────────────────────────────────

    def show(self) -> None:
        """Make this view visible, building on first call."""
        if not self._built:
            self.build()
            self._built = True
        self.pack(fill=tk.BOTH, expand=True)

    def hide(self) -> None:
        """Hide this view."""
        self.pack_forget()
