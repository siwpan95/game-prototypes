"""
View 层 —— 拼图游戏主界面

流程：选择图片 → 应用画风（可选）→ 制作拼图 → 打乱 → 用户拼合

画风预览用 pygame-ce 渲染，拼图交互用 tkinter Canvas 拖拽。
"""

from __future__ import annotations

import queue
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import List, Optional, Tuple

# 第三方库
try:
    import pygame as pg
    from PIL import Image, ImageTk
except ImportError as e:
    print(f"导入库失败: {e}")
    print("请确保已安装所需库: pip install pygame-ce Pillow")
    sys.exit(1)

from models import ArtStyle
from viewmodels import ImageViewModel


# ======================================================================
# 拼图交互 Canvas
# ======================================================================
class PuzzleCanvas(tk.Canvas):
    """
    拼图交互 Canvas：
    - 绘制网格背景（正确位置提示）
    - 绘制所有拼图碎片（PIL → PhotoImage）
    - 鼠标拖拽移动碎片，松手时吸附到最近格位
    """
    TILE_PAD_RATIO = 0.015

    def __init__(self, parent, view_model: ImageViewModel, **kwargs):
        super().__init__(parent, **kwargs)
        self.vm = view_model
        self.tile_photos: List[tk.PhotoImage] = []
        self._drag_data = {"tile_id": None, "x": 0, "y": 0}
        self._tile_items: dict = {}

        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<B1-Motion>", self._on_drag)
        self.bind("<ButtonRelease-1>", self._on_release)

    # ------------------------------------------------------------------
    # 布局计算：等比缩放拼图适配 Canvas 大小
    # ------------------------------------------------------------------
    def _get_layout(self):
        """返回缩放后的 (tw, th, ox, oy)，使拼图适配 Canvas 窗口"""
        rows, cols = self.vm.get_puzzle_grid_size()
        raw_tw, raw_th = self.vm.get_puzzle_tile_pixel_size()
        cw = self.winfo_width()
        ch = self.winfo_height()
        total_w = cols * raw_tw
        total_h = rows * raw_th
        margin = 20
        scale = min(
            (cw - margin * 2) / total_w if total_w > 0 else 1,
            (ch - margin * 2) / total_h if total_h > 0 else 1,
            1.0,
        )
        tw = raw_tw * scale
        th = raw_th * scale
        ox = (cw - cols * tw) / 2
        oy = (ch - rows * th) / 2
        return tw, th, ox, oy

    def redraw(self) -> None:
        self.delete("all")
        self.tile_photos.clear()
        self._tile_items.clear()

        tiles = self.vm.get_puzzle_tiles()
        if not tiles:
            w, h = self.winfo_width(), self.winfo_height()
            self.create_text(
                w // 2, h // 2,
                text="请先加载图片并制作拼图",
                font=("", 16), fill="gray",
            )
            return

        rows, cols = self.vm.get_puzzle_grid_size()
        tw, th, ox, oy = self._get_layout()
        cw = self.winfo_width()
        pad = max(1, int(tw * self.TILE_PAD_RATIO))

        # 网格背景
        for r in range(rows):
            for c in range(cols):
                x0 = ox + c * tw
                y0 = oy + r * th
                x1 = x0 + tw
                y1 = y0 + th
                self.create_rectangle(
                    x0, y0, x1, y1,
                    fill="#e8e8e8", outline="#cccccc", width=1,
                )
                self.create_text(
                    x0 + tw // 2, y0 + th // 2,
                    text=str(r * cols + c),
                    font=("", 10), fill="#dddddd",
                )

        # 拼图碎片
        for tile in tiles:
            correct_r = tile.id // cols
            correct_c = tile.id % cols
            is_home = (tile.row == correct_r and tile.col == correct_c)

            x0 = ox + tile.col * tw + pad
            y0 = oy + tile.row * th + pad
            pw = max(1, int(tw - pad * 2))
            ph = max(1, int(th - pad * 2))

            # 缩放碎片图像
            display_img = tile.image.copy()
            display_img = display_img.resize(
                (pw, ph), Image.Resampling.LANCZOS,
            )
            photo = ImageTk.PhotoImage(display_img)
            self.tile_photos.append(photo)

            border_color = "#00aa00" if is_home else "#444444"
            rect = self.create_rectangle(
                x0, y0, x0 + pw, y0 + ph,
                outline=border_color, width=2,
            )
            img = self.create_image(x0, y0, image=photo, anchor=tk.NW)
            self.tag_raise(img, rect)
            self._tile_items[tile.id] = (img, rect)

        # 进度文字
        completed, total = self.vm.get_puzzle_completed_count()
        self.create_text(
            cw - 10, 10,
            text=f"进度: {completed}/{total}",
            anchor=tk.NE, font=("", 12), fill="#333333",
        )

    # ------------------------------------------------------------------
    # 鼠标交互
    # ------------------------------------------------------------------
    def _hit_test(self, x: int, y: int) -> Optional[int]:
        """返回鼠标位置所在的格位对应的 tile_id"""
        rows, cols = self.vm.get_puzzle_grid_size()
        tw, th, ox, oy = self._get_layout()
        col = int((x - ox) / tw) if tw > 0 else 0
        row = int((y - oy) / th) if th > 0 else 0
        if 0 <= row < rows and 0 <= col < cols:
            for tile in self.vm.get_puzzle_tiles():
                if tile.row == row and tile.col == col:
                    return tile.id
        return None

    def _on_press(self, event):
        tid = self._hit_test(event.x, event.y)
        if tid is not None:
            self._drag_data["tile_id"] = tid
            self._drag_data["x"] = event.x
            self._drag_data["y"] = event.y
            items = self._tile_items.get(tid)
            if items:
                self.tag_raise(items[0])
                self.tag_raise(items[1])

    def _on_drag(self, event):
        tid = self._drag_data["tile_id"]
        if tid is None:
            return
        dx = event.x - self._drag_data["x"]
        dy = event.y - self._drag_data["y"]
        self._drag_data["x"] = event.x
        self._drag_data["y"] = event.y
        items = self._tile_items.get(tid)
        if items:
            self.move(items[0], dx, dy)
            self.move(items[1], dx, dy)

    def _on_release(self, event):
        tid = self._drag_data["tile_id"]
        if tid is None:
            return
        rows, cols = self.vm.get_puzzle_grid_size()
        tw, th, ox, oy = self._get_layout()
        tcol = max(0, min(cols - 1, round((event.x - ox) / tw))) if tw > 0 else 0
        trow = max(0, min(rows - 1, round((event.y - oy) / th))) if th > 0 else 0

        ok, msg = self.vm.move_tile_command(tid, trow, tcol)
        self.redraw()
        if self.vm.is_puzzle_completed():
            messagebox.showinfo("恭喜！", "拼图完成！所有碎片已归位。")
        self._drag_data = {"tile_id": None, "x": 0, "y": 0}


# ======================================================================
# 主视图
# ======================================================================
class ImageView(tk.Tk):
    """
    主视图 —— 拼图游戏完整流程：
    1. 加载图片
    2. 画风处理（可选，可切换风格 + 预览）
    3. 制作拼图（设置行列数）
    4. 打乱并开始拼图
    """

    def __init__(self, view_model: ImageViewModel) -> None:
        super().__init__()
        self.vm = view_model

        self.title("拼图游戏 - 艺术风格转换器")
        self.geometry("1000x720")

        self._setup_widgets()
        self._setup_pygame()
        self._bind_events()

        self.after(100, self._process_messages)

    # ==================================================================
    # UI 搭建
    # ==================================================================
    def _setup_widgets(self) -> None:
        # ---- 顶部控制栏 ----
        top = ttk.Frame(self, padding="8")
        top.pack(side=tk.TOP, fill=tk.X)

        ttk.Button(top, text="① 选择图片", command=self._on_load).pack(
            side=tk.LEFT, padx=3
        )

        ttk.Separator(top, orient=tk.VERTICAL).pack(
            side=tk.LEFT, padx=8, fill=tk.Y
        )

        # 画风处理区
        ttk.Label(top, text="② 画风:").pack(side=tk.LEFT, padx=(0, 3))
        self.style_var = tk.StringVar(value=ArtStyle.ORIGINAL.value)
        self.style_combo = ttk.Combobox(
            top, textvariable=self.style_var,
            state="readonly", width=20,
        )
        self.style_combo["values"] = [s.value for s in ArtStyle]
        self.style_combo.pack(side=tk.LEFT, padx=3)
        self.style_combo.bind("<<ComboboxSelected>>", self._on_style_selected)

        ttk.Button(top, text="应用画风", command=self._on_apply_style).pack(
            side=tk.LEFT, padx=3
        )

        ttk.Separator(top, orient=tk.VERTICAL).pack(
            side=tk.LEFT, padx=8, fill=tk.Y
        )

        # 拼图制作区
        ttk.Label(top, text="③ 难度:").pack(side=tk.LEFT, padx=(0, 3))
        self._difficulty_presets = {
            "简单 (2×2)": (2, 2),
            "普通 (3×3)": (3, 3),
            "困难 (4×4)": (4, 4),
            "专家 (5×5)": (5, 5),
            "地狱 (6×6)": (6, 6),
            "自定义":     None,
        }
        self.diff_var = tk.StringVar(value="普通 (3×3)")
        self.diff_combo = ttk.Combobox(
            top, textvariable=self.diff_var,
            state="readonly", width=14,
        )
        self.diff_combo["values"] = list(self._difficulty_presets.keys())
        self.diff_combo.pack(side=tk.LEFT, padx=3)
        self.diff_combo.bind("<<ComboboxSelected>>", self._on_difficulty_changed)

        ttk.Label(top, text="行列:").pack(side=tk.LEFT, padx=(8, 3))
        self.spin_rows = tk.Spinbox(
            top, from_=2, to=10, width=4,
            command=self._on_spin_edited,
        )
        self.spin_rows.delete(0, "end")
        self.spin_rows.insert(0, "3")
        self.spin_rows.pack(side=tk.LEFT, padx=2)

        ttk.Label(top, text="x").pack(side=tk.LEFT)
        self.spin_cols = tk.Spinbox(
            top, from_=2, to=10, width=4,
            command=self._on_spin_edited,
        )
        self.spin_cols.delete(0, "end")
        self.spin_cols.insert(0, "3")
        self.spin_cols.pack(side=tk.LEFT, padx=2)

        ttk.Button(top, text="制作拼图", command=self._on_create_puzzle).pack(
            side=tk.LEFT, padx=(10, 3)
        )
        ttk.Button(top, text="打乱", command=self._on_shuffle).pack(
            side=tk.LEFT, padx=3
        )

        # 右侧状态
        self.info_label = ttk.Label(top, text="请先选择一张图片")
        self.info_label.pack(side=tk.RIGHT, padx=10)

        # ---- 主显示区 ----
        self.display_frame = ttk.Frame(self)
        self.display_frame.pack(
            side=tk.TOP, fill=tk.BOTH, expand=True, padx=10, pady=(4, 10)
        )

        # pygame 画布（画风预览 + 原图/效果图展示）
        self.pygame_canvas = tk.Canvas(
            self.display_frame,
            bg="gray",
            highlightthickness=1, highlightbackground="black",
        )
        # PuzzleCanvas（拼图交互，初始隐藏）
        self.puzzle_canvas = PuzzleCanvas(
            self.display_frame,
            self.vm,
            bg="lightgray",
            highlightthickness=1, highlightbackground="black",
        )

        # 默认显示 pygame 画布
        self.pygame_canvas.pack(fill=tk.BOTH, expand=True)

        # ---- 底部状态栏 ----
        bottom = ttk.Frame(self, relief=tk.SUNKEN, padding="5")
        bottom.pack(side=tk.BOTTOM, fill=tk.X)
        self.status_label = ttk.Label(
            bottom, text="流程：选择图片 → 应用画风（可选）→ 制作拼图 → 打乱 → 开始拼图"
        )
        self.status_label.pack(side=tk.LEFT)

    # ==================================================================
    # pygame 初始化
    # ==================================================================
    def _setup_pygame(self) -> None:
        pg.init()
        self.pg_surface = pg.Surface((800, 500))
        self.pg_display_initialized = False
        self.current_display_size = (800, 500)

    def _init_pygame_display(self, width: int, height: int) -> None:
        self.pg_surface = pg.Surface((width, height))
        self.current_display_size = (width, height)
        self.pg_display_initialized = True

    # ==================================================================
    # 事件绑定
    # ==================================================================
    def _bind_events(self) -> None:
        self.protocol("WM_DELETE_WINDOW", self._on_closing)
        self.pygame_canvas.bind("<Configure>", self._on_pygame_resize)
        self.puzzle_canvas.bind("<Configure>", lambda e: self._redraw_puzzle())

    # ==================================================================
    # 画风模式：pygame 渲染
    # ==================================================================
    def _render_to_pygame(self) -> None:
        pil_img = self.vm.get_current_image_for_display()
        if pil_img and self.pg_display_initialized:
            cw = self.pygame_canvas.winfo_width()
            ch = self.pygame_canvas.winfo_height()
            if cw > 1 and ch > 1:
                ratio = pil_img.width / pil_img.height
                canvas_ratio = cw / ch
                if ratio > canvas_ratio:
                    dw = cw
                    dh = int(cw / ratio)
                else:
                    dh = ch
                    dw = int(ch * ratio)
                if dw != self.current_display_size[0] or dh != self.current_display_size[1]:
                    self._init_pygame_display(dw, dh)
                resized = pil_img.resize((dw, dh), Image.Resampling.LANCZOS)
                pg_img = pg.image.fromstring(
                    resized.tobytes(), resized.size, resized.mode
                )
                self.pg_surface.fill((240, 240, 240))
                x_off = (self.current_display_size[0] - dw) // 2
                y_off = (self.current_display_size[1] - dh) // 2
                self.pg_surface.blit(pg_img, (x_off, y_off))
                pg_bytes = pg.image.tostring(self.pg_surface, "RGB")
                w, h = self.current_display_size
                ppm = f"P6\n{w} {h}\n255\n".encode("ascii") + pg_bytes
                pg_img_tk = tk.PhotoImage(data=ppm)
                self.pygame_canvas.delete("all")
                self.pygame_canvas.create_image(
                    cw // 2, ch // 2,
                    image=pg_img_tk, anchor=tk.CENTER,
                )
                self.pygame_canvas.image = pg_img_tk
        elif self.pg_display_initialized:
            self.pg_surface.fill((200, 200, 200))
            font = pg.font.SysFont(None, 36)
            text = font.render("请加载一张图片", True, (100, 100, 100))
            rect = text.get_rect(
                center=(self.current_display_size[0] // 2,
                        self.current_display_size[1] // 2)
            )
            self.pg_surface.blit(text, rect)
            pg_bytes = pg.image.tostring(self.pg_surface, "RGB")
            w, h = self.current_display_size
            ppm = f"P6\n{w} {h}\n255\n".encode("ascii") + pg_bytes
            pg_img_tk = tk.PhotoImage(data=ppm)
            self.pygame_canvas.delete("all")
            self.pygame_canvas.create_image(
                self.pygame_canvas.winfo_width() // 2,
                self.pygame_canvas.winfo_height() // 2,
                image=pg_img_tk, anchor=tk.CENTER,
            )
            self.pygame_canvas.image = pg_img_tk

    def _on_pygame_resize(self, event: tk.Event) -> None:
        if event.width > 10 and event.height > 10:
            if hasattr(self, "_resize_job"):
                self.after_cancel(self._resize_job)
            self._resize_job = self.after(200, self._render_to_pygame)

    # ==================================================================
    # 拼图模式：Canvas 重绘
    # ==================================================================
    def _redraw_puzzle(self) -> None:
        self.puzzle_canvas.redraw()

    def _switch_to_puzzle_view(self) -> None:
        """切换到拼图交互视图"""
        self.pygame_canvas.pack_forget()
        self.puzzle_canvas.pack(fill=tk.BOTH, expand=True)
        self._redraw_puzzle()

    def _switch_to_art_view(self) -> None:
        """切换回画风预览视图"""
        self.puzzle_canvas.pack_forget()
        self.pygame_canvas.pack(fill=tk.BOTH, expand=True)
        self._render_to_pygame()

    # ==================================================================
    # 事件处理
    # ==================================================================
    def _on_difficulty_changed(self, _event: object) -> None:
        """难度下拉框变更 → 自动设置行列数"""
        preset = self._difficulty_presets.get(self.diff_var.get())
        if preset is None:
            return  # 自定义：保持当前值
        rows, cols = preset
        self.spin_rows.delete(0, "end")
        self.spin_rows.insert(0, str(rows))
        self.spin_cols.delete(0, "end")
        self.spin_cols.insert(0, str(cols))

    def _on_spin_edited(self) -> None:
        """手动编辑行列数 → 切换为自定义"""
        if self.diff_var.get() != "自定义":
            self.diff_var.set("自定义")

    def _on_load(self) -> None:
        file_path = filedialog.askopenfilename(
            title="选择图片",
            filetypes=[
                ("图片文件", "*.jpg *.jpeg *.png *.bmp *.gif"),
                ("所有文件", "*.*"),
            ],
        )
        if not file_path:
            return
        success, msg = self.vm.load_image_command(file_path)
        self.status_label.config(text=msg)
        if success:
            cw = self.pygame_canvas.winfo_width()
            ch = self.pygame_canvas.winfo_height()
            if cw < 10:
                cw, ch = 800, 500
            self._init_pygame_display(cw, ch)
            self._render_to_pygame()
            self.info_label.config(text=self.vm.get_image_info())
            self.style_var.set(ArtStyle.ORIGINAL.value)
            # 如果当前在拼图视图，切换回画风视图
            self._switch_to_art_view()

    def _on_style_selected(self, _event: object) -> None:
        pass

    def _on_apply_style(self) -> None:
        if not self.vm.has_image():
            messagebox.showwarning("提示", "请先选择一张图片")
            return
        try:
            selected = next(
                s for s in ArtStyle if s.value == self.style_var.get()
            )
        except StopIteration:
            messagebox.showerror("错误", "无效的风格选择")
            return
        self.vm.apply_style_command(selected)
        self.status_label.config(text=f"正在应用 {selected.value} 风格...")

    def _on_create_puzzle(self) -> None:
        if not self.vm.has_image():
            messagebox.showwarning("提示", "请先选择一张图片")
            return
        try:
            rows = int(self.spin_rows.get())
            cols = int(self.spin_cols.get())
        except ValueError:
            messagebox.showerror("错误", "行/列数必须为整数")
            return
        ok, msg = self.vm.create_puzzle_command(rows, cols)
        if ok:
            self.status_label.config(text=msg)
            # 自动切换到拼图视图
            self._switch_to_puzzle_view()
        else:
            messagebox.showerror("错误", msg)

    def _on_shuffle(self) -> None:
        ok, msg = self.vm.shuffle_puzzle_command()
        if ok:
            self.status_label.config(text=msg)
            # 确保在拼图视图
            self._switch_to_puzzle_view()
        else:
            messagebox.showwarning("提示", msg)

    # ==================================================================
    # 消息队列（画风应用完成回调）
    # ==================================================================
    def _process_messages(self) -> None:
        try:
            while True:
                msg_type, data = self.vm.message_queue.get_nowait()
                if msg_type == "style_applied":
                    self.status_label.config(text=f"风格应用完成: {data.value}")
                    self._render_to_pygame()
                    self.info_label.config(text=self.vm.get_image_info())
        except queue.Empty:
            pass
        self.after(100, self._process_messages)

    # ==================================================================
    # 生命周期
    # ==================================================================
    def _on_closing(self) -> None:
        pg.quit()
        self.destroy()

    def run(self) -> None:
        self.mainloop()
