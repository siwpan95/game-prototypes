"""
Progress Quest Multiverse - Tkinter UI（原版PQ布局复刻）
完全对照原版Progress Quest界面布局：
- 左列：人物信息 → 属性 → 法术书 → 经验条
- 中列：11装备槽 → 背包详细目录 → 负重条
- 右上：剧情发展（章节复选框+倒计时）
- 右下：任务面板（多活跃任务）
- 底部：当前行动文字 + 大进度条
"""

import tkinter as tk
from tkinter import ttk, font as tkfont
import threading
import time
import sys
import os

# 添加src目录到路径
src_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from core.themed_engine import ThemedGameEngine

# ============================================================
# 颜色方案（原版PQ的Win32经典灰色/Excel风格）
# ============================================================
COLORS = {
    'bg': '#c0c0c0',           # 窗口背景（Win32标准灰）
    'frame_bg': '#e8e8e8',     # LabelFrame 内部背景（浅灰白，模拟Excel单元格）
    'text': '#000000',         # 黑色文字
    'bar_bg': '#a0a0a0',       # 进度条背景灰（带凹陷感）
    'exp_fill': '#0055cc',     # 经验条深蓝
    'action_fill': '#228b22',  # 行动条深绿
    'encum_fill': '#cc7700',   # 负重条深橙
    'plot_fill': '#8844aa',    # 剧情条深紫
    'header_bg': '#d0d0d0',    # 表头背景（略深于frame_bg）
    'highlight': '#ffff00',    # 高亮黄色
}

# 罗马数字转换
_ROMAN = ['','I','II','III','IV','V','VI','VII','VIII','IX','X',
          'XI','XII','XIII','XIV','XV','XVI','XVII','XVIII','XIX','XX',
          'XXI','XXII','XXIII','XXIV','XXV','XXVI','XXVII','XXVIII','XXIX','XXX']
def to_roman(n):
    return _ROMAN[min(max(n, 0), len(_ROMAN)-1)]


class PqMainWindow:
    """原版PQ风格主窗口"""

    def __init__(self, root, theme_name="warcraft", char_name=None, race=None, char_class=None):
        self.root = root
        display_name = ThemedGameEngine.get_theme_display_name(theme_name)
        self.root.title(f"Progress Quest - {display_name}")
        self.root.geometry("1000x680")
        self.root.configure(bg=COLORS['bg'])
        # 禁用窗口缩放以保持原版固定布局感（可选，注释掉即可恢复缩放）
        # self.root.resizable(False, False)
        
        # 引擎
        self.engine = ThemedGameEngine(theme_name)
        self.running = False
        
        # 字体（原版PQ使用小号等宽/系统字体，紧凑排列）
        self.font_ui = tkfont.Font(family='Microsoft YaHei UI', size=8)
        self.font_bold = tkfont.Font(family='Microsoft YaHei UI', size=8, weight='bold')
        self.font_title = tkfont.Font(family='Microsoft YaHei UI', size=9, weight='bold')
        self.font_small = tkfont.Font(family='Microsoft YaHei UI', size=7)
        
        # 构建全部UI
        self._build_main_layout()
        self._create_character(char_name, race, char_class)
        
        # 日志回调
        self.engine.on_log = self._on_log
        
        # 初始更新
        self._refresh_all()
        
        # 窗口大小变化时自动调整任务列宽
        self.root.bind('<Configure>', lambda e: self._auto_adjust_task_width())
    
    # ==================== 布局构建 ====================
    
    def _build_main_layout(self):
        """构建主布局：4列 + 底部栏"""
        # 顶部主区域（4列网格）
        self.main_frame = tk.Frame(self.root, bg=COLORS['bg'])
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        
        # 配置网格权重（任务列给更多空间，行也需扩展以填充垂直空间）
        self.main_frame.rowconfigure(0, weight=1)
        for col in range(4):
            self.main_frame.columnconfigure(col, weight=1 if col < 3 else 2)
        
        # ---- 第1列: 人物信息 / 属性 / 法术书 / 经验条 ----
        self._build_col_char()
        
        # ---- 第2列: 装备 / 背包 / 负重 ----
        self._build_col_equip()
        
        # ---- 第3列: 剧情发展 ----
        self._build_col_plot()
        
        # ---- 第4列: 任务面板 ----
        self._build_col_tasks()
        
        # ---- 底部: 行动状态栏 ----
        self._build_bottom_bar()
        
        # ---- 最底部: 控制按钮 ----
        self._build_control_bar()
    
    def _make_labelframe(self, parent, text, **kwargs):
        """创建统一风格的LabelFrame（紧凑原版PQ风格）"""
        lf = tk.LabelFrame(
            parent, text=text,
            font=self.font_bold,
            bg=COLORS['frame_bg'],
            fg=COLORS['text'],
            padx=1, pady=1,
            **kwargs
        )
        return lf
    
    # ---------- 第1列 ----------
    
    def _build_col_char(self):
        """左列：人物信息 + 属性 + HP/MP + 经验条 + 法术书"""
        frame = tk.Frame(self.main_frame, bg=COLORS['bg'])
        frame.grid(row=0, column=0, sticky='nswe', padx=(0,1))
        
        # === 人物信息面板 ===
        char_lf = self._make_labelframe(frame, "人物信息")
        char_lf.pack(fill=tk.X, pady=(0,1))
        
        # 特性表头
        hdr = tk.Frame(char_lf, bg=COLORS['header_bg'])
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text="特性", width=10, anchor='w', font=self.font_bold,
                 bg=COLORS['header_bg']).pack(side=tk.LEFT)
        tk.Label(hdr, text="值", width=12, anchor='center', font=self.font_bold,
                 bg=COLORS['header_bg']).pack(side=tk.LEFT)
        
        # 特性行
        self.char_labels = {}
        for label in ['名称', '种族', '职业', '等级']:
            row = tk.Frame(char_lf, bg=COLORS['frame_bg'])
            row.pack(fill=tk.X)
            tk.Label(row, text=label, width=10, anchor='w', font=self.font_ui,
                     bg=COLORS['frame_bg']).pack(side=tk.LEFT)
            lbl = tk.Label(row, text="", width=12, anchor='w', font=self.font_ui,
                           bg=COLORS['frame_bg'], fg=COLORS['text'])
            lbl.pack(side=tk.LEFT)
            self.char_labels[label] = lbl
        
        # === 属性面板 ===
        stat_lf = self._make_labelframe(frame, "属性")
        stat_lf.pack(fill=tk.X, pady=(0,1))
        
        hdr2 = tk.Frame(stat_lf, bg=COLORS['header_bg'])
        hdr2.pack(fill=tk.X)
        tk.Label(hdr2, text="属性", width=10, anchor='w', font=self.font_bold,
                 bg=COLORS['header_bg']).pack(side=tk.LEFT)
        tk.Label(hdr2, text="数值", width=12, anchor='center', font=self.font_bold,
                 bg=COLORS['header_bg']).pack(side=tk.LEFT)
        
        stat_names_cn = [('力', 'strength'), ('体', 'constitution'),
                         ('敏', 'dexterity'), ('智', 'intelligence'),
                         ('魅', 'charm'), ('慧', 'wisdom')]
        self.stat_labels = {}
        for cn, en in stat_names_cn:
            row = tk.Frame(stat_lf, bg=COLORS['frame_bg'])
            row.pack(fill=tk.X)
            tk.Label(row, text=cn, width=10, anchor='w', font=self.font_ui,
                     bg=COLORS['frame_bg']).pack(side=tk.LEFT)
            lbl = tk.Label(row, text="0", width=12, anchor='w', font=self.font_ui,
                           bg=COLORS['frame_bg'], fg='#0000cc')
            lbl.pack(side=tk.LEFT)
            self.stat_labels[cn] = lbl
        
        # HP / MP
        self.hp_label = tk.Label(stat_lf, text="HP Max      0",
                                  anchor='w', font=self.font_ui,
                                  bg=COLORS['frame_bg'], fg=COLORS['text'])
        self.hp_label.pack(fill=tk.X, anchor='w')
        self.mp_label = tk.Label(stat_lf, text="MP Max      0",
                                  anchor='w', font=self.font_ui,
                                  bg=COLORS['frame_bg'], fg=COLORS['text'])
        self.mp_label.pack(fill=tk.X, anchor='w')
        
        # === 经验条 ===
        exp_lf = self._make_labelframe(frame, "经验值")
        exp_lf.pack(fill=tk.X, pady=(0,1))
        
        self.exp_canvas = tk.Canvas(exp_lf, height=16, bg=COLORS['bar_bg'],
                                    highlightthickness=0)
        self.exp_canvas.pack(fill=tk.X, padx=1, pady=1)
        self.exp_bar_rect = None
        
        # === 法术书 ===
        spell_lf = self._make_labelframe(frame, "法术书")
        spell_lf.pack(fill=tk.BOTH, expand=True, pady=(0,1))
        
        # 表头
        shdr = tk.Frame(spell_lf, bg=COLORS['header_bg'])
        shdr.pack(fill=tk.X)
        tk.Label(shdr, text="咒语", width=16, anchor='w', font=self.font_bold,
                 bg=COLORS['header_bg']).pack(side=tk.LEFT)
        tk.Label(shdr, text="等级", width=6, anchor='center', font=self.font_bold,
                 bg=COLORS['header_bg']).pack(side=tk.LEFT)
        
        # 法术列表（带滚动）
        spell_container = tk.Frame(spell_lf, bg=COLORS['frame_bg'])
        spell_container.pack(fill=tk.BOTH, expand=True)
        
        self.spell_listbox = tk.Listbox(spell_container, font=self.font_ui,
                                         bg=COLORS['frame_bg'], fg=COLORS['text'],
                                         selectmode=tk.SINGLE, height=6,
                                         activestyle='none')
        spell_scroll = tk.Scrollbar(spell_container, command=self.spell_listbox.yview)
        self.spell_listbox.config(yscrollcommand=spell_scroll.set)
        self.spell_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        spell_scroll.pack(side=tk.RIGHT, fill=tk.Y)
    
    # ---------- 第2列 ----------
    
    def _build_col_equip(self):
        """中左列：装备 + 背包 + 负重"""
        frame = tk.Frame(self.main_frame, bg=COLORS['bg'])
        frame.grid(row=0, column=1, sticky='nswe', padx=(0,1))
        
        # === 装备 ===
        equip_lf = self._make_labelframe(frame, "装备")
        equip_lf.pack(fill=tk.BOTH, expand=True, pady=(0,1))
        
        # 装备槽位列表
        self.equip_labels = {}  # slot_id -> Label
        slot_order = ThemedGameEngine.SLOT_NAMES.keys()
        
        for slot_id in slot_order:
            cn_name = ThemedGameEngine.SLOT_NAMES.get(slot_id, slot_id)
            row = tk.Frame(equip_lf, bg=COLORS['frame_bg'])
            row.pack(fill=tk.X)
            
            tk.Label(row, text=cn_name, width=5, anchor='w', font=self.font_ui,
                     bg=COLORS['frame_bg']).pack(side=tk.LEFT)
            
            lbl = tk.Label(row, text="", anchor='w', font=self.font_small,
                           bg=COLORS['frame_bg'], fg=COLORS['text'],
                           wraplength=200, justify=tk.LEFT)
            lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)
            self.equip_labels[slot_id] = lbl
        
        # === 详细目录（背包）===
        inv_lf = self._make_labelframe(frame, "详细目录")
        inv_lf.pack(fill=tk.BOTH, expand=True, pady=(0,1))
        
        # 表头
        ihdr = tk.Frame(inv_lf, bg=COLORS['header_bg'])
        ihdr.pack(fill=tk.X)
        tk.Label(ihdr, text="项目", width=20, anchor='w', font=self.font_bold,
                 bg=COLORS['header_bg']).pack(side=tk.LEFT)
        tk.Label(ihdr, text="数量", width=5, anchor='center', font=self.font_bold,
                 bg=COLORS['header_bg']).pack(side=tk.LEFT)
        
        # 物品列表
        inv_container = tk.Frame(inv_lf, bg=COLORS['frame_bg'])
        inv_container.pack(fill=tk.BOTH, expand=True)
        
        self.inv_tree = ttk.Treeview(inv_container, columns=('count',),
                                      show='tree headings', height=8,
                                      selectmode='browse')
        self.inv_tree.heading('#0', text='项目')
        self.inv_tree.heading('count', text='数量')
        self.inv_tree.column('#0', width=150)
        self.inv_tree.column('count', width=40, anchor='center')
        
        inv_scroll = tk.Scrollbar(inv_container, command=self.inv_tree.yview)
        self.inv_tree.configure(yscrollcommand=inv_scroll.set)
        self.inv_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        inv_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # === 负重条 ===
        encum_lf = self._make_labelframe(frame, "负重")
        encum_lf.pack(fill=tk.X, pady=(0,1))
        
        self.encum_canvas = tk.Canvas(encum_lf, height=12, bg=COLORS['bar_bg'],
                                      highlightthickness=0)
        self.encum_canvas.pack(fill=tk.X, padx=1, pady=1)
    
    # ---------- 第3列 ----------
    
    def _build_col_plot(self):
        """中右列：剧情发展（原版PQ：逐步解锁，序章=纯文字）"""
        frame = tk.Frame(self.main_frame, bg=COLORS['bg'])
        frame.grid(row=0, column=2, sticky='nswe', padx=(0,1))

        plot_lf = self._make_labelframe(frame, "剧情发展")
        plot_lf.pack(fill=tk.BOTH, expand=True)

        # 序章文字区域（固定显示）
        self.plot_prologue_label = tk.Label(
            plot_lf, text="", font=self.font_small,
            bg=COLORS['frame_bg'], fg='#555', wraplength=200,
            justify=tk.LEFT, anchor='nw'
        )
        self.plot_prologue_label.pack(fill=tk.X, padx=2, pady=(2,1))

        # 章节复选框容器（动态更新）
        self.plot_chapter_frame = tk.Frame(plot_lf, bg=COLORS['frame_bg'])
        self.plot_chapter_frame.pack(fill=tk.BOTH, expand=True)

        self.plot_checkboxes = []
        self.plot_vars = []

        # 剧情进度条
        self.plot_canvas = tk.Canvas(plot_lf, height=14, bg=COLORS['bar_bg'],
                                      highlightthickness=0)
        self.plot_canvas.pack(fill=tk.X, padx=2, pady=2)

        # 倒计时/进度标签
        self.plot_time_label = tk.Label(plot_lf, text="",
                                         font=self.font_ui, bg=COLORS['frame_bg'],
                                         fg='#006400')
        self.plot_time_label.pack(anchor=tk.E)
    
    # ---------- 第4列 ----------
    
    def _build_col_tasks(self):
        """右列：任务面板"""
        frame = tk.Frame(self.main_frame, bg=COLORS['bg'])
        frame.grid(row=0, column=3, sticky='nswe')
        
        task_lf = self._make_labelframe(frame, "任务")
        task_lf.pack(fill=tk.BOTH, expand=True)
        
        # 任务列表（Treeview，两栏：类型+描述，匹配原版PQ格式）
        self.task_tree = ttk.Treeview(task_lf, columns=('desc',),
                                       show='tree headings', height=14,
                                       selectmode='browse')
        self.task_tree.heading('#0', text='')
        self.task_tree.heading('desc', text='')
        self.task_tree.column('#0', minwidth=60, width=70, stretch=False)
        self.task_tree.column('desc', minwidth=120, stretch=True)
        
        task_scroll = tk.Scrollbar(task_lf, command=self.task_tree.yview)
        self.task_tree.configure(yscrollcommand=task_scroll.set)
        self.task_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        task_scroll.pack(side=tk.RIGHT, fill=tk.Y)
    
    def _auto_adjust_task_width(self):
        """根据任务描述文字长度自动调整 desc 列宽"""
        try:
            tree_width = self.task_tree.winfo_width()
            if tree_width < 50:
                return
            # type列固定宽度，剩余给desc列
            type_col = self.task_tree.column('#0', 'width') or 70
            available = max(100, tree_width - type_col - 25)  # 减去scrollbar和边距
            
            # 计算所有描述文字的最大像素宽度
            max_desc_width = 0
            for item_id in self.task_tree.get_children():
                vals = self.task_tree.item(item_id, 'values')
                desc = vals[0] if vals else ''
                w = self.font_ui.measure(desc) if desc else 0
                if w > max_desc_width:
                    max_desc_width = w
            
            # 加上缩进空间
            needed = max_desc_width + 20
            col_w = min(needed, available)
            self.task_tree.column('desc', width=max(120, col_w))
        except tk.TclError:
            pass
    
    # ---------- 底部行动栏 ----------
    
    def _build_bottom_bar(self):
        """底部：当前行动描述 + 大进度条"""
        bottom_frame = tk.Frame(self.root, bg=COLORS['bg'])
        bottom_frame.pack(fill=tk.X, padx=2)
        
        # 行动文字
        self.action_label = tk.Label(bottom_frame, text="准备开始冒险...",
                                      font=self.font_ui, anchor='w',
                                      bg=COLORS['bg'], fg=COLORS['text'])
        self.action_label.pack(fill=tk.X, side=tk.LEFT, padx=(0,5))
        
        # 大进度条
        self.action_canvas = tk.Canvas(bottom_frame, height=20, bg=COLORS['bar_bg'],
                                        highlightthickness=1, highlightbackground='#888')
        self.action_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0,2))
    
    # ---------- 控制按钮栏 ----------
    
    def _build_control_bar(self):
        """底部控制按钮"""
        ctrl = tk.Frame(self.root, bg=COLORS['bg'])
        ctrl.pack(fill=tk.X, pady=2)
        
        self.btn_start = tk.Button(ctrl, text="▶ 开始", font=self.font_ui, width=10,
                                   command=self.start_game, bg='#228b22', fg='white',
                                   activebackground='#32cd32')
        self.btn_start.pack(side=tk.LEFT, padx=3)
        
        self.btn_stop = tk.Button(ctrl, text="⏹ 停止", font=self.font_ui, width=10,
                                  command=self.stop_game, state=tk.DISABLED,
                                  bg='#b22222', fg='white')
        self.btn_stop.pack(side=tk.LEFT, padx=3)
        
        self.btn_save = tk.Button(ctrl, text="💾 保存", font=self.font_ui, width=10,
                                  command=self.save_game)
        self.btn_save.pack(side=tk.LEFT, padx=3)
        
        self.btn_load = tk.Button(ctrl, text="📂 加载", font=self.font_ui, width=10,
                                  command=self.load_game)
        self.btn_load.pack(side=tk.LEFT, padx=3)
        
        # 状态标签
        self.status_label = tk.Label(ctrl, text="就绪", font=self.font_small,
                                      bg=COLORS['bg'], fg='#666')
        self.status_label.pack(side=tk.RIGHT, padx=5)
    
    # ==================== 数据操作 ====================
    
    def _create_character(self, char_name=None, race=None, char_class=None):
        """创建角色（支持外部传入，未传入则取默认）"""
        if not char_name:
            char_name = "勇者"
        if not race:
            race = self.engine.theme.races[0] if self.engine.theme.races else "人类"
        if not char_class:
            char_class = self.engine.theme.classes[0] if self.engine.theme.classes else "战士"
        self.engine.create_character(char_name, race, char_class)
    
    def _refresh_all(self):
        """刷新全部UI数据"""
        data = self.engine.get_ui_data()
        if not data:
            return
        
        c = data.get('char', {})
        
        # 人物信息
        for key, label in self.char_labels.items():
            map_key = {'名称':'name','种族':'race','职业':'class','等级':'level'}
            val = c.get(map_key.get(key, key), '')
            if isinstance(val, int):
                val = str(val)
            label.config(text=val)
        
        # 属性
        stats = c.get('stats', {})
        for cn, lbl in self.stat_labels.items():
            val = stats.get(cn, 0)
            lbl.config(text=str(val))
        
        # HP/MP
        self.hp_label.config(text=f"HP Max{c.get('hp_max',0):>10}")
        self.mp_label.config(text=f"MP Max{c.get('mp_max',0):>10}")
        
        # 装备
        equip_data = data.get('equipment', [])
        for slot_id, (slot_name, display_name) in zip(ThemedGameEngine.SLOT_NAMES.keys(), equip_data):
            if slot_id in self.equip_labels:
                self.equip_labels[slot_id].config(text=display_name or "")
        
        # 法术书
        self.spell_listbox.delete(0, tk.END)
        spells = data.get('spellbook', [])
        for name, level in spells:
            rlv = to_roman(level)
            self.spell_listbox.insert(tk.END, f"{name:<16s}{rlv:>6s}")
        
        # 背包
        for item in self.inv_tree.get_children():
            self.inv_tree.delete(item)
        inv_data = data.get('inventory', [])
        # 先显示金币
        gold = c.get('gold', 0)
        self.inv_tree.insert('', 'end', iid='_gold', text='金币', values=(str(gold),),
                              tags=('gold',))
        self.inv_tree.tag_configure('gold', foreground='#d4a017')
        # 再显示物品
        for item_name, count in inv_data:
            self.inv_tree.insert('', 'end', text=item_name, values=(str(count),))
        
        # 剧情章节（逐步解锁，序章=纯文字）
        chapters = data.get('plot_chapters', [])
        # 更新序章文字
        prologue_text = ""
        for name, completed, unlocked, is_prologue, desc in chapters:
            if is_prologue:
                prologue_text = desc or f"【{name}】故事背景..."
        self.plot_prologue_label.config(text=prologue_text)

        # 动态重建章节复选框（只显示已解锁的非序章章节）
        for widget in self.plot_chapter_frame.winfo_children():
            widget.destroy()
        self.plot_checkboxes.clear()
        self.plot_vars.clear()

        for name, completed, unlocked, is_prologue, desc in chapters:
            if is_prologue or not unlocked:
                continue
            var = tk.IntVar(value=1 if completed else 0)
            cb = tk.Checkbutton(self.plot_chapter_frame, text=name, variable=var,
                                 font=self.font_ui, bg=COLORS['frame_bg'],
                                 activebackground=COLORS['frame_bg'],
                                 state=tk.DISABLED)
            cb.pack(anchor=tk.W)
            self.plot_checkboxes.append(cb)
            self.plot_vars.append(var)
        
        # 任务（原版PQ格式：☑/☐ + 类型 | — + 描述）
        for item in self.task_tree.get_children():
            self.task_tree.delete(item)
        tasks = data.get('active_tasks', [])
        for t_type, desc, completed in tasks:
            check = "☑" if completed else "☐"
            type_text = f"{check}{t_type}"
            desc_text = f"—{desc}"
            self.task_tree.insert('', 'end', text=type_text, values=(desc_text,))
        self._auto_adjust_task_width()
        
        # 进度条
        bars = data.get('bars', {})
        self._draw_bar(self.exp_canvas, bars.get('exp', 0), COLORS['exp_fill'], 16)
        self._draw_bar(self.encum_canvas, bars.get('encum', 0), COLORS['encum_fill'], 12)
        self._draw_bar(self.plot_canvas, bars.get('plot', 0), COLORS['plot_fill'], 14)
        
        # 底部行动栏
        action_text = data.get('action_text', '')
        action_pct = data.get('action_percent', 0)
        self.action_label.config(text=action_text)
        self._draw_bar(self.action_canvas, action_pct, COLORS['action_fill'], 20)
        
        # 倒计时
        plot_pct = bars.get('plot', 0)
        unlocked_chapters = [(n, c, u, p, d) for n, c, u, p, d in chapters if u and not p]
        remaining_chapters = sum(1 for n, c, u, p, d in unlocked_chapters if not c)
        if remaining_chapters > 0:
            total_q = self.engine._quests_completed_total
            # 找下一章所需任务数
            next_req = 999
            for name, comp, unlk, pro, desc in chapters:
                if not pro and unlk and not comp:
                    # 找到这个 chapter 在 plot_chapters 列表中的索引来获取 tasks_required
                    idx = self.engine.plot_chapters.index(
                        next((ch for ch in self.engine.plot_chapters if ch.name == name), None)
                    )
                    if 0 <= idx < len(self.engine.plot_chapters):
                        next_req = self.engine.plot_chapters[idx].tasks_required
                    break
            remaining = max(0, next_req - total_q)
            self.plot_time_label.config(text=f"  还需 {remaining} 个任务解锁下章")
        else:
            self.plot_time_label.config(text="")
    
    def _draw_bar(self, canvas, percent, color, height):
        """绘制Canvas进度条"""
        canvas.delete('all')
        w = canvas.winfo_width() or 300
        h = height
        pct = max(0, min(100, percent))
        fill_w = int(w * pct / 100)
        if fill_w > 0:
            canvas.create_rectangle(0, 0, fill_w, h, fill=color, outline='')
    
    # ==================== 游戏控制 ====================
    
    def start_game(self):
        """开始游戏"""
        if not self.character_created():
            return
        self.running = True
        self.btn_start.config(state=tk.DISABLED)
        self.btn_stop.config(state=tk.NORMAL)
        self.status_label.config(text="运行中...", fg='green')
        
        def game_loop():
            while self.running and self.character_created():
                self.engine._game_tick()
                self.root.after(0, self._refresh_all)
                time.sleep(0.5)
            self.root.after(0, self._on_stopped)
        
        threading.Thread(target=game_loop, daemon=True).start()
    
    def stop_game(self):
        """停止游戏"""
        self.running = False
    
    def _on_stopped(self):
        """停止后回调"""
        self.btn_start.config(state=tk.NORMAL)
        self.btn_stop.config(state=tk.DISABLED)
        self.status_label.config(text="已停止", fg='#666')
        self.engine.save_game()
    
    def save_game(self):
        """保存游戏"""
        try:
            self.engine.save_game()
            self.status_label.config(text="已保存", fg='green')
        except Exception as e:
            self.status_label.config(text=f"保存失败: {e}", fg='red')
    
    def load_game(self):
        """加载游戏"""
        try:
            self.engine.load_game()
            self._refresh_all()
            self.status_label.config(text="已加载", fg='green')
        except FileNotFoundError:
            self.status_label.config(text="没有存档", fg='orange')
        except Exception as e:
            self.status_label.config(text=f"加载失败: {e}", fg='red')
    
    def character_created(self):
        """检查角色是否已创建"""
        return self.engine.character is not None
    
    def _on_log(self, msg):
        """日志回调（可选：可添加底部日志区）"""
        pass


# ==================== 入口 ====================

def main(root=None, theme_name="warcraft"):
    """启动UI"""
    if root is None:
        root = tk.Tk()
        app = PqMainWindow(root, theme_name=theme_name)
        root.mainloop()


if __name__ == "__main__":
    main()
