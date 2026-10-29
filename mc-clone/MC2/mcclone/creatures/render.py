# -*- coding: utf-8 -*-
"""creatures.render — 生物 / 作业精灵渲染（M4，T-M4-07 / R2）。

提供：
  - CreatureRenderer.draw(camera, renderer, creatures, jobs=None)：绘制生物 glyph
    （被动绿 / 敌对红）+ 受损生物血条 + 作业 glyph（dig▽ / build△）。

设计要点（架构 §2.1 / §7.5 / O17）：
  - 复用 tile_world_renderer._world_to_screen 同款像素映射公式；**tile_world_renderer.py
    本体不改造**。
  - 纯色块程序生成（同 TileWorldRenderer 风格），叠加 1px 描边。
  - headless（screen=None）时仅遍历验证，不 blit（不依赖显示设备）。
  - 仅依赖 geometry（AABB2D）/ block_registry / 本地 creatures 模块；pygame 延迟导入。
"""

from __future__ import annotations

from mcclone.render.tile_world_renderer import VIEW_OFFSET_X, HUD_TOP, TILE_SIZE
from mcclone.creatures.entity import CreatureKind


def _pygame():
    """延迟导入 pygame；不可用时抛出清晰错误。"""
    import pygame
    if pygame is None:
        raise RuntimeError("需要安装可选依赖 pygame 才能渲染生物")
    return pygame


# 生物 glyph 颜色（被动绿 / 敌对红，架构 §7.5）
_CREATURE_COLOR: dict = {
    CreatureKind.COW: (80, 200, 90),
    CreatureKind.PIG: (80, 200, 90),
    CreatureKind.ZOMBIE: (200, 60, 60),
}


class CreatureRenderer:
    """生物 / 作业精灵渲染器。"""

    def __init__(self, screen, registry) -> None:
        self.screen = screen
        self.registry = registry

    def draw(self, camera, renderer, creatures, jobs=None) -> None:
        """绘制生物 + 作业 glyph。

        参数：
            camera: Camera（提供 viewport: AABB2D）。
            renderer: TileWorldRenderer（仅取 tile_size，复用其像素映射）。
            creatures: CreatureSystem（提供 .creatures 只读列表）。
            jobs: JobSystem（提供 .jobs()）；None 不画作业 glyph。
        """
        viewport = camera.viewport
        ts = renderer.tile_size

        # headless：仅遍历验证，不 blit。
        if self.screen is None:
            _ = list(creatures.creatures)
            if jobs is not None:
                _ = list(jobs.jobs())
            return

        pg = _pygame()

        # 1) 生物 glyph
        for c in creatures.creatures:
            ccol = c.fx - viewport.min_x
            rrow = viewport.max_y - c.fy
            px = VIEW_OFFSET_X + ccol * ts
            py = HUD_TOP + rrow * ts
            w = max(1, int(c.width_f * ts))
            h = max(1, int(c.height_f * ts))
            color = _CREATURE_COLOR.get(c.kind, (200, 200, 200))
            body = pg.Surface((w, h), pg.SRCALPHA)
            body.fill((*color, 220))
            self.screen.blit(body, (int(px), int(py)))
            pg.draw.rect(self.screen, (255, 255, 255),
                         (int(px), int(py), w, h), 1)

            # 2) 受损生物血条（头顶，绿→红按 hp 比例）
            if c.hp < c.max_hp:
                self._draw_hp_bar(pg, int(px), int(py) - 6, w, c.hp / c.max_hp)

        # 3) 作业 glyph（M4-R2：在世界空间标记 dig▽ / build△）
        if jobs is not None:
            for job in jobs.jobs():
                jx, jy = renderer._world_to_screen(job.x, job.y, viewport)
                if job.type == "dig":
                    self._draw_triangle(pg, jx + ts // 2, jy + ts - 6, 7, (224, 200, 90), down=True)
                else:  # build
                    self._draw_triangle(pg, jx + ts // 2, jy + 6, 7, (80, 200, 200), down=False)

    def _draw_hp_bar(self, pg, x: int, y: int, w: int, ratio: float) -> None:
        """绘制一个小 HP 条（绿→红，宽∝hp/max_hp）。"""
        bw = max(8, w)
        bh = 4
        ratio = max(0.0, min(1.0, ratio))
        pg.draw.rect(self.screen, (40, 40, 40), (x, y, bw, bh))
        r = int(255 * (1.0 - ratio))
        g = int(255 * ratio)
        pg.draw.rect(self.screen, (r, g, 60), (x, y, int(bw * ratio), bh))
        pg.draw.rect(self.screen, (255, 255, 255), (x, y, bw, bh), 1)

    def _draw_triangle(self, pg, cx: int, cy: int, size: int,
                       color, down: bool) -> None:
        """绘制一个小三角标记（down=True 朝下▽，否则朝上△）。"""
        if down:
            pts = [(cx - size, cy - size), (cx + size, cy - size), (cx, cy + size)]
        else:
            pts = [(cx - size, cy + size), (cx + size, cy + size), (cx, cy - size)]
        pg.draw.polygon(self.screen, color, pts)
