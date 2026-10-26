"""
PQ 架构版 - 简化测试 UI

用于验证 PQ 核心架构（队列系统、Tick 引擎）与 UI 的集成。
"""
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import sys
import os

# 添加src目录到路径
src_path = os.path.dirname(os.path.abspath(__file__))
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from themed_engine_pq import PQThemedGameEngine


class PQTestUI:
    """PQ 架构版测试 UI"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("Progress Quest Multiverse - PQ 架构测试")
        self.root.geometry("800x600")
        self.root.configure(bg='#f0f0f0')
        
        self.engine = None
        self.is_running = False
        
        self._build_ui()
    
    def _build_ui(self):
        """构建 UI"""
        # === 顶部：主题选择 ===
        top_frame = tk.Frame(self.root, bg='#f0f0f0')
        top_frame.pack(fill=tk.X, padx=10, pady=5)
        
        tk.Label(top_frame, text="主题:", bg='#f0f0f0').pack(side=tk.LEFT, padx=(0, 5))
        
        self.theme_var = tk.StringVar(value="diablo")
        theme_combo = ttk.Combobox(top_frame, textvariable=self.theme_var, 
                                    values=list(PQThemedGameEngine.list_themes()), 
                                    state='readonly', width=15)
        theme_combo.pack(side=tk.LEFT, padx=5)
        
        # === 中间：状态显示 ===
        status_frame = tk.LabelFrame(self.root, text="游戏状态", bg='#f0f0f0', font=('Microsoft YaHei UI', 9, 'bold'))
        status_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # 当前行动
        action_frame = tk.Frame(status_frame, bg='#f0f0f0')
        action_frame.pack(fill=tk.X, padx=5, pady=5)
        
        tk.Label(action_frame, text="当前行动:", bg='#f0f0f0', font=('Microsoft YaHei UI', 9, 'bold')).pack(side=tk.LEFT)
        self.action_label = tk.Label(action_frame, text="未开始", bg='#f0f0f0', fg='#0000cc')
        self.action_label.pack(side=tk.LEFT, padx=5)
        
        # 进度条
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(status_frame, variable=self.progress_var, 
                                             maximum=100, length=700, mode='determinate')
        self.progress_bar.pack(padx=5, pady=5)
        
        # 队列状态
        queue_frame = tk.Frame(status_frame, bg='#f0f0f0')
        queue_frame.pack(fill=tk.X, padx=5, pady=5)
        
        tk.Label(queue_frame, text="队列长度:", bg='#f0f0f0').pack(side=tk.LEFT)
        self.queue_label = tk.Label(queue_frame, text="0", bg='#f0f0f0', fg='#cc0000')
        self.queue_label.pack(side=tk.LEFT, padx=5)
        
        # 角色信息
        char_frame = tk.LabelFrame(status_frame, text="角色信息", bg='#f0f0f0')
        char_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.char_text = tk.Text(char_frame, height=6, width=90, bg='#ffffff', fg='#000000')
        self.char_text.pack(padx=5, pady=5)
        
        # 日志
        log_frame = tk.LabelFrame(status_frame, text="日志", bg='#f0f0f0')
        log_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.log_text = tk.Text(log_frame, height=10, width=90, bg='#000000', fg='#00ff00')
        self.log_text.pack(padx=5, pady=5)
        
        # === 底部：控制按钮 ===
        button_frame = tk.Frame(self.root, bg='#f0f0f0')
        button_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.btn_create = tk.Button(button_frame, text="创建角色", command=self._create_character, 
                                  bg='#4caf50', fg='white', font=('Microsoft YaHei UI', 9, 'bold'))
        self.btn_create.pack(side=tk.LEFT, padx=5)
        
        self.btn_start = tk.Button(button_frame, text="开始游戏", command=self._start_game, 
                                 bg='#2196f3', fg='white', font=('Microsoft YaHei UI', 9, 'bold'), 
                                 state=tk.DISABLED)
        self.btn_start.pack(side=tk.LEFT, padx=5)
        
        self.btn_stop = tk.Button(button_frame, text="停止游戏", command=self._stop_game, 
                                bg='#f44336', fg='white', font=('Microsoft YaHei UI', 9, 'bold'), 
                                state=tk.DISABLED)
        self.btn_stop.pack(side=tk.LEFT, padx=5)
        
        self.btn_exit = tk.Button(button_frame, text="退出", command=self.root.quit, 
                                bg='#9e9e9e', fg='white', font=('Microsoft YaHei UI', 9))
        self.btn_exit.pack(side=tk.RIGHT, padx=5)
    
    def _create_character(self):
        """创建角色"""
        theme_name = self.theme_var.get()
        
        try:
            self.engine = PQThemedGameEngine(theme_name, seed=12345)
            
            # 获取主题的第一个种族和职业
            races = self.engine.get_available_races()
            classes = self.engine.get_available_classes()
            
            if not races or not classes:
                messagebox.showerror("错误", "主题数据不完整")
                return
            
            # 创建角色
            self.engine.create_character("测试英雄", races[0], classes[0])
            
            # 设置回调
            self.engine.on_log = self._on_log
            self.engine.on_update = self._on_update
            
            self.log(f"✅ 角色创建成功: 测试英雄 ({races[0]} {classes[0]})")
            self.log(f"🎲 随机种子: {self.engine.rng.get_seed()}")
            
            # 更新按钮状态
            self.btn_start.config(state=tk.NORMAL)
            self.btn_create.config(state=tk.DISABLED)
            
            # 更新角色信息
            self._update_char_info()
            
        except Exception as e:
            messagebox.showerror("错误", str(e))
            self.log(f"❌ 创建角色失败: {e}")
    
    def _start_game(self):
        """开始游戏"""
        if not self.engine:
            return
        
        try:
            self.engine.start_game()
            self.is_running = True
            
            self.btn_start.config(state=tk.DISABLED)
            self.btn_stop.config(state=tk.NORMAL)
            
            self.log(f"▶️ 游戏开始 (Tick 间隔: 50ms)")
            
        except Exception as e:
            messagebox.showerror("错误", str(e))
            self.log(f"❌ 开始游戏失败: {e}")
    
    def _stop_game(self):
        """停止游戏"""
        if not self.engine:
            return
        
        try:
            self.engine.stop_game()
            self.is_running = False
            
            self.btn_start.config(state=tk.NORMAL)
            self.btn_stop.config(state=tk.DISABLED)
            
            self.log(f"⏸️ 游戏停止")
            
        except Exception as e:
            messagebox.showerror("错误", str(e))
            self.log(f"❌ 停止游戏失败: {e}")
    
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
        
        # 更新队列长度
        self.queue_label.config(text=str(status.get('queue_length', 0)))
        
        # 更新角色信息
        self._update_char_info()
    
    def _update_char_info(self):
        """更新角色信息"""
        if not self.engine or not self.engine.character:
            return
        
        char = self.engine.character
        
        info = f"名称: {getattr(char, 'name', 'Unknown')}\n"
        info += f"等级: {getattr(char, 'level', 1)}\n"
        info += f"经验: {getattr(char, 'exp', 0)}\n"
        info += f"金币: {getattr(char, 'gold', 0)}\n"
        info += f"Tick 计数: {self.engine.tick_engine._tick_count if self.engine.tick_engine else 0}\n"
        
        self.char_text.delete(1.0, tk.END)
        self.char_text.insert(tk.END, info)
    
    def log(self, msg):
        """添加日志"""
        self.log_text.insert(tk.END, f"{msg}\n")
        self.log_text.see(tk.END)


def main():
    """主函数"""
    root = tk.Tk()
    app = PQTestUI(root)
    root.mainloop()


if __name__ == '__main__':
    main()
