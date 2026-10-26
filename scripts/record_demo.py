# -*- coding: utf-8 -*-
"""
record_demo —— 实机演示录像（一键跑完：录制 → 封装 → 出片）。

    python scripts/record_demo.py                          # 默认 180 秒 / 1280x720
    python scripts/record_demo.py --duration 60 --out docs/demo.mp4

流程：

1. 找 ffmpeg（``WORLD3D_FFMPEG`` → PATH → imageio-ffmpeg → 常见安装位置）
2. 起 ``main.py --demo --record=... --record-audio=...``：
   演示编排 = 自动驾驶保持居中 → 开头暂停展示 PAUSED → 末段撞毁展示 GAME OVER
3. 结束后把视频（H.264）与录音 WAV 封装成一个带音轨的 mp4

画面是**进程内回读 GL 帧缓冲**得到的（不是抓屏），因此不受窗口遮挡/最小化
影响；音轨来自 ``audio/sd_mixer.py`` 的混音输出，保留了自适应电子配乐。
"""

import argparse
import os
import subprocess
import sys
import time

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

from recorder import find_ffmpeg                              # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--duration', type=float, default=180.0,
                    help='录制时长（秒），默认 180')
    ap.add_argument('--size', default='1280x720', help='窗口尺寸')
    ap.add_argument('--fps', type=int, default=30, help='成片帧率')
    ap.add_argument('--out', default=os.path.join('docs', 'demo_3d.mp4'),
                    help='成片输出路径')
    ap.add_argument('--no-audio', action='store_true', help='不录音')
    args = ap.parse_args()

    exe = find_ffmpeg()
    if not exe:
        print('找不到 ffmpeg。装一个：pip install imageio-ffmpeg')
        return 2
    print(f'[record] ffmpeg: {exe}')

    out = os.path.abspath(args.out)
    os.makedirs(os.path.dirname(out) or '.', exist_ok=True)
    video_tmp = out + '.video.mp4'
    audio_tmp = out + '.wav'

    cmd = [
        sys.executable, os.path.join(BASE, 'main.py'),
        f'--size={args.size}',
        f'--record={video_tmp}',
        f'--demo',
        f'--demo-crash-at={max(5.0, args.duration - 18.0)}',
        f'--exit-after={args.duration}',
    ]
    if not args.no_audio:
        cmd.append(f'--record-audio={audio_tmp}')

    print(f'[record] 录制 {args.duration:.0f}s @ {args.size} → {video_tmp}')
    t0 = time.time()
    rc = subprocess.call(cmd, cwd=BASE)
    print(f'[record] 应用退出 rc={rc}，耗时 {time.time() - t0:.1f}s')
    if rc != 0:
        return rc

    if os.path.exists(video_tmp):
        print(f'[record] 视频大小 {os.path.getsize(video_tmp) / 1e6:.1f} MB')

    # 封装音视频
    mux_cmd = [exe, '-y', '-hide_banner', '-loglevel', 'error']
    if args.no_audio or not os.path.exists(audio_tmp):
        mux_cmd += ['-i', video_tmp, '-c:v', 'copy', '-an']
    else:
        mux_cmd += ['-i', video_tmp, '-i', audio_tmp,
                    '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-shortest']
    mux_cmd += ['-movflags', '+faststart', out]

    print('[record] 封装音视频…')
    r = subprocess.run(mux_cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(f'[record] 封装失败：\n{r.stderr[-1500:]}')
        return r.returncode

    # 清理中间产物
    for tmp in (video_tmp, audio_tmp):
        if os.path.exists(tmp):
            os.remove(tmp)

    size = os.path.getsize(out) / 1e6
    print(f'[record] 完成：{out}（{size:.1f} MB）')
    return 0


if __name__ == '__main__':
    sys.exit(main())
