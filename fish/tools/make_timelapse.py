"""从游戏过程实时抓取画面，制作定格（stop-motion）风格的 MP4 视频。

设计目标
--------
做一个**独立**的小工具：把养鱼游戏的窗口画面按固定帧率逐帧抓下来，
再合成一段 MP4。定格感来自"每帧抓取间隔固定、画面之间靠真实游戏时间推进"，
所以鱼在视频里是"一格一格"游动的，而不是丝滑连续。

🔴 遵守项目宪法：依赖全部可选。缺 mss / Pillow / ffmpeg 时给出清晰指引，
   绝不抛未捕获异常导致崩溃（参考 README §1「全部 pip 依赖都是可选的」）。

用法
----
    # 启动游戏 + 抓"鱼缸"窗口 30 秒，输出 fish_timelapse.mp4
    python tools/make_timelapse.py --launch --duration 30

    # 抓取已经运行、标题含"鱼缸"的窗口
    python tools/make_timelapse.py --window 鱼缸 --fps 12 --duration 20

    # 抓取整个屏幕（不挑游戏窗口）
    python tools/make_timelapse.py --screen --fps 10 --duration 15 --out demo.mp4

依赖（任一组合即可，缺失时会有提示）
--------------------------------------
    pip install mss Pillow            # 抓屏 + 图像
    pip install imageio-ffmpeg        # 自带 ffmpeg 运行时（推荐，无需系统装 ffmpeg）
    # 或者系统 PATH 里已有 ffmpeg 命令也可用
"""

import argparse
import os
import shutil
import subprocess
import sys
import time


# ════════════════════════════════════════════════════════════
#  依赖探测（全部尽力而为，缺了就降级/报错）
# ════════════════════════════════════════════════════════════

def _have(module):
    try:
        __import__(module)
        return True
    except Exception:
        return False


def find_ffmpeg():
    """找一个能用的 ffmpeg 可执行文件。

    优先 imageio-ffmpeg 自带的运行时，其次系统 PATH 里的 ffmpeg。
    :returns: (路径或命令, 来源说明)；找不到返回 ("", 原因)
    """
    if _have("imageio_ffmpeg"):
        try:
            import imageio_ffmpeg
            exe = imageio_ffmpeg.get_ffmpeg_exe()
            if exe and os.path.exists(exe):
                return exe, "imageio-ffmpeg"
        except Exception:
            pass
    # 系统 ffmpeg
    exe = shutil.which("ffmpeg")
    if exe:
        return exe, "system-PATH"
    return "", "未找到（装 imageio-ffmpeg 或把 ffmpeg 放进 PATH）"


# ════════════════════════════════════════════════════════════
#  抓屏后端
# ════════════════════════════════════════════════════════════

class ScreenGrabber(object):
    """跨后端抓屏封装：优先 mss（支持按窗口矩形裁切），退化为 PIL.ImageGrab。"""

    def __init__(self):
        self._mss = None
        self._use_mss = _have("mss")
        if self._use_mss:
            try:
                import mss
                self._mss_mod = mss
                self._mss = mss.mss()
            except Exception:
                self._use_mss = False

    def grab(self, rect=None):
        """抓一帧，返回 RGB 像素 bytes + 尺寸 (w, h)。

        :param rect: (left, top, width, height) 可选；提供时优先按该矩形裁切。
        :returns: (rgb_bytes, (w, h))，失败抛异常由调用方处理
        """
        if self._use_mss and self._mss is not None:
            import mss
            if rect is not None:
                left, top, w, h = rect
                monitor = {"left": int(left), "top": int(top),
                           "width": int(w), "height": int(h)}
            else:
                monitor = self._mss.monitors[0]
            shot = self._mss.grab(monitor)  # BGRX
            from PIL import Image
            img = Image.frombytes("RGB", (shot.width, shot.height), shot.rgb)
            return img.tobytes(), (shot.width, shot.height)
        # 退化：PIL.ImageGrab 只能抓全屏，再按 rect 裁
        from PIL import Image, ImageGrab
        img = ImageGrab.grab()
        if rect is not None:
            left, top, w, h = rect
            img = img.crop((int(left), int(top),
                            int(left) + int(w), int(top) + int(h)))
        rgb = img.convert("RGB")
        return rgb.tobytes(), rgb.size


# ════════════════════════════════════════════════════════════
#  Windows 窗口定位（按标题找窗口矩形）
# ════════════════════════════════════════════════════════════

def find_window_rect(title_substr):
    """在 Windows 上按标题子串找第一个可见窗口，返回 (left, top, w, h)。

    非 Windows 或找不到返回 None。
    """
    if not sys.platform.startswith("win"):
        return None
    try:
        import ctypes
        from ctypes import wintypes
    except Exception:
        return None

    user32 = ctypes.windll.user32
    EnumWindows = user32.EnumWindows
    EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    GetWindowTextW = user32.GetWindowTextW
    GetWindowTextLengthW = user32.GetWindowTextLengthW
    IsWindowVisible = user32.IsWindowVisible
    GetWindowRect = user32.GetWindowRect

    found = {}

    def _each(hwnd, _lparam):
        if not IsWindowVisible(hwnd):
            return True
        length = GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        GetWindowTextW(hwnd, buf, length + 1)
        if title_substr in (buf.value or ""):
            rect = wintypes.RECT()
            if GetWindowRect(hwnd, ctypes.byref(rect)):
                found["rect"] = (rect.left, rect.top,
                                 rect.right - rect.left,
                                 rect.bottom - rect.top)
                return False  # 找到一个就停
        return True

    EnumWindows(EnumWindowsProc(_each), 0)
    return found.get("rect")


# ════════════════════════════════════════════════════════════
#  启动游戏（--launch）
# ════════════════════════════════════════════════════════════

def launch_game():
    """用子进程启动养鱼桌宠，返回 Popen；失败返回 None。"""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    main_py = os.path.join(root, "main.py")
    if not os.path.exists(main_py):
        print("[错误] 找不到项目入口 %s" % main_py)
        return None
    try:
        return subprocess.Popen([sys.executable, main_py], cwd=root)
    except Exception as e:
        print("[错误] 启动游戏失败：%s" % e)
        return None


# ════════════════════════════════════════════════════════════
#  主流程
# ════════════════════════════════════════════════════════════

def parse_args(argv):
    p = argparse.ArgumentParser(
        prog="make_timelapse",
        description="从游戏窗口实时抓屏，制作定格风格 MP4",
    )
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--launch", action="store_true",
                     help="先启动养鱼游戏，再抓其窗口")
    src.add_argument("--window", metavar="TITLE",
                     help="抓取已运行、标题含 TITLE 子串的窗口")
    src.add_argument("--screen", action="store_true",
                     help="抓取整个屏幕")
    p.add_argument("--fps", type=float, default=10.0,
                   help="视频帧率（每张截图=1帧）。默认 10")
    p.add_argument("--duration", type=float, default=30.0,
                   help="抓取时长（秒）。默认 30")
    p.add_argument("--out", default="fish_timelapse.mp4",
                   help="输出视频路径。默认 fish_timelapse.mp4")
    p.add_argument("--wait", type=float, default=2.0,
                   help="--launch 模式下，启动后等待窗口出现的秒数。默认 2")
    return p.parse_args(argv)


def pick_rect(args):
    """根据模式决定裁切矩形（None = 全屏）。找不到窗口则报错退出。"""
    if args.screen:
        return None
    title = args.window if args.window else "鱼缸"
    print("查找窗口标题含 '%s' 的窗口…" % title)
    # --launch 时游戏刚起，多等一会儿
    deadline = time.time() + (args.wait if args.launch else 10.0)
    rect = None
    while time.time() < deadline:
        rect = find_window_rect(title)
        if rect is not None:
            break
        time.sleep(0.5)
    if rect is None:
        if args.launch:
            print("[错误] 游戏窗口未出现，可能被托盘/热键隐藏。请先呼出鱼缸窗口再试。")
        else:
            print("[错误] 未找到标题含 '%s' 的窗口。" % title)
        sys.exit(2)
    print("定位到窗口矩形 left=%d top=%d w=%d h=%d" % rect)
    return rect


def main(argv=None):
    args = parse_args(argv if argv is not None else sys.argv[1:])

    # 1) 依赖检查
    if not _have("PIL"):
        print("[错误] 缺少 Pillow，请先：pip install Pillow")
        return 2
    if not (_have("mss") or _have("PIL")):
        print("[错误] 缺少抓屏后端（mss 或 Pillow），请：pip install mss Pillow")
        return 2
    ffmpeg, src = find_ffmpeg()
    if not ffmpeg:
        print("[错误] 找不到 ffmpeg：%s" % src)
        print("        请选其一：pip install imageio-ffmpeg   或   安装系统 ffmpeg 并加入 PATH")
        return 2
    print("ffmpeg 来源：%s" % src)

    # 2) 启动游戏（如需）
    proc = None
    if args.launch:
        print("启动游戏…")
        proc = launch_game()
        if proc is None:
            return 2

    # 3) 抓屏
    rect = pick_rect(args)
    grabber = ScreenGrabber()

    fps = max(0.1, float(args.fps))
    interval = 1.0 / fps
    total = max(1.0, float(args.duration))
    n_frames = int(total * fps)
    print("开始抓取：fps=%.2f 时长=%.1fs 预计 %d 帧" % (fps, total, n_frames))

    frames = []  # list of (rgb_bytes, (w, h))
    t0 = time.perf_counter()
    next_tick = t0
    try:
        for i in range(n_frames):
            now = time.perf_counter()
            if now < next_tick:
                time.sleep(next_tick - now)
            try:
                rgb, size = grabber.grab(rect)
            except Exception as e:
                print("[警告] 第 %d 帧抓取失败：%s（跳过）" % (i, e))
                next_tick = time.perf_counter() + interval
                continue
            frames.append((rgb, size))
            next_tick += interval
            if (i + 1) % max(1, (n_frames // 10)) == 0:
                print("  已抓 %d / %d 帧" % (i + 1, n_frames))
    except KeyboardInterrupt:
        print("\n[中断] 已抓取 %d 帧，用现有帧合成。" % len(frames))
    finally:
        if proc is not None:
            try:
                proc.terminate()
            except Exception:
                pass

    if not frames:
        print("[错误] 一帧都没抓到，无法生成视频。")
        return 2

    # 4) 统一尺寸（取第一帧尺寸，其余若不一致则跳过的保守处理）
    w0, h0 = frames[0][1]
    out_frames = []
    for rgb, size in frames:
        if size == (w0, h0):
            out_frames.append(rgb)
    if not out_frames:
        out_frames = [rgb for rgb, _ in frames]

    # 5) 用 ffmpeg 合成 MP4（管道喂 rawvideo，避免落盘中间帧）
    out_path = os.path.abspath(args.out)
    out_dir = os.path.dirname(out_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    cmd = [
        ffmpeg, "-y",
        "-f", "rawvideo", "-pix_fmt", "rgb24",
        "-s", "%dx%d" % (w0, h0), "-r", "%.2f" % fps,
        "-i", "-",
        "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-crf", "18", "-preset", "medium",
        out_path,
    ]
    print("合成视频 → %s" % out_path)
    try:
        proc_ff = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        for rgb in out_frames:
            try:
                proc_ff.stdin.write(rgb)
            except Exception:
                break
        proc_ff.stdin.close()
        _, err = proc_ff.communicate()
        if proc_ff.returncode != 0:
            print("[错误] ffmpeg 失败：\n%s" % (err.decode("utf-8", "replace")[-2000:]))
            return 2
    except Exception as e:
        print("[错误] 调用 ffmpeg 失败：%s" % e)
        return 2

    print("完成：%d 帧 → %s（%.1fs 视频）" % (len(out_frames), out_path, len(out_frames) / fps))
    return 0


if __name__ == "__main__":
    sys.exit(main())
