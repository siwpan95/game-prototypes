"""tkinter 测试桩 — 供无 GUI 环境下的 VM 冒烟测试使用。

本机托管 Python 不含 tkinter，GUI 无法本地启动（环境限制）。
测试时调用 install() 把本模块注册为 sys.modules["tkinter"]，
即可在无显示环境创建 StringVar/BooleanVar 等对象并驱动 GameViewModel。

仅实现 VM/View 用到的 API 子集：变量类、Tk（after/bind/title/geometry/
resizable/config/mainloop/quit）。
"""
import sys
import types


class _Var:
    """Tkinter 变量最小实现（get/set/trace_add）"""

    def __init__(self, master=None, value="", name=""):
        self._value = value
        self._callbacks = []

    def get(self):
        return self._value

    def set(self, value):
        if value != self._value:
            self._value = value
            for cb in list(self._callbacks):
                cb()

    def trace_add(self, mode, callback):
        # 简化：任何写操作都触发（不区分 read/write/unset）
        self._callbacks.append(callback)

    def trace_remove(self, mode, cbname):
        self._callbacks = [cb for cb in self._callbacks if getattr(cb, "__name__", "") != cbname]

    def trace_info(self):
        return []


class StringVar(_Var):
    def __init__(self, master=None, value="", name=""):
        super().__init__(master, "" if value is None else str(value), name)


class IntVar(_Var):
    def __init__(self, master=None, value=0, name=""):
        super().__init__(master, int(value), name)


class DoubleVar(_Var):
    def __init__(self, master=None, value=0.0, name=""):
        super().__init__(master, float(value), name)


class BooleanVar(_Var):
    def __init__(self, master=None, value=False, name=""):
        super().__init__(master, bool(value), name)


class Tk:
    """Tk 根窗口最小实现：after 不真正循环（记录待执行回调由测试自行驱动）"""

    def __init__(self):
        self._after_id = 0
        self._scheduled = {}
        self._bindings = {}

    def after(self, ms, func=None, *args):
        self._after_id += 1
        self._scheduled[self._after_id] = (func, args)
        return self._after_id

    def run_pending_after(self, times=1):
        """测试辅助：手动触发 after 注册的回调（模拟游戏循环 tick）"""
        for _ in range(times):
            pending = dict(self._scheduled)
            self._scheduled.clear()
            for func, args in pending.values():
                if func:
                    func(*args)

    def bind(self, sequence, func, add=None):
        self._bindings.setdefault(sequence, []).append(func)

    def unbind(self, sequence):
        self._bindings.pop(sequence, None)

    def config(self, **kwargs):
        pass

    def title(self, text):
        pass

    def geometry(self, spec):
        pass

    def resizable(self, width=True, height=True):
        pass

    def mainloop(self, n=0):
        pass

    def quit(self):
        pass

    def destroy(self):
        pass


def install():
    """把本桩注册为 sys.modules['tkinter']（在导入 viewmodel/view 之前调用）"""
    if "tkinter" in sys.modules and getattr(sys.modules["tkinter"], "__is_stub__", False):
        return sys.modules["tkinter"]
    mod = types.ModuleType("tkinter")
    mod.__is_stub__ = True
    mod.StringVar = StringVar
    mod.IntVar = IntVar
    mod.DoubleVar = DoubleVar
    mod.BooleanVar = BooleanVar
    mod.Tk = Tk
    # View 层还会 from tkinter import messagebox / simpledialog，
    # 冒烟测试不实例化 View，这里给个占位避免 import 失败
    mod.messagebox = types.SimpleNamespace(
        showinfo=lambda *a, **k: None,
        showwarning=lambda *a, **k: None,
        showerror=lambda *a, **k: None,
    )
    mod.simpledialog = types.SimpleNamespace(
        askinteger=lambda *a, **k: None,
        askstring=lambda *a, **k: None,
    )
    sys.modules["tkinter"] = mod
    # tkinter.ttk / tkinter.font 等子模块占位
    for sub in ("ttk", "font", "filedialog"):
        if f"tkinter.{sub}" not in sys.modules:
            sys.modules[f"tkinter.{sub}"] = types.ModuleType(f"tkinter.{sub}")
    return mod
