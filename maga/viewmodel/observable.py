"""Observable 属性 — Tkinter Variable 包装器"""
import tkinter as tk
from typing import Any, Callable


class ObservableProperty:
    """基于 Tkinter Variable 的可观察属性，支持绑定和变更通知"""

    _tk_var_types = {
        str: tk.StringVar,
        int: tk.IntVar,
        float: tk.DoubleVar,
        bool: tk.BooleanVar,
    }

    def __init__(self, value: Any, name: str = ""):
        self._name = name
        var_type = self._tk_var_types.get(type(value), tk.StringVar)
        self._var = var_type(value=str(value) if var_type is tk.StringVar else value)
        self._listeners = []

    @property
    def tk_var(self):
        """返回底层 Tkinter Variable，可直接用于 textvariable="""
        return self._var

    def get(self) -> Any:
        return self._var.get()

    def set(self, value: Any):
        current = self._var.get()
        if current != value:
            self._var.set(value)

    def on_change(self, callback: Callable):
        """注册变更回调"""
        self._var.trace_add("write", lambda *_: callback(self.get()))


def observable(value: Any) -> ObservableProperty:
    """快捷工厂函数"""
    return ObservableProperty(value)
