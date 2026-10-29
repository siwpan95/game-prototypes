"""
事件总线 — 改进版本
=====================
添加错误处理、防止递归、事件日志。
"""

from typing import Any, Callable, Dict, List, Optional, Set


# 类型别名
EventHandler = Callable[[Any], None]


class EventBus:
    """
    事件总线 — 松耦合的系统间通信。

    改进点：
        - 错误处理：单个回调失败不影响其他回调
        - 防止递归：检测并阻止事件递归爆炸
        - 安全遍历：复制监听器列表，支持动态订阅/取消订阅
        - 可选日志：调试模式下记录所有事件
    """

    def __init__(self, debug: bool = False) -> None:
        """
        初始化事件总线。

        参数：
            debug: 是否启用事件日志（默认 False）
        """
        self.listeners: Dict[str, List[EventHandler]] = {}
        self.debug = debug
        self._recursion_guard: Set[str] = set()  # 递归检测
        self._max_recursion_depth = 5  # 最大递归深度
        self._event_log: List[Dict[str, Any]] = []  # 事件日志
        self._log_max_size = 1000  # 日志最大长度

    def subscribe(self, event_type: str, callback: Optional[EventHandler] = None):
        """
        订阅事件。支持两种用法：

        用法 1 - 直接调用：
            bus.subscribe('EVENT', handler)

        用法 2 - 装饰器：
            @bus.subscribe('EVENT')
            def handler(data):
                ...

        参数：
            event_type: 事件类型字符串
            callback: 事件处理函数（可选，用于装饰器模式）

        返回：
            装饰器或 callback
        """
        if callback is None:
            # 装饰器模式
            def decorator(func: EventHandler) -> EventHandler:
                self.listeners.setdefault(event_type, []).append(func)
                return func
            return decorator

        # 直接调用模式
        self.listeners.setdefault(event_type, []).append(callback)
        return callback

    def unsubscribe(self, event_type: str, callback: EventHandler) -> None:
        """
        取消订阅。

        参数：
            event_type: 事件类型字符串
            callback: 要移除的回调函数
        """
        if event_type in self.listeners:
            try:
                self.listeners[event_type].remove(callback)
                # 清理空列表
                if not self.listeners[event_type]:
                    del self.listeners[event_type]
            except ValueError:
                pass  # 回调函数未注册

    def emit(self, event_type: str, data: Any = None) -> None:
        """
        发射事件 — 通知所有监听器。

        改进点：
            - 复制监听器列表，支持动态修改
            - 错误处理，单个回调失败不影响其他回调
            - 递归检测，防止事件死循环

        参数：
            event_type: 事件类型字符串
            data: 事件数据（任意类型）
        """
        # 递归检测
        if event_type in self._recursion_guard:
            if self.debug:
                print(f"[EventBus] ⚠️ 递归检测：{event_type} 正在处理中，跳过")
            return

        # 记录事件日志
        if self.debug:
            self._log_event(event_type, data)

        # 复制监听器列表（防止遍历时修改）
        listeners = list(self.listeners.get(event_type, []))

        if not listeners:
            return

        # 递归保护入栈
        self._recursion_guard.add(event_type)

        try:
            for cb in listeners:
                try:
                    cb(data)
                except Exception as e:
                    # 单个回调失败不影响其他回调
                    print(f"[EventBus] ❌ 事件 {event_type} 回调失败: {e}")
                    if self.debug:
                        import traceback
                        traceback.print_exc()
        finally:
            # 递归保护出栈
            self._recursion_guard.discard(event_type)

    def clear(self, event_type: Optional[str] = None) -> None:
        """
        清除监听器。

        参数：
            event_type: 要清除的事件类型（None 表示清除所有）
        """
        if event_type:
            self.listeners.pop(event_type, None)
        else:
            self.listeners.clear()

    def has_listeners(self, event_type: str) -> bool:
        """
        检查是否有监听器订阅了指定事件。

        参数：
            event_type: 事件类型字符串

        返回：
            是否有监听器
        """
        return (event_type in self.listeners and
                len(self.listeners[event_type]) > 0)

    def listener_count(self, event_type: str) -> int:
        """
        返回指定事件的监听器数量。

        参数：
            event_type: 事件类型字符串

        返回：
            监听器数量
        """
        return len(self.listeners.get(event_type, []))

    def _log_event(self, event_type: str, data: Any) -> None:
        """
        记录事件到日志（调试用）。

        参数：
            event_type: 事件类型
            data: 事件数据
        """
        import time
        entry = {
            "time": time.time(),
            "event_type": event_type,
            "data": repr(data) if data else None,
        }
        self._event_log.append(entry)

        # 限制日志大小
        if len(self._event_log) > self._log_max_size:
            self._event_log = self._event_log[-self._log_max_size // 2:]

    def get_log(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        获取事件日志。

        参数：
            limit: 返回最后 N 条记录（None 表示全部）

        返回：
            日志记录列表
        """
        if limit is None:
            return self._event_log
        return self._event_log[-limit:]

    def clear_log(self) -> None:
        """清除事件日志。"""
        self._event_log.clear()

    def enable_debug(self) -> None:
        """启用调试日志。"""
        self.debug = True

    def disable_debug(self) -> None:
        """禁用调试日志。"""
        self.debug = False

    def __repr__(self) -> str:
        total = sum(len(v) for v in self.listeners.values())
        return f"EventBus({len(self.listeners)} events, {total} listeners)"
