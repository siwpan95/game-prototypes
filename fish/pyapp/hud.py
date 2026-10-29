"""HUD：金币 / 鱼数 / 水质条（P0-18，子任务 4.9）。

🔴 禁止 `from __future__ import annotations`（E6）。
🔴 文案一律取自 `ui_text.json`，代码内不写中文字面量（§7.6）。

淡出实现说明
------------
tkinter Canvas **没有 per-item alpha**，所以"淡出"是靠把前景色朝水体背景色
混合来模拟的（:func:`pyapp.theme.mix`）。鼠标移出 `ui.hud_fade_sec` 秒后
渐变到 `ui.hud_dim_alpha`，移入立刻恢复。

这符合准则 L8（不抢注意力）：HUD 平时是"淡淡地在那儿"，需要时才清晰。
"""

from pyapp.theme import mix

_PAD = 8


class Hud(object):
    """右上角信息条 + 底部水质条。"""

    def __init__(self, canvas, theme, game, text):
        """:param text: :class:`~fishtank.data_defs.UIText`"""
        self.canvas = canvas
        self.theme = theme
        self.game = game
        self.text = text

        self.visible = True
        self.alpha = 1.0
        """当前不透明度（1=清晰，`hud_dim_alpha`=淡出到底）。"""
        self._target = 1.0
        self._idle = 0.0
        self._items = {}
        self._size = (0, 0)
        self._font = (theme.font_family, 9, "normal")
        self._font_bold = (theme.font_family, 10, "bold")

    def set_font(self, font, font_bold):
        """由 app 在字体探测完成后注入。"""
        self._font = font
        self._font_bold = font_bold

    def resize(self, width, height):
        """记录画布尺寸。"""
        self._size = (max(1, int(width)), max(1, int(height)))

    def on_enter(self):
        """鼠标进入 → 立刻恢复清晰。"""
        self._idle = 0.0
        self._target = 1.0

    def on_leave(self):
        """鼠标移出 → 开始计时淡出。"""
        self._idle = 0.0
        self._target = self.theme.hud_dim_alpha

    def update(self, dt):
        """推进淡出动画。"""
        fade_sec = max(0.05, self.theme.hud_fade_sec)
        if self._target < self.alpha:
            self._idle += float(dt)
            if self._idle >= fade_sec:
                self.alpha += (self._target - self.alpha) * min(1.0, float(dt) * 2.0)
        else:
            self.alpha += (self._target - self.alpha) * min(1.0, float(dt) * 8.0)
        if abs(self.alpha - self._target) < 0.005:
            self.alpha = self._target

    # ── 绘制 ──

    def render(self):
        """差分绘制 HUD。隐藏时直接清空。"""
        width, height = self._size
        if width <= 1 or not self.visible:
            self.clear()
            return False

        snap = self.game.hud_snapshot()
        fg = mix(self.theme.water_bottom, self.theme.hud_text, self.alpha)

        coins = "%s %s" % (self.text.get("labels.coins"), snap["coins_text"])
        fishes = "%s %d/%d" % (self.text.get("labels.fish_count"),
                               snap["fish_count"], snap["capacity"])
        self._label("coins", width - _PAD, _PAD, coins, fg, self._font_bold, "ne")
        self._label("fish", width - _PAD, _PAD + 16, fishes, fg, self._font, "ne")

        self._water_bar(width, height, snap)
        return True

    def _label(self, key, x, y, text, color, font, anchor):
        """复用 text item，只改文字与颜色。"""
        item = self._items.get(key)
        if item is None:
            item = self.canvas.create_text(x, y, text=text, fill=color,
                                           font=font, anchor=anchor, tags="hud")
            self._items[key] = item
        else:
            self.canvas.coords(item, x, y)
            self.canvas.itemconfig(item, text=text, fill=color, font=font)
        self.canvas.tag_raise(item)
        return item

    def _water_bar(self, width, height, snap):
        """左下角水质条：底槽 + 填充 + 标签。"""
        ratio = max(0.0, min(1.0, float(snap.get("water", 100.0)) / 100.0))
        bar_w = max(40.0, width * 0.34)
        bar_h = 6.0
        x0 = _PAD
        y0 = height - _PAD - bar_h
        bg = mix(self.theme.water_bottom, self.theme.hud_bar_bg, self.alpha)
        fill = mix(self.theme.water_bottom, self.theme.bar_color(ratio), self.alpha)

        self._rect("wbar_bg", x0, y0, x0 + bar_w, y0 + bar_h, bg)
        self._rect("wbar_fg", x0, y0, x0 + bar_w * ratio, y0 + bar_h, fill)
        label = "%s %d%%" % (self.text.get("labels.water"), int(round(ratio * 100)))
        self._label("wbar_txt", x0, y0 - 4,
                    label, mix(self.theme.water_bottom, self.theme.hud_text, self.alpha),
                    self._font, "sw")

    def _rect(self, key, x0, y0, x1, y1, color):
        """复用矩形 item。"""
        if x1 < x0:
            x1 = x0
        item = self._items.get(key)
        if item is None:
            item = self.canvas.create_rectangle(x0, y0, x1, y1, fill=color,
                                                outline="", tags="hud")
            self._items[key] = item
        else:
            self.canvas.coords(item, x0, y0, x1, y1)
            self.canvas.itemconfig(item, fill=color)
        self.canvas.tag_raise(item)
        return item

    def clear(self):
        """删掉全部 HUD item。"""
        for item in self._items.values():
            try:
                self.canvas.delete(item)
            except Exception:
                pass
        self._items = {}
