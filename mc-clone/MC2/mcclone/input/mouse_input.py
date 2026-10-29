# -*- coding: utf-8 -*-
"""mouse_input — 鼠标输入源 + GUI 输入管理器（保持地基零改动）。

提供：
  - MouseStateSource: 鼠标位置 / 按键状态（左/中/右），提供“本帧刚按下”语义。
  - GUIInputManager(RealtimeInputManager): 组合键盘（RealtimeInputManager）
    + 鼠标，并提供 left()/right()/jump_pressed() 等语义动作，集中管理键位映射。

本模块仅在真实 GUI 运行期构造；导入期不依赖 pygame（pygame 延迟导入）。
headless 测试可用鸭子类型桩替代 MouseStateSource / GUIInputManager。
"""

from __future__ import annotations

from mcclone.input.input_realtime import RealtimeInputManager


def _pygame():
    """延迟导入 pygame；不可用时抛出清晰错误。"""
    import pygame
    if pygame is None:
        raise RuntimeError("需要安装可选依赖 pygame 才能使用鼠标输入")
    return pygame


# pygame 键常量缓存（仅在真实 GUI 运行期首次访问时填充）。
_KEYS = None


def _pg_keys():
    """返回 pygame 键常量字典（首次访问时延迟填充）。"""
    global _KEYS
    if _KEYS is None:
        pg = _pygame()
        _KEYS = {
            "A": pg.K_a, "D": pg.K_d, "W": pg.K_w,
            "LEFT": pg.K_LEFT, "RIGHT": pg.K_RIGHT, "UP": pg.K_UP,
            "SPACE": pg.K_SPACE, "J": pg.K_j, "K": pg.K_k,
            "ESC": pg.K_ESCAPE, "F3": pg.K_F3,
            "UP": pg.K_UP, "DOWN": pg.K_DOWN,
            "E": pg.K_e, "RETURN": pg.K_RETURN,
            "NUM": [pg.K_1, pg.K_2, pg.K_3, pg.K_4, pg.K_5, pg.K_6],
            # ── M3 新增键位（§7.4）──
            "Z": pg.K_z, "X": pg.K_x,            # Z 层切换（上/下）
            "LBRACKET": pg.K_LEFTBRACKET,        # Z 上（alias）
            "RBRACKET": pg.K_RIGHTBRACKET,       # Z 下（alias）
            "T": pg.K_t,                         # 温度覆盖层开关
            "V": pg.K_v,                         # 水/岩浆覆盖层开关
            "G": pg.K_g,                         # 挖掘作业模式
            "B": pg.K_b,                         # 建造作业模式
            # ── M5 存档 / 读档键位 ──
            "F5": pg.K_F5,                       # 存档
            "F9": pg.K_F9,                       # 读档
        }
    return _KEYS


class MouseStateSource:
    """鼠标状态源：位置 + 三键按下 / 本帧刚按下。"""

    def __init__(self) -> None:
        self._pos = (0, 0)
        self._down: set = set()
        self._pressed: set = set()
        self._prev_down: set = set()
        self._wheel: int = 0  # 累计滚轮增量（上滚 +，下滚 -）

    def poll(self) -> None:
        """读取鼠标位置与按键（本帧刚按下 = 当前按下且上一帧未按下）。"""
        pg = _pygame()
        self._pos = pg.mouse.get_pos()
        cur = pg.mouse.get_pressed()  # (left, middle, right)
        cur_set = {i for i in (0, 1, 2) if cur[i]}
        self._pressed = cur_set - self._prev_down
        self._down = cur_set
        self._prev_down = cur_set
        # 仅过滤滚轮事件（不触动键盘队列；R1）。键盘事件由冻结的
        # PygameKeyStateSource.poll() 处理。注意：调用方需保证本 poll
        # 在 key_source.poll() 之前执行（见 GUIInputManager.update）。
        for e in pg.event.get(pg.MOUSEWHEEL):
            self._wheel += e.y

    def position(self) -> tuple:
        """鼠标像素位置 (x, y)。"""
        return self._pos

    def is_down(self, button: int) -> bool:
        """某键当前是否按下（button: 0 左 / 1 中 / 2 右）。"""
        return button in self._down

    def pressed_this_frame(self, button: int) -> bool:
        """某键本帧是否刚按下。"""
        return button in self._pressed

    def wheel_delta(self) -> int:
        """返回累计滚轮增量并清零（上滚为正，下滚为负）。"""
        w = self._wheel
        self._wheel = 0
        return w

    def reset_frame(self) -> None:
        """清空“本帧刚按下”集合（每帧轮询前调用）。"""
        self._pressed.clear()


class GUIInputManager(RealtimeInputManager):
    """组合键盘 + 鼠标的输入管理器（继承 RealtimeInputManager）。

    集中管理键位映射（A/D/←→ 移动，Space/W/↑ 跳，1-6 切手持，J/K 降级），
    并透传鼠标状态。

    update() 先 reset 上一帧“刚按下”再 poll，确保 pressed_this_frame 在本帧
    内可读（修正地基 RealtimeInputManager.update 的清空顺序问题）。
    """

    def __init__(self, base, key_source, mouse: MouseStateSource) -> None:
        super().__init__(base, key_source)
        self._mouse = mouse

    def update(self) -> None:
        """每帧调用：先清上一帧“刚按下”，再轮询键鼠。

        R1 关键顺序：先 mouse.poll() 再 key_source.poll()。原因：冻结的
        PygameKeyStateSource.poll() 用 pygame.event.get() 清空整个事件队列，
        若在鼠标之前调用会吞掉 MOUSEWHEEL 事件。两者均保持
        reset_frame → poll 模式，仅调整相对顺序以保留滚轮。
        """
        self._key_source.reset_frame()
        self._mouse.reset_frame()
        self._mouse.poll()          # 先抓滚轮（R1）
        self._key_source.poll()

    def reset_frame(self) -> None:
        """清空键鼠“本帧刚按下”（供显式帧末重置）。"""
        self._key_source.reset_frame()
        self._mouse.reset_frame()

    # ── 鼠标透传 ──
    def mouse_down(self, button: int) -> bool:
        """鼠标某键是否按住。"""
        return self._mouse.is_down(button)

    def mouse_pressed(self, button: int) -> bool:
        """鼠标某键本帧是否刚按下。"""
        return self._mouse.pressed_this_frame(button)

    def mouse_pos(self) -> tuple:
        """鼠标像素位置。"""
        return self._mouse.position()

    # ── 语义动作（键位集中映射）──
    def left(self) -> bool:
        """是否向左移动（A / ←）。"""
        k = _pg_keys()
        return self.is_down(k["A"]) or self.is_down(k["LEFT"])

    def right(self) -> bool:
        """是否向右移动（D / →）。"""
        k = _pg_keys()
        return self.is_down(k["D"]) or self.is_down(k["RIGHT"])

    def jump_pressed(self) -> bool:
        """跳跃是否本帧刚按下（Space / W / ↑）。"""
        k = _pg_keys()
        return (self.pressed_this_frame(k["SPACE"])
                or self.pressed_this_frame(k["W"])
                or self.pressed_this_frame(k["UP"]))

    def select_slot_pressed(self, index: int) -> bool:
        """数字键 1-6 是否本帧刚按下（index 0..5）。"""
        k = _pg_keys()
        if 0 <= index < len(k["NUM"]):
            return self.pressed_this_frame(k["NUM"][index])
        return False

    def is_break_key_pressed(self) -> bool:
        """键盘降级：破坏键 J 是否本帧刚按下。"""
        return self.pressed_this_frame(_pg_keys()["J"])

    def is_place_key_pressed(self) -> bool:
        """键盘降级：放置键 K 是否本帧刚按下。"""
        return self.pressed_this_frame(_pg_keys()["K"])

    def escape_pressed(self) -> bool:
        """Esc 是否本帧刚按下（退出）。"""
        return self.pressed_this_frame(_pg_keys()["ESC"])

    def debug_toggle_pressed(self) -> bool:
        """F3 是否本帧刚按下（调试覆盖层开关）。"""
        return self.pressed_this_frame(_pg_keys()["F3"])

    # ── M2 合成 / 滚轮手持切换（T-M2-10）──
    def wheel_slot_delta(self) -> int:
        """滚轮手持切换增量：上滚 +1，下滚 -1，无滚动 0。"""
        w = self._mouse.wheel_delta()
        if w > 0:
            return 1
        if w < 0:
            return -1
        return 0

    def craft_toggle_pressed(self) -> bool:
        """合成 overlay 开关键（E）本帧是否刚按下。"""
        return self.pressed_this_frame(_pg_keys()["E"])

    def craft_confirm_pressed(self) -> bool:
        """合成确认键（Enter / Return）本帧是否刚按下。"""
        return self.pressed_this_frame(_pg_keys()["RETURN"])

    def craft_up_pressed(self) -> bool:
        """合成列表上移键（↑）本帧是否刚按下。"""
        return self.pressed_this_frame(_pg_keys()["UP"])

    def craft_down_pressed(self) -> bool:
        """合成列表下移键（↓）本帧是否刚按下。"""
        return self.pressed_this_frame(_pg_keys()["DOWN"])

    # ── M3 层 / 覆盖层 / 作业语义动作（T-M3-11）──
    # 键位集中映射（§7.4）；全部「本帧刚按下」语义，与 M1/M2 一致。
    # update() 调用顺序保持不变（先 mouse 后 key，保 M2 R1 滚轮）。
    def layer_up_pressed(self) -> bool:
        """Z（或 [）本帧刚按下 → 切换上层。"""
        k = _pg_keys()
        return (self.pressed_this_frame(k["Z"])
                or self.pressed_this_frame(k["LBRACKET"]))

    def layer_down_pressed(self) -> bool:
        """X（或 ]）本帧刚按下 → 切换下层。"""
        k = _pg_keys()
        return (self.pressed_this_frame(k["X"])
                or self.pressed_this_frame(k["RBRACKET"]))

    def temp_overlay_toggle(self) -> bool:
        """T 本帧刚按下 → 温度覆盖层开关。"""
        return self.pressed_this_frame(_pg_keys()["T"])

    def water_overlay_toggle(self) -> bool:
        """V 本帧刚按下 → 水/岩浆覆盖层开关。"""
        return self.pressed_this_frame(_pg_keys()["V"])

    def dig_mode_pressed(self) -> bool:
        """G 本帧刚按下 → 挖掘作业模式开关。"""
        return self.pressed_this_frame(_pg_keys()["G"])

    def build_mode_pressed(self) -> bool:
        """B 本帧刚按下 → 建造作业模式开关。"""
        return self.pressed_this_frame(_pg_keys()["B"])

    def cancel_job_pressed(self) -> bool:
        """鼠标右键本帧刚按下 → 取消作业（复用 mouse_pressed(2)）。

        作业模式下由 GameLoop 解释为取消（§7.4）。
        """
        return self.mouse_pressed(2)

    # ── M5 存档 / 读档键位（T-M5-*）──
    def save_pressed(self) -> bool:
        """F5 本帧刚按下 → 触发存档。"""
        return self.pressed_this_frame(_pg_keys()["F5"])

    def load_pressed(self) -> bool:
        """F9 本帧刚按下 → 触发读档。"""
        return self.pressed_this_frame(_pg_keys()["F9"])
