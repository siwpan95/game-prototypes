# -*- coding: utf-8 -*-
"""
test_input_realtime — input_realtime 补充测试（实时输入模块）。

覆盖：
  - 模拟无 pygame 时 input_realtime.pygame 为 None（导入安全）。
  - PygameKeyStateSource 在无 pygame 时构造抛 RuntimeError。
  - 若环境装有 pygame，则验证 PygameKeyStateSource / RealtimeInputManager 真实可用。
  - RealtimeInputManager 对键盘源的委托与对 base 的属性委托（鸭子类型桩，
    不依赖 pygame 是否安装）。
"""

from __future__ import annotations

from mcclone.input import input_realtime
from _testutil import simulate_no_pygame, restore_pygame


class _FakeKeySource:
    """鸭子类型桩：模拟 PygameKeyStateSource 的公开接口。

    poll() 把本帧按下集合并入按下集合（对齐真实实现的 KEYDOWN 语义），
    reset_frame() 清空本帧按下集合。is_down / pressed_this_frame 读取状态。
    """

    def __init__(self):
        self._down = set()
        self._pressed = set()

    def is_down(self, key):
        return key in self._down

    def pressed_this_frame(self, key):
        return key in self._pressed

    def poll(self):
        self._down |= self._pressed

    def reset_frame(self):
        self._pressed.clear()


class _FakeBase:
    """鸭子类型桩：模拟 InputManager 的 get_command / get_raw_input。"""

    def get_command(self, *a, **k):
        return ("move", 1)

    def get_raw_input(self, *a, **k):
        return ""


def test_simulate_no_pygame_sets_none():
    saved = simulate_no_pygame()
    try:
        assert input_realtime.pygame is None
        # 模拟无 pygame 时，构造应抛 RuntimeError
        try:
            input_realtime.PygameKeyStateSource()
            raise AssertionError("无 pygame 时构造应抛 RuntimeError")
        except RuntimeError as e:
            assert "pygame" in str(e).lower()
    finally:
        restore_pygame(saved)


def test_key_source_raises_without_pygame():
    saved = simulate_no_pygame()
    try:
        try:
            input_realtime.PygameKeyStateSource()
            raise AssertionError("无 pygame 时构造应抛 RuntimeError")
        except RuntimeError as e:
            assert "pygame" in str(e).lower()
    finally:
        restore_pygame(saved)


def test_key_source_usable_with_pygame():
    """若环境装有 pygame，则真实构造并调用不应报错（无需显示设备）。"""
    if input_realtime.pygame is None:
        return  # 无 pygame 环境：该路径不可用，视为通过（由无-pygame 用例覆盖）
    src = input_realtime.PygameKeyStateSource()
    assert src.is_down(65) is False
    src.poll()
    assert src.pressed_this_frame(65) is False


def test_manager_delegates_to_key_source():
    fake = _FakeKeySource()
    fake._down.add(65)
    fake._pressed.add(66)
    base = _FakeBase()
    mgr = input_realtime.RealtimeInputManager(base, fake)
    assert mgr.is_down(65) is True
    assert mgr.is_down(99) is False
    assert mgr.pressed_this_frame(66) is True
    mgr.update()
    assert mgr.is_down(66) is True            # poll 后按下集合并入 down
    assert mgr.pressed_this_frame(66) is False  # reset_frame 已清空本帧


def test_manager_delegates_to_base_via_getattr():
    fake = _FakeKeySource()
    base = _FakeBase()
    mgr = input_realtime.RealtimeInputManager(base, fake)
    # __getattr__ 应把未知属性委托给 base
    assert mgr.get_command() == ("move", 1)


def test_manager_update_calls_source():
    calls = {"poll": 0, "reset": 0}

    class _Instrumented(_FakeKeySource):
        def poll(self):
            calls["poll"] += 1
        def reset_frame(self):
            calls["reset"] += 1

    fake = _Instrumented()
    mgr = input_realtime.RealtimeInputManager(_FakeBase(), fake)
    mgr.update()
    assert calls["poll"] == 1
    assert calls["reset"] == 1
