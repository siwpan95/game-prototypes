"""视口相机 — 平滑跟随 + 坐标转换"""

from config import CAMERA_SMOOTH


class Camera:
    """世界坐标系中的视口窗口。

    内部保存视口左上角在世界中的位置 (cx, cy)。
    提供 world ↔ screen 坐标互转。
    """

    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        # 视口左上角的世界坐标
        self.cx = 0.0
        self.cy = 0.0
        # 目标位置（lerp 目标）
        self._target_cx = 0.0
        self._target_cy = 0.0

    def follow(self, world_x: float, world_y: float):
        """让视口中心跟随世界坐标 (world_x, world_y)"""
        self._target_cx = world_x - self.width / 2
        self._target_cy = world_y - self.height / 2

    def update(self):
        """每帧调用，平滑插值到目标位置"""
        self.cx += (self._target_cx - self.cx) * CAMERA_SMOOTH
        self.cy += (self._target_cy - self.cy) * CAMERA_SMOOTH

    def world_to_screen(self, wx: float, wy: float):
        """世界坐标 → 屏幕坐标"""
        return wx - self.cx, wy - self.cy

    def screen_to_world(self, sx: float, sy: float):
        """屏幕坐标 → 世界坐标"""
        return sx + self.cx, sy + self.cy
