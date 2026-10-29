# -*- coding: utf-8 -*-
"""tile_world_renderer — pygame 瓦片渲染器（程序生成纯色块 + 可选 PNG）。

提供：
  - TileWorldRenderer: 将 BlockWorld 的可见方块逐格 blit 为 32px 瓦片；
    与 TextWorldRenderer 共享坐标映射（r=max_y-r, c=min_x+c）；
    玩家与准星由调用方叠加（render 只画世界）。

坐标映射（架构 §7）：
  - 屏幕瓦片行 r ↔ world y = viewport.max_y - r
  - 屏幕瓦片列 c ↔ world x = viewport.min_x + c
  - 像素：px = VIEW_OFFSET_X + c*TILE_SIZE, py = HUD_TOP + r*TILE_SIZE

本模块仅在真实 GUI 运行期渲染；导入期不依赖 pygame（延迟导入）。
headless 下可用 collect_tiles() 做几何一致性断言（T-M1-11）。
"""

from __future__ import annotations

import os
from typing import Dict, List, Tuple

from mcclone.core.geometry import AABB2D
from mcclone.core.block_registry import BlockRegistry
from mcclone.core.block_world import BlockWorld
from mcclone.paths import DATA_DIR


# 调色板（BlockDef.color 语义名 → RGB），集中登记（架构 §7.4）。
_TILE_RGB: Dict[str, Tuple[int, int, int]] = {
    "white": (240, 240, 240),
    "gray": (130, 130, 130),
    "brown": (134, 96, 67),
    "green": (80, 170, 70),
    "blue": (60, 120, 220),
    "yellow": (224, 200, 90),
    "black": (20, 20, 20),
    "red": (200, 60, 60),
    "magenta": (180, 80, 180),
    "cyan": (80, 200, 200),
    "lava": (220, 90, 30),
}

# 半透明方块（water）的 alpha。
_WATER_ALPHA: int = 150

# 温度 tint 最大 alpha（架构 §7.1 / §7.5）。
_MAX_TEMP_ALPHA: int = 90

# 温度 tint 颜色端点（蓝 → 红，t=0 → t=1）。
_TEMP_COOL: Tuple[int, int, int] = (60, 120, 220)
_TEMP_HOT: Tuple[int, int, int] = (200, 60, 60)

# 水/岩浆覆盖层 tint（架构 §7.5）。
_WATER_TINT: Tuple[int, int, int] = (60, 120, 220)
_WATER_TINT_ALPHA: int = 110
_LAVA_TINT: Tuple[int, int, int] = (220, 90, 30)
_LAVA_TINT_ALPHA: int = 160
_TEMP_THRESHOLD: float = 0.05   # 低于此温度不画 tint（避免全屏泛蓝）

# 屏幕映射常量（与 camera.py / main_gui.py 共享）。
VIEW_OFFSET_X: int = 0
HUD_TOP: int = 28
TILE_SIZE: int = 32

# PNG tileset 覆盖钩子目录（命中则优先用 PNG；不存在则回退纯色块）。
_DATA_TILES_DIR = os.path.join(DATA_DIR, "tiles")


def _pygame():
    """延迟导入 pygame；不可用时抛出清晰错误。"""
    import pygame
    if pygame is None:
        raise RuntimeError("需要安装可选依赖 pygame 才能渲染瓦片")
    return pygame


class TileWorldRenderer:
    """pygame 瓦片渲染器。

    设计要点：
      - 不修改现有地基；坐标映射与 TextWorldRenderer 完全一致（T-M1-11）。
      - 瓦片 Surface 以 block_id 缓存（程序生成纯色块 + 1px 立体边框）。
      - 命中 data/tiles/{name}.png 则优先用 PNG（M1 仅留加载钩子）。
      - render 只画世界；玩家与准星由 draw_player / draw_highlight 叠加。
    """

    def __init__(self, screen, registry: BlockRegistry,
                 tile_size: int = TILE_SIZE) -> None:
        self.screen = screen                    # pygame.Surface（headless 可为 None）
        self.registry = registry
        self.tile_size = tile_size
        self._tile_cache: Dict[int, object] = {}  # block_id → Surface（延迟生成）

    # ── 几何映射（与 TextWorldRenderer 一致）──
    def _world_to_screen(self, tx: int, ty: int,
                         viewport: AABB2D) -> Tuple[int, int]:
        """世界格 → 屏幕像素（左上角）。与 Camera.screen_to_world_cell 互逆。"""
        c = tx - viewport.min_x
        r = viewport.max_y - ty
        px = VIEW_OFFSET_X + c * self.tile_size
        py = HUD_TOP + r * self.tile_size
        return (px, py)

    def _iter_visible(self, world: BlockWorld, viewport: AABB2D, z: int = 0):
        """生成可见非空气方块：(c, r, world_x, world_y, block_id)。

        z: 目标 Z 层（M3；默认 0 与 M1 行为一致）。
        """
        min_x, max_x = viewport.min_x, viewport.max_x
        min_y, max_y = viewport.min_y, viewport.max_y
        for r in range(0, (max_y - min_y) + 1):
            world_y = max_y - r
            for c in range(0, (max_x - min_x) + 1):
                world_x = min_x + c
                bid = world.get(world_x, world_y, z)
                if bid != 0:
                    yield (c, r, world_x, world_y, bid)

    def collect_tiles(self, world: BlockWorld, viewport: AABB2D,
                      z: int = 0) -> List[Tuple[int, int, int]]:
        """返回可见非空气方块列表 [(world_x, world_y, block_id)]（纯逻辑，headless 可用）。

        z: 目标 Z 层（M3；默认 0 与 M1 测试签名兼容）。
        """
        return [(wx, wy, bid) for (_c, _r, wx, wy, bid)
                in self._iter_visible(world, viewport, z)]

    # ── 瓦片 Surface 生成 ──
    def _tile_surface(self, block_id: int):
        """返回 block_id 对应的瓦片 Surface（缓存）。"""
        if block_id in self._tile_cache:
            return self._tile_cache[block_id]
        pg = _pygame()
        ts = self.tile_size
        try:
            block = self.registry.get(block_id)
        except KeyError:
            block = None

        # PNG 覆盖钩子
        if block is not None:
            png_path = os.path.join(_DATA_TILES_DIR, f"{block.name}.png")
            if os.path.isfile(png_path):
                surf = pg.image.load(png_path).convert_alpha()
                if surf.get_width() != ts or surf.get_height() != ts:
                    surf = pg.transform.scale(surf, (ts, ts))
                self._tile_cache[block_id] = surf
                return surf

        # M6：程序化像素纹理（优先于纯色块；失败/无 pygame 时回退）
        try:
            from mcclone.render.fx_tiles import TileTextureFactory
            tex = TileTextureFactory.make(block_id, self.registry, ts)
            if tex is not None:
                self._tile_cache[block_id] = tex
                return tex
        except Exception:
            pass

        # 程序生成纯色块
        color_name = block.color if block is not None else "white"
        rgb = _TILE_RGB.get(color_name, _TILE_RGB["white"])
        surf = pg.Surface((ts, ts))
        surf.fill(rgb)
        if block is not None and block.transparent:
            surf.set_alpha(_WATER_ALPHA)

        # 立体边框：左上高光、右下暗影（1px）
        lighter = self._shade(rgb, 1.25)
        darker = self._shade(rgb, 0.7)
        pg.draw.rect(surf, lighter, (0, 0, ts, 1))    # 上
        pg.draw.rect(surf, lighter, (0, 0, 1, ts))    # 左
        pg.draw.rect(surf, darker, (0, ts - 1, ts, 1))  # 下
        pg.draw.rect(surf, darker, (ts - 1, 0, 1, ts))  # 右
        self._tile_cache[block_id] = surf
        return surf

    @staticmethod
    def _shade(rgb: Tuple[int, int, int], factor: float) -> Tuple[int, int, int]:
        """按比例调亮/调暗颜色（钳制到 [0,255]）。"""
        return (min(255, int(rgb[0] * factor)),
                min(255, int(rgb[1] * factor)),
                min(255, int(rgb[2] * factor)))

    # ── 渲染（只画世界）──
    def render(self, world: BlockWorld, viewport: AABB2D, overlays=None,
               z: int = 0, show_temp: bool = True,
               show_water: bool = True) -> None:
        """逐格 blit 可见非空气方块（不画玩家/准星）。

        overlays: LayerOverlay（温度/水/岩浆 tint 数据），None 时不叠加。
        z: 目标 Z 层（M3）。
        show_temp / show_water: 是否叠加温度 / 水岩浆 tint（独立开关）。

        headless（screen=None）时仅遍历验证，不 blit（避免 pygame 依赖）。
        """
        if self.screen is None:
            # headless：仅遍历 + 触发 overlay 读取验证，不绘制。
            for (_c, _r, wx, wy, bid) in self._iter_visible(world, viewport, z):
                if overlays is not None:
                    _ = overlays.temp[wy][wx]
            return
        for (_c, _r, wx, wy, bid) in self._iter_visible(world, viewport, z):
            surf = self._tile_surface(bid)
            px, py = self._world_to_screen(wx, wy, viewport)
            self.screen.blit(surf, (px, py))
            if overlays is not None:
                self._apply_overlay(px, py, overlays, wx, wy,
                                    show_temp, show_water)

    def _apply_overlay(self, px: int, py: int, overlays, x: int, y: int,
                       show_temp: bool, show_water: bool) -> None:
        """在 (px,py) 叠加覆盖层 tint（温度/水/岩浆）。"""
        pg = _pygame()
        ts = self.tile_size
        # 温度 tint（蓝→红渐变，alpha∝t）
        if show_temp:
            t = overlays.temp[y][x]
            if t > _TEMP_THRESHOLD:
                rgb = self._lerp_color(_TEMP_COOL, _TEMP_HOT, t)
                alpha = int(t * _MAX_TEMP_ALPHA)
                tint = pg.Surface((ts, ts))
                tint.fill(rgb)
                tint.set_alpha(alpha)
                self.screen.blit(tint, (px, py))
        # 水 tint（半透明蓝，强化水体）
        if show_water and overlays.water[y][x]:
            tint = pg.Surface((ts, ts))
            tint.fill(_WATER_TINT)
            tint.set_alpha(_WATER_TINT_ALPHA)
            self.screen.blit(tint, (px, py))
        # 岩浆 tint（橙红）
        if show_water and overlays.lava[y][x]:
            tint = pg.Surface((ts, ts))
            tint.fill(_LAVA_TINT)
            tint.set_alpha(_LAVA_TINT_ALPHA)
            self.screen.blit(tint, (px, py))

    @staticmethod
    def _lerp_color(a: Tuple[int, int, int], b: Tuple[int, int, int],
                    t: float) -> Tuple[int, int, int]:
        """在颜色 a→b 之间按 t∈[0,1] 线性插值。"""
        return (int(a[0] + (b[0] - a[0]) * t),
                int(a[1] + (b[1] - a[1]) * t),
                int(a[2] + (b[2] - a[2]) * t))

    def draw_player(self, player, viewport: AABB2D) -> None:
        """在玩家 AABB 对应像素位置叠加玩家色块（调用方叠加）。"""
        pg = _pygame()
        ts = self.tile_size
        # 玩家浮点脚底坐标 → 屏幕像素（同瓦片映射）
        c = player.fx - viewport.min_x
        r = viewport.max_y - player.fy
        px = VIEW_OFFSET_X + c * ts
        py = HUD_TOP + r * ts
        w = player.width_f * ts
        h = player.height_f * ts
        body = pg.Surface((int(w), int(h)), pg.SRCALPHA)
        body.fill((230, 60, 60, 220))
        self.screen.blit(body, (int(px), int(py)))
        pg.draw.rect(self.screen, (255, 255, 255),
                     (int(px), int(py), int(w), int(h)), 2)
        # 朝向眼睛
        ex = int(px + (w * 0.7 if player.facing >= 0 else w * 0.3))
        pg.draw.rect(self.screen, (255, 255, 255),
                     (ex, int(py + h * 0.2), 4, 4))

    def draw_highlight(self, tx: int, ty: int, viewport: AABB2D) -> None:
        """在被瞄准瓦片叠加描边（调用方叠加，M1-R7）。"""
        pg = _pygame()
        ts = self.tile_size
        px, py = self._world_to_screen(tx, ty, viewport)
        pg.draw.rect(self.screen, (255, 255, 255), (px, py, ts, ts), 2)
        # 角标
        pg.draw.line(self.screen, (255, 230, 80), (px, py), (px + 8, py), 2)
        pg.draw.line(self.screen, (255, 230, 80), (px, py), (px, py + 8), 2)
