"""
Command Handler — 命令分发器。

将解析后的命令路由到对应的处理器函数。
"""

from __future__ import annotations
from typing import Any, Callable, Optional


class CommandResult:
    """命令执行结果。"""

    def __init__(self, success: bool, message: str = "", data: Any = None):
        self.success = success
        self.message = message
        self.data = data

    def __repr__(self) -> str:
        status = "OK" if self.success else "FAIL"
        return f"CommandResult({status}: {self.message})"


class CommandHandler:
    """中央命令分发器。"""

    def __init__(self):
        self._handlers: dict[str, Callable] = {}
        self._context: dict[str, Any] = {}

    def set_context(self, **kwargs: Any) -> None:
        self._context.update(kwargs)

    def register(self, name: str, handler: Callable) -> None:
        """注册命令处理器。"""
        self._handlers[name.lower()] = handler

    def execute(self, cmd_name: str, args: list[str]) -> CommandResult:
        """执行命令。"""
        handler = self._handlers.get(cmd_name.lower())
        if not handler:
            return CommandResult(False, f"未知命令: {cmd_name}")
        try:
            result = handler(args, self._context)
            if isinstance(result, CommandResult):
                return result
            return CommandResult(True, str(result))
        except Exception as e:
            return CommandResult(False, f"命令错误 ({type(e).__name__}): {e}")

    def get_all_commands(self) -> list[str]:
        return list(self._handlers.keys())
