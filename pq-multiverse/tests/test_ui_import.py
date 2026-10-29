"""
测试 PQ 架构版 UI 导入

验证 ui/tkinter_ui_pq.py 可以正常导入。
"""
import sys
import os

# 添加src目录到路径
src_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)

print("=== 测试 PQ 架构版 UI 导入 ===\n")

# 测试1: 导入核心模块
print("[1/3] 导入核心模块...")
try:
    from core.queue_system import QueueSystem, QueueItem
    from core.deterministic_rng import DeterministicRNG
    from core.monster_task_generator import MonsterTaskGenerator
    from core.equipment_generator import EquipmentGenerator
    from core.tick_engine import TickEngine
    print("  ✅ 核心模块导入成功")
except Exception as e:
    print(f"  ❌ 核心模块导入失败: {e}")
    sys.exit(1)

# 测试2: 导入引擎模块
print("\n[2/3] 导入引擎模块...")
try:
    from themed_engine_pq import PQThemedGameEngine
    print("  ✅ 引擎模块导入成功")
except Exception as e:
    print(f"  ❌ 引擎模块导入失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 测试3: 导入 UI 模块
print("\n[3/3] 导入 UI 模块...")
try:
    from ui.tkinter_ui_pq import PQMainWindow
    print("  ✅ UI 模块导入成功")
except Exception as e:
    print(f"  ❌ UI 模块导入失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n=== 测试结果 ===")
print("✅ 所有模块导入成功！")
print("\nPQ 架构版 UI 已准备就绪。")
print("\n下一步：")
print("  1. 在本地运行 ui/tkinter_ui_pq.py 测试 UI")
print("  2. 完成步骤 C (测试多主题)")
print("  3. 完成步骤 D (完善 TickEngine 逻辑)")
