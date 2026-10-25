# -*- coding: utf-8 -*-
"""超级引擎接入探测 —— **可选依赖的定位与降级都收在这里**。

为什么要有这一层
----------------
本仓对外承诺「纯标准库、无第三方依赖」（打包成单文件 exe）。而超级引擎需要
cordis + numpy + PyYAML + watchdog + 三个仓的源码 —— 直接硬依赖会**破坏发行**。
所以接入做成**可选增强**：

* 探测顺序：``import superengine`` → 环境变量 ``SUPERENGINE_SRC`` → 并排目录；
* 探测不到就**优雅降级**回内置实现（世界与规则各自独立降级）；
* `--engine super` 显式要求却不可用时，给出**可执行的**修复指令而不是含糊报错。

这样：普通用户双击 exe 还是原汁原味的纯标准库版；开发/演示时接上引擎就是真地牢。
"""

from __future__ import annotations

import os
import sys
from typing import Any, Optional, Tuple

__all__ = ["SuperEngine", "probe", "describe", "ENGINE_ENV"]

ENGINE_ENV = "SUPERENGINE_SRC"


class SuperEngine:
    """一个可用的超级引擎会话（懒装配；装配失败即视为不可用）。

    属性 ``ok`` 表示三仓桥接是否都装配成功。装配是**惰性**的：只有真正用到
    （比如要生成地牢）时才付出启动成本。
    """

    def __init__(self, root: Optional[str] = None, reason: str = "",
                 importable: bool = False):
        self.root = root
        self.reason = reason
        self.importable = importable
        self._ctx = None
        self._error = None

    @property
    def available(self) -> bool:
        # 两种可用形态：① 直接 import 得到（root=None）② 目录定位（root 有值）。
        # 只看 root 会把「已安装」误判成不可用。
        return self._error is None and (self.root is not None or self.importable)

    @property
    def error(self) -> Optional[str]:
        return self._error

    def ctx(self):
        """装配并返回 cordis 上下文（含 worldbuilder / anengine / tdworld 三个服务）。"""
        if self._ctx is None:
            if self.root is None and not self.importable:
                raise RuntimeError(f"超级引擎不可用（{self.reason}）")
            if self.root is not None and self.root not in sys.path:
                sys.path.insert(0, self.root)
            import asyncio

            from superengine.assembly import mount

            self._ctx = asyncio.run(mount())
        return self._ctx

    # ---- 便捷访问 ----
    def worldbuilder(self):
        return self.ctx().worldbuilder

    def anengine(self):
        return self.ctx().anengine


def _sibling_root() -> Optional[str]:
    """并排目录约定：``<random-dungeon->/../superengine``。"""
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cand = os.path.join(os.path.dirname(here), "superengine")
    return cand if os.path.isdir(os.path.join(cand, "superengine")) else None


def probe(explicit: Optional[str] = None) -> SuperEngine:
    """探测超级引擎是否可用。**只读探测**，不触发装配。"""
    # ① 已经可直接 import（pip 安装过 / PYTHONPATH 里有）
    try:
        import superengine  # noqa: F401
        return SuperEngine(None, "已安装", importable=True)
    except ImportError:
        pass
    # ② 显式指定 / 环境变量
    for cand in (explicit, os.environ.get(ENGINE_ENV), _sibling_root()):
        if cand and os.path.isdir(os.path.join(cand, "superengine")):
            return SuperEngine(os.path.abspath(cand), "目录定位")
    missing = []
    try:
        import numpy  # noqa: F401
    except ImportError:
        missing.append("numpy")
    try:
        import yaml  # noqa: F401
    except ImportError:
        missing.append("PyYAML")
    hint = f"（还缺依赖：{', '.join(missing)}）" if missing else ""
    return SuperEngine(None, f"未找到 superengine{hint}")


def ready(engine: SuperEngine) -> bool:
    """**真正验证**引擎可用：走一次装配。

    只在目录层面探测是不够的 —— 目录在、但 PyYAML / watchdog / cordis 缺失时，
    `mount()` 会失败。这时应当**降级回内置**，而不是让程序崩在使用点。
    装配失败的原因会记进 ``engine.error``，供 `--status` 排查。
    """
    if not engine.available:
        return False
    try:
        engine.ctx()
        return True
    except Exception as exc:                                # noqa: BLE001
        engine._error = f"{type(exc).__name__}: {exc}"
        return False


def describe(engine: SuperEngine) -> str:
    """一行人类可读的可用性说明（CLI `--status` 用）。"""
    if engine.available:
        return f"超级引擎可用（{engine.reason}{'：' + engine.root if engine.root else ''}）"
    return f"超级引擎不可用（{engine.reason}）；将使用内置实现"


def ensure(engine: SuperEngine) -> Tuple[bool, str]:
    """确认可用；不可用则返回 ``(False, 可执行的修复指令)``。"""
    if engine.available:
        return True, "ok"
    tips = [
        f"设置环境变量 {ENGINE_ENV} 指向 superengine 仓根目录，",
        "或把 superengine 与 random-dungeon- 并排放置，",
        "并确保依赖齐备：pip install numpy PyYAML watchdog（cordis 由 3dworld/vendor/cordis/src 提供）。",
    ]
    return False, " ".join(tips)
