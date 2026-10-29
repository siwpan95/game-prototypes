# -*- coding: utf-8 -*-
"""test_m2_mouse_input — 鼠标输入：滚轮抓取(R1) / 轮询顺序 / 合成与滚轮动作（headless，T-M2-10）。

说明：
  - 用模块级假 _pg_keys 脱离真实 pygame 键常量。
  - 用假 pygame 替换 mouse_input._pygame，验证 poll() 经
    pygame.event.get(MOUSEWHEEL) 抓取滚轮增量（R1 关键路径）。
"""

from __future__ import annotations

from mcclone.input import mouse_input

# 假 pygame 键常量（覆盖 _pg_keys，脱离真实 pygame）
_FAKE_KEYS = {
    "A": 1, "D": 2, "W": 3, "LEFT": 4, "RIGHT": 5, "UP": 6, "DOWN": 7,
    "SPACE": 8, "J": 9, "K": 10, "ESC": 11, "F3": 12, "E": 13, "RETURN": 14,
    "NUM": [20, 21, 22, 23, 24, 25],
}
mouse_input._pg_keys = lambda: _FAKE_KEYS


class _FakeKey:
    """记录调用顺序的假键盘源；可注入按下集合。"""

    def __init__(self, order=None):
        self.calls = []
        self._order = order if order is not None else self.calls
        self._down = set()
        self._pressed = set()

    def reset_frame(self):
        self._order.append("key_reset")

    def poll(self):
        self._order.append("key_poll")

    def is_down(self, k):
        return k in self._down

    def pressed_this_frame(self, k):
        return k in self._pressed


class _FakeMouse:
    """记录调用顺序的假鼠标源；可注入滚轮/按下。"""

    def __init__(self, order=None):
        self.calls = []
        self._order = order if order is not None else self.calls
        self._down = set()
        self._pressed = set()
        self._wheel = 0
        self._pos = (0, 0)

    def reset_frame(self):
        self._order.append("mouse_reset")

    def poll(self):
        self._order.append("mouse_poll")

    def position(self):
        return self._pos

    def is_down(self, b):
        return b in self._down

    def pressed_this_frame(self, b):
        return b in self._pressed

    def wheel_delta(self):
        w = self._wheel
        self._wheel = 0
        return w


def _gui():
    key = _FakeKey()
    mouse = _FakeMouse()
    gui = mouse_input.GUIInputManager(object(), key, mouse)
    return gui, key, mouse


def test_update_poll_order_preserves_wheel_R1():
    """update() 必须 mouse.poll() 先于 key_source.poll()，否则 MOUSEWHEEL 被吞。"""
    order = []
    key = _FakeKey(order)
    mouse = _FakeMouse(order)
    gui = mouse_input.GUIInputManager(object(), key, mouse)
    gui.update()
    assert order == ["key_reset", "mouse_reset", "mouse_poll", "key_poll"]
    assert order.index("mouse_poll") < order.index("key_poll")


def test_wheel_slot_delta_mapping():
    mouse = _FakeMouse()
    gui = mouse_input.GUIInputManager(object(), _FakeKey(), mouse)
    mouse._wheel = 1
    assert gui.wheel_slot_delta() == 1
    mouse._wheel = -1
    assert gui.wheel_slot_delta() == -1
    mouse._wheel = 0
    assert gui.wheel_slot_delta() == 0


def test_mouse_state_wheel_delta_accumulates():
    m = mouse_input.MouseStateSource()
    m._wheel = 5
    assert m.wheel_delta() == 5
    assert m.wheel_delta() == 0


def test_craft_toggle_confirm_up_down():
    key = _FakeKey()
    gui = mouse_input.GUIInputManager(object(), key, _FakeMouse())
    key._pressed = {_FAKE_KEYS["E"]}
    assert gui.craft_toggle_pressed() is True
    key._pressed = {_FAKE_KEYS["RETURN"]}
    assert gui.craft_confirm_pressed() is True
    key._pressed = {_FAKE_KEYS["UP"]}
    assert gui.craft_up_pressed() is True
    key._pressed = {_FAKE_KEYS["DOWN"]}
    assert gui.craft_down_pressed() is True


def test_mouse_wheel_captured_via_event_get_R1():
    """用假 pygame 替换 mouse_input._pygame，验证 poll 抓取 MOUSEWHEEL 增量。"""

    class _Ev:
        def __init__(self, **kw):
            self.__dict__.update(kw)

    class _EvMod:
        def __init__(self):
            self.q = {"MOUSEWHEEL": []}

        def get(self, t):
            if t == "MOUSEWHEEL":
                evs = self.q["MOUSEWHEEL"]
                self.q["MOUSEWHEEL"] = []
                return evs
            return []

    class _Mouse:
        def get_pos(self):
            return (0, 0)

        def get_pressed(self):
            return (0, 0, 0)

    class _Pg:
        def __init__(self):
            self.event = _EvMod()
            self.MOUSEWHEEL = "MOUSEWHEEL"
            self.mouse = _Mouse()

    fake = _Pg()
    fake.event.q["MOUSEWHEEL"] = [_Ev(y=3)]
    orig = mouse_input._pygame
    mouse_input._pygame = lambda: fake
    try:
        m = mouse_input.MouseStateSource()
        m.poll()
        assert m._wheel == 3
    finally:
        mouse_input._pygame = orig
