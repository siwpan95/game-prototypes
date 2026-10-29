# -*- coding: utf-8 -*-
"""
M1c — 黄金测试（sim_core 核心安全网）

构造 SimCore（固定 seed + 固定缺失存档 -> 确定性新建游戏），跑固定 dt 序列，
断言：
  1) log_messages 与 golden_baseline.json 逐字（字节级）一致；
  2) 状态指纹（level/gold/region_id/game_time/kills/deaths）完全一致；
  3) sim_core 包内不导入 tkinter / pystray（引擎无关）。

用法：
  pytest tests/test_sim_core_golden.py
"""
import os
import sys
import json
import random
from unittest.mock import MagicMock

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

SEED = 12345
DT = 0.05
STEPS = 200
FIXTURE_DIR = os.path.join(BASE_DIR, "tests", "fixtures")
BASELINE = os.path.join(BASE_DIR, "tests", "golden_baseline.json")
MISSING_SAVE = os.path.join(FIXTURE_DIR, "_missing_save.json")


def _install_stubs():
    # headless：任意属性/方法访问安全返回 MagicMock（tk.Tk()/np.array() 等均不报错）
    for mod in (
        "tkinter", "tkinter.messagebox", "pystray",
        "PIL", "PIL.Image", "PIL.ImageDraw",
        "numpy", "scipy", "scipy.io", "scipy.io.wavfile", "sounddevice",
        "openpyxl",
    ):
        if mod not in sys.modules:
            sys.modules[mod] = MagicMock()


_install_stubs()

from src.sim_core.engine import SimCore  # noqa: E402


def _normalize_paths(logs):
    """把仓库绝对路径归一化为 <REPO>，保证黄金基准可跨机器移植"""
    normalized = []
    roots = {BASE_DIR, BASE_DIR.replace("\\", "/")}
    for line in logs:
        for root in roots:
            line = line.replace(root, "<REPO>")
        normalized.append(line)
    return normalized


def _fingerprint(sim):
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


def _capture():
    """固定 seed 构造 SimCore，固定 seed 后跑固定序列，返回 (logs, fingerprint)。"""
    random.seed(SEED)
    sim = SimCore(save_path=MISSING_SAVE)
    random.seed(SEED)  # 与黄金基准捕获流程一致：构造后重置随机种子
    for _ in range(STEPS):
        sim.update(DT)
    return list(sim.log_messages), _fingerprint(sim)


def test_sim_core_matches_baseline():
    """SimCore 须逐字复现 golden_baseline.json（迁移语义零变化）。"""
    assert os.path.exists(BASELINE), "请先运行 python tests/test_sim_reference.py 生成基准"
    with open(BASELINE, "r", encoding="utf-8") as f:
        base = json.load(f)

    logs, fp = _capture()

    assert _normalize_paths(logs) == _normalize_paths(base["log_messages"]), (
        "SimCore 日志与黄金基准不一致（迁移改变了模拟语义？）"
    )
    assert fp == base["fingerprint"], "SimCore 状态指纹与黄金基准不一致"


def test_sim_core_no_gui_import():
    """sim_core 包不得依赖 tkinter / pystray（引擎无关约束）。"""
    import src
    sim_core_dir = os.path.join(os.path.dirname(src.__file__), "sim_core")
    assert os.path.isdir(sim_core_dir), "sim_core 包缺失"

    bad_patterns = ("import tkinter", "from tkinter", "import pystray", "from pystray")
    offenders = []
    for root, _dirs, files in os.walk(sim_core_dir):
        for fn in files:
            if not fn.endswith(".py"):
                continue
            path = os.path.join(root, fn)
            with open(path, "r", encoding="utf-8") as f:
                for i, line in enumerate(f, 1):
                    if any(p in line for p in bad_patterns):
                        offenders.append(f"{path}:{i}: {line.strip()}")
    assert not offenders, f"sim_core 含 GUI 依赖:\n" + "\n".join(offenders)
