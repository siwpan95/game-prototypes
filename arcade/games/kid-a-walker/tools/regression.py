# -*- coding: utf-8 -*-
"""KID-A WALKER 回归测试（无窗口，dummy SDL 驱动）。

    D:\\Python314\\python.exe tools\\regression.py

两段测试：
  A. 确定性回放 —— 固定种子 + 脚本化输入跑 120 帧，打印 5 个关键帧的逐像素
     画面哈希与终局玩法状态。改动渲染/逻辑后对比输出，即可知道是否动了不该动的东西。
  B. 完整生命周期 —— 开始界面 → 预加载 → 游戏 → 死亡结算 → 重开 → 再进游戏，
     覆盖 PreloadManager / _initialize_game / 渲染后端选择 / _restart 这些真实路径。

注意：A 段的画面哈希会随渲染后端（RENDER_BACKEND）改变，这是预期行为；
玩法状态（位姿/能量/碎片/探索数）则应当始终稳定。
"""
import hashlib
import os
import random
import sys
import time

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("SDL_WINDOWS_DPI_AWARENESS", "permonitorv2")

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import pygame  # noqa: E402

import kaw  # noqa: E402

SEED = 20261009


class FakeKeys:
    def __init__(self):
        self.d = {}

    def __getitem__(self, k):
        return self.d.get(k, False)

    def clear(self):
        self.d.clear()


def frame_hash(surf):
    return hashlib.sha256(surf.get_buffer().raw).hexdigest()[:16]


def part_a():
    print("=" * 62)
    print("A. 确定性回放（120 帧）")
    print("=" * 62)
    random.seed(SEED)
    g = kaw.Game()
    g.world = kaw.WorldMap(seed=SEED)
    g.renderer = g._make_renderer()
    g.renderer._ensure_bg_cache()
    g.vignette = kaw.make_vignette(kaw.W, kaw.H)
    g.synth = None
    g.px, g.py = g.world.find_safe_spawn(0, 0)
    g.pang = 0.0
    g.last_chunk = g.world.world_to_chunk(g.px, g.py)
    g._last_zone_chunk = g.last_chunk
    g.dominant_zone = 5
    g.state = kaw.GameState.PLAYING

    held = FakeKeys()
    pygame.key.get_pressed = lambda: held
    print(f"渲染后端: {type(g.renderer).__name__}")

    for f in range(1, 121):
        held.clear()
        if f < 30:
            held.d[pygame.K_w] = True
        elif f < 60:
            held.d[pygame.K_a] = True
        elif f < 90:
            held.d[pygame.K_w] = True
            held.d[pygame.K_d] = True
        else:
            held.d[pygame.K_s] = True
        if f in (25, 70, 110):
            pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_e))
        g._handle_playing(1.0 / 60.0)
        if f in (1, 30, 60, 90, 120):
            print(f"  frame {f:3d}  screen={frame_hash(g.screen)}  "
                  f"pos=({g.px:.4f},{g.py:.4f})  ang={g.pang:.4f}  "
                  f"nrg={g.energy.energy:.4f}")

    print(f"  终局 pos=({g.px:.6f},{g.py:.6f}) ang={g.pang:.6f}")
    print(f"  能量={g.energy.energy:.6f}  碎片={g.fragments.get_total()}  "
          f"探索={g.exploration.get_explored_count()}  tick={g.tick}")


def part_b():
    print("=" * 62)
    print("B. 完整生命周期")
    print("=" * 62)
    held = FakeKeys()
    pygame.key.get_pressed = lambda: held

    g = kaw.Game()
    g.menu_synth = kaw.ZoneSynth()
    for _ in range(5):
        g._handle_start_screen(1 / 60)
    print(f"  开始界面       {g.state.value}")

    g._start_loading()
    t0 = time.time()
    n = 0
    while g.state == kaw.GameState.LOADING and n < 5000 and time.time() - t0 < 20:
        g._handle_loading()
        n += 1
    print(f"  加载完成       {time.time()-t0:5.2f}s / {n} 帧 → {g.state.value}"
          f"  后端={type(g.renderer).__name__}  区块={len(g.world.generated_chunks())}")

    held.d[pygame.K_w] = True
    for i in range(300):
        if i == 100:
            held.d[pygame.K_d] = True
        if i == 150:
            held.d[pygame.K_d] = False
        if i == 200:
            held.d[pygame.K_r] = True
        if i == 210:
            held.d[pygame.K_r] = False
        g._handle_playing(1 / 60)
        if g.state != kaw.GameState.PLAYING:
            break
    print(f"  游戏 {g.tick} 帧     pos=({g.px:.2f},{g.py:.2f}) pitch={g.pitch:.1f} "
          f"nrg={g.energy.energy:.1f} 探索={g.exploration.get_explored_count()} "
          f"鼠标已抓={not g._grab_released}")

    g.energy.energy = 0.0
    g.energy.grace_timer = 0.0
    g._handle_playing(1 / 60)
    for _ in range(5):
        g._handle_game_over(1 / 60)
    print(f"  能量耗尽       {g.state.value}  鼠标已释放={g._grab_released}")

    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_r))
    g._handle_game_over(1 / 60)
    print(f"  按 R 重开      {g.state.value}  world={g.world}  renderer={g.renderer}")

    g.menu_synth = kaw.ZoneSynth()
    g._start_loading()
    n = 0
    while g.state == kaw.GameState.LOADING and n < 5000:
        g._handle_loading()
        n += 1
    for _ in range(10):
        g._handle_playing(1 / 60)
    print(f"  二次进入       {g.state.value}  后端={type(g.renderer).__name__}")

    for s in (g.synth, g.menu_synth):
        if s:
            s.running = False
    print("  生命周期跑通。")


if __name__ == "__main__":
    part_a()
    part_b()
