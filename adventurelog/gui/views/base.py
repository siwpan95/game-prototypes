# -*- coding: utf-8 -*-
"""视图基类与视图栈 — 借鉴 pq2 的 View 栈管理设计"""

from __future__ import annotations
from typing import List, Optional, Callable
from abc import ABC, abstractmethod


# ── 消息类型：视图间通信 ──
MSG_QUIT    = "quit"       # 退出游戏
MSG_NEW     = "new"        # 新游戏 / 开始探索
MSG_CANCEL  = "cancel"     # 取消当前操作
MSG_START   = "start"      # 开始冒险
MSG_LOAD    = "load"       # 加载存档
MSG_BACK    = "back"       # 返回上一视图

# MessageHandler = Callable[[str, Optional[dict]], None]
MessageHandler = Callable


class View(ABC):
    """视图基类 — 类似 pq2 的 View

    每个视图有 Show/Hide/Close 生命周期。
    通过 message_handler 回调与 ViewStack 通信。
    """

    def __init__(self, name: str, message_handler: Optional[MessageHandler] = None):
        self.name = name
        self.message_handler = message_handler

    @abstractmethod
    def show(self):
        """显示视图"""
        ...

    @abstractmethod
    def hide(self):
        """隐藏视图"""
        ...

    def close(self):
        """关闭视图（清理资源）"""
        pass

    def send_message(self, msg: str, data: dict = None):
        """向 ViewStack 发送消息"""
        if self.message_handler:
            self.message_handler(msg, data or {})


class ViewStack:
    """视图栈管理器 — 借鉴 pq2 的 GUI 基类

    使用栈管理视图导航：
    - push(view): 将新视图入栈并显示
    - pop(): 关闭当前视图，回到上一视图
    - pop_all(): 清空栈回到根视图

    内置消息路由：
    - "back" → pop()
    - "quit" → 传递给根处理
    - 自定义消息由子类或宿主处理
    """

    def __init__(self, root_message_handler: Optional[MessageHandler] = None):
        self._stack: List[View] = []
        self._root_handler = root_message_handler

    @property
    def current(self) -> Optional[View]:
        return self._stack[-1] if self._stack else None

    @property
    def depth(self) -> int:
        return len(self._stack)

    def push(self, view: View):
        """将视图入栈，隐藏当前视图后显示新视图"""
        if self._stack:
            self._stack[-1].hide()

        view.message_handler = self._route_message
        self._stack.append(view)
        view.show()

    def pop(self):
        """弹出当前视图，显示上一视图"""
        if not self._stack:
            return

        view = self._stack.pop()
        view.hide()
        view.close()

        if self._stack:
            self._stack[-1].show()

    def pop_all(self):
        """清空视图栈（回到根）"""
        while self._stack:
            view = self._stack.pop()
            view.hide()
            view.close()

    def _route_message(self, msg: str, data: dict):
        """内部消息路由"""
        if msg == MSG_BACK:
            self.pop()
        else:
            # 传递给根处理器
            if self._root_handler:
                self._root_handler(msg, data)
