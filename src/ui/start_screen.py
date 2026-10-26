"""
Progress Quest Multiverse - 开始界面
主题选择 -> 随机角色生成 -> 进入游戏

原版PQ风格：纯随机角色，玩家只需选主题和确认。
"""

import tkinter as tk
from tkinter import font as tkfont
import random
import os
import sys

# 添加src目录到路径
src_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from core.themed_engine import ThemedGameEngine

# 复用主界面颜色方案
COLORS = {
    'bg': '#f0f0f0',
    'frame_bg': '#d4d0c8',
    'text': '#000000',
    'header_bg': '#e0e0e0',
    'accent': '#0078d7',
}

# 随机名字片段（通用奇幻风，不绑定特定主题）
_NAME_A = ['艾', '洛', '卡', '雷', '塞', '维', '芬', '德', '萨', '玛',
           '泰', '弗', '格', '布', '达', '希', '莫', '瓦', '瑟', '奥']
_NAME_B = ['伦', '斯', '德', '尔', '克', '恩', '拉', '顿', '里', '娜',
           '丝', '娅', '洛', '风', '刃', '影', '辉', '焰', '霜', '岩']


def generate_random_name():
    """生成随机角色名"""
    return random.choice(_NAME_A) + random.choice(_NAME_B)


class StartScreen:
    """开始界面：主题选择 + 随机角色生成

    流程：选主题 -> 自动随机角色 -> 可重新随机/编辑名字 -> 开始游戏
    回调 on_start(theme_name, char_name, race, char_class)
    """

    def __init__(self, root, on_start):
        self.root = root
        self.on_start = on_start
        self.selected_theme = None
        self.theme_obj = None  # 主题数据对象（轻量，非引擎）

        # 字体
        self.font_ui = tkfont.Font(family='Microsoft YaHei UI', size=9)
        self.font_bold = tkfont.Font(family='Microsoft YaHei UI', size=9, weight='bold')
        self.font_title = tkfont.Font(family='Microsoft YaHei UI', size=16, weight='bold')
        self.font_subtitle = tkfont.Font(family='Microsoft YaHei UI', size=10)
        self.font_small = tkfont.Font(family='Microsoft YaHei UI', size=8)

        self._build_ui()
        self._select_default_theme()

    def _build_ui(self):
        self.root.title("Progress Quest Multiverse")
        self.root.geometry("620x500")
        self.root.configure(bg=COLORS['bg'])
        self.root.resizable(False, False)

        # === 标题 ===
        title_frame = tk.Frame(self.root, bg=COLORS['bg'])
        title_frame.pack(fill=tk.X, padx=20, pady=(18, 8))

        tk.Label(title_frame, text="Progress Quest Multiverse",
                 font=self.font_title, bg=COLORS['bg'],
                 fg=COLORS['accent']).pack()
        tk.Label(title_frame, text="多元宇宙进度任务 -- 选择主题，开始你的挂机冒险",
                 font=self.font_subtitle, bg=COLORS['bg'],
                 fg='#555').pack()

        # === 主体两列 ===
        content = tk.Frame(self.root, bg=COLORS['bg'])
        content.pack(fill=tk.BOTH, expand=True, padx=20, pady=8)

        # --- 左列：主题列表 ---
        left = tk.Frame(content, bg=COLORS['bg'])
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8))

        lf_theme = tk.LabelFrame(left, text="选择主题",
                                 font=self.font_bold, bg=COLORS['frame_bg'],
                                 padx=5, pady=5)
        lf_theme.pack(fill=tk.BOTH, expand=True)

        self.theme_listbox = tk.Listbox(
            lf_theme, font=self.font_ui,
            bg='white', fg=COLORS['text'],
            selectmode=tk.SINGLE, height=8,
            activestyle='none', highlightthickness=1,
            highlightbackground='#999')
        self.theme_listbox.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        self.theme_listbox.bind('<<ListboxSelect>>', self._on_theme_select)

        # 填充主题
        self._theme_keys = ThemedGameEngine.list_themes()
        for key in self._theme_keys:
            self.theme_listbox.insert(tk.END, ThemedGameEngine.get_theme_display_name(key))

        # --- 右列：主题详情 + 角色 ---
        right = tk.Frame(content, bg=COLORS['bg'])
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # 主题详情
        lf_info = tk.LabelFrame(right, text="主题信息",
                                font=self.font_bold, bg=COLORS['frame_bg'],
                                padx=5, pady=5)
        lf_info.pack(fill=tk.X, pady=(0, 8))

        self.info_labels = {}
        for key, label_text in [('name', '名称'), ('description', '描述'),
                                 ('race_count', '种族数'), ('class_count', '职业数'),
                                 ('monster_count', '怪物种类'), ('quest_count', '任务模板')]:
            row = tk.Frame(lf_info, bg=COLORS['frame_bg'])
            row.pack(fill=tk.X)
            tk.Label(row, text=label_text, width=10, anchor='w',
                     font=self.font_ui, bg=COLORS['frame_bg']).pack(side=tk.LEFT)
            lbl = tk.Label(row, text="--", anchor='w', font=self.font_ui,
                           bg=COLORS['frame_bg'], fg=COLORS['text'])
            lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)
            self.info_labels[key] = lbl

        # 角色信息
        lf_char = tk.LabelFrame(right, text="你的角色",
                                font=self.font_bold, bg=COLORS['frame_bg'],
                                padx=5, pady=5)
        lf_char.pack(fill=tk.BOTH, expand=True)

        # 名称（可编辑）
        row_name = tk.Frame(lf_char, bg=COLORS['frame_bg'])
        row_name.pack(fill=tk.X, pady=(5, 3))
        tk.Label(row_name, text="名称", width=10, anchor='w',
                 font=self.font_ui, bg=COLORS['frame_bg']).pack(side=tk.LEFT)
        self.name_var = tk.StringVar()
        tk.Entry(row_name, textvariable=self.name_var,
                 font=self.font_ui, width=18).pack(side=tk.LEFT, padx=2)

        # 种族（只读）- 标签会根据主题动态更新
        row_race = tk.Frame(lf_char, bg=COLORS['frame_bg'])
        row_race.pack(fill=tk.X, pady=2)
        self.race_label_widget = tk.Label(row_race, text="种族", width=10, anchor='w',
                 font=self.font_ui, bg=COLORS['frame_bg'])
        self.race_label_widget.pack(side=tk.LEFT)
        self.race_label = tk.Label(row_race, text="--", anchor='w',
                                   font=self.font_ui, bg=COLORS['frame_bg'],
                                   fg=COLORS['accent'])
        self.race_label.pack(side=tk.LEFT)

        # 职业（只读）- 标签会根据主题动态更新
        row_cls = tk.Frame(lf_char, bg=COLORS['frame_bg'])
        row_cls.pack(fill=tk.X, pady=2)
        self.class_label_widget = tk.Label(row_cls, text="职业", width=10, anchor='w',
                    font=self.font_ui, bg=COLORS['frame_bg'])
        self.class_label_widget.pack(side=tk.LEFT)
        self.class_label = tk.Label(row_cls, text="--", anchor='w',
                                    font=self.font_ui, bg=COLORS['frame_bg'],
                                    fg=COLORS['accent'])
        self.class_label.pack(side=tk.LEFT)

        # 重新随机按钮
        row_btn = tk.Frame(lf_char, bg=COLORS['frame_bg'])
        row_btn.pack(fill=tk.X, pady=(10, 5))
        self.btn_reroll = tk.Button(row_btn, text="重新随机",
                                    font=self.font_ui, command=self._reroll_character)
        self.btn_reroll.pack(side=tk.LEFT)

        # === 底部按钮 ===
        bottom = tk.Frame(self.root, bg=COLORS['bg'])
        bottom.pack(fill=tk.X, padx=20, pady=(5, 18))

        self.btn_start = tk.Button(
            bottom, text="开始游戏",
            font=self.font_bold, command=self._start_game,
            bg='#228b22', fg='white', activebackground='#32cd32',
            width=15)
        self.btn_start.pack(side=tk.RIGHT)

        # 初始禁用
        self.btn_start.config(state=tk.DISABLED)
        self.btn_reroll.config(state=tk.DISABLED)

    def _select_default_theme(self):
        """默认选中第一个主题"""
        if self._theme_keys:
            self.theme_listbox.selection_set(0)
            self.theme_listbox.activate(0)
            self._on_theme_select(None)

    def _on_theme_select(self, event):
        """主题选择事件"""
        sel = self.theme_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        self.selected_theme = self._theme_keys[idx]

        # 轻量加载主题数据（不创建引擎）
        self.theme_obj = ThemedGameEngine.load_theme(self.selected_theme)
        if not self.theme_obj:
            return

        info = self.theme_obj.get_theme_info()
        for key, lbl in self.info_labels.items():
            val = info.get(key, '--')
            lbl.config(text=str(val))

        # 根据主题更新种族/职业标签
        labels = ThemedGameEngine.get_theme_labels(self.selected_theme)
        self.race_label_widget.config(text=labels.get('race_label', '种族'))
        self.class_label_widget.config(text=labels.get('class_label', '职业'))

        # 启用按钮
        self.btn_reroll.config(state=tk.NORMAL)
        self.btn_start.config(state=tk.NORMAL)

        # 自动随机角色
        self._reroll_character()

    def _reroll_character(self):
        """重新随机生成角色（名称 + 种族 + 职业）"""
        if not self.theme_obj:
            return
        races = self.theme_obj.races
        classes = self.theme_obj.classes
        self.name_var.set(generate_random_name())
        self.race_label.config(text=random.choice(races) if races else "--")
        self.class_label.config(text=random.choice(classes) if classes else "--")

    def _start_game(self):
        """确认开始游戏，回调主程序"""
        if not self.selected_theme:
            return
        name = self.name_var.get().strip()
        if not name:
            name = generate_random_name()
        race = self.race_label.cget('text')
        char_class = self.class_label.cget('text')
        if race == '--' or char_class == '--':
            return
        self.on_start(self.selected_theme, name, race, char_class)
