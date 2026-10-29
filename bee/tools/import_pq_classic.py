# -*- coding: utf-8 -*-
"""导入 progress_quest 经典 PQ 内容 → bee 主题包 pq_classic（P1）

用法：
    python tools/import_pq_classic.py [progress_quest 项目路径]

    数据源根目录解析顺序（去本地化，命令行优先）：
      1) 命令行参数 [progress_quest 项目路径]
      2) 环境变量 PQ_CLASSIC_SRC
      3) 由本仓位置推导的同级候选（<工作区>/progress_quest、<工作区>/table-hanging-machine，
         PQ 内容现行落点即 table-hanging-machine/data/pq_*.py）
      4) 都不成立则报错退出，并提示应设置哪个变量

读取 <progress_quest>/data/pq_*.py 模块（怪物/种族/职业/法术/特殊宝物），
生成主题包：

    src/resources/themes/pq_classic/
        meta.json               主题元信息
        enemy_templates.json    180+ PQ 怪物（name/level/loot → bee schema）
        prefix_templates.json   PQ 戏谑种族/职业/变体修饰作词缀
        artifact_config.json    PQ 特殊宝物 → bee 神器 schema（确定性生成）
        spells.json             47 个 PQ 法术名
        races.json / classes.json  原始 PQ 种族/职业（供后续消费）
"""
import importlib.util
import json
import os
import random
import sys

ENV_SRC = "PQ_CLASSIC_SRC"          # 环境变量：progress_quest 项目根目录
_SRC_MARKER = os.path.join("data", "pq_monsters.py")   # 数据源特征文件
BEE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_WORKSPACE = os.path.dirname(BEE_ROOT)                 # 本仓所在工作区（G:\repos 一类）
THEME_OUT = os.path.join(BEE_ROOT, "src", "resources", "themes", "pq_classic")


def resolve_src_root(explicit=None):
    """解析 progress_quest 数据源根目录（去本地化）。

    优先级：命令行参数 > 环境变量 PQ_CLASSIC_SRC > 由本仓位置推导的候选 > None（调用方 fail-loud）。
    候选均为相对本仓位置推导，不写死任何本机绝对路径。
    """
    if explicit:
        return explicit
    env = os.environ.get(ENV_SRC, "").strip()
    if env:
        return env
    for cand in (os.path.join(_WORKSPACE, "progress_quest"),
                 os.path.join(_WORKSPACE, "table-hanging-machine")):
        if os.path.isfile(os.path.join(cand, _SRC_MARKER)):
            return cand
    return None


def load_pq_data_package(data_dir: str) -> dict:
    """以伪包 pq_data 批量加载 progress_quest 数据模块（支持模块间相对导入）"""
    import types
    pkg = types.ModuleType("pq_data")
    pkg.__path__ = [data_dir]
    sys.modules["pq_data"] = pkg
    modules = {}
    for fn in ("pq_equipment", "pq_monsters", "pq_races", "pq_classes",
               "pq_spells", "pq_specials"):
        spec = importlib.util.spec_from_file_location(
            f"pq_data.{fn}", os.path.join(data_dir, fn + ".py"))
        mod = importlib.util.module_from_spec(spec)
        sys.modules[f"pq_data.{fn}"] = mod  # 先注册，供 .pq_equipment 相对导入解析
        spec.loader.exec_module(mod)
        modules[fn] = mod
    return modules


def _collect_string_lists(mod, keywords):
    """从模块中收集名字含关键词的 list[str] 变量内容"""
    out = []
    for var_name, value in vars(mod).items():
        if not isinstance(value, list):
            continue
        if not any(k in var_name for k in keywords):
            continue
        for item in value:
            s = str(item).strip()
            if s and len(s) <= 16:
                out.append(s)
    return out


def main(src_root=None) -> int:
    src_root = resolve_src_root(src_root)
    if not src_root:
        print("✗ 未找到 progress_quest 数据源。")
        print("  请用命令行参数指定，或设置环境变量 "
              f"{ENV_SRC} 指向含 {_SRC_MARKER} 的项目根目录。")
        return 1
    data_dir = os.path.join(src_root, "data")
    if not os.path.isdir(data_dir):
        print("未找到 progress_quest 数据目录:", data_dir)
        return 1

    mods = load_pq_data_package(data_dir)
    pq_monsters = mods["pq_monsters"]
    pq_races = mods["pq_races"]
    pq_classes = mods["pq_classes"]
    pq_spells = mods["pq_spells"]
    pq_equipment = mods["pq_equipment"]
    pq_specials = mods["pq_specials"]

    monsters = getattr(pq_monsters, "MONSTERS", [])
    races = getattr(pq_races, "RACES", {})
    classes = getattr(pq_classes, "CLASSES", {})
    spell_names = getattr(pq_spells, "SPELL_NAMES", [])

    os.makedirs(THEME_OUT, exist_ok=True)

    # meta.json
    meta = {
        "id": "pq_classic",
        "name": "经典 Progress Quest",
        "description": "致敬 2002 年原版 Progress Quest：180+ 怪物、戏谑种族/职业、"
                       "47 个法术与特殊宝物（来自 progress_quest 项目）",
        "source": "progress_quest",
    }
    with open(os.path.join(THEME_OUT, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    # enemy_templates.json（PQ 怪物 (name, level, loot) → bee schema）
    enemies = []
    for entry in monsters:
        try:
            name, lv, loot = entry[0], int(entry[1]), entry[2]
        except Exception:
            continue
        lv = max(1, lv)
        enemies.append({
            "name": str(name),
            "race": "PQ生物",
            "description": "来自经典 Progress Quest 世界的生物",
            "hp": 10 + lv * 8,
            "damage": max(1, lv),
            "defense": max(0, lv // 2),
            "exp": lv * 11,
            "gold": lv * 6,
            "loot_table": "normal",
        })
    with open(os.path.join(THEME_OUT, "enemy_templates.json"), "w", encoding="utf-8") as f:
        json.dump(enemies, f, ensure_ascii=False, indent=2)

    # prefix_templates.json：PQ 种族/职业 + 变体修饰（戏谑词缀池）
    seen, prefixes = set(), []
    for name in list(races.keys()) + list(classes.keys()) +                  _collect_string_lists(pq_monsters, ("变体", "修饰", "VARIANT")):
        p = name if name.endswith("的") else name + "的"
        if p not in seen:
            seen.add(p)
            prefixes.append({"type": "", "prefix": p, "effect": "", "value": 0.0})
    with open(os.path.join(THEME_OUT, "prefix_templates.json"), "w", encoding="utf-8") as f:
        json.dump(prefixes, f, ensure_ascii=False, indent=2)

    # artifact_config.json：PQ 特殊宝物 → bee 神器（种子固定，可复现）
    base = getattr(pq_specials, "SPECIAL_BASE", []) or []
    adj = getattr(pq_specials, "SPECIAL_ADJ", []) or []
    item_of = getattr(pq_equipment, "ITEM_OF", []) or []
    rng = random.Random(42)
    effect_rotation = [
        ("gold", 0.05, "金币获取提升"), ("xp", 0.08, "经验获取提升"),
        ("drop_rate", 0.06, "掉落率提升"), ("damage", 0.10, "物理伤害提升"),
        ("defense", 0.10, "防御提升"),
    ]
    artifacts = []
    for i in range(40):
        b = base[i % len(base)] if base else "宝物"
        a = adj[i % len(adj)] if adj else ""
        o = item_of[i % len(item_of)] if item_of else ""
        full_name = f"{a}{o}{b}" if o else f"{a}{b}"
        etype, evalue, edesc = effect_rotation[i % len(effect_rotation)]
        artifacts.append({
            "神器ID": f"PQSP_{i + 1:03d}",
            "名称": full_name,
            "description": f"经典 PQ 特殊宝物：{edesc}",
            "效果类型": etype,
            "效果值": round(evalue, 2),
            "来源": "pq_special",
            "hp": 1, "damage": 1, "defense": 0,
            "exp": 0, "gold": 0, "loot_table": "",
        })
    with open(os.path.join(THEME_OUT, "artifact_config.json"), "w", encoding="utf-8") as f:
        json.dump(artifacts, f, ensure_ascii=False, indent=2)

    # spells.json / races.json / classes.json（原样保留）
    with open(os.path.join(THEME_OUT, "spells.json"), "w", encoding="utf-8") as f:
        json.dump(spell_names, f, ensure_ascii=False, indent=2)
    with open(os.path.join(THEME_OUT, "races.json"), "w", encoding="utf-8") as f:
        json.dump(races, f, ensure_ascii=False, indent=2)
    with open(os.path.join(THEME_OUT, "classes.json"), "w", encoding="utf-8") as f:
        json.dump(classes, f, ensure_ascii=False, indent=2)

    print(f"✓ pq_classic: 敌人={len(enemies)} 前缀={len(prefixes)} 神器={len(artifacts)} "
          f"法术={len(spell_names)} 种族={len(races)} 职业={len(classes)}")
    print(f"完成 → {THEME_OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else None))
