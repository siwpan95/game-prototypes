"""无限地形生成器 — 使用哈希函数实现确定性伪随机地形

核心思路：
- 对每个 (x, y) 坐标，基于哈希值决定地形
- 同一个坐标总是返回相同的地形（确定性）
- 无边界限制，玩家可以向任意方向无限移动
- 地形生成无需存储，按需计算
"""


class InfiniteTerrain:
    """无限地形生成器 — 纯函数，零状态"""

    # 地形符号及其权重
    TERRAIN_WEIGHTS = [
        ('.', 82),   # 平原 - 82%
        ('T', 10),   # 树木 - 10%
        ('^', 5),    # 山地 - 5%
        ('~', 3),    # 水域 - 3%
    ]

    # 不同地形类型的累计阈值（自动计算）
    _thresholds = None

    @classmethod
    def _init_thresholds(cls):
        if cls._thresholds is not None:
            return
        total = sum(w for _, w in cls.TERRAIN_WEIGHTS)
        acc = 0
        thresholds = []
        for terrain, weight in cls.TERRAIN_WEIGHTS:
            acc += weight / total * 100
            thresholds.append((terrain, acc))
        cls._thresholds = thresholds

    @staticmethod
    def _hash_coord(x: int, y: int, seed: int = 42) -> int:
        """对坐标 (x, y) 做确定性哈希，返回 [0, 2^31-1] 的伪随机整数"""
        h = seed
        h = (h * 374761393 + x * 668265263) & 0xFFFFFFFF
        h = (h * 374761393 + y * 668265263) & 0xFFFFFFFF
        h = (h ^ (h >> 13)) * 1274126177
        h = h ^ (h >> 16)
        return h & 0x7FFFFFFF

    @classmethod
    def pick_weighted(cls, x: int, y: int, seed: int, chars: list) -> str:
        """按权重表从 chars 中确定性选一个字符（有限地图生成用）"""
        if not chars:
            return '.'
        h = cls._hash_coord(x, y, seed)
        return chars[h % len(chars)]

    @classmethod
    def get_terrain(cls, x: int, y: int) -> str:
        """获取 (x, y) 处的地形字符，始终返回相同结果"""
        cls._init_thresholds()
        h = cls._hash_coord(x, y)
        # 将哈希值映射到 [0, 99]
        roll = (h % 7919) % 100  # 7919 是质数，改善分布

        for terrain, threshold in cls._thresholds:
            if roll < threshold:
                return terrain
        return '.'  # 兜底

    @classmethod
    def is_passable(cls, x: int, y: int) -> bool:
        """坐标是否可通行"""
        terrain = cls.get_terrain(x, y)
        return terrain not in ('~', '^')

    @classmethod
    def get_chunk(
        cls, start_x: int, start_y: int, width: int, height: int
    ) -> list:
        """生成一块矩形区域的地形（二维字符列表）"""
        chunk = []
        for cy in range(start_y, start_y + height):
            row = []
            for cx in range(start_x, start_x + width):
                row.append(cls.get_terrain(cx, cy))
            chunk.append(row)
        return chunk
