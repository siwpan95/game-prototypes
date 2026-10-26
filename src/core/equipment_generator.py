"""
Progress Quest Multiverse - 装备生成器

复刻原版 ProgressQuest 的 WinEquip() 函数，生成随机装备。
"""
from typing import Optional, Dict, List, Any
from. queue_system import QueueItem


class EquipmentGenerator:
    """装备生成器 (原版：WinEquip() 函数)
    
    原版 PQ 的装备生成逻辑：
    1. 根据角色等级选择基础装备
    2. 添加随机属性修饰符 (最多 2 个)
    3. 构建装备名称 (前缀系统)
    4. 计算装备属性
    """
    
    def __init__(self, theme_data: Dict, rng):
        """初始化
        
        Args:
            theme_data: 主题数据 (从 JSON 加载)
            rng: 确定随机数生成器 (DeterministicRNG)
        """
        self.theme_data = theme_data
        self.rng = rng
    
    def generate(self, char_level: int) -> Dict:
        """生成装备 (原版：WinEquip() 函数)
        
        Args:
            char_level: 角色等级
            
        Returns:
            Dict: 生成的装备数据
        """
        # 1. 获取装备列表
        equipment_list = self.theme_data.get('equipment', [])
        if not equipment_list:
            # 如果没有装备数据，返回默认装备
            return {
                'name': 'Basic Sword',
                'slot': 'weapon',
                'stats': {'attack': 5},
                'level': char_level,
            }
        
        # 2. 选择合适的基础装备
        base_equipment = self._pick_equipment(char_level, equipment_list)
        
        # 3. 添加随机属性修饰符
        modifiers = self._generate_modifiers(char_level, base_equipment)
        
        # 4. 构建装备名称
        name = self._build_equipment_name(base_equipment, modifiers)
        
        # 5. 计算装备属性
        stats = self._calculate_stats(base_equipment, modifiers, char_level)
        
        # 6. 确定装备槽位
        slot = base_equipment.get('slot', 'weapon')
        
        return {
            'name': name,
            'slot': slot,
            'stats': stats,
            'level': char_level,
            'base_name': base_equipment['name'],
            'modifiers': modifiers,
        }
    
    def _pick_equipment(self, char_level: int, equipment_list: List[Dict]) -> Dict:
        """选择基础装备
        
        原版逻辑：根据等级选择，允许略高于角色等级
        """
        # 选择合适的装备 (等级 <= char_level + 2)
        suitable = [eq for eq in equipment_list if eq.get('level', 1) <= char_level + 2]
        
        if not suitable:
            # 如果没有合适的，选择等级最低的
            suitable = sorted(equipment_list, key=lambda x: x.get('level', 1))
            return suitable[0]
        
        # 随机选择一个
        return self.rng.pick(suitable)
    
    def _generate_modifiers(self, char_level: int, base_equipment: Dict) -> List[str]:
        """生成修饰符 (原版：前缀系统)
        
        原版 PQ 的修饰符逻辑：
        - plus = char_level - base_equipment.level
        - 最多 2 个修饰符
        - 每个修饰符对应一个属性
        """
        modifiers = []
        
        # 计算等级差
        base_level = base_equipment.get('level', 1)
        plus = char_level - base_level
        
        # 最多 2 个修饰符
        num_modifiers = min(2, abs(plus))
        
        # 可能的属性修饰符
        possible_attrs = ['strength', 'constitution', 'dexterity', 'intelligence', 'wisdom', 'charisma']
        
        for _ in range(num_modifiers):
            attr = self.rng.pick(possible_attrs)
            modifiers.append(attr)
        
        return modifiers
    
    def _build_equipment_name(self, base_equipment: Dict, modifiers: List[str]) -> str:
        """构建装备名称 (原版：前缀系统)
        
        原版 PQ 的装备名称格式：
        [属性1] [属性2] [+/-等级] [基础名称]
        例：+3 Giant Fire Sword of Burning
        """
        name = base_equipment['name']
        
        # 添加修饰符前缀
        for mod in modifiers:
            mod_prefix = self._get_modifier_prefix(mod)
            name = f"{mod_prefix} {name}"
        
        # 添加等级加成
        base_level = base_equipment.get('level', 1)
        plus = len(modifiers)
        
        if plus > 0:
            name = f"+{plus} {name}"
        
        return name
    
    def _get_modifier_prefix(self, modifier: str) -> str:
        """获取修饰符前缀"""
        prefix_map = {
            'strength': 'Strong',
            'constitution': 'Sturdy',
            'dexterity': 'Swift',
            'intelligence': 'Wise',
            'wisdom': 'Sage',
            'charisma': 'Noble',
        }
        
        return prefix_map.get(modifier, 'Magic')
    
    def _calculate_stats(self, base_equipment: Dict, modifiers: List[str], char_level: int) -> Dict:
        """计算装备属性"""
        # 基础属性
        stats = base_equipment.get('base_stats', {}).copy()
        
        # 添加修饰符加成
        for mod in modifiers:
            if mod == 'strength':
                stats['attack'] = stats.get('attack', 0) + char_level
            elif mod == 'constitution':
                stats['hp'] = stats.get('hp', 0) + char_level * 5
            elif mod == 'dexterity':
                stats['dodge'] = stats.get('dodge', 0) + char_level
            elif mod == 'intelligence':
                stats['magic_attack'] = stats.get('magic_attack', 0) + char_level
            elif mod == 'wisdom':
                stats['mp'] = stats.get('mp', 0) + char_level * 3
            elif mod == 'charisma':
                stats['charm'] = stats.get('charm', 0) + char_level
        
        return stats
    
    def generate_purchase_task(self, char_level: int) -> QueueItem:
        """生成购买装备任务 (原版：buying 任务)
        
        Returns:
            QueueItem: 购买装备任务
        """
        # 计算装备价格 (原版：5 * level^2 + 10 * level + 20)
        price = 5 * char_level * char_level + 10 * char_level + 20
        
        return QueueItem(
            item_type='task',
            label='Negotiating purchase of better equipment',
            duration_ms=5000,  # 5 秒
            metadata={
                'type': 'buying',
                'price': price,
            }
        )
