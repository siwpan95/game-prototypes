"""
Progress Quest Multiverse - 确定随机数生成器

复刻原版 ProgressQuest 的 Alea+Mash 算法，确保游戏可重复性。
原版 PQ 使用确定随机数，使得相同种子产生相同游戏流程。
"""
import random
import time


class DeterministicRNG:
    """确定随机数生成器 (原版 PQ：Alea+Mash 算法简化版)
    
    用途：
    - 确保游戏可重复 (相同种子 = 相同流程)
    - 这是 PQ 的核心特征之一
    - 所有游戏逻辑都应使用此 RNG，而非 Python 的 random
    
    原版 PQ 使用 Alea 和 Mash 算法，这里用 Python 的 random.Random 模拟。
    """
    
    def __init__(self, seed: Optional[int] = None):
        """初始化 RNG
        
        Args:
            seed: 随机种子，如果为 None 则使用当前时间戳
        """
        if seed is None:
            seed = int(time.time() * 1000)
        
        self.seed = seed
        self.rng = random.Random(seed)
    
    def random_int(self, n: int) -> int:
        """返回 [0, n) 的随机整数 (原版：Random(n))
        
        Args:
            n: 上限 (不包含)
            
        Returns:
            int: [0, n) 的随机整数
        """
        if n <= 0:
            return 0
        return self.rng.randint(0, n - 1)
    
    def odds(self, chance: int, out_of: int) -> bool:
        """概率判断 (原版：Odds(chance, out_of))
        
        Args:
            chance: 成功概率分子
            out_of: 概率分母
            
        Returns:
            bool: 是否成功
            
        Example:
            odds(1, 4)  # 25% 概率返回 True
        """
        return self.random_int(out_of) < chance
    
    def random_low(self, below: int) -> int:
        """返回两个随机数的较小值 (原版：RandomLow(below))
        
        用途：生成偏向小值的结果，用于等级调整等
        
        Args:
            below: 上限 (不包含)
            
        Returns:
            int: 两个随机数中的较小值
        """
        return min(self.random_int(below), self.random_int(below))
    
    def pick(self, items: list) -> Any:
        """随机选择一个元素 (原版：Pick(list))"""
        if not items:
            return None
        return items[self.random_int(len(items))]
    
    def pick_low(self, items: list) -> Any:
        """随机选择 (偏向低索引，原版：PickLow(list))"""
        if not items:
            return None
        return items[self.random_low(len(items))]
    
    def rand_sign(self) -> int:
        """返回随机正负号 (原版：RandSign())
        
        Returns:
            int: -1 或 1
        """
        return self.random_int(2) * 2 - 1
    
    def random_float(self) -> float:
        """返回 [0.0, 1.0) 的随机浮点数"""
        return self.rng.random()
    
    def shuffle(self, items: list):
        """随机打乱列表 (原地修改)"""
        self.rng.shuffle(items)
    
    def set_seed(self, seed: int):
        """重新设置种子"""
        self.seed = seed
        self.rng = random.Random(seed)
    
    def get_seed(self) -> int:
        """获取当前种子"""
        return self.seed
