"""
命令系统 — 文本命令解析与分发。

解析用户原始输入为 (command_name, args) 元组，
并通过注册的处理器函数分发执行。

使用方式:

    parser = CommandParser()
    handler = CommandHandler()
    handler.register("look", look_handler)
    parsed = parser.parse("look north")   # → ("look", ["north"])
    result = handler.execute("look", ["north"])
"""

from __future__ import annotations
from typing import Any, Callable, Optional


# ---------------------------------------------------------------
# 预定义别名表
# ---------------------------------------------------------------

DEFAULT_ALIASES: dict[str, str] = {
    # 退出/帮助
    "q": "quit",
    "exit": "quit",
    "h": "help",
    "?": "help",

    # 探索
    "l": "look",
    "look": "look",
    "n": "next",
    "next": "next",
    "r": "read",

    # 背包
    "i": "inventory",
    "inv": "inventory",

    # 谜题
    "hint": "hint",
    "hints": "hint",

    # 存档
    "save": "save",
    "load": "load",

    # 战斗
    "a": "attack",
    "d": "defend",
    "use": "use",
    "c": "card",

    # 移动
    "north": "go",
    "south": "go",
    "east": "go",
    "west": "go",
    "up": "go",
    "down": "go",
    "w": "go",
    "s": "go",
    "e": "go",
    "nw": "go",
    "ne": "go",
    "sw": "go",
    "se": "go",
}


# ---------------------------------------------------------------
# CommandResult
# ---------------------------------------------------------------

class CommandResult:
    """命令执行结果。

    Attributes:
        success: 是否成功执行
        message: 反馈消息
        data: 附加数据
        next_action: 建议的后续动作（可选）
    """

    def __init__(
        self,
        success: bool,
        message: str = "",
        data: Any = None,
        next_action: str = "",
    ):
        self.success = success
        self.message = message
        self.data = data
        self.next_action = next_action

    def __repr__(self) -> str:
        status = "OK" if self.success else "FAIL"
        parts = [f"CommandResult({status}"]
        if self.message:
            parts.append(f": {self.message}")
        parts.append(")")
        return "".join(parts)

    def __bool__(self) -> bool:
        return self.success

    def to_dict(self) -> dict:
        """转为可序列化字典。"""
        return {
            "success": self.success,
            "message": self.message,
            "data": self.data,
            "next_action": self.next_action,
        }

    @classmethod
    def ok(cls, message: str = "", data: Any = None) -> "CommandResult":
        """快捷创建成功结果。"""
        return cls(True, message, data)

    @classmethod
    def fail(cls, message: str = "", data: Any = None) -> "CommandResult":
        """快捷创建失败结果。"""
        return cls(False, message, data)


# ---------------------------------------------------------------
# CommandParser
# ---------------------------------------------------------------

class CommandParser:
    """文本命令解析器。

    解析原始输入字符串为 (command_name, arguments) 元组。
    支持别名系统，可动态添加/移除别名。

    使用方式:

        parser = CommandParser()
        parser.parse("l north")   # → ("look", ["north"])
        parser.parse("q")         # → ("quit", [])
        parser.parse("")          # → ("", [])
    """

    def __init__(self, aliases: dict[str, str] | None = None):
        self._aliases: dict[str, str] = {}
        # 默认别名
        self._aliases.update(DEFAULT_ALIASES)
        # 合并自定义别名
        if aliases:
            self._aliases.update(aliases)

    # ---- 别名管理 ----

    def add_alias(self, alias: str, command: str) -> None:
        """添加命令别名。

        :param alias: 简称（如 "q"）
        :param command: 目标命令名（如 "quit"）
        """
        self._aliases[alias.lower()] = command

    def remove_alias(self, alias: str) -> bool:
        """移除命令别名。"""
        if alias.lower() in self._aliases:
            del self._aliases[alias.lower()]
            return True
        return False

    def get_alias(self, alias: str) -> Optional[str]:
        """查询别名对应的命令名。"""
        return self._aliases.get(alias.lower())

    @property
    def aliases(self) -> dict[str, str]:
        """返回所有别名（只读副本）。"""
        return dict(self._aliases)

    # ---- 解析 ----

    def parse(self, raw_input: str) -> tuple[str, list[str]]:
        """解析原始输入为 (command_name, args)。

        :param raw_input: 用户输入的原始字符串
        :returns:
            - ("", []) — 空输入
            - ("quit", []) — 别名解析后的命令
            - ("unknown_cmd", [raw_parts...]) — 未识别的命令保留原样
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

    def parse_with_raw(self, raw_input: str) -> tuple[str, list[str], str]:
        """解析并保留原始命令词。

        Returns:
            (resolved_command, args, raw_command)
        """
        text = raw_input.strip()
        if not text:
            return ("", [], "")
        parts = text.split(None, 1)
        raw_cmd = parts[0].lower()
        args_str = parts[1] if len(parts) > 1 else ""
        args = args_str.split() if args_str else []
        resolved = self._aliases.get(raw_cmd, raw_cmd)
        return (resolved, args, raw_cmd)

    def is_quit(self, raw_input: str) -> bool:
        """检查输入是否为退出命令。"""
        cmd, _ = self.parse(raw_input)
        return cmd == "quit"


# ---------------------------------------------------------------
# CommandHandler
# ---------------------------------------------------------------

class CommandHandler:
    """中央命令分发器。

    将 CommandParser 解析的结果路由到注册的处理器函数。
    支持上下文注入，处理器可访问游戏状态等共享数据。

    使用方式:

        handler = CommandHandler()
        handler.set_context(world=world, player=player)
        handler.register("look", lambda args, ctx: look_room(args, ctx))
        result = handler.execute("look", ["north"])
    """

    def __init__(self):
        self._handlers: dict[str, Callable[..., Any]] = {}
        self._context: dict[str, Any] = {}
        self._result_history: list[CommandResult] = []

    # ---- 上下文 ----

    def set_context(self, **kwargs: Any) -> None:
        """设置处理器可访问的共享上下文。

        典型用法::
            handler.set_context(world=world, player=player, event_bus=event_bus)
        """
        self._context.update(kwargs)

    def get_context(self, key: str) -> Any:
        """获取上下文值。"""
        return self._context.get(key)

    def clear_context(self) -> None:
        """清空所有上下文。"""
        self._context.clear()

    # ---- 注册 ----

    def register(self, name: str, handler: Callable[..., Any]) -> None:
        """注册命令处理器。

        :param name: 命令名（不区分大小写）
        :param handler: 处理器函数，签名为 handler(args: list[str], context: dict) -> Any

        handler 返回:
            - CommandResult: 直接作为结果
            - str: 转换为 CommandResult(True, str)
            - None: 转换为 CommandResult(True, "")
            - 其他: 转换为 CommandResult(True, repr(result))
        """
        self._handlers[name.lower()] = handler

    def unregister(self, name: str) -> bool:
        """移除命令处理器。"""
        if name.lower() in self._handlers:
            del self._handlers[name.lower()]
            return True
        return False

    def has_handler(self, name: str) -> bool:
        """检查命令是否已注册处理器。"""
        return name.lower() in self._handlers

    def get_all_commands(self) -> list[str]:
        """返回所有已注册命令名。"""
        return list(self._handlers.keys())

    # ---- 执行 ----

    def execute(self, cmd_name: str, args: list[str] | None = None) -> CommandResult:
        """执行命令。

        :param cmd_name: 命令名
        :param args: 参数列表
        :returns: CommandResult
        """
        args = args or []
        handler = self._handlers.get(cmd_name.lower())
        if not handler:
            result = CommandResult(False, f"未知命令: {cmd_name}")
            self._result_history.append(result)
            return result

        try:
            result = handler(args, self._context)
        except Exception as e:
            result = CommandResult(False, f"命令执行错误 ({type(e).__name__}): {e}")
            self._result_history.append(result)
            return result

        # 标准化返回值
        if isinstance(result, CommandResult):
            final = result
        elif isinstance(result, str):
            final = CommandResult(True, result)
        elif result is None:
            final = CommandResult(True, "")
        else:
            final = CommandResult(True, repr(result), data=result)

        self._result_history.append(final)
        return final

    @property
    def last_result(self) -> Optional[CommandResult]:
        """获取最近一次执行结果。"""
        return self._result_history[-1] if self._result_history else None

    @property
    def result_history(self) -> list[CommandResult]:
        """返回结果历史。"""
        return list(self._result_history)
