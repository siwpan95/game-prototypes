"""
example_local_font.py — 本地字体加载示例

演示 allin_engine 的「从本地加载字体」能力：
  - 自动发现包内 fonts/ 目录的打包字体
  - pygame 端：load_local_font 渲染中文文字并导出 PNG
  - tkinter 端：load_local_tk_font 用于 GUI 标题/按钮

运行：
    cd D:/allin && python allin_engine/example_local_font.py

说明：
  - 无需显示器即可体验字体加载逻辑（pygame 渲染部分在无头环境仅导出 PNG）
  - tkinter 示例在有图形界面的机器上才会弹出窗口
"""

from __future__ import annotations

import os
import sys
import tempfile

# 确保项目根目录在路径中
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from allin_engine.utils.font import (
    discover_local_fonts,
    get_default_local_font_name,
    load_local_font,
    load_local_tk_font,
    load_cjk_font,
)


def demo_discovery() -> None:
    print("=" * 60)
    print("  1. 本地字体发现")
    print("=" * 60)
    fonts = discover_local_fonts()
    if not fonts:
        print("  （未找到本地字体，请将 .ttf/.otf/.ttc 放入 allin_engine/fonts/）")
        return
    for alias, path in fonts:
        print(f"  - 别名: {alias}")
        print(f"    路径: {path}")
    print(f"  默认本地字体别名: {get_default_local_font_name()}")
    print()


def demo_pygame() -> None:
    print("=" * 60)
    print("  2. Pygame 本地字体渲染")
    print("=" * 60)
    try:
        import pygame
    except ImportError:
        print("  pygame 未安装，跳过（pip install pygame-ce）")
        return

    if not fonts_exist():
        print("  无本地字体，跳过渲染演示。")
        return

    pygame.init()
    name = get_default_local_font_name()

    # 加载打包手写体（默认本地字体）
    big = load_local_font(64, name=name, bold=True)
    mid = load_local_font(32, name=name)
    # 兜底系统字体（正文可读性）
    sys_font = load_cjk_font(20)

    if big is None:
        print("  本地字体加载失败。")
        return

    lines = [
        (big, "饱餐谋·文字冒险", (230, 216, 200)),
        (mid, "从本地加载字体 · Local Font", (212, 175, 55)),
        (sys_font, "正文使用系统 CJK 字体保证可读性", (180, 175, 150)),
    ]

    pad = 24
    widths = []
    heights = []
    for font, text, _ in lines:
        s = font.render(text, True, (255, 255, 255))
        widths.append(s.get_width())
        heights.append(s.get_height())
    w = max(widths) + pad * 2
    h = sum(heights) + pad * (len(lines) + 1)

    surf = pygame.Surface((w, h))
    surf.fill((20, 20, 34))

    y = pad
    for font, text, color in lines:
        s = font.render(text, True, color)
        surf.blit(s, (pad, y))
        y += s.get_height() + pad

    out = os.path.join(tempfile.gettempdir(), "allin_local_font_demo.png")
    try:
        pygame.image.save(surf, out)
        print(f"  已导出演示图: {out}")
    except Exception as e:
        print(f"  导出 PNG 失败（无显示环境常见）: {e}")
    pygame.quit()
    print()


def demo_tkinter() -> None:
    print("=" * 60)
    print("  3. Tkinter 本地字体")
    print("=" * 60)
    try:
        import tkinter as tk  # noqa: F401
    except ImportError:
        print("  tkinter 不可用，跳过 GUI 演示。")
        return

    if not fonts_exist():
        print("  无本地字体，跳过 GUI 演示。")
        return

    import tkinter as tk
    import tkinter.font as tkfont

    root = tk.Tk()
    root.title("本地字体演示")
    root.geometry("480x200")

    name = get_default_local_font_name()
    # 标题用手写体（本地字体）
    title_font = load_local_tk_font(28, name=name, bold=True)
    # 正文用系统字体
    body_font = tkfont.Font(family="Microsoft YaHei", size=12)

    tk.Label(root, text="饱餐谋·文字冒险", font=title_font or ("Arial", 28)).pack(pady=20)
    tk.Label(root, text="正文保持系统字体，标题用手写体（本地加载）", font=body_font).pack()

    print("  已创建 Tk 窗口（关闭窗口以结束示例）。")
    root.mainloop()


def fonts_exist() -> bool:
    try:
        return len(discover_local_fonts()) > 0
    except Exception:
        return False


def main() -> None:
    print()
    print("  allin_engine — 本地字体加载示例")
    print()
    demo_discovery()
    demo_pygame()
    demo_tkinter()
    print("  完成。")


if __name__ == "__main__":
    main()
