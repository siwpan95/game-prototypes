# -*- coding: utf-8 -*-
"""
MC2 探针测试 — 验证 MC2 已统一到 alloy 并真正使用该引擎能力

验证点：
  1. 去重统一：mcclone._engine 的 Serializable/JSONLoader/InputManager 与
     alloy 同一份实现（身份相同），不再内联重复代码。
  2. 世界生成/渲染：BlockRegistry(继承引擎 Serializable) + JSONLoader 加载，
     TerrainGenerator 生成，TextWorldRenderer 渲染出非空画面。
  3. 音频接入引擎：SoundEngine 默认后端为 alloy.audio.AudioSystem
     （EngineAudioBackend），play() 经引擎音频管线且不抛错。
  4. headless 可游玩：组装 GameLoop（引擎音频后端 + 粒子系统），触发挖掘事件
     驱动粒子与音效，连续 _update 不崩 → 证明游戏可运行、可玩。

运行方式：
    python tests/integration/test_mc2_probes.py
退出码：全部通过返回 0，否则 1。
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]          # D:/allin/MCclone
_MC2 = _ROOT / "MC2"
for _p in (str(_ROOT), str(_MC2)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from alloy.test import Probe, ProbeManager      # noqa: E402
import alloy.core.serializable as _eng_serializable   # noqa: E402
import alloy.utils.json_loader as _eng_json          # noqa: E402
import alloy.systems.input as _eng_input              # noqa: E402
import mcclone._engine as _mc2_engine                        # noqa: E402


def probe_mc2_engine_unified() -> tuple[bool, str]:
    """mcclone._engine 应与 alloy 同一份实现（去重验证）。"""
    ok = (
        _mc2_engine.Serializable is _eng_serializable.Serializable
        and _mc2_engine.JSONLoader is _eng_json.JSONLoader
        and _mc2_engine.InputManager is _eng_input.InputManager
    )
    detail = (
        f"Serializable={'同' if _mc2_engine.Serializable is _eng_serializable.Serializable else '异'}"
        f"；JSONLoader={'同' if _mc2_engine.JSONLoader is _eng_json.JSONLoader else '异'}"
        f"；InputManager={'同' if _mc2_engine.InputManager is _eng_input.InputManager else '异'}"
    )
    return ok, detail


def probe_mc2_world_gen_render() -> tuple[bool, str]:
    """世界生成与渲染（依赖引擎 Serializable + JSONLoader）。"""
    from mcclone.core.block_registry import BlockRegistry
    from mcclone.core.noise import PerlinNoise
    from mcclone.core.terrain import TerrainGenerator
    from mcclone.render.text_world_renderer import TextWorldRenderer
    from mcclone.core.geometry import AABB2D

    reg = BlockRegistry.from_json()
    seed = 12345
    w, h = 48, 20
    world = TerrainGenerator(reg, seed, PerlinNoise(seed)).generate(w, h)
    pic = TextWorldRenderer(reg).render(world, AABB2D(0, 0, w - 1, h - 1))
    ok = bool(pic) and len(pic.strip()) > 0
    detail = f"注册表方块={len(reg.ids())}种；世界={w}x{h}；渲染输出字符数={len(pic)}"
    return ok, detail


def probe_mc2_audio_engine_backend() -> tuple[bool, str]:
    """SoundEngine 应接入 alloy.audio.AudioSystem。"""
    from mcclone.audio.audio_fx import SoundEngine

    sound = SoundEngine()
    inited = sound.init()
    backend_name = type(sound.backend).__name__
    # play 不应抛错（headless 经引擎音频管线静默降级或真实播放）
    try:
        sound.play("dig")
        sound.play("place")
        play_ok = True
    except Exception as e:  # noqa: BLE001
        play_ok = False
        detail = f"play 抛错: {type(e).__name__}: {e}"
        return False, detail
    ok = inited and backend_name == "EngineAudioBackend" and play_ok
    detail = f"init={inited}；后端={backend_name}；play 安全={'是' if play_ok else '否'}"
    return ok, detail


def probe_mc2_headless_playable() -> tuple[bool, str]:
    """headless 组装 GameLoop 并连续更新，证明可运行可玩。"""
    from mcclone.core.geometry import AABB2D
    from mcclone.core.block_registry import BlockRegistry, STONE
    from mcclone.core.block_world import BlockWorld
    from mcclone.player.player import Player
    from mcclone.core.camera import Camera
    from mcclone.render.tile_world_renderer import TileWorldRenderer
    from mcclone.render.hud import HUD
    from mcclone.core.event_bus import EventBus, EventTypes
    from mcclone.audio.audio_fx import SoundEngine
    from mcclone.render.particles import ParticleSystem
    from mcclone.main_gui import GameLoop

    class _FakeInput:
        def left(self): return False
        def right(self): return False
        def jump_pressed(self): return False
        def craft_toggle_pressed(self): return False
        def craft_confirm_pressed(self): return False
        def craft_up_pressed(self): return False
        def craft_down_pressed(self): return False
        def layer_up_pressed(self): return False
        def layer_down_pressed(self): return False
        def temp_overlay_toggle(self): return False
        def water_overlay_toggle(self): return False
        def dig_mode_pressed(self): return False
        def build_mode_pressed(self): return False
        def cancel_job_pressed(self): return False
        def mouse_pos(self): return (0, 0)
        def mouse_pressed(self, b): return False
        def is_break_key_pressed(self): return False
        def is_place_key_pressed(self): return False
        def wheel_slot_delta(self): return 0
        def select_slot_pressed(self, i): return False
        def update(self): pass
        def escape_pressed(self): return False
        def debug_toggle_pressed(self): return False

    reg = BlockRegistry()
    reg.load_defaults()
    world = BlockWorld(16, 16, 1)
    for x in range(16):
        for y in range(3):
            world.set(x, y, 0, STONE)
    player = Player(1.0, 3.0, reg)
    camera = Camera(AABB2D(0, 0, 15, 15))
    bus = EventBus()
    sound = SoundEngine()
    sound.init()
    sound.subscribe(bus)
    particles = ParticleSystem()
    particles.subscribe(bus, reg)
    loop = GameLoop(None, world, player, camera, TileWorldRenderer(None, reg),
                    HUD(None), _FakeInput(), bus, 1, reg,
                    sound=sound, particles=particles)
    # 挖掘事件 → 粒子生成 + 经引擎音效播放
    bus.emit(EventTypes.BLOCK_BROKEN, x=2, y=3, id=1)
    particles_ok = len(particles._ps) >= 1
    # 连续更新（粒子 update + 脚步检测 + 生物 tick）不崩
    try:
        for _ in range(10):
            loop._update(1 / 60)
        tick_ok = True
    except Exception as e:  # noqa: BLE001
        tick_ok = False
        return False, f"_update 抛错: {type(e).__name__}: {e}"
    ok = particles_ok and tick_ok
    detail = (f"挖掘事件触发粒子={'是' if particles_ok else '否'}；"
              f"连续10帧更新不崩={'是' if tick_ok else '否'}；"
              f"音频后端={type(sound.backend).__name__}")
    return ok, detail


def build_manager() -> ProbeManager:
    mgr = ProbeManager()
    mgr.register(Probe("mc2_engine_unified", probe_mc2_engine_unified,
                       category="去重统一", priority=1, tags={"engine", "dedup"}))
    mgr.register(Probe("mc2_world_gen_render", probe_mc2_world_gen_render,
                       category="世界", priority=1, tags={"world"}))
    mgr.register(Probe("mc2_audio_engine_backend", probe_mc2_audio_engine_backend,
                       category="音频", priority=1, tags={"audio", "engine"}))
    mgr.register(Probe("mc2_headless_playable", probe_mc2_headless_playable,
                       category="可玩性", priority=1, tags={"playable"}))
    return mgr


def main() -> int:
    print("=" * 60)
    print("MC2 探针测试（统一到 alloy 验证）")
    print("=" * 60)
    mgr = build_manager()
    results = mgr.run_all()
    passed = sum(1 for r in results if r.success)
    print("=" * 60)
    print(f"总计: {len(results)}  通过: {passed}  失败: {len(results) - passed}")
    print("=" * 60)
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
