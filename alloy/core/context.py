"""
可逆装配内核 — Context（注册即回滚）
====================================

源自 Cordis 的三个核心算子，为 alloy 提供声明式装配：

    provide(key, service, *, dispose=None)   注册服务，注册动作压入 dispose 栈
    get(key, default=...)                    依赖查找，缺失即装配期报错
    effect(fn)                               注册可逆副作用，随上下文销毁自动撤销

另外提供插件安装（install）、单服务卸载（unload）、fork 双作用域
（fork / fork_install / scopes：命名子作用域 + reusable 语义，
对齐 Cordis fork 事件与 reusable 插件）。

设计约定：
    - dispose 栈按注册逆序回滚（后注册先销毁），与 Cordis 语义一致；
    - 重复 provide 同一 key 默认抛 DuplicateServiceError，可用 replace=True 覆盖；
    - install(plugin) 按 name/inject/apply 协议装配，inject 缺失在装配期报错；
    - 纯标准库实现，零第三方依赖。
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple

__all__ = [
    "Context",
    "DuplicateScopeError",
    "DuplicateServiceError",
    "MissingDependencyError",
]

_MISSING = object()

# 条目类型：(key, disposer)；key 为 None 表示匿名副作用（effect）
_Entry = Tuple[Optional[str], Optional[Callable[[], Any]]]


class DuplicateScopeError(RuntimeError):
    """同一父上下文中重复 fork 同名作用域。"""

    def __init__(self, name: str):
        super().__init__(f"作用域已存在: '{name}'（重复 fork）。先 dispose 或换名")


class DuplicateServiceError(RuntimeError):
    """同一上下文内重复提供同名服务。"""

    def __init__(self, key: str):
        super().__init__(f"服务已注册: '{key}'（重复 provide）。如需覆盖请使用 replace=True")


class MissingDependencyError(RuntimeError):
    """插件要求的依赖服务不存在。"""

    def __init__(self, key: str, context: "Context" = None):
        hint = f"（已注册: {sorted(context.keys())}）" if context is not None else ""
        super().__init__(f"缺少依赖服务: '{key}' {hint}")


class Context:
    """
    服务注册表 + 可逆副作用栈。

    用法::

        ctx = Context()
        ctx.provide("world", World(), dispose=world.clear)
        ctx.effect(lambda: print("undo"))
        ctx.get("world")          # -> World 实例
        ctx.install(my_plugin)    # 按 name/inject/apply 协议装配
        ctx.dispose()             # 逆序回滚全部注册
    """

    def __init__(self, parent: Optional["Context"] = None):
        self._parent = parent
        self._services: Dict[str, Any] = {}
        self._entries: List[_Entry] = []
        self._disposed = False
        self._children: List["Context"] = []
        self._name: Optional[str] = None
        self._outer_done: set = set()
        self._fork_seq: Dict[str, int] = {}

    # ── 注册 ──────────────────────────────────────────

    def provide(self, key: str, service: Any, *, dispose: Optional[Callable[[], Any]] = None,
                replace: bool = False) -> Any:
        """注册服务；可附带 disposer（卸载/销毁时调用）。返回 service 便于链式赋值。"""
        self._ensure_live()
        if key in self._services and not replace:
            raise DuplicateServiceError(key)
        if key in self._services and replace:
            self.unload(key)
        self._services[key] = service
        self._entries.append((key, dispose))
        return service

    def effect(self, fn: Callable[[], Any]) -> None:
        """注册匿名可逆副作用：上下文销毁时逆序执行。"""
        self._ensure_live()
        if not callable(fn):
            raise TypeError("effect 需要可调用对象")
        self._entries.append((None, fn))

    # ── 查找 ──────────────────────────────────────────

    def has(self, key: str) -> bool:
        """本上下文或其父链上是否存在服务。"""
        if key in self._services:
            return True
        return self._parent.has(key) if self._parent is not None else False

    def get(self, key: str, default: Any = _MISSING) -> Any:
        """按 key 查找服务：先本层、再父链；缺失且无 default 时抛 MissingDependencyError。"""
        if key in self._services:
            return self._services[key]
        if self._parent is not None:
            value = self._parent.get(key, _MISSING)
            if value is not _MISSING:
                return value
        if default is _MISSING:
            raise MissingDependencyError(key, self)
        return default

    def keys(self) -> List[str]:
        """本层注册的所有 key（不含父链）。"""
        return list(self._services.keys())

    def parent(self) -> Optional["Context"]:
        return self._parent

    @property
    def name(self) -> Optional[str]:
        """fork 作用域名（顶层或匿名 child 为 None）。"""
        return self._name

    # ── 插件 ──────────────────────────────────────────

    def install(self, plugin: Any, config: Any = None) -> "Context":
        """按插件协议装配：name（标识）+ inject（依赖 key 列表）+ apply(ctx, config)。

        apply 若返回可调用对象，则视为该插件的统一 disposer，随上下文销毁执行。
        """
        self._ensure_live()
        name = getattr(plugin, "name", None) or plugin.__class__.__name__
        inject = list(getattr(plugin, "inject", None) or [])
        missing = [k for k in inject if not self.has(k)]
        if missing:
            raise MissingDependencyError(
                f"插件 '{name}' 缺少依赖: {missing}（已注册: {sorted(self.keys())}）")
        result = plugin.apply(self, {} if config is None else config)
        if callable(result):
            self.effect(result)
        return self

    # ── 卸载 / 销毁 ───────────────────────────────────

    def unload(self, key: str) -> bool:
        """只回滚指定 key 的注册：逆序执行其 disposer 并移除服务。未注册返回 False。"""
        if key not in self._services:
            return False
        for k, disp in reversed(self._entries):
            if k == key and disp is not None:
                disp()
        self._entries = [(k, d) for k, d in self._entries if k != key]
        del self._services[key]
        return True

    def dispose(self) -> None:
        """销毁本上下文：按注册逆序回滚全部 effect/disposer，并递归销毁子上下文。

        幂等；单个 disposer 抛异常不中断其余回滚（与 EventBus 容错口径一致）；
        fork 作用域销毁后自动从父上下文摘除（反复 fork/mount 不累积）。
        """
        if self._disposed:
            return
        for child in list(self._children):
            child.dispose()
        for _, disp in reversed(self._entries):
            if disp is None:
                continue
            try:
                disp()
            except Exception:
                pass  # 容错：记录到 debug 日志的责任在调用方
        self._entries.clear()
        self._services.clear()
        self._disposed = True
        if self._parent is not None and self in self._parent._children:
            self._parent._children.remove(self)

    def child(self) -> "Context":
        """创建匿名子作用域：查找沿父链向上，销毁只回滚自身注册。

        fork(name=None) 的等价形式；命名作用域请用 fork()。
        """
        return self.fork(None)

    # ── fork 双作用域（Cordis fork / reusable 语义） ────────

    def fork(self, name: Optional[str] = None) -> "Context":
        """创建命名 fork 作用域（对齐 Cordis fork 事件）。

        - 服务查找沿父链向上（get/has 已支持）；注册/effect 只落本层；
        - 同层 provide 可遮蔽父层同名服务（shadow），父层不受影响；
        - dispose 逆序回滚本层全部副作用，并自动从父上下文摘除——
          同一名称可反复 fork，多实例玩法复用（每个实例独立回收）；
        - 同名作用域未销毁时重复 fork 抛 DuplicateScopeError，防作用域混叠。
        """
        self._ensure_live()
        if name is not None and any(c._name == name for c in self._children):
            raise DuplicateScopeError(name)
        child = Context(parent=self)
        child._name = name
        self._children.append(child)
        return child

    def fork_install(self, plugin: Any, config: Any = None, *,
                     name: Optional[str] = None) -> "Context":
        """reusable/fork 双作用域装配：outer 只执行一次，apply 每次落独立 fork。

        - 插件若提供 outer(ctx) 钩子（可重用外作用域：共享状态、一次性注册），
          按插件 name 在**本上下文**去重执行，其副作用挂本上下文；
        - apply(ctx, config) 每次调用都在新建的 fork 作用域内装配，
          返回该 fork——同一插件可多实例并存，实例副作用随各自 fork 独立回收。
        """
        self._ensure_live()
        pname = getattr(plugin, "name", None) or plugin.__class__.__name__
        outer = getattr(plugin, "outer", None)
        if callable(outer) and pname not in self._outer_done:
            outer(self)
            self._outer_done.add(pname)
        seq = self._fork_seq.get(pname, 0) + 1
        self._fork_seq[pname] = seq
        scope = name if name is not None else f"{pname}#{seq}"
        fork = self.fork(scope)
        fork.install(plugin, config)
        return fork

    def scopes(self) -> List[Tuple[Optional[str], "Context"]]:
        """当前存活的子作用域（fork）清单：[(name, child), ...]。"""
        return [(c._name, c) for c in self._children]

    # ── 内部 ──────────────────────────────────────────

    def _ensure_live(self) -> None:
        if self._disposed:
            raise RuntimeError("Context 已销毁，不能再注册服务")

    def __contains__(self, key: str) -> bool:
        return self.has(key)

    def __repr__(self) -> str:
        name = f" name={self._name!r}" if self._name is not None else ""
        return (f"<Context{name} keys={sorted(self.keys())} "
                f"parent={'yes' if self._parent else 'no'}>")
