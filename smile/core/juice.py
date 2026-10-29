"""
Game Juice 模块 — 让反馈"有汁"
基于业界 game feel 最佳实践（Vlambeer / Juice it or lose it / GDC Trauma 系统）：
- ScreenShake: trauma² 震动系统（震动强度 = trauma 的平方，衰减自然）
- Easing: 缓动函数库（ease_out_back 用于弹出、ease_out_cubic 用于进度条）
- ConfettiSystem: 彩带粒子（获得奖励时的庆祝效果，方向性喷射 + 重力 + 淡出）
- RevealSequence: 抽卡式开奖悬念动画（anticipation → flash → reveal 三段式）
"""
import math
import random


# ══════════════════════════════════════════════════════════════
#  缓动函数（替代线性动画，业界共识：linear = 机械感，eased = 生命感）
# ══════════════════════════════════════════════════════════════

def ease_out_cubic(t):
    """快起慢停 — 适合进度条、滑入"""
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3

def ease_out_back(t, overshoot=1.70158):
    """冲过头再弹回 — 适合弹窗、奖励卡片（活泼感）"""
    t = max(0.0, min(1.0, t))
    c3 = overshoot + 1
    return 1 + c3 * (t - 1) ** 3 + overshoot * (t - 1) ** 2

def ease_out_elastic(t):
    """果冻弹性 — 适合大奖登场"""
    t = max(0.0, min(1.0, t))
    if t == 0 or t == 1:
        return t
    c4 = (2 * math.pi) / 3
    return 2 ** (-10 * t) * math.sin((t * 10 - 0.75) * c4) + 1

def ease_in_expo(t):
    """慢起爆发 — 适合蓄力"""
    t = max(0.0, min(1.0, t))
    return 0 if t == 0 else 2 ** (10 * t - 10)


# ══════════════════════════════════════════════════════════════
#  屏幕震动 — Trauma 系统
#  震动量 = trauma²，大事件震感强烈但衰减迅速、小事件几乎无感
# ══════════════════════════════════════════════════════════════

class ScreenShake:
    """基于 trauma 的屏幕震动（GDC 推荐做法）"""

    def __init__(self, decay=1.6, max_offset=14.0):
        self.trauma = 0.0
        self.decay = decay          # 每秒衰减量
        self.max_offset = max_offset
        self._t = 0.0

    def add(self, amount):
        """叠加创伤值：轻微 0.2 / 中等 0.4 / 强烈 0.7"""
        self.trauma = min(1.0, self.trauma + amount)

    def update(self, dt):
        if self.trauma > 0:
            self.trauma = max(0.0, self.trauma - self.decay * dt)
        self._t += dt

    def offset(self):
        """返回本帧 (dx, dy) 偏移；用平滑噪声而非纯随机避免闪烁感"""
        if self.trauma <= 0:
            return 0, 0
        shake = self.trauma ** 2  # 平方衰减：大震夸张、小震收敛
        # 用不同频率的正弦叠加模拟 Perlin 噪声的平滑随机
        t = self._t
        nx = math.sin(t * 37.7) * 0.6 + math.sin(t * 23.3 + 1.7) * 0.4
        ny = math.sin(t * 41.1 + 0.9) * 0.6 + math.sin(t * 19.7 + 2.3) * 0.4
        return (self.max_offset * shake * nx,
                self.max_offset * shake * ny)


# ══════════════════════════════════════════════════════════════
#  彩带庆祝粒子
# ══════════════════════════════════════════════════════════════

CONFETTI_COLORS = [
    (255, 99, 99), (255, 180, 60), (255, 235, 80),
    (110, 220, 120), (90, 170, 255), (190, 110, 255),
    (255, 130, 200),
]


class ConfettiSystem:
    """奖励庆祝彩带：向上喷射 → 重力下落 + 左右飘 + 旋转 + 淡出"""

    def __init__(self):
        self.parts = []

    def burst(self, x, y, count=60, power=1.0):
        for _ in range(count):
            angle = random.uniform(-math.pi * 0.85, -math.pi * 0.15)  # 向上扇形
            speed = random.uniform(180, 420) * power
            self.parts.append({
                "x": x, "y": y,
                "vx": math.cos(angle) * speed,
                "vy": math.sin(angle) * speed,
                "w": random.uniform(4, 9),
                "h": random.uniform(6, 13),
                "rot": random.uniform(0, 360),
                "rot_v": random.uniform(-540, 540),
                "sway": random.uniform(2.0, 6.0),
                "phase": random.uniform(0, math.pi * 2),
                "life": random.uniform(1.6, 3.0),
                "max_life": 3.0,
                "color": random.choice(CONFETTI_COLORS),
            })

    def update(self, dt):
        alive = []
        for p in self.parts:
            p["life"] -= dt
            if p["life"] <= 0:
                continue
            p["vy"] += 620 * dt                       # 重力
            p["vx"] *= (1 - min(1.0, 2.2 * dt))        # 空气阻力
            p["vy"] = min(p["vy"], 260)                # 终端速度（纸片飘落感）
            p["phase"] += p["sway"] * dt
            p["x"] += (p["vx"] + math.sin(p["phase"]) * 60) * dt
            p["y"] += p["vy"] * dt
            p["rot"] += p["rot_v"] * dt
            alive.append(p)
        self.parts = alive

    def draw(self, surface):
        import pygame
        for p in self.parts:
            alpha = max(0.0, min(1.0, p["life"] / 1.0))  # 最后 1 秒淡出
            w, h = int(p["w"]), int(p["h"])
            if w < 1 or h < 1:
                continue
            piece = pygame.Surface((w * 2, h * 2), pygame.SRCALPHA)
            c = p["color"]
            pygame.draw.rect(piece, (*c, int(230 * alpha)),
                             (w // 2, h // 2, w, h), border_radius=2)
            rotated = pygame.transform.rotate(piece, p["rot"])
            surface.blit(rotated, (int(p["x"] - rotated.get_width() / 2),
                                   int(p["y"] - rotated.get_height() / 2)))


# ══════════════════════════════════════════════════════════════
#  开奖悬念序列 — 借鉴抽卡游戏的"金光预兆 → 停顿 → 揭晓"节奏
# ══════════════════════════════════════════════════════════════

class RevealSequence:
    """
    三段式开奖：
    1. anticipation (0 ~ T1): 光球脉冲旋转，颜色未知（悬念积累）
    2. flash        (T1 ~ T2): 光球颜色渐变为稀有度色（预兆，类似原神金光）
    3. done         (> T2):   触发揭晓回调（表情/彩带/震动/结果卡片）
    """
    T1 = 0.9      # 悬念阶段时长
    T2 = 1.5      # 预兆结束、正式揭晓时刻

    def __init__(self):
        self.active = False
        self.timer = 0.0
        self.result = None
        self.on_reveal = None      # 揭晓回调
        self._revealed = False

    def start(self, result, on_reveal=None):
        self.active = True
        self.timer = 0.0
        self.result = result
        self.on_reveal = on_reveal
        self._revealed = False

    def update(self, dt):
        if not self.active:
            return
        self.timer += dt
        if self.timer >= self.T2 and not self._revealed:
            self._revealed = True
            self.active = False
            if self.on_reveal:
                self.on_reveal(self.result)

    @property
    def phase(self):
        """'anticipation' | 'flash' | None"""
        if not self.active:
            return None
        return "anticipation" if self.timer < self.T1 else "flash"

    @property
    def flash_progress(self):
        """预兆阶段进度 0~1"""
        if self.timer <= self.T1:
            return 0.0
        return min(1.0, (self.timer - self.T1) / (self.T2 - self.T1))
