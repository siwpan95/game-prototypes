"""坐标一致性集成测试 — 验证 objects.json / card_placements 与 map.txt 一致。

这些测试防止历史上反复出现的问题：
- 物件坐标与实际地图字符位置不匹配
- 卡牌被放置到墙壁上
- hitbox 多格物件覆盖到墙壁或其他物件
"""
import json
from pathlib import Path

import pytest

DATA = Path(__file__).resolve().parent.parent / "data"


def _load_map():
    with open(DATA / "mansion_map.txt", encoding="utf-8") as f:
        return f.read().strip("\n").split("\n")


def _load_objects():
    with open(DATA / "mansion_objects.json", encoding="utf-8") as f:
        return json.load(f)


def _load_cards():
    cards = {}
    for cf in sorted((DATA / "cards").glob("*.json")):
        with open(cf, encoding="utf-8") as f:
            card = json.load(f)
        cards[card["id"]] = card
    return cards


# ─── 辅助函数 ──────────────────────────────────────────


def _at(map_lines, col, row):
    """安全获取地图 (col, row) 的字符，越界返回 '?'。"""
    if 0 <= row < len(map_lines):
        line = map_lines[row]
        if 0 <= col < len(line):
            return line[col]
    return "?"


def _slice(map_lines, col, row, width):
    """获取地图从 (col, row) 开始宽度为 width 的字符串片段。"""
    if 0 <= row < len(map_lines):
        end = min(col + width, len(map_lines[row]))
        return map_lines[row][col:end]
    return ""

from core.config import BLOCKED_CHARS


# ─── 交互物件坐标测试 ──────────────────────────────────


class TestInteractiveCoordinates:
    """验证 mansion_objects.json 中每个 interactives 项坐标正确。"""

    def test_all_interactives_char_match(self):
        """物件 char 必须在地图坐标处匹配。"""
        map_lines = _load_map()
        obj = _load_objects()
        failures = []
        for item in obj["interactives"]:
            c, r = item["col"], item["row"]
            actual = _slice(map_lines, c, r, len(item["char"]))
            if actual != item["char"]:
                failures.append(f"{item['id']}: expected '{item['char']}' at ({c},{r}), got '{actual}'")
        assert not failures, "\n" + "\n".join(failures)

    def test_interactives_not_on_wall(self):
        """物件不应该放置在墙壁上（除非地图设计如此）。"""
        map_lines = _load_map()
        obj = _load_objects()
        for item in obj["interactives"]:
            c, r = item["col"], item["row"]
            ch = _at(map_lines, c, r)
            assert ch != "墙", f"{item['id']} at ({c},{r}) is on wall char '墙'"

    def test_multi_hitbox_coverage_safe(self):
        """多格物件（hitbox_w/h > 1）的所有覆盖格不应包含墙。"""
        map_lines = _load_map()
        obj = _load_objects()
        for item in obj["interactives"]:
            hw = max(item.get("hitbox_w", 1), 1)
            hh = max(item.get("hitbox_h", 1), 1)
            for dc in range(hw):
                for dr in range(hh):
                    c, r = item["col"] + dc, item["row"] + dr
                    ch = _at(map_lines, c, r)
                    assert ch != "墙", \
                        f"{item['id']} hitbox ({hw}×{hh}) cell ({c},{r}) is wall"


# ─── 记忆问题坐标测试 ──────────────────────────────────


class TestMemoryQuestionCoordinates:
    """验证 memory_questions 中每个 ◈ 坐标正确。"""

    def test_all_questions_char_match(self):
        map_lines = _load_map()
        obj = _load_objects()
        failures = []
        for q in obj["memory_questions"]:
            c, r = q["col"], q["row"]
            actual = _at(map_lines, c, r)
            if actual != q["char"]:
                failures.append(f"{q['id']}: expected '{q['char']}' at ({c},{r}), got '{actual}'")
        assert not failures, "\n" + "\n".join(failures)

    def test_questions_not_on_wall(self):
        map_lines = _load_map()
        obj = _load_objects()
        for q in obj["memory_questions"]:
            c, r = q["col"], q["row"]
            ch = _at(map_lines, c, r)
            assert ch != "墙", f"{q['id']} at ({c},{r}) is on wall"

    def test_answer_card_exists(self):
        """每个记忆问题的 answer_card 必须在 cards/ 目录中存在。"""
        cards = _load_cards()
        obj = _load_objects()
        for q in obj["memory_questions"]:
            aid = q.get("answer_card")
            assert aid in cards, \
                f"{q['id']} answer_card '{aid}' not found in data/cards/"


# ─── 卡牌坐标测试 ──────────────────────────────────────


class TestCardCoordinates:
    """验证 text_world.py 中的 card_placements 坐标有效。"""

    # 这些坐标来自 core/text_world.py — 测试失败时请更新 text_world.py
    CARD_PLACEMENTS = {
        "old_woman_01":     (35, 11),
        "strange_symbol_01": (30, 25),
        "doll_01":          (6, 5),
        "dead_vole_01":     (4, 13),
        "grave_01":         (35, 2),
        "hut_01":           (2, 15),
        "garden_tools_01":  (2, 16),
        "owl_01":           (29, 6),
        "key_01":           (34, 17),
        "lizard_01":        (30, 15),
        "owl_statue_01":    (34, 7),
        "full_moon_01":     (20, 1),
        "treasure_chest_01": (10, 24),
        "lavender_01":      (12, 8),
        "suspicious_hole_01": (20, 15),
        "vole_01":          (3, 15),
        "wooden_statue_01": (28, 8),
        "carimara_01":      None,
    }

    def test_no_card_on_wall(self):
        """任何卡牌坐标不能落在墙壁（墙）上。"""
        map_lines = _load_map()
        for cid, pos in self.CARD_PLACEMENTS.items():
            if pos is None:
                continue
            c, r = pos
            ch = _at(map_lines, c, r)
            assert ch != "墙", f"Card '{cid}' at ({c},{r}) is on wall char '墙'"

    def test_no_card_on_door(self):
        """卡牌不能落在不可通行的"门"字符上。"""
        map_lines = _load_map()
        for cid, pos in self.CARD_PLACEMENTS.items():
            if pos is None:
                continue
            c, r = pos
            ch = _at(map_lines, c, r)
            assert ch != "门", f"Card '{cid}' at ({c},{r}) is on door char '门'"

    def test_placements_match_text_world(self):
        """确保测试中的坐标与 text_world.py 中的 card_placements 一致。"""
        # 如果这里失败，说明 text_world.py 被手动修改了而测试未同步更新
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from core.text_world import create_text_world  # 会触发 import 副作用

        # 重新读取 text_world 源码中的字典
        text_world_path = Path(__file__).resolve().parent.parent / "core" / "text_world.py"
        with open(text_world_path, encoding="utf-8") as f:
            source = f.read()

        # 解析 card_placements 字典中的坐标
        import re
        for cid, expected in self.CARD_PLACEMENTS.items():
            if expected is None:
                # 确认源码中确实是 None
                pattern = rf'"{cid}":\s*None'
                assert re.search(pattern, source), \
                    f"'{cid}' should be None in text_world.py"
            else:
                pattern = rf'"{cid}":\s*\((\d+),\s*(\d+)\)'
                m = re.search(pattern, source)
                assert m, f"'{cid}' placement not found in text_world.py"
                actual = (int(m.group(1)), int(m.group(2)))
                assert actual == expected, \
                    f"'{cid}': test expects {expected}, text_world.py has {actual}"


# ─── 地图与游戏逻辑交叉验证 ────────────────────────────


class TestMapGameLogicConsistency:
    """验证地图配置与游戏逻辑的一致性。"""

    def test_map_row_count(self):
        map_lines = _load_map()
        assert len(map_lines) == 32, "mansion_map.txt should have exactly 32 rows"

    def test_map_columns_padded_by_mapdata(self):
        """MapData._load 自动用 FILL_CHAR 补齐不足 COLS 的行。"""
        from core.map_data import MapData
        from core.config import COLS, ROWS
        md = MapData(DATA / "mansion_map.txt")
        for r in range(ROWS):
            assert len(md.grid[r]) == COLS, \
                f"Row {r}: MapData grid has {len(md.grid[r])} cols, expected {COLS}"

    def test_player_start_is_walkable(self):
        """玩家出生点 (19, 13) 应该是可行走的地板。"""
        map_lines = _load_map()
        ch = _at(map_lines, 19, 13)
        assert ch not in BLOCKED_CHARS, \
            f"Player start (19,13) is blocked: '{ch}'"

    def test_attic_door_exists(self):
        """阁楼门在 col=18, row=3。"""
        map_lines = _load_map()
        assert _at(map_lines, 18, 3) == "门", \
            "Attic door '门' not found at (18,3)"
