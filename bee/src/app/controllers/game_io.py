# -*- coding: utf-8 -*-
"""
游戏 I/O 模块 - 暂停 / 静音（存档读档已迁入 SimCore）

以 Mixin 方式注入 GameController。
  - save_game         -> 委派给 self.sim.save_game()
  - _toggle_pause     -> 通过 GameController.paused 属性代理到 SimCore
  - _toggle_mute      -> 切换共享的 AudioService 实例

真实的存读档逻辑见 src.sim_core.engine.SimCore.save_game / _load_game。
"""


class GameIOMixin:
    """I/O Mixin — 提供 save_game / _toggle_pause / _toggle_mute"""

    def save_game(self):
        """保存游戏（委派给模拟内核）"""
        self.sim.save_game()

    def _toggle_pause(self):
        """切换暂停/继续"""
        self.paused = not self.paused
        status = "\u5df2\u6682\u505c" if self.paused else "\u7ee7\u7eed"
        self._add_log(f"[\u7cfb\u7edf] {status}")
        # 刷新托盘菜单（如果正在运行）
        if hasattr(self, '_refresh_tray_menu'):
            self._refresh_tray_menu()

    def _toggle_mute(self):
        """切换静音状态"""
        if hasattr(self, 'audio') and self.audio:
            muted = self.audio.toggle_mute()
            status = "已静音" if muted else "已取消静音"
            self._add_log(f"[系统] {status}")
            # 刷新托盘菜单（如果正在运行）
            if hasattr(self, '_refresh_tray_menu'):
                self._refresh_tray_menu()
