# -*- coding: utf-8 -*-
"""游戏状态枚举。"""
from enum import Enum

# ─────────────────────── 游戏状态枚举 ─────────────────────────
class GameState(Enum):
    START_SCREEN = "start"      # 开始界面
    LOADING = "loading"         # 加载中
    PLAYING = "playing"         # 游戏运行
    PAUSED = "paused"           # 暂停
    GAME_OVER = "game_over"     # 死亡结算
    QUIT = "quit"               # 退出
