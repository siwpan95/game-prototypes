"""游戏状态枚举与游戏数据聚合类（纯数据）"""
from enum import Enum
from typing import Optional


class GameState(Enum):
    MENU = 0
    WORLD = 1
    BATTLE = 2
    INVENTORY = 3
    DIALOG = 4
    SHOP = 5
    TOWN = 6


class Direction(Enum):
    UP = 0
    DOWN = 1
    LEFT = 2
    RIGHT = 3


class QuestTrack:
    """任务进度追踪"""
    __slots__ = ("quest_data", "kill_count", "collect_count", "explored")

    def __init__(self, quest_data: "QuestData"):
        self.quest_data = quest_data
        self.kill_count = 0
        self.collect_count = 0
        self.explored = False


class QuestManager:
    """任务管理器 — 静态方法，负责任务进度和完成检测"""

    @staticmethod
    def track_kill(data: "GameData", enemy_id: int):
        """追踪击杀（killed enemy）"""
        for track in data.quest_progress:
            q = track.quest_data
            if q.type == "kill" and q.target_id == enemy_id:
                track.kill_count += 1
                if track.kill_count >= q.target_id:
                    QuestManager._complete(data, track)

    @staticmethod
    def track_explore(data: "GameData", world_x: int, world_y: int):
        """追踪探索（到达指定坐标区域）"""
        for track in data.quest_progress:
            q = track.quest_data
            if q.type == "explore" and not track.explored:
                # target_id 编码为坐标: target_id = x * 10000 + y
                tx = q.target_id // 10000
                ty = q.target_id % 10000
                if abs(world_x - tx) <= 3 and abs(world_y - ty) <= 3:
                    track.explored = True
                    QuestManager._complete(data, track)

    @staticmethod
    def track_collect(data: "GameData", item_id: int):
        """追踪收集（获得指定物品）"""
        for track in data.quest_progress:
            q = track.quest_data
            if q.type == "collect" and q.target_id == item_id:
                track.collect_count += 1
                if track.collect_count >= 1:
                    QuestManager._complete(data, track)

    @staticmethod
    def _complete(data: "GameData", track: QuestTrack):
        """完成任务，发放奖励"""
        q = track.quest_data
        data.quest_progress.remove(track)
        data.completed_quests.append(q)

        data.player.gain_exp(q.reward_exp)
        data.gold += q.reward_gold
        data.add_log(f"任务完成: {q.name}！获得{q.reward_exp}经验和{q.reward_gold}金币！")

        # 发放任务奖励物品
        if q.reward_item_id > 0 and data.config:
            item_data = data.config.get_item_by_id(q.reward_item_id)
            if item_data:
                from .item import Item
                data.inventory.append(Item(item_data))
                data.add_log(f"获得物品: {item_data.name}！")


class GameData:
    """游戏运行时数据聚合，纯数据无UI逻辑"""

    def __init__(self):
        self.state = GameState.MENU
        self.player = None  # Character，由外部注入
        self.current_enemy = None  # Enemy
        self.current_npc = None  # NPC
        self.current_shop = None  # ShopData，当前商店
        self.current_map_id = 1
        self.player_x = 10
        self.player_y = 10
        self.game_time = 0.0
        self.gold = 500
        self.current_vehicle = None  # Vehicle
        self.config = None  # ConfigLoader 引用（由外部注入）

        # 当前地图（二维列表）
        self.current_map = []
        self.town_positions = []

        # 集合数据
        self.inventory = []  # list[Item]
        self.vehicles = []  # list[Vehicle]
        self.active_quests = []  # list[QuestData]
        self.completed_quests = []  # list[QuestData]
        self.quest_progress = []  # list[QuestTrack]

        # 日志
        self.log_messages = []  # list[str]

    def add_log(self, message: str):
        timestamp = f"[{int(self.game_time // 60):02d}:{int(self.game_time % 60):02d}] "
        self.log_messages.append(timestamp + message)
        if len(self.log_messages) > 50:
            self.log_messages.pop(0)

    def get_recent_logs(self, count: int = 5) -> list:
        return self.log_messages[-count:]

    def is_in_town(self) -> bool:
        return (self.player_x, self.player_y) in self.town_positions

