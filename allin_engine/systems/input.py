"""
输入管理器 — 统一多输入源抽象。

支持 CLI、Pygame、Tkinter 三种输入源，可插拔切换。
管理输入历史与命令映射。

使用方式:

    im = InputManager()
    im.add_source("cli", CLIInputSource())
    im.set_active_source("cli")
    cmd = im.get_command()  # ("look", ["north"])
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import deque
from typing import Optional


# ---------------------------------------------------------------
# 抽象输入源
# ---------------------------------------------------------------

class InputSource(ABC):
    """抽象输入源基类。"""

    @abstractmethod
    def poll(self) -> Optional[str]:
        """
        轮询输入，返回原始字符串或 None（无输入）。

        CLI 模式下阻塞等待；GUI 模式下非阻塞返回 None。
        """
        ...

    @abstractmethod
    def start(self) -> None:
        """初始化输入源。"""
        ...

    @abstractmethod
    def stop(self) -> None:
        """清理输入源资源。"""
        ...

    @property
    @abstractmethod
    def is_ready(self) -> bool:
        """输入源是否就绪可用。"""
        ...


class CLIInputSource(InputSource):
    """标准输入/输出（终端）输入源。

    poll() 阻塞等待用户输入。
    """

    def __init__(self, prompt: str = "> "):
        self._prompt = prompt
        self._ready = True

    def start(self) -> None:
        self._ready = True

    def stop(self) -> None:
        self._ready = False

    def poll(self) -> Optional[str]:
        """阻塞等待一行输入，返回去除首尾空白后的字符串。"""
        if not self._ready:
            return None
        try:
            raw = input(self._prompt)
            return raw.strip() if raw.strip() else None
        except (EOFError, KeyboardInterrupt):
            return None

    @property
    def is_ready(self) -> bool:
        return self._ready


class PygameInputSource(InputSource):
    """Pygame 事件输入源。

    poll() 从事件队列中提取键盘输入的文本。
    需在主循环中先调用 feed_event() 投喂 KEYDOWN 事件。
    """

    def __init__(self):
        self._ready = True
        self._buffer: list[str] = []
        self._current_line: str = ""

    def start(self) -> None:
        self._ready = True

    def stop(self) -> None:
        self._ready = False

    def feed_event(self, event) -> None:
        """投喂 Pygame 事件。"""
        import pygame
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_RETURN:
                if self._current_line.strip():
                    self._buffer.append(self._current_line.strip())
                self._current_line = ""
            elif event.key == pygame.K_BACKSPACE:
                self._current_line = self._current_line[:-1]
            elif event.unicode and event.unicode.isprintable():
                self._current_line += event.unicode

    def poll(self) -> Optional[str]:
        """从缓冲区取出最早的一行输入。"""
        if not self._ready:
            return None
        if self._buffer:
            return self._buffer.pop(0)
        return None

    @property
    def is_ready(self) -> bool:
        return self._ready


class TkinterInputSource(InputSource):
    """Tkinter GUI 输入源。

    通过 Tkinter Entry 组件接收输入，poll() 从缓冲队列取出行文本。
    """

    def __init__(self):
        self._ready = True
        self._buffer: list[str] = []
        self._entry: object = None  # tkinter.Entry

    def start(self) -> None:
        self._ready = True

    def stop(self) -> None:
        self._ready = False

    def bind_entry(self, entry: object) -> None:
        """绑定 Tkinter Entry 组件。

        :param entry: tkinter.Entry 实例
        """
        self._entry = entry
        entry.bind("<Return>", self._on_enter)

    def _on_enter(self, event) -> None:
        """回车回调，将 Entry 内容放入缓冲区。"""
        if self._entry is None:
            return
        text = self._entry.get().strip()
        if text:
            self._buffer.append(text)
        self._entry.delete(0, "end")

    def poll(self) -> Optional[str]:
        """从缓冲区取出最早的一行输入。"""
        if not self._ready:
            return None
        if self._buffer:
            return self._buffer.pop(0)
        return None

    @property
    def is_ready(self) -> bool:
        return self._ready


# ---------------------------------------------------------------
# 输入管理器
# ---------------------------------------------------------------

class InputManager:
    """管理多个输入源，支持运行时切换。

    特性：
    - 多输入源注册与切换
    - 输入历史（可回溯）
    - 命令键位映射（用于 GUI 快捷键）
    """

    def __init__(self, max_history: int = 100):
        self._sources: dict[str, InputSource] = {}
        self._active_source: str = ""
        self._history: deque[str] = deque(maxlen=max_history)
        self._command_map: dict[str, str] = {}
        # 默认命令映射
        self._command_map.update({
            "KEY_UP": "look north",
            "KEY_DOWN": "look south",
            "KEY_LEFT": "look west",
            "KEY_RIGHT": "look east",
            "KEY_ESCAPE": "quit",
            "KEY_I": "inventory",
            "KEY_M": "map",
        })

    # ---- 输入源管理 ----

    def add_source(self, name: str, source: InputSource) -> None:
        """注册输入源。"""
        self._sources[name] = source
        if not self._active_source:
            self._active_source = name

    def remove_source(self, name: str) -> bool:
        """移除输入源。"""
        if name in self._sources:
            if self._active_source == name:
                self._active_source = ""
            self._sources[name].stop()
            del self._sources[name]
            return True
        return False

    def set_active_source(self, name: str) -> bool:
        """切换活跃输入源。"""
        if name not in self._sources:
            return False
        if self._active_source and self._active_source != name:
            # 不停止旧源，只标记切换
            pass
        self._active_source = name
        self._sources[name].start()
        return True

    def get_active_source(self) -> Optional[InputSource]:
        """获取当前活跃输入源。"""
        if self._active_source:
            return self._sources.get(self._active_source)
        return None

    def start_all(self) -> None:
        """启动所有已注册输入源。"""
        for src in self._sources.values():
            src.start()

    def stop_all(self) -> None:
        """停止所有输入源。"""
        for src in self._sources.values():
            src.stop()

    # ---- 输入获取 ----

    def get_raw_input(self) -> Optional[str]:
        """从活跃源获取一行原始输入。"""
        src = self.get_active_source()
        if src is None:
            return None
        text = src.poll()
        if text:
            self._history.append(text)
        return text

    def get_command(self) -> tuple[str, list[str]]:
        """获取输入并尝试通过命令映射解析。

        Returns:
            (command_name, args) 或 ("", []) 表示空输入
        """
        raw = self.get_raw_input()
        if raw is None:
            return ("", [])
        # 先检查命令映射
        if raw in self._command_map:
            mapped = self._command_map[raw]
            parts = mapped.split(None, 1)
            cmd = parts[0].lower()
            args = parts[1].split() if len(parts) > 1 else []
            return (cmd, args)
        # 普通输入
        parts = raw.split(None, 1)
        cmd = parts[0].lower()
        args = parts[1].split() if len(parts) > 1 else []
        return (cmd, args)

    # ---- 输入历史 ----

    def get_history(self, n: int = 1) -> list[str]:
        """获取最近 n 条输入历史。"""
        items = list(self._history)
        return items[-n:] if n > 0 else []

    def get_last_input(self) -> Optional[str]:
        """获取上一条输入。"""
        return self._history[-1] if self._history else None

    def clear_history(self) -> None:
        """清空输入历史。"""
        self._history.clear()

    @property
    def history(self) -> list[str]:
        """返回完整历史列表。"""
        return list(self._history)

    # ---- 命令映射 ----

    def add_command_map(self, key: str, command: str) -> None:
        """注册命令映射（用于 GUI 快捷键翻译）。"""
        self._command_map[key] = command

    def remove_command_map(self, key: str) -> bool:
        """移除命令映射。"""
        if key in self._command_map:
            del self._command_map[key]
            return True
        return False

    @property
    def command_map(self) -> dict[str, str]:
        return dict(self._command_map)
