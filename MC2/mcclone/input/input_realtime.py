"""
input_realtime — 实时键盘输入（pygame 为可选软依赖，延迟导入）。

提供：
  - PygameKeyStateSource: 维护按下集合与「本帧刚按下」集合
  - RealtimeInputManager: 委托实时键盘状态，同时保留基类文本命令能力

重要：
  - 顶层绝不 import pygame；仅在使用时按需导入（延迟导入）。
  - 若运行环境无 pygame，构造或使用会抛出清晰的 RuntimeError。
  - 不破坏既有 InputManager 的文本命令能力（运行时需 tkinter/CLI 源）。

本模块只依赖纯净版 alloy 的通用能力：
  - alloy.systems.input.InputManager
"""

from __future__ import annotations

# 延迟导入：顶层绝不 import pygame（可选软依赖）
try:
    import pygame
except Exception:  # noqa: BLE001 — 任何异常都视为不可用
    pygame = None

from mcclone._engine import InputManager


class PygameKeyStateSource:
    """基于 pygame 事件的实时键盘状态源。"""

    def __init__(self) -> None:
        if pygame is None:
            raise RuntimeError("需要安装可选依赖 pygame 才能使用实时键盘输入")
        self._down: set = set()                # 当前按下的键
        self._pressed_this_frame: set = set()  # 本帧刚按下的键

    def poll(self) -> None:
        """读取 pygame 事件队列，更新按下/本帧按下集合。"""
        if pygame is None:
            raise RuntimeError("需要安装可选依赖 pygame 才能使用实时键盘输入")
        for event in pygame.event.get():
            if event.type == pygame.KEYDOWN:
                self._down.add(event.key)
                self._pressed_this_frame.add(event.key)
            elif event.type == pygame.KEYUP:
                self._down.discard(event.key)

    def is_down(self, key: int) -> bool:
        """判断某键当前是否处于按下状态（key 为 pygame 键常量，如 pygame.K_w）。"""
        return key in self._down

    def pressed_this_frame(self, key: int) -> bool:
        """判断某键是否在本帧刚被按下。"""
        return key in self._pressed_this_frame

    def reset_frame(self) -> None:
        """清空「本帧刚按下」集合（每帧更新后调用）。"""
        self._pressed_this_frame.clear()


class RealtimeInputManager:
    """实时输入管理器：组合实时键盘源与既有文本命令输入。

    实时键盘状态委托给 key_source；文本命令能力保留自 base（InputManager）。
    """

    def __init__(self, base: InputManager, key_source: PygameKeyStateSource) -> None:
        self._base = base
        self._key_source = key_source

    # ── 实时键盘委托 ──

    def is_down(self, key: int) -> bool:
        """委托：判断某键当前是否按下。"""
        return self._key_source.is_down(key)

    def pressed_this_frame(self, key: int) -> bool:
        """委托：判断某键本帧是否刚按下。"""
        return self._key_source.pressed_this_frame(key)

    def update(self) -> None:
        """每帧调用：轮询事件后重置本帧状态。"""
        self._key_source.poll()
        self._key_source.reset_frame()

    # ── 保留基类文本命令能力（不破坏既有 InputManager）──

    def get_command(self, *args, **kwargs):
        """委托给 base.get_command()，保留文本命令解析能力。"""
        return self._base.get_command(*args, **kwargs)

    def get_raw_input(self, *args, **kwargs):
        """委托给 base.get_raw_input()。"""
        return self._base.get_raw_input(*args, **kwargs)

    def __getattr__(self, name: str):
        # 其余属性/方法一律委托给 base（如 add_source/history 等），
        # 从而完整保留既有 InputManager 能力。
        return getattr(self._base, name)
