"""★ FishTankApp：GUI 装配与主循环（子任务 4.1 / 4.2 / 4.14 / 4.15）。

🔴 禁止 `from __future__ import annotations`（E6）。

启动顺序（严格照 ARCHITECTURE §7.1，顺序错了会踩三个坑）
--------------------------------------------------------
1. `game.start()` —— **离线结算必须在建窗口之前完成**，
   否则玩家会先看到旧数据再跳变；
2. `tk.Tk()` —— 此后才允许构造 `Styles`（E9：它会建 tkfont.Font）；
3. `PetWindow` / 渲染器 / 托盘；
4. 离线卡片（唯一一次主动弹出，P0-19）；
5. `root.after(...)` 驱动，`root.mainloop()`。

主循环（4.2）
-------------
🔴 **绝不调用引擎 `FixedTimestepLoop.run_real_time()`** —— 它自带 while+sleep，
   会把 tkinter 的事件循环彻底冻死（E2）。这里用 `root.after` 自驱动，
   每次回调里按真实经过时间调 `game.update(dt)`。

省电（P0-22 / 4.14）
--------------------
窗口隐藏时：`_render` 直接 return，且帧率降到 `loop.render_hz_hidden`（2Hz）。
玩法仍然按真实时间推进（准则 L2：收益永不丢失），只是不画。

零打扰（P0-23 / 4.15）
----------------------
本文件及全 `pyapp/` **不出现任何桌面通知 API**（无 win10toast / plyer /
notify-send / NSUserNotification）。全程唯一的主动弹出就是离线卡片。
"""

import time
import tkinter as tk

from fishtank import engine_bootstrap as boot
from pyapp.canvas_render import CanvasRenderer
from pyapp.fish_card import FishCard
from pyapp.hud import Hud
from pyapp.offline_card import OfflineCard
from pyapp.panel_window import PanelWindow
from pyapp.pet_window import PetWindow
from pyapp.theme import Theme
from pyapp.tray import make_tray


class FishTankApp(object):
    """把 `FishTankGame` 装进 tkinter 桌宠窗口。"""

    def __init__(self, game, no_tray=False, logger=None):
        """:param game: 已构造但**尚未** `start()` 的 :class:`~fishtank.game.FishTankGame`
        :param no_tray: CLI `--no-tray`
        """
        self.game = game
        self.no_tray = bool(no_tray)
        self.log = logger or boot.get_logger("fishtank")

        self.root = None
        self.theme = None
        self.text = None
        self.window = None
        self.renderer = None
        self.hud = None
        self.card = None
        self.panel = None
        self.tray = None
        self.offline_card = None

        self._gui_syms = None
        self._running = False
        self._last = 0.0
        self._timer = None
        self._hz = 30.0
        self._hz_hidden = 2.0
        self.hud_fade_enabled = True
        self.frames = 0

    # ── 引擎 GUI 符号（E9：必须在 tk.Tk() 之后取）──

    def gui_syms(self):
        """惰性取 `(Styles, StatusPanel, TkUtil, hsv_to_rgb)`。"""
        if self._gui_syms is None:
            self._gui_syms = boot.gui_symbols()
        return self._gui_syms

    # ── 装配 ──

    def build(self):
        """按 §7.1 的顺序把整个应用装起来。"""
        # ① 领域层先跑完（含离线结算）
        self.game.start()
        self.text = self.game.text
        bal = self.game.bal
        self._hz = max(1.0, float(bal.get("loop.render_hz", 30) or 30))
        self._hz_hidden = max(0.5, float(bal.get("loop.render_hz_hidden", 2) or 2))

        # ② 再建 Tk root
        self.root = tk.Tk()
        self.root.withdraw()
        self.theme = Theme(bal)
        for problem in self.theme.validate():
            self.log.warning("[app] 配色校验：%s" % problem)

        font = self.theme.pick_font(boot.engine_font_candidates(), 10)
        font_bold = (font[0], font[1], "bold")
        try:
            self.gui_syms()          # E9：此刻构造 Styles 才是安全的
        except Exception as exc:
            self.log.warning("[app] 引擎 GUI 符号不可用（降级为纯 tk）：%s" % exc)

        # ③ 窗口与渲染
        self.window = PetWindow(self.root, self.theme, self.text,
                                on_event=self._on_window_event)
        self.renderer = CanvasRenderer(self.window.canvas, self.theme, self.game)
        self.hud = Hud(self.window.canvas, self.theme, self.game, self.text)
        self.hud.set_font(font, font_bold)
        self.card = FishCard(self.window.canvas, self.theme, self.game, self.text)
        self.card.set_font(font, font_bold)
        self.panel = PanelWindow(self.root, self.theme, self.text, self.game, self)

        # ④ 托盘（本机实测走 NullTray）
        self.tray = make_tray(self, no_tray=self.no_tray)
        self.tray.start()
        self.window.set_menu(self.tray.menu_items())

        self.root.deiconify()
        self.root.update_idletasks()
        w, h = self.window.size()
        self.renderer.resize(w, h)
        self.hud.resize(w, h)
        self.window.start_fullscreen_watch()

        # ⑤ 离线卡片：全程唯一一次主动弹出（P0-19）
        self.offline_card = OfflineCard(self.root, self.theme, self.text, bal)
        report = self.game.offline_report
        if self.offline_card.should_show(report):
            self.offline_card.show(report)
        return self

    # ── 主循环（4.2）──

    def run(self):
        """建好界面并进入 tk 主循环。返回退出码。"""
        self.build()
        self._running = True
        self._last = time.perf_counter()
        self._schedule()
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            pass
        finally:
            self._teardown()
        return 0

    def _schedule(self):
        """按当前应有帧率排下一次 tick。

        🔴 **不变式：任何时刻至多有一个待处理的帧定时器。**
        排新的之前先取消旧的 —— 否则一旦有第二处代码调到 `_schedule()`，
        帧驱动就会静默地变成两条并行的链，CPU 翻倍且再也降不回来
        （P0-22 要求空闲 CPU < 2%，这种翻倍是致命的）。
        """
        if self.root is None:
            return None
        if self._timer is not None:
            try:
                self.root.after_cancel(self._timer)
            except tk.TclError:
                pass
            self._timer = None
        if not self._running:
            return None
        hz = self._hz if self.window.is_visible() else self._hz_hidden
        delay = max(1, int(1000.0 / max(0.5, hz)))
        self._timer = self.root.after(delay, self._tick)
        return self._timer

    def _tick(self):
        """一帧：推进模拟 → 渲染 → 排下一帧。"""
        self._timer = None          # 本次定时器已到期，避免 _schedule 去 cancel 它
        if not self._running:
            return
        now = time.perf_counter()
        dt = now - self._last
        self._last = now
        if dt < 0.0:
            dt = 0.0

        try:
            self.game.update(dt)
        except Exception as exc:
            self.log.error("[app] 模拟异常：%r" % (exc,))

        try:
            self._render(dt)
        except tk.TclError:
            # 窗口已销毁
            self._running = False
            return
        except Exception as exc:
            self.log.error("[app] 渲染异常：%r" % (exc,))

        self.frames += 1
        self._schedule()

    def _render(self, dt):
        """画一帧。隐藏时直接 return（P0-22 ①）。"""
        if not self.window.is_visible():
            return False
        w, h = self.window.size()
        self.renderer.resize(w, h)
        self.hud.resize(w, h)
        self.renderer.render()
        if self.hud_fade_enabled:
            self.hud.update(dt)
        else:
            self.hud.alpha = 1.0
        self.hud.render()
        self.card.update(dt)
        self.card.render(w, h)
        return True

    # ── 窗口事件 ──

    def _on_window_event(self, name, payload=None):
        """`PetWindow` 的统一事件出口。"""
        if name == "enter":
            self.hud.on_enter()
        elif name == "leave":
            self.hud.on_leave()
            self.game.set_interest(None, None)
        elif name == "motion" and payload:
            w, h = self.window.size()
            self.game.set_interest(payload[0] / float(w), payload[1] / float(h))
        elif name == "click" and payload:
            self._on_click(payload[0], payload[1])
        elif name == "double" and payload:
            self._on_double(payload[0], payload[1])
        elif name == "resize" and payload:
            self.renderer.resize(payload[0], payload[1])
            self.hud.resize(payload[0], payload[1])
        elif name == "close":
            # 关闭按钮 = 隐藏，绝不退出（4.13）。
            # 走 hide_window 而不是 window.hide，才会尊重"无托盘且无热键时
            # 禁止完全隐藏"的守卫（4.12 / §7.5）。
            self.hide_window()
            return True
        return True

    def _on_click(self, px, py):
        """单击：点到鱼弹小卡，点到空水域不做任何事（准则 L5，不误触）。"""
        uid = self.renderer.fish_at(px, py)
        if uid is not None:
            self.card.show(uid)
        else:
            self.card.hide()
        return uid

    def _on_double(self, px, py):
        """双击空白 = 投喂一颗（≤3 次点击达成核心操作）。"""
        w, h = self.window.size()
        self.game.feed_at(px / float(w), py / float(h))
        return True

    # ── 托盘 / 菜单动作 ──

    def call_on_ui(self, fn):
        """把回调弹回 tk 主线程执行（pystray 回调跑在别的线程）。"""
        if self.root is None:
            return False
        try:
            self.root.after(0, fn)
            return True
        except (tk.TclError, RuntimeError):
            return False

    def show_window(self):
        """显示鱼缸。"""
        self.window.show()
        self._schedule_now()
        return True

    def hide_window(self):
        """隐藏鱼缸。

        🔴 只有在托盘可用或热键注册成功时才允许**完全**隐藏；
        否则退化成迷你角标，保证永远找得回来（§7.5）。
        """
        self.window.hide(allow_full=self.tray.can_fully_hide())
        return True

    def toggle_window(self):
        """全局热键 `Ctrl+Alt+F` 的回调。"""
        if self.window.is_visible() and not self.window.mini:
            self.hide_window()
        else:
            self.show_window()
        return True

    def open_panel(self):
        """打开管理面板。"""
        self.panel.open()
        return True

    def feed_center(self):
        """从菜单投喂（丢在缸中央）。"""
        self.game.feed_at(0.5, 0.35)
        return True

    def set_topmost(self, on):
        return self.window.set_topmost(on)

    def set_click_through(self, on):
        """开关鼠标穿透。穿透后必须还有恢复通道，否则拒绝开启。"""
        if on and not self.tray.can_fully_hide():
            self.log.warning("[app] 无托盘且热键不可用，拒绝开启鼠标穿透（会失去操作入口）")
            return False
        return self.window.set_click_through(on)

    def set_hud_fade(self, on):
        self.hud_fade_enabled = bool(on)
        if not on:
            self.hud.alpha = 1.0
        return True

    def _schedule_now(self):
        """立刻按新帧率重排一次 tick（显隐切换后帧率会变）。

        取消动作已经内建在 `_schedule()` 里，这里直接转调即可。
        """
        return self._schedule()

    def quit(self):
        """真正退出：存档 → 停托盘 → 销毁窗口。"""
        self._running = False
        self._teardown()
        if self.root is not None:
            try:
                self.root.quit()
                self.root.destroy()
            except tk.TclError:
                pass
        return True

    def _teardown(self):
        """收尾（幂等）。"""
        if self.game is not None:
            try:
                self.game.shutdown()
            except Exception as exc:
                self.log.error("[app] 退出存档失败：%r" % (exc,))
        if self.window is not None:
            self.window.stop_fullscreen_watch()
        if self.tray is not None:
            self.tray.stop()
        return True
