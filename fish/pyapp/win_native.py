"""Windows 原生能力封装（贴边吸附 / 鼠标穿透 / 全屏让位 / 全局热键）。

🔴 禁止 `from __future__ import annotations`（E6）。
🔴 非 Windows 平台**全部退化为 no-op**，绝不抛异常（ARCHITECTURE §7.2 表格要求）。

设计原则：本模块是"尽力而为"层。每个能力都返回布尔值告知调用方是否真的
生效，调用方据此决定降级策略 —— 尤其是 :func:`register_hotkey`：
注册失败时 `NullTray` **必须禁止完全隐藏**（否则窗口再也找不回来）。
"""

import sys

IS_WINDOWS = sys.platform.startswith("win")

_WS_EX_TRANSPARENT = 0x00000020
_WS_EX_LAYERED = 0x00080000
_GWL_EXSTYLE = -20

# RegisterHotKey 修饰符
_MOD_ALT = 0x0001
_MOD_CONTROL = 0x0002
_MOD_SHIFT = 0x0004
_MOD_NOREPEAT = 0x4000

_HOTKEY_ID = 0xF15A
"""本程序热键的唯一 id（随便取的常数，只要进程内不冲突）。"""


def _user32():
    """拿到 user32，失败返回 None。"""
    if not IS_WINDOWS:
        return None
    try:
        import ctypes
        return ctypes.windll.user32
    except (ImportError, AttributeError, OSError):
        return None


def hwnd_of(widget):
    """取 tkinter 窗口的 HWND；失败返回 0。"""
    if not IS_WINDOWS or widget is None:
        return 0
    try:
        return int(widget.winfo_id())
    except (AttributeError, ValueError, RuntimeError):
        return 0


def toplevel_hwnd(widget):
    """取顶层窗口 HWND。

    tkinter 的 `winfo_id()` 给的是内部子窗口，`overrideredirect` 之后
    改扩展样式必须作用在**顶层**窗口上，所以要往上找一层 parent。
    """
    u = _user32()
    h = hwnd_of(widget)
    if u is None or not h:
        return h
    try:
        parent = u.GetParent(h)
        return int(parent) if parent else h
    except (AttributeError, OSError, ValueError):
        return h


# ══════════════════════════════════════════════════════════════
#  贴边吸附
# ══════════════════════════════════════════════════════════════

def screen_size(widget):
    """屏幕逻辑尺寸 (w, h)。优先用 tk 自己的值（多屏下更稳）。"""
    try:
        return int(widget.winfo_screenwidth()), int(widget.winfo_screenheight())
    except (AttributeError, RuntimeError):
        pass
    u = _user32()
    if u is not None:
        try:
            return int(u.GetSystemMetrics(0)), int(u.GetSystemMetrics(1))
        except (AttributeError, OSError):
            pass
    return (1920, 1080)


def snap_position(x, y, win_w, win_h, screen_w, screen_h, snap_px):
    """把窗口位置吸附到屏幕边缘。

    纯函数（方便单测）：距离任一边小于 `snap_px` 就贴上去。

    :returns: (new_x, new_y)
    """
    s = max(0, int(snap_px))
    x = int(x)
    y = int(y)
    if s <= 0:
        return x, y
    if abs(x) <= s:
        x = 0
    elif abs((x + win_w) - screen_w) <= s:
        x = int(screen_w - win_w)
    if abs(y) <= s:
        y = 0
    elif abs((y + win_h) - screen_h) <= s:
        y = int(screen_h - win_h)
    return x, y


# ══════════════════════════════════════════════════════════════
#  鼠标穿透（P1-14）
# ══════════════════════════════════════════════════════════════

def set_click_through(root, enable):
    """开关鼠标穿透。

    首选纯 tk 的 `-disabled`（实测可用）；不生效再用 ctypes 设
    `WS_EX_TRANSPARENT | WS_EX_LAYERED`。

    🔴 调用方必须保证穿透时仍有退出通道（托盘菜单或全局热键），
    否则窗口会变成一块点不到的"幽灵"。

    :returns: 是否成功
    """
    if root is None:
        return False
    ok = False
    try:
        root.attributes("-disabled", bool(enable))
        ok = True
    except Exception:
        ok = False

    u = _user32()
    if u is None:
        return ok
    h = toplevel_hwnd(root)
    if not h:
        return ok
    try:
        import ctypes
        get_fn = getattr(u, "GetWindowLongPtrW", None) or u.GetWindowLongW
        set_fn = getattr(u, "SetWindowLongPtrW", None) or u.SetWindowLongW
        style = int(get_fn(ctypes.c_void_p(h), _GWL_EXSTYLE))
        if enable:
            style |= (_WS_EX_TRANSPARENT | _WS_EX_LAYERED)
        else:
            style &= ~_WS_EX_TRANSPARENT
        set_fn(ctypes.c_void_p(h), _GWL_EXSTYLE, style)
        return True
    except Exception:
        return ok


# ══════════════════════════════════════════════════════════════
#  全屏让位（Q10）
# ══════════════════════════════════════════════════════════════

def foreground_is_fullscreen(widget=None):
    """前台窗口是否占满整屏（看视频/玩游戏时应该让位）。

    非 Windows 或查询失败一律返回 False —— 让位是"锦上添花"，
    查不到就当没有全屏，绝不因此影响主流程。
    """
    u = _user32()
    if u is None:
        return False
    try:
        import ctypes
        from ctypes import wintypes

        hwnd = u.GetForegroundWindow()
        if not hwnd:
            return False
        # 桌面/任务栏本身不算全屏
        shell = u.GetShellWindow()
        if shell and int(hwnd) == int(shell):
            return False
        rect = wintypes.RECT()
        if not u.GetWindowRect(ctypes.c_void_p(int(hwnd)), ctypes.byref(rect)):
            return False
        sw = int(u.GetSystemMetrics(0))
        sh = int(u.GetSystemMetrics(1))
        return (rect.left <= 0 and rect.top <= 0
                and rect.right >= sw and rect.bottom >= sh)
    except Exception:
        return False


# ══════════════════════════════════════════════════════════════
#  全局热键（NullTray 的救命稻草）
# ══════════════════════════════════════════════════════════════

class HotkeyRegistration(object):
    """一次全局热键注册的句柄。

    :ivar ok: 是否注册成功。**False 时调用方禁止完全隐藏窗口。**
    """

    __slots__ = ("ok", "_hwnd", "_id", "_polling")

    def __init__(self, ok=False, hwnd=0, hid=_HOTKEY_ID):
        self.ok = bool(ok)
        self._hwnd = hwnd
        self._id = hid
        self._polling = False

    def unregister(self):
        """注销热键；未注册成功时是空操作。"""
        if not self.ok:
            return False
        u = _user32()
        if u is None:
            return False
        try:
            import ctypes
            u.UnregisterHotKey(ctypes.c_void_p(self._hwnd) if self._hwnd else None,
                               self._id)
        except Exception:
            return False
        self.ok = False
        return True


def register_hotkey(root, callback, ctrl=True, alt=True, shift=False, key="F"):
    """注册全局热键（默认 `Ctrl+Alt+F`）呼出鱼缸。

    实现说明：tkinter 没法直接进 Windows 消息循环拿 `WM_HOTKEY`，
    所以这里用 `RegisterHotKey(NULL, ...)` 把热键投递到**当前线程队列**，
    再用 `root.after` 轮询 `PeekMessage` 取。轮询间隔 120ms 对
    "呼出窗口"这种低频操作完全够用，CPU 开销可忽略（P0-22）。

    :param callback: 命中热键时调用（无参）
    :returns: :class:`HotkeyRegistration`；`ok=False` 表示注册失败
    """
    u = _user32()
    if u is None or root is None:
        return HotkeyRegistration(False)

    mods = _MOD_NOREPEAT
    if ctrl:
        mods |= _MOD_CONTROL
    if alt:
        mods |= _MOD_ALT
    if shift:
        mods |= _MOD_SHIFT
    vk = ord(str(key or "F")[0].upper())

    try:
        import ctypes
        from ctypes import wintypes
        if not u.RegisterHotKey(None, _HOTKEY_ID, mods, vk):
            return HotkeyRegistration(False)
    except Exception:
        return HotkeyRegistration(False)

    reg = HotkeyRegistration(True, 0, _HOTKEY_ID)
    msg = wintypes.MSG()
    wm_hotkey = 0x0312

    def _poll():
        if not reg.ok:
            return
        try:
            while u.PeekMessageW(ctypes.byref(msg), None, wm_hotkey, wm_hotkey, 1):
                if int(msg.wParam) == _HOTKEY_ID:
                    try:
                        callback()
                    except Exception:
                        pass
        except Exception:
            pass
        try:
            root.after(120, _poll)
        except Exception:
            reg.ok = False

    try:
        root.after(120, _poll)
    except Exception:
        reg.unregister()
        return HotkeyRegistration(False)
    return reg
