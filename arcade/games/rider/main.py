"""Line Rider Pro — 主入口 + 应用整合"""

import math
import time
import random
import tkinter as tk
from typing import List

from config import (WIDTH, HEIGHT, BG, FPS, DT, MATERIALS, DEFAULT_MATERIAL,
                    TRACK_SAMPLE_STEPS)
from camera import Camera
from track import Track, bezier_point
from physics import ChaoticPhysics, step_physics
from rider_entity import Rider
from audio import AudioSynthesizer
from effects import EchoRipple, Particle


# ─── 轨道绘制预览工具 ───────────────────────────────

def get_bezier_preview_line(control_points, steps=40):
    """返回贝塞尔预览点列表（世界坐标）"""
    pts = []
    for i in range(steps):
        t = i / (steps - 1)
        pts.append(bezier_point(control_points, t))
    return pts


# ─── 主应用 ──────────────────────────────────────

class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.canvas = tk.Canvas(root, width=WIDTH, height=HEIGHT, bg=BG, highlightthickness=0)
        self.canvas.pack()

        # ── 模块 ──
        self.camera = Camera(WIDTH, HEIGHT)
        self.physics = ChaoticPhysics()
        self.rider = Rider(self.canvas)
        self.audio = AudioSynthesizer()
        self.tracks: List[Track] = []
        self.ripples: List[EchoRipple] = []
        self.particles: List[Particle] = []

        # ── 状态 ──
        self.drawing_pts: List[tuple] = []          # 当前绘制中的屏幕点
        self.current_material = DEFAULT_MATERIAL
        self.running = False
        self.last_time = time.time()
        self.preview_ids: List[int] = []

        # ── Track 的 canvas 渲染 ID（用于更新视口）──
        self._track_line_ids: List[int] = []
        self._last_cam_x = 0.0
        self._last_cam_y = 0.0

        # ── 事件绑定 ──
        self.canvas.bind("<Button-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        root.bind("<space>", self.toggle_play)
        for i in range(1, 6):
            root.bind(str(i), lambda e, m=i: self.set_material(m))
        root.bind("r", self.reset)
        root.bind("c", lambda e: self._reset_camera())

        # ── HUD ──
        self.status_label = tk.Label(
            root, text="1-5 材质 | Space 开始 | R 重置 | C 重置镜头",
            bg="#111122", fg="#00FFFF", font=("Microsoft YaHei", 11))
        self.status_label.place(x=10, y=10)

        self.mat_label = tk.Label(
            root, text=self._mat_text(),
            bg="#111122", fg=MATERIALS[self.current_material].color,
            font=("Microsoft YaHei", 11))
        self.mat_label.place(x=10, y=36)

        self.speed_label = tk.Label(
            root, text="", bg="#111122", fg="#FFFFFF",
            font=("Consolas", 11))
        self.speed_label.place(x=WIDTH - 160, y=10)

        # ── 初始提示 ──
        self._show_title()

        # ── 启动音频 ──
        self.audio.start()

    # ── UI 工具 ───────────────────────────────

    def _mat_text(self):
        return f"材质: {MATERIALS[self.current_material].name}"

    def set_material(self, mat_id):
        self.current_material = mat_id
        self.mat_label.config(
            text=self._mat_text(), fg=MATERIALS[mat_id].color)

    def _show_title(self):
        self.canvas.create_text(
            WIDTH // 2, HEIGHT // 2,
            text="Line Rider Pro\n\n"
                 "左键拖拽绘制轨道 | 1-5 切换材质\n"
                 "Space 开始/暂停 | R 重置 | C 重置镜头",
            fill="#5577AA", font=("Microsoft YaHei", 16), justify="center",
            tags="title")

    def _reset_camera(self):
        self.camera.cx = self.camera.cy = 0
        self.camera._target_cx = self.camera._target_cy = 0

    # ── 输入处理 ──────────────────────────────

    def on_press(self, e):
        if self.running:
            return
        wx, wy = self.camera.screen_to_world(e.x, e.y)
        self.drawing_pts = [(wx, wy)]

    def on_drag(self, e):
        if self.running:
            return
        wx, wy = self.camera.screen_to_world(e.x, e.y)
        self.drawing_pts.append((wx, wy))

        # 贝塞尔预览：取前 4 个点和最后 3 个点组成控制点
        if len(self.drawing_pts) >= 4:
            cp = [self.drawing_pts[0],
                  self.drawing_pts[-3],
                  self.drawing_pts[-2],
                  self.drawing_pts[-1]]
            pts = get_bezier_preview_line(cp)
            self._draw_preview(pts)

    def _draw_preview(self, world_pts):
        """绘制预览曲线（屏幕坐标）"""
        self.canvas.delete("preview")
        screen_pts = []
        for wx, wy in world_pts:
            sx, sy = self.camera.world_to_screen(wx, wy)
            screen_pts.extend([sx, sy])
        self.preview_ids = [self.canvas.create_line(
            screen_pts, smooth=True,
            fill=MATERIALS[self.current_material].color,
            width=4, tags="preview")]

    def on_release(self, e):
        if self.running:
            return
        if len(self.drawing_pts) >= 4:
            cp = [self.drawing_pts[0],
                  self.drawing_pts[-3],
                  self.drawing_pts[-2],
                  self.drawing_pts[-1]]
            track = Track(cp, self.current_material)
            self.tracks.append(track)
            self._render_track(track)
        self.drawing_pts = []
        self.canvas.delete("preview")

    def _render_track(self, track: Track):
        """在画布上绘制一条轨道（屏幕坐标），返回 line id"""
        screen_pts = []
        for (x1, y1, x2, y2, _, _) in track.segments:
            sx1, sy1 = self.camera.world_to_screen(x1, y1)
            sx2, sy2 = self.camera.world_to_screen(x2, y2)
            screen_pts.extend([sx1, sy1, sx2, sy2])
            lid = self.canvas.create_line(
                screen_pts, smooth=True,
                fill=track.material.color, width=5,
                capstyle=tk.ROUND, joinstyle=tk.ROUND, tags="track_line")
            self._track_line_ids.append(lid)

    def _redraw_all_tracks(self):
        """相机移动后重绘所有轨道"""
        self.canvas.delete("track_line")
        self._track_line_ids.clear()
        for track in self.tracks:
            screen_pts = []
            for (x1, y1, x2, y2, _, _) in track.segments:
                sx1, sy1 = self.camera.world_to_screen(x1, y1)
                sx2, sy2 = self.camera.world_to_screen(x2, y2)
                screen_pts.extend([sx1, sy1, sx2, sy2])
            lid = self.canvas.create_line(
                screen_pts, smooth=True,
                fill=track.material.color, width=5,
                capstyle=tk.ROUND, joinstyle=tk.ROUND, tags="track_line")
            self._track_line_ids.append(lid)

    # ── 游戏循环 ──────────────────────────────

    def toggle_play(self, e=None):
        if not self.running:
            self.running = True
            if not self.rider.alive:
                # 在屏幕中央生成 rider
                spawn_x = self.camera.cx + WIDTH / 2
                spawn_y = self.camera.cy + 100
                self.rider.spawn(spawn_x, spawn_y)
            self.canvas.delete("title")
            self.status_label.config(text="播放中…  Space 暂停  R 重置")
            self._game_loop()
        else:
            self.running = False
            self.status_label.config(text="已暂停  Space 继续")

    def _game_loop(self):
        if not self.running:
            return

        # ── 物理一步 ──
        state = step_physics(
            self.rider.x, self.rider.y,
            self.rider.vx, self.rider.vy,
            self.rider.radius, self.rider.mass,
            self.tracks, self.physics)

        self.rider.apply_state(state)

        # ── 边界兜底 ──
        if self.rider.y > 5000:
            self.rider.alive = False
            self.status_label.config(text="Rider 坠入深渊！按 R 重置")
            self.running = False

        # ── 音频 ──
        mat = state.get('material')
        acoustic = self.rider.get_acoustic_params(mat)
        self.audio.update_params(acoustic)

        # ── 腾空波纹 ──
        if self.rider.just_took_off:
            self.ripples.append(EchoRipple(self.canvas, self.rider.x, self.rider.y, self.camera))
            # 粒子爆发
            for _ in range(8):
                self.particles.append(Particle(
                    self.canvas, self.rider.x, self.rider.y,
                    (random.random() - 0.5) * 6,
                    (random.random() - 0.5) * 6 - 2,
                    "#00FFFF", ttl=15, camera=self.camera))

        # ── 触地粒子 ──
        if self.rider.on_ground and not self.rider._last_on_ground and self.rider.speed > 200:
            color = mat.color if mat else "#00FFFF"
            for _ in range(5):
                self.particles.append(Particle(
                    self.canvas, self.rider.x, self.rider.y,
                    (random.random() - 0.5) * 3,
                    random.random() * 5 - 5,
                    color, ttl=12, camera=self.camera))

        # ── 相机跟随 ──
        if self.rider.alive:
            self.camera.follow(self.rider.x, self.rider.y)

        self.camera.update()

        # ── 渲染（仅相机移动时重绘轨道）──
        if abs(self.camera.cx - getattr(self, '_last_cam_x', 0)) > 0.5 or \
           abs(self.camera.cy - getattr(self, '_last_cam_y', 0)) > 0.5:
            self._redraw_all_tracks()
            self._last_cam_x = self.camera.cx
            self._last_cam_y = self.camera.cy
        self.rider.render(self.camera)

        # 更新特效
        self.ripples = [r for r in self.ripples if r.update(self.camera)]
        self.particles = [p for p in self.particles if p.update(self.camera)]

        # ── 混沌全局参数 ──
        self.physics.turbulence = 0.3 + 0.2 * math.sin(time.time() * 0.5)
        self.physics.wind = 0.5 * math.sin(time.time() * 0.3)

        # ── HUD ──
        speed = self.rider.speed
        self.speed_label.config(text=f"速度: {speed:.0f} px/s")

        self.root.after(16, self._game_loop)

    # ── 重置 ─────────────────────────────────

    def reset(self, e=None):
        self.running = False
        self.canvas.delete("all")
        self.canvas.delete("track_line")
        self._track_line_ids.clear()
        self.tracks.clear()
        self.ripples.clear()
        self.particles.clear()
        self.rider.alive = False
        self.rider.clear()
        self._reset_camera()
        self._last_cam_x = 0.0
        self._last_cam_y = 0.0
        self._show_title()
        self.status_label.config(text="1-5 材质 | Space 开始 | R 重置 | C 重置镜头")
        self.speed_label.config(text="")

    def on_close(self):
        self.audio.stop()
        self.root.destroy()


# ─── 入口 ──────────────────────────────────────

if __name__ == "__main__":
    root = tk.Tk()
    root.title("Line Rider Pro")
    root.geometry(f"{WIDTH}x{HEIGHT}")
    root.resizable(False, False)
    app = App(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()
