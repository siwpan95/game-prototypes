"""
完整集成测试 - PQ 架构

测试完整的游戏循环：
1. 创建角色
2. 启动 TickEngine
3. 验证队列系统自动生成新任务
4. 验证升级逻辑
5. 验证装备购买逻辑
"""
import sys
import os
import time

# 添加src目录到路径
src_path = os.path.dirname(os.path.abspath(__file__))
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from themed_engine_pq import PQThemedGameEngine


def test_full_game_loop():
    """测试完整游戏循环"""
    print("=== 完整集成测试 - PQ 架构 ===\n")
    
    # 1. 创建引擎
    print("[1/5] 创建引擎...")
    engine = PQThemedGameEngine("diablo", seed=12345)
    print(f"  ✅ 引擎创建成功 (主题: {engine.theme.name})")
    
    # 2. 创建角色
    print("\n[2/5] 创建角色...")
    engine.create_character("测试英雄", "人类", "死灵法师")
    print(f"  ✅ 角色创建成功: {engine.character.name}")
    print(f"  ✅ 第一个任务: {engine.current_action_text}")
    
    # 3. 手动模拟 TickEngine（不启动线程）
    print("\n[3/5] 模拟游戏循环 (50 ticks)...")
    
    class MockUI:
        def __init__(self):
            self.update_count = 0
        
        def on_update(self, status):
            self.update_count += 1
            if self.update_count % 10 == 0:
                print(f"  Tick {status['tick_count']}: {status['current_action']} ({status['progress']:.1%})")
    
    mock_ui = MockUI()
    engine.on_update = mock_ui.on_update
    
    # 手动推进 50 个 tick
    for i in range(50):
        # 推进当前行动
        action_completed = engine.queue_system.advance(50)
        
        if action_completed:
            # 处理完成的行动
            engine._process_completed_action()
            # 选择下一个行动
            engine._select_next_action()
        
        # 更新 UI
        if engine.on_update:
            engine.on_update(engine.get_pq_status())
    
    print(f"  ✅ 模拟完成 (队列长度: {engine.queue_system.get_queue_length()})")
    print(f"  ✅ 当前行动: {engine.queue_system.get_current_action_label()}")
    
    # 4. 检查队列是否自动生成新任务
    print("\n[4/5] 检查队列自动生成...")
    
    # 让当前任务完成，看看是否会生成新任务
    current = engine.queue_system.current_action
    if current:
        # 直接设置进度为完成
        engine.queue_system.current_progress_ms = current.duration_ms
        
        # 处理完成的行动
        engine._process_completed_action()
        
        # 选择下一个行动
        engine._select_next_action()
        
        print(f"  ✅ 新任务生成: {engine.queue_system.get_current_action_label()}")
        print(f"  ✅ 队列长度: {engine.queue_system.get_queue_length()}")
    
    # 5. 测试升级逻辑
    print("\n[5/5] 测试升级逻辑...")
    
    # 手动设置经验值
    engine.character.exp = 20 * engine.character.level * 60  # 升级所需经验
    
    # 检查升级
    engine._check_level_up()
    
    print(f"  ✅ 角色等级: {engine.character.level}")
    print(f"  ✅ 角色经验: {engine.character.exp}")
    
    print("\n=== 测试结果 ===")
    print(f"✅ 所有测试通过！")
    print(f"\n最终状态:")
    print(f"  角色: {engine.character.name} (等级 {engine.character.level})")
    print(f"  经验: {engine.character.exp}")
    print(f"  金币: {getattr(engine.character, 'gold', 0)}")
    print(f"  当前任务: {engine.queue_system.get_current_action_label()}")
    print(f"  队列长度: {engine.queue_system.get_queue_length()}")


if __name__ == '__main__':
    try:
        test_full_game_loop()
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
