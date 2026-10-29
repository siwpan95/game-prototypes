# -*- coding: utf-8 -*-
"""
探险日志 - Auto Exploration Idle RPG
入口文件
"""

import sys
import os
import atexit
import traceback

# ---- Windows DPI 感知（必须在创建窗口前调用）----
if sys.platform == "win32":
    import ctypes
    # DPI 感知：阻止 Windows 把 Tkinter 文字放大后塞进小容器导致裁切
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)   # Per-Monitor V2 (Win10 1703+)
    except AttributeError:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)   # Per-Monitor (Win8.1+)
        except AttributeError:
            ctypes.windll.user32.SetProcessDPIAware()         # System DPI (Vista+)

# 确保项目根目录在 sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

# ---- 文件日志（早于其他导入，方便记录启动错误）----
LOG_FILE = os.path.join(BASE_DIR, "log.txt")

def _write_log(line: str):
    """写入启动日志到文件"""
    try:
        from datetime import datetime
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {line}\n")
    except Exception:
        pass

from core.config import DATA_DIR, CONFIG_DIR
from data.loader import DataLoader, get_loader
from gui.app import ExplorationApp

# 单例锁文件，防止重复启动
if getattr(sys, 'frozen', False):
    _APP_DIR = os.path.dirname(sys.executable)
else:
    _APP_DIR = BASE_DIR
LOCK_FILE = os.path.join(_APP_DIR, ".running.pid")


def _cleanup_lock():
    """退出时清理锁文件"""
    try:
        if os.path.exists(LOCK_FILE):
            with open(LOCK_FILE, "r") as f:
                pid = f.read().strip()
            # 只清理当前进程的锁文件
            if str(os.getpid()) == pid:
                os.remove(LOCK_FILE)
    except Exception:
        pass


def _check_singleton():
    """检查是否已有实例在运行"""
    if os.path.exists(LOCK_FILE):
        try:
            with open(LOCK_FILE, "r") as f:
                old_pid = int(f.read().strip())
            # 检查进程是否仍在运行
            import ctypes
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(0x0400, False, old_pid)  # PROCESS_QUERY_INFORMATION
            if handle:
                kernel32.CloseHandle(handle)
                # 进程存在 → 杀旧进程（清理残留托盘图标）
                try:
                    import signal
                    os.kill(old_pid, signal.SIGTERM)
                except Exception:
                    pass
        except (ValueError, FileNotFoundError):
            pass
    # 写入当前 PID
    with open(LOCK_FILE, "w") as f:
        f.write(str(os.getpid()))
    atexit.register(_cleanup_lock)


def main():
    _write_log("===== 探险日志 启动 =====")
    _write_log(f"Python: {sys.version}")
    _write_log(f"工作目录: {BASE_DIR}")

    _check_singleton()

    # 1. 加载游戏数据（优先 Excel，回退 JSON）
    try:
        loader = DataLoader()
        loader.load_all(DATA_DIR, CONFIG_DIR)

        # 设为全局单例
        import data.loader as loader_mod
        loader_mod._loader = loader

        if not loader.jobs:
            msg = "错误: 无法加载游戏数据！请检查 data/ 或 config/ 目录。"
            print(msg)
            _write_log(f"[ERROR] {msg}")
            sys.exit(1)

        print(f"数据加载完成: {len(loader.jobs)}职业 {len(loader.skills)}技能 "
              f"{len(loader.equipment)}装备 {len(loader.monsters)}怪物 {len(loader.dungeons)}地下城")
        _write_log(f"数据加载完成: {len(loader.jobs)}职业 {len(loader.skills)}技能 "
                  f"{len(loader.equipment)}装备 {len(loader.monsters)}怪物 {len(loader.dungeons)}地下城")
    except Exception as e:
        _write_log(f"[FATAL] 数据加载失败: {traceback.format_exc()}")
        raise

    # 2. 启动游戏
    try:
        app = ExplorationApp()
        app.run()
    except KeyboardInterrupt:
        print("\n游戏已退出")
        _write_log("游戏正常退出 (KeyboardInterrupt)")
    except Exception:
        tb = traceback.format_exc()
        print(f"\n发生错误:\n{tb}")
        _write_log(f"[FATAL] 运行时错误:\n{tb}")
        raise
    finally:
        _cleanup_lock()
        _write_log("===== 探险日志 退出 =====")


if __name__ == "__main__":
    main()
