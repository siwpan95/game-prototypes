# -*- coding: utf-8 -*-
"""模拟内核配置 — 仅模拟相关参数，从 src.config.settings 单源再导出。

UI 相关参数（GAME_TITLE / WINDOW_WIDTH / HEIGHT / FPS）保留在 src.config.settings。
未来 Godot 桥接层从此处取模拟参数，避免反向依赖 app 配置。
"""
from src.config.settings import (  # noqa: F401
    HP_REGEN_RATE, LOOT_INTERVAL, REGION_CHANGE_INTERVAL,
    ENEMY_RESPAWN_DELAY, MAX_LOG_ENTRIES,
    exp_to_next_level, is_region_suitable,
)
