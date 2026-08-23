# -*- coding: utf-8 -*-
"""camera — 2D 侧视相机（视口跟随 + 边界钳制 + Z 层级预留）。

提供：
  - Camera: 持有固定尺寸视口 AABB2D，使玩家居中并显示在视口中央；
            抵达世界边界时钳制；提供屏幕像素 → 世界格反算。

坐标约定（继承地基）：
  - 屏幕瓦片行 r ↔ world y = viewport.max_y - r
  - 屏幕瓦片列 c ↔ world x = viewport.min_x + c
  - 屏幕像素：px = VIEW_OFFSET_X + c*TILE_SIZE，py = HUD_TOP + r*TILE_SIZE

本模块无 pygame 依赖，可在 headless 下断言（T-M1-03 / T-M1-11）。
"""

from __future__ import annotations

import math

from mcclone.core.geometry import AABB2D, clamp


# 屏幕映射常量（与 tile_world_renderer / main_gui 共享；集中定义便于引用）。
VIEW_OFFSET_X: int = 0
HUD_TOP: int = 28
TILE_SIZE: int = 32


class Camera:
    """2D 侧视相机。

    视口为固定尺寸的世界坐标 AABB2D（整数格坐标，宽 = 像素列数 - 1）。
    follow 使视口中心对齐目标中心（整数钳制，渲染逐格）；
    clamp_to 把视口钳制进世界包围盒；current_z 预留（M3 启用多层）。
    """

    def __init__(self, viewport: AABB2D) -> None:
        # 视口尺寸固定（调用方构造，宽 = 列数 - 1，高 = 行数 - 1）。
        self.viewport = viewport
        self.current_z: int = 0  # Z 层级（M3 启用，M1 恒为 0）

    def follow(self, target: AABB2D) -> None:
        """使视口中心对齐 target 中心（整数格坐标，渲染逐格稳定）。"""
        # 先捕获视口尺寸（避免修改 min 后 width 属性失真）。
        vw = self.viewport.width
        vh = self.viewport.height
        cx = (target.min_x + target.max_x) / 2.0
        cy = (target.min_y + target.max_y) / 2.0
        half_w = vw / 2.0
        half_h = vh / 2.0
        min_x = int(math.floor(cx - half_w))
        min_y = int(math.floor(cy - half_h))
        self.viewport.min_x = min_x
        self.viewport.min_y = min_y
        self.viewport.max_x = min_x + vw
        self.viewport.max_y = min_y + vh

    def clamp_to(self, world_bounds: AABB2D) -> None:
        """把视口钳制进 world_bounds（防止越界黑边）。"""
        vw = self.viewport.width
        vh = self.viewport.height
        wb = world_bounds
        # X 轴
        if vw >= wb.width:
            self.viewport.min_x = wb.min_x
            self.viewport.max_x = wb.max_x
        else:
            if self.viewport.min_x < wb.min_x:
                self.viewport.min_x = wb.min_x
                self.viewport.max_x = wb.min_x + vw
            elif self.viewport.max_x > wb.max_x:
                self.viewport.max_x = wb.max_x
                self.viewport.min_x = wb.max_x - vw
        # Y 轴
        if vh >= wb.height:
            self.viewport.min_y = wb.min_y
            self.viewport.max_y = wb.max_y
        else:
            if self.viewport.min_y < wb.min_y:
                self.viewport.min_y = wb.min_y
                self.viewport.max_y = wb.min_y + vh
            elif self.viewport.max_y > wb.max_y:
                self.viewport.max_y = wb.max_y
                self.viewport.min_y = wb.max_y - vh

    def set_z(self, z: int, world_depth: "int | None" = None) -> None:
        """设置当前 Z 层级。

        M3 主用（2 参）：钳制到 ``[0, world_depth-1]``，避免越界。
        M1 兼容（1 参）：等同旧行为，不钳制（保留 M1 测试语义）。
        """
        if world_depth is not None:
            self.current_z = clamp(z, 0, world_depth - 1)
        else:
            self.current_z = z

    def clamp_z(self, world) -> None:
        """把 current_z 钳制进世界深度范围 ``[0, world.depth-1]``。"""
        self.current_z = clamp(self.current_z, 0, world.depth - 1)

    def screen_to_world_cell(self, mx: int, my: int) -> tuple[int, int]:
        """屏幕像素 → 世界格（与 TileWorldRenderer._world_to_screen 互逆）。

        公式（架构 §7.3）：
            c = (mx - VIEW_OFFSET_X) // TILE_SIZE
            r = (my - HUD_TOP) // TILE_SIZE
            world_x = viewport.min_x + c
            world_y = viewport.max_y - r
        """
        c = (mx - VIEW_OFFSET_X) // TILE_SIZE
        r = (my - HUD_TOP) // TILE_SIZE
        world_x = self.viewport.min_x + c
        world_y = self.viewport.max_y - r
        return (world_x, world_y)

    # 架构类图别名：屏幕像素 → 世界格（等价于 screen_to_world_cell）。
    def screen_center_to_world(self, mx: int, my: int) -> tuple[int, int]:
        """别名：屏幕像素 → 世界格。"""
        return self.screen_to_world_cell(mx, my)
