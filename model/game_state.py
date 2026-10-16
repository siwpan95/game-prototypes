"""游戏状态枚举与游戏数据聚合类（纯数据）"""
from enum import Enum
from typing import Optional

from .character import Character
from .item import Item
from .vehicle import Vehicle


class GameState(Enum):
    MENU = 0
    WORLD = 1
    BATTLE = 2
    INVENTORY = 3
    DIALOG = 4
    SHOP = 5
    TOWN = 6
    BOUNTY = 7
    GARAGE = 8
    ENGINE_SHOP = 9
    WEAPON_SHOP = 10
    TAXI = 11


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

    # ── 存档序列化 ──

    def to_dict(self) -> dict:
        return {
            "quest_id": self.quest_data.id,
            "kill_count": self.kill_count,
            "collect_count": self.collect_count,
            "explored": self.explored,
        }

    @classmethod
    def from_dict(cls, d: dict, config) -> "QuestTrack":
        quest_data = config.get_quest_by_id(d["quest_id"])
        if quest_data is None:
            raise ValueError(f"存档引用了不存在的任务ID: {d['quest_id']}")
        t = cls(quest_data)
        t.kill_count = d.get("kill_count", 0)
        t.collect_count = d.get("collect_count", 0)
        t.explored = d.get("explored", False)
        return t


class QuestManager:
    """任务管理器 — 静态方法，负责任务进度和完成检测

    任务类型与判定语义：
    - kill    ：target_id=敌人ID，击杀 target_count 只后完成
    - collect ：target_id=物品ID，获得 target_count 个后完成（购买/掉落均计入）
    - explore ：target_id=地图ID，进入该地图后完成（target_count>1 需重复到访）
    """

    @staticmethod
    def track_kill(data: "GameData", enemy_id: int):
        """追踪击杀"""
        for track in list(data.quest_progress):
            q = track.quest_data
            if q.type == "kill" and q.target_id == enemy_id:
                track.kill_count += 1
                if track.kill_count >= q.target_count:
                    QuestManager._complete(data, track)

    @staticmethod
    def track_collect(data: "GameData", item_id: int, count: int = 1):
        """追踪收集（获得物品时调用）"""
        for track in list(data.quest_progress):
            q = track.quest_data
            if q.type == "collect" and q.target_id == item_id:
                track.collect_count += count
                if track.collect_count >= q.target_count:
                    QuestManager._complete(data, track)

    @staticmethod
    def track_explore_map(data: "GameData", map_id: int):
        """追踪地图到访（进入某地图时调用；collect_count 复用到访计数）"""
        for track in list(data.quest_progress):
            q = track.quest_data
            if q.type == "explore" and q.target_id == map_id:
                track.collect_count += 1
                if track.collect_count >= q.target_count:
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

        # 地图系统
        self.town_positions = []    # 荒野中的地图入口坐标列表 [(x, y), ...]
        self.map_entrances = {}     # 荒野入口坐标 → map_id
        self.map_grids = {}         # 有限地图网格缓存 map_id -> list[list[str]]
        self.return_x = 10          # 从有限地图返回荒野时的落脚点
        self.return_y = 10

        # 集合数据
        self.inventory = []  # list[Item]
        self.vehicles = []  # list[Vehicle]
        self.active_quests = []  # list[QuestData]
        self.completed_quests = []  # list[QuestData]
        self.quest_progress = []  # list[QuestTrack]

        # 赏金首运行时状态（不持久化 current_bounty_id：战斗中禁止保存）
        self.bounty_accepted = set()   # 已接取
        self.bounty_defeated = set()   # 已击杀待领
        self.bounty_claimed = set()    # 赏金已入账
        self.current_bounty_id = None  # 当前赏金首战斗（临时）
        # 迷彩条剩余隐身步数（0 = 未生效）
        self.camouflage_steps = 0

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

    # ── 存档序列化 ──

    def to_dict(self) -> dict:
        """序列化为可 JSON 存档的字典

        注意：战斗中/对话中的临时对象（current_enemy/current_npc/current_shop）
        不持久化，VM 层会阻止在战斗中保存。
        """
        current_vehicle_index = -1
        if self.current_vehicle is not None:
            try:
                current_vehicle_index = self.vehicles.index(self.current_vehicle)
            except ValueError:
                current_vehicle_index = -1
        return {
            "schema_version": 1,
            "state": self.state.name,
            "current_map_id": self.current_map_id,
            "player_x": self.player_x,
            "player_y": self.player_y,
            "return_x": self.return_x,
            "return_y": self.return_y,
            "game_time": self.game_time,
            "gold": self.gold,
            "player": self.player.to_dict() if self.player else None,
            "inventory": [item.to_dict() for item in self.inventory],
            "vehicles": [v.to_dict() for v in self.vehicles],
            "current_vehicle_index": current_vehicle_index,
            "active_quests": [q.id for q in self.active_quests],
            "completed_quests": [q.id for q in self.completed_quests],
            "quest_progress": [t.to_dict() for t in self.quest_progress],
            "bounty_accepted": sorted(self.bounty_accepted),
            "bounty_defeated": sorted(self.bounty_defeated),
            "bounty_claimed": sorted(self.bounty_claimed),
            "camouflage_steps": self.camouflage_steps,
        }

    @classmethod
    def from_dict(cls, d: dict, config) -> "GameData":
        """从存档字典重建游戏数据；config 为 ConfigLoader"""
        gd = cls()
        gd.config = config
        gd.current_map_id = d.get("current_map_id", 1)
        gd.player_x = d.get("player_x", 10)
        gd.player_y = d.get("player_y", 10)
        gd.return_x = d.get("return_x", 10)
        gd.return_y = d.get("return_y", 10)
        gd.game_time = d.get("game_time", 0.0)
        gd.gold = d.get("gold", 0)

        player_d = d.get("player")
        if player_d:
            gd.player = Character.from_dict(player_d, config)

        gd.inventory = [Item.from_dict(x, config) for x in d.get("inventory", [])]
        gd.vehicles = [Vehicle.from_dict(x, config) for x in d.get("vehicles", [])]

        idx = d.get("current_vehicle_index", -1)
        if isinstance(idx, int) and 0 <= idx < len(gd.vehicles):
            gd.current_vehicle = gd.vehicles[idx]
            if gd.player:
                gd.player.vehicle = gd.current_vehicle

        for quest_id in d.get("active_quests", []):
            quest = config.get_quest_by_id(quest_id)
            if quest is not None:
                gd.active_quests.append(quest)
        for quest_id in d.get("completed_quests", []):
            quest = config.get_quest_by_id(quest_id)
            if quest is not None:
                gd.completed_quests.append(quest)
        for track_d in d.get("quest_progress", []):
            gd.quest_progress.append(QuestTrack.from_dict(track_d, config))

        gd.bounty_accepted = set(d.get("bounty_accepted", []))
        gd.bounty_defeated = set(d.get("bounty_defeated", []))
        gd.bounty_claimed = set(d.get("bounty_claimed", []))
        gd.camouflage_steps = d.get("camouflage_steps", 0)

        # 状态校正：依赖未持久化临时对象的状态一律回退到 WORLD
        try:
            state = GameState[d.get("state", "WORLD")]
        except KeyError:
            state = GameState.WORLD
        if state in (GameState.DIALOG, GameState.SHOP, GameState.BATTLE):
            state = GameState.WORLD
        gd.state = state
        return gd

