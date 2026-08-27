"""地图管理器（纯业务逻辑，零UI依赖）— 支持伪无限地图"""
from .infinite_map import InfiniteTerrain, TownGenerator


# 视口大小（字符单位）
VIEWPORT_W = 40
VIEWPORT_H = 22


class MapManager:
    """地图生成、碰撞检测与视口渲染"""

    @staticmethod
    def create_map(data: "GameData", maps_config: dict, npcs_config: dict):
        """初始化无限地图 — 不再创建固定大小的二维数组"""
        # 无限地图不需要预生成整个地图，地形按需计算
        data.current_map = []  # 不再使用二维列表存储

        # 从配置加载 NPC 城镇位置
        town_positions = []
        for npc in npcs_config.values():
            if npc.map_id == data.current_map_id and npc.role in ['镇长', '向导']:
                town_positions.append((npc.location_x, npc.location_y))

        # 如果没有配置城镇，使用程序化生成
        data.town_positions = town_positions

    @staticmethod
    def can_move_to(data: "GameData", x: int, y: int) -> bool:
        """检查是否能移动到指定坐标 — 无限地图无边界限制"""
        return InfiniteTerrain.is_passable(x, y)

    @staticmethod
    def try_move(data: "GameData", dx: int, dy: int, npcs_config: dict) -> "NPCData | None":
        """尝试移动，返回新位置遇到的NPC（如果有）"""
        new_x = data.player_x + dx
        new_y = data.player_y + dy

        if not MapManager.can_move_to(data, new_x, new_y):
            return None

        data.player_x = new_x
        data.player_y = new_y

        # 检查配置中的 NPC
        for npc in npcs_config.values():
            if (npc.map_id == data.current_map_id
                    and npc.location_x == new_x
                    and npc.location_y == new_y):
                return npc

        return None

    @staticmethod
    def get_map_char(data: "GameData", x: int, y: int) -> str:
        """获取地图上指定坐标的显示字符（不再是数组查找，而是计算生成）"""
        return InfiniteTerrain.get_terrain(x, y)

    @staticmethod
    def get_viewport(data: "GameData", npcs_config: dict) -> str:
        """渲染玩家周围的视口文本

        视口以玩家为中心，显示 VIEWPORT_W × VIEWPORT_H 的区域。
        返回纯文本字符串，供 View 层渲染。
        """
        px, py = data.player_x, data.player_y
        half_w = VIEWPORT_W // 2
        half_h = VIEWPORT_H // 2

        start_x = px - half_w
        start_y = py - half_h

        # 构建 NPC 位置字典
        npc_positions = {}
        for npc in npcs_config.values():
            if npc.map_id == data.current_map_id:
                npc_positions[(npc.location_x, npc.location_y)] = npc

        # 查找视口内的程序化城镇
        town_set = set(data.town_positions)
        generated_towns = TownGenerator.find_towns_in_rect(
            start_x, start_y,
            start_x + VIEWPORT_W - 1,
            start_y + VIEWPORT_H - 1
        )
        town_set.update(generated_towns)

        lines = []
        for vy in range(start_y, start_y + VIEWPORT_H):
            row_chars = []
            for vx in range(start_x, start_x + VIEWPORT_W):
                if (vx, vy) == (px, py):
                    row_chars.append('P')
                elif (vx, vy) in npc_positions:
                    row_chars.append('N')
                elif (vx, vy) in town_set:
                    row_chars.append('□')
                else:
                    row_chars.append(InfiniteTerrain.get_terrain(vx, vy))
            lines.append(''.join(row_chars))

        result = '\n'.join(lines)
        result += f"\n\n位置: ({px}, {py})"
        result += f"  时间: {int(data.game_time // 3600)}:{int((data.game_time % 3600) // 60):02d}"

        # 检查是否在城镇位置
        if MapManager.is_at_town(data):
            result += "\n你来到了一个城镇。按空格键进入。"

        return result

    @staticmethod
    def is_at_town(data: "GameData") -> bool:
        """判断玩家当前是否在城镇位置"""
        px, py = data.player_x, data.player_y

        # 配置中的城镇
        if (px, py) in data.town_positions:
            return True

        # 程序化生成的城镇
        if TownGenerator.is_town_at(px, py):
            return True

        return False
