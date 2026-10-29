"""★ 托盘与降级（P0-15 / Q4，子任务 4.12）。

🔴 禁止 `from __future__ import annotations`（E6）。
🔴 **本机实测 `pystray=False`，所以 `NullTray` 是当前的默认路径**，
   它必须第一天就是对的，不能当成"以后再说"的兜底。

最严重的可用性事故是"隐藏之后找不回来"。因此 :class:`NullTray` 遵守
一条铁律（ARCHITECTURE §7.5）：

    **永远存在一条恢复路径。**

具体分三级降级：

1. 有 `pystray` + `Pillow` → :class:`PystrayTray`，托盘图标恢复；
2. 没有托盘，但全局热键 `Ctrl+Alt+F` 注册成功 → 允许完全隐藏，热键呼出；
3. 热键也注册失败 → **禁止完全隐藏**，改为缩成 `ui.mini_size` 迷你角标，
   点角标即可恢复。

菜单项定义只写一份（:meth:`TrayController.menu_items`），
托盘菜单与窗口右键菜单共用，避免两边行为漂移。
"""


class TrayController(object):
    """托盘控制器基类：定义菜单与显隐协议。"""

    def __init__(self, app):
        """:param app: :class:`pyapp.app.FishTankApp`"""
        self.app = app
        self.text = app.text
        self.available = False
        self.hotkey = None

    # ── 共用菜单定义 ──

    def menu_items(self):
        """返回 [(标题, 回调), ...]；`None` 标题表示分隔线。

        托盘菜单和窗口右键菜单共用这一份定义。
        """
        t = self.text
        app = self.app
        return [
            (t.get("buttons.show_tank"), app.show_window),
            (t.get("buttons.hide_window"), app.hide_window),
            (None, None),
            (t.get("buttons.open_panel"), app.open_panel),
            (t.get("buttons.feed"), app.feed_center),
            (None, None),
            (t.get("buttons.quit"), app.quit),
        ]

    def start(self):
        """启动托盘（基类不做事）。"""
        return False

    def stop(self):
        """停止托盘。"""
        return False

    def can_fully_hide(self):
        """是否允许把窗口**完全**隐藏。"""
        return False

    def notify_hidden(self):
        """窗口被隐藏后的提示钩子（默认什么都不做，准则 L6 零打扰）。"""
        return False


class PystrayTray(TrayController):
    """真·系统托盘（需要 `pystray` + `Pillow`）。"""

    def __init__(self, app):
        TrayController.__init__(self, app)
        self.icon = None
        self.available = True
        self._thread = None

    def _make_image(self, size=64):
        """用 Pillow 画一个简单的鱼缸图标（不依赖任何 PNG 资源，Q5）。"""
        from PIL import Image, ImageDraw
        th = self.app.theme
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle([2, 8, size - 2, size - 6], radius=8,
                            fill=th.water_top, outline=th.glass_edge, width=2)
        body = [size * 0.30, size * 0.42, size * 0.66, size * 0.66]
        d.ellipse(body, fill=th.card_accent)
        d.polygon([(size * 0.30, size * 0.54), (size * 0.18, size * 0.44),
                   (size * 0.18, size * 0.64)], fill=th.card_accent)
        return img

    def start(self):
        """在后台线程起托盘（pystray 自己需要独立线程）。"""
        try:
            import threading
            import pystray

            items = []
            for title, cb in self.menu_items():
                if title is None:
                    items.append(pystray.Menu.SEPARATOR)
                else:
                    items.append(pystray.MenuItem(
                        title, self._wrap(cb)))
            self.icon = pystray.Icon(
                "lazy_fish_tank", self._make_image(),
                self.text.get("app.title"), pystray.Menu(*items))
            self._thread = threading.Thread(target=self.icon.run, daemon=True)
            self._thread.start()
            return True
        except Exception:
            self.available = False
            self.icon = None
            return False

    def _wrap(self, cb):
        """托盘回调跑在别的线程，必须弹回 tk 主线程执行。"""
        def _fn(icon=None, item=None):
            self.app.call_on_ui(cb)
        return _fn

    def stop(self):
        if self.icon is not None:
            try:
                self.icon.stop()
            except Exception:
                pass
            self.icon = None
            return True
        return False

    def can_fully_hide(self):
        """有托盘图标就可以放心全隐藏。"""
        return self.icon is not None


class NullTray(TrayController):
    """🔴 无托盘降级路径（当前生效）。

    恢复通道优先级：全局热键 → 迷你角标。
    """

    def __init__(self, app):
        TrayController.__init__(self, app)
        self.available = False
        self.hotkey_ok = False

    def start(self):
        """尝试注册全局热键 `Ctrl+Alt+F`。"""
        from pyapp import win_native

        self.hotkey = win_native.register_hotkey(
            self.app.root, self.app.toggle_window,
            ctrl=True, alt=True, shift=False, key="F")
        self.hotkey_ok = bool(self.hotkey and self.hotkey.ok)
        self.app.log.info(
            "[tray] 未检测到 pystray/Pillow，启用无托盘降级；全局热键注册%s"
            % ("成功（Ctrl+Alt+F）" if self.hotkey_ok else "失败，将保留迷你角标"))
        return self.hotkey_ok

    def stop(self):
        if self.hotkey is not None:
            self.hotkey.unregister()
            self.hotkey = None
            return True
        return False

    def can_fully_hide(self):
        """🔴 只有热键可用时才允许完全隐藏，否则必须留迷你角标。"""
        return self.hotkey_ok


def make_tray(app, no_tray=False):
    """按依赖可用性选择托盘实现（ARCHITECTURE §7.5）。

    :param no_tray: CLI `--no-tray`，强制走降级路径
    :returns: :class:`TrayController` 子类实例
    """
    if no_tray:
        return NullTray(app)
    try:
        from fishtank.engine_bootstrap import deps
        if deps.has("pystray") and deps.has("PIL"):
            return PystrayTray(app)
    except Exception:
        pass
    return NullTray(app)
