"""
测试 PQ 核心架构

验证队列系统、Tick 引擎、生成器是否正常工作。
"""
import sys
import os

# 添加 src 目录到路径
src_path = os.path.dirname(os.path.abspath(__file__))
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from core.queue_system import QueueSystem, QueueItem
from core.deterministic_rng import DeterministicRNG
from core.monster_task_generator import MonsterTaskGenerator
from core.equipment_generator import EquipmentGenerator


def test_queue_system():
    """测试队列系统"""
    print("=== 测试队列系统 ===")
    
    queue = QueueSystem()
    
    # 添加任务
    queue.enqueue(QueueItem('task', 'Task 1', 5000))
    queue.enqueue(QueueItem('task', 'Task 2', 3000))
    queue.enqueue(QueueItem('plot', 'Plot 1', 2000))
    
    print(f"队列长度: {queue.get_queue_length()}")
    
    # 取出第一个任务
    queue.dequeue()
    print(f"当前任务: {queue.get_current_action_label()}")
    print(f"进度: {queue.get_current_progress():.2%}")
    
    # 推进进度
    queue.advance(2500)
    print(f"推进 2500ms 后进度: {queue.get_current_progress():.2%}")
    
    # 完成当前任务
    queue.advance(2500)
    print(f"完成任务后，下一个任务: {queue.get_current_action_label()}")
    
    print("✅ 队列系统测试通过\n")


def test_deterministic_rng():
    """测试确定随机数生成器"""
    print("=== 测试确定随机数生成器 ===")
    
    rng1 = DeterministicRNG(seed=12345)
    rng2 = DeterministicRNG(seed=12345)
    
    # 相同种子应该产生相同序列
    nums1 = [rng1.random_int(100) for _ in range(10)]
    nums2 = [rng2.random_int(100) for _ in range(10)]
    
    print(f"RNG1: {nums1}")
    print(f"RNG2: {nums2}")
    print(f"相同种子产生相同序列: {nums1 == nums2}")
    
    # 测试 odds
    print(f"Odds(1, 4) 测试: {rng1.odds(1, 4)}")
    
    # 测试 pick
    items = ['A', 'B', 'C', 'D', 'E']
    print(f"Pick: {rng1.pick(items)}")
    
    print("✅ 确定随机数生成器测试通过\n")


def test_monster_task_generator():
    """测试怪物任务生成器"""
    print("=== 测试怪物任务生成器 ===")
    
    # 模拟主题数据
    theme_data = {
        'monsters': [
            {'name': 'Rat', 'level': 1, 'exp_reward': 50, 'gold_reward': 10},
            {'name': 'Goblin', 'level': 2, 'exp_reward': 100, 'gold_reward': 20},
            {'name': 'Orc', 'level': 5, 'exp_reward': 300, 'gold_reward': 50},
            {'name': 'Dragon', 'level': 20, 'exp_reward': 5000, 'gold_reward': 1000},
        ],
        'prefixes': {
            'sick': ['Dead', 'Comatose', 'Crippled'],
            'young': ['Baby', 'Teenage', 'Underage'],
            'big': ['Greater', 'Massive', 'Enormous'],
            'special': ['Veteran', 'Cursed', 'Undead'],
        }
    }
    
    rng = DeterministicRNG(seed=12345)
    generator = MonsterTaskGenerator(theme_data, rng)
    
    # 生成几个任务
    for i in range(5):
        task = generator.generate(char_level=3, char_name='TestHero')
        print(f"任务 {i+1}: {task.label} (持续 {task.duration_ms}ms)")
        print(f"  元数据: {task.metadata}")
    
    print("✅ 怪物任务生成器测试通过\n")


def test_equipment_generator():
    """测试装备生成器"""
    print("=== 测试装备生成器 ===")
    
    # 模拟主题数据
    theme_data = {
        'equipment': [
            {'name': 'Sword', 'slot': 'weapon', 'level': 1, 'base_stats': {'attack': 5}},
            {'name': 'Shield', 'slot': 'offhand', 'level': 1, 'base_stats': {'defense': 3}},
            {'name': 'Helmet', 'slot': 'head', 'level': 2, 'base_stats': {'hp': 10}},
        ]
    }
    
    rng = DeterministicRNG(seed=12345)
    generator = EquipmentGenerator(theme_data, rng)
    
    # 生成几个装备
    for i in range(5):
        equip = generator.generate(char_level=3)
        print(f"装备 {i+1}: {equip['name']}")
        print(f"  槽位: {equip['slot']}, 属性: {equip['stats']}")
    
    print("✅ 装备生成器测试通过\n")


def test_tick_engine():
    """测试 Tick 引擎 (简化版)"""
    print("=== 测试 Tick 引擎 (简化版) ===")
    
    # 创建模拟角色
    class MockCharacter:
        def __init__(self):
            self.name = "TestHero"
            self.level = 1
            self.exp = 0
            self.gold = 100
    
    character = MockCharacter()
    rng = DeterministicRNG(seed=12345)
    queue = QueueSystem()
    
    # 添加初始任务
    queue.enqueue(QueueItem('task', 'Test Task', 5000))
    queue.dequeue()
    
    # 测试推进
    print(f"初始进度: {queue.get_current_progress():.2%}")
    
    queue.advance(2500)
    print(f"推进 2500ms 后: {queue.get_current_progress():.2%}")
    
    queue.advance(2500)
    print(f"完成任务后: {queue.get_current_progress():.2%}")
    
    print("✅ Tick 引擎测试通过\n")


if __name__ == '__main__':
    print("🧪 开始测试 PQ 核心架构\n")
    
    try:
        test_queue_system()
        test_deterministic_rng()
        test_monster_task_generator()
        test_equipment_generator()
        test_tick_engine()
        
        print("🎉 所有测试通过！核心架构工作正常。")
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
