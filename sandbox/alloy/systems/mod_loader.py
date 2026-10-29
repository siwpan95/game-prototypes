"""
Mod/DLC 加载系统 — 发现、验证、加载 Mod 内容。

支持：Mod 清单扫描、地图切换、传送门、数据驱动机关、
通用数据目录查找（简化为不依赖特定卡牌/记忆组件）。

数据类：
- ModManifest: 单个 Mod 的完整描述
- MapDef: 单张地图定义
- PortalDef: 传送门定义
- MechanismDef: 数据驱动机关（MechanismAction 复用 world/room.py）
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

# 复用 world/room.py 中定义的 MechanismAction
from alloy.world.room import MechanismAction


# ---------------------------------------------------------------
# 数据类
# ---------------------------------------------------------------

@dataclass
class PortalDef:
    """传送门定义。

    玩家走到该位置时触发地图切换。

    Attributes:
        col, row: 触发位置
        char: 地图上显示的字符
        target_mod: 目标 Mod ID（None = base game）
        target_map: 目标地图 ID
        target_col, target_row: 传送后玩家位置
    """
    col: int
    row: int
    char: str = "▣"
    target_mod: Optional[str] = None
    target_map: str = ""
    target_col: int = 0
    target_row: int = 0


@dataclass
class MechanismDef:
    """数据驱动机关定义。

    Attributes:
        mech_id: 机关唯一 ID
        trigger_type: 触发条件 — ITEM_USED / EVENT_FIRED / POSITION_REACHED / TURN_PASSED
        trigger_id: 触发器标识
        desc: 描述文本
        actions: 触发时执行的动作列表
    """
    mech_id: str
    trigger_type: str
    trigger_id: str
    desc: str = ""
    actions: list[MechanismAction] = field(default_factory=list)


@dataclass
class MapDef:
    """单张地图的完整定义。

    Attributes:
        map_id: 地图唯一 ID
        name: 显示名称
        map_file: 地图数据文件（相对 Mod 根目录）
        player_start: 玩家出生点 (col, row)
        objects_file: 可交互物件 JSON 路径
        portals: 传送门列表
        mechanisms: 机关列表
        metadata: 扩展数据
    """
    map_id: str
    name: str = ""
    map_file: str = ""
    player_start: tuple[int, int] = (0, 0)
    objects_file: str = ""
    portals: list[PortalDef] = field(default_factory=list)
    mechanisms: list[MechanismDef] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ModManifest:
    """Mod 清单 — 一个 Mod 可包含多张地图和多种资源。

    Attributes:
        mod_id: 唯一标识符
        name: 显示名称
        version: 版本号
        description: 描述
        root_dir: Mod 根目录
        maps: map_id → MapDef
        dependencies: 依赖的 Mod ID 列表
    """
    mod_id: str
    name: str
    version: str = "1.0"
    description: str = ""
    root_dir: Path = field(default_factory=Path)
    maps: dict[str, MapDef] = field(default_factory=dict)
    dependencies: list[str] = field(default_factory=list)

    def get_map(self, map_id: str) -> Optional[MapDef]:
        """获取指定地图定义。"""
        return self.maps.get(map_id)

    def has_map(self, map_id: str) -> bool:
        """检查是否包含指定地图。"""
        return map_id in self.maps


# ---------------------------------------------------------------
# 路径安全工具
# ---------------------------------------------------------------

def _safe_join(root: "Path | str", rel: str,
               on_reject: "Optional[Callable[[str], None]]" = None) -> "Optional[Path]":
    """安全拼接相对路径，防止路径穿越（Path Traversal）。

    仅允许返回位于 root 目录内（含 root 本身）的绝对路径；
    若 rel 试图跳出 root（如 '../etc/passwd' 或绝对路径），返回 None。

    :param root: Mod / 数据根目录
    :param rel: 清单中声明的相对路径（来自不受信任的 mod.json）
    :param on_reject: 可选的拒绝回调（用于打日志）
    :returns: 校验通过的绝对路径，或 None
    """
    if not rel:
        return None
    root_resolved = Path(root).resolve()
    target = (root_resolved / rel).resolve()
    if target != root_resolved and root_resolved not in target.parents:
        if on_reject:
            on_reject(f"路径穿越被拒绝: {rel!r} -> {target}")
        return None
    return target


# ---------------------------------------------------------------
# ModManager — 发现并管理所有 Mod
# ---------------------------------------------------------------

class ModManager:
    """扫描 mods/ 目录，加载所有有效 Mod 的清单。

    使用方式:

        mgr = ModManager(root_dir / "mods")
        mod = mgr.get_mod("my_mod")
        mod_id, map_def = mgr.get_map("my_mod", "level1")
    """

    def __init__(self, mods_root: Path | str, base_data_dir: Path | str | None = None, logger: Any = None):
        """
        :param mods_root: Mod 目录路径
        :param base_data_dir: 基础游戏数据目录（可选，用于加载 base mod 清单）
        :param logger: 可选的 Logger 实例
        """
        self.mods_root = Path(mods_root)
        self.base_data_dir = Path(base_data_dir) if base_data_dir else None
        self.mods: dict[str, ModManifest] = {}
        self._logger = logger
        self._discover()

    def _log(self, msg: str) -> None:
        """记录警告信息。"""
        if self._logger:
            self._logger.warning(f"[ModManager] {msg}")
        else:
            print(f"[ModManager] {msg}")

    # ---- 扫描 ----

    def _discover(self) -> None:
        """扫描 mods/ 下每个子目录的 mod.json；同时加载 base_mod.json。"""

        # ── 加载 Base Mod ──
        if self.base_data_dir and self.base_data_dir.exists():
            base_manifest = self.base_data_dir / "base_mod.json"
            if base_manifest.exists():
                try:
                    mod = self._load_mod(self.base_data_dir, base_manifest)
                    self.mods[mod.mod_id] = mod
                except Exception as e:
                    self._log(f"跳过 base: {e}")

        # ── 扫描 mods/ 目录 ──
        if not self.mods_root.exists():
            return

        for mod_dir in sorted(self.mods_root.iterdir()):
            if not mod_dir.is_dir():
                continue
            manifest_path = mod_dir / "mod.json"
            if not manifest_path.exists():
                continue
            try:
                mod = self._load_mod(mod_dir, manifest_path)
                self.mods[mod.mod_id] = mod
            except Exception as e:
                self._log(f"跳过 {mod_dir.name}: {e}")

    def _load_mod(self, mod_dir: Path, manifest_path: Path) -> ModManifest:
        """从 mod.json 加载单个 Mod 清单。"""
        with open(manifest_path, encoding="utf-8") as f:
            data = json.load(f)

        maps: dict[str, MapDef] = {}
        for mdef in data.get("maps", []):
            # 传送门
            portals: list[PortalDef] = []
            for p in mdef.get("portals", []):
                portals.append(PortalDef(
                    col=p["col"],
                    row=p["row"],
                    char=p.get("char", "▣"),
                    target_mod=p.get("target_mod"),
                    target_map=p["target_map"],
                    target_col=p.get("target_col", 0),
                    target_row=p.get("target_row", 0),
                ))

            # 机关
            mechanisms: list[MechanismDef] = []
            for mech in mdef.get("mechanisms", []):
                actions: list[MechanismAction] = []
                for a in mech.get("actions", []):
                    action_params = {k: v for k, v in a.items() if k != "type"}
                    actions.append(MechanismAction(type=a["type"], params=action_params))
                mechanisms.append(MechanismDef(
                    mech_id=mech["id"],
                    trigger_type=mech.get("trigger_type", "EVENT_FIRED"),
                    trigger_id=mech.get("trigger_id", ""),
                    desc=mech.get("desc", ""),
                    actions=actions,
                ))

            maps[mdef["map_id"]] = MapDef(
                map_id=mdef["map_id"],
                name=mdef.get("name", mdef["map_id"]),
                map_file=mdef.get("map_file", ""),
                player_start=(
                    mdef.get("player_start", {}).get("col", 0),
                    mdef.get("player_start", {}).get("row", 0),
                ),
                objects_file=mdef.get("objects_file", ""),
                portals=portals,
                mechanisms=mechanisms,
                metadata=mdef.get("metadata", {}),
            )

        return ModManifest(
            mod_id=data["mod_id"],
            name=data.get("name", data["mod_id"]),
            version=data.get("version", "1.0"),
            description=data.get("description", ""),
            root_dir=mod_dir,
            maps=maps,
            dependencies=data.get("dependencies", []),
        )

    # ---- 查询 ----

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

    def list_mods(self) -> list[ModManifest]:
        """列出所有已加载的 Mod。"""
        return list(self.mods.values())

    def list_maps(self, mod_id: str | None = None) -> list[tuple[str, str, str]]:
        """列出所有地图。

        Returns:
            [(mod_id, map_id, map_name), ...]
        """
        result: list[tuple[str, str, str]] = []
        if mod_id:
            mod = self.get_mod(mod_id)
            if mod:
                for mid, mdef in mod.maps.items():
                    result.append((mod.mod_id, mid, mdef.name))
        else:
            for mod in self.mods.values():
                for mid, mdef in mod.maps.items():
                    result.append((mod.mod_id, mid, mdef.name))
        return result

    # ---- 通用数据目录查找 ----

    def find_data_dirs(self, subdir: str) -> list[Path]:
        """在所有已加载 Mod 中查找指定子目录。

        用于通用数据查找（如 cards/, enemies/, puzzles/ 等），
        替代 carimara_py 中硬编码的卡牌/记忆查找。

        :param subdir: 子目录名，如 "cards", "enemies", "puzzles"
        :returns: 存在该子目录的 Path 列表（base 优先）
        """
        dirs: list[Path] = []

        # base 优先级最高
        if self.base_data_dir:
            base_sub = self.base_data_dir / subdir
            if base_sub.exists():
                dirs.append(base_sub)

        # 其他 Mod
        for mod in self.mods.values():
            if mod.mod_id == "base":
                continue
            mod_sub = mod.root_dir / subdir
            if mod_sub.exists():
                dirs.append(mod_sub)

        return dirs

    def find_json_files(self, subdir: str) -> list[Path]:
        """在所有已加载 Mod 中查找指定子目录下的所有 JSON 文件。

        :param subdir: 子目录名
        :returns: JSON 文件 Path 列表
        """
        files: list[Path] = []
        for data_dir in self.find_data_dirs(subdir):
            if data_dir.exists():
                for f in sorted(data_dir.glob("*.json")):
                    files.append(f)
        return files


# ---------------------------------------------------------------
# MapManager — 管理当前活跃地图与切换逻辑
# ---------------------------------------------------------------

class MapManager:
    """地图切换管理器。

    职责：
    - 加载初始地图
    - 响应传送门触发，切换地图
    - 清除/重建非玩家实体
    - 注入传送门、机关等地图要素

    使用方式:

        mm = MapManager(mod_manager, world, map_data, event_bus)
        mm.load_initial_map(mod_id=None, map_id="town")
        mm.switch_map("dungeon_mod", "level_1", 5, 5)
    """

    def __init__(
        self,
        mod_manager: ModManager,
        world: Any,
        map_data: Any,
        event_bus: Any,
        entity_factory: Any = None,
        mechanism_system: Any = None,
        logger: Any = None,
    ):
        """
        :param mod_manager: Mod 管理器实例
        :param world: ECS World 实例
        :param map_data: 地图数据管理对象（需实现 reload/get/set 方法）
        :param event_bus: 事件总线实例
        :param entity_factory: 实体工厂（可选，用于创建地图实体）
        :param mechanism_system: 机关系统（可选，用于加载机关）
        :param logger: 可选的 Logger 实例
        """
        self.mod_mgr = mod_manager
        self.world = world
        self.map_data = map_data
        self.bus = event_bus
        self.entity_factory = entity_factory
        self.mechanism_system = mechanism_system
        self._logger = logger

        # 当前状态
        self.current_mod_id: Optional[str] = None
        self.current_map_id: str = ""
        self.current_mod: Optional[ModManifest] = None
        self.current_map: Optional[MapDef] = None

        # 订阅地图切换事件
        self.bus.subscribe("MAP_TRANSITION", self._on_transition)

    def _log(self, msg: str) -> None:
        """记录警告信息。"""
        if self._logger:
            self._logger.warning(f"[MapManager] {msg}")
        else:
            print(f"[MapManager] {msg}")

    # ---- 加载地图 ----

    def load_initial_map(self, mod_id: str | None = None, map_id: str = "start") -> None:
        """加载初始地图（游戏启动时）。"""
        result = self.mod_mgr.get_map(mod_id, map_id)
        if result is None:
            raise RuntimeError(f"初始地图不存在: mod={mod_id} map={map_id}")

        mod, mdef = result
        if not self._apply_map(mod, mdef):
            raise RuntimeError(
                f"初始地图加载失败（路径校验未通过）: mod={mod_id} map={map_id}"
            )

    def _on_transition(self, data: dict) -> None:
        """处理 MAP_TRANSITION 事件。

        :param data: 事件数据，包含 target_mod, target_map, target_col, target_row
        """
        if data is None:
            return
        target_mod = data.get("target_mod")
        target_map = data.get("target_map", "")
        target_col = data.get("target_col", 0)
        target_row = data.get("target_row", 0)
        self.switch_map(target_mod, target_map, target_col, target_row)

    def switch_map(
        self,
        mod_id: str | None,
        map_id: str,
        entry_col: int = 0,
        entry_row: int = 0,
    ) -> bool:
        """切换到指定地图。

        :returns: 是否切换成功
        """
        result = self.mod_mgr.get_map(mod_id, map_id)
        if result is None:
            self._log(f"地图不存在: mod={mod_id} map={map_id}")
            return False

        mod, mdef = result

        # 清除当前地图的非玩家实体
        self._clear_non_player_entities()

        # 应用新地图
        if not self._apply_map(mod, mdef, entry_col, entry_row):
            self._log(f"地图加载失败（路径校验未通过），取消切换: mod={mod_id} map={map_id}")
            return False

        # 通知地图切换完成
        self.bus.emit("MAP_LOADED", {
            "mod_id": mod_id,
            "map_id": map_id,
            "map_name": mdef.name,
            "mod_name": mod.name,
        })
        return True

    def _apply_map(
        self,
        mod: ModManifest,
        mdef: MapDef,
        player_col: int = 0,
        player_row: int = 0,
    ) -> bool:
        """:内部：应用地图数据。返回是否成功（路径校验未通过时返回 False）。"""
        # 加载地图网格（路径穿越防护）
        map_path = _safe_join(mod.root_dir, mdef.map_file, on_reject=self._log)
        if map_path is None:
            self._log(f"地图文件非法，跳过加载: {mdef.map_file!r}")
            return False
        if hasattr(self.map_data, "reload"):
            self.map_data.reload(map_path)

        # 创建实体
        self._load_map_entities(mod, mdef)

        # 设置玩家位置
        if player_col == 0 and player_row == 0:
            player_col, player_row = mdef.player_start
        self._place_player(player_col, player_row)

        # 加载机关
        if self.mechanism_system:
            self.mechanism_system.load_mechanisms(mod, mdef)

        # 更新状态
        self.current_mod_id = mod.mod_id
        self.current_map_id = mdef.map_id
        self.current_mod = mod
        self.current_map = mdef
        return True

    # ---- 实体管理 ----

    def _clear_non_player_entities(self) -> None:
        """移除世界中除 player 外的所有实体。"""
        if not hasattr(self.world, "remove_entity"):
            return
        # 使用公开 API 遍历实体
        if hasattr(self.world, "list_entity_ids"):
            for eid in list(self.world.list_entity_ids()):
                if eid != "player":
                    self.world.remove_entity(eid)
        elif hasattr(self.world, "entities"):
            # 兼容旧版 World
            to_remove = [eid for eid in self.world.entities if eid != "player"]
            for eid in to_remove:
                del self.world.entities[eid]

    def _load_map_entities(self, mod: ModManifest, mdef: MapDef) -> None:
        """为指定地图创建所有实体（传送门等）。"""
        # 传送门实体
        for portal in mdef.portals:
            pid = f"portal_{portal.target_mod or 'base'}_{portal.target_map}"
            entity = None
            if self.entity_factory:
                entity = self.entity_factory.create(pid, "portal", portal_data=portal)
            else:
                # 简单实体创建（dict 回退）
                entity = {"id": pid, "type": "portal", "_portal_data": portal}
            if entity is not None:
                if hasattr(self.world, "add_entity"):
                    self.world.add_entity(entity)
                elif isinstance(entity, dict) and hasattr(self.world, "entities"):
                    self.world.entities[pid] = entity

            # 在地图上标注传送门字符
            if hasattr(self.map_data, "get"):
                current_char = self.map_data.get(portal.col, portal.row)
                if current_char in (" ", "░", ""):
                    if hasattr(self.map_data, "set"):
                        self.map_data.set(portal.col, portal.row, portal.char)

        # 可交互物件（路径穿越防护）
        obj_path = _safe_join(mod.root_dir, mdef.objects_file, on_reject=self._log)
        if obj_path is not None and obj_path.exists() and self.entity_factory:
            with open(obj_path, encoding="utf-8") as f:
                obj_data = json.load(f)
            for obj_def in obj_data.get("interactives", []):
                entity = self.entity_factory.create(
                    obj_def["id"], "interactive", obj_data=obj_def,
                )
                if hasattr(self.world, "add_entity"):
                    self.world.add_entity(entity)

    def _place_player(self, col: int, row: int) -> None:
        """将玩家移动到指定位置。"""
        # 优先使用公开 API
        if hasattr(self.world, "get_entity"):
            player = self.world.get_entity("player")
        elif hasattr(self.world, "entities"):
            player = self.world.entities.get("player")
        else:
            return

        if player is None:
            return
        # 尝试设置位置属性
        if hasattr(player, "col") and hasattr(player, "row"):
            player.col = col
            player.row = row
        elif isinstance(player, dict):
            player["col"] = col
            player["row"] = row

    # ---- 查询 ----

    def get_portals_at(self, col: int, row: int) -> list[PortalDef]:
        """获取指定位置上的所有传送门定义。"""
        result: list[PortalDef] = []
        # 优先使用公开 API
        if hasattr(self.world, "each_entity"):
            entities = list(self.world.each_entity())
        elif hasattr(self.world, "entities"):
            entities = list(self.world.entities.values())
        else:
            return result

        for entity in entities:
            e_col = entity.get("col") if isinstance(entity, dict) else getattr(entity, "col", None)
            e_row = entity.get("row") if isinstance(entity, dict) else getattr(entity, "row", None)
            if e_col != col or e_row != row:
                continue
            portal_data = entity.get("_portal_data") if isinstance(entity, dict) else getattr(entity, "_portal_data", None)
            if portal_data:
                result.append(portal_data)
        return result

    @property
    def current_map_name(self) -> str:
        """当前地图名称。"""
        return self.current_map.name if self.current_map else ""
