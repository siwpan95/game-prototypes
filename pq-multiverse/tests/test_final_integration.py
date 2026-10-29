"""
最终集成测试 - TickEngine 线程模式

测试 TickEngine 在线程模式下是否正常工作。
"""
import sys
import os
import time

# 添加src目录到路径
src_path = os.path.dirname(os.path.abspath(__file__))
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from themed_engine_pq import PQThemedGameEngine


def test_tick_engine_thread():
    """测试 TickEngine 线程模式"""
    print("=== 最终集成测试 - TickEngine 线程模式 ===\n")
    
    # 1. 创建引擎
    print("[1/4] 创建引擎...")
    engine = PQThemedGameEngine("diablo", seed=12345)
    print(f"  ✅ 引擎创建成功 (主题: {engine.theme.name})")
    
    # 2. 创建角色
    print("\n[2/4] 创建角色...")
    engine.create_character("测试英雄", "人类", "死灵法师")
    print(f"  ✅ 角色创建成功: {engine.character.name}")
    print(f"  ✅ 第一个任务: {engine.current_action_text}")
    
    # 3. 启动 TickEngine (线程模式)
    print("\n[3/4] 启动 TickEngine (线程模式)...")
    
    # 设置更新回调
    update_count = [0]
    last_status = [None]
    
    def on_update(status):
        update_count[0] += 1
        last_status[0] = status
        
        # 每 2 秒显示一次状态
        if update_count[0] % 40 == 0:  # 40 ticks = 2 秒
            print(f"  Tick {status['tick_count']}: {status['current_action']} ({status['progress']:.1%})")
    
    engine.on_update = on_update
    
    # 启动游戏
    engine.start_game()
    print(f"  ✅ TickEngine 启动成功")
    
    # 4. 运行 5 秒
    print("\n[4/4] 运行 5 秒...")
    time.sleep(5)
    
    # 5. 停止游戏
    engine.stop_game()
    print(f"  ✅ TickEngine 停止成功")
    
    # 6. 检查结果
    print("\n=== 检查结果 ===")
    
    final_status = last_status[0]
    if final_status:
        print(f"✅ 最终状态:")
        print(f"  当前行动: {final_status['current_action']}")
        print(f"  进度: {final_status['progress']:.1%}")
        print(f"  Tick 计数: {final_status['tick_count']}")
        print(f"  角色等级: {final_status['character']['level']}")
        print(f"  角色经验: {final_status['character']['exp']}")
        
        # 验证 Tick 计数
        expected_ticks = 5000 // 50  # 5 秒 / 50ms per tick
        actual_ticks = final_status['tick_count']
        
        if actual_ticks > expected_ticks * 0.9:  # 允许 10% 误差
            print(f"\n✅ TickEngine 线程模式测试通过！")
            print(f"  预期 Ticks: ~{expected_ticks}")
            print(f"  实际 Ticks: {actual_ticks}")
        else:
            print(f"\n⚠️ Tick 计数可能不正确")
            print(f"  预期 Ticks: ~{expected_ticks}")
            print(f"  实际 Ticks: {actual_ticks}")
    else:
        print(f"❌ 无法获取最终状态")
    
    print(f"\n{'='*60}")


if __name__ == '__main__':
    try:
        test_tick_engine_thread()
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
