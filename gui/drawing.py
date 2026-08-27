"""gui/drawing.py — Canvas 自绘辅助：圆角矩形 / 弧形仪表 / 排序键 / 文本换行。"""
import tkinter as tk
from typing import Optional
from pathways_data import PATHWAY_GROUPS, get_pathway

def pathway_sort_key(pk: str) -> tuple:
    """途径排序键：按权柄体系分组"""
    order = list(PATHWAY_GROUPS.keys())
    p = get_pathway(pk)
    gk = p["group"]
    return (order.index(gk) if gk in order else 99, pk)


def draw_rounded_rect(canvas: tk.Canvas, x1, y1, x2, y2, r=10, **kwargs):
    """Canvas 圆角矩形"""
    pts = [
        x1+r, y1,  x2-r, y1,  x2, y1,  x2, y1+r,
        x2, y2-r,  x2, y2,  x2-r, y2,  x1+r, y2,
        x1, y2,  x1, y2-r,  x1, y1+r,  x1, y1,
    ]
    return canvas.create_polygon(pts, smooth=True, **kwargs)


def draw_gauge(canvas, cx, cy, r, angle_start, angle_end, color, width=8, bg="#1a1a35"):
    """Canvas 弧形进度条"""
    # 背景弧
    canvas.create_arc(cx-r, cy-r, cx+r, cy+r,
                      start=angle_start, extent=angle_end-angle_start,
                      style="arc", outline=bg, width=width)
    # 进度弧（按 extent 分段）
    return canvas.create_arc(cx-r, cy-r, cx+r, cy+r,
                             start=angle_start, extent=angle_end-angle_start,
                             style="arc", outline=color, width=width)


def group_key_of(pathway_key: str) -> Optional[str]:
    """返回某途径所属的权柄体系（途径组）key"""
    for gk, gd in PATHWAY_GROUPS.items():
        if pathway_key in gd["pathways"]:
            return gk
    return None

def _wrap_text(text: str, max_len: int) -> list[str]:
    """简单文本换行"""
    lines = []
    current = ""
    for ch in text:
        current += ch
        if len(current) >= max_len:
            lines.append(current)
            current = ""
    if current:
        lines.append(current)
    return lines or [text]


# ═══════════════════════════════════════════════════════════
# 入口
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    app = LordOfMysteriesGUI()
    app.run()

