"""管理面板（P0-20，子任务 4.11）：Toplevel + 4 页签。

🔴 禁止 `from __future__ import annotations`（E6）。
🔴 E8：`TkUtil` / `Styles` / `StatusPanel` 必须从 `render.gui_base` 取，
   **不是** `render.widgets`；且只能在 `tk.Tk()` 之后拿（E9）。
   这些都封装在 :func:`fishtank.engine_bootstrap.gui_symbols` 里。
🔴 文案全部走 `ui_text.json`（§7.6）。

四个页签：鱼缸 / 图鉴 / 商店 / 设置。
每次打开时重建内容（数量少，重建比增量维护简单且不易出错）。
"""

import tkinter as tk
from tkinter import ttk

from fishtank.economy import format_coins


class PanelWindow(object):
    """管理面板窗口。"""

    def __init__(self, root, theme, text, game, app):
        self.root = root
        self.theme = theme
        self.text = text
        self.game = game
        self.app = app
        self.win = None
        self.nb = None
        self._tabs = {}
        self._scrollable = None

    # ── 生命周期 ──

    def open(self):
        """打开（或前置）面板。"""
        if self.win is not None:
            try:
                self.win.deiconify()
                self.win.lift()
                return False
            except tk.TclError:
                self.win = None

        th = self.theme
        win = tk.Toplevel(self.root)
        self.win = win
        win.title(self.text.get("app.panel_title"))
        win.geometry("%dx%d" % (th.panel_w, th.panel_h))
        win.configure(bg=th.card_bg)
        win.protocol("WM_DELETE_WINDOW", self.close)

        try:
            _styles, _status, tkutil, _hsv = self.app.gui_syms()
            self._scrollable = getattr(tkutil, "create_scrollable_frame", None)
        except Exception:
            self._scrollable = None

        self.nb = ttk.Notebook(win)
        self.nb.pack(fill="both", expand=True, padx=6, pady=6)
        for key, builder in (("tank", self._build_tank),
                             ("codex", self._build_codex),
                             ("shop", self._build_shop),
                             ("settings", self._build_settings)):
            frame = tk.Frame(self.nb, bg=th.card_bg)
            self.nb.add(frame, text=self.text.get("tabs." + key))
            self._tabs[key] = (frame, builder)
        self.refresh()
        return True

    def close(self):
        """关闭面板。"""
        if self.win is not None:
            try:
                self.win.destroy()
            except tk.TclError:
                pass
            self.win = None
            self.nb = None
            self._tabs = {}
        return True

    def is_open(self):
        return self.win is not None

    def refresh(self):
        """重建全部页签内容。"""
        if self.win is None:
            return False
        for key, (frame, builder) in self._tabs.items():
            for child in frame.winfo_children():
                child.destroy()
            try:
                builder(self._body(frame))
            except Exception as exc:
                self.app.log.warning("[panel] 页签 %s 构建失败：%s" % (key, exc))
        return True

    # ── 通用小部件 ──

    def _body(self, parent):
        """返回可滚动内容容器（引擎有就用引擎的，E8）。"""
        if self._scrollable is not None:
            try:
                result = self._scrollable(parent)
                if isinstance(result, (tuple, list)) and result:
                    return result[-1] if len(result) > 1 else result[0]
                if result is not None:
                    return result
            except Exception:
                pass

        # 降级：Canvas + Scrollbar 实现可滚动区域
        container = tk.Frame(parent, bg=self.theme.card_bg)
        container.pack(fill="both", expand=True)

        canvas = tk.Canvas(container, bg=self.theme.card_bg,
                           highlightthickness=0, bd=0)
        scrollbar = tk.Scrollbar(container, orient="vertical",
                                 command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        inner = tk.Frame(canvas, bg=self.theme.card_bg)
        inner_id = canvas.create_window((0, 0), window=inner, anchor="nw")

        def _on_inner_configure(event):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _on_canvas_configure(event):
            canvas.itemconfig(inner_id, width=event.width)

        inner.bind("<Configure>", _on_inner_configure, add="+")
        canvas.bind("<Configure>", _on_canvas_configure, add="+")

        # 鼠标滚轮滚动
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def _bind_wheel(_event):
            canvas.bind_all("<MouseWheel>", _on_mousewheel, add="+")

        def _unbind_wheel(_event):
            canvas.unbind_all("<MouseWheel>")

        canvas.bind("<Enter>", _bind_wheel, add="+")
        canvas.bind("<Leave>", _unbind_wheel, add="+")

        # 当 inner 销毁时解绑滚轮（防止残留绑定）
        def _on_destroy(_event):
            try:
                canvas.unbind_all("<MouseWheel>")
            except tk.TclError:
                pass

        inner.bind("<Destroy>", _on_destroy, add="+")

        return inner

    def _row(self, parent):
        row = tk.Frame(parent, bg=self.theme.card_bg)
        row.pack(fill="x", padx=10, pady=3)
        return row

    def _label(self, parent, txt, bold=False, fg=None, side="left"):
        lbl = tk.Label(parent, text=txt, bg=self.theme.card_bg,
                       fg=fg or self.theme.card_fg,
                       font=(self.theme.font_family, 10,
                             "bold" if bold else "normal"),
                       anchor="w", justify="left")
        lbl.pack(side=side, padx=(0, 8))
        return lbl

    def _button(self, parent, txt, cmd, enabled=True):
        btn = tk.Button(parent, text=txt, command=cmd, relief="flat", bd=0,
                        bg=self.theme.card_accent if enabled else self.theme.hud_bar_bg,
                        fg=self.theme.card_bg if enabled else self.theme.card_fg,
                        font=(self.theme.font_family, 9), padx=10, pady=2,
                        cursor="hand2" if enabled else "arrow",
                        state="normal" if enabled else "disabled")
        btn.pack(side="right")
        return btn

    def _act(self, result):
        """执行动作后刷新面板（动作本身在 game 层）。"""
        self.refresh()
        return result

    # ── 页签：鱼缸 ──

    def _build_tank(self, body):
        t = self.text
        snap = self.game.hud_snapshot()
        head = self._row(body)
        self._label(head, "%s %s" % (t.get("labels.coins"), snap["coins_text"]), True,
                    self.theme.card_accent)
        self._label(head, "%s %d/%d" % (t.get("labels.capacity"),
                                        snap["fish_count"], snap["capacity"]))
        self._label(head, "%s %d%%" % (t.get("labels.water"),
                                       int(round(snap["water"]))))

        views = self.game.fish_views()
        if not views:
            self._label(self._row(body), t.get("empty_states.tank_empty"))
            return
        for v in views:
            row = self._row(body)
            sp = self.game.species.get(v["species"])
            name = sp.name_zh if sp else v["species"]
            self._label(row, name, True)
            self._label(row, "%s %s" % (t.get("labels.rarity"), v["rarity"]))
            self._label(row, "%s %s" % (t.get("labels.stage"),
                                        t.get("stages.%s" % v.get("stage", "adult"))))

    # ── 页签：图鉴 ──

    def _build_codex(self, body):
        t = self.text
        unlocked = set(self.game.state.codex)
        if not unlocked:
            self._label(self._row(body), t.get("empty_states.codex_empty"))
        items = self.game.species.all_items.values()
        for sp in items:
            row = self._row(body)
            if sp.id in unlocked:
                self._label(row, sp.name_zh, True)
                self._label(row, sp.rarity)
                self._label(row, sp.science[:38])
            else:
                self._label(row, t.get("labels.unknown"), False,
                            self.theme.hud_bar_bg)

    # ── 页签：商店 ──

    def _build_shop(self, body):
        t = self.text
        snap = self.game.hud_snapshot()
        self._label(self._row(body),
                    "%s %s" % (t.get("labels.coins"), snap["coins_text"]),
                    True, self.theme.card_accent)

        # 鱼苗
        sale = self.game.bal.get("shop.sale_rarities") or []
        sold = [sp for sp in self.game.species.all_items.values()
                if not sale or sp.rarity in sale]
        if not sold:
            self._label(self._row(body), t.get("empty_states.shop_empty"))
        for sp in sold:
            row = self._row(body)
            self._label(row, sp.name_zh, True)
            self._label(row, sp.rarity)
            price = self.game.fry_price_text(sp.id)
            self._label(row, "%s %s" % (t.get("labels.price"), price))
            self._button(row, t.get("buttons.buy"),
                         lambda i=sp.id: self._act(self.game.buy_fry(i)))

        # 升级
        for kind in ("capacity", "filter", "feeder"):
            row = self._row(body)
            info = self.game.upgrade_info(kind)
            self._label(row, t.get("labels.%s" % (
                "capacity" if kind == "capacity" else
                "filter" if kind == "filter" else "feeder")), True)
            self._label(row, "%s %d" % (t.get("labels.level"), info["level"]))
            if info["maxed"]:
                self._label(row, t.get("labels.max_level"))
                self._button(row, t.get("buttons.upgrade"), lambda: None, False)
            else:
                self._label(row, "%s %s" % (t.get("labels.price"), info["price_text"]))
                self._button(row, t.get("buttons.upgrade"),
                             lambda k=kind: self._act(self.game.buy_upgrade(k)))

        # 装饰
        owned = set(self.game.state.tank.decors)
        for did in self.game.decor.ids():
            d = self.game.decor.get(did)
            row = self._row(body)
            self._label(row, d.name, True)
            self._label(row, "%s +%.0f%%" % (t.get("labels.bonus"), d.bonus * 100))
            if did in owned:
                self._label(row, t.get("labels.installed"))
                self._button(row, t.get("buttons.owned"), lambda: None, False)
            else:
                self._label(row, "%s %s" % (
                    t.get("labels.price"),
                    format_coins(d.price * self.game.bal.coin_scale(), self.game.bal)))
                self._button(row, t.get("buttons.place"),
                             lambda i=did: self._act(self.game.buy_decor(i)))

    # ── 页签：设置 ──

    def _build_settings(self, body):
        t = self.text
        app = self.app

        def toggle(label, getter, setter):
            row = self._row(body)
            var = tk.BooleanVar(value=bool(getter()))
            self._label(row, label, True)
            chk = tk.Checkbutton(
                row, variable=var, bg=self.theme.card_bg,
                activebackground=self.theme.card_bg,
                selectcolor=self.theme.hud_bar_bg, bd=0,
                command=lambda: setter(var.get()))
            chk.pack(side="right")
            return var

        toggle(t.get("buttons.topmost"),
               lambda: app.window.topmost, app.set_topmost)
        toggle(t.get("buttons.click_through"),
               lambda: app.window.click_through, app.set_click_through)
        toggle(t.get("buttons.hud_fade"),
               lambda: app.hud_fade_enabled, app.set_hud_fade)
        toggle(t.get("buttons.feed_auto"),
               lambda: self.game.state.tank.feeder_on,
               lambda v: self._act(self.game.toggle_feeder(bool(v))))

        row = self._row(body)
        self._label(row, t.get("buttons.close_hint"))
        if not app.tray.can_fully_hide():
            self._label(self._row(body), t.get("hints.hotkey_failed"))
        elif not app.tray.available:
            self._label(self._row(body), t.get("hints.tray_missing"))
            self._label(self._row(body), t.get("hints.hotkey_hint"))

        row = self._row(body)
        self._button(row, t.get("buttons.quit"), app.quit)
