# -*- coding: utf-8 -*-
"""
M2 — SimCore IPC 桥接服务（headless TCP JSON-line server）

让外部进程（Godot / 测试 / 任意前端）以独立子进程方式驱动 SimCore，
验证「模拟内核与 UI 完全解耦」：前端只发 JSON 指令，内核跑同一份确定性逻辑。

协议（UTF-8，每行一条 JSON）：
  客户端 → 服务端：
    {"cmd":"init","seed":12345,"save_path":"<path|null>"}
        固定随机种子构造 SimCore（与黄金基准捕获流程一致，确定性）。
    {"cmd":"step","dt":0.05}
        推进一帧模拟（等价于 SimCore.update(dt)）。
    {"cmd":"new_game","race":..,"char_class":..,"name":..,"seed":..}
        角色创建后重开一局（等价于 SimCore._init_new_game(...)）。
    {"cmd":"state"}
        取回 {"log_messages":[...], "fingerprint":{...}}。
    {"cmd":"quit"}
        优雅退出服务端。
  服务端 → 客户端：
    {"ok":true, ...} 或 {"ok":false, "error":"..."}

运行：
    python -m src.sim_core.bridge [--host 127.0.0.1] [--port 0]
    启动后向 stdout 打印一行：  READY <port>   （--port 0 时由系统分配实际端口）
"""
import argparse
import json
import os
import random
import socket
import sys
import threading

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)


def _install_stubs():
    """headless 桩：构造 SimCore / AudioService 时不触发 GUI / 音频硬件依赖。

    仅当对应模块尚未真实安装时才注入 MagicMock（numpy/scipy 若已安装则不覆盖，
    保证数值逻辑真实运行，与黄金测试行为一致）。
    """
    for mod in (
        "tkinter", "tkinter.messagebox", "pystray",
        "PIL", "PIL.Image", "PIL.ImageDraw",
        "numpy", "scipy", "scipy.io", "scipy.io.wavfile", "sounddevice",
        "openpyxl",
    ):
        if mod not in sys.modules:
            from unittest.mock import MagicMock
            sys.modules[mod] = MagicMock()


_install_stubs()

from src.sim_core.engine import SimCore  # noqa: E402
from src.sim_core.models.character import Race, CharClass  # noqa: E402


def _fingerprint(sim):
    """状态指纹——与黄金测试 test_sim_core_golden._fingerprint 完全一致。"""
    char = sim.character
    region_id = sim.current_region["region_id"] if sim.current_region else None
    return {
        "level": char.level,
        "gold": char.gold,
        "region_id": region_id,
        "game_time": round(sim.game_time, 4),
        "kills": char.kills,
        "deaths": char.deaths,
    }


def _resolve_race(value):
    """字符串 race_id -> RaceData；非字符串原样返回；无效则回退首个。"""
    if value is None or not isinstance(value, str):
        return value
    key = value.strip().upper()
    item = Race._by_id.get(key)
    if item is None:
        try:
            item = getattr(Race, key)
        except AttributeError:
            item = None
    return item if item is not None else list(Race)[0]


def _resolve_class(value):
    """字符串 class_id -> ClassData；非字符串原样返回；无效则回退首个。"""
    if value is None or not isinstance(value, str):
        return value
    key = value.strip().upper()
    item = CharClass._by_id.get(key)
    if item is None:
        try:
            item = getattr(CharClass, key)
        except AttributeError:
            item = None
    return item if item is not None else list(CharClass)[0]


class SimBridge:
    """单连接 TCP JSON-line 桥接服务。驱动一个 SimCore 实例。"""

    def __init__(self, host="127.0.0.1", port=0):
        self.host = host
        self.port = port
        self.sim = None
        self._sock = None

    def _make_sim(self, seed, save_path):
        # 与 golden_baseline 捕获流程逐字一致：构造前 seed，构造后再次 seed。
        random.seed(seed)
        sim = SimCore(save_path=save_path)
        random.seed(seed)
        return sim

    def _handle(self, msg):
        cmd = msg.get("cmd")
        if cmd == "init":
            seed = msg.get("seed", 12345)
            save_path = msg.get("save_path")
            self.sim = self._make_sim(seed, save_path)
            return {"ok": True}
        if cmd == "new_game":
            if self.sim is None:
                return {"ok": False, "error": "not initialized"}
            self.sim._init_new_game(
                race=_resolve_race(msg.get("race")),
                char_class=_resolve_class(msg.get("char_class")),
                name=msg.get("name"),
                seed=msg.get("seed"),
            )
            return {"ok": True}
        if cmd == "step":
            if self.sim is None:
                return {"ok": False, "error": "not initialized"}
            self.sim.update(float(msg.get("dt", 0.05)))
            return {"ok": True}
        if cmd == "state":
            if self.sim is None:
                return {"ok": False, "error": "not initialized"}
            return {
                "ok": True,
                "log_messages": list(self.sim.log_messages),
                "fingerprint": _fingerprint(self.sim),
            }
        if cmd == "quit":
            return {"ok": True, "_quit": True}
        return {"ok": False, "error": "unknown cmd: %r" % (cmd,)}

    def serve(self):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind((self.host, self.port))
        self._sock.listen(1)

        # 报告系统分配的实际端口（--port 0 时必要）
        actual_port = self._sock.getsockname()[1]
        sys.stdout.write("READY %d\n" % actual_port)
        sys.stdout.flush()

        conn, _addr = self._sock.accept()
        try:
            conn.settimeout(30.0)
            f = conn.makefile("rwb", buffering=0)
            for raw in f:
                try:
                    msg = json.loads(raw.decode("utf-8"))
                except Exception as e:  # noqa: BLE001
                    f.write((json.dumps({"ok": False, "error": "bad json: %s" % e})
                             + "\n").encode("utf-8"))
                    continue
                try:
                    resp = self._handle(msg)
                except Exception as e:  # noqa: BLE001
                    resp = {"ok": False, "error": "handler error: %s" % e}
                f.write((json.dumps(resp, ensure_ascii=False) + "\n").encode("utf-8"))
                if resp.get("_quit"):
                    break
        finally:
            try:
                conn.close()
            except Exception:  # noqa: BLE001
                pass
            self._sock.close()


def main():
    ap = argparse.ArgumentParser(description="SimCore IPC bridge server")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=0,
                    help="监听端口；0 = 系统分配（stdout 输出 READY <port>）")
    args = ap.parse_args()
    SimBridge(host=args.host, port=args.port).serve()


if __name__ == "__main__":
    main()
