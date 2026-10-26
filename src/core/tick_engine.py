"""
Progress Quest Multiverse - Tick 引擎

复刻原版 ProgressQuest 的 Timer1Timer() 函数，实现游戏主循环。
"""
import threading
import time
from typing import Optional, Callable
from. queue_system import QueueSystem, QueueItem
from. deterministic_rng import DeterministicRNG


class TickEngine:
    """Tick 引擎 (原版：Timer1Timer() 函数)
    
    原版 PQ 的 Tick 逻辑 (每 50ms 执行一次)：
    1. 推进当前行动进度
    2. 如果行动完成，处理结果并选择下一个
    3. 获得经验 (每次 tick 获得 MaxProgress/1000)
    4. 检查升级
    5. 更新 UI
    
    这是 PQ 的核心 game loop。
    """
    
    TICK_INTERVAL_MS = 50  # 原版：50ms
    TICK_INTERVAL_SEC = TICK_INTERVAL_MS / 1000.0
    
    def __init__(self, queue_system: QueueSystem, character, rng: DeterministicRNG,
                 ui_callback: Optional[Callable] = None):
        """初始化
        
        Args:
            queue_system: 队列系统
            character: 角色对象
            rng: 确定随机数生成器
            ui_callback: UI 更新回调函数 (可选)
        """
        self.queue_system = queue_system
        self.character = character
        self.rng = rng
        self.ui_callback = ui_callback
        
        self.is_running = False
        self._timer = None
        self._tick_count = 0
    
    def start(self):
        """启动引擎 (原版：StartTimer())"""
        if not self.is_running:
            self.is_running = True
            self._tick()
            print(f"✅ TickEngine 启动 (间隔: {self.TICK_INTERVAL_MS}ms)")
    
    def stop(self):
        """停止引擎 (原版：StopTimer())"""
        self.is_running = False
        if self._timer:
            self._timer.cancel()
            self._timer = None
        print(f"⏸️ TickEngine 停止 (总 tick: {self._tick_count})")
    
    def manual_tick(self) -> dict:
        """手动推进一个 tick (用于测试/调试)
        
        Returns:
            如果行动完成，返回结果字典；否则返回 None
        """
        # 1. 推进当前行动
        action_completed = self.queue_system.advance(self.TICK_INTERVAL_MS)
        
        result = None
        if action_completed:
            # 处理完成的行动
            result = self._process_completed_action()
            # 选择下一个行动
            self._select_next_action()
        
        # 2. 获得经验
        if self.queue_system.current_action:
            exp_gain = self._calculate_exp_gain()
            self.character.exp = getattr(self.character, 'exp', 0) + exp_gain
        
        # 3. 检查升级
        self._check_level_up()
        
        # 4. 更新 tick 计数
        self._tick_count += 1
        
        return result
    
    def _tick(self):
        """每次 tick 处理逻辑 (原版：Timer1Timer() 函数)"""
        if not self.is_running:
            return
        
        try:
            # 1. 推进当前行动
            action_completed = self.queue_system.advance(self.TICK_INTERVAL_MS)
            
            if action_completed:
                # 处理完成的行动
                self._process_completed_action()
                # 选择下一个行动
                self._select_next_action()
            
            # 2. 获得经验 (原版：每次 tick 获得 MaxProgress/1000)
            if self.queue_system.current_action:
                exp_gain = self._calculate_exp_gain()
                self.character.exp = getattr(self.character, 'exp', 0) + exp_gain
            
            # 3. 检查升级
            self._check_level_up()
            
            # 4. 更新 UI
            if self.ui_callback:
                self.ui_callback(self.get_status())
            
            # 5. 继续下一个 tick
            self._tick_count += 1
            if self.is_running:
                self._timer = threading.Timer(self.TICK_INTERVAL_SEC, self._tick)
                self._timer.start()
        
        except Exception as e:
            print(f"❌ TickEngine 错误: {e}")
            self.stop()
    
    def _process_completed_action(self):
        """处理完成的行动 (原版：Dequeue() 中的逻辑)"""
        completed_action = self.queue_system.current_action
        
        if completed_action is None:
            return
        
        metadata = completed_action.metadata
        
        if metadata.get('type') == 'kill':
            # 击杀怪物：获得经验、金币、战利品
            self.character.exp = getattr(self.character, 'exp', 0) + metadata.get('reward_exp', 100)
            self.character.gold = getattr(self.character, 'gold', 0) + metadata.get('reward_gold', 50)
            print(f"✅ 击败 {metadata.get('monster_name', '怪物')}！获得 {metadata.get('reward_exp', 100)} 经验")
        
        elif metadata.get('type') == 'buying':
            # 购买装备：生成新装备
            self._win_equip()
            print(f"🛡️ 购买了新装备！")
        
        elif metadata.get('type') == 'sell':
            # 出售战利品
            self._sell_loot()
            print(f"💰 出售了战利品！")
        
        elif metadata.get('type') == 'market':
            # 前往市场
            print(f"🏪 前往市场出售战利品")
    
    def _select_next_action(self):
        """选择下一个行动 (原版：Dequeue() 逻辑)
        
        优先级：
        1. 队列中有任务 → 执行
        2. 负重满 → 去市场
        3. 有钱 → 买装备
        4. 生成怪物任务
        """
        # 1. 如果队列中有任务，取出下一个
        if self.queue_system.queue:
            self.queue_system.dequeue()
            return
        
        # 2. 检查负重 (如果有 encumbrance 系统)
        encumbrance_percent = self._get_encumbrance_percent()
        if encumbrance_percent >= 100:
            # 负重满：去市场
            self.queue_system.enqueue(QueueItem(
                item_type='task',
                label='Heading to market to sell loot',
                duration_ms=4000,
                metadata={'type': 'market'}
            ))
            self.queue_system.dequeue()
            return
        
        # 3. 检查是否有钱买装备
        equip_price = self._calculate_equip_price()
        if getattr(self.character, 'gold', 0) >= equip_price:
            # 有钱：买装备
            self.queue_system.enqueue(QueueItem(
                item_type='task',
                label='Negotiating purchase of better equipment',
                duration_ms=5000,
                metadata={'type': 'buying'}
            ))
            self.queue_system.dequeue()
            return
        
        # 4. 生成怪物任务
        # 这个方法需要在集成时注入 monster_task_generator
        if hasattr(self, 'monster_task_generator'):
            monster_task = self.monster_task_generator.generate(
                getattr(self.character, 'level', 1),
                getattr(self.character, 'name', '')
            )
            self.queue_system.enqueue(monster_task)
            self.queue_system.dequeue()
        else:
            # 如果没有 monster_task_generator，生成默认任务
            self.queue_system.enqueue(QueueItem(
                item_type='task',
                label='Exploring the wilderness',
                duration_ms=5000,
                metadata={'type': 'explore'}
            ))
            self.queue_system.dequeue()
    
    def _calculate_exp_gain(self) -> float:
        """计算经验获得 (原版：MaxProgress/1000)
        
        原版 PQ 每次 tick 获得经验 = MaxProgress / 1000
        这里简化为每次 tick 获得 1 经验
        """
        return 1.0
    
    def _check_level_up(self):
        """检查升级 (原版：GetLevelUpMaxValue())"""
        current_exp = getattr(self.character, 'exp', 0)
        current_level = getattr(self.character, 'level', 1)
        
        # 原版公式：20 * level * 60 (秒)
        exp_needed = 20 * current_level * 60
        
        if current_exp >= exp_needed:
            # 升级！
            self.character.level = current_level + 1
            self.character.exp = current_exp - exp_needed
            print(f"🎉 升级！等级 {current_level} → {current_level + 1}")
            
            # 提升属性 (原版：WinStat() 逻辑)
            self._win_stat()
    
    def _win_stat(self):
        """提升属性 (原版：WinStat() 函数)
        
        原版 PQ 的属性提升逻辑：
        - 50% 概率选择当前最低的属性
        - 50% 概率随机选择属性
        """
        # 获取当前属性
        stats = ['strength', 'constitution', 'dexterity', 'intelligence', 'wisdom', 'charisma']
        current_stats = {}
        
        for stat in stats:
            current_stats[stat] = getattr(self.character, stat, 10)
        
        # 50% 概率选择最低属性
        if self.rng.odds(1, 2):
            # 选择最低属性
            min_stat = min(current_stats, key=current_stats.get)
            setattr(self.character, min_stat, current_stats[min_stat] + 1)
            print(f"📈 属性提升: {min_stat} +1")
        else:
            # 随机选择属性
            random_stat = self.rng.pick(stats)
            setattr(self.character, random_stat, current_stats[random_stat] + 1)
            print(f"📈 属性提升: {random_stat} +1")
    
    def _win_equip(self):
        """获得新装备 (原版：WinEquip() 函数)
        
        这个方法需要在集成时注入 equipment_generator
        """
        if hasattr(self, 'equipment_generator'):
            new_equip = self.equipment_generator.generate(
                getattr(self.character, 'level', 1)
            )
            print(f"🛡️ 获得新装备: {new_equip['name']}")
            # 这里需要将装备添加到角色的装备槽
            # 具体实现在集成时完成
        else:
            print(f"🛡️ 获得新装备 (未配置 equipment_generator)")
    
    def _sell_loot(self):
        """出售战利品"""
        # 具体实现在集成时完成
        pass
    
    def _get_encumbrance_percent(self) -> float:
        """获取负重百分比"""
        # 具体实现在集成时完成
        return 0.0
    
    def _calculate_equip_price(self) -> int:
        """计算装备价格 (原版：EquipPrice())
        
        原版公式：5 * level^2 + 10 * level + 20
        """
        level = getattr(self.character, 'level', 1)
        return 5 * level * level + 10 * level + 20
    
    def get_status(self) -> dict:
        """获取当前状态 (供 UI 显示)"""
        current = self.queue_system.current_action
        progress = self.queue_system.get_current_progress()
        
        return {
            'is_running': self.is_running,
            'tick_count': self._tick_count,
            'current_action': current.label if current else 'Idle',
            'progress': progress,
            'queue_length': self.queue_system.get_queue_length(),
            'character': {
                'name': getattr(self.character, 'name', 'Unknown'),
                'level': getattr(self.character, 'level', 1),
                'exp': getattr(self.character, 'exp', 0),
                'gold': getattr(self.character, 'gold', 0),
            }
        }
