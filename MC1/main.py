# -*- coding: utf-8 -*-
"""
《我的世界》文字冒险 — 主程序入口
==================================
基于 allin_engine 构建，使用 PingFangJiangNanTi-2.ttf 字体的 Tkinter GUI。

启动方式:
    python main.py

需要:
    - Python 3.10+
    - tkinter（通常自带）
    - PingFangJiangNanTi-2.ttf（项目目录下）
    - D:\allin\tools\allin_engine（引擎）
"""

from __future__ import annotations

import os
import sys
import tkinter as tk
from pathlib import Path
from tkinter import font, scrolledtext, ttk

# 添加引擎路径（引擎统一位于 D:/allin/MCclone/allin_engine）
# minecraft_adventure 内部已把 MC1 的父目录（MCclone）注入 sys.path，
# 这里也做一层兜底，保证 allin_engine 可被导入。
_ENGINE_PARENT = str(Path(__file__).resolve().parent.parent)
if _ENGINE_PARENT not in sys.path:
    sys.path.insert(0, _ENGINE_PARENT)

from minecraft_adventure import MinecraftAdventure, GamePhase


# ═══════════════════════════════════════════════════════════
#  颜色主题（MC 风格）
# ═══════════════════════════════════════════════════════════

class MCTheme:
    """Minecraft 风格配色。"""
    BG_DARK     = "#1a1a1a"
    BG_PANEL    = "#2d2d2d"
    BG_INPUT    = "#3a3a3a"
    FG_PRIMARY  = "#e0e0e0"
    FG_ACCENT   = "#7ec850"   # 绿色（经验条色）
    FG_GOLD     = "#ffaa00"   # 金色
    FG_RED      = "#ff5555"   # 红色（血量）
    FG_BLUE     = "#55aaff"   # 蓝色
    FG_DIM      = "#888888"   # 暗灰
    FG_PURPLE   = "#aa55ff"   # 紫色（末地）
    BORDER      = "#444444"
    SELECT_BG   = "#3a3a3a"


# ═══════════════════════════════════════════════════════════
#  GUI 应用
# ═══════════════════════════════════════════════════════════

class MinecraftTextAdventureApp:
    """主 GUI 窗口。"""

    TITLE = "我的世界 · 文字冒险"
    FONT_FAMILY = "PingFangJiangNan"
    FONT_SIZE = 13
    FONT_SIZE_TITLE = 18
    FONT_SIZE_SMALL = 11
    MAX_HISTORY = 500

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(self.TITLE)
        self.root.geometry("900x680")
        self.root.minsize(700, 500)
        self.root.configure(bg=MCTheme.BG_DARK)

        # 加载字体
        self._load_font()

        # 游戏引擎
        self.game = MinecraftAdventure(log_callback=self._game_log)

        # 构建界面
        self._build_ui()

        # 显示欢迎信息
        self._show_welcome()

        # 绑定事件
        self.root.bind("<Return>", self._on_enter)
        self.root.bind("<Up>", self._on_history_up)
        self.root.bind("<Down>", self._on_history_down)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # 命令历史
        self._cmd_history: list[str] = []
        self._history_idx: int = -1

    def _load_font(self):
        """加载 PingFangJiangNanTi-2.ttf 字体。"""
        font_path = Path(__file__).parent / "PingFangJiangNanTi-2.ttf"
        if font_path.exists():
            try:
                # 使用 tkinter 加载外部字体（Windows 需要特殊处理）
                if sys.platform == "win32":
                    import ctypes
                    FR_PRIVATE = 0x10
                    ctypes.windll.gdi32.AddFontResourceExW(
                        str(font_path), FR_PRIVATE, 0
                    )
                self.FONT_FAMILY = "PingFangJiangNanTi-2"
            except Exception:
                pass  # 回退到系统默认字体

        self.font_main = font.Font(family=self.FONT_FAMILY, size=self.FONT_SIZE)
        self.font_title = font.Font(family=self.FONT_FAMILY, size=self.FONT_SIZE_TITLE, weight="bold")
        self.font_small = font.Font(family=self.FONT_FAMILY, size=self.FONT_SIZE_SMALL)

    def _build_ui(self):
        """构建界面布局。"""
        # ── 顶部标题栏 ──
        self._build_title_bar()

        # ── 主内容区 ──
        main_frame = tk.Frame(self.root, bg=MCTheme.BG_DARK)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 5))

        # 左侧日志区 (70%)
        left_frame = tk.Frame(main_frame, bg=MCTheme.BG_DARK)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.log_area = scrolledtext.ScrolledText(
            left_frame,
            wrap=tk.WORD,
            bg=MCTheme.BG_PANEL,
            fg=MCTheme.FG_PRIMARY,
            insertbackground=MCTheme.FG_PRIMARY,
            font=self.font_main,
            relief=tk.FLAT,
            borderwidth=0,
            padx=12,
            pady=10,
            state=tk.DISABLED,
        )
        self.log_area.pack(fill=tk.BOTH, expand=True)

        # 自定义滚动条样式
        self.log_area.configure(
            selectbackground=MCTheme.SELECT_BG,
            selectforeground=MCTheme.FG_PRIMARY,
        )

        # 右侧状态面板 (30%)
        right_frame = tk.Frame(main_frame, bg=MCTheme.BG_DARK, width=240)
        right_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(8, 0))
        right_frame.pack_propagate(False)

        self._build_status_panel(right_frame)

        # ── 底部输入区 ──
        self._build_input_bar()

        # ── 快捷命令栏 ──
        self._build_quick_bar()

    def _build_title_bar(self):
        """顶部标题栏。"""
        title_frame = tk.Frame(self.root, bg=MCTheme.BG_PANEL, height=45)
        title_frame.pack(fill=tk.X)
        title_frame.pack_propagate(False)

        tk.Label(
            title_frame,
            text="⛏️ 我的世界 · 文字冒险",
            font=self.font_title,
            bg=MCTheme.BG_PANEL,
            fg=MCTheme.FG_ACCENT,
        ).pack(side=tk.LEFT, padx=15, pady=8)

        self.title_info_label = tk.Label(
            title_frame,
            text="",
            font=self.font_small,
            bg=MCTheme.BG_PANEL,
            fg=MCTheme.FG_DIM,
        )
        self.title_info_label.pack(side=tk.RIGHT, padx=15, pady=8)

    def _build_status_panel(self, parent):
        """右侧状态面板。"""
        # 玩家状态
        status_frame = tk.LabelFrame(
            parent, text=" 玩家状态 ", font=self.font_small,
            bg=MCTheme.BG_PANEL, fg=MCTheme.FG_GOLD,
            relief=tk.FLAT, bd=1,
        )
        status_frame.pack(fill=tk.X, pady=(0, 10))

        self.hp_label = tk.Label(status_frame, text="", font=self.font_main,
                                bg=MCTheme.BG_PANEL, fg=MCTheme.FG_RED, anchor="w")
        self.hp_label.pack(fill=tk.X, padx=10, pady=(5, 0))

        self.hunger_label = tk.Label(status_frame, text="", font=self.font_main,
                                     bg=MCTheme.BG_PANEL, fg=MCTheme.FG_ACCENT, anchor="w")
        self.hunger_label.pack(fill=tk.X, padx=10, pady=(2, 0))

        self.armor_label = tk.Label(status_frame, text="", font=self.font_small,
                                    bg=MCTheme.BG_PANEL, fg=MCTheme.FG_PRIMARY, anchor="w")
        self.armor_label.pack(fill=tk.X, padx=10, pady=(2, 5))

        # 位置信息
        loc_frame = tk.LabelFrame(
            parent, text=" 位置 ", font=self.font_small,
            bg=MCTheme.BG_PANEL, fg=MCTheme.FG_BLUE,
            relief=tk.FLAT, bd=1,
        )
        loc_frame.pack(fill=tk.X, pady=(0, 10))

        self.biome_label = tk.Label(loc_frame, text="", font=self.font_main,
                                    bg=MCTheme.BG_PANEL, fg=MCTheme.FG_PRIMARY, anchor="w")
        self.biome_label.pack(fill=tk.X, padx=10, pady=(5, 2))

        self.dimension_label = tk.Label(loc_frame, text="", font=self.font_small,
                                        bg=MCTheme.BG_PANEL, fg=MCTheme.FG_PURPLE, anchor="w")
        self.dimension_label.pack(fill=tk.X, padx=10, pady=(2, 0))

        self.time_label = tk.Label(loc_frame, text="", font=self.font_small,
                                   bg=MCTheme.BG_PANEL, fg=MCTheme.FG_DIM, anchor="w")
        self.time_label.pack(fill=tk.X, padx=10, pady=(2, 5))

        # 装备信息
        equip_frame = tk.LabelFrame(
            parent, text=" 装备 ", font=self.font_small,
            bg=MCTheme.BG_PANEL, fg=MCTheme.FG_GOLD,
            relief=tk.FLAT, bd=1,
        )
        equip_frame.pack(fill=tk.X, pady=(0, 10))

        self.weapon_label = tk.Label(equip_frame, text="", font=self.font_small,
                                     bg=MCTheme.BG_PANEL, fg=MCTheme.FG_PRIMARY, anchor="w")
        self.weapon_label.pack(fill=tk.X, padx=10, pady=(5, 2))

        self.tool_label = tk.Label(equip_frame, text="", font=self.font_small,
                                    bg=MCTheme.BG_PANEL, fg=MCTheme.FG_PRIMARY, anchor="w")
        self.tool_label.pack(fill=tk.X, padx=10, pady=(2, 5))

        # 快捷提示
        help_frame = tk.LabelFrame(
            parent, text=" 快速上手 ", font=self.font_small,
            bg=MCTheme.BG_PANEL, fg=MCTheme.FG_DIM,
            relief=tk.FLAT, bd=1,
        )
        help_frame.pack(fill=tk.BOTH, expand=True)

        help_text = (
            "1. 输入 采集 获取资源\n"
            "2. 输入 合成列表 查看配方\n"
            "3. 输入 合成 木镐 做工具\n"
            "4. 输入 装备 木镐 装备\n"
            "5. 输入 北/南/西/东 探索\n"
            "6. 夜晚小心怪物！\n"
            "输入 help 查看全部命令"
        )
        tk.Label(help_frame, text=help_text, font=self.font_small,
                bg=MCTheme.BG_PANEL, fg=MCTheme.FG_DIM,
                anchor="w", justify=tk.LEFT).pack(
            fill=tk.BOTH, padx=10, pady=8)

    def _build_input_bar(self):
        """底部输入栏。"""
        input_frame = tk.Frame(self.root, bg=MCTheme.BG_PANEL, height=50)
        input_frame.pack(fill=tk.X, padx=10, pady=(0, 5))
        input_frame.pack_propagate(False)

        tk.Label(input_frame, text="> ", font=self.font_main,
                bg=MCTheme.BG_PANEL, fg=MCTheme.FG_ACCENT).pack(side=tk.LEFT, padx=(10, 0))

        self.cmd_entry = tk.Entry(
            input_frame,
            font=self.font_main,
            bg=MCTheme.BG_INPUT,
            fg=MCTheme.FG_PRIMARY,
            insertbackground=MCTheme.FG_ACCENT,
            relief=tk.FLAT,
            borderwidth=0,
        )
        self.cmd_entry.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5, 10), pady=10)
        self.cmd_entry.focus_set()

    def _build_quick_bar(self):
        """快捷命令按钮栏。"""
        quick_frame = tk.Frame(self.root, bg=MCTheme.BG_DARK)
        quick_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        buttons = [
            ("⛏️ 采集", "采集"),
            ("🎒 背包", "背包"),
            ("🔨 合成", "合成"),
            ("🍖 吃", "吃"),
            ("📊 状态", "状态"),
            ("👀 观察", "观察"),
            ("💾 存档", "存档"),
            ("📂 读档", "读档"),
            ("📋 帮助", "help"),
        ]

        for text, cmd in buttons:
            btn = tk.Button(
                quick_frame, text=text, font=self.font_small,
                bg=MCTheme.BG_PANEL, fg=MCTheme.FG_PRIMARY,
                activebackground=MCTheme.BG_INPUT,
                activeforeground=MCTheme.FG_ACCENT,
                relief=tk.FLAT, bd=1,
                padx=8, pady=3,
                command=lambda c=cmd: self._quick_cmd(c),
            )
            btn.pack(side=tk.LEFT, padx=2)

    # ── 事件处理 ──

    def _on_enter(self, event=None):
        """回车提交命令。"""
        cmd = self.cmd_entry.get().strip()
        if not cmd:
            return

        self._cmd_history.append(cmd)
        self._history_idx = len(self._cmd_history)
        self.cmd_entry.delete(0, tk.END)

        self._append_log(f"> {cmd}", MCTheme.FG_ACCENT)

        # 待处理交互
        if self.game._pending_mob:
            result = self.game.handle_pending_mob(cmd)
            if result:
                self._append_log(result)
                self._refresh_status()
                return

        # 执行命令
        result = self.game.execute(cmd)
        if result:
            self._append_log(result)

        self._refresh_status()

        # 游戏结束
        if self.game.phase == GamePhase.VICTORY:
            self._append_log("\n🏆 恭喜通关！感谢游玩《我的世界》文字冒险。", MCTheme.FG_GOLD)
        elif self.game.phase == GamePhase.GAMEOVER:
            self._append_log("\n💀 游戏结束。输入 '读档' 继续，或重启游戏。", MCTheme.FG_RED)

    def _on_history_up(self, event=None):
        """上箭头：上一个命令。"""
        if self._history_idx > 0:
            self._history_idx -= 1
            self.cmd_entry.delete(0, tk.END)
            self.cmd_entry.insert(0, self._cmd_history[self._history_idx])

    def _on_history_down(self, event=None):
        """下箭头：下一个命令。"""
        if self._history_idx < len(self._cmd_history) - 1:
            self._history_idx += 1
            self.cmd_entry.delete(0, tk.END)
            self.cmd_entry.insert(0, self._cmd_history[self._history_idx])
        else:
            self._history_idx = len(self._cmd_history)
            self.cmd_entry.delete(0, tk.END)

    def _on_close(self):
        """关闭窗口。"""
        self.root.destroy()

    def _quick_cmd(self, cmd: str):
        """快捷按钮执行命令。"""
        if self.game._pending_mob:
            result = self.game.handle_pending_mob(cmd)
            if result:
                self._append_log(f"> {cmd}", MCTheme.FG_ACCENT)
                self._append_log(result)
                self._refresh_status()
                return

        self._append_log(f"> {cmd}", MCTheme.FG_ACCENT)
        result = self.game.execute(cmd)
        if result:
            self._append_log(result)
        self._refresh_status()

    # ── 日志/显示 ──

    def _game_log(self, msg: str):
        """回调：游戏内部日志。"""
        self._append_log(msg)

    def _append_log(self, text: str, color: str | None = None):
        """追加日志到显示区。"""
        self.log_area.configure(state=tk.NORMAL)

        if color:
            self.log_area.tag_add("colored", "end-2l", "end-1c")
            self.log_area.tag_config("colored", foreground=color)
            self.log_area.insert(tk.END, text + "\n", "colored")
        else:
            self.log_area.insert(tk.END, text + "\n")

        # 自动滚动
        self.log_area.see(tk.END)

        # 限制历史行数
        lines = int(self.log_area.index('end-1c').split('.')[0])
        if lines > self.MAX_HISTORY:
            self.log_area.delete('1.0', f'{lines - self.MAX_HISTORY}.0')

        self.log_area.configure(state=tk.DISABLED)

    def _refresh_status(self):
        """刷新右侧状态面板。"""
        p = self.game.player
        weapon_name = "徒手"
        if p.weapon:
            from game_data import ITEMS
            weapon_name = ITEMS.get(p.weapon, {}).get("name", p.weapon)
        tool_name = "无"
        if p.tool:
            from game_data import ITEMS
            tool_name = ITEMS.get(p.tool, {}).get("name", p.tool)

        self.hp_label.config(text=f"❤️ 生命: {p.hp}/{p.max_hp}")
        self.hunger_label.config(text=f"🍖 饥饿: {p.hunger}/{p.max_hunger}")
        self.armor_label.config(text=f"🛡️ 护甲: {p.armor}  |  ⭐ 经验: {p.xp}")

        self.biome_label.config(
            text=f"{self.game.current_biome_icon} {self.game.current_biome_name}"
        )
        self.dimension_label.config(text=f"🌍 {p.dimension.value}")
        self.time_label.config(text=f"🌓 第{p.day}天 · {self.game.time.phase.value}")

        self.weapon_label.config(text=f"⚔️ 武器: {weapon_name}")
        self.tool_label.config(text=f"⛏️ 工具: {tool_name}")

        # 标题栏信息
        phase_str = p.dimension.value
        if self.game.phase == GamePhase.COMBAT:
            phase_str = "⚔️ 战斗中"
        self.title_info_label.config(text=f"{phase_str} · 第{p.day}天")

    def _show_welcome(self):
        """显示欢迎信息。"""
        welcome = """
╔══════════════════════════════════════════════════════╗
║        ⛏️  我的世界 · 文字冒险  ⛏️                ║
║          Minecraft Text Adventure                  ║
╚══════════════════════════════════════════════════════╝

🌿 你在一望无际的平原上醒来。
    环顾四周，这里只有几棵树和一些动物。

💡 新手引导:
    1. 输入 '采集' 获取木材
    2. 输入 '合成列表' 查看可合成物品
    3. 输入 '合成 木板' 来制作木板
    4. 输入 '观察' 查看周围环境
    5. 输入 'help' 查看所有命令

⚔️ 你的目标: 探索世界 → 制作钻石装备 → 进入下界
              → 激活末地传送门 → 击败末影龙！

🌙 注意: 夜晚会有怪物出没！建造庇护所来保护自己。
"""
        self._append_log(welcome, MCTheme.FG_ACCENT)
        self._refresh_status()


# ═══════════════════════════════════════════════════════════
#  入口
# ═══════════════════════════════════════════════════════════

def main():
    root = tk.Tk()
    app = MinecraftTextAdventureApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
