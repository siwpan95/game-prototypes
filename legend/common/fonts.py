"""字体工具 — 优先返回中文字体"""
import tkinter as tk
from tkinter import font


def cn_font(size: int = 12) -> tuple[str, int]:
    """返回 (字体名, size)，优先 Microsoft YaHei > SimHei > PingFang SC"""
    for f in ("Microsoft YaHei", "SimHei", "PingFang SC"):
        if f in font.families():
            return (f, size)
    return ("Arial", size)
