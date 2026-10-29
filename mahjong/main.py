"""麻将连连看 - 入口

MVVM 架构:
  Model      : models/      (Tile, Board, GameState)
  Service    : services/    (deck, layouts, matcher, scorer)
  ViewModel  : viewmodel/   (GameViewModel - 状态机+命令)
  View       : views/       (TileRenderer, BoardCanvas, Hud)

运行: python main.py
"""
from __future__ import annotations

import time
import tkinter as tk
from tkinter import messagebox

from allin_engine.core.game_loop import FixedTimestepLoop
from models.game_state import GameMode
from services.layouts import LayoutKind
from viewmodel.game_viewmodel import GameViewModel
from views import BoardCanvas, Hud, TileRenderer
from views.audio_controller import AudioController


TILE_SIZE = 52


class App:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        root.title("麻将连连看 · MVVM")
        root.configure(bg="#2d5016")

        # ViewModel (无 UI 依赖)
        self.vm = GameViewModel(
            layout=LayoutKind.TURTLE,
            mode=GameMode.MAHJONG,
            time_limit=300,
            hints=3,
            shuffles=3,
        )
        self.vm.start_new_game()

        # 音效（Cocos 素材复用：选中读牌 + 配对碰 + 通关胡；无 pygame 时静默）
        self.audio = AudioController(self.vm)

        # View
        self.hud = Hud(root, self.vm)
        self.renderer = TileRenderer(tile_size=TILE_SIZE)
        # 棋盘容器 (可滚动以适配小屏)
        wrap = tk.Frame(root, bg="#2d5016")
        wrap.pack(fill=tk.BOTH, expand=True)
        self.canvas_view = BoardCanvas(wrap, self.vm, self.renderer)
        self.canvas_view.container.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        # 胜负 / 死局 监听
        self.vm.add_listener(self._on_global_event)

        # 键盘绑定
        root.bind("<h>", lambda e: self.vm.use_hint())
        root.bind("<H>", lambda e: self.vm.use_hint())
        root.bind("<z>", lambda e: self.vm.undo())
        root.bind("<Z>", lambda e: self.vm.undo())
        root.bind("<s>", lambda e: self.vm.shuffle())
        root.bind("<S>", lambda e: self.vm.shuffle())
        root.bind("<r>", lambda e: self.vm.restart())
        root.bind("<R>", lambda e: self.vm.restart())
        root.bind("<m>", lambda e: self.vm.toggle_mode())
        root.bind("<M>", lambda e: self.vm.toggle_mode())
        root.bind("<l>", lambda e: self.hud._cycle_layout())
        root.bind("<L>", lambda e: self.hud._cycle_layout())
        root.bind("<Escape>", lambda e: self.vm.toggle_pause())
        root.bind("?", lambda e: self.hud._show_help())

        # 计时循环（引擎固定步长主循环：逻辑与帧率解耦，钳制防死亡螺旋）
        self._loop = FixedTimestepLoop(self.vm.tick, fixed_dt=0.25)
        self._last = time.monotonic()
        self._tick_loop()

        root.update_idletasks()
        root.minsize(880, 680)

    # ---- 计时（固定步长驱动）-------------------------------
    def _tick_loop(self) -> None:
        now = time.monotonic()
        self._loop.advance(now - self._last)   # 内部按 0.25 切分，单帧上限防死亡螺旋
        self._last = now
        self.root.after(250, self._tick_loop)

    # ---- 全局事件 (胜负/死局) ------------------------------------
    def _on_global_event(self, ev) -> None:
        if ev.type == "win":
            d = ev.data
            messagebox.showinfo(
                "通关!",
                f"恭喜通关!\n\n"
                f"最终分数: {d['final_score']}\n"
                f"步数: {d['moves']}\n"
                f"时间奖励: +{d['time_bonus']}",
            )
        elif ev.type == "lose":
            messagebox.showinfo("超时", "时间到，游戏结束。按 R 重开。")
        elif ev.type == "deadlock":
            if self.vm.state.shuffles_left > 0:
                if messagebox.askyesno("死局", "已无可用配对!\n是否自动洗牌?"):
                    self.vm.shuffle()
            else:
                messagebox.showinfo("死局", "无可用配对且洗牌已用尽。\n可按 Z 撤销或 R 重开。")


def main() -> None:
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
