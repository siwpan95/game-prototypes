# -*- coding: utf-8 -*-
"""地牢服务 - 地牢生成、房间推进"""
from __future__ import annotations
import random
from typing import List, Dict, Optional
from ..models.dungeon import Dungeon, Room, RoomContent


# 地牢名称词库
DUNGEON_PREFIXES = [
    "暗影", "遗忘", "诅咒", "深渊", "血染", "黑暗", "幽暗", "混沌",
    "烈焰", "冰霜", "雷霆", "毒雾", "死寂", "破碎", "荒芜", "腐化",
]
DUNGEON_TYPES = [
    "洞穴", "神殿", "矿坑", "堡垒", "地牢", "陵墓", "高塔", "深渊",
    "墓穴", "石窟", "要塞", "地窖", "迷宫", "废墟", "巢穴", "回廊",
]

# 地牢前缀 → 房间环境标签映射
PREFIX_ENVIRONMENT = {
    "烈焰": "高温",  # 火焰伤害+20%
    "冰霜": "严寒",  # 冰霜减速增强
    "雷霆": "雷暴",  # 闪电伤害增强
    "毒雾": "毒雾",  # 毒素效果增强
    "死寂": "死灵",  # 亡灵回血
    "腐化": "死灵",  # 亡灵回血
    "暗影": "暗影",  # 闪避增强
    "黑暗": "暗影",
    "幽暗": "暗影",
    "诅咒": "诅咒",  # 玩家属性减弱
    "深渊": "混沌",  # 随机增强
    "混沌": "混沌",
    "血染": "血域",  # 吸血增强
    "破碎": "破碎",  # 防御降低
    "荒芜": "荒芜",  # 回复减弱
    "遗忘": "遗忘",  # 暴击率波动
}

# 环境标签 → 战斗修正
ENVIRONMENT_EFFECTS = {
    "高温":  {"fire_bonus": 0.20, "ice_penalty": -0.20},
    "严寒":  {"ice_bonus": 0.20, "fire_penalty": -0.20},
    "雷暴":  {"shock_bonus": 1, "player_slow": -0.10},
    "毒雾":  {"poison_bonus": 3, "player_poison": 1},
    "死灵":  {"undead_regen": 5, "holy_bonus": 0.15},
    "暗影":  {"evasion_bonus": 0.08, "light_penalty": -0.10},
    "诅咒":  {"player_hp_down": -0.15, "player_dmg_down": -0.10},
    "混沌":  {"random_bonus": 0.10},  # 随机一种增强
    "血域":  {"life_steal_bonus": 0.08},
    "破碎":  {"defense_down": -0.20},
    "荒芜":  {"regen_down": -5},
    "遗忘":  {"crit_fluctuation": 0.10},
}


class DungeonService:
    """地牢生成与管理服务"""

    def __init__(self, data_service, world_service, difficulty_service=None):
        self.data_service = data_service
        self.world_service = world_service
        self.difficulty_service = difficulty_service  # DDA 动态难度服务
        self.dungeons: Dict[str, List[Dungeon]] = {}  # region_id → [Dungeon, ...]

    def generate_dungeons_for_region(self, region: dict, party=None) -> List[Dungeon]:
        """为指定区域生成地牢（2-4个）"""
        region_id = region["region_id"]
        danger = region.get("danger_level", 1)
        num_dungeons = random.randint(2, 4)

        dungeons = []
        for i in range(num_dungeons):
            prefix = random.choice(DUNGEON_PREFIXES)
            dtype = random.choice(DUNGEON_TYPES)
            name = f"{prefix}{dtype}"

            # 房间数: 5 + 危险等级 * 2
            num_rooms = 5 + danger * 2
            env_tag = PREFIX_ENVIRONMENT.get(prefix, "")
            rooms = self._generate_rooms(num_rooms, danger, env_tag, party)

            dungeon = Dungeon(
                dungeon_id=f"{region_id}_d{i:02d}",
                name=name,
                region_id=region_id,
                danger_level=danger,
                rooms=rooms,
            )
            dungeons.append(dungeon)

        self.dungeons[region_id] = dungeons
        return dungeons

    def _generate_rooms(self, num_rooms: int, danger: int, env_tag: str = "",
                        party=None) -> List[Room]:
        """生成地牢房间"""
        rooms = []
        for idx in range(num_rooms):
            # 房间内容随机
            roll = random.random()
            if roll < 0.25:
                content = RoomContent.CHEST
            elif roll < 0.40:
                content = RoomContent.POTION_RACK
            elif roll < 0.50 and idx > 0:  # 第一个房间不生成精英房
                content = RoomContent.ELITE
            else:
                content = RoomContent.ENEMY

            # 生成房间敌人（ENEMY/ELITE 才生成，CHEST/POTION 为空）
            enemies = []
            if content in (RoomContent.ENEMY, RoomContent.ELITE):
                min_e, max_e = (3, 6) if content == RoomContent.ELITE else (1, 3)
                enemies = self._spawn_enemies(danger, min_e, max_e, party)

            # ★ 房间环境标签（战斗修正）
            rooms.append(Room(
                room_index=idx, content=content, enemies=enemies,
                environment=env_tag,
            ))

        return rooms

    def _spawn_enemies(self, danger: int, min_count: int, max_count: int,
                       party=None) -> List[dict]:
        """生成房间怪物

        怪物等级 = 玩家等级（由 difficulty_service 在 scale_enemy_template 中处理），
        不再按固定等级范围筛选模板。
        """
        from ..services.combat_service import CombatService
        cs = CombatService(self.data_service, self.difficulty_service)

        # 直接取所有敌人模板（等级缩放由 DDA 服务统一处理）
        templates = self.data_service.get_enemy_templates()
        if not templates:
            templates = self.data_service.get_enemy_templates()

        count = random.randint(min_count, max_count)
        enemies = []
        for _ in range(count):
            tpl = random.choice(templates)
            enemy = cs.create_enemy_from_template(tpl, party)
            enemies.append(enemy)
        return enemies

    def get_region_dungeons(self, region_id: str) -> List[Dungeon]:
        """获取区域的地牢列表（不存在则生成）"""
        if region_id not in self.dungeons:
            region = self.world_service.get_region_by_id(region_id)
            if region:
                self.generate_dungeons_for_region(region)
        return self.dungeons.get(region_id, [])

    def get_current_dungeon(self, region_id: str, dungeon_idx: int = 0) -> Optional[Dungeon]:
        """获取当前区域当前地牢"""
        dungeons = self.get_region_dungeons(region_id)
        if dungeons and 0 <= dungeon_idx < len(dungeons):
            return dungeons[dungeon_idx]
        return None

    def advance_room(self, dungeon: Dungeon) -> Optional[Room]:
        """推进到下一个房间，返回新房间"""
        if dungeon.current_room:
            dungeon.current_room.cleared = True

        dungeon.current_room_idx += 1
        if dungeon.current_room_idx >= dungeon.total_rooms:
            dungeon.cleared = True
            return None

        return dungeon.current_room

    def check_region_cleared(self, region_id: str) -> bool:
        """检查区域所有地牢是否清空"""
        dungeons = self.get_region_dungeons(region_id)
        if not dungeons:
            return False
        return all(d.cleared for d in dungeons)

    def check_infest(self, region_id: str, party=None) -> Optional[Dungeon]:
        """
        入侵/滋生检查：
        如果区域没有可探索的地牢（全清空或无未清空房间），
        随机选一个已清空但未守护的地牢重新滋生怪物。
        返回被入侵的地牢，或 None 表示无需入侵。
        """
        dungeons = self.get_region_dungeons(region_id)
        if not dungeons:
            return None

        # 检查是否有未完成的地牢
        has_uncleared = any(not d.cleared for d in dungeons)
        if has_uncleared:
            return None

        # 所有地牢都已清空：找一个未守护的进行入侵
        unsecured = [d for d in dungeons if not d.secured and not d.is_farm]
        if not unsecured:
            return None

        target = random.choice(unsecured)
        # 随机重新滋生：保留原有房间数，重新生成怪物
        danger = target.danger_level
        for room in target.rooms:
            content = room.content
            if content in (RoomContent.ENEMY, RoomContent.ELITE):
                if content == RoomContent.ENEMY:
                    room.enemies = self._spawn_enemies(danger, 1, 3, party)
                else:
                    room.enemies = self._spawn_enemies(danger, 3, 6, party)
            room.cleared = False
            room.chest_opened = False
        target.cleared = False
        target.current_room_idx = 0
        return target

    def check_region_has_uncleared(self, region_id: str) -> bool:
        """检查区域是否有未清空地牢"""
        dungeons = self.get_region_dungeons(region_id)
        if not dungeons:
            return False
        return any(not d.cleared for d in dungeons)

    def get_first_uncleared_dungeon(self, region_id: str) -> Optional[Dungeon]:
        """获取区域第一个未清空地牢"""
        dungeons = self.get_region_dungeons(region_id)
        for d in dungeons:
            if not d.cleared:
                return d
        return None
