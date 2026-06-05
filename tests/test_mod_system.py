"""
Mod/DLC 系统测试套件
=====================
验证 ModManager、地图加载、传送门连接、卡牌/记忆完整性。

运行方式:
    python tests/test_mod_system.py          # 全部测试
    python tests/test_mod_system.py --verbose  # 详细输出
"""
import json
import sys
from pathlib import Path

# 将项目根目录加入 sys.path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.mod_loader import ModManager


# ═══════════════════════════════════════════
#  Test helpers
# ═══════════════════════════════════════════

TESTS_PASSED = 0
TESTS_FAILED = 0
TESTS_WARNED = 0
VERBOSE = "--verbose" in sys.argv or "-v" in sys.argv


def ok(msg):
    global TESTS_PASSED
    TESTS_PASSED += 1
    if VERBOSE:
        print(f"  [PASS] {msg}")


def fail(msg):
    global TESTS_FAILED
    TESTS_FAILED += 1
    print(f"  [FAIL] {msg}")


def warn(msg):
    global TESTS_WARNED
    TESTS_WARNED += 1
    if VERBOSE:
        print(f"  [WARN] {msg}")


def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


# ═══════════════════════════════════════════
#  Test 1: ModManager 发现所有 Mod
# ═══════════════════════════════════════════

def test_mod_discovery(mm: ModManager):
    section("T1: Mod 发现与解析")

    mod_ids = sorted(mm.mods.keys())
    print(f"  发现 Mod: {mod_ids}")

    if "base" in mod_ids:
        ok("Base Mod 已注册")
    else:
        fail("Base Mod 未注册")

    dlc_mods = [m for m in mod_ids if m != "base"]
    if len(dlc_mods) >= 3:
        ok(f"DLC Mod 数量 ≥ 3: {len(dlc_mods)}")
    else:
        fail(f"DLC Mod 数量不足: {len(dlc_mods)} < 3")

    for mid in mod_ids:
        mod = mm.mods[mid]
        if mod.name and mod.version and mod.maps:
            ok(f"  {mid}: {mod.name} v{mod.version} ({len(mod.maps)} 张地图)")
        else:
            fail(f"  {mid}: 缺少必要字段 (name/version/maps)")


# ═══════════════════════════════════════════
#  Test 2: 地图文件存在性
# ═══════════════════════════════════════════

def test_map_files(mm: ModManager):
    section("T2: 地图文件存在性")

    for mod_id, mod in mm.mods.items():
        for map_id, mdef in mod.maps.items():
            # 地图 .txt 文件
            map_path = mod.root_dir / mdef.map_file
            if map_path.exists():
                ok(f"  地图文件: {mod_id}/{map_id} → {mdef.map_file}")
            else:
                fail(f"  地图文件缺失: {mod_id}/{map_id} → {mdef.map_file}")

            # 物件 .json 文件
            obj_path = mod.root_dir / mdef.objects_file
            if obj_path.exists():
                ok(f"  物件文件: {mod_id}/{map_id} → {mdef.objects_file}")
            else:
                fail(f"  物件文件缺失: {mod_id}/{map_id} → {mdef.objects_file}")


# ═══════════════════════════════════════════
#  Test 3: 传送门连接有效性
# ═══════════════════════════════════════════

def test_portal_validity(mm: ModManager):
    section("T3: 传送门连接有效性")

    total_portals = 0
    for mod_id, mod in mm.mods.items():
        for map_id, mdef in mod.maps.items():
            for p in mdef.portals:
                total_portals += 1
                key = f"{mod_id}/{map_id} ({p.col},{p.row}) → {p.target_mod or 'base'}/{p.target_map}"

                # 检查目标是否存在
                target_result = mm.get_map(p.target_mod, p.target_map)
                if target_result:
                    ok(f"  传送门: {key}")
                else:
                    fail(f"  传送门目标不存在: {key}")

    print(f"\n  总计 {total_portals} 个传送门")


# ═══════════════════════════════════════════
#  Test 4: 传送门坐标在边界内
# ═══════════════════════════════════════════

def test_portal_bounds(mm: ModManager):
    section("T4: 传送门坐标边界检查")

    for mod_id, mod in mm.mods.items():
        for map_id, mdef in mod.maps.items():
            # 读取地图文件获取实际尺寸
            map_path = mod.root_dir / mdef.map_file
            try:
                with open(map_path, encoding="utf-8") as f:
                    lines = [l.rstrip("\n") for l in f.readlines()]
                map_rows = len(lines)
                map_cols = max(len(l) for l in lines) if lines else 0
            except FileNotFoundError:
                continue

            for p in mdef.portals:
                key = f"{mod_id}/{map_id} portal@{p.col},{p.row}"

                if 0 <= p.col < map_cols and 0 <= p.row < map_rows:
                    ok(f"  坐标在边界内: {key} (地图 {map_cols}x{map_rows})")
                else:
                    fail(f"  坐标越界: {key} (地图 {map_cols}x{map_rows})")

                # 目标坐标也在目标地图边界内
                tgt = mm.get_map(p.target_mod, p.target_map)
                if tgt:
                    tmod, tmdef = tgt
                    tgt_path = tmod.root_dir / tmdef.map_file
                    try:
                        with open(tgt_path, encoding="utf-8") as f:
                            tgt_lines = [l.rstrip("\n") for l in f.readlines()]
                        tgt_rows = len(tgt_lines)
                        tgt_cols = max(len(l) for l in tgt_lines) if tgt_lines else 0
                        if 0 <= p.target_col < tgt_cols and 0 <= p.target_row < tgt_rows:
                            ok(f"  目标坐标在边界内: {key} → ({p.target_col},{p.target_row}) (目标 {tgt_cols}x{tgt_rows})")
                        else:
                            fail(f"  目标坐标越界: {key} → ({p.target_col},{p.target_row}) (目标 {tgt_cols}x{tgt_rows})")
                    except FileNotFoundError:
                        pass


# ═══════════════════════════════════════════
#  Test 5: 卡牌文件完整性
# ═══════════════════════════════════════════

def test_card_files(mm: ModManager):
    section("T5: 卡牌 JSON 文件完整性")

    required_fields = {"name", "glyph", "desc"}

    for mod_id, mod in mm.mods.items():
        # 卡牌可能位于 cards/ 或 data/cards/
        candidates = [mod.root_dir / "cards"]
        if mod.mod_id == "base":
            candidates.append(mod.root_dir / "data" / "cards")

        for cards_dir in candidates:
            if not cards_dir.exists():
                continue

            for card_file in sorted(cards_dir.glob("*.json")):
                try:
                    with open(card_file, encoding="utf-8") as f:
                        card = json.load(f)
                except json.JSONDecodeError:
                    fail(f"  JSON 解析失败: {mod_id}/{card_file.name}")
                    continue

                missing = required_fields - set(card.keys())
                if missing:
                    fail(f"  缺失字段 {missing}: {mod_id}/{card_file.name}")
                else:
                    ok(f"  卡牌: {mod_id}/{card_file.name} → {card['name']} {card['glyph']}")

    # 汇总
    total = 0
    for m in mm.mods.values():
        for cd in [m.root_dir / "cards", m.root_dir / "data" / "cards"]:
            if cd.exists():
                total += len(list(cd.glob("*.json")))
    print(f"\n  总计 {total} 张卡牌")


# ═══════════════════════════════════════════
#  Test 6: 记忆文件完整性
# ═══════════════════════════════════════════

def test_memory_files(mm: ModManager):
    section("T6: 记忆 JSON 文件完整性")

    required_fields = {"name", "text"}

    for mod_id, mod in mm.mods.items():
        candidates = [mod.root_dir / "memories"]
        if mod.mod_id == "base":
            candidates.append(mod.root_dir / "data" / "memories")

        for mem_dir in candidates:
            if not mem_dir.exists():
                continue

            for mem_file in sorted(mem_dir.glob("*.json")):
                try:
                    with open(mem_file, encoding="utf-8") as f:
                        mem = json.load(f)
                except json.JSONDecodeError:
                    fail(f"  JSON 解析失败: {mod_id}/{mem_file.name}")
                    continue

                missing = required_fields - set(mem.keys())
                if missing:
                    fail(f"  缺失字段 {missing}: {mod_id}/{mem_file.name}")
                else:
                    ok(f"  记忆: {mod_id}/{mem_file.name} → {mem['name']}")

    # 汇总
    total = 0
    for m in mm.mods.values():
        for md in [m.root_dir / "memories", m.root_dir / "data" / "memories"]:
            if md.exists():
                total += len(list(md.glob("*.json")))
    print(f"\n  总计 {total} 个记忆")


# ═══════════════════════════════════════════
#  Test 7: 传送门循环/重复引用检测
# ═══════════════════════════════════════════

def test_portal_dedup(mm: ModManager):
    section("T7: 传送门去重检查")

    seen_entries = set()
    for mod_id, mod in mm.mods.items():
        for map_id, mdef in mod.maps.items():
            for p in mdef.portals:
                entry = (mod_id, map_id, p.col, p.row)
                if entry in seen_entries:
                    fail(f"  重复入口: {mod_id}/{map_id} ({p.col},{p.row})")
                else:
                    seen_entries.add(entry)
                    ok(f"  唯一入口: {mod_id}/{map_id} ({p.col},{p.row}) → {p.target_mod or 'base'}/{p.target_map}")

    print(f"\n  唯一传送门入口: {len(seen_entries)}")


# ═══════════════════════════════════════════
#  Test 8: 物件 JSON 结构检查
# ═══════════════════════════════════════════

def test_objects_schema(mm: ModManager):
    section("T8: 物件 JSON Schema 检查")

    for mod_id, mod in mm.mods.items():
        for map_id, mdef in mod.maps.items():
            obj_path = mod.root_dir / mdef.objects_file
            if not obj_path.exists():
                continue

            try:
                with open(obj_path, encoding="utf-8") as f:
                    obj = json.load(f)
            except json.JSONDecodeError as e:
                fail(f"  JSON 解析失败: {mod_id}/{map_id}")
                continue

            # 检查 interactives
            for item in obj.get("interactives", []):
                if "id" not in item:
                    fail(f"  interactive 缺少 id: {mod_id}/{map_id}")
                elif "col" not in item or "row" not in item:
                    fail(f"  interactive 缺少坐标: {mod_id}/{map_id}/{item['id']}")
                else:
                    ok(f"  interactive: {mod_id}/{map_id}/{item['id']} @({item['col']},{item['row']})")

            # 检查 memory_questions
            for q in obj.get("memory_questions", []):
                required = {"id", "col", "row", "text"}
                missing = required - set(q.keys())
                if missing:
                    fail(f"  memory_question 缺失 {missing}: {mod_id}/{map_id}/{q.get('id','?')}")
                else:
                    ok(f"  question: {mod_id}/{map_id}/{q['id']} @({q['col']},{q['row']})")

    # 汇总
    total_interactives = 0
    total_questions = 0
    for mod_id, mod in mm.mods.items():
        for map_id, mdef in mod.maps.items():
            obj_path = mod.root_dir / mdef.objects_file
            if not obj_path.exists():
                continue
            with open(obj_path, encoding="utf-8") as f:
                obj = json.load(f)
            total_interactives += len(obj.get("interactives", []))
            total_questions += len(obj.get("memory_questions", []))
    print(f"\n  总计 {total_interactives} 个可交互物件, {total_questions} 个记忆问题")


# ═══════════════════════════════════════════
#  Test 9: 卡牌引用完整性
# ═══════════════════════════════════════════

def test_card_references(mm: ModManager):
    section("T9: 跨 Mod 卡牌引用完整性")

    # 收集所有已知卡牌 ID（含 base 的 data/cards/ 和 DLC 的 cards/）
    all_cards = set()
    for mod_id, mod in mm.mods.items():
        for cd in [mod.root_dir / "cards", mod.root_dir / "data" / "cards"]:
            if not cd.exists():
                continue
            for cf in cd.glob("*.json"):
                all_cards.add(cf.stem)

    # 检查地图中的卡牌引用
    for mod_id, mod in mm.mods.items():
        for map_id, mdef in mod.maps.items():
            for card_id, placement in mdef.cards.items():
                if placement is None:
                    # null 表示占位/未放置，跳过
                    continue
                if card_id in all_cards:
                    ok(f"  卡牌引用有效: {mod_id}/{map_id} → {card_id}")
                else:
                    fail(f"  卡牌引用无定义: {mod_id}/{map_id} → {card_id} (未在任何 cards/ 目录找到)")

    # 检查机关中的卡牌引用
    for mod_id, mod in mm.mods.items():
        for map_id, mdef in mod.maps.items():
            for mech in mdef.mechanisms:
                if mech.trigger_type == "CARD_COLLECTED":
                    tid = mech.trigger_id
                    if tid in all_cards:
                        ok(f"  机关卡牌引用有效: {mod_id}/{map_id}::{mech.mech_id} → {tid}")
                    else:
                        fail(f"  机关卡牌引用无定义: {mod_id}/{map_id}::{mech.mech_id} → {tid}")

    print(f"\n  已知卡牌数: {len(all_cards)}")


# ═══════════════════════════════════════════
#  Test 10: players_start 坐标安全
# ═══════════════════════════════════════════

def test_player_start(mm: ModManager):
    section("T10: 玩家出生点安全")

    from core.config import BLOCKED_CHARS, PORTAL_CHARS

    for mod_id, mod in mm.mods.items():
        for map_id, mdef in mod.maps.items():
            col, row = mdef.player_start

            # 读地图
            map_path = mod.root_dir / mdef.map_file
            try:
                with open(map_path, encoding="utf-8") as f:
                    lines = [l.rstrip("\n") for l in f.readlines()]
                if 0 <= row < len(lines) and 0 <= col < len(lines[row]):
                    cell_char = lines[row][col]
                    if cell_char in BLOCKED_CHARS:
                        fail(f"  出生点被阻挡: {mod_id}/{map_id} ({col},{row}) char='{cell_char}'")
                    else:
                        ok(f"  出生点安全: {mod_id}/{map_id} ({col},{row}) char='{cell_char}'")
                else:
                    fail(f"  出生点越界: {mod_id}/{map_id} ({col},{row})")
            except FileNotFoundError:
                warn(f"  地图文件不存在，跳过出生点检查: {mod_id}/{map_id}")


# ═══════════════════════════════════════════
#  Main
# ═══════════════════════════════════════════

def main():
    print("=" * 60)
    print("  carimara_py — Mod/DLC 系统测试套件")
    print("=" * 60)

    # 初始化
    mm = ModManager()

    # 运行所有测试
    test_mod_discovery(mm)
    test_map_files(mm)
    test_portal_validity(mm)
    test_portal_bounds(mm)
    test_card_files(mm)
    test_memory_files(mm)
    test_portal_dedup(mm)
    test_objects_schema(mm)
    test_card_references(mm)
    test_player_start(mm)

    # ── 汇总 ──
    total = TESTS_PASSED + TESTS_FAILED + TESTS_WARNED
    print(f"\n{'='*60}")
    print(f"  测试结果汇总")
    print(f"{'='*60}")
    print(f"  通过: {TESTS_PASSED}/{total}")
    print(f"  失败: {TESTS_FAILED}/{total}")
    if TESTS_WARNED:
        print(f"  警告: {TESTS_WARNED}/{total}")
    print(f"{'='*60}")

    if TESTS_FAILED > 0:
        print(f"\n  ❌ {TESTS_FAILED} 项测试失败！请检查上方 [FAIL] 项。")
        sys.exit(1)
    else:
        print(f"\n  ✅ 全部 {TESTS_PASSED} 项测试通过！")
        sys.exit(0)


if __name__ == "__main__":
    main()
