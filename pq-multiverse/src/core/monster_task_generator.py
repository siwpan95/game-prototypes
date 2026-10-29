"""
Progress Quest Multiverse - 怪物任务生成器

复刻原版 ProgressQuest 的 MonsterTask() 函数，生成怪物战斗任务。
"""
from typing import Optional, Dict, List, Any
from. queue_system import QueueItem


class MonsterTaskGenerator:
    """怪物任务生成器 (原版：MonsterTask() 函数)
    
    原版 PQ 的怪物任务生成逻辑：
    1. 根据角色等级选择合适的怪物
    2. 添加修饰符 (Sick/Young/Big/Special)
    3. 计算任务持续时间
    4. 返回队列项
    """
    
    def __init__(self, theme_data: Dict, rng):
        """初始化
        
        Args:
            theme_data: 主题数据 (从 JSON 加载)
            rng: 确定随机数生成器 (DeterministicRNG)
        """
        self.theme_data = theme_data
        self.rng = rng
    
    def generate(self, char_level: int, char_name: str = "") -> QueueItem:
        """生成怪物任务 (原版：MonsterTask() 函数)
        
        Args:
            char_level: 角色等级
            char_name: 角色名称 (用于日志)
            
        Returns:
            QueueItem: 怪物任务队列项
        """
        # 1. 获取怪物列表
        monsters = self.theme_data.get('monsters', [])
        if not monsters:
            # 如果没有怪物数据，返回默认任务
            return QueueItem(
                item_type='task',
                label='Exploring the wilderness',
                duration_ms=5000,
                metadata={'type': 'explore'}
            )
        
        # 2. 选择合适的怪物 (原版：选择 5 次，取等级最接近的)
        suitable_monster = self._pick_monster(char_level, monsters)
        
        # 3. 生成怪物名称 (带修饰符)
        monster_name = self._generate_monster_name(
            suitable_monster['name'],
            suitable_monster.get('level', 1),
            char_level
        )
        
        # 4. 计算任务时长 (原版：2 * 3 * level * 1000 / char_level)
        monster_level = suitable_monster.get('level', 1)
        duration_ms = int(2 * 3 * monster_level * 1000 / max(char_level, 1))
        duration_ms = max(duration_ms, 1000)  # 最少 1 秒
        
        # 5. 创建队列项
        return QueueItem(
            item_type='task',
            label=f"Executing {monster_name}",
            duration_ms=duration_ms,
            metadata={
                'type': 'kill',
                'monster': suitable_monster,
                'monster_name': monster_name,
                'monster_level': monster_level,
                'reward_exp': suitable_monster.get('exp_reward', 100),
                'reward_gold': suitable_monster.get('gold_reward', 50),
            }
        )
    
    def _pick_monster(self, char_level: int, monsters: List[Dict]) -> Dict:
        """选择合适的怪物 (原版：MonsterTask 逻辑)
        
        原版逻辑：随机选择 5 次，选等级最接近的
        """
        best_monster = None
        best_diff = float('inf')
        
        for _ in range(5):
            monster = self.rng.pick(monsters)
            monster_level = monster.get('level', 1)
            diff = abs(char_level - monster_level)
            
            if diff < best_diff:
                best_diff = diff
                best_monster = monster
        
        return best_monster
    
    def _generate_monster_name(self, base_name: str, monster_level: int, char_level: int) -> str:
        """生成怪物名称 (带修饰符，原版逻辑)
        
        原版 PQ 的修饰符逻辑：
        - diff <= -10: "imaginary"
        - diff < -5: Sick + Young
        - diff < 0: Sick 或 Young
        - diff >= 10: "messianic"
        - diff > 5: Big + Special
        - diff > 0: Big 或 Special
        """
        diff = char_level - monster_level
        
        # 从主题数据读取修饰符 (如果有)
        prefixes = self.theme_data.get('prefixes', {})
        
        if diff <= -10:
            prefix = "Imaginary"
        elif diff < -5:
            # Sick + Young
            sick_prefix = self.rng.pick(prefixes.get('sick', ['weak', 'sick', 'crippled']))
            young_prefix = self.rng.pick(prefixes.get('young', ['baby', 'young', 'teenage']))
            prefix = f"{sick_prefix} {young_prefix}"
        elif diff < 0:
            # Sick 或 Young
            if self.rng.random_int(2) == 0:
                prefix = self.rng.pick(prefixes.get('sick', ['sick', 'weak', 'undernourished']))
            else:
                prefix = self.rng.pick(prefixes.get('young', ['young', 'baby', 'underage']))
        elif diff >= 10:
            prefix = "Messianic"
        elif diff > 5:
            # Big + Special
            big_prefix = self.rng.pick(prefixes.get('big', ['greater', 'massive', 'enormous']))
            special_prefix = self.rng.pick(prefixes.get('special', ['veteran', 'cursed', 'undead']))
            prefix = f"{big_prefix} {special_prefix}"
        elif diff > 0:
            # Big 或 Special
            if self.rng.random_int(2) == 0:
                prefix = self.rng.pick(prefixes.get('big', ['greater', 'massive', 'giant']))
            else:
                prefix = self.rng.pick(prefixes.get('special', ['veteran', 'cursed', 'demon']))
        else:
            prefix = ""
        
        # 组合名称
        if prefix:
            return f"{prefix} {base_name}"
        else:
            return base_name
