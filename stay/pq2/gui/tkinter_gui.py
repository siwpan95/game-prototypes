"""Tkinter GUI — Progress Quest 2"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import json
import os
import ctypes
import sys
from datetime import datetime, timedelta
from ..types import (
    Equipment, CurrentActionType, Color, GameState, EQUIPMENT_LABELS, SaveError
)
from ..newgame import NewGame
from ..localization import translate, translate_action_label, translate_quest_label, get_cn
from ..themes import THEMES, DEFAULT_THEME


# ── 加载本地字体 ──────────────────────────────────────────────
# 项目根目录 = pq2/gui/ 的上三级；本地资源（字体）现归入根下 assets/ 子目录
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def _resolve_resource(rel_path: str) -> str:
    """解析资源路径（A5）：PyInstaller 冻结包用 sys._MEIPASS，
    否则回退到项目根目录。rel_path 可跨子目录，如 'assets/STKAITI.TTF'。"""
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return os.path.join(base, rel_path)
    return os.path.join(_PROJECT_ROOT, rel_path)

# 字体归入 assets/（原散落于项目根，已于 2026-07-27 归档整理）
_FONT_PATH = _resolve_resource(os.path.join("assets", "STKAITI.TTF"))
_LOCAL_FONT_FAMILY = "STKaiti"

def _register_local_font(font_path):
    """通过 Win32 API 注册本地字体文件，使 tkinter 可识别"""
    if os.name == "nt" and os.path.exists(font_path):
        try:
            # FR_PRIVATE = 0x10 —— 仅当前进程可见，不污染系统
            result = ctypes.windll.gdi32.AddFontResourceExW(font_path, 0x10, 0)
            if result > 0:
                return True
        except Exception:
            pass
    return False

_FONT_LOADED = _register_local_font(_FONT_PATH)

def _get_font_family():
    """返回应使用的字体族名（优先本地 STKaiti，回退 Segoe UI）"""
    if _FONT_LOADED:
        return _LOCAL_FONT_FAMILY
    # 回退：尝试系统自带中文字体
    for name in ("STKaiti", "Microsoft YaHei", "SimSun", "Segoe UI"):
        try:
            tk.font.Font(family=name, size=10)
            return name
        except Exception:
            continue
    return "Segoe UI"

_FONT_FAMILY = _get_font_family()


# 颜色常量
COLOR_MAP = {
    Color.Gray: "#808080",
    Color.Silver: "#C0C0C0",
    Color.White: "#000000",
    Color.Yellow: "#DAA520",
    Color.Red: "#DC143C",
}

FONT_TITLE      = (_FONT_FAMILY, 16, "bold")
FONT_HEADING    = (_FONT_FAMILY, 12, "bold")
FONT_NORMAL     = (_FONT_FAMILY, 10)
FONT_SMALL      = (_FONT_FAMILY, 9)
FONT_MONO       = ("Consolas", 10)
FONT_TITLE_LARGE= (_FONT_FAMILY, 24, "bold")
FONT_STAT       = ("Consolas", 12, "bold")

_SETTINGS_PATH = _resolve_resource("settings.json")


def _load_settings():
    try:
        with open(_SETTINGS_PATH, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"theme": DEFAULT_THEME, "is_cn": True}


def _save_settings(settings):
    try:
        with open(_SETTINGS_PATH, "w") as f:
            json.dump(settings, f)
    except Exception:
        pass


class TkGUI:
    """Tkinter GUI 实现"""

    def __init__(self, game):
        self._game = game
        self._game._save_error_handler = self._on_save_error  # A4 契约接线
        self._root = None
        self._current_frame = None
        self._update_timer = None
        self._speed_ms = 100
        self._paused = False
        self._birthday = datetime.now()
        self._total_seconds = 0
        self._settings = _load_settings()
        self._theme = self._settings.get("theme", DEFAULT_THEME)
        self._cn_mode = self._settings.get("is_cn", True)
        self._in_creator = False  # #2：标记角色创建界面是否活跃，用于守卫刷新回调

    @property
    def _t(self):
        """当前主题配置"""
        return THEMES[self._theme]

    def run(self):
        self._root = tk.Tk()
        self._root.title("Progress Quest 2 — The Progression")
        self._root.geometry("1024x700")
        self._root.minsize(900, 600)
        self._root.configure(bg="#f5f0e8")
        self._root.protocol("WM_DELETE_WINDOW", self._on_close)

        # A11：启动时做一次本地化缺键覆盖审计（上报监控，而非仅静默回退英文）
        self._report_localization_coverage()

        # A7 启动自愈：优先尝试继续默认存档（savefile.pq2）；损坏则回退 .bak
        self._try_autoload_with_recovery()

        if self._game.get_state() == GameState.Ready:
            self._show_game_screen()
        else:
            self._show_main_menu()

        self._root.mainloop()

    def _clear_frame(self):
        if self._current_frame:
            self._current_frame.destroy()
            self._current_frame = None
        if self._update_timer:
            self._root.after_cancel(self._update_timer)
            self._update_timer = None

    # ========== 主菜单 ==========

    def _show_main_menu(self):
        self._clear_frame()
        frame = tk.Frame(self._root, bg="#f5f0e8")
        frame.place(relx=0, rely=0, relwidth=1, relheight=1)
        self._current_frame = frame

        cn = self._cn_mode

        # Logo
        logo_text = (
            " ____  ____    ___ \n"
            "|  _ \\|  _ \\  |_ _|\n"
            "| |_) | |_) |  | | \n"
            "|  __/|  _ <   | | \n"
            "| |   | |_) |  | | \n"
            "|_|   |____/  |___|\n\n"
            "Progress Quest 2\n"
            "The Progression"
        )
        tk.Label(
            frame, text=logo_text, font=("Courier New", 14, "bold"),
            bg="#f5f0e8", fg="#4a3728", justify="center"
        ).pack(pady=(60, 30))

        tk.Label(
            frame, text=get_cn("A Zero-Player RPG Adventure") if cn else "A Zero-Player RPG Adventure",
            font=FONT_HEADING, bg="#f5f0e8", fg="#666"
        ).pack(pady=(0, 40))

        btn_style = {"font": FONT_HEADING, "width": 18, "height": 2, "bd": 2}

        tk.Button(
            frame, text=get_cn("New Game") if cn else "New Game",
            command=self._on_new_game,
            bg="#6b8e5a", fg="white", activebackground="#5a7a4a", **btn_style
        ).pack(pady=8)

        tk.Button(
            frame, text=get_cn("Load Game") if cn else "Load Game",
            command=self._on_load_game,
            bg="#5a7a8e", fg="white", activebackground="#4a6a7e", **btn_style
        ).pack(pady=8)

        tk.Button(
            frame, text=get_cn("Exit") if cn else "Exit",
            command=self._on_close,
            bg="#8e5a5a", fg="white", activebackground="#7e4a4a", **btn_style
        ).pack(pady=8)

    # ========== 角色创建 ==========

    def _show_character_creator(self, new_game: NewGame):
        self._clear_frame()
        self._new_game = new_game
        self._in_creator = True  # #2：进入创建界面，允许刷新回调
        cn = self._cn_mode

        frame = tk.Frame(self._root, bg="#f5f0e8")
        frame.place(relx=0, rely=0, relwidth=1, relheight=1)
        self._current_frame = frame

        # 顶部标题
        tk.Label(
            frame, text=get_cn("Character Creation") if cn else "Character Creation",
            font=FONT_TITLE, bg="#f5f0e8", fg="#4a3728"
        ).pack(pady=(15, 10))

        # 内容区域
        content = tk.Frame(frame, bg="#f5f0e8")
        content.pack(fill="both", expand=True, padx=30, pady=10)

        # --- 左列: 名字 + 种族 + 职业 ---
        left_col = tk.Frame(content, bg="#f5f0e8")
        left_col.pack(side="left", fill="both", expand=True, padx=(0, 10))

        # 名字
        name_frame = tk.LabelFrame(
            left_col, text=get_cn("Name") if cn else "Name",
            font=FONT_HEADING, bg="#f5f0e8"
        )
        name_frame.pack(fill="x", pady=5)
        name_inner = tk.Frame(name_frame, bg="#f5f0e8")
        name_inner.pack(fill="x", padx=10, pady=8)

        self._name_var = tk.StringVar(value=new_game.get_name())
        tk.Entry(name_inner, textvariable=self._name_var, font=FONT_NORMAL, width=25).pack(side="left", padx=(0, 10))
        tk.Button(
            name_inner, text=get_cn("Random") if cn else "Random",
            command=self._on_random_name,
            bg="#d4c5a9", font=FONT_SMALL
        ).pack(side="left")

        # 种族
        race_frame = tk.LabelFrame(
            left_col, text=get_cn("Race") if cn else "Race",
            font=FONT_HEADING, bg="#f5f0e8"
        )
        race_frame.pack(fill="both", expand=True, pady=5)

        race_scroll = tk.Frame(race_frame, bg="#f5f0e8")
        race_scroll.pack(fill="both", expand=True, padx=5, pady=5)

        self._race_var = tk.StringVar(value=new_game.get_race())
        races = new_game.get_available_races()
        for i, r in enumerate(races):
            display_r = translate(r) if cn else r
            tk.Radiobutton(
                race_scroll, text=display_r, variable=self._race_var, value=r,
                font=FONT_SMALL, bg="#f5f0e8", anchor="w",
                command=lambda r=r: new_game.set_race(r)
            ).grid(row=i // 2, column=i % 2, sticky="w", padx=5, pady=1)

        # 职业
        class_frame = tk.LabelFrame(
            left_col, text=get_cn("Class") if cn else "Class",
            font=FONT_HEADING, bg="#f5f0e8"
        )
        class_frame.pack(fill="both", expand=True, pady=5)

        class_scroll = tk.Frame(class_frame, bg="#f5f0e8")
        class_scroll.pack(fill="both", expand=True, padx=5, pady=5)

        self._class_var = tk.StringVar(value=new_game.get_class())
        classes = new_game.get_available_classes()
        for i, c in enumerate(classes):
            display_c = translate(c) if cn else c
            tk.Radiobutton(
                class_scroll, text=display_c, variable=self._class_var, value=c,
                font=FONT_SMALL, bg="#f5f0e8", anchor="w",
                command=lambda c=c: new_game.set_class(c)
            ).grid(row=i // 2, column=i % 2, sticky="w", padx=5, pady=1)

        # --- 右列: 属性 ---
        right_col = tk.Frame(content, bg="#f5f0e8")
        right_col.pack(side="right", fill="both", expand=True, padx=(10, 0))

        stats_frame = tk.LabelFrame(
            right_col, text=get_cn("Attributes") if cn else "Attributes",
            font=FONT_HEADING, bg="#f5f0e8"
        )
        stats_frame.pack(fill="both", expand=True, pady=5)

        stats_inner = tk.Frame(stats_frame, bg="#f5f0e8")
        stats_inner.pack(padx=20, pady=15)

        self._stat_labels = {}
        stat_names = ["STR", "CON", "DEX", "INT", "WIS", "CHA"]
        for i, sn in enumerate(stat_names):
            tk.Label(stats_inner, text=sn, font=FONT_STAT, bg="#f5f0e8", fg="#4a3728").grid(
                row=i, column=0, sticky="e", padx=(0, 10), pady=3
            )
            lbl = tk.Label(stats_inner, text="00", font=FONT_STAT, bg="#f5f0e8", fg="#2a2a2a", width=4, anchor="e")
            lbl.grid(row=i, column=1, sticky="w", pady=3)
            self._stat_labels[sn] = lbl

        # Total
        tk.Label(stats_inner, text="─" * 8, font=FONT_SMALL, bg="#f5f0e8", fg="#999").grid(
            row=6, column=0, columnspan=2, pady=(8, 0)
        )
        self._total_label = tk.Label(stats_inner, text=f"{get_cn('Total') if cn else 'Total'}: 0", font=FONT_STAT, bg="#f5f0e8")
        self._total_label.grid(row=7, column=0, columnspan=2, pady=(3, 0))

        # Roll / Unroll / Auto Roll
        btn_frame = tk.Frame(stats_inner, bg="#f5f0e8")
        btn_frame.grid(row=8, column=0, columnspan=2, pady=(15, 5))
        tk.Button(
            btn_frame, text=get_cn("Roll") if cn else "Roll",
            command=self._on_roll,
            bg="#6b8e5a", fg="white", font=FONT_HEADING, width=8
        ).pack(side="left", padx=3)
        self._unroll_btn = tk.Button(
            btn_frame, text=get_cn("Unroll") if cn else "Unroll",
            command=self._on_unroll,
            bg="#8e7a5a", fg="white", font=FONT_HEADING, width=8, state="disabled"
        )
        self._unroll_btn.pack(side="left", padx=3)
        self._auto_roll_btn = tk.Button(
            btn_frame, text=get_cn("Auto") if cn else "Auto",
            command=self._on_auto_roll,
            bg="#4a7a8e", fg="white", font=FONT_HEADING, width=6
        )
        self._auto_roll_btn.pack(side="left", padx=3)

        # 目标属性设置
        target_frame = tk.Frame(stats_inner, bg="#f5f0e8")
        target_frame.grid(row=9, column=0, columnspan=2, pady=(10, 0))
        tk.Label(
            target_frame, text=get_cn("Target (optional):") if cn else "Target (optional):",
            font=FONT_SMALL, bg="#f5f0e8", fg="#888"
        ).pack()
        target_inputs = tk.Frame(target_frame, bg="#f5f0e8")
        target_inputs.pack(pady=3)
        self._target_vars = {}
        for sn in stat_names:
            row_f = tk.Frame(target_inputs, bg="#f5f0e8")
            row_f.pack(side="left", padx=3)
            tk.Label(row_f, text=sn, font=("Consolas", 7), bg="#f5f0e8", fg="#999").pack()
            var = tk.StringVar(value="0")
            tk.Entry(row_f, textvariable=var, font=("Consolas", 8), width=3, justify="center").pack()
            self._target_vars[sn] = var
        # Total target
        row_f = tk.Frame(target_inputs, bg="#f5f0e8")
        row_f.pack(side="left", padx=5)
        tk.Label(row_f, text=get_cn("TOTAL") if cn else "TOTAL",
                 font=("Consolas", 7, "bold"), bg="#f5f0e8", fg="#c66").pack()
        self._target_total_var = tk.StringVar(value="0")
        tk.Entry(row_f, textvariable=self._target_total_var, font=("Consolas", 8, "bold"), width=3, justify="center").pack()

        # Create 按钮
        tk.Button(
            right_col, text=get_cn("SOLD! Begin Adventure") if cn else "SOLD! Begin Adventure",
            command=self._on_confirm,
            bg="#4a7a4a", fg="white", font=(_FONT_FAMILY, 14, "bold"),
            width=24, height=2
        ).pack(pady=15)

        # 刷新属性显示
        self._refresh_stats(new_game)
        # 设置属性变化回调（用于自动投骰时刷新UI）
        new_game.set_stats_changed_callback(lambda: self._root.after(0, self._refresh_stats))

    def _refresh_stats(self, new_game: NewGame = None):
        # #2：若已离开创建界面（确认/关闭），控件可能已销毁，跳过刷新避免 TclError
        if not getattr(self, "_in_creator", False):
            return
        if new_game is None:
            new_game = self._new_game
        try:
            cn = self._cn_mode
            stat_names = ["STR", "CON", "DEX", "INT", "WIS", "CHA"]
            values = [new_game.get_str(), new_game.get_con(), new_game.get_dex(),
                      new_game.get_int(), new_game.get_wis(), new_game.get_cha()]
            for sn, v in zip(stat_names, values):
                self._stat_labels[sn].config(text=str(v))

            total = new_game.get_total()
            color = new_game.get_total_color()
            fg_color = COLOR_MAP.get(color, "#000000")
            total_label = get_cn("Total") if cn else "Total"
            self._total_label.config(text=f"{total_label}: {total}", fg=fg_color)

            self._unroll_btn.config(state="normal" if new_game.can_unroll() else "disabled")

            # 自动投骰按钮状态
            if not new_game.is_auto_rolling():
                self._auto_roll_btn.config(text=get_cn("Auto") if cn else "Auto", bg="#4a7a8e")
        except tk.TclError:
            # 控件在切换界面过程中被销毁，静默忽略
            return

    def _on_random_name(self):
        self._new_game.generate_name()
        self._name_var.set(self._new_game.get_name())

    def _on_roll(self):
        self._new_game.re_roll()
        self._refresh_stats()

    def _on_unroll(self):
        self._new_game.un_roll()
        self._refresh_stats()

    def _on_auto_roll(self):
        if self._new_game.is_auto_rolling():
            # 正在自动投骰中，停止
            self._new_game.stop_auto_roll()
            self._auto_roll_btn.config(text=get_cn("Auto") if self._cn_mode else "Auto", bg="#4a7a8e")
            return

        # 收集目标值
        targets = {}
        stat_names = ["STR", "CON", "DEX", "INT", "WIS", "CHA"]
        for sn in stat_names:
            try:
                v = int(self._target_vars[sn].get())
                if v > 0:
                    targets[sn] = v
            except ValueError:
                pass
        try:
            total_v = int(self._target_total_var.get())
            if total_v > 0:
                targets["Total"] = total_v
        except ValueError:
            pass

        if not targets:
            # #2 修复：原先默认 {Total:1} 会被瞬间满足（Total 恒 >=1），
            # 形同空转且注释误导。改为一个可达的“强力角色”目标，让自动投骰真正有意义。
            targets["Total"] = 78

        self._new_game.set_auto_roll_targets(targets)
        self._new_game.start_auto_roll()
        self._auto_roll_btn.config(text=get_cn("Stop") if self._cn_mode else "Stop", bg="#c0392b")

    def _on_confirm(self):
        # #2：确认前停止自动投骰后台线程，避免线程继续通过 after(0) 刷新已销毁的创建界面控件（TclError 崩溃）
        self._new_game.stop_auto_roll()
        self._in_creator = False
        self._new_game.set_name(self._name_var.get())
        self._new_game.confirm_character()
        self._show_game_screen()

    # ========== 游戏界面 ==========

    def _show_game_screen(self):
        self._clear_frame()
        cn = self._cn_mode
        frame = tk.Frame(self._root, bg="#f5f0e8")
        frame.place(relx=0, rely=0, relwidth=1, relheight=1)
        self._current_frame = frame

        # 三列布局
        left_col = tk.Frame(frame, bg="#f5f0e8", width=300)
        left_col.pack(side="left", fill="both", padx=(10, 5), pady=10)
        left_col.pack_propagate(False)

        mid_col = tk.Frame(frame, bg="#f5f0e8", width=340)
        mid_col.pack(side="left", fill="both", padx=5, pady=10)
        mid_col.pack_propagate(False)

        right_col = tk.Frame(frame, bg="#f5f0e8")
        right_col.pack(side="left", fill="both", expand=True, padx=(5, 10), pady=10)

        # 顶部控制栏（保存 + 语言切换 + 主题切换）
        control_bar = tk.Frame(frame, bg=self._t["bg"])
        control_bar.place(relx=1.0, y=5, anchor="ne")
        tk.Button(
            control_bar, text="保存存档" if cn else "Save",
            command=self._on_save,
            font=FONT_SMALL, bg="#6b8e5a", fg="white",
            relief="flat", padx=8
        ).pack(side="right", padx=3)
        tk.Button(
            control_bar, text="中文/EN" if self._cn_mode else "EN/中文",
            command=self._toggle_language,
            font=FONT_SMALL, bg=self._t["button_bg"], fg=self._t["fg"],
            relief="flat", padx=8
        ).pack(side="right", padx=3)
        tk.Button(
            control_bar, text=self._t["name"],
            command=self._toggle_theme,
            font=FONT_SMALL, bg=self._t["button_bg"], fg=self._t["fg"],
            relief="flat", padx=8
        ).pack(side="right", padx=3)

        # ---- 左列: 角色信息 + 法术 ----
        char_frame = tk.LabelFrame(
            left_col, text=get_cn("Character") if cn else "Character",
            font=FONT_HEADING, bg="#f5f0e8"
        )
        char_frame.pack(fill="x", pady=(0, 5))

        self._char_name_lbl = tk.Label(char_frame, text="", font=FONT_TITLE, bg="#f5f0e8", fg="#4a3728")
        self._char_name_lbl.pack(pady=(5, 0))

        self._char_race_lbl = tk.Label(char_frame, text="", font=FONT_NORMAL, bg="#f5f0e8", fg="#555")
        self._char_race_lbl.pack()

        self._char_level_lbl = tk.Label(char_frame, text="", font=FONT_HEADING, bg="#f5f0e8", fg="#333")
        self._char_level_lbl.pack(pady=(5, 5))

        # 属性
        self._stat_display = {}
        stats = ["STR", "CON", "DEX", "INT", "WIS", "CHA", "HP", "MP"]
        stat_grid = tk.Frame(char_frame, bg="#f5f0e8")
        stat_grid.pack(padx=15, pady=5)
        for i, s in enumerate(stats):
            label_text = get_cn(s) if cn else s
            tk.Label(stat_grid, text=label_text, font=FONT_SMALL, bg="#f5f0e8", fg="#666").grid(
                row=i, column=0, sticky="e", padx=(0, 5), pady=1
            )
            lbl = tk.Label(stat_grid, text="0", font=FONT_NORMAL, bg="#f5f0e8", fg="#2a2a2a", anchor="e", width=6)
            lbl.grid(row=i, column=1, sticky="w", pady=1)
            self._stat_display[s] = lbl

        self._gold_lbl = tk.Label(char_frame, text="", font=FONT_HEADING, bg="#f5f0e8", fg="#DAA520")
        self._gold_lbl.pack(pady=(5, 10))

        # 法术
        spells_frame = tk.LabelFrame(
            left_col, text=get_cn("Spells") if cn else "Spells",
            font=FONT_HEADING, bg="#f5f0e8"
        )
        spells_frame.pack(fill="both", expand=True)
        self._spells_text = tk.Text(spells_frame, font=FONT_SMALL, bg="#f5f0e8", fg="#333",
                                     wrap="word", bd=0, relief="flat", state="disabled", height=10)
        self._spells_text.pack(fill="both", expand=True, padx=5, pady=5)

        # ---- 中列: 装备 + 背包 ----
        equip_frame = tk.LabelFrame(
            mid_col, text=get_cn("Equipment") if cn else "Equipment",
            font=FONT_HEADING, bg="#f5f0e8"
        )
        equip_frame.pack(fill="x", pady=(0, 5))

        self._equip_labels = {}
        for i in range(11):
            name = EQUIPMENT_LABELS[i]
            display_name = get_cn(name) if cn else name
            row_frame = tk.Frame(equip_frame, bg="#f5f0e8")
            row_frame.pack(fill="x", padx=10, pady=1)
            tk.Label(row_frame, text=f"{display_name}:", font=FONT_SMALL, bg="#f5f0e8", fg="#666",
                     width=12, anchor="e").pack(side="left", padx=(0, 5))
            lbl = tk.Label(row_frame, text="", font=FONT_SMALL, bg="#f5f0e8", fg="#2a2a2a", anchor="w")
            lbl.pack(side="left", fill="x", expand=True)
            self._equip_labels[name] = lbl

        # 背包
        inv_frame = tk.LabelFrame(
            mid_col, text=get_cn("Inventory") if cn else "Inventory",
            font=FONT_HEADING, bg="#f5f0e8"
        )
        inv_frame.pack(fill="both", expand=True)
        self._inv_text = tk.Text(inv_frame, font=FONT_SMALL, bg="#f5f0e8", fg="#333",
                                  wrap="word", bd=0, relief="flat", state="disabled", height=10)
        self._inv_text.pack(fill="both", expand=True, padx=5, pady=5)

        # ---- 右列: 行动 + 剧情 + 任务 ----
        # 当前行动
        action_frame = tk.LabelFrame(
            right_col, text=get_cn("Current Action") if cn else "Current Action",
            font=FONT_HEADING, bg="#f5f0e8"
        )
        action_frame.pack(fill="x", pady=(0, 5))

        self._action_lbl = tk.Label(
            action_frame,
            text=get_cn("Loading") if cn else "Loading...",
            font=FONT_NORMAL, bg="#f5f0e8", fg="#4a3728", wraplength=300
        )
        self._action_lbl.pack(padx=10, pady=(5, 0))

        # 进度条
        self._progress_canvas = tk.Canvas(action_frame, height=26, bg="#ddd", highlightthickness=0)
        self._progress_canvas.pack(fill="x", padx=10, pady=8)

        self._progress_text = tk.Label(action_frame, text="", font=FONT_SMALL, bg="#f5f0e8", fg="#555")
        self._progress_text.pack(pady=(0, 5))

        # 剧情
        plot_frame = tk.LabelFrame(
            right_col, text=get_cn("Plot") if cn else "Plot",
            font=FONT_HEADING, bg="#f5f0e8"
        )
        plot_frame.pack(fill="both", expand=True, pady=(0, 5))
        self._plot_text = tk.Text(plot_frame, font=FONT_SMALL, bg="#f5f0e8", fg="#333",
                                   wrap="word", bd=0, relief="flat", state="disabled", height=6)
        self._plot_text.pack(fill="both", expand=True, padx=5, pady=5)

        # 任务
        quest_frame = tk.LabelFrame(
            right_col, text=get_cn("Quests") if cn else "Quests",
            font=FONT_HEADING, bg="#f5f0e8"
        )
        quest_frame.pack(fill="both", expand=True)
        self._quest_text = tk.Text(quest_frame, font=FONT_SMALL, bg="#f5f0e8", fg="#333",
                                    wrap="word", bd=0, relief="flat", state="disabled", height=6)
        self._quest_text.pack(fill="both", expand=True, padx=5, pady=5)

        # ---- 旅途日记 (底部) ----
        diary_frame = tk.LabelFrame(
            right_col, text="旅途日记" if self._cn_mode else "Adventure Diary",
            font=FONT_HEADING, bg=self._t["panel_bg"], fg=self._t["fg"]
        )
        diary_frame.pack(fill="x", pady=(5, 0))
        diary_inner = tk.Frame(diary_frame, bg=self._t["panel_bg"])
        diary_inner.pack(fill="x", padx=8, pady=5)
        self._diary_labels = {}
        diary_items = [
            ("birthday", "始于: " if self._cn_mode else "Started: "),
            ("elapsed", "游历: " if self._cn_mode else "Elapsed: "),
            ("tasks", "里程: " if self._cn_mode else "Tasks: "),
            ("bestequip", "神装: " if self._cn_mode else "Best equip: "),
            ("bestspell", "巅峰: " if self._cn_mode else "Best spell: "),
            ("beststat", "属性: " if self._cn_mode else "Best stat: "),
        ]
        for key, prefix in diary_items:
            lbl = tk.Label(diary_inner, text=f"{prefix}—", font=FONT_SMALL,
                          bg=self._t["panel_bg"], fg=self._t["fg_secondary"], anchor="w")
            lbl.pack(fill="x")
            self._diary_labels[key] = {"label": lbl, "prefix": prefix}

        # 键盘绑定
        self._root.bind("<KeyPress-d>", lambda e: self._show_dna())
        self._root.bind("<KeyPress-D>", lambda e: self._show_dna())
        self._root.bind("<KeyPress-p>", lambda e: self._toggle_pause())
        self._root.bind("<KeyPress-P>", lambda e: self._toggle_pause())
        self._root.bind("<KeyPress-s>", lambda e: self._game.save_game())
        self._root.bind("<KeyPress-S>", lambda e: self._game.save_game())

        # 开始定时更新
        self._update_display()

    def _update_display(self):
        """每 100ms 刷新游戏界面"""
        c = self._game.character

        # 角色信息
        cn = self._cn_mode
        self._char_name_lbl.config(text=c.Name)
        race_label = f"{c.CharacterRace.name} {c.CharacterClass.name}"
        self._char_race_lbl.config(text=translate(race_label) if cn else race_label)
        self._char_level_lbl.config(
            text=f"{'等级' if cn else 'Level'} {c.Level}  ({'经验' if cn else 'XP'}: {c.Experience})")

        self._stat_display["STR"].config(text=str(c.STR))
        self._stat_display["CON"].config(text=str(c.CON))
        self._stat_display["DEX"].config(text=str(c.DEX))
        self._stat_display["INT"].config(text=str(c.INT))
        self._stat_display["WIS"].config(text=str(c.WIS))
        self._stat_display["CHA"].config(text=str(c.CHA))
        self._stat_display["HP"].config(text=f"{c.MAX_HP}")
        self._stat_display["MP"].config(text=f"{c.MAX_MP}")

        self._gold_lbl.config(text=f"{'金币' if cn else 'Gold'}: {c.Gold:,}")

        # 装备
        for i, name in enumerate(EQUIPMENT_LABELS):
            eq = c.Equipment[i] if i < len(c.Equipment) else ""
            self._equip_labels[name].config(text=eq if eq else "—")

        # 法术
        self._spells_text.config(state="normal")
        self._spells_text.delete("1.0", "end")
        for s in c.Spells:
            name = get_cn(s.name) if cn else s.name
            self._spells_text.insert("end", f"{name} x{s.count}\n")
        self._spells_text.config(state="disabled")

        # 背包
        self._inv_text.config(state="normal")
        self._inv_text.delete("1.0", "end")
        for item in c.Inventory:
            name = translate(item.name) if cn else item.name
            self._inv_text.insert("end", f"{name} x{item.count}\n")
        if not c.Inventory:
            self._inv_text.insert("end", "(空)" if cn else "(empty)")
        self._inv_text.config(state="disabled")

        # 行动
        action_text = translate_action_label(c.CurrentActionLabel) if cn else c.CurrentActionLabel
        self._action_lbl.config(text=action_text)

        # 进度条
        self._progress_canvas.delete("all")
        w = self._progress_canvas.winfo_width()
        if w < 10:
            w = 300
        if c.MaxProgress > 0:
            ratio = min(c.CurrentProgress / c.MaxProgress, 1.0)
            fill_w = int(w * ratio)
            self._progress_canvas.create_rectangle(0, 0, fill_w, 26, fill="#6b8e5a", outline="")
            self._progress_text.config(text=f"{c.CurrentProgress:,} / {c.MaxProgress:,} ({ratio*100:.1f}%)")
        else:
            self._progress_canvas.create_rectangle(0, 0, w, 26, fill="#6b8e5a", outline="")
            self._progress_text.config(text="")

        # 剧情
        self._plot_text.config(state="normal")
        self._plot_text.delete("1.0", "end")
        for p in c.Plot:
            self._plot_text.insert("end", f"{translate(p) if cn else p}\n")
        self._plot_text.insert("end",
            f"\n{'剧情进度' if cn else 'Plot Progress'}: {c.CurrentPlotProgress}")
        self._plot_text.config(state="disabled")

        # 任务
        self._quest_text.config(state="normal")
        self._quest_text.delete("1.0", "end")
        for q in c.Quests[-10:]:
            label = translate_quest_label(q.label) if cn else q.label
            self._quest_text.insert("end", f"{label}\n")
        if c.Quests:
            self._quest_text.insert("end",
                f"\n{'任务进度' if cn else 'Quest Progress'}: {c.CurrentQuestProgress} / {c.MaxQuestProgress}")
        self._quest_text.config(state="disabled")

        # 推进游戏
        if not self._paused:
            self._game.tick(self._speed_ms)
            self._total_seconds += self._speed_ms / 1000.0

        # 更新旅途日记
        self._update_diary()

        # 下一帧
        self._update_timer = self._root.after(self._speed_ms, self._update_display)

    # ========== 按钮回调 ==========

    def _toggle_language(self):
        self._cn_mode = not self._cn_mode
        self._settings["is_cn"] = self._cn_mode
        _save_settings(self._settings)
        # 重建游戏界面以应用语言切换
        if self._game.get_state() == GameState.Ready:
            self._show_game_screen()

    def _toggle_theme(self):
        themes = list(THEMES.keys())
        idx = themes.index(self._theme)
        self._theme = themes[(idx + 1) % len(themes)]
        self._settings["theme"] = self._theme
        _save_settings(self._settings)
        # 重建界面以应用主题
        if self._game.get_state() == GameState.Ready:
            self._show_game_screen()

    def _toggle_pause(self):
        self._paused = not self._paused

    def _on_save(self):
        """保存存档并给出提示"""
        result = self._game.save_game()
        cn = self._cn_mode
        if result == 0:  # SaveError.None_
            self._game.set_auto_save(True)  # A4：手动保存成功后恢复自动存盘
            messagebox.showinfo(
                "保存存档" if cn else "Save Game",
                "存档已保存。" if cn else "Game saved."
            )
        else:
            messagebox.showerror(
                "保存失败" if cn else "Save Error",
                "保存存档失败，请检查磁盘空间。" if cn else "Failed to save game. Check disk space."
            )

    def _on_save_error(self, err):
        """A4 契约：自动存盘失败回调。停止自动存盘并暂停，向用户给出可见告警，
        避免写失败被静默吞掉（postmortem Why3）。OutOfSpace 用专门文案。
        """
        self._game.set_auto_save(False)
        self._paused = True
        cn = self._cn_mode
        if err == SaveError.OutOfSpace:
            title = "磁盘空间不足" if cn else "Disk Full"
            msg = ("磁盘空间不足，已停止自动存档并暂停游戏。\n"
                   "请清理空间后点击“保存存档”手动保存。" if cn
                   else "Disk is full. Auto-save stopped and game paused.\n"
                        "Free space, then use Save to save manually.")
        else:
            title = "保存失败" if cn else "Save Error"
            msg = ("存档写入失败，已停止自动存档并暂停游戏。" if cn
                   else "Save failed. Auto-save stopped and game paused.")
        messagebox.showerror(title, msg)

    def _update_diary(self):
        c = self._game.character
        cn = self._cn_mode

        # 时间
        bday = self._birthday.strftime("%Y-%m-%d %H:%M:%S")
        hours = int(self._total_seconds // 3600)
        minutes = int((self._total_seconds % 3600) // 60)
        secs = int(self._total_seconds % 60)
        elapsed = f"{hours:02d}:{minutes:02d}:{secs:02d}"

        # 最佳装备/法术/属性
        best_equip = max(c.Equipment, key=len, default="—")
        best_spell = max((s.name for s in c.Spells), key=len, default="—")
        stats = [("STR", c.STR), ("CON", c.CON), ("DEX", c.DEX), ("INT", c.INT), ("WIS", c.WIS), ("CHA", c.CHA)]
        best_stat_name, best_stat_val = max(stats, key=lambda x: x[1])
        best_stat = f"{best_stat_name} {best_stat_val}"

        if cn:
            best_equip = translate(best_equip)
            best_spell = get_cn(best_spell)
            best_stat = f"{get_cn(best_stat_name)} {best_stat_val}"

        values = {
            "birthday": bday,
            "elapsed": elapsed,
            "tasks": str(len(c.Quests)),
            "bestequip": best_equip[:40],
            "bestspell": best_spell[:30],
            "beststat": best_stat,
        }

        for key, info in self._diary_labels.items():
            info["label"].config(text=f"{info['prefix']}{values.get(key, '—')}")

    def _show_dna(self):
        """显示角色基因组编码"""
        c = self._game.character
        seed_hash = abs(hash(f"{c.Name}{c.CharacterRace.name}{c.CharacterClass.name}"))
        dna_map = {0: 'A', 1: 'T', 2: 'C', 3: 'G'}
        dna = ""
        val = seed_hash
        for _ in range(64):
            dna += dna_map[val & 3]
            val >>= 2
        cn = self._cn_mode
        if cn:
            title = get_cn("DNA")
            msg = f"{c.Name}{get_cn('的基因序列:')}\n\n{dna}"
        else:
            title = "DNA"
            msg = f"Genetic Sequence of {c.Name}:\n\n{dna}"
        messagebox.showinfo(title, msg)

    def _on_new_game(self):
        new_game = self._game.start_new_game()
        self._show_character_creator(new_game)

    def _on_load_game(self):
        cn = self._cn_mode
        filepath = filedialog.askopenfilename(
            title=get_cn("Load Save Game") if cn else "Load Save Game",
            filetypes=[
                (get_cn("PQ2 Save Files") if cn else "PQ2 Save Files", "*.pq2"),
                (get_cn("All Files") if cn else "All Files", "*.*")
            ]
        )
        if filepath:
            from ..types import LoadError
            # A7 启动自愈：主档损坏时隔离为 .corrupt 并回退 .bak
            error, recovered = self._game.load_game_with_recovery(filepath)
            if error == LoadError.None_:
                if recovered:
                    messagebox.showinfo(
                        get_cn("Load Error") if cn else "Load Error",
                        "检测到存档损坏，已自动从备份恢复。"
                    )
                self._show_game_screen()
            else:
                title = get_cn("Load Error") if cn else "Load Error"
                msg_prefix = get_cn("Failed to load save file") if cn else "Failed to load save file"
                messagebox.showerror(title, f"{msg_prefix}: {error.name}")

    def _default_save_path(self) -> str:
        """默认存档路径（与 Game.save_game 的回退路径一致：game.py 同级 savefile.pq2）。"""
        import pq2.game as _game_mod
        return os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(_game_mod.__file__))),
            "savefile.pq2",
        )

    def _try_autoload_with_recovery(self):
        """A7 启动自愈：启动时优先继续默认存档；损坏则回退 .bak，避免「启动即崩溃」。"""
        from ..types import LoadError
        path = self._default_save_path()
        if not os.path.exists(path):
            return
        err, recovered = self._game.load_game_with_recovery(path)
        if err != LoadError.None_:
            # 主档与 .bak 均损坏/缺失：停留在主菜单并提示开新游戏，不崩溃
            cn = self._cn_mode
            title = get_cn("Load Error") if cn else "Load Error"
            msg_prefix = get_cn("Failed to load save file") if cn else "Failed to load save file"
            messagebox.showwarning(
                title,
                f"{msg_prefix}（{err.name}）\n可点击「新游戏」重新开始。",
            )
        elif recovered:
            cn = self._cn_mode
            messagebox.showinfo(
                get_cn("Load Error") if cn else "Load Error",
                "检测到存档损坏，已自动从备份恢复。",
            )

    def _report_localization_coverage(self):
        """A11 上报：启动时审计本地化缺键覆盖（呼应 A8 轻量遥测），缺失仅本地日志。"""
        from ..localization import audit_translation_coverage
        missing = audit_translation_coverage()
        if missing:
            print(f"[i18n] 本地化缺键 {len(missing)} 项（前 10）：{missing[:10]}")

    def _on_close(self):
        # #2：关闭窗口前停止自动投骰线程（创建界面未确认也可能在后台运行）
        ng = getattr(self, "_new_game", None)
        if ng is not None:
            ng.stop_auto_roll()
        if self._game.get_state() == GameState.Ready:
            self._game.save_game()
        self._game._game_state = GameState.Finished
        if self._update_timer:
            self._root.after_cancel(self._update_timer)
        if self._root:
            self._root.destroy()
