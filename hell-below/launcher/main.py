"""Hell Below Launcher Platform. Entry point (Tkinter)."""

import os
import sys
import tkinter as tk

# Ensure working directory is the project root
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from src.core.constants import WIN_WIDTH, WIN_HEIGHT, COLOR_BG
from src.controllers.launcher_controller import LauncherController


def main() -> None:
    root = tk.Tk()
    root.title("地狱之下")
    root.geometry(f"{WIN_WIDTH}x{WIN_HEIGHT}")
    root.resizable(False, False)
    root.configure(bg=COLOR_BG)

    # Center the window on screen
    root.update_idletasks()
    screen_w = root.winfo_screenwidth()
    screen_h = root.winfo_screenheight()
    x = (screen_w - WIN_WIDTH) // 2
    y = (screen_h - WIN_HEIGHT) // 2
    root.geometry(f"{WIN_WIDTH}x{WIN_HEIGHT}+{x}+{y}")

    # Create the controller (which sets up views and bindings)
    _controller = LauncherController(root)

    # Start the Tkinter main loop
    root.mainloop()


if __name__ == "__main__":
    main()
