"""
Mod/DLC 加载系统 — 发现、验证、加载 Mod 内容。
支持：地图切换、传送门、数据驱动机关、跨 Mod 卡牌/记忆查找。
"""
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

from core.paths import ROOT
from core.ecs import Entity
from components.grid_position import GridPosition
from components.memory import Memory
from components.interactable import Interactable
from components.card_collectible import CardCollectible


# ---------------------------------------------------------------
# 数据类 — Mod 清单解析结果
# ---------------------------------------------------------------

@dataclass
class PortalDef:
    """传送门定义。玩家走到该位置时触发地图切换。"""
    col: int
    row: int
    char: str              # 地图上显示的字符（如 '▼', '▲', '→'）
    target_mod: Optional[str]  # None = base game
    target_map: str
    target_col: int
    target_row: int


@dataclass
class MechanismAction:
    """数据驱动机关动作。"""
    type: str      # replace_at | replace_region | replace_area
    params: dict   # 动作参数


@dataclass
class MechanismDef:
    """数据驱动机关定义。"""
    mech_id: str
    trigger_type: str   # CARD_COLLECTED | MEMORY_TRIGGERED
    trigger_id: str
    desc: str
    actions: list


@dataclass
class MapDef:
    """单张地图的完整定义。"""
    map_id: str
    name: str
    map_file: str              # 相对 mod 根目录
    player_start: tuple         # (col, row)
    objects_file: str
    cards: dict                 # card_id → [col, row] | None (None=不在本图)
    portals: list               # list[PortalDef]
    mechanisms: list            # list[MechanismDef]


@dataclass
class ModManifest:
    """Mod 清单 — 一个 Mod 可包含多张地图。"""
    mod_id: str
    name: str
    version: str
    description: str
    root_dir: Path
    maps: dict                  # map_id → MapDef

    def get_map(self, map_id: str) -> Optional[MapDef]:
        return self.maps.get(map_id)


# ---------------------------------------------------------------
# ModManager — 发现并管理所有 Mod
# ---------------------------------------------------------------

class ModManager:
    """扫描 mods/ 目录，加载所有有效 Mod 的清单。"""

    def __init__(self, mods_root: Path = None):
        if mods_root is None:
            mods_root = ROOT / "mods"
        self.mods_root = mods_root
        self.mods: dict[str, ModManifest] = {}
        self._discover()

    def _discover(self):
        """扫描 mods/ 下每个子目录的 mod.json；同时加载 base_mod.json。"""
        # ── 加载 Base Mod（位于 data/base_mod.json，root_dir = ROOT）──
        base_manifest = ROOT / "data" / "base_mod.json"
        if base_manifest.exists():
            try:
                mod = self._load_mod(ROOT, base_manifest)
                self.mods[mod.mod_id] = mod
            except Exception as e:
                print(f"[ModManager] 跳过 base: {e}")

        # ── 扫描 mods/ 目录 ──
        if not self.mods_root.exists():
            return
        for mod_dir in sorted(self.mods_root.iterdir()):
            if not mod_dir.is_dir():
                continue
            mp = mod_dir / "mod.json"
            if not mp.exists():
                continue
            try:
                mod = self._load_mod(mod_dir, mp)
                self.mods[mod.mod_id] = mod
            except Exception as e:
                print(f"[ModManager] 跳过 {mod_dir.name}: {e}")

    def _load_mod(self, mod_dir: Path, manifest_path: Path) -> ModManifest:
        with open(manifest_path, encoding="utf-8") as f:
            data = json.load(f)

        maps = {}
        for mdef in data.get("maps", []):
            # 传送门
            portals = []
            for p in mdef.get("portals", []):
                portals.append(PortalDef(
                    col=p["col"], row=p["row"],
                    char=p.get("char", "▣"),
                    target_mod=p.get("target_mod"),
                    target_map=p["target_map"],
                    target_col=p["target_col"],
                    target_row=p["target_row"],
                ))

            # 机关
            mechanisms = []
            for mech in mdef.get("mechanisms", []):
                actions = []
                for a in mech.get("actions", []):
                    actions.append(MechanismAction(
                        type=a["type"],
                        params={k: v for k, v in a.items() if k != "type"},
                    ))
                mechanisms.append(MechanismDef(
                    mech_id=mech["id"],
                    trigger_type=mech["trigger_type"],
                    trigger_id=mech["trigger_id"],
                    desc=mech["desc"],
                    actions=actions,
                ))

            maps[mdef["map_id"]] = MapDef(
                map_id=mdef["map_id"],
                name=mdef["name"],
                map_file=mdef["map_file"],
                player_start=(mdef["player_start"]["col"], mdef["player_start"]["row"]),
                objects_file=mdef["objects_file"],
                cards=mdef.get("cards", {}),
                portals=portals,
                mechanisms=mechanisms,
            )

        return ModManifest(
            mod_id=data["mod_id"],
            name=data["name"],
            version=data["version"],
            description=data.get("description", ""),
            root_dir=mod_dir,
            maps=maps,
        )

    def get_mod(self, mod_id: str | None) -> Optional[ModManifest]:
        """获取 Mod 清单。mod_id=None 返回 base。"""
        if mod_id is None:
            return self.mods.get("base")
        return self.mods.get(mod_id)

    def get_map(self, mod_id: str | None, map_id: str) -> Optional[tuple[ModManifest, MapDef]]:
        """解析地图引用，返回 (ModManifest, MapDef) 或 None。"""
        mod = self.get_mod(mod_id)
        if mod is None:
            return None
        mdef = mod.get_map(map_id)
        if mdef is None:
            return None
        return (mod, mdef)

    def all_card_dirs(self) -> list[Path]:
        """返回所有已知卡牌 JSON 目录（base 优先）。"""
        dirs = [ROOT / "data" / "cards"]
        for mod in self.mods.values():
            if mod.mod_id == "base":
                continue
            cd = mod.root_dir / "cards"
            if cd.exists():
                dirs.append(cd)
        return dirs

    def all_memory_paths(self) -> list[Path]:
        """返回所有已知记忆 JSON 目录（base 优先）。"""
        dirs = [ROOT / "data" / "memories"]
        for mod in self.mods.values():
            if mod.mod_id == "base":
                continue
            md = mod.root_dir / "memories"
            if md.exists():
                dirs.append(md)
        return dirs


# ---------------------------------------------------------------
# MapManager — 管理当前活跃地图与切换逻辑
# ---------------------------------------------------------------

class MapManager:
    """地图切换管理器。

    职责：
    - 加载初始地图（base game 的 mansion）
    - 响应传送门触发，切换地图
    - 清除/重建非玩家实体
    - 注入 Portal 实体到世界
    """

    def __init__(self, mod_manager: ModManager, world, map_data, event_bus,
                 card_sys=None, mech_sys=None, ui_sys=None):
        self.mod_mgr = mod_manager
        self.world = world
        self.map_data = map_data
        self.bus = event_bus
        self.card_sys = card_sys
        self.mech_sys = mech_sys
        self.ui_sys = ui_sys

        # 当前状态
        self.current_mod_id: Optional[str] = None
        self.current_map_id: str = ""
        self.current_mod: Optional[ModManifest] = None
        self.current_map: Optional[MapDef] = None

        # 订阅地图切换事件
        self.bus.subscribe("MAP_TRANSITION", self._on_transition)

    def load_initial_map(self, mod_id: str | None = None, map_id: str = "mansion"):
        """加载初始地图（首次进入游戏）。"""
        result = self.mod_mgr.get_map(mod_id, map_id)
        if result is None:
            raise RuntimeError(f"初始地图不存在: mod={mod_id} map={map_id}")
        mod, mdef = result

        # 加载地图网格
        map_path = mod.root_dir / mdef.map_file
        self.map_data.reload(map_path)

        # 创建实体
        self._load_map_entities(mod, mdef)

        # 设置玩家位置
        self._place_player(mdef.player_start[0], mdef.player_start[1])

        # 设置机关
        if self.mech_sys:
            self.mech_sys.load_mechanisms(mod, mdef)

        # 记录当前状态
        self.current_mod_id = mod_id
        self.current_map_id = map_id
        self.current_mod = mod
        self.current_map = mdef

        # 加载 Mod 卡牌定义
        if self.card_sys and mod_id and mod_id != "base":
            self.card_sys.load_mod_cards(mod)

    def _on_transition(self, data):
        """处理 MAP_TRANSITION 事件。"""
        if data is None:
            return
        target_mod = data.get("target_mod")
        target_map = data.get("target_map")
        target_col = data.get("target_col", 0)
        target_row = data.get("target_row", 0)
        self.switch_map(target_mod, target_map, target_col, target_row)

    def switch_map(self, mod_id: str | None, map_id: str, entry_col: int, entry_row: int):
        """切换到指定地图。"""
        result = self.mod_mgr.get_map(mod_id, map_id)
        if result is None:
            print(f"[MapManager] 地图不存在: mod={mod_id} map={map_id}")
            return
        mod, mdef = result

        # 清除当前地图的非玩家实体
        self._clear_non_player_entities()

        # 加载新地图网格
        map_path = mod.root_dir / mdef.map_file
        self.map_data.reload(map_path)

        # 创建新地图实体
        self._load_map_entities(mod, mdef)

        # 设置玩家位置
        self._place_player(entry_col, entry_row)

        # 加载新地图的机关
        if self.mech_sys:
            self.mech_sys.load_mechanisms(mod, mdef)

        # 更新状态
        self.current_mod_id = mod_id
        self.current_map_id = map_id
        self.current_mod = mod
        self.current_map = mdef

        # 首次进入某个 Mod 时加载其卡牌定义
        if self.card_sys and mod_id and mod_id != "base":
            self.card_sys.load_mod_cards(mod)

        # 通知地图切换完成
        self.bus.emit("MAP_LOADED", {
            "mod_id": mod_id, "map_id": map_id,
            "map_name": mdef.name, "mod_name": mod.name,
        })

    def _clear_non_player_entities(self):
        """移除世界中除 player 外的所有实体。"""
        to_remove = [eid for eid in self.world.entities if eid != "player"]
        for eid in to_remove:
            del self.world.entities[eid]

    def _load_map_entities(self, mod: ModManifest, mdef: MapDef):
        """为指定地图创建所有实体。"""
        # ── 可交互物件 ──
        obj_path = mod.root_dir / mdef.objects_file
        if obj_path.exists():
            with open(obj_path, encoding="utf-8") as f:
                obj_data = json.load(f)

            for obj in obj_data.get("interactives", []):
                e = Entity(obj["id"])
                e.add(GridPosition(col=obj["col"], row=obj["row"]))
                e.add(Memory(obj["id"]))
                hw = obj.get("hitbox_w", 1)
                hh = obj.get("hitbox_h", 1)
                e.add(Interactable(hitbox_width=hw * 20, hitbox_height=hh * 20))
                self.world.add_entity(e)

            for q in obj_data.get("memory_questions", []):
                e = Entity(q["id"])
                e.add(GridPosition(col=q["col"], row=q["row"]))
                e.add(Memory(q["id"]))
                e.add(Interactable(hitbox_width=20, hitbox_height=20))
                self.world.add_entity(e)

        # ── 卡牌收集实体 ──
        for card_id, placement in mdef.cards.items():
            if placement is None:
                continue
            col, row = placement
            # 跳过已收集的卡牌
            if self.card_sys and self.card_sys.has_card(card_id):
                continue
            e = Entity(f"card_{card_id}")
            e.add(GridPosition(col=col, row=row))
            e.add(CardCollectible(card_id=card_id, collected=False))
            e.add(Interactable(hitbox_width=20, hitbox_height=20))
            self.world.add_entity(e)

        # ── 传送门实体 ──
        for portal in mdef.portals:
            pid = f"portal_{portal.target_mod or 'base'}_{portal.target_map}"
            e = Entity(pid)
            e.add(GridPosition(col=portal.col, row=portal.row))
            e.add(Interactable(hitbox_width=20, hitbox_height=20))
            # 将传送门数据附加到实体上供 PlayerController 读取
            e._portal_data = portal
            self.world.add_entity(e)

            # 在地图上标注传送门字符（如果地图该位置是空白/可通行）
            current_char = self.map_data.get(portal.col, portal.row)
            if current_char in (" ", "░"):
                self.map_data.set(portal.col, portal.row, portal.char)

    def _place_player(self, col: int, row: int):
        """将玩家移动到指定位置。"""
        player = self.world.entities.get("player")
        if not player:
            return
        gp = player.get(GridPosition)
        if gp:
            gp.col = col
            gp.row = row

    def get_portals_at(self, col: int, row: int) -> list[PortalDef]:
        """获取指定位置上的所有传送门定义。"""
        result = []
        for e in self.world.entities.values():
            gp = e.get(GridPosition)
            if not gp or gp.col != col or gp.row != row:
                continue
            if hasattr(e, "_portal_data"):
                result.append(e._portal_data)
        return result
