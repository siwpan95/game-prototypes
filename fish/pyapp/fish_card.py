"""点击鱼时弹出的信息小卡（画在 Canvas 内，不新建窗口）。

🔴 禁止 `from __future__ import annotations`（E6）。
🔴 文案取自 `ui_text.json`（§7.6）。

做成 Canvas 图元而不是 Toplevel 的原因：
桌宠窗口是 `overrideredirect` 无边框窗，再叠一个小窗会闪、会抢焦点，
也会在任务栏留痕。画在缸里最安静（准则 L8）。

`ui.fish_card_sec` 秒后自动消失，不需要用户去关它（准则 L5）。
"""

_PAD = 7
_LINE = 14


class FishCard(object):
    """一张跟随鱼的信息小卡。"""

    def __init__(self, canvas, theme, game, text):
        self.canvas = canvas
        self.theme = theme
        self.game = game
        self.text = text
        self.uid = None
        self._timer = 0.0
        self._items = []
        self._font = (theme.font_family, 9, "normal")
        self._font_bold = (theme.font_family, 9, "bold")

    def set_font(self, font, font_bold):
        """由 app 注入探测好的中文字体。"""
        self._font = font
        self._font_bold = font_bold

    def show(self, uid):
        """展示某条鱼的小卡；重复点同一条则关闭（toggle）。"""
        if self.uid == uid:
            self.hide()
            return False
        self.uid = uid
        self._timer = max(0.5, float(self.theme.fish_card_sec))
        return True

    def hide(self):
        """收起小卡。"""
        self.uid = None
        self._timer = 0.0
        self._clear()
        return True

    def update(self, dt):
        """倒计时；到点自动收起。"""
        if self.uid is None:
            return False
        self._timer -= float(dt)
        if self._timer <= 0.0:
            self.hide()
            return False
        return True

    def _clear(self):
        for item in self._items:
            try:
                self.canvas.delete(item)
            except Exception:
                pass
        self._items = []

    def _lines(self, view):
        """组织卡片文字行。全部走 ui_text，代码里没有中文。"""
        t = self.text
        sp = self.game.species.get(view.get("species", "")) if self.game.species else None
        name = sp.name_zh if sp is not None else view.get("species", "")
        stage_key = "stages.%s" % view.get("stage", "adult")
        rows = [
            (name, True),
            ("%s %s" % (t.get("labels.rarity"), view.get("rarity", "R1")), False),
            ("%s %s" % (t.get("labels.stage"), t.get(stage_key)), False),
        ]
        if sp is not None and getattr(sp, "group", ""):
            rows.append(("%s %s" % (t.get("labels.group"), sp.group), False))
        return rows

    def render(self, width, height):
        """把小卡画在鱼的上方；靠边时自动翻转，保证不出画布。"""
        self._clear()
        if self.uid is None:
            return False
        view = None
        for v in self.game.fish_views():
            if v["uid"] == self.uid:
                view = v
                break
        if view is None:
            self.hide()
            return False

        rows = self._lines(view)
        card_w = 118.0
        card_h = _PAD * 2 + _LINE * len(rows)
        fx = float(view["x"]) * width
        fy = float(view["y"]) * height

        x0 = fx - card_w * 0.5
        y0 = fy - card_h - 18
        if y0 < 2:
            y0 = fy + 18
        x0 = max(2.0, min(x0, width - card_w - 2.0))
        y0 = max(2.0, min(y0, height - card_h - 2.0))

        self._items.append(self.canvas.create_rectangle(
            x0, y0, x0 + card_w, y0 + card_h,
            fill=self.theme.card_bg, outline=self.theme.card_accent,
            width=1, tags="fishcard"))
        for i, (line, bold) in enumerate(rows):
            self._items.append(self.canvas.create_text(
                x0 + _PAD, y0 + _PAD + i * _LINE,
                text=line, anchor="nw",
                fill=self.theme.card_accent if bold else self.theme.card_fg,
                font=self._font_bold if bold else self._font, tags="fishcard"))
        for item in self._items:
            self.canvas.tag_raise(item)
        return True
