# -*- coding: utf-8 -*-
"""地图机关（Phase 7）：矿坑·矿车冲撞 / 神庙·神柱脉冲。

数据来自 data.MAPS 的 carts / pillar 字段；无该字段的地图零开销。
"""
import math
import random

from settings import COL


# ================================================================ 矿车
def _tick_carts(game, dt, cfg):
    game.cart_t -= dt
    # 预警期：亮箭头方向（draw 处理），到时发车
    if game.cart_t <= -cfg["warn"] and not game.carts:
        p = game.player
        a = random.uniform(0, math.tau)
        x = p.x + math.cos(a) * 980.0
        y = p.y + math.sin(a) * 980.0
        game.carts.append(dict(x=x, y=y, vx=-math.cos(a) * cfg["speed"],
                               vy=-math.sin(a) * cfg["speed"], life=6.0))
        game._floater("矿车来袭！", (222, 150, 60), 22)
        game.cart_t = cfg["period"]
    # 行进 + 碰撞
    p = game.player
    for c in game.carts[:]:
        c["x"] += c["vx"] * dt
        c["y"] += c["vy"] * dt
        c["life"] -= dt
        d2 = (c["x"] - p.x) ** 2 + (c["y"] - p.y) ** 2
        if d2 <= 36.0 ** 2:
            if game.hurt_player(cfg["dmg"]):
                game.hurt_flash = 0.35
            c["life"] = 0.0
        for e in game.enemies[:]:
            if (c["x"] - e.x) ** 2 + (c["y"] - e.y) ** 2 <= (34 + e.radius) ** 2:
                game.deal_damage(e, 60.0, flat=True, proc=False)
        if c["life"] <= 0:
            game.carts.remove(c)


def _draw_carts(game, surf, cx, cy):
    import pygame
    for c in game.carts:
        sx, sy = int(c["x"] - cx), int(c["y"] - cy)
        ang = -math.degrees(math.atan2(c["vy"], c["vx"]))
        body = pygame.Surface((44, 26), pygame.SRCALPHA)
        pygame.draw.rect(body, (146, 100, 56), (0, 0, 44, 26), border_radius=6)
        pygame.draw.rect(body, (204, 150, 80), (0, 0, 44, 26), 2, border_radius=6)
        pygame.draw.rect(body, (60, 48, 36), (8, 6, 12, 14))
        pygame.draw.circle(body, (40, 34, 28), (10, 24), 5)
        pygame.draw.circle(body, (40, 34, 28), (34, 24), 5)
        rot = pygame.transform.rotate(body, ang)
        surf.blit(rot, (sx - rot.get_width() // 2, sy - rot.get_height() // 2))


# ================================================================ 神柱脉冲
def _tick_pillar(game, dt, cfg):
    p = game.player
    game.pillar_t -= dt
    w = game.pillar_wave
    if w is not None:
        w["t"] -= dt
        if w["t"] <= 0:
            game.pillar_wave = None
    if game.pillar_t <= 0:
        game.pillar_t = cfg["period"]
        a = random.uniform(0, math.tau)
        d = random.uniform(300.0, 500.0)
        game.pillar_wave = dict(x=p.x + math.cos(a) * d,
                                y=p.y + math.sin(a) * d,
                                t=cfg["warn"] + 0.5, warn=cfg["warn"])
        game._floater("神柱轰鸣……", (210, 190, 120), 20)
    if w is not None and w["t"] <= 0.5:      # 预警结束：推人
        dx, dy = p.x - w["x"], p.y - w["y"]
        d = math.hypot(dx, dy) or 1.0
        if d <= cfg["radius"]:
            k = 1.0 - d / cfg["radius"]
            p.x += dx / d * cfg["push"] * (0.4 + 0.6 * k)
            p.y += dy / d * cfg["push"] * (0.4 + 0.6 * k)
            if not game.pillar_pushed:
                game.pillar_pushed = True
                game._floater("被神柱推开！", (210, 190, 120), 20)
        if not game.pillar_pushed:
            game.pillar_pushed = False


def _draw_pillar(game, surf, cx, cy):
    import pygame
    w = game.pillar_wave
    if w is None:
        return
    sx, sy = int(w["x"] - cx), int(w["y"] - cy)
    if w["t"] > w["warn"]:
        r = int(20 + 10 * math.sin(pygame.time.get_ticks() * 0.01))
        pygame.draw.circle(surf, (210, 190, 120), (sx, sy), r, 2)
    else:
        k = max(0.0, w["t"] / 0.5)
        r = int(440 * (1.0 - k))
        pygame.draw.circle(surf, (220, 200, 130), (sx, sy), max(2, r), 3)
        pygame.draw.circle(surf, (150, 130, 80), (sx, sy), 60, 2)


# ================================================================ 总入口
def tick(game, dt):
    th = game.theme
    if th.get("carts"):
        _tick_carts(game, dt, th["carts"])
    if th.get("pillar"):
        _tick_pillar(game, dt, th["pillar"])


def draw(game, surf, cx, cy):
    th = game.theme
    if th.get("carts"):
        _draw_carts(game, surf, cx, cy)
    if th.get("pillar"):
        _draw_pillar(game, surf, cx, cy)
