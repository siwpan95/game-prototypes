"""
ui_tkinter.py - 十二试炼：神话重构  Tkinter 图形界面
"""
import tkinter as tk
from tkinter import ttk, font as tkfont
import json
import os
import sys
import random
from typing import Optional, List, Dict

# ─────────────────────────── 颜色主题 ──────────────────────────────
THEME = {
    'bg':          '#0d0d14',   # 深色背景
    'panel':       '#16161f',   # 面板背景
    'border':      '#2a2a3a',   # 边框
    'text':        '#e8e0cc',   # 主文字（羊皮纸色）
    'text_dim':    '#8a7f6a',   # 次要文字
    'accent':      '#c8a96e',   # 金色强调
    'accent2':     '#8b5cf6',   # 紫色（神性）
    'success':     '#4ade80',   # 成功绿
    'fail':        '#f87171',   # 失败红
    'crit_s':      '#fde047',   # 大成功金
    'crit_f':      '#ef4444',   # 大失败深红
    'btn_normal':  '#1e2030',   # 按钮背景
    'btn_hover':   '#2a2d40',   # 按钮悬停
    'btn_border':  '#3d3f5c',   # 按钮边框
    'bar_life':    '#22c55e',   # 生命条
    'bar_madness': '#a855f7',   # 疯狂条
    'bar_glory':   '#f59e0b',   # 荣耀条
    'bar_power':   '#ef4444',   # 力量条
    'bar_wisdom':  '#3b82f6',   # 智慧条
    'bar_grace':   '#d946ef',   # 神恩条
}

STAT_COLORS = {
    '荣耀': THEME['bar_glory'],
    '力量': THEME['bar_power'],
    '智慧': THEME['bar_wisdom'],
    '神恩': THEME['bar_grace'],
    '疯狂': THEME['bar_madness'],
    '生命': THEME['bar_life'],
}

CHAR_DESC = {
    'heracles': {
        'title': '赫拉克勒斯',
        'sub': '半神 · 为赎罪而战',
        'lore': (
            '宙斯之子，因赫拉的诅咒失去理智，在狂怒中杀害了自己的家人。'
            '为了赎罪，他踏上了十二试炼之路。'
            '他的力量举世无双，但内心的疯狂从未消散。'
        ),
        'stats_hint': '高力量 · 中等神恩 · 起始遗物：涅墨亚狮皮',
        'color': '#c8a96e',
    },
    'beowulf': {
        'title': '贝奥武夫',
        'sub': '北欧之王 · 荣耀即吾命',
        'lore': (
            '盖特人的英雄，一生以荣耀为名。'
            '斩杀格伦德尔、战胜水下魔怪，最终以老迈之躯独战巨龙。'
            '北境的诗人将为他吟唱，直到最后一颗星星熄灭。'
        ),
        'stats_hint': '高荣耀 · 被动：荣耀≥10时每回合自增 · 起始遗物：命运甲胄',
        'color': '#60a5fa',
    },
    'kratos': {
        'title': '奎托斯',
        'sub': '斯巴达幽灵 · 弑神者',
        'lore': (
            '曾是斯巴达将军，被阿瑞斯欺骗，亲手杀死了挚爱的家人。'
            '他的皮肤被家人的灰烬染成灰白，那是永远无法洗去的印记。'
            '他的目标只有一个：杀死每一位奥林匹斯神明。'
        ),
        'stats_hint': '极高力量·高疯狂·神恩为0·被动：疯狂增加时力量提升 · 起始遗物：混沌之刃',
        'color': '#f87171',
    },
}


def _data_path(rel: str) -> str:
    if getattr(sys, 'frozen', False):
        base = sys._MEIPASS  # type: ignore
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # src/ 的上级=项目根
    return os.path.join(base, rel)


def _save_path(rel: str) -> str:
    if getattr(sys, 'frozen', False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # src/ 的上级=项目根
    return os.path.join(base, rel)


# ─────────────────────────── 主 UI 类 ──────────────────────────────
class TkinterUI:
    """Tkinter 图形界面，调用 run(engine) 启动游戏主循环。"""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("十二试炼：神话重构")
        self.root.configure(bg=THEME['bg'])
        self.root.resizable(True, True)
        # 居中显示
        w, h = 1100, 760
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.root.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")
        self.root.minsize(900, 600)

        self._setup_fonts()
        self._engine = None
        self._endings: List[Dict] = []
        self._restart = False  # 结算后是否再次挑战

    def _setup_fonts(self):
        """加载字体，优先使用系统中文字体"""
        cjk_candidates = [
            'Microsoft YaHei', 'Microsoft YaHei UI',
            'SimHei', 'SimSun', 'NSimSun',
            'PingFang SC', 'Hiragino Sans GB', 'WenQuanYi Micro Hei',
            'Noto Sans CJK SC', 'Noto Sans SC',
        ]
        available = list(tkfont.families())
        cjk_font = next((f for f in cjk_candidates if f in available), None)
        if cjk_font is None:
            cjk_font = 'TkDefaultFont'

        self.font_title  = tkfont.Font(family=cjk_font, size=22, weight='bold')
        self.font_sub    = tkfont.Font(family=cjk_font, size=13)
        self.font_body   = tkfont.Font(family=cjk_font, size=12)
        self.font_small  = tkfont.Font(family=cjk_font, size=10)
        self.font_btn    = tkfont.Font(family=cjk_font, size=11, weight='bold')
        self.font_stat   = tkfont.Font(family=cjk_font, size=11)
        self.font_lore   = tkfont.Font(family=cjk_font, size=11)
        self.font_mono   = tkfont.Font(family=cjk_font, size=11)

    # ─────────── run 入口 ───────────
    def run(self, engine) -> List[Dict]:
        self._engine = engine
        self._show_game_screen()
        self.root.mainloop()
        return self._endings

    # ─────────── 标题/角色选择界面（静态调用） ───────────
    @staticmethod
    def launch_title(unlock_mgr, char_data: dict) -> Optional[tuple]:
        """
        显示标题 + 角色选择 + 模式选择窗口。
        返回 (character_id, labour_combo) 或 None（关闭窗口）。
        """
        result = [None]

        root = tk.Tk()
        root.title("十二试炼：神话重构")
        root.configure(bg=THEME['bg'])
        w, h = 960, 680
        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
        # 自适应屏幕高度（留出任务栏余量），小屏幕自动缩小
        h = min(h, sh - 60)
        w = min(w, sw - 40)
        root.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")
        root.resizable(True, True)
        root.minsize(500, 400)

        # ── 字体 ──
        cjk_candidates = [
            'Microsoft YaHei', 'Microsoft YaHei UI', 'SimHei', 'SimSun',
            'PingFang SC', 'Hiragino Sans GB', 'Noto Sans CJK SC',
        ]
        available = list(tkfont.families())
        cjk_font = next((f for f in cjk_candidates if f in available), 'TkDefaultFont')

        f_title  = tkfont.Font(family=cjk_font, size=26, weight='bold')
        f_sub    = tkfont.Font(family=cjk_font, size=12)
        f_char   = tkfont.Font(family=cjk_font, size=14, weight='bold')
        f_lore   = tkfont.Font(family=cjk_font, size=11)
        f_btn    = tkfont.Font(family=cjk_font, size=12, weight='bold')
        f_label  = tkfont.Font(family=cjk_font, size=11)

        # ── 标题区 ──
        header = tk.Frame(root, bg=THEME['bg'])
        header.pack(fill='x', padx=30, pady=(28, 0))
        tk.Label(header, text="十 二 试 炼", font=f_title,
                 fg=THEME['accent'], bg=THEME['bg']).pack()
        tk.Label(header, text="十二试炼 · 神话重构",
                 font=f_sub, fg=THEME['text_dim'], bg=THEME['bg']).pack()

        sep = tk.Frame(root, height=1, bg=THEME['border'])
        sep.pack(fill='x', padx=30, pady=12)

        # ── 角色选择 ──
        available_chars = unlock_mgr.get_available_characters()
        selected_char = tk.StringVar(value=available_chars[0])
        selected_combo = tk.StringVar(value='random')

        char_frame = tk.Frame(root, bg=THEME['bg'])
        char_frame.pack(fill='x', padx=30)
        tk.Label(char_frame, text="选择英雄", font=f_btn,
                 fg=THEME['accent'], bg=THEME['bg']).pack(anchor='w')

        cards_frame = tk.Frame(char_frame, bg=THEME['bg'])
        cards_frame.pack(fill='x', pady=8)

        # 角色卡片（互斥单选）
        char_card_refs = {}

        def select_char(cid):
            selected_char.set(cid)
            for c, widgets in char_card_refs.items():
                is_sel = (c == cid)
                border_color = CHAR_DESC.get(c, {}).get('color', THEME['accent']) if is_sel else THEME['border']
                widgets['frame'].config(highlightbackground=border_color,
                                        highlightthickness=2 if is_sel else 1)
                widgets['title'].config(fg=CHAR_DESC.get(c, {}).get('color', THEME['text']))

        for cid in available_chars:
            info = CHAR_DESC.get(cid, {'title': cid, 'sub': '', 'lore': '', 'stats_hint': '', 'color': THEME['text']})
            frame = tk.Frame(cards_frame, bg=THEME['panel'],
                             highlightbackground=THEME['border'],
                             highlightthickness=1, cursor='hand2')
            frame.pack(side='left', padx=6, pady=4, fill='both', expand=True)

            title_lbl = tk.Label(frame, text=info['title'], font=f_char,
                                 fg=info['color'], bg=THEME['panel'])
            title_lbl.pack(anchor='w', padx=10, pady=(10, 2))
            tk.Label(frame, text=info['sub'], font=f_lore,
                     fg=THEME['text_dim'], bg=THEME['panel']).pack(anchor='w', padx=10)
            tk.Label(frame, text=info['lore'], font=f_lore, fg=THEME['text'],
                     bg=THEME['panel'], wraplength=240, justify='left').pack(
                anchor='w', padx=10, pady=4)
            tk.Label(frame, text=info['stats_hint'], font=tkfont.Font(family=cjk_font, size=9),
                     fg=THEME['text_dim'], bg=THEME['panel'], wraplength=240,
                     justify='left').pack(anchor='w', padx=10, pady=(0, 10))

            char_card_refs[cid] = {'frame': frame, 'title': title_lbl}
            frame.bind('<Button-1>', lambda e, c=cid: select_char(c))
            for child in frame.winfo_children():
                child.bind('<Button-1>', lambda e, c=cid: select_char(c))

        # 解锁提示
        locked_chars = [c for c in ['beowulf', 'kratos'] if c not in available_chars]
        if locked_chars:
            lock_text = "  ".join([
                f"【{CHAR_DESC[c]['title']}】需触发特定结局解锁"
                for c in locked_chars
            ])
            tk.Label(char_frame, text=lock_text, font=f_lore,
                     fg=THEME['text_dim'], bg=THEME['bg']).pack(anchor='w', pady=(4, 0))

        select_char(available_chars[0])

        sep2 = tk.Frame(root, height=1, bg=THEME['border'])
        sep2.pack(fill='x', padx=30, pady=12)

        # ── 试炼模式 ──
        mode_frame = tk.Frame(root, bg=THEME['bg'])
        mode_frame.pack(fill='x', padx=30)
        tk.Label(mode_frame, text="选择试炼之路", font=f_btn,
                 fg=THEME['accent'], bg=THEME['bg']).pack(anchor='w')

        modes_base = [
            ("random",       "命运裁决（随机）",    "从所有试炼池中随机抽取三场"),
            ("balanced",     "均衡之路",           "每种类型各取一场（肉体·心智·神性）"),
            ("all_physical", "暴力之路",           "三场均为肉体试炼"),
            ("all_mental",   "智者之路",           "三场均为心智试炼"),
            ("all_divine",   "神眷之路",           "三场均为神性试炼"),
        ]
        if unlock_mgr.is_unlocked('chaos_mode'):
            modes_base.append(("chaos", "混沌之路",  "从所有池随机混合，包含隐藏试炼"))

        # 检查当前选中角色是否有专属路线
        def get_modes():
            cid = selected_char.get()
            modes = list(modes_base)
            if cid in ('beowulf', 'kratos'):
                info = CHAR_DESC.get(cid, {})
                modes.insert(0, ("lore", f"传承之路（{info.get('title', '')}专属）",
                                 "体验角色专属史诗剧情试炼"))
            return modes

        mode_radio_frame = tk.Frame(mode_frame, bg=THEME['bg'])
        mode_radio_frame.pack(fill='x', pady=4)
        mode_radios = []

        def refresh_modes():
            for w in mode_radio_frame.winfo_children():
                w.destroy()
            modes = get_modes()
            # 如果当前选择的模式不在列表里，重置
            valid_vals = [m[0] for m in modes]
            if selected_combo.get() not in valid_vals:
                selected_combo.set(modes[0][0])
            for val, label, desc in modes:
                row = tk.Frame(mode_radio_frame, bg=THEME['bg'])
                row.pack(anchor='w', pady=1)
                rb = tk.Radiobutton(row, variable=selected_combo, value=val,
                                    bg=THEME['bg'], fg=THEME['text'],
                                    selectcolor=THEME['panel'],
                                    activebackground=THEME['bg'],
                                    font=f_label)
                rb.pack(side='left')
                tk.Label(row, text=f"{label}  ", font=tkfont.Font(family=cjk_font, size=11, weight='bold'),
                         fg=THEME['accent'], bg=THEME['bg']).pack(side='left')
                tk.Label(row, text=desc, font=f_label,
                         fg=THEME['text_dim'], bg=THEME['bg']).pack(side='left')
                mode_radios.append(rb)

        # 绑定角色切换时刷新模式
        def on_char_selected(c):
            select_char(c)
            refresh_modes()
        for cid in available_chars:
            frame = char_card_refs[cid]['frame']
            frame.bind('<Button-1>', lambda e, c=cid: on_char_selected(c))
            for child in frame.winfo_children():
                child.bind('<Button-1>', lambda e, c=cid: on_char_selected(c))

        refresh_modes()

        # ── 挑战模式（解锁后显示）──
        challenge_var = tk.BooleanVar(value=False)
        if unlock_mgr.is_unlocked('challenge_mode'):
            ch_row = tk.Frame(mode_frame, bg=THEME['bg'])
            ch_row.pack(anchor='w', pady=4)
            tk.Checkbutton(ch_row, variable=challenge_var,
                           text="挑战模式（属性封顶10 · 禁用遗物 · 失败惩罚加重）",
                           bg=THEME['bg'], fg=THEME['accent2'],
                           selectcolor=THEME['panel'], activebackground=THEME['bg'],
                           font=f_label).pack(anchor='w')

        # ── 已解锁代币展示 ──
        ups = unlock_mgr.get_unlocked_upgrades()
        if ups:
            ups_text = "已获代币：" + "、".join(unlock_mgr.upgrade_name(u) for u in ups)
            tk.Label(mode_frame, text=ups_text, font=f_label,
                     fg=THEME['accent'], bg=THEME['bg']).pack(anchor='w', pady=2)

        # ── 开始按钮 ──
        sep3 = tk.Frame(root, height=1, bg=THEME['border'])
        sep3.pack(fill='x', padx=30, pady=12)

        btn_frame = tk.Frame(root, bg=THEME['bg'])
        btn_frame.pack(pady=8)

        def on_start():
            ch = None
            if challenge_var.get():
                ch = {'cap_strength': True, 'no_relics': True}
            result[0] = (selected_char.get(), selected_combo.get(), ch)
            root.destroy()

        def on_quit():
            root.destroy()

        start_btn = tk.Button(
            btn_frame, text="  踏上试炼之路  ",
            font=f_btn, fg=THEME['bg'], bg=THEME['accent'],
            relief='flat', padx=20, pady=10, cursor='hand2',
            command=on_start
        )
        start_btn.pack(side='left', padx=10)
        quit_btn = tk.Button(
            btn_frame, text="  退出  ",
            font=f_btn, fg=THEME['text_dim'], bg=THEME['panel'],
            relief='flat', padx=20, pady=10, cursor='hand2',
            command=on_quit
        )
        quit_btn.pack(side='left', padx=10)

        root.mainloop()
        return result[0]

    # ─────────── 游戏主界面 ───────────
    def _show_game_screen(self):
        """清除所有 widget，构建游戏主界面"""
        for w in self.root.winfo_children():
            w.destroy()

        engine = self._engine
        self._passive_msg = None  # 本回合角色被动提示

        # ── 顶部标题栏 ──
        topbar = tk.Frame(self.root, bg=THEME['panel'], height=44)
        topbar.pack(fill='x', side='top')
        topbar.pack_propagate(False)

        self._title_var = tk.StringVar(value="十二试炼 · 神话重构")
        tk.Label(topbar, textvariable=self._title_var, font=self.font_sub,
                 fg=THEME['accent'], bg=THEME['panel']).pack(side='left', padx=16)

        self._turn_var = tk.StringVar(value="回合 0")
        tk.Label(topbar, textvariable=self._turn_var, font=self.font_small,
                 fg=THEME['text_dim'], bg=THEME['panel']).pack(side='right', padx=16)

        self._labour_var = tk.StringVar(value="试炼 1/3")
        tk.Label(topbar, textvariable=self._labour_var, font=self.font_small,
                 fg=THEME['text_dim'], bg=THEME['panel']).pack(side='right', padx=8)

        # ── 主内容区 ──
        main = tk.Frame(self.root, bg=THEME['bg'])
        main.pack(fill='both', expand=True)

        # 左侧：属性面板
        left = tk.Frame(main, bg=THEME['panel'], width=220)
        left.pack(side='left', fill='y', padx=(6, 0), pady=6)
        left.pack_propagate(False)
        self._build_stat_panel(left)

        # 中部：事件文本 + 选项
        center = tk.Frame(main, bg=THEME['bg'])
        center.pack(side='left', fill='both', expand=True, padx=6, pady=6)
        self._build_center(center)

        # 右侧：遗物+日志
        right = tk.Frame(main, bg=THEME['panel'], width=220)
        right.pack(side='right', fill='y', padx=(0, 6), pady=6)
        right.pack_propagate(False)
        self._build_right_panel(right)

        # 初始刷新
        self._refresh_all()

    def _build_stat_panel(self, parent):
        """左侧属性面板"""
        tk.Label(parent, text="英雄属性", font=self.font_btn,
                 fg=THEME['accent'], bg=THEME['panel']).pack(pady=(12, 4))

        # 角色名
        self._char_name_var = tk.StringVar(value=self._engine.character_name)
        tk.Label(parent, textvariable=self._char_name_var, font=self.font_sub,
                 fg=THEME['text'], bg=THEME['panel']).pack()

        sep = tk.Frame(parent, height=1, bg=THEME['border'])
        sep.pack(fill='x', padx=10, pady=8)

        # 属性条
        self._stat_vars: Dict[str, tk.StringVar] = {}
        self._stat_bars: Dict[str, tk.Canvas] = {}

        self._stat_val_labels = {}
        self._prev_stats = {}
        stat_order = ['荣耀', '力量', '智慧', '神恩', '疯狂', '生命']
        for stat in stat_order:
            row = tk.Frame(parent, bg=THEME['panel'])
            row.pack(fill='x', padx=10, pady=3)

            label = tk.Label(row, text=f"{stat}", width=3, font=self.font_stat,
                             fg=STAT_COLORS.get(stat, THEME['text']), bg=THEME['panel'],
                             anchor='w')
            label.pack(side='left')

            # 进度条（Canvas 实现）
            bar_canvas = tk.Canvas(row, height=14, width=100,
                                   bg=THEME['border'], highlightthickness=0)
            bar_canvas.pack(side='left', padx=4)
            self._stat_bars[stat] = bar_canvas

            val_var = tk.StringVar(value="0")
            self._stat_vars[stat] = val_var
            val_lbl = tk.Label(row, textvariable=val_var, width=4, font=self.font_stat,
                               fg=THEME['text'], bg=THEME['panel'], anchor='e')
            val_lbl.pack(side='left')
            self._stat_val_labels[stat] = val_lbl

        sep2 = tk.Frame(parent, height=1, bg=THEME['border'])
        sep2.pack(fill='x', padx=10, pady=8)

        # 临界状态
        tk.Label(parent, text="临界状态", font=self.font_small,
                 fg=THEME['text_dim'], bg=THEME['panel']).pack(anchor='w', padx=10)
        self._threshold_frame = tk.Frame(parent, bg=THEME['panel'])
        self._threshold_frame.pack(fill='x', padx=10, pady=2)

        # 角色被动提示
        sep3 = tk.Frame(parent, height=1, bg=THEME['border'])
        sep3.pack(fill='x', padx=10, pady=6)
        self._passive_var = tk.StringVar(value="")
        tk.Label(parent, textvariable=self._passive_var, font=self.font_small,
                 fg=THEME['crit_s'], bg=THEME['panel'],
                 wraplength=195, justify='left').pack(padx=10, pady=2)

    def _build_center(self, parent):
        """中部事件文本 + 选项按钮区域"""
        # 事件标题
        self._event_title_var = tk.StringVar(value="")
        tk.Label(parent, textvariable=self._event_title_var,
                 font=self.font_title, fg=THEME['accent'], bg=THEME['bg'],
                 wraplength=600, justify='center').pack(pady=(8, 4))

        # 分隔
        tk.Frame(parent, height=1, bg=THEME['border']).pack(fill='x', padx=20, pady=2)

        # 事件文本（可滚动）
        txt_frame = tk.Frame(parent, bg=THEME['bg'])
        txt_frame.pack(fill='both', expand=True, padx=20, pady=4)

        self._event_text = tk.Text(
            txt_frame, font=self.font_lore, fg=THEME['text'], bg=THEME['bg'],
            relief='flat', wrap='word', state='disabled',
            height=10, selectbackground=THEME['border'],
            cursor='arrow', spacing1=3, spacing3=3,
        )
        scroll = tk.Scrollbar(txt_frame, command=self._event_text.yview,
                              bg=THEME['panel'], troughcolor=THEME['bg'])
        self._event_text.config(yscrollcommand=scroll.set)
        self._event_text.pack(side='left', fill='both', expand=True)
        scroll.pack(side='right', fill='y')

        # 检定结果提示
        self._roll_var = tk.StringVar(value="")
        self._roll_label = tk.Label(parent, textvariable=self._roll_var,
                                    font=self.font_sub, fg=THEME['crit_s'],
                                    bg=THEME['bg'])
        self._roll_label.pack(pady=2)

        # 选项按钮区
        tk.Frame(parent, height=1, bg=THEME['border']).pack(fill='x', padx=20)
        self._options_frame = tk.Frame(parent, bg=THEME['bg'])
        self._options_frame.pack(fill='x', padx=20, pady=8)

    def _build_right_panel(self, parent):
        """右侧遗物 + 战斗日志"""
        tk.Label(parent, text="持有遗物", font=self.font_btn,
                 fg=THEME['accent'], bg=THEME['panel']).pack(pady=(12, 4))

        self._relic_frame = tk.Frame(parent, bg=THEME['panel'])
        self._relic_frame.pack(fill='x', padx=8, pady=2)

        sep = tk.Frame(parent, height=1, bg=THEME['border'])
        sep.pack(fill='x', padx=8, pady=8)

        tk.Label(parent, text="战斗日志", font=self.font_btn,
                 fg=THEME['accent'], bg=THEME['panel']).pack()

        log_frame = tk.Frame(parent, bg=THEME['panel'])
        log_frame.pack(fill='both', expand=True, padx=8, pady=4)

        self._log_text = tk.Text(
            log_frame, font=self.font_small, fg=THEME['text_dim'],
            bg=THEME['panel'], relief='flat', wrap='word', state='disabled',
            height=20, cursor='arrow',
        )
        log_scroll = tk.Scrollbar(log_frame, command=self._log_text.yview,
                                  bg=THEME['panel'])
        self._log_text.config(yscrollcommand=log_scroll.set)
        self._log_text.pack(side='left', fill='both', expand=True)
        log_scroll.pack(side='right', fill='y')

    # ─────────── 刷新 UI ───────────
    def _refresh_all(self):
        engine = self._engine
        if engine is None:
            return

        # 角色被动
        passive_msg = engine.apply_character_passive()
        if passive_msg:
            self._passive_var.set(passive_msg)
            self._log(passive_msg, color=THEME['crit_s'])
        else:
            self._passive_var.set("")

        # 顶栏
        self._turn_var.set(f"回合 {engine.turn}")
        self._labour_var.set(
            f"试炼 {engine.current_labour_index + 1}/{engine.total_labours}"
        )

        # 属性条（含变化高亮）
        for stat, bar in self._stat_bars.items():
            val = engine.stats.get(stat, 0)
            old = self._prev_stats.get(stat, val)
            self._stat_vars[stat].set(str(val))
            # 数值变化高亮：增加闪绿、减少闪红，600ms 后恢复
            lbl = self._stat_val_labels.get(stat)
            if lbl is not None and val != old:
                lbl.config(fg=THEME['success'] if val > old else THEME['fail'])
                self.root.after(600, lambda l=lbl: l.config(fg=THEME['text']))
            self._prev_stats[stat] = val
            bar.delete('all')
            max_val = 20 if stat != '生命' else engine.stats.get('_max_life', 20)
            pct = max(0.0, min(1.0, val / max(1, max_val)))
            color = STAT_COLORS.get(stat, THEME['accent'])
            bar_w = 100
            filled_w = int(bar_w * pct)
            if filled_w > 0:
                bar.create_rectangle(0, 0, filled_w, 14, fill=color, outline='')

        # 临界状态
        for w in self._threshold_frame.winfo_children():
            w.destroy()
        for name in engine.get_stat_threshold_effects():
            color_map = {
                '战神': THEME['bar_power'], '先知': THEME['bar_wisdom'],
                '幻觉': THEME['bar_madness'], '湮灭': THEME['fail'],
                '半神容器': THEME['accent2'], '被遗弃': THEME['text_dim'],
            }
            fg = color_map.get(name, THEME['accent'])
            tk.Label(self._threshold_frame, text=f"◆ {name}",
                     font=self.font_small, fg=fg, bg=THEME['panel']).pack(anchor='w')

        # 遗物
        for w in self._relic_frame.winfo_children():
            w.destroy()
        rarity_colors = {
            'chapter_unique': THEME['accent'],
            'rare':           '#60a5fa',
            'epic':           THEME['accent2'],
            'legendary':      '#f59e0b',
            'divine':         '#d946ef',
            'cursed':         '#ef4444',
        }
        for relic in engine.relics:
            rarity = relic.get('rarity', 'rare')
            color = rarity_colors.get(rarity, THEME['text'])
            tk.Label(self._relic_frame, text=f"◆ {relic.get('name', '?')}",
                     font=self.font_small, fg=color, bg=THEME['panel'],
                     anchor='w').pack(anchor='w')

        # 当前事件
        self._refresh_event()

    def _refresh_event(self):
        engine = self._engine
        if engine is None:
            return

        # 检查死亡
        if not engine.is_alive():
            self._show_death_screen()
            return

        # 检查游戏结束
        if engine.state == "GAME_OVER":
            self._show_ending_screen()
            return

        event = engine.get_current_event()
        if event is None:
            if engine.state == "GAME_OVER":
                self._show_ending_screen()
            return

        # 更新事件标题
        self._title_var.set("十二试炼 · 神话重构")
        self._event_title_var.set(event.get('title', ''))

        # 更新事件文本
        self._set_text(self._event_text, event.get('text', ''))

        # 清空检定提示
        self._roll_var.set("")

        # 构建选项按钮
        self._build_option_buttons(event)

    def _build_option_buttons(self, event: dict):
        """动态创建选项按钮"""
        for w in self._options_frame.winfo_children():
            w.destroy()

        options = event.get('options', [])
        engine = self._engine
        for i, opt in enumerate(options):
            # 检查属性需求
            req = opt.get('required_stat', {})
            can_meet = all(engine.stats.get(s, 0) >= v for s, v in req.items())
            check_stat = opt.get('check_stat')
            difficulty = opt.get('difficulty')

            # 按钮文字
            label_text = opt.get('text', f'选项 {i+1}')
            hint_parts = []
            if req:
                for s, v in req.items():
                    if engine.unlock_mgr.is_unlocked('god_eye'):
                        cur = engine.stats.get(s, 0)
                        mark = "✓" if cur >= v else "✗"
                        hint_parts.append(f"需要 {s}≥{v}（当前{cur} {mark}）")
                    else:
                        hint_parts.append(f"需要 {s}≥{v}")
            if check_stat and difficulty:
                hint_parts.append(f"检定：{check_stat} DC{difficulty}")
            if hint_parts:
                label_text += f"\n  [{' · '.join(hint_parts)}]"

            fg_color = THEME['text'] if can_meet else THEME['text_dim']
            bg_color = THEME['btn_normal']
            border_color = THEME['btn_border']

            btn_frame = tk.Frame(self._options_frame,
                                 bg=border_color, padx=1, pady=1)
            btn_frame.pack(fill='x', pady=3)

            btn = tk.Button(
                btn_frame,
                text=label_text,
                font=self.font_btn,
                fg=fg_color, bg=bg_color,
                relief='flat', anchor='w',
                padx=12, pady=8,
                wraplength=540, justify='left',
                cursor='hand2' if can_meet else 'arrow',
                command=lambda idx=i, ev=event: self._on_option_click(ev, idx)
            )
            btn.pack(fill='x')

            # 悬停效果
            if can_meet:
                btn.bind('<Enter>', lambda e, b=btn: b.config(bg=THEME['btn_hover']))
                btn.bind('<Leave>', lambda e, b=btn: b.config(bg=THEME['btn_normal']))

    def _on_option_click(self, event: dict, option_index: int):
        engine = self._engine
        success, text, effects = engine.process_option(event, option_index)

        # 检定结果提示
        roll_result = engine.last_roll_result
        roll_val = engine.last_roll_value
        if roll_result == "CRIT_SUCCESS":
            self._roll_var.set(f"✦ 大成功！骰点 {roll_val}")
            self._roll_label.config(fg=THEME['crit_s'])
        elif roll_result == "CRIT_FAILURE":
            self._roll_var.set(f"✦ 大失败！骰点 {roll_val}")
            self._roll_label.config(fg=THEME['crit_f'])
        elif roll_result == "SUCCESS":
            self._roll_var.set(f"✦ 成功（骰点 {roll_val}）")
            self._roll_label.config(fg=THEME['success'])
        elif roll_result == "FAILURE":
            self._roll_var.set(f"✦ 失败（骰点 {roll_val}）")
            self._roll_label.config(fg=THEME['fail'])
        else:
            self._roll_var.set("")

        engine.last_roll_result = None

        # 效果日志
        color = THEME['success'] if success else THEME['fail']
        self._log(text, color=color)
        if effects:
            fx_parts = []
            for stat, val in effects.items():
                if stat.startswith('_'):
                    continue
                sign = '+' if val > 0 else ''
                fx_parts.append(f"{stat}{sign}{val}")
            if fx_parts:
                self._log("  " + " · ".join(fx_parts), color=THEME['text_dim'])

        self._refresh_all()

    # ─────────── 死亡界面 ───────────
    def _show_death_screen(self):
        engine = self._engine
        for w in self.root.winfo_children():
            w.destroy()

        frame = tk.Frame(self.root, bg=THEME['bg'])
        frame.pack(fill='both', expand=True)

        tk.Label(frame, text="†  英雄陨落  †", font=self.font_title,
                 fg=THEME['fail'], bg=THEME['bg']).pack(pady=(36, 8))
        tk.Label(frame, text=engine.get_death_reason(), font=self.font_sub,
                 fg=THEME['text'], bg=THEME['bg']).pack(pady=4)

        sep = tk.Frame(frame, height=1, bg=THEME['border'])
        sep.pack(fill='x', padx=80, pady=14)

        # 完整试炼报告（可滚动）
        self._show_report_panel(frame, engine)

        btn_frame = tk.Frame(frame, bg=THEME['bg'])
        btn_frame.pack(pady=14)
        tk.Button(btn_frame, text="  再次挑战  ", font=self.font_btn,
                  fg=THEME['bg'], bg=THEME['accent'], relief='flat',
                  padx=16, pady=8, cursor='hand2',
                  command=self._on_restart).pack(side='left', padx=10)
        tk.Button(btn_frame, text="  退出游戏  ", font=self.font_btn,
                  fg=THEME['text_dim'], bg=THEME['panel'], relief='flat',
                  padx=16, pady=8, cursor='hand2',
                  command=self._on_quit).pack(side='left', padx=10)

    # ─────────── 结局界面 ───────────
    def _show_ending_screen(self):
        engine = self._engine
        endings = engine.check_endings()
        self._endings = endings

        for w in self.root.winfo_children():
            w.destroy()

        frame = tk.Frame(self.root, bg=THEME['bg'])
        frame.pack(fill='both', expand=True)

        if endings:
            main_ending = endings[0]
            tk.Label(frame, text=f"✦  {main_ending['name']}  ✦",
                     font=self.font_title, fg=THEME['crit_s'], bg=THEME['bg']).pack(pady=(28, 6))
            tk.Label(frame, text=main_ending['text'], font=self.font_lore,
                     fg=THEME['text'], bg=THEME['bg'], wraplength=740,
                     justify='center').pack(padx=80, pady=4)
            if len(endings) > 1:
                others = "、".join(e['name'] for e in endings[1:])
                tk.Label(frame, text=f"亦触发：{others}",
                         font=self.font_small, fg=THEME['accent2'],
                         bg=THEME['bg']).pack(pady=2)
        else:
            tk.Label(frame, text="试炼结束", font=self.font_title,
                     fg=THEME['text'], bg=THEME['bg']).pack(pady=(40, 8))
            tk.Label(frame, text="你完成了三场试炼，但没有触发特定结局。",
                     font=self.font_sub, fg=THEME['text_dim'], bg=THEME['bg']).pack()

        # 隐藏第十三试炼检测
        if engine.check_hidden_labor_trigger():
            tk.Label(frame, text="你在通关的光芒中，似乎听到了第十三个心跳……",
                     font=self.font_small, fg=THEME['accent2'], bg=THEME['bg'],
                     wraplength=740, justify='center').pack(pady=6)

        sep = tk.Frame(frame, height=1, bg=THEME['border'])
        sep.pack(fill='x', padx=80, pady=12)

        # 完整试炼报告
        self._show_report_panel(frame, engine)

        btn_frame = tk.Frame(frame, bg=THEME['bg'])
        btn_frame.pack(pady=12)
        tk.Button(btn_frame, text="  再次挑战  ", font=self.font_btn,
                  fg=THEME['bg'], bg=THEME['accent'], relief='flat',
                  padx=16, pady=8, cursor='hand2',
                  command=self._on_restart).pack(side='left', padx=10)
        tk.Button(btn_frame, text="  退出游戏  ", font=self.font_btn,
                  fg=THEME['text_dim'], bg=THEME['panel'], relief='flat',
                  padx=16, pady=8, cursor='hand2',
                  command=self._on_quit).pack(side='left', padx=10)

    # ─────────── 结算报告面板 ───────────
    def _show_report_panel(self, parent, engine):
        """在结算界面展示完整试炼报告（可滚动）"""
        report = engine.generate_post_game_report()
        rep_frame = tk.Frame(parent, bg=THEME['panel'],
                             highlightbackground=THEME['border'],
                             highlightthickness=1)
        rep_frame.pack(fill='both', expand=True, padx=80, pady=4)
        tk.Label(rep_frame, text="试 炼 报 告", font=self.font_btn,
                 fg=THEME['accent'], bg=THEME['panel']).pack(pady=(8, 2))
        txt = tk.Text(rep_frame, font=self.font_mono, fg=THEME['text'],
                      bg=THEME['panel'], relief='flat', wrap='word',
                      height=12, state='normal', cursor='arrow')
        scroll = tk.Scrollbar(rep_frame, command=txt.yview, bg=THEME['panel'])
        txt.config(yscrollcommand=scroll.set)
        txt.pack(side='left', fill='both', expand=True, padx=(10, 0), pady=4)
        scroll.pack(side='right', fill='y', pady=4)
        txt.insert('1.0', report)
        txt.config(state='disabled')

    def _on_restart(self):
        self._restart = True
        self.root.destroy()

    def _on_quit(self):
        self._restart = False
        self.root.destroy()

    # ─────────── 工具方法 ───────────
    def _set_text(self, widget: tk.Text, content: str):
        widget.config(state='normal')
        widget.delete('1.0', 'end')
        widget.insert('1.0', content)
        widget.config(state='disabled')

    def _log(self, msg: str, color: str = ''):
        self._log_text.config(state='normal')
        self._log_text.insert('end', f"{msg}\n")
        if color:
            start = self._log_text.index(f'end-{len(msg)+1}c')
            end = self._log_text.index('end-1c')
            tag = f'color_{len(self._log_text.tag_names())}'
            self._log_text.tag_add(tag, start, end)
            self._log_text.tag_config(tag, foreground=color)
        self._log_text.see('end')
        self._log_text.config(state='disabled')


# ─────────── 标题+选择独立入口 ───────────
def run_with_title(unlock_mgr):
    """完整游戏流程：标题 → 角色选择 → 游戏 → 结局 → 解锁保存
    支持结算后再次挑战，循环返回标题界面。"""
    from game_engine import GameEngine

    all_endings = []
    while True:
        choice = TkinterUI.launch_title(unlock_mgr, {})
        if choice is None:
            break

        character_id, labour_combo, challenge = choice
        engine = GameEngine(
            character_id, unlock_mgr, labour_combo,
            data_root=_data_path('data'), challenge=challenge
        )
        ui = TkinterUI()
        endings = ui.run(engine)

        if endings:
            for e in endings:
                unlock_mgr.unlock_ending(e['id'])
            all_endings.extend(endings)

        # 结算界面选"退出"则结束，选"再次挑战"则循环回标题
        if not ui._restart:
            break

    return all_endings


if __name__ == '__main__':
    # 直接运行此文件时用于测试
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from unlock_manager import UnlockManager
    from game_engine import GameEngine

    unlock = UnlockManager(
        save_path=_save_path('data/unlocks.json'),
        data_path=_data_path('data')
    )
    run_with_title(unlock)
