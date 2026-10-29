"""入口与编排层 - 连接引擎和 UI，管理游戏循环和键盘事件。

增强版控制方案（参考原版 SkiFree + 现代 ergonomics）：
  ←/→ 或 A/D   转弯
  F            加速冲刺（逃脱雪人）
  P            暂停
  T            暂停时单帧步进
  R            重开当前模式
  1/2/3        主菜单选模式（无尽/回转/自由式）
  空格/回车    开始游戏
  ESC          返回主菜单
"""

from __future__ import annotations

import time
import tkinter as tk

from config import MODE_ENDLESS, MODE_FREESTYLE, MODE_NAMES, MODE_SLALOM, TICK_INTERVAL_MS
from engine import GameEngine
from storage import load_best, save_best
from ui import GameUI

_MODE_KEYS = {
    "1": MODE_ENDLESS,
    "2": MODE_SLALOM,
    "3": MODE_FREESTYLE,
}


class SkiGame:
    """游戏编排器：将引擎逻辑与 UI 渲染连接起来，控制游戏生命周期。"""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.engine = GameEngine(mode=MODE_ENDLESS)
        self.ui = GameUI(root)

        # 主菜单模式（开始前可切换）
        self.menu_mode = MODE_ENDLESS
        # 暂停状态下保留上一帧 snapshot，便于叠加暂停遮罩
        self._last_snapshot: dict | None = None

        self._bind_keys()
        self._refresh_menu()

    # ========== 输入绑定 ==========

    def _bind_keys(self):
        """绑定键盘控制事件。"""
        # 方向
        self.root.bind("<Left>", lambda e: self._on_turn(-1))
        self.root.bind("<Right>", lambda e: self._on_turn(1))
        self.root.bind("<a>", lambda e: self._on_turn(-1))
        self.root.bind("<d>", lambda e: self._on_turn(1))
        self.root.bind("<A>", lambda e: self._on_turn(-1))
        self.root.bind("<D>", lambda e: self._on_turn(1))

        # 动作
        self.root.bind("f", self._on_boost)
        self.root.bind("F", self._on_boost)
        self.root.bind("p", self._on_pause)
        self.root.bind("P", self._on_pause)
        self.root.bind("t", self._on_step)
        self.root.bind("T", self._on_step)
        self.root.bind("r", self._on_restart)
        self.root.bind("R", self._on_restart)
        self.root.bind("<Escape>", self._on_escape)

        # 模式选择 + 开始
        for k, mode in _MODE_KEYS.items():
            self.root.bind(k, lambda e, m=mode: self._on_select_mode(m))
        self.root.bind("<space>", self._on_start_or_resume)
        self.root.bind("<Return>", self._on_start_or_resume)

    # ========== 输入回调 ==========

    def _on_turn(self, direction: int):
        self.engine.turn(direction)

    def _on_boost(self, _event=None):
        if self.engine.activate_boost():
            self.ui.show_crash_effect("jump")  # 复用闪烁特效显示加速起效

    def _on_pause(self, _event=None):
        if not self.engine.game_started:
            return
        self.engine.toggle_pause()
        if self.engine.paused:
            self.ui.show_paused()
        elif self._last_snapshot:
            self.ui.render(self._last_snapshot)

    def _on_step(self, _event=None):
        if self.engine.step_single_frame():
            events = []  # step_single_frame 内部已 tick，这里只补渲染
            snap = self.engine.get_snapshot()
            self._last_snapshot = snap
            self.ui.render(snap)
            self._handle_events(events)

    def _on_restart(self, _event=None):
        self._start_game()

    def _on_escape(self, _event=None):
        """返回主菜单。"""
        self.engine.reset()
        self._refresh_menu()

    def _on_select_mode(self, mode: str):
        if self.engine.game_started and not self.engine.game_over:
            return  # 游戏中不切换
        self.menu_mode = mode
        self.engine.set_mode(mode)
        self._refresh_menu()

    def _on_start_or_resume(self, _event=None):
        if self.engine.game_started and self.engine.paused:
            self.engine.toggle_pause()
            if self._last_snapshot:
                self.ui.render(self._last_snapshot)
            return
        if self.engine.game_over or not self.engine.game_started:
            self._start_game()

    # ========== 游戏生命周期 ==========

    def _refresh_menu(self):
        """刷新主菜单画面。"""
        high = load_best(self.menu_mode)
        self.engine.set_mode(self.menu_mode)
        self.ui.show_start_screen(high_score=high, mode=self.menu_mode)

    def _start_game(self):
        """开始游戏（或重新开始）。"""
        self.engine.mode = self.menu_mode
        self.engine.start()
        self.engine.high_score = load_best(self.menu_mode)
        self._game_loop()

    def _game_loop(self):
        """游戏主循环：每帧执行 tick → 处理事件 → 渲染 → 调度下一帧。"""
        # 暂停或已结束：停止调度
        if self.engine.game_over:
            self._show_game_over()
            return
        if self.engine.paused or not self.engine.game_started:
            return

        # 1. 执行一帧逻辑
        events = self.engine.tick()

        # 2. 处理事件特效
        self._handle_events(events)

        # 3. 渲染最新状态
        snapshot = self.engine.get_snapshot()
        self._last_snapshot = snapshot
        self.ui.render(snapshot)

        # 4. 继续调度或结束
        if self.engine.game_over:
            self._show_game_over()
        else:
            self.root.after(TICK_INTERVAL_MS, self._game_loop)

    def _handle_events(self, events: list[tuple]):
        """根据引擎事件触发 UI 特效。"""
        for event in events:
            if not event:
                continue
            kind = event[0]
            if kind in ("tree", "rock"):
                self.ui.show_crash_effect(kind)
                time.sleep(0.3)
            elif kind == "flag":
                self.ui.show_crash_effect("flag")
                time.sleep(0.08)
            elif kind == "jump_start":
                self.ui.show_crash_effect("jump")
                time.sleep(0.08)
            elif kind == "yeti_spawn":
                # 雪人出现：屏幕短暂闪烁
                self.ui.show_crash_effect("rock")  # 借用警告色
                time.sleep(0.2)
            elif kind == "eaten":
                self.ui.show_crash_effect("tree")
                time.sleep(0.5)

    def _show_game_over(self):
        """显示结束画面并更新高分。"""
        snapshot = self.engine.get_snapshot()
        # 落库高分
        old_best, is_new = save_best(self.engine.mode, snapshot["score"])
        current_best = load_best(self.engine.mode)
        self.ui.show_game_over(
            snapshot,
            high_score=current_best,
            is_new_record=is_new,
        )
        # 允许 R 重开 / ESC 返回菜单
        self.engine.game_started = False


def main():
    root = tk.Tk()
    root.configure(bg="#1a1a2e")
    root.resizable(False, False)
    SkiGame(root)
    root.mainloop()


if __name__ == "__main__":
    main()
