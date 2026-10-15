"""地图管理器（纯业务逻辑，零UI依赖）

两套地图体系：
1. 无限地图（荒野）：哈希函数确定性生成地形，无边界，向任意方向探索；
   配置的有限地图在荒野中有固定入口（地图上显示为 □），走到入口按空格进入。
2. 有限地图（城镇/遗迹）：按 Maps 表 宽度×高度 程序化生成 bounded 网格，
   边界为墙，内部按 地形类型 权重铺地形；城镇地图进入后直接处于城镇状态。
"""
from .game_state import GameState
from .infinite_map import InfiniteTerrain


# 视口大小（字符单位）
VIEWPORT_W = 40
VIEWPORT_H = 22

# 有限地图中不可通行的字符
BLOCKED_CHARS = ('~', '^', '#')

# 地形类型名（Excel 配置） → 显示字符
TERRAIN_CHAR_MAP = {
    '平原': '.', '道路': '.', '城镇': '.', '废墟': '.',
    '森林': 'T', '树木': 'T',
    '山地': '^', '洞穴': '^',
    '水域': '~', '港口': '~', '河流': '~',
    '建筑': '#', '工厂': '#', '机械': '#',
}


class MapManager:
    """地图生成、碰撞检测与视口渲染"""

    # ── 初始化 / 网格生成 ──

    @staticmethod
    def create_map(data: "GameData", maps_config: dict, npcs_config: dict):
        """初始化地图系统：登记荒野入口 + 确保当前地图网格已生成"""
        data.town_positions = []
        data.map_entrances = {}  # (x, y) -> map_id，荒野中的地图入口
        for m in maps_config.values():
            if m.infinite:
                continue
            # 荒野坐标可正可负，用 -1 表示"无入口"
            if m.entrance_x != -1 and m.entrance_y != -1:
                data.map_entrances[(m.entrance_x, m.entrance_y)] = m.id
                data.town_positions.append((m.entrance_x, m.entrance_y))
        MapManager._ensure_grid(data, maps_config, npcs_config)

    @staticmethod
    def _ensure_grid(data: "GameData", maps_config: dict, npcs_config: dict):
        """当前所在地图是有限地图时，确保其网格已生成"""
        m = maps_config.get(data.current_map_id)
        if m is None or m.infinite:
            return
        if data.current_map_id not in data.map_grids:
            MapManager.generate_map(data, m, npcs_config)

    @staticmethod
    def generate_map(data: "GameData", map_data, npcs_config: dict = None):
        """为有限地图生成确定性 bounded 网格并缓存到 data.map_grids"""
        w, h = map_data.width, map_data.height
        seed = 9000 + map_data.id * 137

        # 地形类型 → 字符权重表
        weights = []
        for t in str(map_data.terrain_types).split(','):
            t = t.strip()
            if t:
                weights.append(TERRAIN_CHAR_MAP.get(t, '.'))
        if not weights:
            weights = ['.']

        grid = []
        for y in range(h):
            row = []
            for x in range(w):
                if x == 0 or y == 0 or x == w - 1 or y == h - 1:
                    row.append('^')  # 边界墙
                else:
                    row.append(InfiniteTerrain.pick_weighted(x, y, seed, weights))
            grid.append(row)

        # NPC 所在格强制可通行（保证配置的 NPC 一定可达）
        if npcs_config:
            for npc in npcs_config.values():
                if npc.map_id == map_data.id:
                    nx, ny = npc.location_x, npc.location_y
                    if 0 <= nx < w and 0 <= ny < h:
                        grid[ny][nx] = '.'

        # 入口格（底部中央）强制可通行
        ex, ey = MapManager.entrance_cell(map_data)
        if 0 <= ex < w and 0 <= ey < h:
            grid[ey][ex] = '.'

        data.map_grids[map_data.id] = grid

    @staticmethod
    def entrance_cell(map_data) -> tuple:
        """有限地图的入口格坐标（底部中央）"""
        return (map_data.width // 2, map_data.height - 2)

    # ── 查询 ──

    @staticmethod
    def _map_data(data: "GameData", map_id: int = None):
        """取 MapData；config 缺失时返回 None"""
        mid = data.current_map_id if map_id is None else map_id
        if data.config is None:
            return None
        return data.config.maps.get(mid)

    @staticmethod
    def is_bounded(data: "GameData", map_id: int = None) -> bool:
        """该地图是否为有限地图（城镇/遗迹）"""
        m = MapManager._map_data(data, map_id)
        return m is not None and not m.infinite

    @staticmethod
    def is_passable(data: "GameData", x: int, y: int) -> bool:
        """坐标是否可通行（有限地图还受边界限制）"""
        m = MapManager._map_data(data)
        if m is None:
            return True
        if m.infinite:
            if InfiniteTerrain.is_passable(x, y):
                return True
            # 入口与赏金首所在格强制可通行（视为空地），保证可达
            if data.config is not None:
                if (x, y) in data.map_entrances:
                    return True
                for bounty in data.config.bounties.values():
                    if (bounty.map_id == m.id and (x, y) == (bounty.x, bounty.y)):
                        return True
            return False
        if not (0 <= x < m.width and 0 <= y < m.height):
            return False
        grid = data.map_grids.get(m.id)
        if grid is None:
            return True
        return grid[y][x] not in BLOCKED_CHARS

    @staticmethod
    def can_move_to(data: "GameData", x: int, y: int) -> bool:
        return MapManager.is_passable(data, x, y)

    @staticmethod
    def get_map_char(data: "GameData", x: int, y: int) -> str:
        """获取地图上指定坐标的显示字符"""
        m = MapManager._map_data(data)
        if m is not None and not m.infinite:
            grid = data.map_grids.get(m.id)
            if grid and 0 <= x < m.width and 0 <= y < m.height:
                return grid[y][x]
            return ' '
        return InfiniteTerrain.get_terrain(x, y)

    @staticmethod
    def entrance_at(data: "GameData"):
        """荒野中玩家脚下是否有地图入口，返回 map_id 或 None"""
        m = MapManager._map_data(data)
        if m is None or not m.infinite:
            return None
        return data.map_entrances.get((data.player_x, data.player_y))

    @staticmethod
    def is_at_leave_point(data: "GameData") -> bool:
        """有限地图中玩家是否站在入口格（可离开）"""
        m = MapManager._map_data(data)
        if m is None or m.infinite:
            return False
        return (data.player_x, data.player_y) == MapManager.entrance_cell(m)

    @staticmethod
    def is_at_town(data: "GameData") -> bool:
        """玩家当前是否在城镇（有限城镇地图内，或荒野中站在城镇入口上）"""
        m = MapManager._map_data(data)
        if m is not None and not m.infinite:
            return m.is_town
        mid = MapManager.entrance_at(data)
        if mid is not None and data.config is not None:
            target = data.config.maps.get(mid)
            return target is not None and target.is_town
        return False

    # ── 移动 ──

    @staticmethod
    def try_move(data: "GameData", dx: int, dy: int, npcs_config: dict):
        """尝试移动，返回新位置遇到的NPC（如果有）；不可通行返回 None"""
        new_x = data.player_x + dx
        new_y = data.player_y + dy

        if not MapManager.is_passable(data, new_x, new_y):
            return None

        data.player_x = new_x
        data.player_y = new_y

        for npc in npcs_config.values():
            if (npc.map_id == data.current_map_id
                    and npc.location_x == new_x
                    and npc.location_y == new_y):
                return npc

        return None

    # ── 视口渲染 ──

    @staticmethod
    def get_viewport_origin(data: "GameData") -> tuple:
        """返回 (origin_x, origin_y, pad_x, pad_y)

        无限地图：视口以玩家为中心，pad 为 0。
        有限地图：视口贴合地图；地图小于视口时居中，pad 为地图在视口中的偏移。
        """
        m = MapManager._map_data(data)
        if m is None or m.infinite:
            return (data.player_x - VIEWPORT_W // 2,
                    data.player_y - VIEWPORT_H // 2, 0, 0)
        if m.width >= VIEWPORT_W:
            origin_x = min(max(data.player_x - VIEWPORT_W // 2, 0),
                           m.width - VIEWPORT_W)
            pad_x = 0
        else:
            origin_x = 0
            pad_x = (VIEWPORT_W - m.width) // 2
        if m.height >= VIEWPORT_H:
            origin_y = min(max(data.player_y - VIEWPORT_H // 2, 0),
                           m.height - VIEWPORT_H)
            pad_y = 0
        else:
            origin_y = 0
            pad_y = (VIEWPORT_H - m.height) // 2
        return (origin_x, origin_y, pad_x, pad_y)

    @staticmethod
    def get_viewport(data: "GameData", npcs_config: dict) -> str:
        """渲染玩家周围的视口文本（纯文本，供 View 层渲染）"""
        m = MapManager._map_data(data)
        origin_x, origin_y, pad_x, pad_y = MapManager.get_viewport_origin(data)
        bounded = m is not None and not m.infinite

        npc_positions = {}
        for npc in npcs_config.values():
            if npc.map_id == data.current_map_id:
                npc_positions[(npc.location_x, npc.location_y)] = npc

        # 荒野中未领取的赏金首位置（显示 B 标记）
        bounty_positions = {}
        if not bounded and data.config is not None:
            for bounty in data.config.bounties.values():
                if (bounty.map_id == data.current_map_id
                        and bounty.id not in data.bounty_claimed):
                    bounty_positions[(bounty.x, bounty.y)] = bounty

        lines = []
        for vy in range(VIEWPORT_H):
            row_chars = []
            for vx in range(VIEWPORT_W):
                wx = origin_x + (vx - pad_x)
                wy = origin_y + (vy - pad_y)
                if bounded and not (0 <= wx < m.width and 0 <= wy < m.height):
                    row_chars.append(' ')  # 有限地图之外的留白
                    continue
                if (wx, wy) == (data.player_x, data.player_y):
                    row_chars.append('P')
                elif (wx, wy) in npc_positions:
                    row_chars.append('N')
                elif not bounded and (wx, wy) in data.map_entrances:
                    row_chars.append('□')  # 荒野中的地图入口
                elif not bounded and (wx, wy) in bounty_positions:
                    row_chars.append('B')  # 荒野中的赏金首
                elif bounded:
                    row_chars.append(data.map_grids[m.id][wy][wx])
                else:
                    row_chars.append(InfiniteTerrain.get_terrain(wx, wy))
            lines.append(''.join(row_chars))

        result = '\n'.join(lines)
        map_name = m.name if m is not None else "未知区域"
        result += f"\n\n位置: ({data.player_x}, {data.player_y})  地图: {map_name}"
        result += f"  时间: {int(data.game_time // 3600)}:{int((data.game_time % 3600) // 60):02d}"

        # 情境提示
        entrance_id = MapManager.entrance_at(data)
        if entrance_id is not None and data.config is not None:
            target = data.config.maps.get(entrance_id)
            if target is not None:
                result += f"\n你来到了{target.name}入口。按空格键进入。"
        elif MapManager.is_at_leave_point(data):
            if data.state == GameState.TOWN:
                result += "\n你身处城镇（在城镇菜单选 4 离开）。"
            else:
                result += "\n你站在出口处。按空格键离开。"
        elif bounded and m.is_town:
            result += "\n你身处城镇。按空格键打开城镇菜单。"

        return result
