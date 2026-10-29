# -*- coding: utf-8 -*-
"""游戏控制器 - 薄前端 / 宿主层

M1 重构：模拟逻辑已迁入 src.sim_core.engine.SimCore。本类只负责：
  - 构建 tkinter UI（Canvas / 托盘 / 键鼠绑定）
  - 持有 SimCore 实例并每帧驱动 update(dt)
  - 消费 SimCore 产生的 audio_events 并真实播放（音频与模拟解耦）
  - 通过属性代理把 UI 层的 self.<sim字段> 映射到 self.sim.<字段>

行为与重构前一致（除音频改为事件队列驱动外，玩法/日志/存档零变化）。
"""
import time
import tkinter as tk
from tkinter import messagebox

from src.config.settings import (
    GAME_TITLE, WINDOW_WIDTH, WINDOW_HEIGHT,
)
from src.app.controllers.game_render import GameRenderer
from src.app.controllers.game_tray import SystemTrayMixin
from src.app.controllers.game_io import GameIOMixin
from src.app.controllers.game_init import GameInitMixin
from src.sim_core.engine import SimCore
from src.app.services.audio_service import AudioService


class GameController(
    GameInitMixin,
    GameRenderer,
    SystemTrayMixin,
    GameIOMixin,
):
    # ── 模拟状态代理（UI 层只读/写经由此映射到 SimCore）──
    @property
    def paused(self):
        return self.sim.paused

    @paused.setter
    def paused(self, value):
        self.sim.paused = value

    @property
    def _game_over(self):
        return self.sim._game_over

    def _add_log(self, msg: str):
        """日志统一走 SimCore（单一数据源）"""
        self.sim._add_log(msg)

    def __init__(self, root):
        self.root = root
        self.root.title(GAME_TITLE)
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.root.configure(bg="#0d1117")

        # 仅 UI / 生命周期状态（模拟状态全部在 self.sim 中）
        self.running = True
        self.tray_icon = None
        self._tray_running = False
        self._tray_minimizing = False

        # 分隔条状态（日志区 vs 右侧面板）
        self._split_ratio = 0.75  # 默认右侧面板占 25% 宽度
        self._dragging_split = False

        self._build_ui()

        # ── 创建模拟内核（构造即读档或新建世界）──
        self.sim = SimCore()
        # 音频服务与 SimCore 共享同一实例（宿主负责真实播放）
        self.audio = self.sim.audio

        self._last_frame = time.time()
        self._game_loop()

    def _build_ui(self):
        self.canvas = tk.Canvas(self.root, bg="#0d1117", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Configure>", self._on_resize)
        # 分隔条拖拽事件
        self.canvas.bind("<Button-1>", self._on_split_press)
        self.canvas.bind("<B1-Motion>", self._on_split_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_split_release)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.bind("<Unmap>", self._on_minimize)
        self.root.bind("<space>", lambda e: self._toggle_pause())
        self.root.bind("<Key-1>", lambda e: self._set_speed(1))
        self.root.bind("<Key-2>", lambda e: self._set_speed(2))
        self.root.bind("<Key-s>", lambda e: self.save_game())
        self.root.bind("<Key-m>", lambda e: self._toggle_mute())
        self.root.bind("<Key-n>", lambda e: self._show_character_creation())
        self.canvas.focus_set()

    def _on_resize(self, event):
        self._redraw()

    # ---- 分隔条拖拽（日志区 vs 右侧面板）----
    def _get_split_x(self, w):
        """根据当前比例计算分隔条 x 坐标"""
        return int(w * self._split_ratio)

    def _on_split_press(self, event):
        w = self.canvas.winfo_width() or 960
        split_x = self._get_split_x(w)
        if abs(event.x - split_x) < 6:  # 点击在分隔条附近
            self._dragging_split = True

    def _on_split_drag(self, event):
        if not self._dragging_split:
            return
        w = self.canvas.winfo_width() or 960
        # 限制范围：至少给右侧面板留 200px，日志区至少留 300px
        min_split = max(200.0 / w, 0.2)
        max_split = (w - 300) / w if w > 350 else 0.85
        new_ratio = max(min_split, min(max_split, event.x / w))
        self._split_ratio = new_ratio

    def _on_split_release(self, event):
        self._dragging_split = False

    def _on_close(self):
        if messagebox.askyesno("退出确认", "确定退出游戏?\n退出前自动保存。"):
            self.running = False
            self.audio.stop_all()
            if not self._game_over:
                self.save_game()
            self._tray_minimizing = True
            self.root.destroy()

    def _on_minimize(self, event=None):
        if self._tray_minimizing:
            return
        if event and event.widget == self.root and self.root.state() == "iconic":
            if self.tray_available:
                self._tray_minimizing = True
                self._minimize_to_tray()
                self._tray_minimizing = False

    def _game_loop(self):
        if not self.running:
            return
        now = time.time()
        dt = min(0.1, now - self._last_frame)
        self._last_frame = now

        # 推进模拟内核
        self.sim.update(dt)

        # 消费模拟产生的音频事件并真实播放（音频与模拟解耦）
        if self.sim.audio_events:
            audio = self.audio
            for name, args in self.sim.audio_events:
                fn = getattr(audio, name, None)
                if fn:
                    try:
                        fn(*args)
                    except Exception:
                        pass  # 单条音效失败不影响主循环
            self.sim.audio_events.clear()

        self._redraw()
        self.root.after(50, self._game_loop)
