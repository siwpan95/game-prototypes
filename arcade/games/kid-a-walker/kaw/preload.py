# -*- coding: utf-8 -*-
"""后台预加载管理器：独立线程生成初始区块并寻找安全出生点。"""
import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional

from .config import CHUNK_PRELOAD_RANGE
from .world.worldmap import WorldMap

# ─────────────────────── 预加载任务系统 ─────────────────────────
@dataclass
class LoadingTask:
    name: str
    progress: float  # 0.0 ~ 1.0
    status: str
    complete: bool = False

class PreloadManager:
    """后台预加载管理器，使用独立线程"""
    
    def __init__(self, progress_callback: Optional[Callable[[LoadingTask], None]] = None):
        self._lock = threading.Lock()
        self._tasks: dict[str, LoadingTask] = {}
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._canceled = False
        self._progress_callback = progress_callback
        self._world: Optional['WorldMap'] = None
        self._spawn: tuple[float, float] = (10.5, 10.5)
        
    def _update_task(self, name: str, progress: float, status: str):
        """更新任务进度（线程安全）"""
        with self._lock:
            self._tasks[name] = LoadingTask(name, progress, status)
        if self._progress_callback:
            self._progress_callback(self._tasks[name])
    
    def _run_loading(self):
        """后台加载线程的主逻辑"""
        import pygame
        
        self._update_task("world", 0.0, "Initializing world generator...")
        self._world = WorldMap(seed=None)
        time.sleep(0.05)  # 让界面有机会更新
        
        self._update_task("terrain", 0.0, "Generating terrain...")
        # 使用预加载范围常量生成初始区块
        preload_r = CHUNK_PRELOAD_RANGE
        for radius in range(preload_r + 1):
            for dy in range(-radius, radius + 1):
                for dx in range(-radius, radius + 1):
                    if abs(dx) == radius or abs(dy) == radius:
                        self._world._generate_chunk((dx, dy))
            self._update_task("terrain", (radius + 1) / (preload_r + 1), f"Generating chunks... ({radius}/{preload_r})")
            time.sleep(0.02)
        
        self._update_task("connections", 0.0, "Connecting regions...")
        self._world.ensure_neighbors(0, 0)
        self._update_task("connections", 1.0, "Connected!")
        
        self._update_task("audio", 0.5, "Preparing audio synth...")
        # 音频在主线程初始化
        
        self._update_task("spawn", 0.0, "Finding safe spawn...")
        self._spawn = self._world.find_safe_spawn(0, 0)
        self._update_task("spawn", 1.0, "Spawn found!")
        
        self._update_task("complete", 1.0, "Ready!")
        time.sleep(0.1)
        
        with self._lock:
            for task in self._tasks.values():
                task.complete = True
            self._tasks["complete"] = LoadingTask("complete", 1.0, "All done!", True)
    
    def start(self):
        """启动后台加载"""
        if self._thread and self._thread.is_alive():
            return
        self._running = True
        self._canceled = False
        self._thread = threading.Thread(target=self._run_loading, daemon=True)
        self._thread.start()
    
    def cancel(self):
        """取消加载"""
        self._canceled = True
        self._running = False
    
    def get_overall_progress(self) -> tuple[float, str]:
        """获取总体进度"""
        with self._lock:
            if not self._tasks:
                return 0.0, "Initializing..."
            total = sum(t.progress for t in self._tasks.values())
            count = len(self._tasks)
            if count == 0:
                return 0.0, "Initializing..."
            avg = total / count
            current_task = next((t for t in reversed(list(self._tasks.values())) if not t.complete), None)
            status = current_task.status if current_task else "Complete!"
            return avg, status
    
    def is_complete(self) -> bool:
        """检查是否加载完成"""
        with self._lock:
            return any(t.complete for t in self._tasks.values())
    
    def get_world(self) -> Optional['WorldMap']:
        """获取加载好的世界"""
        with self._lock:
            return self._world
    
    def get_spawn(self) -> tuple[float, float]:
        """获取出生点"""
        with self._lock:
            return self._spawn
    
    def get_task_status(self, name: str) -> Optional[LoadingTask]:
        """获取特定任务状态"""
        with self._lock:
            return self._tasks.get(name)
