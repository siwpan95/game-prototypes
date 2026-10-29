# -*- coding: utf-8 -*-
"""hud — pygame HUD 绘制（顶部状态条 / 快捷栏 / 提示条 / 合成 overlay）。

提供：
  - HUD.draw(player, world, fps, seed, overlays_on=False, daynight=None)：
    顶部坐标/手持/HP/饥饿/时间；底部快捷栏（计数+高亮）；提示条；
    可选 daynight 时绘制时钟与昼夜图标。

M2 扩展（T-M2-07）：
  - 顶部条新增 HP 红条 / 饥饿黄条 / 时间+昼夜图标。
  - 快捷栏显示各槽计数（player.inventory.slot(i).count），高亮 selected_slot。
  - _draw_crafting_overlay(crafting, sel, player)：文本列表 overlay。

本模块仅在真实 GUI 运行期绘制；导入期不依赖 pygame（延迟导入）。
daynight=None 时退化为 M1 行为（向后兼容）。
"""

from __future__ import annotations

import os

# 屏幕映射常量（与 camera.py / tile_world_renderer.py 共享）。
HUD_TOP: int = 28
HUD_BOTTOM: int = 48
TILE_SIZE: int = 32


def _pygame():
    """延迟导入 pygame；不可用时抛出清晰错误。"""
    import pygame
    if pygame is None:
        raise RuntimeError("需要安装可选依赖 pygame 才能绘制 HUD")
    return pygame


class HUD:
    """pygame HUD 绘制器（顶部状态条 / 快捷栏 / 提示条 / 合成 overlay）。"""

    def __init__(self, screen) -> None:
        self.screen = screen

    def draw(self, player, world, fps, seed, overlays_on: bool = False,
             daynight=None, current_z=None, show_temp: bool = False,
             show_water: bool = False, jobs=None,
             creature_count: int = 0, nearest_hp: float = 0.0,
             nearest_max: float = 0.0) -> None:
        """绘制整块 HUD（顶部条 + 快捷栏 + 提示条）。

        headless（screen=None）时直接返回（不依赖显示设备），供测试验证
        新参数签名与属性读取（T-M4-10）。真实 GUI 运行期 screen 永不为 None。
        """
        if self.screen is None:
            return

        self._draw_top_bar(player, world, fps, seed, daynight,
                           current_z, show_temp, show_water, creature_count)
        self._draw_hotbar(player)
        self._draw_hint_bar(overlays_on)
        if jobs is not None:
            self._draw_jobs(jobs)
        if nearest_max > 0:
            self._draw_nearest_hp(nearest_hp, nearest_max)

    def _draw_top_bar(self, player, world, fps, seed, daynight=None,
                      current_z=None, show_temp: bool = False,
                      show_water: bool = False, creature_count: int = 0) -> None:
        """顶部状态条：坐标/手持/FPS/种子/Z + HP/饥饿条 + 时间/昼夜 + 生物计数。"""
        pg = _pygame()
        bar_h = HUD_TOP
        pg.draw.rect(self.screen, (20, 20, 30),
                     (0, 0, self.screen.get_width(), bar_h))
        try:
            held_name = player.registry.get(player.held_id).name
        except Exception:
            held_name = str(player.held_id)
        z = current_z if current_z is not None else getattr(player, "z", 0)
        depth = getattr(world, "depth", 1)
        base = (f"XY:({player.fx:.0f},{player.fy:.0f}) Z:{z}/{depth-1} "
                f"手持:{held_name} FPS:{fps:.0f} 种子:{seed}")
        self._text(base, 6, 6, (230, 230, 230))
        # M4：生物计数（顶部条右侧、时间左侧）
        self._text(f"生物:{creature_count}", 250, 6, (200, 230, 200))

        # M3：覆盖层开关态指示
        ov = f"T温:{'开' if show_temp else '关'} V水:{'开' if show_water else '关'}"
        self._text(ov, 320, 6, (210, 230, 210))

        # HP / 饥饿条（右上）
        bx = self.screen.get_width() - 240
        self._draw_stat_bar(bx, 6, 110, 14,
                            player.hp / player.max_hp, (200, 60, 60), "HP")
        self._draw_stat_bar(bx + 120, 6, 110, 14,
                            player.hunger / player.max_hunger, (224, 200, 90),
                            "饥饿")

        # 时间 / 昼夜（daynight 提供）
        if daynight is not None:
            mark = "[夜]" if daynight.is_night() else "[昼]"
            txt = f"时间:{daynight.time_str()}{mark}"
            self._text(txt, self.screen.get_width() // 2 - 60, 6, (230, 230, 200))

    def _draw_stat_bar(self, x, y, w, h, ratio, color, label) -> None:
        """绘制一个状态条（背景 + 填充 + 边框 + 文本）。"""
        pg = _pygame()
        ratio = max(0.0, min(1.0, ratio))
        pg.draw.rect(self.screen, (40, 40, 40), (x, y, w, h))
        pg.draw.rect(self.screen, color, (x, y, int(w * ratio), h))
        pg.draw.rect(self.screen, (255, 255, 255), (x, y, w, h), 1)
        self._text(f"{label}:{ratio * 100:.0f}%", x + 3, y + 1, (235, 235, 235))

    def _draw_nearest_hp(self, hp: float, max_hp: float) -> None:
        """绘制右侧「最近生物 HP」条（M4，T-M4-10；无生物时由调用方隐藏）。"""
        pg = _pygame()
        bx = self.screen.get_width() - 240
        by = HUD_TOP + 6
        self._text("最近生物", bx, by, (210, 230, 210))
        self._draw_stat_bar(bx, by + 16, 110, 14,
                            hp / max_hp if max_hp > 0 else 0.0,
                            (200, 60, 60), "HP")

    def _draw_hotbar(self, player) -> None:
        """底部快捷栏：1-6 槽 + 高亮当前手持 + 各槽数量。"""
        pg = _pygame()
        slot = 40
        gap = 4
        total = len(player.hotbar) * (slot + gap)
        x0 = (self.screen.get_width() - total) // 2
        y = self.screen.get_height() - HUD_BOTTOM + 8
        for i, bid in enumerate(player.hotbar):
            x = x0 + i * (slot + gap)
            color = (120, 120, 60) if i == player.selected_slot else (60, 60, 70)
            pg.draw.rect(self.screen, color, (x, y, slot, slot))
            pg.draw.rect(self.screen, (255, 255, 255), (x, y, slot, slot), 2)
            try:
                name = player.registry.get(bid).name
            except Exception:
                name = str(bid)
            self._text(str(i + 1), x + 3, y + 2, (200, 200, 200))
            self._text(name[:6], x + 3, y + slot - 14, (230, 230, 230))
            # 数量（来自背包；空槽不显示）
            it = player.inventory.slot(i)
            if it is not None:
                self._text(str(it[1]), x + slot - 18, y + 2, (180, 255, 180))

    def _draw_hint_bar(self, overlays_on: bool) -> None:
        """底部提示条。"""
        pg = _pygame()
        bar_h = HUD_BOTTOM
        y0 = self.screen.get_height() - bar_h
        pg.draw.rect(self.screen, (20, 20, 30),
                     (0, y0, self.screen.get_width(), bar_h))
        hint = ("A/D 移动 · Space 跳 · 左键挖 · 右键放 · 鼠标瞄准 · "
                "1-6/滚轮切换 · E 合成 · Esc 退出 · F3 调试"
                + (" [覆盖层:开]" if overlays_on else ""))
        self._text(hint, 6, y0 + 16, (200, 200, 200))

    def _draw_crafting_overlay(self, crafting, sel: int, player) -> None:
        """合成 overlay：文本列表，高亮 sel，提示操作。"""
        pg = _pygame()
        recipes = crafting.recipes
        pw, ph = 380, 230
        px = (self.screen.get_width() - pw) // 2
        py = (self.screen.get_height() - ph) // 2
        panel = pg.Surface((pw, ph))
        panel.set_alpha(225)
        panel.fill((18, 18, 28))
        self.screen.blit(panel, (px, py))
        pg.draw.rect(self.screen, (255, 255, 255), (px, py, pw, ph), 2)
        self._text("合成 (E 退出)", px + 12, py + 10, (235, 235, 235))
        if not recipes:
            self._text("（无可用配方）", px + 14, py + 40, (200, 200, 200))
        else:
            for idx, r in enumerate(recipes):
                prefix = "▶" if idx == sel else "  "
                can = crafting.can_craft(r.id, player.inventory)
                mark = "可合成" if can else "材料不足"
                line = f"{prefix}{r.name} [{mark}]"
                color = (180, 255, 180) if idx == sel else (205, 205, 205)
                self._text(line, px + 16, py + 38 + idx * 24, color)
        self._text("↑/↓ 选择 · Enter 合成 · E 退出",
                   px + 12, py + ph - 24, (200, 200, 200))

    def _draw_jobs(self, jobs) -> None:
        """绘制活动作业列表（右侧，M3；最多显示 6 条）。

        jobs: JobSystem.jobs() 返回的可迭代对象，元素具
        type/id/x/y/z/progress_ratio() 属性（鸭子类型，避免循环导入）。
        """
        pg = _pygame()
        items = list(jobs)
        x = self.screen.get_width() - 240
        y0 = HUD_TOP + 22
        self._text("作业:", x, y0, (200, 230, 255))
        if not items:
            self._text("无作业", x + 40, y0, (180, 180, 180))
            return
        for i, job in enumerate(items[:6]):
            pr = getattr(job, "progress_ratio", None)
            ratio = pr() if callable(pr) else 0.0
            line = (f"{job.type} #{job.id} "
                    f"({job.x},{job.y},{job.z}) {ratio * 100:.0f}%")
            self._text(line, x, y0 + 18 + i * 16, (210, 230, 210))

    # 字体缓存：避免每次绘制都重建字体。
    _font_cache: dict = {}
    # 本地字体候选（优先自本文件向上遍历到的项目目录下的中文友好字体；直接用文件加载，
    # 规避 SysFont 在 Windows + Python3.14 下枚举系统字体崩溃的问题）。
    _FONT_NAMES = ("SmileySans-Oblique-2.ttf", "SmileySans-Oblique-3.otf")
    _local_font_path = None  # 启动时查找一次

    @classmethod
    def _find_local_font(cls):
        """从当前文件位置向上遍历目录，定位本地字体文件。"""
        if cls._local_font_path is not None:
            return cls._local_font_path
        cur = os.path.abspath(__file__)
        seen = set()
        while True:
            d = os.path.dirname(cur)
            if d in seen:
                break
            seen.add(d)
            for name in cls._FONT_NAMES:
                p = os.path.join(d, name)
                if os.path.isfile(p):
                    cls._local_font_path = p
                    return p
            if d == cur:  # 已到达根目录
                break
            cur = d
        return None

    def _get_font(self, size: int):
        """获取缓存字体；优先本地字体文件，失败回退内置默认字体。"""
        cache = HUD._font_cache
        if size not in cache:
            pg = _pygame()
            font = None
            path = HUD._find_local_font()
            if path is not None:
                try:
                    font = pg.font.Font(path, size)
                except Exception:
                    font = None
            if font is None:
                font = pg.font.Font(None, size)
            cache[size] = font
        return cache[size]

    def _text(self, s: str, x: int, y: int, color) -> None:
        """用本地/默认字体绘制一行文本。"""
        pg = _pygame()
        font = self._get_font(16)
        surf = font.render(s, True, color)
        self.screen.blit(surf, (x, y))