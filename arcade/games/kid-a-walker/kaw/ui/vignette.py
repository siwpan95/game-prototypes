# -*- coding: utf-8 -*-
"""暗角遮罩。"""
import math

import pygame

# ─────────────────────── 暗角遮罩（减弱版本） ─────────────────────────
def make_vignette(w, h):
    v = pygame.Surface((w, h), pygame.SRCALPHA)
    cx, cy = w // 2, h // 2
    max_r = int(math.sqrt(cx*cx + cy*cy))
    for radius in range(max_r, max_r - 100, -6):
        t = (max_r - radius) / 100.0
        alpha = int(min(40, t * 40))  # 最大透明度从90减到40
        pygame.draw.circle(v, (0, 0, 0, alpha), (cx, cy), radius, 6)
    return v
