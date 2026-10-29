"""可复用 Tkinter 辅助组件"""
import tkinter as tk
from tkinter import messagebox
from typing import Callable, Optional


class TaggedTextDisplay(tk.Text):
    """带标签配置的 ASCII 显示区域"""

    TAG_STYLES = {
        "player": {"foreground": "#f1c40f", "font": ("Courier New", 12, "bold")},
        "npc": {"foreground": "#9b59b6", "font": ("Courier New", 12, "bold")},
        "bounty": {"foreground": "#e74c3c", "font": ("Courier New", 12, "bold")},
        "town": {"foreground": "#3498db"},
        "mountain": {"foreground": "#95a5a6"},
        "water": {"foreground": "#2980b9"},
        "tree": {"foreground": "#27ae60"},
    }

    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg="black", fg="#ecf0f1",
                         font=("Courier New", 12),
                         width=60, height=30,
                         state=tk.DISABLED, cursor="arrow",
                         **kwargs)
        for tag, style in self.TAG_STYLES.items():
            self.tag_config(tag, **style)

    def set_content(self, text: str):
        """设置内容（World地图时会自动应用标签）"""
        self.config(state=tk.NORMAL)
        self.delete(1.0, tk.END)

        # 逐行处理：对世界地图应用颜色标签
        lines = text.split('\n')
        map_started = False
        for line_idx, line in enumerate(lines):
            if map_started or self._looks_like_map_line(line):
                map_started = True
                if self._looks_like_map_line(line):
                    self._insert_map_line(line)
                else:
                    self.insert(tk.END, line)
                if line_idx < len(lines) - 1:
                    self.insert(tk.END, "\n")
            else:
                self.insert(tk.END, line)
                if line_idx < len(lines) - 1:
                    self.insert(tk.END, "\n")

        self.config(state=tk.DISABLED)

    def _looks_like_map_line(self, line: str) -> bool:
        """判断是否像是地图行（由 .P N B □ ^ ~ T 等字符组成）"""
        if len(line) < 5:
            return False
        map_chars = set('.PNB□^~T')
        return all(c in map_chars or c == ' ' for c in line.strip())

    def _insert_map_line(self, line: str):
        for ch in line:
            tag = self._char_tag(ch)
            if tag:
                self.insert(tk.END, ch, tag)
            else:
                self.insert(tk.END, ch)

    @staticmethod
    def _char_tag(ch: str) -> Optional[str]:
        if ch == 'P':
            return "player"
        elif ch == 'N':
            return "npc"
        elif ch == 'B':
            return "bounty"
        elif ch == '□':
            return "town"
        elif ch == '^':
            return "mountain"
        elif ch == '~':
            return "water"
        elif ch == 'T':
            return "tree"
        return None


class InfoPanel(tk.Frame):
    """右侧信息面板"""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg="#34495e", width=280, **kwargs)

    def add_section_label(self, text: str, fg: str = "#3498db"):
        lbl = tk.Label(self, text=text, bg="#34495e", fg=fg,
                       font=("Arial", 11, "bold"), anchor=tk.W)
        lbl.pack(fill=tk.X, padx=10, pady=(10, 5))
        return lbl

    def add_separator(self):
        tk.Frame(self, bg="#7f8c8d", height=2).pack(fill=tk.X, padx=10, pady=10)


class ButtonBar(tk.Frame):
    """控制按钮栏"""

    def __init__(self, parent, buttons: list, **kwargs):
        """
        buttons: [(text, command), ...]
        """
        super().__init__(parent, bg="#34495e", **kwargs)
        for text, command in buttons:
            btn = tk.Button(self, text=text, command=command,
                            bg="#3498db", fg="white",
                            font=("Arial", 9), width=8)
            btn.pack(side=tk.LEFT, padx=2)


def show_messagebox(title: str, text: str, kind: str = "info"):
    if kind == "error":
        messagebox.showerror(title, text)
    elif kind == "warning":
        messagebox.showwarning(title, text)
    else:
        messagebox.showinfo(title, text)
