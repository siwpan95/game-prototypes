"""无限地图生成器 — 使用哈希函数实现确定性伪随机地形

核心思路：
- 对每个 (x, y) 坐标，基于哈希值决定地形
- 同一个坐标总是返回相同的地形（确定性）
- 无边界限制，玩家可以向任意方向无限移动
- 地形生成无需存储，按需计算
"""
import random


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


class TownGenerator:
    """城镇放置规则 — 在指定间隔生成城镇"""

    # 城镇间隔（每多少格放置一个城镇）
    TOWN_SPACING = 30

    @staticmethod
    def _hash_town_at(x: int, y: int, seed: int = 77) -> bool:
        """判断某坐标是否应放置城镇（确定性）"""
        h = seed
        h = (h * 374761393 + x * 668265263) & 0xFFFFFFFF
        h = (h * 374761393 + y * 668265263) & 0xFFFFFFFF
        h = (h ^ (h >> 13)) * 1274126177
        h = h ^ (h >> 16)
        return (h & 0x7FFFFFFF) % 100 < 30  # 30% 概率在有网格点上生成城镇

    @classmethod
    def get_town_position(cls, grid_x: int, grid_y: int) -> tuple:
        """返回城镇在网格点附近的具体坐标"""
        # 网格中心坐标
        cx = grid_x * cls.TOWN_SPACING + cls.TOWN_SPACING // 2
        cy = grid_y * cls.TOWN_SPACING + cls.TOWN_SPACING // 2

        # 加上小随机偏移（确定性）
        h = cx * 374761393 + cy * 668265263 + 99
        offset_x = (h & 0x7FFFFFFF) % 5 - 2  # [-2, 2]
        h = (h * 374761393) & 0xFFFFFFFF
        offset_y = ((h ^ (h >> 13)) * 1274126177) & 0x7FFFFFFF % 5 - 2

        return (cx + offset_x, cy + offset_y)

    @classmethod
    def is_town_at(cls, x: int, y: int) -> bool:
        """判断给定坐标是否有城镇"""
        # 找到最近的网格点
        grid_x = x // cls.TOWN_SPACING
        grid_y = y // cls.TOWN_SPACING
        tx, ty = cls.get_town_position(grid_x, grid_y)

        # 如果坐标恰好落在城镇位置且该网格点有城镇
        if (x, y) == (tx, ty):
            return cls._hash_town_at(grid_x, grid_y)

        # 也检查周围网格点（因为偏移可能使城镇落在相邻网格）
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                gx, gy = grid_x + dx, grid_y + dy
                pos = cls.get_town_position(gx, gy)
                if (x, y) == pos and cls._hash_town_at(gx, gy):
                    return True
                # 如果坐标碰巧在网格中心，也作为城镇
                if pos == (x, y):
                    return cls._hash_town_at(gx, gy)

        return False

    @classmethod
    def find_towns_in_rect(
        cls, x1: int, y1: int, x2: int, y2: int
    ) -> list:
        """查找矩形区域内的所有城镇坐标"""
        towns = []
        grid_x1 = (x1 - cls.TOWN_SPACING) // cls.TOWN_SPACING
        grid_y1 = (y1 - cls.TOWN_SPACING) // cls.TOWN_SPACING
        grid_x2 = (x2 + cls.TOWN_SPACING) // cls.TOWN_SPACING
        grid_y2 = (y2 + cls.TOWN_SPACING) // cls.TOWN_SPACING

        for gx in range(grid_x1, grid_x2 + 1):
            for gy in range(grid_y1, grid_y2 + 1):
                if cls._hash_town_at(gx, gy):
                    tx, ty = cls.get_town_position(gx, gy)
                    if x1 <= tx <= x2 and y1 <= ty <= y2:
                        towns.append((tx, ty))

        return towns
