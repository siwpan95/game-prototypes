"""
玩家控制器 — WASD 移动 + 空格触碰交互 + 传送门检测
------------------------------------------------------
文字网格上的移动，碰撞检测基于地图的墙壁/不可通行字符。
支持地图传送门触发（MAP_TRANSITION 事件）。
"""
import json
from pathlib import Path

import pygame
from core.ecs import System
from core.config import CELL, COLS, ROWS, BLOCKED_CHARS, PORTAL_CHARS
from core.paths import ROOT
from components.grid_position import GridPosition
from components.memory import Memory
from components.interactable import Interactable
from components.card_collectible import CardCollectible


# 上一次移动方向（用于渲染器显示朝向）
LAST_DIR = None

# 全局搜索路径 — 由 main.py 在初始化时设置
MEMORY_SEARCH_PATHS: list[Path] = []
CARD_SEARCH_PATHS: list[Path] = []


class PlayerController(System):
    """玩家移动 + 触碰交互 + 传送门检测。"""

    def __init__(self, event_bus, map_data=None, map_manager=None):
        self.bus = event_bus
        self.move_timer = 0
        self.move_delay = 120  # 毫秒
        self.map_manager = map_manager
        self._map_data = map_data  # 持有 MapData 实例，不持有 grid 引用
        self._fallback_grid = None  # 无 map_data 注入时的回退

    def update(self, world, dt):
        """PlayerController 使用 handle_input 而非 update，此方法为空实现。"""
        pass

    @property
    def map_grid(self):
        """始终从 MapData 实例获取当前网格（支持地图切换后自动更新）。"""
        if self._map_data:
            return self._map_data.grid
        return self._fallback_grid

    def _load_map(self):
        """Standalone fallback（无 map_data 注入时）。"""
        map_path = ROOT / "data" / "mansion_map.txt"
        with open(map_path, encoding="utf-8") as f:
            raw = f.read()
        lines = raw.strip("\n").split("\n")
        self._fallback_grid = []
        for row_idx, line in enumerate(lines):
            if row_idx >= ROWS:
                break
            row_chars = []
            for col_idx, ch in enumerate(line):
                if col_idx >= COLS:
                    break
                row_chars.append(ch)
            while len(row_chars) < COLS:
                row_chars.append(" ")
            self._fallback_grid.append(row_chars)
        while len(self._fallback_grid) < ROWS:
            self._fallback_grid.append([" "] * COLS)

    def is_walkable(self, col, row):
        """检查格子是否可行走。传送门字符视为可行走（触发切换而非阻挡）。"""
        if not (0 <= col < COLS and 0 <= row < ROWS):
            return False
        ch = self.map_grid[row][col]
        # 传送门字符允许走入（触发 MAP_TRANSITION）
        if ch in PORTAL_CHARS:
            return True
        return ch not in BLOCKED_CHARS

    def handle_input(self, world, dt, events=None):
        """处理键盘输入。"""
        global LAST_DIR
        self.move_timer += dt

        keys = pygame.key.get_pressed()
        dx, dy = 0, 0
        if keys[pygame.K_w] or keys[pygame.K_UP]:
            dy = -1
        elif keys[pygame.K_s] or keys[pygame.K_DOWN]:
            dy = 1
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            dx = -1
        elif keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            dx = 1

        if (dx != 0 or dy != 0) and self.move_timer >= self.move_delay:
            self.move_timer = 0
            self._try_move(world, dx, dy)
            if dx != 0 or dy != 0:
                LAST_DIR = (dx, dy)

        if events:
            for event in events:
                if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
                    self._try_touch(world)

    def _try_move(self, world, dx, dy):
        """尝试移动玩家一格，并检测传送门。"""
        player = world.entities.get("player")
        if not player:
            return
        gp = player.get(GridPosition)
        if not gp:
            return
        new_col = gp.col + dx
        new_row = gp.row + dy

        if self.is_walkable(new_col, new_row) and not self._entity_blocks(world, new_col, new_row):
            gp.col = new_col
            gp.row = new_row
            self.bus.emit("PLAYER_MOVE", {"col": new_col, "row": new_row})

            # ── 传送门检测 ──
            self._check_portal(world, new_col, new_row)

    def _check_portal(self, world, col, row):
        """检查当前位置是否有传送门，如有则触发地图切换。"""
        if self.map_manager is None:
            return
        portals = self.map_manager.get_portals_at(col, row)
        for portal in portals:
            self.bus.emit("MAP_TRANSITION", {
                "target_mod": portal.target_mod,
                "target_map": portal.target_map,
                "target_col": portal.target_col,
                "target_row": portal.target_row,
            })
            return  # 只触发第一个传送门

    # ── 实体阻挡检测（同原有逻辑）──

    def _entity_blocks(self, world, col, row):
        for e in world.entities.values():
            egp = e.get(GridPosition)
            if not egp:
                continue
            ia = e.get(Interactable)
            if ia is None:
                continue
            hw_cells = max(ia.hitbox_width // 20, 1)
            hh_cells = max(ia.hitbox_height // 20, 1)
            if not (egp.col <= col < egp.col + hw_cells and egp.row <= row < egp.row + hh_cells):
                continue
            # 传送门不阻挡移动
            if hasattr(e, "_portal_data"):
                continue
            cc = e.get(CardCollectible)
            if cc and cc.collected:
                continue
            m = e.get(Memory)
            if m and m.discovered:
                continue
            return True
        return False

    # ── 触碰交互（同原有逻辑）──

    def _try_touch(self, world):
        player = world.entities.get("player")
        if not player:
            return
        gp = player.get(GridPosition)
        if not gp:
            return
        neighbors = [
            (gp.col,     gp.row - 1),
            (gp.col,     gp.row + 1),
            (gp.col - 1, gp.row),
            (gp.col + 1, gp.row),
        ]
        extra_neighbors = []
        for e in world.entities.values():
            egp = e.get(GridPosition)
            ia = e.get(Interactable)
            if not egp or not ia:
                continue
            hw_cells = ia.hitbox_width // 20
            hh_cells = ia.hitbox_height // 20
            if hw_cells <= 1 and hh_cells <= 1:
                continue
            for dc in range(hw_cells):
                for dr in range(hh_cells):
                    tc, tr = egp.col + dc, egp.row + dr
                    if abs(gp.col - tc) + abs(gp.row - tr) == 1:
                        extra_neighbors.append((tc, tr))
        all_neighbors = neighbors + extra_neighbors
        for nx, ny in all_neighbors:
            self._try_interact_at(world, nx, ny)

    def _try_interact_at(self, world, col, row):
        for e in world.entities.values():
            gp = e.get(GridPosition)
            if not gp:
                continue
            ia = e.get(Interactable)
            exact_match = (gp.col == col and gp.row == row)
            hitbox_match = False
            if ia:
                hw = max(ia.hitbox_width // 20, 1)
                hh = max(ia.hitbox_height // 20, 1)
                hitbox_match = (gp.col <= col < gp.col + hw and gp.row <= row < gp.row + hh)
            if not exact_match and not hitbox_match:
                continue
            # 跳过传送门实体（由行走触发，不由空格触碰触发）
            if hasattr(e, "_portal_data"):
                continue
            cc = e.get(CardCollectible)
            if cc and not cc.collected:
                cc.collected = True
                card_data = self._load_card(cc.card_id)
                self.bus.emit("CARD_COLLECTED", {
                    "card_id": cc.card_id,
                    "name": card_data["name"],
                    "glyph": card_data["glyph"],
                })
                return
            m = e.get(Memory)
            if m and ia and not m.discovered:
                m.discovered = True
                data = self._load_memory(m.memory_id)
                self.bus.emit("MEMORY_TRIGGERED", data)
                return

    # ── 数据加载（支持多路径搜索）──

    def _load_memory(self, memory_id):
        """加载记忆数据 — 搜索 MEMORY_SEARCH_PATHS 中的多个目录。"""
        if memory_id.startswith("q_"):
            return self._load_question(memory_id)
        for search_dir in MEMORY_SEARCH_PATHS:
            path = search_dir / f"{memory_id}.json"
            if path.exists():
                with open(path, encoding="utf-8") as f:
                    return json.load(f)
        return {"name": "???", "sanity_cost": 0, "text": "..."}

    def _load_question(self, qid):
        """加载记忆问题 — 搜索所有 objects JSON 文件中的 memory_questions 数组。"""
        search_roots = {ROOT / "data"}
        for mem_dir in MEMORY_SEARCH_PATHS:
            search_roots.add(mem_dir.parent)

        for root_dir in search_roots:
            for pattern in ["*objects*.json", "objects/*.json"]:
                for obj_path in root_dir.glob(pattern):
                    if not obj_path.exists():
                        continue
                    try:
                        with open(obj_path, encoding="utf-8") as f:
                            obj_data = json.load(f)
                    except Exception:
                        continue
                    for q in obj_data.get("memory_questions", []):
                        if q["id"] == qid:
                            return {
                                "id": qid, "name": "记忆之问",
                                "sanity_cost": 0, "text": q["text"],
                                "answer_card": q.get("answer_card", ""),
                            }
        return {"id": qid, "name": "???", "sanity_cost": 0, "text": "..."}

    @staticmethod
    def _load_card(card_id):
        """加载卡牌数据 — 搜索 CARD_SEARCH_PATHS 中的多个目录。"""
        for search_dir in CARD_SEARCH_PATHS:
            path = search_dir / f"{card_id}.json"
            if path.exists():
                with open(path, encoding="utf-8") as f:
                    return json.load(f)
        return {"name": card_id, "glyph": "?"}

    # ── 相邻可交互物查询（供渲染器使用）──

    def get_adjacent_interactables(self, world):
        player = world.entities.get("player")
        if not player:
            return []
        gp = player.get(GridPosition)
        if not gp:
            return []
        neighbors = [
            (gp.col,     gp.row - 1),
            (gp.col,     gp.row + 1),
            (gp.col - 1, gp.row),
            (gp.col + 1, gp.row),
        ]
        result = []
        for ac, ar in neighbors:
            for e in world.entities.values():
                eg = e.get(GridPosition)
                if not eg or eg.col != ac or eg.row != ar:
                    continue
                ia = e.get(Interactable)
                if hasattr(e, "_portal_data"):
                    continue
                m = e.get(Memory)
                cc = e.get(CardCollectible)
                if (ia and m and not m.discovered) or (cc and not cc.collected):
                    result.append((ac, ar, e))
        return result
