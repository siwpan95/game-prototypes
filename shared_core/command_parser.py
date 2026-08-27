"""
Command Parser — 文本命令解析器。

解析用户输入为 (command_name, arguments) 元组。
"""

from __future__ import annotations
from typing import Optional


class CommandParser:
    """简单的文本命令解析器。"""

    def __init__(self):
        self._aliases: dict[str, str] = {}
        # 默认别名
        self._aliases.update({
            "q": "quit", "exit": "quit",
            "h": "help", "?": "help",
            "l": "look", "look": "look",
            "n": "next", "next": "next", "r": "read",
            "hint": "hint", "hints": "hint",
            "i": "inventory", "inv": "inventory",
            "save": "save", "load": "load",
        })

    def add_alias(self, alias: str, command: str) -> None:
        self._aliases[alias.lower()] = command

    def parse(self, raw_input: str) -> tuple[str, list[str]]:
        """
        解析输入为 (command_name, args)。

        Returns:
            ("", []) for empty input
            ("unknown", [raw]) for unrecognized commands
        """
        text = raw_input.strip()
        if not text:
            return ("", [])

        parts = text.split(None, 1)
        cmd = parts[0].lower()
        args_str = parts[1] if len(parts) > 1 else ""
        args = args_str.split() if args_str else []

        # 解析别名
        resolved = self._aliases.get(cmd, cmd)
        return (resolved, args)

    def is_quit(self, raw_input: str) -> bool:
        cmd, _ = self.parse(raw_input)
        return cmd == "quit"
