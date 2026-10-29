# -*- coding: utf-8 -*-
"""KID-A WALKER —— 伪 3D 步行模拟器（模块化拆分版）。

分层：
    config / state          常量与状态机
    world                   地图生成（43 个房间模板 + 无限区块网格）
    systems                 玩法（能量 / 碎片 / 交互 / 能力 / 探索）
    audio                   区域合成 BGM + 音效
    render                  渲染（raycast 伪 3D；后续接入 moderngl 真 3D）
    ui                      HUD / 图鉴 / 加载界面 / 结算画面
    game                    主控状态机
"""
from .config import *  # noqa: F401,F403
from .state import GameState
from .world.worldmap import WorldMap
from .preload import LoadingTask, PreloadManager
from .systems.ability import AbilitySystem
from .systems.energy import EnergySystem
from .systems.exploration import ExplorationTracker
from .systems.fragments import FragmentSystem
from .systems.interaction import InteractionSystem
from .audio.synth import WalkerSynth, ZoneSynth
from .audio.sfx import SFXPlayer
from .render.particles import Particle
from .render.raycast import Renderer
from .ui.hud import draw_codex, draw_hud
from .ui.vignette import make_vignette
from .ui.loading import LoadingScreen
from .ui.death import DeathScreen
from .highscore import load_highscore, save_highscore
from .game import Game

__all__ = [
    "Game", "GameState", "WorldMap", "PreloadManager", "LoadingTask",
    "EnergySystem", "FragmentSystem", "InteractionSystem", "AbilitySystem",
    "ExplorationTracker", "ZoneSynth", "WalkerSynth", "SFXPlayer",
    "Particle", "Renderer", "draw_hud", "draw_codex", "make_vignette",
    "LoadingScreen", "DeathScreen", "load_highscore", "save_highscore",
]
