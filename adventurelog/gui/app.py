# -*- coding: utf-8 -*-
"""主应用 GUI — Progress Quest 风格地牢探索 + 嵌入式自动化管线"""

import sys
import tkinter as tk
from tkinter import ttk, messagebox
import time
import random
import threading
import os
from datetime import datetime
from PIL import Image, ImageDraw

from core.config import (
    WIN_W, WIN_H,
    C_BG, C_PANEL_BG, C_CONTENT_BG, C_GOLD, C_ACCENT_TEAL, C_ACCENT_RED,
    C_TEXT, C_TEXT_LIGHT, C_TEXT_HINT,
    C_BTN_NORMAL, C_BTN_HOVER, C_BTN_TEXT, C_BTN_DANGER, C_BTN_DANGER_TEXT,
    C_BTN_PRIMARY, C_BTN_PRIMARY_TEXT,
    C_TAB_BAR_BG, C_TAB_ACTIVE, C_TAB_INACTIVE,
    C_TAB_ACTIVE_TEXT,
    FONT_TITLE, FONT_LABEL, FONT_SMALL, FONT_TINY, FONT_TAB, FONT_NARRATIVE,
    NARRATIVE_INTERVAL,
)
from core.engine import GameEngine
from core.game_loop import GameLoop
from data.loader import get_loader
from gui import dialogs
from gui.tabs.tavern_tab import TavernTabMixin
from gui.tabs.wilderness_tab import WildernessTabMixin
from gui.tabs.inn_tab import InnTabMixin
from gui.tabs.shop_tab import ShopTabMixin
from gui.tabs.warehouse_tab import WarehouseTabMixin
from gui.auto_panel import AutoStatusMixin

# pystray 延迟导入
pystray = None
try:
    import pystray as _pystray
    pystray = _pystray
except ImportError:
    pass

TAB_NAMES = ["酒馆", "郊外", "旅店", "商店", "仓库"]

# ---- 文件日志配置 ----
_LOG_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_FILE = os.path.join(_LOG_DIR, "log.txt")
_MAX_LOG_SIZE = 5 * 1024 * 1024  # 5MB 轮转

def _write_file_log(line: str):
    """写入文件日志，超 5MB 自动轮转"""
    try:
        if os.path.exists(LOG_FILE) and os.path.getsize(LOG_FILE) > _MAX_LOG_SIZE:
            bak = LOG_FILE + ".old"
            if os.path.exists(bak):
                os.remove(bak)
            os.rename(LOG_FILE, bak)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


class ExplorationApp(TavernTabMixin, WildernessTabMixin,
                     InnTabMixin, ShopTabMixin, WarehouseTabMixin,
                     AutoStatusMixin):
    """主应用 — 标签页式 RPG + 嵌入式自动化管线面板"""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("探险日志 - Auto Exploration RPG")

        # ---- 同步 Tkinter 缩放因子与系统 DPI（防止文字被裁切）----
        if sys.platform == "win32":
            try:
                import ctypes
                hdc = ctypes.windll.user32.GetDC(0)
                dpi = ctypes.windll.gdi32.GetDeviceCaps(hdc, 88)  # LOGPIXELSX
                ctypes.windll.user32.ReleaseDC(0, hdc)
                scale = dpi / 96.0
                self.root.tk.call('tk', 'scaling', scale)
            except Exception:
                pass

        # 窗口尺寸加大以容纳侧边栏
        self.root.geometry(f"{WIN_W + 140}x{WIN_H}")
        self.root.configure(bg=C_BG)
        self.root.resizable(True, True)
        self.root.minsize(840, 520)

        self.engine = GameEngine()
        self.game_loop = GameLoop(self.root, self.engine)

        self._active_tab = "酒馆"
        self._tab_labels = {}
        self._tab_indicators = {}
        self._after_ids = []
        self._floor_choice_visible = False
        self._tray_icon = None
        self._tray_thread = None
        self._narrative_idx = 0
        self._narrative_lines = []

        self.stat_var = tk.StringVar(value="击杀: 0 | 宝物: 0 | 事件: 0 | 金币: 0")
        self.gold_var = tk.StringVar(value="💰 100 G")

        self._build_ui()
        self.root.bind("<Unmap>", self._on_unmap)
        loaded = self.engine.load()
        if not loaded:
            self._switch_tab("酒馆")
        else:
            self._switch_tab("酒馆" if not self.engine.party else "郊外")
        self._refresh_all()

    # ==================== 系统托盘 ====================
    def _create_tray_icon(self):
        """创建系统托盘图标（Pillow 生成 64x64 像素图标）"""
        if pystray is None:
            return

        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.ellipse([4, 4, 60, 60], fill="#2A9D8F", outline="#1A7D6F", width=2)
        draw.rectangle([28, 14, 36, 46], fill="#F5F0E6")
        draw.polygon([24, 14, 40, 14, 32, 4], fill="#F5F0E6")
        draw.rectangle([22, 46, 42, 50], fill="#F5F0E6")

        menu = pystray.Menu(
            pystray.MenuItem("显示窗口", self._tray_show, default=True),
            pystray.MenuItem("退出", self._tray_exit),
        )
        self._tray_icon = pystray.Icon(
            f"exploration_log_{os.getpid()}", img, "探险日志", menu)

    def _tray_show(self, icon=None, item=None):
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def _tray_exit(self, icon=None, item=None):
        self.engine.save()
        if self._tray_icon:
            self._tray_icon.stop()
            self._tray_icon = None
        self.root.destroy()

    def _on_unmap(self, event=None):
        if pystray and self._tray_icon and self.root.state() == 'iconic':
            self._minimize_to_tray()

    def _minimize_to_tray(self):
        if self.root.state() == 'iconic':
            self.root.deiconify()
        self.root.withdraw()
        try:
            if self._tray_thread is None or not self._tray_thread.is_alive():
                self._tray_thread = threading.Thread(
                    target=self._tray_icon.run, daemon=True)
                self._tray_thread.start()
        except Exception:
            self.engine.save()
            self.root.destroy()

    def _on_close(self):
        if not messagebox.askyesno("退出确认", "确定要退出游戏吗？\n未保存的进度将丢失。"):
            return
        if hasattr(self, 'auto_engine') and self.auto_engine:
            self.auto_engine.stop()
        self.engine.save()
        if self._tray_icon:
            try:
                self._tray_icon.stop()
            except Exception:
                pass
            self._tray_icon = None
        try:
            messagebox.showinfo("存档完成", "游戏进度已保存！\n下次启动将自动读取。")
        except Exception:
            pass
        self.root.destroy()

    # ==================== 整体布局 ====================
    def _build_ui(self):
        # --- 先创建自动化控制按钮（供标题栏使用）---
        try:
            self._build_auto_controls()
        except Exception:
            self._ctrl_frame = None
            _write_file_log("[WARN] _build_auto_controls() 失败，控制按钮不可用")

        # --- 顶部标题栏 ---
        title_bar = tk.Frame(self.root, bg=C_PANEL_BG, height=44)
        title_bar.pack(fill=tk.X)
        title_bar.pack_propagate(False)

        tk.Label(title_bar, text="⚔ 探险日志", font=FONT_TITLE,
                 bg=C_PANEL_BG, fg=C_TEXT).pack(side=tk.LEFT, padx=16, pady=6)

        self.gold_var = tk.StringVar(value="💰 100 G")
        tk.Label(title_bar, textvariable=self.gold_var, font=FONT_LABEL,
                 bg=C_PANEL_BG, fg=C_GOLD).pack(side=tk.LEFT, padx=16, pady=6)

        # ---- 将自动化控制按钮嵌入标题栏右侧 ----
        if self._ctrl_frame is not None:
            self._ctrl_frame.pack(side=tk.RIGHT, padx=(0, 12), pady=6)

        # --- 标签栏 ---
        tab_bar = tk.Frame(self.root, bg=C_TAB_BAR_BG, height=38)
        tab_bar.pack(fill=tk.X)
        tab_bar.pack_propagate(False)

        n_tabs = len(TAB_NAMES)
        for i, name in enumerate(TAB_NAMES):
            btn = tk.Label(tab_bar, text=name, font=FONT_TAB,
                           bg=C_TAB_BAR_BG, fg=C_TAB_INACTIVE,
                           cursor="hand2", padx=16, pady=6)
            btn.place(relx=(i / n_tabs), rely=0, relwidth=(1 / n_tabs), height=34)
            btn.bind("<Button-1>", lambda e, n=name: self._switch_tab(n))
            btn.bind("<Enter>", lambda e, w=btn: w.configure(fg=C_TAB_ACTIVE_TEXT))
            btn.bind("<Leave>", lambda e, w=btn, n=name: self._tab_leave(w, n))
            self._tab_labels[name] = btn

            ind = tk.Frame(tab_bar, bg=C_TAB_ACTIVE, height=4)
            ind.place(relx=(i / n_tabs), rely=1.0, relwidth=(1 / n_tabs), height=4, anchor="sw")
            self._tab_indicators[name] = ind

        ttk.Separator(self.root, orient=tk.HORIZONTAL).pack(fill=tk.X)

        # --- 内容区 ---
        self.content_frame = tk.Frame(self.root, bg=C_CONTENT_BG)
        self.content_frame.pack(fill=tk.BOTH, expand=True)

        self._tab_content = {}
        self._build_tavern_tab()
        self._build_outskirts_tab()
        self._build_inn_tab()
        self._build_shop_tab()
        self._build_warehouse_tab()

        # --- 构建嵌入式自动化面板（侧边栏+底部增强状态栏）---
        self._build_auto_status_panel()

        # --- 底部叙事滚动字幕 ---
        narration_bar = tk.Frame(self.root, bg=C_PANEL_BG, height=42)
        narration_bar.pack(fill=tk.X, side=tk.BOTTOM)

        self.narration_canvas = tk.Canvas(narration_bar, bg=C_PANEL_BG,
                                           height=42, highlightthickness=0, bd=0)
        self.narration_canvas.pack(fill=tk.BOTH, expand=True)
        self._narration_scroll_id = None

        if pystray:
            self._create_tray_icon()

    # ==================== 冒险日志 (共享方法) ====================
    def _log(self, msg: str, tag: str = None):
        self.engine.battle_log.append(msg)
        if len(self.engine.battle_log) > self.engine.max_log_lines:
            self.engine.battle_log = self.engine.battle_log[-self.engine.max_log_lines:]

        ts = time.strftime("%H:%M:%S")
        line = f"[{ts}] {msg}"
        if tag:
            line = f"[{ts}] [{tag}] {msg}"

        # 写入内存日志控件（如果有）
        if hasattr(self, 'log_text') and self.log_text is not None:
            try:
                self.log_text.configure(state=tk.NORMAL)
                self.log_text.insert(tk.END, f"[{ts}] ", "timestamp")
                if tag:
                    self.log_text.insert(tk.END, f"{msg}\n", tag)
                else:
                    self.log_text.insert(tk.END, f"{msg}\n")
                self.log_text.see(tk.END)
                self.log_text.configure(state=tk.DISABLED)
            except Exception:
                pass

        # 写入文件日志
        try:
            _write_file_log(line)
        except Exception:
            pass

    # ==================== 叙事滚动字幕 ====================
    def _start_narrative(self):
        loader = get_loader()
        if loader.narratives:
            self._narrative_lines = list(loader.narratives)
        else:
            self._narrative_lines = [
                "冒险者们踏上了通往未知的旅程……",
                "远处传来野兽的低吼，黑暗中有东西在窥视。",
                "古老的石碑上刻着模糊的符文，似乎在诉说被遗忘的历史。",
                "微风吹过荒原，卷起一阵尘土。",
                "地下城的气息愈发浓重，空气中弥漫着硫磺和铁锈的味道。",
                "队伍在黑暗中摸索前进，每一步都可能触发古老的陷阱。",
                "传说这座地下城中埋藏着无数宝藏，但从未有人活着带出去过。",
                "火把的光芒在墙壁上投下摇曳的影子，仿佛在警告着什么。",
                "冒险者的直觉告诉队伍，前方不远处就是 BOSS 的巢穴。",
                "金币碰撞的清脆响声在洞穴中回荡……",
                "队伍在一处岔路口停下脚步，左右两条路都通向未知的黑暗。",
                "石壁上的苔藓发出微弱的荧光，勉强照亮前进的道路。",
                "远处传来铁链拖地的声音，越来越近……",
            ]
        random.shuffle(self._narrative_lines)
        self._scroll_narrative()

    def _scroll_narrative(self):
        if self._narration_scroll_id:
            self.root.after_cancel(self._narration_scroll_id)
            self._narration_scroll_id = None

        if not self._narrative_lines:
            self._narration_scroll_id = self.root.after(NARRATIVE_INTERVAL,
                                                         self._scroll_narrative)
            return

        text = self._narrative_lines[self._narrative_idx]
        self._narrative_idx = (self._narrative_idx + 1) % len(self._narrative_lines)
        if self._narrative_idx == 0:
            random.shuffle(self._narrative_lines)

        cw = self.narration_canvas.winfo_width()
        if cw < 50:
            cw = WIN_W - 20

        ch = self.narration_canvas.winfo_height()
        if ch < 10:
            ch = 42

        self.narration_canvas.delete("narrative")

        text_id = self.narration_canvas.create_text(
            cw, ch // 2, text=text, anchor=tk.W,
            font=FONT_NARRATIVE, fill=C_TEXT_LIGHT, tags="narrative"
        )

        self.narration_canvas.update_idletasks()
        bbox = self.narration_canvas.bbox(text_id)
        text_width = (bbox[2] - bbox[0]) if bbox else cw

        total_distance = cw + text_width
        speed = 1.5
        interval = 25
        total_steps = max(1, int(total_distance / speed))

        self._narrative_scroll_step = 0

        def _animate():
            self._narrative_scroll_step += 1
            self.narration_canvas.move("narrative", -speed, 0)

            if self._narrative_scroll_step >= total_steps:
                self.narration_canvas.delete("narrative")
                self._narration_scroll_id = self.root.after(
                    600, self._scroll_narrative)
            else:
                self._narration_scroll_id = self.root.after(interval, _animate)

        _animate()

    def _set_narrative(self, text: str):
        """临时设置叙事文字"""
        if self._narration_scroll_id:
            self.root.after_cancel(self._narration_scroll_id)
            self._narration_scroll_id = None

        cw = self.narration_canvas.winfo_width()
        if cw < 50:
            cw = WIN_W - 20

        ch = self.narration_canvas.winfo_height()
        if ch < 10:
            ch = 42

        self.narration_canvas.delete("narrative")

        text_id = self.narration_canvas.create_text(
            cw, ch // 2, text=text, anchor=tk.W,
            font=FONT_NARRATIVE, fill=C_ACCENT_TEAL, tags="narrative"
        )

        self.narration_canvas.update_idletasks()
        bbox = self.narration_canvas.bbox(text_id)
        text_width = (bbox[2] - bbox[0]) if bbox else cw

        total_distance = cw + text_width
        speed = 1.5
        interval = 25
        total_steps = max(1, int(total_distance / speed))

        self._narrative_scroll_step = 0

        def _animate_temp():
            self._narrative_scroll_step += 1
            self.narration_canvas.move("narrative", -speed, 0)

            if self._narrative_scroll_step >= total_steps:
                self._narration_scroll_id = self.root.after(
                    400, self._scroll_narrative)
            else:
                self._narration_scroll_id = self.root.after(interval, _animate_temp)

        _animate_temp()

    # ==================== 标签切换 ====================
    def _switch_tab(self, name: str):
        self._active_tab = name
        for tab_name, lbl in self._tab_labels.items():
            if tab_name == name:
                lbl.configure(fg=C_TAB_ACTIVE_TEXT)
                self._tab_indicators[tab_name].configure(bg=C_TAB_ACTIVE)
            else:
                lbl.configure(fg=C_TAB_INACTIVE)
                self._tab_indicators[tab_name].configure(bg=C_TAB_BAR_BG)

        for frame in self._tab_content.values():
            frame.pack_forget()
        self._tab_content[name].pack(fill=tk.BOTH, expand=True)

        if name == "酒馆":
            self._refresh_tavern()
        elif name == "旅店":
            self._refresh_inn()
        elif name == "商店":
            self._refresh_shop()
        elif name == "仓库":
            self._refresh_warehouse()

    def _tab_leave(self, widget, name):
        widget.configure(fg=C_TAB_ACTIVE_TEXT if self._active_tab == name else C_TAB_INACTIVE)

    # ==================== 全局刷新 ====================
    def _refresh_all(self):
        self.gold_var.set(f"💰 {self.engine.gold} G")
        self.stat_var.set(
            f"击杀: {self.engine.total_monsters_killed}  |  "
            f"宝物: {self.engine.total_treasures_found}  |  "
            f"事件: {self.engine.total_events_triggered}  |  "
            f"金币: {self.engine.gold}"
        )

        self._update_dungeon_list()

        if self._active_tab == "旅店":
            self._refresh_inn()
        elif self._active_tab == "仓库":
            self._refresh_warehouse()
        elif self._active_tab == "酒馆":
            self._refresh_tavern()

        self.engine.save()

    def _update_dungeon_list(self):
        loader = get_loader()
        names = [d.name for d in loader.dungeons[:self.engine.unlocked_dungeons]]
        self.dungeon_combo["values"] = names
        if names and (not self.dungeon_var.get() or self.dungeon_var.get() not in names):
            self.dungeon_var.set(names[0])

    # ==================== 工具方法 ====================
    def _bind_hover(self, widget, normal_color, hover_color):
        widget.bind("<Enter>", lambda e: widget.configure(bg=hover_color))
        widget.bind("<Leave>", lambda e: widget.configure(bg=normal_color))

    def _disable_widget(self, widget):
        widget.configure(fg=C_TEXT_HINT, bg="#C4B998")
        widget.unbind("<Button-1>")
        widget.unbind("<Enter>")
        widget.unbind("<Leave>")

    def _enable_widget(self, widget):
        widget.configure(fg=C_BTN_PRIMARY_TEXT, bg=C_BTN_PRIMARY)
        widget.bind("<Button-1>", lambda e: self._start_explore())
        self._bind_hover(widget, C_BTN_PRIMARY, "#238B7E")

    def _bind_mousewheel(self, canvas):
        canvas.bind("<MouseWheel>",
                    lambda e: canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))

    def _unbind_mousewheel(self, canvas):
        canvas.unbind("<MouseWheel>")

    def run(self):
        """启动应用"""
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._start_narrative()
        self.root.mainloop()
