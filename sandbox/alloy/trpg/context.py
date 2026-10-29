"""alloy.trpg.context - TRPG 规则内核的装配上下文（D20 → alloy 适配层）

并入背景（R2，2026-08-27）：
    D20（G:\\local\\D20，D&D-GURPS 变体角色构建器）自带一套 mini-Cordis
    （Context + EventBus + effect 栈）。并入 alloy 后，规则内核不再自带容器：

    - 服务容器 / 可逆副作用：复用 alloy.core.context.Context（get/has/provide/
      effect/dispose 原语齐全，注册即回滚）；
    - 事件：骑在 alloy.core.event_bus.EventBus 上——宿主已提供 'bus' 服务则共享
      同一条总线（TRPG 事件与引擎事件同一名字空间），否则提供独立 EventBus；
    - 本模块只保留 D20 语义中 alloy 缺失的两块：``ctx.<service>`` 属性代理与
      emit/waterfall/serial/parallel 的 D20 兼容分发，外加 Service 插件基类。

事件语义对照（D20 → alloy）：
    emit      —— 观察型：bus.emit(name, data)，忽略返回值（D20 同）
    waterfall —— 中间件链：bus.waterfall(name, seed)，监听签名 (value, next)（D20 同）
    serial    —— D20 为「按序执行 + 逐个 await 协程」，alloy 为「首个非 None 短路投票」。
                 内核未用 serial，此处保留 D20 原语义（直接遍历 bus.listeners 实现）
    parallel  —— alloy 无此语义，保留 D20 原语义（asyncio.gather 扇出）

生命周期：TrpgContext 构造时把 self.dispose 挂到宿主 alloy Context 的 effect 栈
（注册即回滚），宿主销毁时自动回收；Character 也可显式 dispose()。

与 D20 mini-Cordis 的刻意差异：
    - 重复 provide 同一 key 抛 DuplicateServiceError（D20 静默覆盖）——fail loud；
    - effect(fn) 沿用 D20 语义：立即执行装配体、收集返回值与期间 on() 的 disposer。
"""

from __future__ import annotations

import asyncio
from typing import Any, Callable, Optional

from alloy.core.context import Context
from alloy.core.event_bus import EventBus

__all__ = ["TrpgContext", "Service", "CordisError"]


class CordisError(Exception):
    """TRPG 内核装配错误（缺失服务 / 配置错误等）。"""


class Service:
    """能力单位基类。子类声明 ``inject`` 依赖列表与 ``name``。

    协议与 alloy 插件同构（name/inject/apply），构造签名保持 D20 的
    ``(ctx, config)`` 形态，由 TrpgContext.mount 装配。
    """

    inject: list[str] = []
    name: str = ""

    def __init__(self, ctx: "TrpgContext", config: Optional[dict] = None) -> None:
        self.ctx = ctx
        self.config = config or {}
        if not self.name:
            self.name = type(self).__name__.lower().replace("service", "")

    def apply(self) -> None:
        """挂载钩子，子类可重写（默认空）。"""
        return None


class TrpgContext:
    """TRPG 服务容器：alloy Context 的 D20 兼容视图。

    - 服务以稳定 key 挂到 ctx（``ctx.attributes`` / ``ctx.get("attributes")``）；
    - 事件经 alloy EventBus 分发（与宿主共享一条总线）；
    - ``ctx.state`` 持有宿主（Character）的可变状态，服务读写它；
    - 构造即挂到宿主 Context 的 effect 栈：宿主销毁自动回收（注册即回滚）。
    """

    def __init__(self, host: Context) -> None:
        self._ctx = Context()
        self._host = host
        bus = host.get("bus", None)
        if bus is None:
            bus = EventBus()
            host.provide("bus", bus)
        self._bus: EventBus = bus
        self.state: Any = None
        self._disposers: list[list[Callable[[], None]]] = []
        self._effect_stack: list[list[Callable[[], None]]] = []
        self._listener_disposers: list[Callable[[], None]] = []
        host.effect(self.dispose)

    # ---- 服务注册（委托 alloy Context） ----
    def provide(self, name: str, service: Any, *, dispose: Optional[Callable[[], Any]] = None,
                replace: bool = False) -> Any:
        return self._ctx.provide(name, service, dispose=dispose, replace=replace)

    def get(self, name: str, default: Any = ...) -> Any:
        if default is ...:
            return self._ctx.get(name)
        return self._ctx.get(name, default)

    def has(self, name: str) -> bool:
        return self._ctx.has(name)

    def keys(self) -> list[str]:
        return self._ctx.keys()

    def __contains__(self, name: str) -> bool:
        return self._ctx.has(name)

    @property
    def live(self) -> bool:
        """内核容器是否仍存活（供 preset 幂等复用判定）。"""
        return not self._ctx._disposed

    # 供装配自检 / 测试内省（与 D20 Context 兼容）
    @property
    def _services(self) -> dict:
        return self._ctx._services

    # ---- 服务代理（D20: ctx.<name>） ----
    def __getattr__(self, name: str) -> Any:
        ctx = self.__dict__.get("_ctx")
        if ctx is not None and ctx.has(name):
            return ctx.get(name)
        raise AttributeError(name)

    # ---- 事件（骑 alloy EventBus；签名与 D20 兼容） ----
    def on(self, name: str, fn: Callable) -> Callable[[], None]:
        """注册监听，返回 disposer。

        所有订阅都被内核追踪（骑共享总线，退订责任在内核侧），
        dispose() 时逆序退订；在 effect(fn) 装配体内注册同样会被收集。
        """
        self._bus.subscribe(name, fn)

        def dispose() -> None:
            self._bus.unsubscribe(name, fn)

        self._listener_disposers.append(dispose)
        if self._effect_stack:
            self._effect_stack[-1].append(dispose)
        return dispose

    def emit(self, name: str, *args: Any) -> None:
        """观察型分发：全部监听按注册顺序触发，忽略返回值。"""
        self._bus.emit(name, args[0] if len(args) == 1 else (args if args else None))

    def waterfall(self, name: str, seed: Any, *args: Any) -> Any:
        """变换/包装型：每个监听 ``fn(current, next)`` 返回新 current，按序链式。

        不调用 ``next()`` 即短路。alloy EventBus 的链签名不含额外参数，
        故额外 args 直接报错（fail loud；内核现有钩子均为 2 参形态）。
        """
        if args:
            raise CordisError(
                f"waterfall('{name}') 携带额外参数 {args!r}："
                "alloy EventBus 链签名为 (value, next)，不支持透传额外参数")
        return self._bus.waterfall(name, seed)

    def serial(self, name: str, *args: Any) -> None:
        """按序执行型：监听依次运行（支持 async，逐个 await）。D20 原语义。"""
        for fn in list(self._bus.listeners.get(name, [])):
            result = fn(*args)
            if hasattr(result, "__await__"):
                asyncio.run(result)

    async def parallel(self, name: str, *args: Any) -> None:
        """并行扇出型：所有监听并发执行。D20 原语义。"""
        await asyncio.gather(*(fn(*args) for fn in list(self._bus.listeners.get(name, []))))

    # ---- 插件挂载（依赖注入） ----
    def mount(self, plugin: type, config: Optional[dict] = None,
              name: Optional[str] = None) -> "Service":
        """挂载一个 Service 子类。挂载前校验其 ``inject`` 依赖已就绪。"""
        if not (isinstance(plugin, type) and issubclass(plugin, Service)):
            raise CordisError(f"mount expects a Service subclass, got {plugin!r}")
        for dep in getattr(plugin, "inject", []) or []:
            if not self._ctx.has(dep):
                raise CordisError(
                    f"service '{name or plugin.__name__}' requires '{dep}' "
                    f"but it is not mounted yet")
        svc = plugin(self, config or {})
        sname = name or svc.name
        svc.name = sname
        self._ctx.provide(sname, svc)
        svc.apply()
        return svc

    # ---- 可逆副作用（D20 语义：立即执行 + 收集 disposer） ----
    def effect(self, fn: Callable[[], Any]) -> Callable[[], None]:
        """装配体：立即执行 fn；其返回值与期间 on() 的 disposer 逆序回收。"""
        collected: list[Callable[[], None]] = []
        self._effect_stack.append(collected)
        try:
            result = fn()
            if callable(result):
                collected.append(result)
            elif hasattr(result, "__iter__"):
                collected.extend(result)
        finally:
            self._effect_stack.pop()
        self._disposers.append(collected)

        def dispose() -> None:
            for d in reversed(collected):
                d()

        return dispose

    def dispose(self) -> None:
        """卸载本 TRPG 内核：逆序退订事件、运行 disposer、清空服务。

        幂等；已挂到宿主 Context 的 effect 栈，宿主销毁时自动调用。
        只回收 TRPG 作用域，不动宿主其它服务。
        """
        for d in reversed(self._listener_disposers):
            try:
                d()
            except Exception:
                pass  # 容错：单个 disposer 失败不中断其余回滚
        self._listener_disposers.clear()
        for lst in reversed(self._disposers):
            for d in reversed(lst):
                try:
                    d()
                except Exception:
                    pass  # 容错：单个 disposer 失败不中断其余回滚
        self._disposers.clear()
        self._effect_stack.clear()
        self._ctx.dispose()

    def __repr__(self) -> str:
        return f"<TrpgContext keys={sorted(self.keys())} live={self.live}>"
