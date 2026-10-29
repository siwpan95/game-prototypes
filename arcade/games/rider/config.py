"""Line Rider — 全局常量与材质定义"""

from dataclasses import dataclass

# 窗口 / 视口
WIDTH, HEIGHT = 1200, 800
BG = "#050510"
FPS = 60
DT = 1 / FPS

# 物理常量
GRAVITY_PPS2 = 9.81 * 60          # 像素/s²（缩放为游戏尺度）
AIR_DENSITY = 1.2
DRAG_COEFF = 0.47                 # 球体阻力
MAX_RIDER_SPEED = 3000            # 速度上限
SUBDIVISIONS_PER_FRAME = 4        # CCD 子步数

# 碰撞
RIDER_COLLISION_RADIUS = 10       # 碰撞半径
SURFACE_THICKNESS = 3             # 轨道表面厚度（碰撞容差）

# 音频
SAMPLE_RATE = 44100
BUFFER_SIZE = 1024
MAX_FREQ = 2000
AUDIO_GAIN = 0.3

# 相机
CAMERA_SMOOTH = 0.08              # lerp 系数（越小越平滑）

# 轨迹渲染
TRAIL_LENGTH = 50
TRACK_WIDTH = 6
TRACK_SAMPLE_STEPS = 50           # 贝塞尔采样密度

# ─── 材质定义 ──────────────────────────────
@dataclass
class Material:
    name: str
    color: str
    friction: float               # 0-1: 摩擦系数（1 = 无摩擦）
    restitution: float            # 弹性恢复系数
    chaos_factor: float           # 混沌强度
    base_harmonic: int            # 音频谐波复数

MATERIALS = {
    1: Material("冰面",   "#00FFFF", 0.98, 0.95, 0.05, 1),
    2: Material("木质",   "#DEB887", 0.80, 0.60, 0.15, 2),
    3: Material("橡胶",   "#333333", 0.50, 0.25, 0.30, 3),
    4: Material("加速",   "#FF4500", 1.02, 1.20, 0.25, 4),
    5: Material("混沌",   "#9400D3", 0.70, 0.80, 0.50, 5),
}
DEFAULT_MATERIAL = 2

# ─── Rider 形状（局部坐标，面向右）────────
# sled 滑板：梯形
SLED_BODY_LOCAL = [
    (-14,  2),   # 尾部底部
    (16,   2),   # 头部底部
    (10,  -6),   # 头部顶部
    (-8,  -6),   # 尾部顶部
]
# sled 滑行刃（两条线）: (x1,y1, x2,y2)
SLED_RUNNER_FRONT = (16, 4, 14, 2)
SLED_RUNNER_REAR  = (-14, 4, -12, 2)
# 人物身体
BODY_CENTER = (0, -10)          # 身体圆心
BODY_RADIUS = 5
# 头部
HEAD_CENTER = (4, -20)           # 头部圆心
HEAD_RADIUS = 4
