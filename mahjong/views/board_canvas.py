"""棋盘 Canvas 视图。

职责:
  - 将 (layer, row, col) 映射到屏幕坐标 (交叉堆叠: 每层向右下偏移 tile/2)
  - 绘制全部牌 (底层先画，高层覆盖)
  - 点击反算 -> vm.select(pos)
  - 选中高亮 (金框) / 提示高亮 (蓝框) / 消除动画 (闪光连线)
  - 监听 ViewModel 事件并刷新
"""
from __future__ import annotations

import tkinter as tk
import tkinter.ttk as ttk
from typing import List, Optional

from models.board import Pos
from models.game_state import GameMode
from services.matcher import link_path
from viewmodel.game_viewmodel import GameViewModel
from views.tile_renderer import TileRenderer


class BoardCanvas:
    def __init__(self, parent: tk.Widget, vm: GameViewModel, renderer) -> None:
        self.vm = vm
        # 立体牌渲染器 (上海麻将分层堆叠用)
        self._renderer_solid = renderer
        # 连连看专用扁平渲染器: 无侧面厚度/投影 + 更小尺寸, 让整盘不需滚动即可完整显示
        self._renderer_flat = TileRenderer(tile_size=44, thickness=0, shadow=0)
        self.margin = 18
        # 依据当前模式选择渲染器并计算网格参数
        self._apply_mode_renderer()

        # 滚动容器 (平面布局可能超出可视区)
        self.container = ttk.Frame(parent)
        self.canvas = tk.Canvas(
            self.container, bg="#0f1f05", highlightthickness=0,
            bd=3, relief=tk.SUNKEN,
        )
        vsb = ttk.Scrollbar(self.container, orient="vertical", command=self.canvas.yview)
        hsb = ttk.Scrollbar(self.container, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.canvas.grid(row=0, column=0, sticky="nw")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        self.container.grid_rowconfigure(0, weight=1)
        self.container.grid_columnconfigure(0, weight=1)

        self.canvas.bind("<Button-1>", self._on_click)
        self.canvas.bind("<Button-3>", self._on_right_click)

        self._select_item: Optional[int] = None
        self._hint_items: List[int] = []
        self._anim_items: List[int] = []
        self._reject_items: List[int] = []

        vm.add_listener(self._on_event)
        self._recompute_size()
        self._draw()

    # ---- 模式切换: 选定渲染器并刷新网格参数 ----------------------
    def _apply_mode_renderer(self) -> None:
        """连连看用扁平小牌渲染器, 上海麻将用立体牌渲染器。"""
        self.flat = (self.vm.state.mode == GameMode.LINK)
        self.r = self._renderer_flat if self.flat else self._renderer_solid
        self.sz = self.r.sz
        # 单张牌图像含侧面厚度与投影 (扁平渲染器均为 0)，命中/绘制需用到
        self.th = self.r.th
        self.sh = self.r.sh
        # 交叉堆叠层偏移: 每层向右下偏移半个牌宽 (上层压在4张下层中心)
        self.layer_dx = self.sz // 2
        self.layer_dy = self.sz // 2
        # 平面布局 (连连看): 单层网格，格距 = 牌宽(+厚度+投影) + 间隙
        self.step = self.sz + self.th + self.sh + 4

    # ---- 坐标变换 ------------------------------------------------
    def _pos_to_xy(self, pos: Pos):
        l, r, c = pos
        if self.flat:
            # 平面布局: 单层网格, 无层偏移, 按格距排布。
            # 四周预留 +step 外圈, 让连连看"绕到棋盘外"的路径点也落在可视区内。
            return (self.margin + self.step + c * self.step,
                    self.margin + self.step + r * self.step)
        x = self.margin + c * self.sz + l * self.layer_dx
        y = self.margin + r * self.sz + l * self.layer_dy
        return x, y

    def _flat_xy(self, r: int, c: int):
        """平面模式下网格坐标 (row,col, 可为 -1/R/C 等绕外点) -> 屏幕左上角。"""
        return (self.margin + self.step + c * self.step,
                self.margin + self.step + r * self.step)

    def _recompute_size(self) -> None:
        b = self.vm.state.board
        # 依当前模式切换渲染器 (影响 sz/th/sh/step)
        self._apply_mode_renderer()
        if self.flat:
            # 平面布局: 列×格距 / 行×格距 (四周 +step 外圈容纳绕外路径)
            cw = self.margin * 2 + self.step * 2 + b.cols * self.step
            ch = self.margin * 2 + self.step * 2 + b.rows * self.step
        else:
            # 分层布局: 正面网格 + 层偏移 + 最上层牌的侧面厚度 + 投影
            cw = b.cols * self.sz + b.max_layer * self.layer_dx \
                + self.margin * 2 + self.th + self.sh
            ch = b.rows * self.sz + b.max_layer * self.layer_dy \
                + self.margin * 2 + self.th + self.sh
        # 可视区域限制, 超出部分滚动查看
        self.canvas.config(width=min(cw, 1160), height=min(ch, 720))
        self.canvas.config(scrollregion=(0, 0, cw, ch))

    # ---- 绘制 ----------------------------------------------------
    def _draw(self) -> None:
        self.canvas.delete("all")
        self._select_item = None
        self._hint_items = []
        self._anim_items = []
        self._reject_items = []
        b = self.vm.state.board
        # 升序 (底层先画，高层在上覆盖)
        positions = sorted(b.occupied_positions(), key=lambda p: (p[0], p[1], p[2]))
        for pos in positions:
            tile = b.get(pos)
            if tile is None:
                continue
            x, y = self._pos_to_xy(pos)
            img = self.r.get_image(tile)
            self.canvas.create_image(x, y, anchor=tk.NW, image=img)
        if self.vm.state.selected is not None:
            self._draw_select(self.vm.state.selected)

    def _draw_select(self, pos: Pos) -> None:
        x, y = self._pos_to_xy(pos)
        # 高亮包住整块 (正面 + 侧面厚度)
        self._select_item = self.canvas.create_rectangle(
            x - 3, y - 3, x + self.sz + self.th + 2, y + self.sz + self.th + 2,
            outline="#ffd700", width=3, tags="sel",
        )

    # ---- 点击 ----------------------------------------------------
    def _on_click(self, ev) -> None:
        pos = self._hit_test(ev.x, ev.y)
        if pos is not None:
            self.vm.select(pos)

    def _on_right_click(self, ev) -> None:
        # 右键取消选中
        if self.vm.state.selected is not None:
            self.vm.select(self.vm.state.selected)  # 再点一次=取消

    def _hit_test(self, mx: int, my: int) -> Optional[Pos]:
        # occupied_positions 已按 layer 降序，高层优先命中
        for pos in self.vm.state.board.occupied_positions():
            x, y = self._pos_to_xy(pos)
            if x <= mx <= x + self.sz and y <= my <= y + self.sz:
                return pos
        return None

    # ---- 事件处理 ------------------------------------------------
    def _on_event(self, ev) -> None:
        t = ev.type
        if t == "new_game":
            self._recompute_size()
            self._draw()
        elif t in ("select", "deselect"):
            self._draw()
        elif t == "match":
            self._animate_match(ev.data["pos_a"], ev.data["pos_b"])
        elif t in ("shuffle", "undo"):
            self._draw()
        elif t == "hint":
            self._show_hint(ev.data["pair"])
        elif t == "reject":
            self._flash_reject(ev.data.get("pos"), ev.data.get("reason", "无法选择"))
        # win/lose/deadlock 由 main 弹窗处理

    # ---- 动画 ----------------------------------------------------
    def _animate_match(self, pos_a: Pos, pos_b: Pos) -> None:
        if self._select_item is not None:
            self.canvas.delete(self._select_item)
            self._select_item = None
        x1, y1 = self._pos_to_xy(pos_a)
        x2, y2 = self._pos_to_xy(pos_b)
        cx1, cy1 = x1 + self.sz / 2, y1 + self.sz / 2
        cx2, cy2 = x2 + self.sz / 2, y2 + self.sz / 2

        from models.game_state import GameMode
        if self.vm.state.mode == GameMode.LINK:
            # 连连看: 画真实 ≤2 拐弯折线 (含绕到棋盘外的路径点)
            path = link_path(self.vm.state.board, pos_a, pos_b)
            if path:
                pts = []
                for (r, c) in path:
                    gx, gy = self._flat_xy(r, c)
                    pts.extend((gx + self.sz / 2, gy + self.sz / 2))
                line = self.canvas.create_line(
                    *pts, fill="#ffe066", width=4, dash=(5, 3), joinstyle=tk.ROUND,
                )
            else:
                line = self.canvas.create_line(
                    cx1, cy1, cx2, cy2, fill="#ffe066", width=4, dash=(5, 3),
                )
        else:
            # 上海麻将: 自由牌配对, 画直线连线示意
            line = self.canvas.create_line(
                cx1, cy1, cx2, cy2, fill="#ffe066", width=4, dash=(5, 3),
            )
        # 两端闪光圆
        o1 = self.canvas.create_oval(cx1 - 10, cy1 - 10, cx1 + 10, cy1 + 10,
                                      outline="#ffd700", width=3)
        o2 = self.canvas.create_oval(cx2 - 10, cy2 - 10, cx2 + 10, cy2 + 10,
                                      outline="#ffd700", width=3)
        self._anim_items.extend([line, o1, o2])
        # 400ms 后清除动画并全量重绘 (此时牌已从 board 移除)
        self.canvas.after(380, self._finish_match_anim)

    def _finish_match_anim(self) -> None:
        for it in self._anim_items:
            self.canvas.delete(it)
        self._anim_items = []
        self._draw()

    def _show_hint(self, pair) -> None:
        self._clear_hint()
        for pos in pair:
            x, y = self._pos_to_xy(pos)
            # 高亮包住整块 (正面 + 侧面厚度)
            item = self.canvas.create_rectangle(
                x - 3, y - 3, x + self.sz + self.th + 2, y + self.sz + self.th + 2,
                outline="#00bfff", width=3,
            )
            self._hint_items.append(item)
        # 连连看: 额外画出连通路径, 让"提示"一目了然 (≤2 拐弯 + 绕外)
        if self.vm.state.mode == GameMode.LINK:
            path = link_path(self.vm.state.board, pair[0], pair[1])
            if path:
                pts = []
                for (r, c) in path:
                    gx, gy = self._flat_xy(r, c)
                    pts.extend((gx + self.sz / 2, gy + self.sz / 2))
                self._hint_items.append(self.canvas.create_line(
                    *pts, fill="#00bfff", width=3, dash=(4, 3), joinstyle=tk.ROUND,
                ))
        self.canvas.after(2200, self._clear_hint)

    def _clear_hint(self) -> None:
        for it in self._hint_items:
            self.canvas.delete(it)
        self._hint_items = []

    # ---- 拒绝反馈 (点击了不可选的牌) ------------------------------
    def _flash_reject(self, pos, reason: str) -> None:
        if pos is None:
            return
        self._clear_reject()
        x, y = self._pos_to_xy(pos)
        x0, y0 = x - 4, y - 4
        x1, y1 = x + self.sz + self.th + 3, y + self.sz + self.th + 3
        # 红色抖动框
        rect = self.canvas.create_rectangle(
            x0, y0, x1, y1, outline="#ff3b30", width=3,
        )
        self._reject_items.append(rect)
        # 原因文字 (悬浮在牌上方)
        txt = self.canvas.create_text(
            x + self.sz / 2, y - 6, text=reason,
            fill="#ff3b30", font=("SimHei", 11, "bold"), anchor=tk.S,
        )
        self._reject_items.append(txt)
        # 左右抖动几下，直观表达"被夹住"
        self._shake_reject(rect, x0, y0, x1, y1, idx=0)
        self.canvas.after(800, self._clear_reject)

    def _shake_reject(self, rect, x0, y0, x1, y1, idx: int) -> None:
        if idx >= 6:
            self.canvas.coords(rect, x0, y0, x1, y1)
            return
        dx = 5 if idx % 2 == 0 else -5
        self.canvas.coords(rect, x0 + dx, y0, x1 + dx, y1)
        self.canvas.after(55, self._shake_reject, rect, x0, y0, x1, y1, idx + 1)

    def _clear_reject(self) -> None:
        for it in self._reject_items:
            self.canvas.delete(it)
        self._reject_items = []
