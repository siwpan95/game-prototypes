# -*- coding: utf-8 -*-
"""
recorder —— 实机录像：把窗口帧回读后直接喂给 ffmpeg 的 rawvideo 管道。

与"录屏"（gdigrab 抓桌面）不同，这里读的是**本进程的 GL 帧缓冲**：
画面是应用真正渲染出来的内容，不受窗口被遮挡、最小化、缩放或桌面壁纸影响，
也不会录进别的窗口。

ffmpeg 查找顺序（任一可用即采用，跑 ``-version`` 校验）：

1. 环境变量 ``WORLD3D_FFMPEG`` 指定的路径
2. ``PATH`` 上的 ``ffmpeg``
3. ``imageio_ffmpeg`` 自带的二进制（pip install imageio-ffmpeg）
4. 常见安装位置（相对仓库根）

音频不在这条链路上：混音输出由 ``audio/sd_mixer.py`` 直接落成 WAV，
最后再由 ffmpeg 与视频封装到一起（见 ``scripts/record_demo.py``）。
"""

from __future__ import annotations

import ctypes
import os
import subprocess
import sys
import time

__all__ = ['FrameRecorder', 'find_ffmpeg']

# 相对仓库根的常见安装位置（与 3dworld-demos 的候选表同思路）
_FFMPEG_CANDIDATES = (
    os.path.join('ffmpeg', 'bin', 'ffmpeg.exe'),
    'ffmpeg.exe',
)


def _usable(exe: str) -> bool:
    if not exe or not os.path.isfile(exe):
        return False
    try:
        r = subprocess.run([exe, '-version'], capture_output=True, timeout=30)
        return r.returncode == 0
    except Exception:
        return False


def find_ffmpeg() -> str | None:
    """按优先级找一个可用的 ffmpeg 可执行文件；找不到返回 None。"""
    env = os.environ.get('WORLD3D_FFMPEG')
    if env and _usable(env):
        return env

    import shutil
    which = shutil.which('ffmpeg')
    if which and _usable(which):
        return which

    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe and _usable(exe):
            return exe
    except Exception:
        pass

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for rel in _FFMPEG_CANDIDATES:
        p = os.path.join(root, rel)
        if _usable(p):
            return p
    return None


class FrameRecorder:
    """把窗口帧以 rawvideo 管道喂给 ffmpeg，落成 H.264 视频。"""

    def __init__(self, out_path: str, ffmpeg_exe: str | None = None,
                 fps: int = 30, crf: int = 20, preset: str = 'medium'):
        self.out_path = os.path.abspath(out_path)
        self.exe = ffmpeg_exe or find_ffmpeg()
        if not self.exe:
            raise RuntimeError(
                '找不到可用的 ffmpeg。装一个：pip install imageio-ffmpeg，'
                '或设环境变量 WORLD3D_FFMPEG 指向 ffmpeg.exe。')
        self.fps = int(fps)
        self.crf = int(crf)
        self.preset = preset
        self.proc = None
        self.width = 0
        self.height = 0
        self.frames = 0
        self._acc = 0.0
        self._last = None

    # ---- 生命周期 ----
    def start(self, width: int, height: int):
        """按实际窗口尺寸启动 ffmpeg 管道。"""
        self.width, self.height = int(width), int(height)
        cmd = [
            self.exe, '-y',
            '-f', 'rawvideo', '-vcodec', 'rawvideo', '-pix_fmt', 'rgba',
            '-s', f'{self.width}x{self.height}', '-r', str(self.fps), '-i', '-',
            '-an',
            '-c:v', 'libx264', '-preset', self.preset, '-crf', str(self.crf),
            '-pix_fmt', 'yuv420p', '-movflags', '+faststart',
            self.out_path,
        ]
        os.makedirs(os.path.dirname(self.out_path) or '.', exist_ok=True)
        self.proc = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE)
        self._last = time.perf_counter()
        return self

    def grab(self, window, dt: float = 0.0):
        """回读一帧并写入管道；按目标帧率节流（保持实时速度）。

        glReadPixels 读出的行序是**自下而上**的（OpenGL 约定），直接喂
        ffmpeg 会得到上下颠倒的画面，这里按行翻转。
        """
        if self.proc is None or self.proc.stdin is None:
            return False

        now = time.perf_counter()
        elapsed = now - self._last
        self._last = now
        self._acc += elapsed
        if self._acc < 1.0 / self.fps:
            return False
        self._acc -= 1.0 / self.fps
        if self._acc > 1.0:
            self._acc = 0.0

        data = read_pixels(window)
        if data is None:
            return False
        try:
            self.proc.stdin.write(data)
        except (BrokenPipeError, OSError):
            return False
        self.frames += 1
        return True

    def close(self):
        """关闭管道并等 ffmpeg 收尾（写完 moov）。"""
        if self.proc is None:
            return self.out_path
        try:
            if self.proc.stdin is not None:
                self.proc.stdin.close()
        except Exception:
            pass
        try:
            err = self.proc.stderr.read().decode('utf-8', 'ignore') \
                if self.proc.stderr else ''
        except Exception:
            err = ''
        self.proc.wait()
        if self.proc.returncode not in (0, None):
            print(f'[recorder] ffmpeg exited {self.proc.returncode}\n{err[-800:]}')
        self.proc = None
        return self.out_path


def read_pixels(window) -> bytes | None:
    """回读窗口帧缓冲，返回**自上而下**的 RGBA 字节。"""
    try:
        import numpy as np
        from pyglet.gl import GL_RGBA, GL_UNSIGNED_BYTE, glReadPixels
    except Exception:
        return None
    w, h = window.width, window.height
    if w <= 0 or h <= 0:
        return None
    row = w * 4
    buf = (ctypes.c_ubyte * (row * h))()
    try:
        glReadPixels(0, 0, w, h, GL_RGBA, GL_UNSIGNED_BYTE, buf)
    except Exception:
        return None
    arr = np.frombuffer(bytes(buf), dtype=np.uint8).reshape(h, w, 4)
    return arr[::-1].tobytes()          # 翻转行序 → 自上而下
