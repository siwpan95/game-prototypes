"""Logger — 轻量级文件日志工具。"""

from __future__ import annotations

import os
import time
from datetime import datetime


class Logger:
    """简单的文件日志器。"""

    LEVELS = {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40}

    def __init__(self, log_dir: str = "", level: str = "INFO"):
        self.level = self.LEVELS.get(level.upper(), 20)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
            self._log_file = os.path.join(log_dir, "game.log")
        else:
            self._log_file = None

    def _write(self, level: str, message: str) -> None:
        if self.LEVELS.get(level, 0) < self.level:
            return
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{ts}] [{level:<7}] {message}\n"
        print(line.rstrip())
        if self._log_file:
            try:
                with open(self._log_file, "a", encoding="utf-8") as f:
                    f.write(line)
            except OSError:
                pass

    def debug(self, msg: str) -> None:
        self._write("DEBUG", msg)

    def info(self, msg: str) -> None:
        self._write("INFO", msg)

    def warning(self, msg: str) -> None:
        self._write("WARNING", msg)

    def error(self, msg: str) -> None:
        self._write("ERROR", msg)

    def game_event(self, event_type: str, detail: str) -> None:
        self._write("INFO", f"[GAME] [{event_type}] {detail}")
