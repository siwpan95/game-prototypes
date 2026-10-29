# -*- coding: utf-8 -*-
"""
M2 — 桥接黄金测试（子进程 IPC 一致性）

启动 SimBridge 子进程（独立进程），通过 TCP 发送 init/step/state，
断言其产出的 log_messages + fingerprint 与 in-process 黄金基准逐字一致。
证明：模拟内核可在独立进程中以 IPC 驱动，且语义零漂移（Godot 前端可如此接入）。

用法：
  pytest tests/test_sim_bridge.py
"""
import json
import os
import socket
import subprocess
import sys
import threading

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

SEED = 12345
DT = 0.05
STEPS = 200
BASELINE = os.path.join(BASE_DIR, "tests", "golden_baseline.json")
MISSING_SAVE = os.path.join(BASE_DIR, "tests", "fixtures", "_missing_save.json")
PYTHON = sys.executable  # 与运行 pytest 的同一解释器启动桥接子进程

BAD_PATTERNS = ("import tkinter", "from tkinter", "import pystray", "from pystray")


def _normalize_paths(logs):
    """把仓库绝对路径归一化为 <REPO>，保证黄金基准可跨机器移植"""
    normalized = []
    roots = {BASE_DIR, BASE_DIR.replace("\\", "/")}
    for line in logs:
        for root in roots:
            line = line.replace(root, "<REPO>")
        normalized.append(line)
    return normalized


def _read_ready(proc, timeout=30):
    """从子进程 stdout 读取 'READY <port>'，带超时保护（避免启动失败时挂死）。"""
    captured = []

    def _reader():
        captured.append(proc.stdout.readline())

    t = threading.Thread(target=_reader, daemon=True)
    t.start()
    t.join(timeout)
    if t.is_alive():
        raise TimeoutError("bridge 启动超时（未输出 READY）")
    line = captured[0]
    assert line.startswith("READY "), (
        "bridge 未就绪: %r | stderr=%r" % (line, proc.stderr.read())
    )
    return int(line.strip().split()[1])


def _send(sock, msg):
    sock.sendall((json.dumps(msg, ensure_ascii=False) + "\n").encode("utf-8"))
    buf = b""
    while not buf.endswith(b"\n"):
        chunk = sock.recv(65536)
        if not chunk:
            raise ConnectionError("bridge 断开")
        buf += chunk
    return json.loads(buf.decode("utf-8"))


def _start_bridge():
    proc = subprocess.Popen(
        [PYTHON, "-m", "src.sim_core.bridge"],
        cwd=BASE_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    port = _read_ready(proc)
    return proc, port


def test_bridge_matches_baseline():
    """桥接 IPC 须逐字复现 golden_baseline.json（独立进程 + 网络驱动，语义零漂移）。"""
    assert os.path.exists(BASELINE), "请先运行 python tests/test_sim_reference.py 生成基准"
    with open(BASELINE, "r", encoding="utf-8") as f:
        base = json.load(f)

    proc, port = _start_bridge()
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=30) as s:
            r = _send(s, {"cmd": "init", "seed": SEED, "save_path": MISSING_SAVE})
            assert r.get("ok"), r
            for _ in range(STEPS):
                r = _send(s, {"cmd": "step", "dt": DT})
                assert r.get("ok"), r
            r = _send(s, {"cmd": "state"})
            assert r.get("ok"), r
            logs = r["log_messages"]
            fp = r["fingerprint"]
            _send(s, {"cmd": "quit"})
    finally:
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()

    assert _normalize_paths(logs) == _normalize_paths(base["log_messages"]), "桥接 IPC 日志与黄金基准不一致（迁移改变了模拟语义？）"
    assert fp == base["fingerprint"], "桥接 IPC 状态指纹与黄金基准不一致"


def test_bridge_new_game_command():
    """new_game 指令须返回 ok 且能继续推进（角色创建后重开，供 Godot 接入）。"""
    proc, port = _start_bridge()
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=30) as s:
            r = _send(s, {"cmd": "init", "seed": SEED, "save_path": MISSING_SAVE})
            assert r.get("ok"), r
            from src.sim_core.models.character import Race, CharClass
            rid = list(Race)[0].race_id
            cid = list(CharClass)[0].class_id
            r = _send(s, {"cmd": "new_game", "name": "桥接测试",
                          "race": rid, "char_class": cid, "seed": 999})
            assert r.get("ok"), r
            # 重开后推进几帧不应报错
            for _ in range(5):
                r = _send(s, {"cmd": "step", "dt": DT})
                assert r.get("ok"), r
            _send(s, {"cmd": "quit"})
    finally:
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


def test_bridge_no_gui_import():
    """bridge.py 不得依赖 tkinter / pystray（引擎无关约束）。"""
    import src
    bridge_path = os.path.join(os.path.dirname(src.__file__), "sim_core", "bridge.py")
    assert os.path.isfile(bridge_path), "bridge.py 缺失"
    with open(bridge_path, "r", encoding="utf-8") as f:
        offenders = [ln.strip() for ln in f if any(p in ln for p in BAD_PATTERNS)]
    assert not offenders, "bridge.py 含 GUI 依赖:\n" + "\n".join(offenders)
