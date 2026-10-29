"""★ PetWindow：自建桌宠窗口（P0-14，子任务 4.3 / 4.4 / 4.13）。

🔴 禁止 `from __future__ import annotations`（E6）。
🔴 **不继承引擎 `BaseWindow`**（E7）：`BaseWindow` 自带标题栏与
   `mainloop` 约定，与 `overrideredirect` 无边框桌宠冲突。这里直接用 tk。

色键陷阱（§7.2 末尾）
---------------------
`-transparentcolor` 抠掉的像素**同时失去鼠标命中**。
所以窗口底色用色键（`ui.chroma`）实现圆角外的镂空，
而缸体本身必须用**与色键不同**的水色，否则整个鱼缸都点不中、拖不动。
:meth:`pyapp.theme.Theme.validate` 会在启动时校验这一条。
"""

import tkinter as tk

from pyapp import win_native


class PetWindow(object):
    """无边框、置顶、可拖拽的鱼缸窗口。"""

    def __init__(self, root, theme, text, on_event=None):
        """:param root: 唯一的 `tk.Tk()`
        :param on_event: 事件回调 `fn(name, payload)`，由 app 注入
        """
        self.root = root
        self.theme = theme
        self.text = text
        self.on_event = on_event or (lambda name, payload=None: None)

        self.hidden = False
        self.mini = False
        self.topmost = True
        self.click_through = False
        self._drag = None
        self._menu = None
        self._normal_geom = None
        self._yield_timer = None
        self._yielded = False

        self._build()

    # ── 构建 ──

    def _build(self):
        """建窗口与画布。顺序照 ARCHITECTURE §7.2 的代码块。"""
        root = self.root
        th = self.theme
        root.title(self.text.get("app.title"))
        root.overrideredirect(True)
        self._attr("-topmost", True)
        root.configure(bg=th.chroma)
        self._attr("-transparentcolor", th.chroma)
        self._attr("-alpha", 1.0)
        # 不进 Alt+Tab、不抢注意力（准则 L8）
        self._attr("-toolwindow", True)

        self.canvas = tk.Canvas(root, width=th.tank_w, height=th.tank_h,
                                bg=th.chroma, highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)
        root.geometry("%dx%d" % (th.tank_w, th.tank_h))
        self._place_default()
        self._bind()

    def _attr(self, name, value):
        """设置窗口属性，平台不支持时静默跳过。"""
        try:
            self.root.attributes(name, value)
            return True
        except tk.TclError:
            return False

    def _place_default(self):
        """默认摆在右下角，避开任务栏一点。"""
        sw, sh = win_native.screen_size(self.root)
        x = sw - self.theme.tank_w - 40
        y = sh - self.theme.tank_h - 80
        self.root.geometry("+%d+%d" % (max(0, x), max(0, y)))

    def _bind(self):
        """绑定拖拽 / 悬停 / 点击 / 右键菜单。"""
        cv = self.canvas
        cv.bind("<Button-1>", self._on_press)
        cv.bind("<B1-Motion>", self._on_drag)
        cv.bind("<ButtonRelease-1>", self._on_release)
        cv.bind("<Double-Button-1>", self._on_double)
        cv.bind("<Button-3>", self._on_right)
        cv.bind("<Enter>", lambda e: self.on_event("enter"))
        cv.bind("<Leave>", lambda e: self.on_event("leave"))
        cv.bind("<Motion>", self._on_motion)
        cv.bind("<Configure>", self._on_configure)
        # 关闭 = 隐藏，不退出（P0-15 / 4.13）
        # 🔴 必须走 on_event("close") 交给 app 决策，**不能**直接调 self.hide：
        #    self.hide 默认 allow_full=True，会绕过 app 里"托盘/热键都不可用时
        #    禁止完全隐藏"的守卫（§7.5），导致窗口再也叫不回来。
        self.root.protocol("WM_DELETE_WINDOW", self.request_close)

    # ── 输入 ──

    def _on_press(self, event):
        self._drag = (event.x_root, event.y_root,
                      self.root.winfo_x(), self.root.winfo_y())
        self._moved = False

    def _on_drag(self, event):
        if self._drag is None:
            return
        ox, oy, wx, wy = self._drag
        dx = event.x_root - ox
        dy = event.y_root - oy
        if abs(dx) > 2 or abs(dy) > 2:
            self._moved = True
        self.root.geometry("+%d+%d" % (wx + dx, wy + dy))

    def _on_release(self, event):
        """松手时贴边吸附；没拖动则视为一次点击。"""
        if self._drag is None:
            return
        moved = getattr(self, "_moved", False)
        self._drag = None
        if moved:
            self._snap()
            self.on_event("moved")
        else:
            self.on_event("click", (event.x, event.y))

    def _snap(self):
        """贴边吸附（4.4）。"""
        sw, sh = win_native.screen_size(self.root)
        x, y = win_native.snap_position(
            self.root.winfo_x(), self.root.winfo_y(),
            self.root.winfo_width(), self.root.winfo_height(),
            sw, sh, self.theme.snap_px)
        self.root.geometry("+%d+%d" % (x, y))

    def _on_double(self, event):
        self.on_event("double", (event.x, event.y))

    def _on_motion(self, event):
        self.on_event("motion", (event.x, event.y))

    def _on_configure(self, event):
        self.on_event("resize", (event.width, event.height))

    def _on_right(self, event):
        """右键菜单 —— 无托盘时这是主要的操作入口（§7.5）。"""
        if self._menu is not None:
            try:
                self._menu.tk_popup(event.x_root, event.y_root)
            finally:
                self._menu.grab_release()

    def set_menu(self, items):
        """用共用菜单定义建右键菜单。

        :param items: `[(标题, 回调), ...]`，标题 None 为分隔线
        """
        th = self.theme
        menu = tk.Menu(self.root, tearoff=0, bg=th.card_bg, fg=th.card_fg,
                       activebackground=th.card_accent, activeforeground=th.card_bg,
                       bd=0)
        for title, cb in items:
            if title is None:
                menu.add_separator()
            else:
                menu.add_command(label=title, command=cb)
        self._menu = menu
        return menu

    # ── 显隐（4.13 / 4.12）──

    def request_close(self):
        """窗口关闭按钮 / `WM_DELETE_WINDOW` 的入口（4.13：关闭 = 隐藏，不退出）。

        自己不做隐藏决策 —— 能不能**完全**隐藏取决于托盘与热键是否可用，
        那是 app 层才知道的事。这里只上报事件；若无人接管（单测直接构造
        `PetWindow` 的场景），退化成迷你角标这一最保守的选项。
        """
        if self.on_event("close") is True:
            return True
        return self.hide(allow_full=False)

    def hide(self, allow_full=True):
        """隐藏窗口。

        :param allow_full: False 时**禁止完全隐藏**，改为缩成迷你角标
                           （热键注册失败时的保命路径，§7.5）
        """
        if allow_full:
            self.root.withdraw()
            self.hidden = True
            self.mini = False
        else:
            self._to_mini()
        self.on_event("hidden", allow_full)
        return True

    def _to_mini(self):
        """缩成 `ui.mini_size` 迷你角标，贴在屏幕右下角。"""
        if self.mini:
            return False
        self._normal_geom = (self.root.winfo_width(), self.root.winfo_height(),
                             self.root.winfo_x(), self.root.winfo_y())
        sw, sh = win_native.screen_size(self.root)
        w, h = self.theme.mini_w, self.theme.mini_h
        self.root.geometry("%dx%d+%d+%d" % (w, h, sw - w - 8, sh - h - 60))
        self.mini = True
        self.hidden = False
        return True

    def show(self):
        """恢复显示（从隐藏或迷你角标）。"""
        self.root.deiconify()
        self.hidden = False
        if self.mini and self._normal_geom:
            w, h, x, y = self._normal_geom
            self.root.geometry("%dx%d+%d+%d" % (w, h, x, y))
        self.mini = False
        self.on_event("shown")
        return True

    def is_visible(self):
        """窗口当前是否可见（迷你角标也算可见）。"""
        return not self.hidden

    # ── 窗口属性开关（设置页）──

    def set_topmost(self, on):
        """置顶开关（Q10 允许用户关掉）。"""
        self.topmost = bool(on)
        return self._attr("-topmost", bool(on))

    def set_click_through(self, on):
        """鼠标穿透（P1-14）。调用方需保证有恢复通道。"""
        self.click_through = bool(on)
        return win_native.set_click_through(self.root, bool(on))

    # ── 全屏让位（Q10 / 4.x）──

    def start_fullscreen_watch(self, interval_ms=5000):
        """每 5 秒查一次前台是否全屏，是则临时取消置顶。"""
        def _check():
            try:
                if not self.hidden and self.topmost:
                    full = win_native.foreground_is_fullscreen(self.root)
                    if full and not self._yielded:
                        self._attr("-topmost", False)
                        self._yielded = True
                    elif not full and self._yielded:
                        self._attr("-topmost", True)
                        self._yielded = False
            except Exception:
                pass
            self._yield_timer = self.root.after(interval_ms, _check)
        self._yield_timer = self.root.after(interval_ms, _check)
        return True

    def stop_fullscreen_watch(self):
        """停掉让位轮询。"""
        if self._yield_timer is not None:
            try:
                self.root.after_cancel(self._yield_timer)
            except tk.TclError:
                pass
            self._yield_timer = None
            return True
        return False

    def size(self):
        """当前画布像素尺寸。"""
        try:
            return (max(1, self.canvas.winfo_width()),
                    max(1, self.canvas.winfo_height()))
        except tk.TclError:
            return (self.theme.tank_w, self.theme.tank_h)
