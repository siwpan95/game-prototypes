"""差分渲染器（P0-16 / P0-17 / P0-22，子任务 4.5）。

🔴 禁止 `from __future__ import annotations`（E6）。
🔴 **绝不每帧 `delete("all")`**：那会让 tkinter 每帧重建上百个 item，
   是这类桌宠最典型的 CPU 杀手。这里用 `item_map` 复用 item，
   只调 `coords()` / `itemconfig()`（ARCHITECTURE §7.3）。

item_map 的键是 `(entity_key, part_index)`，值是 canvas item id。
每帧结束后，本帧没被 touch 到的 key 会被删除并从 map 移除。
"""

from pyapp import decor_painter
from pyapp.fish_painter import FishPainter
from pyapp.theme import mix

_BG_TAG = "bg"


class CanvasRenderer(object):
    """把 `FishTankGame` 的只读快照差分地画到 Canvas 上。"""

    def __init__(self, canvas, theme, game):
        """:param canvas: tk.Canvas
        :param theme: :class:`pyapp.theme.Theme`
        :param game: :class:`fishtank.game.FishTankGame`
        """
        self.canvas = canvas
        self.theme = theme
        self.game = game
        self.fish = FishPainter(canvas, theme,
                                stage_scale=game.bal.stage_scale_table()
                                if game.bal else None)
        self.decor = decor_painter.DecorPainter(canvas, theme)

        self._items = {}
        """{(key, part): item_id}"""
        self._alive = set()
        self._bg_items = []
        self._decor_sig = None
        self._size = (0, 0)
        self.base_len_ratio = 0.16
        """基准体长占画布宽的比例（纯表现，越大鱼越大）。"""
        self.frames = 0
        self.reused = 0
        self.created = 0
        """诊断计数：`reused / (reused + created)` 越接近 1 说明差分越有效。"""

    # ── 尺寸与背景 ──

    def resize(self, width, height):
        """画布尺寸变化时重建背景与装饰。"""
        width = max(1, int(width))
        height = max(1, int(height))
        if (width, height) == self._size:
            return False
        self._size = (width, height)
        self._draw_background(width, height)
        self._decor_sig = None
        return True

    def _draw_background(self, width, height):
        """水体伪渐变（若干横条）+ 玻璃边框。

        ⚠️ 水体色必须 ≠ 色键，否则整块区域失去鼠标命中（§7.2 警告）。
        """
        for item in self._bg_items:
            self.canvas.delete(item)
        self._bg_items = []
        bands = 12
        for i in range(bands):
            y0 = height * (float(i) / bands)
            y1 = height * (float(i + 1) / bands)
            color = self.theme.water_at((i + 0.5) / bands)
            self._bg_items.append(self.canvas.create_rectangle(
                0, y0, width, y1 + 1, fill=color, outline="", tags=_BG_TAG))
        self._bg_items.append(self.canvas.create_rectangle(
            1, 1, width - 1, height - 1, fill="",
            outline=self.theme.glass_edge, width=2, tags=_BG_TAG))
        for item in self._bg_items:
            self.canvas.tag_lower(item)

    # ── 主渲染 ──

    def render(self):
        """画一帧。返回本帧 touch 的 item 数。"""
        width, height = self._size
        if width <= 1 or height <= 1:
            return 0
        self.frames += 1
        self._alive = set()

        self._render_decor(width, height)
        self._render_food(width, height)
        self._render_fish(width, height)
        self._render_particles(width, height)
        self._sweep()
        return len(self._alive)

    def _touch(self, key, factory, coords, color, **cfg):
        """差分核心：有 item 就改，没有才建。"""
        self._alive.add(key)
        item = self._items.get(key)
        if item is None:
            item = factory()
            self._items[key] = item
            self.created += 1
        else:
            self.reused += 1
        try:
            self.canvas.coords(item, *coords)
            if color is not None:
                self.canvas.itemconfig(item, fill=color, **cfg)
            elif cfg:
                self.canvas.itemconfig(item, **cfg)
        except Exception:
            # item 被外部删掉了（例如切换窗口形态），下一帧会自动重建
            self._items.pop(key, None)
        return item

    def _sweep(self):
        """删掉本帧没出现的 item（鱼被移除 / 鱼食被吃掉）。"""
        dead = [k for k in self._items if k not in self._alive]
        for k in dead:
            try:
                self.canvas.delete(self._items[k])
            except Exception:
                pass
            self._items.pop(k, None)

    # ── 各图层 ──

    def _render_decor(self, width, height):
        """装饰是静态图元，只有列表变化时才重画（P0-22 ⑤）。"""
        views = self.game.decor_views()
        sig = tuple(sorted(v["id"] for v in views))
        if sig != self._decor_sig:
            self.decor.redraw(views, width, height)
            self._decor_sig = sig

    def _render_fish(self, width, height):
        """逐条鱼画出全部部件。"""
        base_len = width * self.base_len_ratio
        for view in self.game.fish_views():
            uid = view["uid"]
            ox = float(view["x"]) * width
            oy = float(view["y"]) * height
            flip = float(view.get("heading", 1.0)) < 0.0
            scale = float(view.get("scale", 1.0) or 1.0)
            prims = self.fish.prims_for(view, base_len * scale)
            for idx, prim in enumerate(prims):
                key = ("fish", uid, idx)
                coords = self.fish.to_canvas_coords(prim, ox, oy, flip)
                color = self.fish.color_for(prim.role, view)
                if prim.kind == "outline":
                    self._touch(key,
                                lambda p=prim, c=coords, col=color:
                                self.fish.create_item(p, c, col, "fish"),
                                coords, None, outline=color,
                                width=max(1.0, prim.width))
                else:
                    self._touch(key,
                                lambda p=prim, c=coords, col=color:
                                self.fish.create_item(p, c, col, "fish"),
                                coords, color)

    def _render_food(self, width, height):
        """鱼食：小圆点，临近过期时朝水色淡出。"""
        for i, f in enumerate(self.game.food_views()):
            x = float(f["x"]) * width
            y = float(f["y"]) * height
            r = max(1.5, width * 0.006)
            life = float(f.get("life", 1.0))
            fade = 1.0 if life > 2.0 else max(0.0, life / 2.0)
            color = mix(self.theme.water_bottom, "#E8C98A", fade)
            self._touch(("food", i),
                        lambda: self.canvas.create_oval(
                            0, 0, 0, 0, fill=color, outline="", tags="food"),
                        (x - r, y - r, x + r, y + r), color)

    def _render_particles(self, width, height):
        """气泡：引擎粒子系统的投影，纯表现。"""
        for i, p in enumerate(self.game.particle_views()):
            x = float(p["x"]) * width
            y = float(p["y"]) * height
            r = max(1.0, float(p.get("size", 2.0)))
            alpha = max(0.0, min(1.0, float(p.get("alpha", 1.0))))
            color = mix(self.theme.water_at(float(p["y"])), "#CFEAF7", alpha * 0.8)
            self._touch(("bubble", i),
                        lambda: self.canvas.create_oval(
                            0, 0, 0, 0, fill=color, outline="", tags="bubble"),
                        (x - r, y - r, x + r, y + r), color)

    # ── 命中测试 ──

    def fish_at(self, px, py, radius_ratio=0.09):
        """返回点击位置命中的鱼 uid（没有则 None）。

        用归一化距离判定，不依赖 canvas 的 `find_closest`，
        这样点到"鱼旁边一点"也能选中，手感更宽容（准则 L5）。
        """
        width, height = self._size
        if width <= 1 or height <= 1:
            return None
        best = None
        best_d = radius_ratio ** 2
        nx = float(px) / width
        ny = float(py) / height
        for view in self.game.fish_views():
            dx = float(view["x"]) - nx
            dy = float(view["y"]) - ny
            d = dx * dx + dy * dy
            if d < best_d:
                best_d = d
                best = view["uid"]
        return best

    def clear(self):
        """清空全部动态 item（切换窗口形态时用）。"""
        for item in self._items.values():
            try:
                self.canvas.delete(item)
            except Exception:
                pass
        self._items = {}
        self._alive = set()
        self.decor.clear()
        self._decor_sig = None
