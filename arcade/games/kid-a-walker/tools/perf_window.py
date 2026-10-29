# -*- coding: utf-8 -*-
"""window 模式真机性能测试（需要真实显示器，无头环境跑不了）。

无头回归只能走 offscreen 回退路径（含每帧读回，约 32.6ms 中位），
而 window 模式（3D 渲进 FBO、后处理后直接上屏、无读回）的真实帧时
只有真机才能测。用法：

    python tools/perf_window.py            # 默认 300 帧
    python tools/perf_window.py --frames 600

输出 p50/p95/平均帧时，并与 offscreen 参考值对比。
走真实路径：开始加载 → 进入游戏 → 不限帧空跑采样（不做确定性比对）。
按关窗提前结束。
"""
import argparse
import os
import statistics
import sys
import time

os.environ.pop("SDL_VIDEODRIVER", None)   # 强制真实视频驱动
os.environ.pop("SDL_AUDIODRIVER", None)

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import pygame  # noqa: E402

from kaw.config import W  # noqa: E402
from kaw.game import Game  # noqa: E402
from kaw.state import GameState  # noqa: E402

OFFSCREEN_P50_MS = 32.6      # 无头回归测得的回退路径参考值


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", type=int, default=300)
    args = ap.parse_args()

    game = Game()               # 内部尝试 OPENGL 窗口，失败自动回退
    if game.gl_renderer is None or game.gl_renderer.mode != "window":
        print("[perf] 本机未走 window 快路径（已回退），无需测试。")
        pygame.quit()
        return

    # 跳过开始界面：直接发起加载并推进到 PLAYING
    game._start_loading()
    guard = 0
    while game.state == GameState.LOADING and guard < 100000:
        game._handle_loading()
        pygame.event.pump()
        guard += 1
    if game.state != GameState.PLAYING:
        print(f"[perf] 未能进入 PLAYING（state={game.state}），中止。")
        pygame.quit()
        return

    print(f"[perf] window 模式（无读回）采 {args.frames} 帧 ...")
    frame_ms = []
    while len(frame_ms) < args.frames:
        t0 = time.perf_counter()
        game._handle_playing(1.0 / 60.0)   # 内部完成 3D+后处理+_present
        pygame.display.flip()              # window 模式唯一的交换步骤
        frame_ms.append((time.perf_counter() - t0) * 1000.0)
        if pygame.event.poll().type == pygame.QUIT:
            break

    n = len(frame_ms)
    frame_ms.sort()
    p50 = statistics.median(frame_ms)
    p95 = frame_ms[max(0, int(n * 0.95) - 1)]
    avg = sum(frame_ms) / n
    print(f"\n[perf] 有效帧数 {n}")
    print(f"[perf] p50  = {p50:6.2f} ms  ({1000.0 / p50:6.1f} FPS)")
    print(f"[perf] p95  = {p95:6.2f} ms")
    print(f"[perf] 平均 = {avg:6.2f} ms")
    print(f"[perf] 参考：offscreen 回退路径（含读回）p50 ≈ {OFFSCREEN_P50_MS} ms")
    verdict = "✅ 达标" if p50 < 16.0 else "❌ 未达 60FPS，需排查"
    print(f"[perf] 判定：window p50 {'<' if p50 < 16 else '>='} 16ms {verdict}")
    pygame.quit()


if __name__ == "__main__":
    main()
