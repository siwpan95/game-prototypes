import tkinter as tk
import math
import threading
import numpy as np
# import pyaudio  # 已替换为 sounddevice
import sounddevice as sd
import time
import random          # 原代码中使用了 random.random() 但没有导入
from dataclasses import dataclass
from typing import List, Tuple, Optional

# ======================
# 全局配置
# ======================
WIDTH, HEIGHT = 1200, 800
BG = "#050510"
FPS = 60
DT = 1 / FPS

# 音频配置
SAMPLE_RATE = 44100
BUFFER_SIZE = 1024
MAX_FREQ = 2000

# ======================
# 材质定义（摩擦系数决定颜色和物理）
# ======================
@dataclass
class Material:
    name: str
    color: str
    friction: float      # 0-1: 摩擦系数
    restitution: float   # 弹性恢复系数
    chaos_factor: float  # 混沌强度
    base_harmonic: int   # 基频谐波倍数

MATERIALS = {
    1: Material("❄ 冰面", "#00FFFF", 0.99, 0.95, 0.05, 1),
    2: Material("🪵 木质", "#DEB887", 0.85, 0.60, 0.15, 2),
    3: Material("🛞 橡胶", "#333333", 0.60, 0.30, 0.30, 3),
    4: Material("⚡ 加速", "#FF4500", 1.02, 1.20, 0.25, 4),
    5: Material("🌪 混沌", "#9400D3", 0.75, 0.80, 0.50, 5),  # 新增混沌材质
}

# ======================
# 混沌物理引擎
# ======================
class ChaoticPhysics:
    def __init__(self):
        self.gravity = 9.81 * 60
        self.air_density = 1.2
        self.drag_coeff = 0.47  # 球体阻力系数
        self.turbulence = 0.0
        self.wind = 0.0
        
    def apply_forces(self, rider, dt):
        """应用所有力：重力、空气阻力、混沌扰动"""
        # 重力
        rider.vy += self.gravity * dt
        
        # 空气阻力 (F_drag = 0.5 * ρ * v² * C_d * A)
        speed = math.hypot(rider.vx, rider.vy)
        if speed > 0:
            area = math.pi * (rider.radius ** 2) / 10000  # 归一化面积
            drag_force = 0.5 * self.air_density * (speed ** 2) * self.drag_coeff * area
            drag_acc = drag_force / rider.mass
            
            # 阻力方向与速度相反
            rider.vx -= (rider.vx / speed) * drag_acc * dt
            rider.vy -= (rider.vy / speed) * drag_acc * dt
        
        # 混沌扰动（随机风、湍流）
        chaos_x = math.sin(time.time() * 5 + rider.x * 0.01) * self.turbulence
        chaos_y = math.cos(time.time() * 3 + rider.y * 0.01) * self.turbulence * 0.5
        rider.vx += chaos_x * dt
        rider.vy += chaos_y * dt
        
        # 水平风
        rider.vx += self.wind * dt

# ======================
# 贝塞尔曲线轨道
# ======================
class BezierTrack:
    def __init__(self, control_points: List[Tuple[float, float]], material_id: int):
        self.control_points = control_points
        self.material = MATERIALS[material_id]
        self.segments = []
        self.color = self.material.color
        self._sample_curve()
    
    def _sample_curve(self, steps=50):
        """采样贝塞尔曲线为线段"""
        for i in range(steps):
            t0 = i / steps
            t1 = (i + 1) / steps
            x1, y1 = self._bezier(t0)
            x2, y2 = self._bezier(t1)
            self.segments.append((x1, y1, x2, y2))
    
    def _bezier(self, t: float) -> Tuple[float, float]:
        """三次贝塞尔曲线"""
        p0, p1, p2, p3 = self.control_points
        u = 1 - t
        x = u**3*p0[0] + 3*u**2*t*p1[0] + 3*u*t**2*p2[0] + t**3*p3[0]
        y = u**3*p0[1] + 3*u**2*t*p1[1] + 3*u*t**2*p2[1] + t**3*p3[1]
        return x, y
    
    def get_normal_at(self, x: float, y: float) -> Tuple[float, float]:
        """获取最近点的法线"""
        # 简化：返回垂直向上的法线
        return 0.0, -1.0

# ======================
# 小车
# ======================
class Rider:
    def __init__(self, canvas):
        self.canvas = canvas
        self.radius = 10
        self.mass = 1.0
        
        # 视觉元素
        self.body = canvas.create_oval(0, 0, self.radius*2, self.radius*2,
                                      fill="#FFFFFF", outline="#00FFFF", width=2)
        self.trail = []  # 轨迹点
        self.trail_ids = []
        
        # 物理状态
        self.x = 0.0
        self.y = 0.0
        self.vx = 0.0
        self.vy = 0.0
        self.on_ground = False
        self.last_on_ground = False
        self.alive = False
        
        # 声学参数
        self.base_freq = 220.0
        self.harmonics = [1.0, 0.5, 0.3, 0.1]
        
    def spawn(self, x: float, y: float):
        self.x = x
        self.y = y
        self.vx = 0.0
        self.vy = 0.0
        self.alive = True
        self._update_visual()
    
    def update(self, tracks: List[BezierTrack], physics: ChaoticPhysics):
        if not self.alive:
            return
        
        # 保存上一帧状态
        self.last_on_ground = self.on_ground
        self.on_ground = False
        
        # 应用混沌物理
        physics.apply_forces(self, DT)
        
        # 预测位置
        nx = self.x + self.vx * DT
        ny = self.y + self.vy * DT
        
        # 碰撞检测
        closest_dist = float('inf')
        closest_push_dir = (0.0, 1.0)   # 推出方向（指向小车）
        closest_material = MATERIALS[2]
        
        for track in tracks:
            for seg in track.segments:
                x1, y1, x2, y2 = seg
                dist, nearest_x, nearest_y = self._point_to_segment_nearest(nx, ny, x1, y1, x2, y2)
                if dist < closest_dist:
                    closest_dist = dist
                    # 推出方向：从小车预测位置指向最近点（远离线段）
                    push_x = nx - nearest_x
                    push_y = ny - nearest_y
                    push_len = math.hypot(push_x, push_y)
                    if push_len > 0:
                        closest_push_dir = (push_x / push_len, push_y / push_len)
                    else:
                        closest_push_dir = (0.0, -1.0)  # 重合时默认向上
                    closest_material = track.material

        # 碰撞响应
        if closest_dist < self.radius + 5:
            self.on_ground = True
            
            # 将小车推出到轨道表面
            overlap = self.radius + 5 - closest_dist
            self.x = nx + closest_push_dir[0] * overlap
            self.y = ny + closest_push_dir[1] * overlap
            
            # 速度分解为切向和法向，保留切向速度（摩擦减速）
            v_n = self.vx * closest_push_dir[0] + self.vy * closest_push_dir[1]
            v_t = (self.vx - v_n * closest_push_dir[0],
                   self.vy - v_n * closest_push_dir[1])
            
            # 法向反弹（受弹性影响）
            bounce = closest_material.restitution
            self.vx = v_t[0] + (-v_n) * bounce * closest_push_dir[0]
            self.vy = v_t[1] + (-v_n) * bounce * closest_push_dir[1]
            
            # 切向摩擦
            friction = closest_material.friction
            self.vx -= v_t[0] * (1 - friction) * 0.1
            self.vy -= v_t[1] * (1 - friction) * 0.1
            
            # 混沌扰动
            chaos = closest_material.chaos_factor
            self.vx += (random.random() - 0.5) * chaos * 5
            self.vy += (random.random() - 0.5) * chaos * 5
        else:
            self.x = nx
            self.y = ny
            self.on_ground = False
        
        # 边界检查
        if self.y > HEIGHT - self.radius:
            self.y = HEIGHT - self.radius
            self.vy = -self.vy * 0.3
            self.on_ground = True
        
        # 更新轨迹
        self.trail.append((self.x, self.y))
        if len(self.trail) > 50:
            self.trail.pop(0)
        
        self._update_visual()
        
        # 返回声学参数
        return self._get_acoustic_parameters(closest_material)

    def _point_to_segment_nearest(self, px, py, x1, y1, x2, y2):
        """返回 (距离, 最近点x, 最近点y)"""
        dx = x2 - x1
        dy = y2 - y1
        if dx == 0 and dy == 0:
            return math.hypot(px - x1, py - y1), x1, y1
        
        t = ((px - x1) * dx + (py - y1) * dy) / (dx*dx + dy*dy)
        t = max(0, min(1, t))
        near_x = x1 + t * dx
        near_y = y1 + t * dy
        return math.hypot(px - near_x, py - near_y), near_x, near_y
    
    def _point_to_segment_distance(self, px, py, x1, y1, x2, y2):
        """计算点到线段的距离"""
        dx = x2 - x1
        dy = y2 - y1
        if dx == 0 and dy == 0:
            return math.hypot(px - x1, py - y1)
        
        t = ((px - x1) * dx + (py - y1) * dy) / (dx*dx + dy*dy)
        t = max(0, min(1, t))
        
        proj_x = x1 + t * dx
        proj_y = y1 + t * dy
        
        return math.hypot(px - proj_x, py - proj_y)
    
    def _get_acoustic_parameters(self, material: Material):
        """将物理状态转换为声学参数"""
        speed = math.hypot(self.vx, self.vy)
        height = max(1, HEIGHT - self.y)  # 反转高度
        
        # 基频：基于高度和速度
        base_freq = 110 + (1000 / height) + speed * 0.5
        
        # 谐波：基于材质
        harmonics = [1.0]
        for i in range(1, material.base_harmonic + 1):
            harmonics.append(1.0 / i)
        
        # 音量：基于速度
        volume = min(0.8, speed / 1000)
        
        # 混沌调制
        chaos = material.chaos_factor
        freq_mod = 1.0 + math.sin(time.time() * 10) * chaos * 0.1
        
        return {
            'freq': base_freq * freq_mod,
            'harmonics': harmonics,
            'volume': volume,
            'chaos': chaos,
            'on_ground': self.on_ground
        }
    
    def _update_visual(self):
        """更新视觉"""
        self.canvas.coords(self.body,
                          self.x - self.radius, self.y - self.radius,
                          self.x + self.radius, self.y + self.radius)
        
        # 更新轨迹（修正：去掉无效的 alpha 参数）
        if len(self.trail) > 1:
            # 删除旧轨迹线
            if self.trail_ids:
                self.canvas.delete(self.trail_ids.pop())
            # 绘制新轨迹线，用浅青色
            self.trail_ids.append(
                self.canvas.create_line(self.trail, smooth=True, 
                                       fill="#00FFFF", width=1)
            )

# ======================
# 实时音频合成器（使用 sounddevice）
# ======================
class AudioSynthesizer:
    def __init__(self):
        self.stream = None
        self.lock = threading.Lock()
        
        # 当前声学参数
        self.current_freq = 440.0
        self.current_harmonics = [1.0]
        self.current_volume = 0.0
        self.current_chaos = 0.0
        self.on_ground = True
        
        # 相位累加器
        self.phase = 0.0
        self.chaos_phase = 0.0
        
    def start(self):
        """启动音频流"""
        self.stream = sd.OutputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype='float32',
            blocksize=BUFFER_SIZE,
            callback=self._audio_callback
        )
        self.stream.start()
    
    def stop(self):
        """停止音频流"""
        if self.stream:
            self.stream.stop()
            self.stream.close()
    
    def update_params(self, params):
        """线程安全地更新声学参数"""
        with self.lock:
            self.current_freq = params['freq']
            self.current_harmonics = params['harmonics']
            self.current_volume = params['volume']
            self.current_chaos = params['chaos']
            self.on_ground = params['on_ground']
    
    def _audio_callback(self, outdata, frames, time_info, status):
        """音频回调函数（sounddevice 要求直接写入 outdata）"""
        with self.lock:
            freq = self.current_freq
            harmonics = self.current_harmonics
            volume = self.current_volume
            chaos = self.current_chaos
            on_ground = self.on_ground
        
        # 生成音频缓冲区
        buffer = np.zeros(frames, dtype=np.float32)
        
        # 基础频率增量
        phase_inc = 2 * np.pi * freq / SAMPLE_RATE
        
        # 混沌调制
        chaos_inc = 2 * np.pi * chaos * 10 / SAMPLE_RATE
        
        for i in range(frames):
            # 混沌相位调制
            self.chaos_phase += chaos_inc
            chaos_mod = 1.0 + math.sin(self.chaos_phase) * chaos * 0.5
            
            # 生成谐波
            sample = 0.0
            for j, amp in enumerate(harmonics[:4]):  # 最多4个谐波
                harmonic_freq = freq * (j + 1) * chaos_mod
                harmonic_inc = 2 * np.pi * harmonic_freq / SAMPLE_RATE
                
                # 选择波形：地面用正弦波，空中用锯齿波
                if on_ground:
                    wave = math.sin(self.phase * (j + 1))
                else:
                    wave = 2 * (self.phase * (j + 1) % (2*np.pi) / (2*np.pi)) - 1
                
                sample += wave * amp * volume
            
            buffer[i] = sample * 0.3  # 整体增益
            self.phase += phase_inc
        
        # 将数据写入输出数组（必须 (frames, channels) 形状）
        outdata[:] = buffer.reshape(-1, 1)

# ======================
# 回声波纹系统
# ======================
class EchoRipple:
    def __init__(self, canvas, x, y):
        self.canvas = canvas
        self.x = x
        self.y = y
        self.radius = 5
        self.alpha = 1.0
        self.id = canvas.create_oval(
            x - self.radius, y - self.radius,
            x + self.radius, y + self.radius,
            outline="#00FFFF", width=2, fill=""
        )
    
    def update(self):
        self.radius += 8
        self.alpha -= 0.02
        if self.alpha <= 0:
            return False
        
        # 更新透明度（通过颜色变暗模拟淡出）
        color = self._fade_color("#00FFFF", self.alpha)
        self.canvas.itemconfig(self.id, outline=color)
        self.canvas.coords(self.id,
                          self.x - self.radius, self.y - self.radius,
                          self.x + self.radius, self.y + self.radius)
        return True
    
    def _fade_color(self, hex_color, alpha):
        """根据alpha值调整颜色亮度"""
        r = int(hex_color[1:3], 16)
        g = int(hex_color[3:5], 16)
        b = int(hex_color[5:7], 16)
        factor = max(0, alpha)
        return f"#{int(r*factor):02x}{int(g*factor):02x}{int(b*factor):02x}"

# ======================
# 主应用
# ======================
class App:
    def __init__(self, root):
        self.root = root
        self.canvas = tk.Canvas(root, width=WIDTH, height=HEIGHT, bg=BG)
        self.canvas.pack()
        
        # 系统组件
        self.physics = ChaoticPhysics()
        self.rider = Rider(self.canvas)
        self.audio = AudioSynthesizer()
        self.tracks: List[BezierTrack] = []
        self.ripples: List[EchoRipple] = []
        
        # 状态
        self.drawing = []
        self.current_material = 2
        self.running = False
        self.last_time = time.time()
        
        # 绑定事件
        self.canvas.bind("<Button-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        root.bind("<space>", self.toggle_play)
        root.bind("1", lambda e: self.set_material(1))
        root.bind("2", lambda e: self.set_material(2))
        root.bind("3", lambda e: self.set_material(3))
        root.bind("4", lambda e: self.set_material(4))
        root.bind("5", lambda e: self.set_material(5))
        root.bind("r", self.reset)
        
        # 启动音频
        self.audio.start()
        
        # UI
        self.status = tk.Label(root, text="按 1-5 选择材质 | Space 开始 | R 重置",
                              bg="#111122", fg="#00FFFF", font=("Arial", 12))
        self.status.place(x=10, y=10)
        
        self.material_label = tk.Label(root, text=f"材质: {MATERIALS[self.current_material].name}",
                                       bg="#111122", fg=MATERIALS[self.current_material].color,
                                       font=("Arial", 12))
        self.material_label.place(x=10, y=40)
        
        # 初始提示
        self.canvas.create_text(WIDTH//2, HEIGHT//2, 
                               text="🎵 Line Rider Pro 🎵\n\n"
                                    "1: 冰面 (低摩擦, 纯净音色)\n"
                                    "2: 木质 (中等摩擦)\n"
                                    "3: 橡胶 (高摩擦, 粗糙音色)\n"
                                    "4: 加速 (负摩擦)\n"
                                    "5: 混沌 (强随机扰动)\n\n"
                                    "左键拖拽绘制轨道\n"
                                    "Space 开始/暂停",
                               fill="#666688", font=("Arial", 16), justify="center")
    
    def set_material(self, mat_id):
        self.current_material = mat_id
        mat = MATERIALS[mat_id]
        self.material_label.config(text=f"材质: {mat.name}", fg=mat.color)
    
    def on_press(self, e):
        self.drawing = [(e.x, e.y)]
    
    def on_drag(self, e):
        self.drawing.append((e.x, e.y))
        if len(self.drawing) > 3:
            # 绘制预览
            self.canvas.delete("preview")
            if len(self.drawing) >= 4:
                # 贝塞尔预览
                cp = [self.drawing[0], self.drawing[-3], self.drawing[-2], self.drawing[-1]]
                points = []
                for i in range(20):
                    t = i / 19
                    x, y = self._bezier(cp, t)
                    points.extend([x, y])
                self.canvas.create_line(points, smooth=True, fill=MATERIALS[self.current_material].color,
                                       width=4, tags="preview")
    
    def on_release(self, e):
        if len(self.drawing) >= 4:
            cp = [self.drawing[0], self.drawing[-3], self.drawing[-2], self.drawing[-1]]
            track = BezierTrack(cp, self.current_material)
            self.tracks.append(track)
            
            # 绘制永久轨道
            points = []
            for seg in track.segments:
                points.extend([seg[0], seg[1]])
                points.extend([seg[2], seg[3]])
            
            self.canvas.create_line(points, smooth=True, fill=track.color,
                                   width=6, capstyle=tk.ROUND, joinstyle=tk.ROUND)
        
        self.drawing = []
        self.canvas.delete("preview")
    
    def _bezier(self, cp, t):
        """三次贝塞尔插值"""
        p0, p1, p2, p3 = cp
        u = 1 - t
        x = u**3*p0[0] + 3*u**2*t*p1[0] + 3*u*t**2*p2[0] + t**3*p3[0]
        y = u**3*p0[1] + 3*u**2*t*p1[1] + 3*u*t**2*p2[1] + t**3*p3[1]
        return x, y
    
    def toggle_play(self, e=None):
        if not self.running:
            self.running = True
            if not self.rider.alive:
                self.rider.spawn(100, 100)
            self.game_loop()
            self.status.config(text="🎵 播放中... | Space 暂停 | R 重置")
        else:
            self.running = False
            self.status.config(text="⏸ 已暂停 | Space 继续")
    
    def game_loop(self):
        if not self.running:
            return
        
        # 物理更新
        acoustic_params = self.rider.update(self.tracks, self.physics)
        
        # 更新音频
        if acoustic_params:
            self.audio.update_params(acoustic_params)
        
        # 腾空检测 → 回声波纹
        if self.rider.last_on_ground and not self.rider.on_ground:
            self.ripples.append(EchoRipple(self.canvas, self.rider.x, self.rider.y))
        
        # 更新波纹
        self.ripples = [r for r in self.ripples if r.update()]
        
        # 混沌物理更新（全局）
        self.physics.turbulence = 0.3 + 0.2 * math.sin(time.time() * 0.5)
        self.physics.wind = 0.5 * math.sin(time.time() * 0.3)
        
        self.root.after(16, self.game_loop)
    
    def reset(self, e=None):
        self.running = False
        self.canvas.delete("all")
        self.tracks.clear()
        self.ripples.clear()
        self.rider.alive = False
        self.status.config(text="按 1-5 选择材质 | Space 开始 | R 重置")
    
    def on_close(self):
        self.audio.stop()
        self.root.destroy()

# ======================
if __name__ == "__main__":
    root = tk.Tk()
    root.title("Line Rider Pro: Chaotic Physics + Real-time Audio")
    root.geometry(f"{WIDTH}x{HEIGHT}")
    root.resizable(False, False)
    
    app = App(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()