"""
最小化调试测试 - 队列系统

测试队列系统是否能正确：
1. 推进当前行动进度
2. 在行动完成后生成新任务
"""
import sys
import os

# 添加src目录到路径
src_path = os.path.dirname(os.path.abspath(__file__))
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from core.queue_system import QueueSystem, QueueItem
from core.deterministic_rng import DeterministicRNG
from core.monster_task_generator import MonsterTaskGenerator


def test_queue_system():
    """测试队列系统"""
    print("=== 最小化调试测试 - 队列系统 ===\n")
    
    # 1. 创建队列系统
    queue = QueueSystem()
    rng = DeterministicRNG(seed=12345)
    
    # 2. 创建模拟主题数据
    theme_data = {
        'monsters': [
            {'name': 'Rat', 'level': 1, 'exp_reward': 50, 'gold_reward': 10},
            {'name': 'Goblin', 'level': 2, 'exp_reward': 100, 'gold_reward': 20},
        ]
    }
    
    generator = MonsterTaskGenerator(theme_data, rng)
    
    # 3. 生成第一个任务
    task1 = generator.generate(char_level=1, char_name='Test')
    print(f"任务 1: {task1.label}")
    print(f"  持续时间: {task1.duration_ms}ms")
    
    # 4. 将任务设置为当前行动
    queue.enqueue(task1)
    queue.dequeue()
    
    print(f"\n当前行动: {queue.get_current_action_label()}")
    print(f"进度: {queue.get_current_progress():.1%}")
    print(f"队列长度: {queue.get_queue_length()}")
    
    # 5. 模拟推进 ticks
    print(f"\n{'='*60}")
    print("模拟推进 ticks...")
    print(f"{'='*60}")
    
    tick = 0
    max_ticks = 200  # 足够完成第一个任务
    
    while tick < max_ticks:
        # 推进 50ms
        action_completed = queue.advance(50)
        
        if action_completed:
            print(f"\n✅ Tick {tick}: 行动完成！")
            print(f"  完成: {task1.label}")
            
            # 生成新任务
            task2 = generator.generate(char_level=1, char_name='Test')
            queue.enqueue(task2)
            queue.dequeue()
            
            print(f"  新任务: {queue.get_current_action_label()}")
            print(f"  新任务持续时间: {task2.duration_ms}ms")
            break
        
        # 每 20 个 tick 显示一次进度
        if tick % 20 == 0:
            print(f"Tick {tick}: 进度 {queue.get_current_progress():.1%}")
        
        tick += 1
    
    if tick >= max_ticks:
        print(f"\n❌ 错误: {max_ticks} 个 ticks 后行动仍未完成")
        print(f"  当前进度: {queue.get_current_progress():.1%}")
        print(f"  当前行动: {queue.get_current_action_label()}")
    else:
        print(f"\n✅ 测试通过！")
        print(f"  完成任务用时: {tick} ticks ({tick * 50}ms)")
        print(f"  新任务: {queue.get_current_action_label()}")


if __name__ == '__main__':
    try:
        test_queue_system()
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
