# -*- coding: utf-8 -*-
"""全局常量：画面 / 视野 / 能量 / 音频参数、调色板、射线查找表。"""
import math

import numpy as np

# ─────────────────────── 常量 ─────────────────────────
W, H     = 1280, 720
FOV      = math.pi / 3
HALF_FOV = FOV / 2
NUM_RAYS = 240  # 射线数量
NUM_RAYS_HALF = NUM_RAYS // 2  # 用于查找表
MAX_DEPTH = 22
MOVE_SPEED = 0.055
ROT_SPEED  = 0.028

SR   = 44100
BPM  = 118
BEAT = 60.0 / BPM
VOL  = 0.13
SEMITONES_DOWN = -8
REVERB_DELAY   = 0.19
REVERB_DECAY   = 0.44

# ─── 游戏增强常量 ───
ENERGY_MAX         = 100.0   # 能量上限
ENERGY_DRAIN_MOVE  = 1.0     # 移动消耗：点/秒
ENERGY_DRAIN_RED   = 3.0     # 红色区消耗：点/秒
ENERGY_RECOVER_GLOW= 0.5     # 发光柱附近恢复：点/秒
INTERACT_RANGE     = 2.0     # 交互检测范围（世界单位）
FRAGMENT_TYPES     = 10      # 碎片种类数（deco_type 2~11）
EXPLORE_RADIUS     = 10      # 区块探索判定半径（世界单位）
ACID_DRAIN_RATE    = 15.0    # 酸液池接触消耗：点/秒
PORTAL_TELEPORT_CHANCE = 0.15  # 传送门触发概率
SPAWN_GRACE_PERIOD  = 3.0     # 出生保护期（秒），期间不消耗能量

# ─── 暗室房间模板名集合 ───
DARK_ROOM_TEMPLATES = {
    'make_room_dark_cross',
    'make_room_secret_ns',
}

CHUNK_VIEW_RANGE = 1      # 视野范围：玩家周边 1 格
CHUNK_PRELOAD_RANGE = 1   # 预加载范围：仅玩家所在+周围1格（3×3）
CHUNK_CLEAN_RANGE = 2     # 清理范围：超出此范围的区块将被卸载

CHUNK_SIZE = 21   # 每个区块的尺寸

# ── 调色板（增加多种氛围色系） ──
# 冰霜蓝系
C_CEIL_TOP = (5,  10,  22)
C_CEIL_BOT = (12,  25,  55)
C_FLOOR_T  = (18,  35,  50)
C_FLOOR_B  = (8,   18,  35)
C_WALL_FAR = (5,   20,  55)
C_WALL_NR  = (15,  60, 120)
C_GLOW_COL = (50, 255, 200)
C_FOG      = (8,   12,  30)
C_GRID     = (15,  45, 90)
C_ACCENT   = (40, 200, 255)
C_HUD      = (50, 180, 230)
C_SCAN     = (0,   4,  12)

# 装饰物颜色
C_DECO_RED    = (180, 50,  50)   # 红色警示
C_DECO_GOLD   = (200, 170, 60)   # 金色装饰
C_DECO_GREEN  = (50,  200, 100)  # 绿色植物
C_DECO_PURPLE = (150, 80,  200)  # 紫色能量
C_DECO_ORANGE = (220, 120, 40)   # 橙色光源

# ─────────────────────── 预计算查找表（优化渲染）────────────────────────
# 预计算射线角度（从 -HALF_FOV 到 +HALF_FOV）
_RAY_ANGLES = np.array([(i / NUM_RAYS) * FOV - HALF_FOV for i in range(NUM_RAYS)], dtype=np.float32)
_RAY_SIN = np.sin(_RAY_ANGLES).astype(np.float32)
_RAY_COS = np.cos(_RAY_ANGLES).astype(np.float32)

# 预计算距离校正因子（fish-eye correction）
_RAY_CORRECTION = np.cos(_RAY_ANGLES).astype(np.float32)

# ─────────────────────── 伪 3D 增强（Stage 1）────────────────────────
# 渲染后端："raycast" = 原始纯色地板/天花板；"enhanced" = 地面投射 + 俯仰 + 精灵
#           "gl"      = ModernGL 真 3D（离屏上下文渲染 + 像素读回叠加到 2D 表面）
# 默认真 3D；GL 上下文创建失败会自动回退 enhanced（见 game._make_renderer）。
RENDER_BACKEND = "gl"

# ─────────────────────── 真 3D（Stage 2，ModernGL）────────────────────────
# 离屏渲染：GL 在独立 moderngl 上下文里渲染到 FBO，再把像素读回成 pygame 表面
# blit 到主窗口。主窗口保持普通 2D 模式，因此 HUD/粒子/暗角/开始/死亡界面零改动。
GL_FOV_Y        = 68.0    # 透视投影垂直视角（度）
GL_EYE_Z        = 0.5     # 眼高（与 raycast 约定一致：地板 0、天花板 1、墙 0~1）
GL_NEAR         = 0.05
GL_FAR          = 80.0
GL_REGION_RADIUS = 1      # 以玩家区块为中心的 (2r+1)² 区块区域整块建网格
GL_FOG_DENSITY  = 0.12    # 指数雾密度（越大越雾）
GL_PITCH_SCALE  = 0.0021  # 像素俯仰 → 弧度（self.pitch 是像素位移，GL 需要弧度）
GL_BB_W         = 0.72    # 装饰物 billboard 宽（世界单位）
GL_BB_H         = 1.15    # 装饰物 billboard 高

# ── 后处理（Stage 4）──
GL_EXPOSURE        = 1.45   # 全局曝光
GL_BLOOM_THRESHOLD = 0.45   # 亮部提取阈值（亮度低于它的不发光）
GL_BLOOM_STRENGTH  = 0.75   # bloom 叠加强度
GL_BLOOM_KNEE      = 0.60   # 软膝宽度（×阈值）：0=硬阈值，防 banding（EEVEE 同款曲线）
GL_BLOOM_CLAMP     = 2.5    # 单像素亮度钳制上限（0=关闭），防爆发亮斑
GL_BLOOM_MIPS      = 4      # bloom 下采样链级数（1/2 → 1/16）
GL_BLOOM_SAMPLE_SCALE = 1.0 # 上采样 tent 半径缩放（EEVEE sampleScale）
GL_SCANLINE_ALPHA  = 0.10   # 扫描线强度（对应旧版 25/255）
GL_VIGNETTE_MAX    = 0.16   # 四角最大压暗（对应旧版 40/255）

TAN_HALF_FOV = math.tan(HALF_FOV)          # 摄像机平面半长
# 世界单位 → 像素（距离 1 处）：水平与垂直比例不同，是 raycasting 的固有拉伸
K_PX_H = W / (2.0 * TAN_HALF_FOV)          # 水平：每世界单位的像素数
K_PX_V = float(H)                          # 垂直：每世界单位的像素数

PITCH_MAX_PIX = 0.42 * H                   # 俯仰位移上限（像素）
PITCH_KEY_SPEED = 7.0                      # 键盘俯仰速度（像素/帧）
MOUSE_SENS_X = 0.0024                      # 鼠标横向灵敏度（弧度/像素）
MOUSE_SENS_Y = 1.7                         # 鼠标纵向灵敏度（像素/像素）

FLOOR_BUFFER_SCALE = 2                     # 地面/天花板降采样倍率（1 = 全分辨率，最慢）
FLOOR_TEX_SIZE = 64                        # 地砖纹理边长
FLOOR_TILE_UNITS = 2.0                     # 一块地砖覆盖的世界格数（越大格子越疏）
SPRITE_VIEW_RADIUS = 9                     # 装饰物精灵可见半径（世界格）
SPRITE_TEX_SIZE = 64                       # 精灵纹理边长
