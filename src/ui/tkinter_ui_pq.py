"""
Progress Quest Multiverse - PQ 架构版 Tkinter UI

基于 tkinter_ui_themed.py 修改，接入 PQ 核心架构。
"""
import tkinter as tk
from tkinter import ttk, font as tkfont, messagebox
import threading
import time
import sys
import os

# 添加src目录到路径
src_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from core.themed_engine_pq import PQThemedGameEngine


# 颜色方案（原版PQ的Win32经典灰色/Excel风格）
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
    """PQ 架构版主窗口"""
    
    def __init__(self, root, theme_name="diablo", char_name=None, race=None, char_class=None):
        self.root = root
        display_name = PQThemedGameEngine.get_theme_display_name(theme_name)
        self.root.title(f"Progress Quest Multiverse - {display_name}")
        self.root.geometry("1000x680")
        self.root.configure(bg=COLORS['bg'])
        
        # 引擎
        self.engine = None
        self.running = False
        
        # 字体（原版PQ使用小号紧凑排列）
        self.font_ui = tkfont.Font(family='Microsoft YaHei UI', size=8)
        self.font_bold = tkfont.Font(family='Microsoft YaHei UI', size=8, weight='bold')
        self.font_title = tkfont.Font(family='Microsoft YaHei UI', size=9, weight='bold')
        self.font_small = tkfont.Font(family='Microsoft YaHei UI', size=7)
        
        # 先创建引擎
        try:
            self.engine = PQThemedGameEngine(theme_name)
        except Exception as e:
            messagebox.showerror("错误", f"无法加载主题: {e}")
            return
        
        # 构建全部UI
        self._build_main_layout()
        
        # 如果提供了角色参数，直接创建角色
        if char_name and race and char_class:
            self._create_character_direct(char_name, race, char_class)
        else:
            self._show_start_dialog()
        
        # 日志回调
        self.engine.on_log = self._on_log
        
        # 初始更新
        self._refresh_all()
    
    def _show_start_dialog(self):
        """显示开始对话框"""
        dialog = tk.Toplevel(self.root)
        dialog.title("创建角色")
        dialog.geometry("400x300")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # 主题信息
        tk.Label(dialog, text=f"主题: {self.engine.theme.name}", 
                 font=self.font_title).pack(pady=10)
        tk.Label(dialog, text=self.engine.theme.get_theme_description(), 
                 wraplength=350, justify=tk.LEFT).pack(padx=20, pady=5)
        
        # 角色名称
        tk.Label(dialog, text="角色名称:").pack(anchor=tk.W, padx=20, pady=(10, 0))
        name_var = tk.StringVar(value="黑暗流浪者")
        tk.Entry(dialog, textvariable=name_var, width=30).pack(padx=20)
        
        # 种族选择
        tk.Label(dialog, text="种族:").pack(anchor=tk.W, padx=20, pady=(10, 0))
        race_var = tk.StringVar(value=self.engine.get_available_races()[0])
        race_combo = ttk.Combobox(dialog, textvariable=race_var, 
                                   values=self.engine.get_available_races(), 
                                   state='readonly', width=27)
        race_combo.pack(padx=20)
        
        # 职业选择
        tk.Label(dialog, text="职业:").pack(anchor=tk.W, padx=20, pady=(10, 0))
        class_var = tk.StringVar(value=self.engine.get_available_classes()[0])
        class_combo = ttk.Combobox(dialog, textvariable=class_var, 
                                     values=self.engine.get_available_classes(), 
                                     state='readonly', width=27)
        class_combo.pack(padx=20)
        
        # 按钮
        btn_frame = tk.Frame(dialog)
        btn_frame.pack(pady=20)
        
        def on_ok():
            name = name_var.get()
            race = race_var.get()
            char_class = class_var.get()
            dialog.destroy()
            self._create_character_direct(name, race, char_class)
        
        tk.Button(btn_frame, text="开始冒险", command=on_ok, 
                   bg='#4caf50', fg='white', font=self.font_bold).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="取消", command=dialog.destroy, 
                   bg='#9e9e9e', fg='white').pack(side=tk.LEFT, padx=5)
        
        # 居中显示
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
        y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")
    
    def _create_character_direct(self, name, race, char_class):
        """直接创建角色"""
        try:
            self.engine.create_character(name, race, char_class)
            self.engine.on_update = self._on_update
            self._refresh_all()
            self.log(f"✅ 角色创建成功: {name}")
        except Exception as e:
            messagebox.showerror("错误", str(e))
    
    def _build_main_layout(self):
        """构建主布局"""
        # 顶部主区域（4列网格）
        self.main_frame = tk.Frame(self.root, bg=COLORS['bg'])
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        
        # 配置网格权重（日志列给更多空间，行也需扩展以填充垂直空间）
        self.main_frame.rowconfigure(0, weight=1)
        for col in range(4):
            self.main_frame.columnconfigure(col, weight=1 if col < 3 else 2)
        
        # 第1列: 人物信息
        self._build_col_char()
        
        # 第2列: 装备
        self._build_col_equip()
        
        # 第3列: PQ 状态
        self._build_col_pq_status()
        
        # 第4列: 日志
        self._build_col_log()
        
        # 底部: 行动状态栏
        self._build_bottom_bar()
        
        # 最底部: 控制按钮
        self._build_control_bar()
    
    def _build_col_char(self):
        """第1列：人物信息"""
        frame = tk.Frame(self.main_frame, bg=COLORS['bg'])
        frame.grid(row=0, column=0, sticky='nswe', padx=(0, 1))
        
        # 人物信息面板
        char_lf = self._make_labelframe(frame, "人物信息")
        char_lf.pack(fill=tk.X, pady=(0, 1))
        
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
        
        # 经验条
        exp_lf = self._make_labelframe(frame, "经验值")
        exp_lf.pack(fill=tk.X, pady=(0, 1))
        
        self.exp_canvas = tk.Canvas(exp_lf, height=16, bg=COLORS['bar_bg'],
                                    highlightthickness=0)
        self.exp_canvas.pack(fill=tk.X, padx=1, pady=1)
        self.exp_bar_rect = None
    
    def _build_col_equip(self):
        """第2列：装备"""
        frame = tk.Frame(self.main_frame, bg=COLORS['bg'])
        frame.grid(row=0, column=1, sticky='nswe', padx=(0, 1))
        
        # 装备面板
        equip_lf = self._make_labelframe(frame, "装备")
        equip_lf.pack(fill=tk.BOTH, expand=True, pady=(0, 1))
        
        self.equip_text = tk.Text(equip_lf, height=15, width=30, bg='#ffffff', fg='#000000')
        self.equip_text.pack(padx=5, pady=5, fill=tk.BOTH, expand=True)
    
    def _build_col_pq_status(self):
        """第3列：PQ 架构状态"""
        frame = tk.Frame(self.main_frame, bg=COLORS['bg'])
        frame.grid(row=0, column=2, sticky='nswe', padx=(0, 1))
        
        # PQ 状态面板
        pq_lf = self._make_labelframe(frame, "PQ 架构状态")
        pq_lf.pack(fill=tk.BOTH, expand=True, pady=(0, 1))
        
        # 当前行动
        tk.Label(pq_lf, text="当前行动:", bg=COLORS['frame_bg'], 
                  font=self.font_bold).pack(anchor=tk.W, padx=5, pady=(5, 0))
        self.action_label = tk.Label(pq_lf, text="未开始", bg=COLORS['frame_bg'], 
                                    fg='#0000cc', wraplength=200, justify=tk.LEFT)
        self.action_label.pack(anchor=tk.W, padx=5, pady=(0, 5))
        
        # 进度条
        tk.Label(pq_lf, text="进度:", bg=COLORS['frame_bg'], 
                  font=self.font_bold).pack(anchor=tk.W, padx=5, pady=(5, 0))
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(pq_lf, variable=self.progress_var, 
                                             maximum=100, length=200, mode='determinate')
        self.progress_bar.pack(padx=5, pady=5, fill=tk.X)
        
        # 队列状态
        tk.Label(pq_lf, text="队列状态:", bg=COLORS['frame_bg'], 
                  font=self.font_bold).pack(anchor=tk.W, padx=5, pady=(5, 0))
        self.queue_label = tk.Label(pq_lf, text="队列长度: 0", bg=COLORS['frame_bg'], 
                                    fg='#cc0000')
        self.queue_label.pack(anchor=tk.W, padx=5, pady=(0, 5))
        
        # Tick 计数
        tk.Label(pq_lf, text="Tick 计数:", bg=COLORS['frame_bg'], 
                  font=self.font_bold).pack(anchor=tk.W, padx=5, pady=(5, 0))
        self.tick_label = tk.Label(pq_lf, text="0", bg=COLORS['frame_bg'], 
                                   fg='#000000')
        self.tick_label.pack(anchor=tk.W, padx=5, pady=(0, 5))
    
    def _build_col_log(self):
        """第4列：日志"""
        frame = tk.Frame(self.main_frame, bg=COLORS['bg'])
        frame.grid(row=0, column=3, sticky='nswe')
        
        log_lf = self._make_labelframe(frame, "日志")
        log_lf.pack(fill=tk.BOTH, expand=True, pady=(0, 1))
        
        self.log_text = tk.Text(log_lf, height=20, width=40, bg='#000000', fg='#00ff00')
        self.log_text.pack(padx=5, pady=5, fill=tk.BOTH, expand=True)
    
    def _build_bottom_bar(self):
        """底部：行动状态栏"""
        bottom_frame = tk.Frame(self.root, bg=COLORS['bg'], height=30)
        bottom_frame.pack(fill=tk.X, side=tk.BOTTOM, padx=2, pady=(0, 2))
        
        self.status_label = tk.Label(bottom_frame, text="准备就绪", 
                                    bg=COLORS['bg'], font=self.font_ui)
        self.status_label.pack(side=tk.LEFT, padx=5)
    
    def _build_control_bar(self):
        """最底部：控制按钮"""
        control_frame = tk.Frame(self.root, bg=COLORS['bg'], height=30)
        control_frame.pack(fill=tk.X, side=tk.BOTTOM, padx=2, pady=(0, 2))
        
        self.btn_start = tk.Button(control_frame, text="开始游戏", command=self._start_game, 
                                  bg='#2196f3', fg='white', font=self.font_bold)
        self.btn_start.pack(side=tk.LEFT, padx=5)
        
        self.btn_stop = tk.Button(control_frame, text="停止游戏", command=self._stop_game, 
                                 bg='#f44336', fg='white', font=self.font_bold, state=tk.DISABLED)
        self.btn_stop.pack(side=tk.LEFT, padx=5)
        
        self.btn_exit = tk.Button(control_frame, text="退出", command=self.root.quit, 
                                 bg='#9e9e9e', fg='white')
        self.btn_exit.pack(side=tk.RIGHT, padx=5)
    
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
    
    def _start_game(self):
        """开始游戏"""
        if not self.engine or not self.engine.character:
            messagebox.showwarning("警告", "请先创建角色")
            return
        
        try:
            self.engine.start_game()
            self.running = True
            
            self.btn_start.config(state=tk.DISABLED)
            self.btn_stop.config(state=tk.NORMAL)
            
            self.log("▶️ 游戏开始")
            
        except Exception as e:
            messagebox.showerror("错误", str(e))
    
    def _stop_game(self):
        """停止游戏"""
        if not self.engine:
            return
        
        try:
            self.engine.stop_game()
            self.running = False
            
            self.btn_start.config(state=tk.NORMAL)
            self.btn_stop.config(state=tk.DISABLED)
            
            self.log("⏸️ 游戏停止")
            
        except Exception as e:
            messagebox.showerror("错误", str(e))
    
    def _on_log(self, msg):
        """日志回调"""
        self.log_text.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] {msg}\n")
        self.log_text.see(tk.END)
    
    def _on_update(self, status):
        """更新回调 (从 TickEngine 调用)"""
        # 使用 after 确保在主线程更新 UI
        self.root.after(0, self._update_ui, status)
    
    def _update_ui(self, status):
        """更新 UI (主线程)"""
        # 更新当前行动
        self.action_label.config(text=status.get('current_action', 'Unknown'))
        
        # 更新进度条
        progress = status.get('progress', 0.0) * 100
        self.progress_var.set(progress)
        
        # 更新队列状态
        queue_text = f"队列长度: {status.get('queue_length', 0)}\n"
        queue_text += f"Tick 计数: {status.get('tick_count', 0)}"
        self.queue_label.config(text=queue_text)
        
        # 更新 Tick 计数
        self.tick_label.config(text=str(status.get('tick_count', 0)))
        
        # 更新角色信息
        self._update_char_info()
    
    def _update_char_info(self):
        """更新角色信息"""
        if not self.engine or not self.engine.character:
            return
        
        char = self.engine.character
        
        # 更新标签
        if '名称' in self.char_labels:
            self.char_labels['名称'].config(text=getattr(char, 'name', 'Unknown'))
        if '种族' in self.char_labels:
            self.char_labels['种族'].config(text=getattr(char, 'race', 'Unknown'))
        if '职业' in self.char_labels:
            self.char_labels['职业'].config(text=getattr(char, 'char_class', 'Unknown'))
        if '等级' in self.char_labels:
            self.char_labels['等级'].config(text=str(getattr(char, 'level', 1)))
        
        # 更新经验条
        self._update_exp_bar()
        
        # 更新装备信息
        self._update_equip_info()
    
    def _update_exp_bar(self):
        """更新经验条"""
        if not self.engine or not self.engine.character:
            return
        
        char = self.engine.character
        level = getattr(char, 'level', 1)
        exp = getattr(char, 'exp', 0)
        
        # 计算经验百分比
        exp_needed = 20 * level * 60
        exp_percent = min(exp / exp_needed * 100, 100) if exp_needed > 0 else 0
        
        # 绘制经验条
        self.exp_canvas.delete("all")
        width = self.exp_canvas.winfo_width()
        if width > 1:
            fill_width = int(width * exp_percent / 100)
            self.exp_canvas.create_rectangle(0, 0, fill_width, 16, 
                                              fill=COLORS['exp_fill'], outline="")
            self.exp_canvas.create_text(width // 2, 9, 
                                          text=f"EXP: {exp}/{exp_needed} ({exp_percent:.1f}%)", 
                                          fill='white', font=self.font_small)
    
    def _update_equip_info(self):
        """更新装备信息"""
        if not self.engine or not self.engine.character:
            return
        
        # 这里需要从 engine.character 获取装备信息
        # 具体实现取决于 Character 类的数据结构
        pass
    
    def _refresh_all(self):
        """刷新所有 UI"""
        self._update_char_info()
    
    def log(self, msg):
        """添加日志"""
        self.log_text.insert(tk.END, f"{msg}\n")
        self.log_text.see(tk.END)


def main():
    """主函数"""
    root = tk.Tk()
    app = PqMainWindow(root, theme_name="diablo")
    root.mainloop()


if __name__ == '__main__':
    main()
