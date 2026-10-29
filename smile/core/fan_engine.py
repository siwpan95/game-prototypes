"""
风扇背景引擎
从 project1 提取核心逻辑，简化为自主运行的背景装饰：
- 自动缓慢变速（模拟真实风扇的转速波动）
- 3 叶片旋转绘制
- 简化物理：转动惯量 + 摩擦 + 目标速度追踪
- 无用户控制参数，完全自主运行
"""
import math
import time
import random


class FanEngine:
    """自主运行的风扇背景装饰"""

    # 物理参数
    MOMENT_OF_INERTIA = 0.1     # 转动惯量
    BEARING_FRICTION = 0.008    # 轴承摩擦
    DAMPING = 0.08              # 目标速度追踪阻尼

    # 视觉参数
    BLADE_COUNT = 3
    HUB_RADIUS_RATIO = 0.17     # 中心毂半径 / 外圈半径
    BLADE_WIDTH_NEAR = 0.06     # 近端叶片宽度比
    BLADE_WIDTH_FAR = 0.16      # 远端叶片宽度比

    # 自主运行参数
    SPEED_CHANGE_INTERVAL = (3.0, 8.0)   # 变速间隔（秒）
    RPM_RANGE = (120, 600)               # RPM 范围

    def __init__(self):
        self._angular_velocity = 0.0       # rad/s
        self._target_velocity = 8.0        # 初始目标 (约 80 RPM)
        self._blade_angle = 0.0            # 累积角度（度）
        self._last_time = time.time()
        self._next_change = time.time() + random.uniform(*self.SPEED_CHANGE_INTERVAL)
        self._running = True

    def update(self):
        """每帧更新物理和角度，返回当前 RPM"""
        now = time.time()
        dt = min(now - self._last_time, 0.05)  # 限制最大 dt 防止跳帧
        self._last_time = now

        # 自主变速
        if now >= self._next_change:
            target_rpm = random.uniform(*self.RPM_RANGE)
            self._target_velocity = target_rpm * 2 * math.pi / 60
            self._next_change = now + random.uniform(*self.SPEED_CHANGE_INTERVAL)

        # 物理更新
        friction = -self.BEARING_FRICTION * self._angular_velocity
        diff = self._target_velocity - self._angular_velocity
        self._angular_velocity += (diff * self.DAMPING + friction) * dt

        # RPM = |ω| * 60 / (2π)
        rpm = abs(self._angular_velocity) * 60 / (2 * math.pi)

        # 角度累积
        self._blade_angle += self._angular_velocity * dt * (180 / math.pi)

        return rpm

    def draw(self, surface, cx, cy, radius, alpha=255):
        """在 surface 上绘制风扇"""
        rpm = abs(self._angular_velocity) * 60 / (2 * math.pi)
        angle = self._blade_angle

        # 外圈保护罩
        cage_color = (70, 70, 90, alpha)
        _draw_circle_alpha(surface, cage_color, (cx, cy), radius, 2)

        # 前后网罩纹路
        for r_frac in (0.35, 0.55, 0.75, 0.92):
            r = int(radius * r_frac)
            ring_color = (55, 55, 70, max(0, alpha - 80))
            _draw_circle_alpha(surface, ring_color, (cx, cy), r, 1)

        # 叶片
        blade_color = (90, 130, 200, alpha) if rpm > 150 else (70, 70, 85, alpha)
        outline_color = (50, 80, 150, alpha) if rpm > 150 else (50, 50, 60, alpha)

        hub_r = int(radius * self.HUB_RADIUS_RATIO)
        for i in range(self.BLADE_COUNT):
            ba = math.radians(angle + i * (360 / self.BLADE_COUNT))
            # 每个叶片是四边形
            near_r = hub_r
            far_r = radius - 4

            perp = ba + math.pi / 2
            near_w = radius * self.BLADE_WIDTH_NEAR
            far_w = radius * self.BLADE_WIDTH_FAR

            pts = [
                (cx + near_r * math.cos(ba) + near_w * math.cos(perp),
                 cy + near_r * math.sin(ba) + near_w * math.sin(perp)),
                (cx + far_r * math.cos(ba) + far_w * math.cos(perp),
                 cy + far_r * math.sin(ba) + far_w * math.sin(perp)),
                (cx + far_r * math.cos(ba) - far_w * math.cos(perp),
                 cy + far_r * math.sin(ba) - far_w * math.sin(perp)),
                (cx + near_r * math.cos(ba) - near_w * math.cos(perp),
                 cy + near_r * math.sin(ba) - near_w * math.sin(perp)),
            ]
            int_pts = [(int(x), int(y)) for x, y in pts]

            blade_surf = pygame.Surface((surface.get_width(), surface.get_height()), pygame.SRCALPHA)
            pygame.draw.polygon(blade_surf, blade_color, int_pts)
            pygame.draw.polygon(blade_surf, outline_color, int_pts, 2)
            surface.blit(blade_surf, (0, 0))

        # 中心毂
        hub_color = (80, 80, 100, alpha)
        _draw_filled_circle_alpha(surface, hub_color, (cx, cy), hub_r)
        hub_inner = (60, 60, 80, alpha)
        _draw_filled_circle_alpha(surface, hub_inner, (cx, cy), max(2, hub_r - 4))

        # 支撑架
        for i in range(self.BLADE_COUNT):
            a = math.radians(i * (360 / self.BLADE_COUNT))
            ex = cx + int((radius - 8) * math.cos(a))
            ey = cy + int((radius - 8) * math.sin(a))
            pygame.draw.line(surface, (60, 60, 75, alpha) if alpha < 255 else (60, 60, 75),
                             (cx, cy), (ex, ey), 3)

    @property
    def rpm(self):
        return abs(self._angular_velocity) * 60 / (2 * math.pi)

    @property
    def speed_ratio(self):
        """0~1 的速度比例"""
        return min(1.0, self.rpm / self.RPM_RANGE[1])


# ─── 绘图辅助 ────────────────────────────────────────────────

def _draw_circle_alpha(surface, color, center, radius, width=1):
    """在任意 surface 上画带 alpha 的圆环"""
    if len(color) == 4 and color[3] < 255:
        s = pygame.Surface((radius * 2 + 4, radius * 2 + 4), pygame.SRCALPHA)
        pygame.draw.circle(s, color, (radius + 2, radius + 2), radius, width)
        surface.blit(s, (center[0] - radius - 2, center[1] - radius - 2))
    else:
        pygame.draw.circle(surface, color[:3], center, radius, width)


def _draw_filled_circle_alpha(surface, color, center, radius):
    """在任意 surface 上画带 alpha 的填充圆"""
    if len(color) == 4 and color[3] < 255:
        s = pygame.Surface((radius * 2 + 2, radius * 2 + 2), pygame.SRCALPHA)
        pygame.draw.circle(s, color, (radius + 1, radius + 1), radius)
        surface.blit(s, (center[0] - radius - 1, center[1] - radius - 1))
    else:
        pygame.draw.circle(surface, color[:3], center, radius)


# 需要 pygame import（延迟导入，因为本模块被 core 包引用）
import pygame
