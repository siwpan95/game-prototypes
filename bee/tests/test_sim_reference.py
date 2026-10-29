# -*- coding: utf-8 -*-
"""黄金基准生成器 — 重新生成 tests/golden_baseline.json

用法：
    python tests/test_sim_reference.py

固定 seed=12345 + 缺失存档 → SimCore 新建游戏，200 步 dt=0.05，
捕获日志 / 状态指纹 / 音频事件，仓库路径归一化为 <REPO> 后写入基准。

注意：仅在确认模拟语义变更是有意为之（如文案/机制调整）后重新生成；
生成后必须运行 pytest，确认 test_sim_core_golden / test_sim_bridge 全绿。
"""
import json
import os
import random
import sys
from unittest.mock import MagicMock

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

SEED = 12345
DT = 0.05
STEPS = 200
BASELINE = os.path.join(BASE_DIR, "tests", "golden_baseline.json")
MISSING_SAVE = os.path.join(BASE_DIR, "tests", "fixtures", "_missing_save.json")


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


def _normalize_paths(logs):
    """把仓库绝对路径归一化为 <REPO>，保证黄金基准可跨机器移植"""
    normalized = []
    roots = {BASE_DIR, BASE_DIR.replace("\\", "/")}
    for line in logs:
        for root in roots:
            line = line.replace(root, "<REPO>")
        normalized.append(line)
    return normalized


def main():
    _install_stubs()
    from src.sim_core.engine import SimCore

    random.seed(SEED)
    sim = SimCore(save_path=MISSING_SAVE)
    random.seed(SEED)  # 与黄金测试捕获流程一致：构造后重置随机种子
    for _ in range(STEPS):
        sim.update(DT)

    char = sim.character
    region_id = sim.current_region["region_id"] if sim.current_region else None
    baseline = {
        "seed": SEED,
        "dt": DT,
        "steps": STEPS,
        "log_messages": _normalize_paths(list(sim.log_messages)),
        "fingerprint": {
            "level": char.level,
            "gold": char.gold,
            "region_id": region_id,
            "game_time": round(sim.game_time, 4),
            "kills": char.kills,
            "deaths": char.deaths,
        },
        "audio_calls": [name for name, _args in sim.audio_events],
    }
    os.makedirs(os.path.dirname(BASELINE), exist_ok=True)
    with open(BASELINE, "w", encoding="utf-8") as f:
        json.dump(baseline, f, ensure_ascii=False, indent=2)
    print(f"基准已生成: {BASELINE}")
    print(f"  日志行数: {len(baseline['log_messages'])} | 指纹: {baseline['fingerprint']}")
    print(f"  音频事件: {len(baseline['audio_calls'])}")


if __name__ == "__main__":
    main()
