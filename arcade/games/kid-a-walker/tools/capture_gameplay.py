# -*- coding: utf-8 -*-
"""完整录制一遍游戏流程（无窗口，offscreen GL 全管线含 bloom）。

走真实状态机：开始界面 → 加载 → 游玩（脚本化输入漫游）→ 能量耗尽
死亡 → 结算 → 按 R 重开 → 二次进入。每 2 个逻辑帧（60Hz）抓取最终
合成画面（3D+bloom+HUD），rgb24 直接管道喂给 imageio-ffmpeg 编码
H.264 MP4 —— 无中间图片文件。

    python tools/capture_gameplay.py               # 默认输出 build_test/gameplay_full.mp4
    python tools/capture_gameplay.py -o out.mp4    # 自定义输出路径

无音频（合成器 BGM 走 dummy 声卡，不采集）。
"""
import argparse
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

import imageio_ffmpeg
import numpy as np
import pygame

import kaw

SEED = 20261009
FPS = 30                 # 视频帧率（逻辑 60Hz，每 2 帧取 1）
CAPTURE_EVERY = 2
W, H = kaw.W, kaw.H


class FakeKeys:
    def __init__(self):
        self.d = {}

    def __getitem__(self, k):
        return self.d.get(k, False)

    def clear(self):
        self.d.clear()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--output",
                    default=os.path.join(_ROOT, "build_test", "gameplay_full.mp4"))
    ap.add_argument("--play-seconds", type=float, default=40.0,
                    help="首次游玩段时长（逻辑秒）")
    args = ap.parse_args()

    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    import random
    random.seed(SEED)

    writer = imageio_ffmpeg.write_frames(
        args.output, (W, H), fps=FPS, pix_fmt_in="rgb24",
        quality=7, macro_block_size=8)
    writer.send(None)                       # 启动 ffmpeg 进程

    held = FakeKeys()
    pygame.key.get_pressed = lambda: held

    def grab():
        """g.screen → rgb24 bytes（surfarray 是 (W,H,3)，需转置）"""
        arr = pygame.surfarray.array3d(g.screen)
        writer.send(np.ascontiguousarray(arr.transpose(1, 0, 2)).tobytes())

    def keydown(key):
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=key))

    total_frames = 0

    def tick(n, phase):
        """跑 n 个逻辑帧，每 CAPTURE_EVERY 帧抓屏"""
        nonlocal total_frames
        for i in range(n):
            if phase == "start":
                g._handle_start_screen(1 / 60)
            elif phase == "loading":
                g._handle_loading()
            elif phase == "playing":
                g._handle_playing(1 / 60)
            elif phase == "gameover":
                g._handle_game_over(1 / 60)
            if i % CAPTURE_EVERY == 0:
                grab()
                total_frames += 1

    print(f"[rec] 构建 Game（seed={SEED}）...")
    g = kaw.Game()
    g.menu_synth = kaw.ZoneSynth()

    print("[rec] 1/6 开始界面")
    tick(120, "start")

    print("[rec] 2/6 加载")
    keydown(pygame.K_RETURN)
    g._handle_start_screen(1 / 60)
    guard = 0
    while g.state == kaw.GameState.LOADING and guard < 5000:
        g._handle_loading()
        if guard % CAPTURE_EVERY == 0:
            grab()
            total_frames += 1
        guard += 1
    print(f"      → {g.state.value}（{guard} 帧）")

    print(f"[rec] 3/6 游玩 {args.play_seconds}s（漫游+俯仰+交互）")
    play_ticks = int(args.play_seconds * 60)
    for i in range(play_ticks):
        held.clear()
        t = i % 600
        if t < 240:                          # 前进 + 缓慢右转
            held.d[pygame.K_w] = True
            if t > 120:
                held.d[pygame.K_d] = True
        elif t < 300:                        # 抬头
            held.d[pygame.K_r] = True
        elif t < 360:                        # 低头回正
            held.d[pygame.K_f] = True
        elif t < 480:                        # 前进 + 左转
            held.d[pygame.K_w] = True
            held.d[pygame.K_a] = True
        else:                                # 原地转向观察
            held.d[pygame.K_d] = True
        if i % 300 == 150:                   # 尝试交互拾取
            keydown(pygame.K_e)
        g._handle_playing(1 / 60)
        if g.state != kaw.GameState.PLAYING: # 意外死亡也继续流程
            break
        if i % CAPTURE_EVERY == 0:
            grab()
            total_frames += 1
    print(f"      pos=({g.px:.1f},{g.py:.1f}) 能量={g.energy.energy:.1f} "
          f"碎片={g.fragments.get_total()}")

    print("[rec] 4/6 能量耗尽 → 死亡")
    g.energy.energy = 0.0
    g.energy.grace_timer = 0.0
    g._handle_playing(1 / 60)               # 状态转移（此调用不渲染）
    print(f"      → {g.state.value}")

    print("[rec] 5/6 结算画面")
    tick(360, "gameover")

    print("[rec] 6/6 重开 → 开始界面 → 加载 → 二次进入")
    keydown(pygame.K_r)
    g._handle_game_over(1 / 60)
    tick(90, "start")
    keydown(pygame.K_RETURN)
    g._handle_start_screen(1 / 60)
    guard = 0
    while g.state == kaw.GameState.LOADING and guard < 5000:
        g._handle_loading()
        if guard % CAPTURE_EVERY == 0:
            grab()
            total_frames += 1
        guard += 1
    tick(600, "playing")

    writer.close()
    size_mb = os.path.getsize(args.output) / 1e6
    print(f"\n[rec] 完成：{args.output}")
    print(f"[rec] 视频帧 {total_frames}（{total_frames / FPS:.1f}s @ {FPS}fps），"
          f"文件 {size_mb:.1f} MB")


if __name__ == "__main__":
    main()
