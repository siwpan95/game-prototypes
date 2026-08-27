# save_load.py
# 存档 / 读档（E4）—— GameSession 序列化
#
# GameSession 持有一次游玩会话的全部可持久化状态：
#   - character  角色（Sequence，经 to_dict/from_dict 重建）
#   - inventory  魔药材料库存（E1）
#   - event_log  事件日志
#   - old_one_info  旧日晋升构成摘要
#   - view_mode  当前视图
#   - factions   阵营声望（E7）
#
# 存档文件为 JSON，落在项目根 saves/ 下，支持多槽位（slot 名即文件名）。
# 纯逻辑模块，不依赖 tkinter，可被无头单测直接覆盖。
import os
import json
import datetime

SAVES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "saves")


def _ensure_dir():
    if not os.path.isdir(SAVES_DIR):
        os.makedirs(SAVES_DIR, exist_ok=True)
    return SAVES_DIR


def slot_path(slot: str) -> str:
    """槽位名 -> 存档文件路径（只接受安全字符，避免路径穿越）"""
    safe = "".join(c for c in slot if c.isalnum() or c in "-_")
    if not safe:
        safe = "quicksave"
    return os.path.join(_ensure_dir(), f"{safe}.json")


def list_slots() -> list:
    """返回所有存档槽位名（不含扩展名），按修改时间倒序"""
    _ensure_dir()
    out = []
    for fn in os.listdir(SAVES_DIR):
        if fn.endswith(".json"):
            out.append(fn[:-5])
    out.sort(key=lambda s: os.path.getmtime(slot_path(s)), reverse=True)
    return out


class GameSession:
    """一次游玩会话的可序列化封装。

    用法：
        sess = GameSession.from_state(gui.state)   # 从 GUIState 收集
        sess.save("quicksave")                      # 落盘
        sess2 = GameSession.load("quicksave")       # 读盘
        sess2.apply_to_state(gui.state)             # 还原到 GUIState

    P2（E8/E9/E11）起，会话还承载：
        - rival_system   AI 对手系统（E8）
        - achievements   成就系统（E9）
        - codex          图鉴系统（E9）
    这些字段同样随会话序列化，使 CLI 与 GUI 共用同一引擎（GameSession）。
    """

    def __init__(self, character=None, inventory=None, event_log=None,
                 old_one_info=None, view_mode="character", factions=None,
                 rival_system=None, achievements=None, codex=None):
        from inventory import Inventory
        self.character = character
        self.inventory = inventory if inventory is not None else Inventory()
        self.event_log = list(event_log) if event_log else []
        self.old_one_info = old_one_info
        self.view_mode = view_mode or "character"
        self.factions = dict(factions) if factions else {}
        # ── P2 新增 ──
        self.rival_system = rival_system
        self.achievements = achievements
        self.codex = codex

    # ─── 从运行时状态收集 ───
    @classmethod
    def from_state(cls, state) -> "GameSession":
        ch = state.character
        rs = getattr(state, "rival_system", None)
        ach = getattr(state, "achievements", None)
        codex = getattr(state, "codex", None)
        return cls(
            character=ch.to_dict() if ch else None,
            inventory=state.inventory.to_dict(),
            event_log=list(state.event_log),
            old_one_info=getattr(state, "old_one_info", None),
            view_mode=getattr(state, "view_mode", "character"),
            factions=dict(getattr(state, "factions", {}) or {}),
            rival_system=rs.to_dict() if rs is not None else None,
            achievements=ach.to_dict() if ach is not None else None,
            codex=codex.to_dict() if codex is not None else None,
        )

    # ─── 还原到运行时状态 ───
    def apply_to_state(self, state):
        from sequences import Sequence
        from rivals import RivalSystem
        from achievements import AchievementSystem, CodexSystem
        state.character = Sequence.from_dict(self.character) if self.character else None
        state.inventory = type(state.inventory).from_dict(self.inventory)
        state.event_log = list(self.event_log)
        state.old_one_info = self.old_one_info
        state.view_mode = self.view_mode
        state.factions = dict(self.factions)
        # ── P2 新增 ──
        state.rival_system = (RivalSystem.from_dict(self.rival_system)
                              if self.rival_system is not None else None)
        state.achievements = (AchievementSystem.from_dict(self.achievements)
                              if self.achievements is not None else AchievementSystem())
        state.codex = (CodexSystem.from_dict(self.codex)
                       if self.codex is not None else CodexSystem())
        return state

    # ─── 序列化 ───
    def to_dict(self) -> dict:
        return {
            "version": 2,
            "saved_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "character": self.character,
            "inventory": self.inventory,
            "event_log": self.event_log,
            "old_one_info": self.old_one_info,
            "view_mode": self.view_mode,
            "factions": self.factions,
            # ── P2 新增 ──
            "rival_system": self.rival_system,
            "achievements": self.achievements,
            "codex": self.codex,
        }

    def save(self, slot: str = "quicksave") -> str:
        """保存到指定槽位，返回文件路径"""
        path = slot_path(slot)
        payload = self.to_dict()
        # 读档时还原 character 需要 pathways_data，存档里直接存角色字典
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        return path

    @classmethod
    def load(cls, slot: str = "quicksave") -> "GameSession":
        path = slot_path(slot)
        if not os.path.exists(path):
            raise FileNotFoundError(f"存档槽位不存在：{slot}")
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        return cls._from_dict_payload(d)

    @classmethod
    def from_dict(cls, d: dict) -> "GameSession":
        """从字典（而非文件）重建会话 —— 供 CLI↔GUI 共享核心做内存级 roundtrip。"""
        return cls._from_dict_payload(d)

    @classmethod
    def _from_dict_payload(cls, d: dict) -> "GameSession":
        return cls(
            character=d.get("character"),
            inventory=d.get("inventory", {}),
            event_log=d.get("event_log", []),
            old_one_info=d.get("old_one_info"),
            view_mode=d.get("view_mode", "character"),
            factions=d.get("factions", {}),
            # ── P2 新增 ──
            rival_system=d.get("rival_system"),
            achievements=d.get("achievements"),
            codex=d.get("codex"),
        )

    def __repr__(self):
        name = self.character.get("SEQUENCE_NAME") if isinstance(self.character, dict) else None
        pk = self.character.get("pathway_key") if isinstance(self.character, dict) else None
        return f"<GameSession {pk}/{name} 日志{len(self.event_log)}条 阵营{len(self.factions)}>"
