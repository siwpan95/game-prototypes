"""
字体模块 — 加载本地思源黑体 OTF 字体
通过 ctypes AddFontResourceExW 注册到系统，供 tkinter 使用。
"""

import os
import ctypes
import tkinter.font as tkfont
import tkinter as tk


_FONT_FILE = os.path.join(os.path.dirname(__file__), "SourceHanSansSC-Heavy-2.otf")


def _register_otf(path: str) -> bool:
    if not os.path.exists(path):
        return False
    try:
        gdi32 = ctypes.WinDLL("gdi32")
        num = gdi32.AddFontResourceExW(path, 0x10, 0)
        if num > 0:
            user32 = ctypes.WinDLL("user32")
            user32.SendMessageW(0xFFFF, 0x001D, 0, 0)
            return True
    except Exception:
        pass
    return False


_FONT_LOADED = _register_otf(_FONT_FILE)


def _detect_family() -> str:
    root = tk.Tk()
    root.withdraw()
    families = set(tkfont.families(root=root))
    root.destroy()

    for c in ["思源黑体 Heavy", "思源黑体", "Source Han Sans SC Heavy",
              "Noto Sans SC Medium", "Noto Sans SC"]:
        if c in families:
            return c
    return "TkDefaultFont"


_FAMILY = _detect_family()
if _FONT_LOADED:
    print(f"[Font] 思源黑体 Heavy → {_FAMILY}")
else:
    print(f"[Font] 未找到 OTF，降级: {_FAMILY}")


def get_font(size: int = 10, bold: bool = False) -> tuple:
    return (_FAMILY, size, "bold" if bold else "normal")
