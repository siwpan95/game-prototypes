# -*- coding: utf-8 -*-
"""终端表现层（慢速打字机输出、房间展示、输入读取）。

刻意把 **I/O 与规则分离**：`game.py` 只调这里的函数，便于测试时注入
一个不打字、不阻塞的输入输出实现。
"""

from __future__ import annotations

import sys
import time
from typing import Callable, List, Optional

__all__ = ["Printer", "slow_print", "make_printer"]

#: 网格模式的中文方向 → 坐标增量
DIRECTIONS = {"北": (-1, 0), "南": (1, 0), "西": (0, -1), "东": (0, 1)}


def slow_print(text: str, delay: float = 0.02) -> None:
    """打字机式输出（旧版同名函数的行为保持一致）。"""
    for ch in text:
        print(ch, end="", flush=True)
        time.sleep(delay)
    print()


class Printer:
    """可替换的输出/输入（测试时注入即时版本）。"""

    def __init__(self, delay: float = 0.02, out=sys.stdout,
                 input_fn: Optional[Callable[[str], str]] = None):
        self.delay = delay
        self.out = out
        self.input_fn = input_fn or input

    # ---- 输出 ----
    def __call__(self, text: str = "") -> None:
        self.say(text)

    def say(self, text: str = "") -> None:
        """慢速输出一行。"""
        if self.delay <= 0:
            print(text, file=self.out, flush=True)
            return
        for ch in text:
            print(ch, end="", file=self.out, flush=True)
            time.sleep(self.delay)
        print(file=self.out)

    # ---- 输入 ----
    def ask(self, prompt: str) -> str:
        if self.delay <= 0:
            print(prompt, file=self.out, flush=True)
        else:
            self.say(prompt)
        try:
            return self.input_fn("").strip()
        except (EOFError, KeyboardInterrupt):
            return "退出"


def make_printer(delay: float = 0.02, out=sys.stdout,
                 input_fn: Optional[Callable[[str], str]] = None) -> Printer:
    return Printer(delay=delay, out=out, input_fn=input_fn)


def describe_room(world, rid: str) -> str:
    """一行房间描述（网格模式显示坐标，图模式显示房间名与出口方向）。"""
    room = world.rooms[rid]
    if world.grid_mode:
        return f"📍 当前房间: ({rid}) - 类型: {room.kind}"
    return f"📍 当前房间: {room.name} - 类型: {room.kind}"


def movement_prompt(world, rid: str) -> str:
    """移动提示语（两种模式措辞不同）。"""
    nb = world.neighbors_of(rid)
    if world.grid_mode:
        r, c = world.rooms[rid].pos
        size = world.size
        dirs: List[str] = []
        if r > 0:
            dirs.append("北")
        if r < size - 1:
            dirs.append("南")
        if c > 0:
            dirs.append("西")
        if c < size - 1:
            dirs.append("东")
        return f"可以移动的方向: {dirs}\n选择移动方向(或输入'退出'): "
    opts = ", ".join(f"{i+1}.{world.rooms[n].name}" for i, n in enumerate(nb))
    return f"可通往: {opts}\n选择编号或房间名(或输入'退出'): "
