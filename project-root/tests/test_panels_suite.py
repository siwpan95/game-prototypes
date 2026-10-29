# tests/test_panels_suite.py
# 一次性运行全部面板单元测试（各 test_panel_*.py 注册用例到共享 harness）。
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _panel_harness import run_all
import test_panel_character
import test_panel_pathways
import test_panel_groups
import test_panel_action
import test_panel_log
# P0 新增：E1 魔药材料 / E3 事件 / 控制器层（E1 门禁 + E3 流转）/ 核心逻辑（E1E2E3）
import test_panel_brewing
import test_panel_event
import test_controller_e1e2e3
import test_e1_core
# P1 新增：E4 存档/读档 控制器层
import test_controller_e4
# P1 新增：E5 扮演质量维度（纯逻辑 + 控制器层）
import test_e5_quality
import test_controller_e5
# P1 新增：E6 能力效果化（纯逻辑 + 角色面板）
import test_e6_abilities
# P1 新增：E7 阵营 / 塔罗会社交（纯逻辑 + 面板 + 控制器）
import test_e7_factions
import test_panel_factions
import test_controller_e7
# P2 新增：E8 AI 对手非凡者（纯逻辑 + 面板 + 控制器）
import test_e8_rivals
import test_panel_rivals
import test_controller_e8
# P2 新增：E9 成就 / 图鉴 / 多结局（纯逻辑 + 面板）
import test_e9_achievements
import test_panel_codex
# P2 新增：E11 CLI↔GUI 共享核心（纯逻辑）
import test_e11_shared_core


if __name__ == "__main__":
    run_all()
