"""
Progress Quest Multiverse - PQ 队列系统

复刻原版 ProgressQuest 的队列机制 (struct QueueItem + game.queue)
"""
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any


@dataclass
class QueueItem:
    """PQ 队列项 (原版：struct QueueItem)
    
    原版 PQ 的队列项格式：
    - "task|duration|label"  (普通任务)
    - "plot|duration|label"  (剧情过场)
    """
    item_type: str           # 'task' | 'plot'
    label: str               # 显示文本
    duration_ms: int         # 持续时间 (毫秒)
    metadata: Dict[str, Any] = field(default_factory=dict)  # 额外数据


class QueueSystem:
    """PQ 队列系统 (原版：game.queue)
    
    原版 PQ 使用队列管理行动顺序：
    1. 队列中的任务按顺序执行
    2. 当前任务完成后，自动选择下一个
    3. 队列为空时，根据条件生成新任务
    """
    
    def __init__(self):
        self.queue: List[QueueItem] = []
        self.current_action: Optional[QueueItem] = None
        self.current_progress_ms: int = 0
    
    def enqueue(self, item: QueueItem):
        """添加队列项 (原版：Q() 函数)"""
        self.queue.append(item)
    
    def enqueue_many(self, items: List[QueueItem]):
        """批量添加队列项"""
        self.queue.extend(items)
    
    def dequeue(self) -> Optional[QueueItem]:
        """取出下一个行动 (原版：Dequeue() 逻辑)
        
        返回下一个行动，如果没有则返回 None
        """
        if self.current_action is None and self.queue:
            self.current_action = self.queue.pop(0)
            self.current_progress_ms = 0
        return self.current_action
    
    def advance(self, ms: int) -> bool:
        """推进当前行动进度
        
        Args:
            ms: 推进的毫秒数
            
        Returns:
            bool: 当前行动是否完成
        """
        if self.current_action is None:
            return False
        
        self.current_progress_ms += ms
        
        if self.current_progress_ms >= self.current_action.duration_ms:
            completed = self.current_action
            self.current_action = None
            self.current_progress_ms = 0
            return True  # 行动完成
        
        return False
    
    def get_current_progress(self) -> float:
        """获取当前进度 (0.0 - 1.0)"""
        if self.current_action is None:
            return 0.0
        
        return self.current_progress_ms / self.current_action.duration_ms
    
    def get_current_action_label(self) -> str:
        """获取当前行动显示文本"""
        if self.current_action is None:
            return "Idle"
        return self.current_action.label
    
    def clear(self):
        """清空队列"""
        self.queue.clear()
        self.current_action = None
        self.current_progress_ms = 0
    
    def is_empty(self) -> bool:
        """队列是否为空"""
        return len(self.queue) == 0 and self.current_action is None
    
    def get_queue_length(self) -> int:
        """获取队列长度"""
        return len(self.queue)
