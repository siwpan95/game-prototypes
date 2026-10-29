"""视觉特效 — 回声波纹 + 粒子"""

import tkinter as tk
from camera import Camera


class EchoRipple:
    """腾空时触发的回声波纹（世界坐标存储）。"""

    def __init__(self, canvas: tk.Canvas, x: float, y: float, camera: Camera):
        self.canvas = canvas
        self.x = x
        self.y = y
        self.radius = 5.0
        self.alpha = 1.0
        sx, sy = camera.world_to_screen(x, y)
        self._id = canvas.create_oval(
            sx - self.radius, sy - self.radius,
            sx + self.radius, sy + self.radius,
            outline="#00FFFF", width=2, fill="")

    def update(self, camera: Camera) -> bool:
        self.radius += 8
        self.alpha -= 0.02
        if self.alpha <= 0:
            self.canvas.delete(self._id)
            return False
        sx, sy = camera.world_to_screen(self.x, self.y)
        self.canvas.itemconfig(self._id, outline=self._fade("#00FFFF", self.alpha))
        self.canvas.coords(self._id,
                           sx - self.radius, sy - self.radius,
                           sx + self.radius, sy + self.radius)
        return True

    @staticmethod
    def _fade(hex_color: str, alpha: float) -> str:
        hex_color = hex_color.lstrip('#')
        if len(hex_color) == 3:
            hex_color = ''.join(c * 2 for c in hex_color)
        r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
        f = max(0.0, alpha)
        return f"#{int(r * f):02x}{int(g * f):02x}{int(b * f):02x}"


class Particle:
    """单个粒子（世界坐标存储）。"""

    def __init__(self, canvas: tk.Canvas, x: float, y: float,
                 vx: float, vy: float, color: str, ttl: int, camera: Camera):
        self.canvas = canvas
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.color = color
        self.ttl = ttl
        self.age = ttl
        sx, sy = camera.world_to_screen(x, y)
        self._id = canvas.create_oval(
            sx - 2, sy - 2, sx + 2, sy + 2, fill=color, outline="")

    def update(self, camera: Camera) -> bool:
        self.x += self.vx
        self.y += self.vy
        self.age -= 1
        if self.age <= 0:
            self.canvas.delete(self._id)
            return False
        sx, sy = camera.world_to_screen(self.x, self.y)
        r = max(0.5, 2.0 * self.age / self.ttl)
        self.canvas.coords(self._id, sx - r, sy - r, sx + r, sy + r)
        self.canvas.itemconfig(self._id, fill=self._fade(self.color, self.age / self.ttl))
        return True

    @staticmethod
    def _fade(hex_color: str, alpha: float) -> str:
        hex_color = hex_color.lstrip('#')
        if len(hex_color) == 3:
            hex_color = ''.join(c * 2 for c in hex_color)
        r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
        f = max(0.0, alpha)
        return f"#{int(r * f):02x}{int(g * f):02x}{int(b * f):02x}"
