# -*- coding: utf-8 -*-
"""
游戏系统托盘模块 - 最小化到托盘 / 恢复 / 退出
集成暂停/静音控制

以 Mixin 方式注入 GameController。
"""

import os
import sys
import threading

try:
    import pystray
    from PIL import Image, ImageDraw
    _TRAY_AVAILABLE = True
except ImportError:
    _TRAY_AVAILABLE = False


class SystemTrayMixin:
    """系统托盘 Mixin — 提供托盘图标、菜单及控制功能"""

    def _get_ico_path(self):
        """获取项目图标的绝对路径（开发环境或打包后均适用）"""
        if getattr(sys, 'frozen', False):
            # PyInstaller 打包后：优先从 _MEIPASS 读取（datas 打包的文件）
            meipass = getattr(sys, '_MEIPASS', None)
            if meipass:
                path = os.path.join(meipass, "BeeIdleRPG.ico")
                if os.path.exists(path):
                    return path
            # 回退：exe 同目录下有 ico 文件
            path = os.path.join(os.path.dirname(sys.executable), "BeeIdleRPG.ico")
            if os.path.exists(path):
                return path
            # 都找不到：返回 _MEIPASS 路径（让后续 try/except 走绘图回退）
            return os.path.join(meipass, "BeeIdleRPG.ico") if meipass else ""
        else:
            base = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "..")
            return os.path.normpath(os.path.join(base, "BeeIdleRPG.ico"))

    def _create_tray_image(self):
        """加载或绘制托盘图标，优先使用 .ico 文件"""
        ico_path = self._get_ico_path()
        if _TRAY_AVAILABLE and os.path.exists(ico_path):
            try:
                img = Image.open(ico_path)
                return img.resize((64, 64), Image.LANCZOS)
            except Exception:
                pass
        # 回退：程序化绘制蜜蜂图标
        img = Image.new("RGB", (64, 64), "#0d1117")
        draw = ImageDraw.Draw(img)
        draw.ellipse([16, 20, 48, 52], fill="#facc15", outline="#e6cc80", width=2)
        draw.rectangle([26, 26, 38, 34], fill="#0d1117")
        draw.rectangle([26, 38, 38, 46], fill="#0d1117")
        draw.arc([22, 4, 34, 18], start=200, end=340, fill="#e6cc80", width=2)
        draw.arc([30, 4, 42, 18], start=200, end=340, fill="#e6cc80", width=2)
        return img

    def _build_tray_menu(self):
        """构建托盘菜单（根据当前状态动态生成）"""
        # 状态文本
        pause_text = "继续游戏" if self.paused else "暂停游戏"
        mute_text = "取消静音" if getattr(self.audio, 'muted', False) else "静音"
        mute_icon = "🔇 " if getattr(self.audio, 'muted', False) else "🔊 "

        return pystray.Menu(
            pystray.MenuItem("显示窗口", self._restore_from_tray, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                pause_text,
                self._tray_toggle_pause,
            ),
            pystray.MenuItem(
                f"{mute_icon}{mute_text}",
                self._tray_toggle_mute,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("退出游戏", self._exit_from_tray),
        )

    def _minimize_to_tray(self):
        """最小化到系统托盘"""
        if self._tray_running:
            return
        self.root.withdraw()
        menu = self._build_tray_menu()
        self.tray_icon = pystray.Icon(
            "蜂蜜挂机", self._create_tray_image(), "蜂蜜挂机 RPG", menu
        )
        self._tray_running = True
        threading.Thread(target=self.tray_icon.run, daemon=True).start()
        self.root.after(100, lambda: None)

    def _refresh_tray_menu(self):
        """刷新托盘菜单（状态变化时调用）"""
        if not self._tray_running or not self.tray_icon:
            return
        try:
            new_menu = self._build_tray_menu()
            self.tray_icon.menu = new_menu
        except Exception:
            pass

    def _restore_from_tray(self, icon=None, item=None):
        """从托盘恢复窗口"""
        self.root.after(0, self.root.deiconify)
        self.root.after(0, self.root.lift)
        if self.tray_icon:
            self.tray_icon.stop()
            self.tray_icon = None
            self._tray_running = False

    def _exit_from_tray(self, icon=None, item=None):
        """从托盘退出游戏"""
        self._tray_running = False
        self.running = False
        self.audio.stop_all()
        self.save_game()
        if self.tray_icon:
            self.tray_icon.stop()
            self.tray_icon = None
        self.root.after(0, self.root.destroy)

    # ---- 托盘菜单控制回调 ----

    def _tray_toggle_pause(self, icon=None, item=None):
        """托盘菜单：切换暂停/继续"""
        self._toggle_pause()
        self._refresh_tray_menu()

    def _tray_toggle_mute(self, icon=None, item=None):
        """托盘菜单：切换静音"""
        muted = self.audio.toggle_mute()
        status = "已静音" if muted else "已取消静音"
        self._add_log(f"[系统] {status}")
        self._refresh_tray_menu()

    @property
    def tray_available(self) -> bool:
        """系统托盘功能是否可用"""
        return _TRAY_AVAILABLE
