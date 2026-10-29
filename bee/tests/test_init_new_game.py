# -*- coding: utf-8 -*-
"""
D4 回归测试 —— SimCore._init_new_game 自定义开局

验证：
  1) 传入 race/class/name/seed 后角色正确创建（对话框接线生效）；
  2) 自定义开局做完整重开（出生区域 / 队伍 / 计时器就绪，日志以新冒险开始）；
  3) 无参默认开局仍工作（golden 依赖的 SimCore() 自动开局不受影响）。

用法：
  pytest tests/test_init_new_game.py
"""
import os
import sys
from unittest.mock import MagicMock

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

SEED = 1
# 非存在的存档路径（哨兵）：确保构造即新建游戏，不读档
MISSING_SAVE = os.path.join(BASE_DIR, "tests", "fixtures", "_missing_save_d4.json")


def _install_stubs():
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
from src.sim_core.models.character import Race, CharClass  # noqa: E402


def test_init_new_game_custom_params():
    """自定义开局：name/race/class 生效，且完整重开（区域/队伍就绪）。"""
    sim = SimCore(save_path=MISSING_SAVE)
    race = list(Race)[0]
    char_class = list(CharClass)[0]

    sim._init_new_game(race=race, char_class=char_class, name="测试", seed=SEED)

    assert sim.character is not None
    assert sim.character.name == "测试", f"name 未生效: {sim.character.name!r}"
    assert sim.character.race == race, "race 未生效"
    assert sim.character.char_class == char_class, "char_class 未生效"
    # 完整重开：出生区域 + 队伍已就绪
    assert sim.current_region is not None, "自定义开局未设定出生区域"
    assert sim.party is not None
    assert sim.game_time == 0.0, "自定义开局未重置计时器"
    assert any("新的冒险开始了" in m for m in sim.log_messages), "未输出新冒险开始日志"


def test_init_new_game_default_unchanged():
    """无参默认开局仍工作（golden 依赖的 SimCore() 自动开局）。"""
    sim = SimCore(save_path=MISSING_SAVE)
    assert sim.character is not None
    assert sim.current_region is not None
    assert sim.party is not None
