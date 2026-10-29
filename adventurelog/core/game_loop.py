# -*- coding: utf-8 -*-
"""统一游戏时钟（Tick 驱动）— 借鉴 pq2 的 Tick(ms) 设计

核心思路：
- 所有定时回调通过 GameLoop 统一管理
- 支持速度倍率（加速/减速战斗和探索节奏）
- cancel_all() 一键取消所有待处理任务（撤退回城时使用）
- 替代散落在各处的 self._after_ids 列表
"""

from __future__ import annotations
from typing import List, Callable, Any
import tkinter as tk


class GameLoop:
    """统一游戏时钟管理器

    借鉴 pq2 的 Tick 设计：pq2 用 Tick(uint64_t ms) 驱动游戏步进，
    探险日志用 tkinter 的 after() 定时回调。GameLoop 封装 after()，
    提供统一的调度/取消/速度控制。

    使用方式:
        # 初始化
        self.game_loop = GameLoop(root, engine)

        # 替代 self.root.after(delay, callback)
        self.game_loop.after(800, self._do_battle, monster, is_boss)

        # 退出探索时一键清理
        self.game_loop.cancel_all()

        # 加速游戏
        self.game_loop.set_speed(2.0)   # 2倍速
        self.game_loop.set_speed(5.0)   # 5倍速
    """

    def __init__(self, root: tk.Tk, engine=None):
        self._root = root
        self._engine = engine
        self._speed: float = 1.0
        self._pending: List[str] = []    # after IDs

    # ── 核心调度 ──

    def after(self, delay_ms: int, callback: Callable, *args: Any) -> str:
        """安排定时回调。

        delay_ms 自动按当前速度倍率调整。
        返回 after ID，可用于单独取消。
        """
        adjusted = max(1, int(delay_ms / self._speed))
        aid = self._root.after(adjusted, callback, *args)
        self._pending.append(aid)
        return aid

    def after_idle(self, callback: Callable, *args: Any) -> str:
        """安排在空闲时回调（不受速度影响）"""
        aid = self._root.after_idle(callback, *args)
        self._pending.append(aid)
        return aid

    # ── 取消管理 ──

    def cancel(self, after_id: str):
        """取消单个定时任务"""
        try:
            self._root.after_cancel(after_id)
        except Exception as _e:
            import sys
            print(f"[GameLoop] after_cancel 失败（ID={after_id}）：{_e}", file=sys.stderr)
        if after_id in self._pending:
            self._pending.remove(after_id)

    def cancel_all(self):
        """取消所有待处理的定时任务。

        用于退出探索、返回城镇时清理所有战斗/事件回调。
        """
        for aid in self._pending:
            try:
                self._root.after_cancel(aid)
            except Exception as _e:
                import sys
                print(f"[GameLoop] after_cancel 失败（ID={aid}）：{_e}", file=sys.stderr)
        self._pending.clear()

    # ── 速度控制 ──

    def set_speed(self, multiplier: float):
        """设置游戏速度倍率。

        multiplier: 0.25 (慢速) ~ 10.0 (极快)
        注意：已排期的任务不会重新调整延迟，仅影响新排期的任务。
        """
        self._speed = max(0.25, min(10.0, multiplier))

    @property
    def speed(self) -> float:
        return self._speed

    @property
    def pending_count(self) -> int:
        return len(self._pending)

    # ── 状态查询 ──

    def is_pending(self) -> bool:
        """是否有待处理的任务"""
        return len(self._pending) > 0
