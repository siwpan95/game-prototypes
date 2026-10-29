# -*- coding: utf-8 -*-
"""HUD 与碎片图鉴页。"""
import math

import pygame

from ..config import C_ACCENT, C_HUD, FRAGMENT_TYPES, H, W

# ─────────────────────── HUD ─────────────────────────
# 区域类型名称映射
ZONE_NAMES = {
    2: "AETHER GLOW",     # 青绿发光
    3: "RED ALERT",       # 红色警示
    4: "TREASURY",        # 金色宝库
    5: "VERDANT GARDEN",  # 绿色植被
    6: "ENERGY CORE",     # 紫色能量
    7: "FIRE EXIT",       # 橙色出口
    8: "RUINS",           # 灰色碎石
    9: "TECH NOOK",       # 科技装饰
    10: "CRYSTAL CAVE",   # 蓝色水晶
    11: "MYSTIC ALTAR",   # 紫水晶
    12: "PORTAL GATE",    # 传送门
}

# 区域颜色
ZONE_COLORS = {
    2: (0, 255, 200),
    3: (220, 60, 60),
    4: (220, 180, 60),
    5: (60, 200, 100),
    6: (180, 80, 240),
    7: (255, 150, 60),
    8: (140, 140, 150),
    9: (80, 220, 255),
    10: (100, 180, 255),
    11: (160, 80, 220),
    12: (255, 255, 100),
}

def draw_hud(surf, f_sm, f_bg, tick, pos, chunk_coord, current_zone=2,
             energy=None, fragments=None, interaction_in_range=False,
             shielded=False, danger_near=False):
    """增强版HUD：能量条、碎片计数、危险提示、交互提示"""
    bar_h = 48
    pygame.draw.rect(surf, (0, 4, 18), (0, H - bar_h, W, bar_h))
    pygame.draw.line(surf, C_ACCENT,   (0, H - bar_h), (W, H - bar_h), 1)

    ts    = tick // 60
    t_str = f"{ts // 60:02d}:{ts % 60:02d}"
    cx, cy = chunk_coord
    zone_name = ZONE_NAMES.get(current_zone, "UNKNOWN")
    zone_color = ZONE_COLORS.get(current_zone, C_ACCENT)
    coord = f"[{pos[0]:.1f}, {pos[1]:.1f}]  SECTOR ({cx},{cy})"

    lbl1 = f_sm.render(f"POS {coord}", True, C_HUD)
    lbl2 = f_sm.render(f"KID-A WALKER  //  {t_str}", True, C_ACCENT)
    zone_lbl = f_sm.render(f"ZONE: {zone_name}", True, zone_color)
    lbl3 = f_sm.render("WASD MOVE | MOUSE LOOK | R/F PITCH | E USE | TAB CODEX | ESC QUIT",
                       True, (0, 70, 110))

    surf.blit(lbl1, (16, H - bar_h + 5))
    surf.blit(lbl2, (W // 2 - lbl2.get_width() // 2, H - bar_h + 5))
    surf.blit(zone_lbl, (W // 2 - zone_lbl.get_width() // 2, H - bar_h + 20))
    surf.blit(lbl3, (W - lbl3.get_width() - 16, H - bar_h + 5))

    # ─── 能量条 ───
    if energy is not None:
        ebar_x, ebar_y = 16, H - bar_h + 24
        ebar_w, ebar_h = 200, 12
        # 背景
        pygame.draw.rect(surf, (15, 15, 30), (ebar_x, ebar_y, ebar_w, ebar_h))
        # 填充（渐变色：青绿→黄→红）
        ratio = energy.get_ratio()
        fill_w = int(ebar_w * ratio)
        if fill_w > 0:
            for i in range(fill_w):
                t = i / ebar_w  # 0~1 从左到右
                if t < 0.5:
                    # 青绿(0,255,200) → 黄(255,255,0)
                    r = int(0 + 255 * (t * 2))
                    g = 255
                    b = int(200 * (1 - t * 2))
                else:
                    # 黄(255,255,0) → 红(255,50,50)
                    t2 = (t - 0.5) * 2
                    r = 255
                    g = int(255 - 205 * t2)
                    b = int(50 * t2)
                pygame.draw.line(surf, (r, g, b),
                                 (ebar_x + i, ebar_y + 1),
                                 (ebar_x + i, ebar_y + ebar_h - 1))
        # 护盾高亮
        if shielded:
            pulse = abs(math.sin(tick * 0.15))
            shield_col = (100, int(200 + 55 * pulse), 255)
            pygame.draw.rect(surf, shield_col, (ebar_x, ebar_y, ebar_w, ebar_h), 2)
        else:
            pygame.draw.rect(surf, (40, 80, 100), (ebar_x, ebar_y, ebar_w, ebar_h), 1)

        # 能量数值
        e_text = f_sm.render(f"NRG {int(energy.energy)}", True, (180, 220, 240))
        surf.blit(e_text, (ebar_x + ebar_w + 8, ebar_y - 2))

        # 出生保护期提示
        if energy.grace_timer > 0:
            grace_sec = int(energy.grace_timer) + 1
            pulse = abs(math.sin(tick * 0.1))
            grace_col = (int(50 + 200 * pulse), 255, int(180 + 75 * pulse))
            grace_text = f_sm.render(f"GRACE {grace_sec}s", True, grace_col)
            surf.blit(grace_text, (ebar_x + ebar_w + 8, ebar_y + 10))

    # ─── 碎片计数（右上角） ───
    if fragments is not None:
        frag_text = f_sm.render(
            f"FRAGMENTS: {fragments.get_total()} ({fragments.get_unique_types()}/{FRAGMENT_TYPES})",
            True, (200, 200, 255))
        surf.blit(frag_text, (W - frag_text.get_width() - 16, 8))

    # ─── 区域危险提示（中央偏下） ───
    if danger_near and current_zone == 3:
        pulse = abs(math.sin(tick * 0.12))
        warn_col = (int(200 + 55 * pulse), int(40 + 30 * pulse), int(40 + 30 * pulse))
        warn_text = f_sm.render("⚠ DANGER ZONE ⚠", True, warn_col)
        surf.blit(warn_text, (W // 2 - warn_text.get_width() // 2, H // 2 + 80))

    # ─── 交互提示 ───
    if interaction_in_range:
        pulse = abs(math.sin(tick * 0.1))
        col = (int(0 + 100 * pulse), int(255 - 55 * pulse), int(200))
        hint = f_sm.render("[E] INTERACT", True, col)
        surf.blit(hint, (W // 2 - hint.get_width() // 2, H // 2 + 50))

    # ─── 危险预警边框闪烁 ───
    if danger_near:
        pulse = abs(math.sin(tick * 0.15))
        border_alpha = int(80 * pulse)
        border_surf = pygame.Surface((W, H), pygame.SRCALPHA)
        # 四边红色半透明边框
        for thickness in range(3):
            pygame.draw.rect(border_surf, (220, 40, 40, border_alpha),
                             (thickness, thickness, W - thickness * 2, H - thickness * 2), 2)
        surf.blit(border_surf, (0, 0))

    if tick < 360:
        alpha = min(255, tick * 2)
        t = f_bg.render("KID-A WALKER", True, C_ACCENT)
        t.set_alpha(alpha)
        surf.blit(t, (W // 2 - t.get_width() // 2, 22))

    # 准星
    hcx, hcy = W // 2, H // 2
    for dx, dy, ln in [(-1,0,9),(1,0,9),(0,-1,9),(0,1,9)]:
        pygame.draw.line(surf, C_ACCENT,
                         (hcx + dx * 3, hcy + dy * 3),
                         (hcx + dx * (3 + ln), hcy + dy * (3 + ln)), 1)


def draw_codex(surf, f_sm, fragments):
    """碎片图鉴页（Tab切换）：展示10种碎片收集进度"""
    overlay = pygame.Surface((W, H), pygame.SRCALPHA)
    overlay.fill((1, 3, 15, 240))
    surf.blit(overlay, (0, 0))

    # 标题
    title = f_sm.render("FRAGMENT CODEX", True, C_ACCENT)
    surf.blit(title, (W // 2 - title.get_width() // 2, 40))

    # 碎片类型信息
    type_info = [
        (2, "AETHER GLOW",    (0, 255, 200)),
        (3, "RED ALERT",      (220, 60, 60)),
        (4, "TREASURY",       (220, 180, 60)),
        (5, "VERDANT GARDEN", (60, 200, 100)),
        (6, "ENERGY CORE",    (180, 80, 240)),
        (7, "FIRE EXIT",      (255, 150, 60)),
        (8, "RUINS",          (140, 140, 150)),
        (9, "TECH NOOK",      (80, 220, 255)),
        (10, "CRYSTAL CAVE",  (100, 180, 255)),
        (11, "MYSTIC ALTAR",  (160, 80, 220)),
    ]

    start_y = 80
    row_h = 50
    col_w = W // 2

    for idx, (dtype, name, color) in enumerate(type_info):
        col_idx = idx % 2
        row_idx = idx // 2
        bx = 60 + col_idx * col_w
        by = start_y + row_idx * row_h

        count = fragments.get_count(dtype)
        in_codex = dtype in fragments.codex
        has_any = count > 0

        # 类型颜色标记块
        display_col = color if has_any else (40, 40, 60)
        pygame.draw.rect(surf, display_col, (bx, by, 20, 20))
        pygame.draw.rect(surf, (80, 80, 100), (bx, by, 20, 20), 1)

        # 名称和计数
        name_col = color if has_any else (60, 60, 80)
        name_text = f_sm.render(f"{name}", True, name_col)
        surf.blit(name_text, (bx + 28, by))

        count_text = f_sm.render(f"x{count}", True, (200, 200, 255) if has_any else (60, 60, 80))
        surf.blit(count_text, (bx + 28, by + 16))

        # 收集进度条（满5为被动能力）
        bar_x = bx + 140
        bar_y = by + 8
        bar_w = 120
        bar_h = 8
        pygame.draw.rect(surf, (20, 20, 35), (bar_x, bar_y, bar_w, bar_h))
        fill = min(count, 5)
        fill_w = int(bar_w * fill / 5)
        if fill_w > 0:
            for i in range(fill_w):
                t = i / bar_w
                fc = tuple(min(255, int(c * (0.5 + 0.5 * t))) for c in color)
                pygame.draw.line(surf, fc, (bar_x + i, bar_y + 1), (bar_x + i, bar_y + bar_h - 1))
        pygame.draw.rect(surf, (60, 60, 80), (bar_x, bar_y, bar_w, bar_h), 1)

        # 被动能力标记
        if count >= 5:
            passive = f_sm.render("PASSIVE", True, (255, 255, 100))
            surf.blit(passive, (bar_x + bar_w + 8, bar_y - 2))

        # 图鉴标记（跨局）
        if in_codex and not has_any:
            codex_mark = f_sm.render("[DISCOVERED]", True, (80, 80, 100))
            surf.blit(codex_mark, (bx + 140, by + 16))

    # 底部统计
    total = fragments.get_total()
    unique = fragments.get_unique_types()
    all_collected = fragments.is_all_types_collected()

    stats_y = start_y + 5 * row_h + 10
    stats_text = f_sm.render(f"TOTAL: {total}  |  TYPES: {unique}/10", True, C_HUD)
    surf.blit(stats_text, (W // 2 - stats_text.get_width() // 2, stats_y))

    if all_collected:
        bonus = f_sm.render("ALL TYPES COLLECTED - DANGER IMMUNE!", True, (255, 255, 100))
        surf.blit(bonus, (W // 2 - bonus.get_width() // 2, stats_y + 20))

    hint = f_sm.render("TAB / ESC close", True, (0, 70, 110))
    surf.blit(hint, (W - hint.get_width() - 20, H - 30))
