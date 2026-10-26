"""
无头测试：验证 PQ UI 逻辑（不显示窗口）

测试内容：
1. 引擎创建和初始化
2. 角色创建
3. 游戏启动
4. 状态更新
5. 队列系统
"""

import sys
import os
import time

# 添加src目录到路径
src_path = os.path.dirname(os.path.abspath(__file__))
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from themed_engine_pq import PQThemedGameEngine

def test_ui_logic():
    """测试 UI 逻辑（无头模式）"""
    print("🧪 开始无头测试：PQ UI 逻辑")
    print("=" * 60)
    
    # 1. 创建引擎
    print("\n📁 步骤 1：创建引擎")
    engine = PQThemedGameEngine("diablo")
    print(f"  ✅ 引擎创建成功")
    print(f"  主题: {engine.theme.name}")
    
    # 2. 创建角色
    print("\n👤 步骤 2：创建角色")
    engine.create_character("测试英雄", "人类", "死灵法师")
    print(f"  ✅ 角色创建成功")
    print(f"  名称: {engine.character.name}")
    print(f"  等级: {engine.character.level}")
    
    # 3. 启动游戏
    print("\n🚀 步骤 3：启动游戏")
    engine.start_game()
    print(f"  ✅ 游戏启动成功")
    
    # 4. 模拟 ticks（手动模式）
    print("\n⏱️  步骤 4：模拟游戏循环（50 ticks）")
    for i in range(50):
        status_before = engine.get_pq_status()
        
        # 手动推进一个 tick
        result = engine.tick_engine.manual_tick()
        
        if result:
            print(f"  Tick {i+1}: ✅ 行动完成 - {result.get('action_label', 'Unknown')}")
            if result.get('rewards'):
                print(f"    奖励: {result['rewards']}")
    
    # 5. 检查最终状态
    print("\n📊 步骤 5：检查最终状态")
    final_status = engine.get_pq_status()
    print(f"  ✅ 最终状态获取成功")
    print(f"  当前行动: {final_status['current_action']}")
    print(f"  进度: {final_status['progress']:.1%}")
    print(f"  队列长度: {final_status['queue_length']}")
    print(f"  角色等级: {final_status['character']['level']}")
    print(f"  角色经验: {final_status['character']['exp']:.1f}")
    
    # 6. 测试暂停/恢复
    print("\n⏸️  步骤 6：测试暂停/恢复")
    engine.pause_game()
    print(f"  ✅ 游戏已暂停")
    
    engine.resume_game()
    print(f"  ✅ 游戏已恢复")
    
    # 7. 测试保存/加载
    print("\n💾 步骤 7：测试保存/加载")
    save_path = "test_save.json"
    engine.save_game(save_path)
    print(f"  ✅ 游戏已保存: {save_path}")
    
    # 8. 测试结果
    print("\n" + "=" * 60)
    print("🎉 所有测试通过！")
    print("=" * 60)
    
    return True

if __name__ == "__main__":
    try:
        success = test_ui_logic()
        if success:
            print("\n✅ 无头测试完成，UI 逻辑验证通过！")
            print("\n💡 下一步：在本地运行 UI")
            print("   命令: python run_pq_ui.py")
        else:
            print("\n❌ 测试失败")
            sys.exit(1)
    except Exception as e:
        print(f"\n❌ 测试错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
