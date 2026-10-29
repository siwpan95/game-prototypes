"""
Mod/DLC 脚手架工具 — 快速创建新 Mod 目录结构
=============================================
用法:
    # 交互式创建
    python tools/create_mod.py

    # 命令行创建
    python tools/create_mod.py --id my_mod --name "我的地图" --maps 2

    # 只验证现有 Mod
    python tools/create_mod.py --validate
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODS_DIR = ROOT / "mods"

# ── 默认模板 ──

DEFAULT_MOD_JSON = """{{
  "mod_id": "{mod_id}",
  "name": "{name}",
  "version": "1.0.0",
  "description": "{description}",
  "maps": [{{
    "map_id": "{first_map_id}",
    "name": "{first_map_name}",
    "map_file": "maps/{first_map_id}.txt",
    "player_start": {{"col": {player_col}, "row": {player_row}}},
    "objects_file": "objects/{first_map_id}.json",
    "cards": {{}},
    "portals": [{portals}],
    "mechanisms": []
  }}]
}}"""

DEFAULT_MAP_TXT = """{border_line}
{header_line}
{blank_line}
{wall_line}
{content_lines}
{wall_line}
{blank_line}
{border_line}
"""

DEFAULT_OBJECTS_JSON = """{
  "interactives": [],
  "memory_questions": []
}"""

DEFAULT_CARD_JSON = """{{
  "name": "{name}",
  "glyph": "{glyph}",
  "desc": "{desc}"
}}"""

DEFAULT_MEMORY_JSON = """{{
  "name": "{name}",
  "sanity_cost": 5,
  "text": "{text}"
}}"""


def ask(prompt, default=""):
    """交互式询问，按 Enter 使用默认值。"""
    d = f" [{default}]" if default else ""
    val = input(f"  {prompt}{d}: ").strip()
    return val if val else default


def create_mod(mod_id, name, description, maps_count, has_portal=True, force=False):
    """创建新 Mod 目录和所有模板文件。"""
    mod_dir = MODS_DIR / mod_id
    if mod_dir.exists():
        if not force:
            print(f"  ⚠️  Mod 目录已存在: {mod_dir}")
            ans = input("  覆盖? [y/N]: ").strip().lower()
            if ans != "y":
                print("  已取消。")
                return
        else:
            print(f"  ⚠️  覆盖已有 Mod: {mod_id}")

    width, height = 40, 32
    border = "墙"
    entry_row = height // 2
    entry_col = width - 2

    for mi in range(maps_count):
        map_id = f"{mod_id}_map{mi+1:02d}" if maps_count > 1 else f"{mod_id}_entrance"
        map_name = name if maps_count == 1 else f"{name} 第{mi+1}层"

        # 创建目录
        for sub in ["maps", "objects", "cards", "memories"]:
            (mod_dir / sub).mkdir(parents=True, exist_ok=True)

        # ── mod.json ──
        if mi == 0:
            portals_str = ""
            if has_portal:
                portals_str = f'''
        {{
          "col": {entry_col}, "row": {entry_row},
          "char": "→",
          "target_mod": null,
          "target_map": "mansion",
          "target_col": 1, "target_row": 13
        }}'''
            mod_json = DEFAULT_MOD_JSON.format(
                mod_id=mod_id,
                name=name,
                description=description,
                first_map_id=map_id,
                first_map_name=map_name,
                player_col=1,
                player_row=entry_row,
                portals=portals_str.lstrip(),
            )
            (mod_dir / "mod.json").write_text(mod_json, encoding="utf-8")

        # ── 地图 .txt ──
        map_lines = []
        # 上边界
        map_lines.append(border * width)
        # 标题行
        title = f"《{map_name}》".center(width - 2, " ")
        map_lines.append(f"{border}{title}{border}")
        # 空白行
        for _ in range(3):
            map_lines.append(f"{border}{'░' * (width - 2)}{border}")
        # 墙壁行
        wall_spaces = "░" * ((width - 6) // 2)
        map_lines.append(f"{border}{border}░{wall_spaces}门{wall_spaces}░{border}{border}")
        # 内容行
        for i in range(height - 9):
            if i == height // 2 - 5:
                map_lines.append(f"{border}{'░' * (width - 2)}{border}")
            else:
                map_lines.append(f"{border}{'░' * (width - 2)}{border}")
        # 下墙壁
        map_lines.append(f"{border}{border}{'░' * (width - 4)}{border}{border}")
        # 下空白
        for _ in range(2):
            map_lines.append(f"{border}{'░' * (width - 2)}{border}")
        # 下边界
        map_lines.append(border * width)

        map_path = mod_dir / "maps" / f"{map_id}.txt"
        map_path.write_text("\n".join(map_lines), encoding="utf-8")

        # ── objects.json ──
        obj_path = mod_dir / "objects" / f"{map_id}.json"
        obj_path.write_text(DEFAULT_OBJECTS_JSON, encoding="utf-8")

        # ── 示例卡牌 ──
        card_id = f"{mod_id}_sample_{mi+1:02d}"
        card_json = DEFAULT_CARD_JSON.format(
            name=f"示例卡牌{mi+1}",
            glyph="卡",
            desc=f"这是{map_name}中的一张示例卡牌。",
        )
        (mod_dir / "cards" / f"{card_id}.json").write_text(card_json, encoding="utf-8")

        # ── 示例记忆 ──
        mem_id = f"{mod_id}_memory_{mi+1:02d}"
        mem_json = DEFAULT_MEMORY_JSON.format(
            name=f"示例记忆{mi+1}",
            text=f"你站在{map_name}中，周围是陌生的文字。这里的一切都笼罩在神秘的寂静之中……",
        )
        (mod_dir / "memories" / f"{mem_id}.json").write_text(mem_json, encoding="utf-8")

        # 添加物件到 objects.json
        if mi == 0:
            obj_data = json.loads(obj_path.read_text(encoding="utf-8"))
            obj_data["interactives"].append({
                "id": mem_id,
                "col": 5, "row": 5,
                "hitbox_w": 1, "hitbox_h": 1,
            })
            obj_path.write_text(
                json.dumps(obj_data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

    print(f"\n  ✅ Mod 创建完成: {mod_dir}")
    print(f"     地图: {maps_count} 张")
    print(f"     卡牌: {maps_count} 张（示例）")
    print(f"     记忆: {maps_count} 个（示例）")
    if has_portal:
        print(f"     传送门: 已添加返回宅邸的入口")

    # ── 提示修改 base_mod.json ──
    print(f"\n  📌 如需从宅邸进入此 Mod，请编辑 data/base_mod.json")
    print(f"     在 \"portals\" 数组中添加如下条目：")
    print(f"     {{")
    print(f"       \"col\": X, \"row\": Y,")
    print(f"       \"char\": \"▼\",")
    print(f"       \"target_mod\": \"{mod_id}\",")
    print(f"       \"target_map\": \"{mod_id}_entrance\",")
    print(f"       \"target_col\": 1, \"target_row\": {height // 2}")
    print(f"     }}")


def validate_existing():
    """验证所有现有 Mod 的完整性。"""
    from core.mod_loader import ModManager
    mm = ModManager()
    print(f"\n  发现 {len(mm.mods)} 个 Mod:\n")
    for mod_id, mod in mm.mods.items():
        maps = list(mod.maps.keys())
        total_cards = len(list((mod.root_dir / "cards").glob("*.json"))) if (mod.root_dir / "cards").exists() else 0
        total_mems = len(list((mod.root_dir / "memories").glob("*.json"))) if (mod.root_dir / "memories").exists() else 0
        print(f"  [{mod_id}] {mod.name}")
        print(f"      地图: {maps}")
        print(f"      卡牌: {total_cards}   记忆: {total_mems}")
        for map_id, mdef in mod.maps.items():
            map_ok = (mod.root_dir / mdef.map_file).exists()
            obj_ok = (mod.root_dir / mdef.objects_file).exists()
            status = "✅" if (map_ok and obj_ok) else "⚠️"
            print(f"      {status} {map_id}: map={'OK' if map_ok else 'MISSING'} objects={'OK' if obj_ok else 'MISSING'}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="carimara_py Mod/DLC 脚手架工具")
    parser.add_argument("--id", help="Mod ID (如 my_mod)")
    parser.add_argument("--name", help="Mod 名称 (如 我的模组)")
    parser.add_argument("--desc", default="", help="Mod 描述")
    parser.add_argument("--maps", type=int, default=1, help="地图数量 (默认 1)")
    parser.add_argument("--no-portal", action="store_true", help="不创建返回传送门")
    parser.add_argument("--force", action="store_true", help="强制覆盖已有 Mod")
    parser.add_argument("--validate", action="store_true", help="验证现有 Mod")
    args = parser.parse_args()

    if args.validate:
        validate_existing()
        return

    print("\n" + "=" * 50)
    print("  carimara_py — Mod/DLC 脚手架工具")
    print("=" * 50)

    if args.id and args.name:
        # 命令行模式
        mod_id = args.id
        name = args.name
        desc = args.desc or f"{name}的扩展内容"
        maps = args.maps
        portal = not args.no_portal
        force = args.force or True  # CLI 模式默认覆盖
        create_mod(mod_id, name, desc, maps, has_portal=portal, force=force)
        return
    else:
        # 交互式模式
        print("\n  创建新 Mod/DLC\n")
        mod_id = ask("Mod ID (英文, 如 my_dungeon)")
        if not mod_id:
            print("  已取消。")
            return
        name = ask("Mod 名称 (中文显示名)")
        if not name:
            print("  已取消。")
            return
        desc = ask("Mod 描述", f"{name}的扩展内容")
        maps = int(ask("地图数量", "1"))
        portal = ask("创建返回宅邸的传送门?", "y").lower() != "n"
        create_mod(mod_id, name, desc, maps, has_portal=portal)


if __name__ == "__main__":
    main()
