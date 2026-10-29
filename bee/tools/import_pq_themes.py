# -*- coding: utf-8 -*-
"""导入 pq_multiverse 主题 → bee 主题包（P0：异界 DLC）

用法：
    python tools/import_pq_themes.py [pq_multiverse 项目路径]

    数据源根目录解析顺序（去本地化，命令行优先）：
      1) 命令行参数 [pq_multiverse 项目路径]
      2) 环境变量 PQ_MULTIVERSE_SRC
      3) 由本仓位置推导的候选（<工作区>/pq_multiverse、<工作区>/pq-multiverse、
         <工作区上级>/local/pq-multiverse）
      4) 都不成立则报错退出，并提示应设置哪个变量

读取 <pq_multiverse>/src/themes/data/<theme>/ 下的
meta / monsters / prefixes / spells，转换为 bee 主题包：

    src/resources/themes/<theme_id>/
        meta.json              主题元信息
        enemy_templates.json   bee 敌人模板 schema（DDA 缩放兼容）
        prefix_templates.json  bee 前缀 schema（主题词缀池）
        spells.json            主题法术名（原样保留，供后续消费）
"""
import json
import os
import sys

ENV_SRC = "PQ_MULTIVERSE_SRC"       # 环境变量：pq_multiverse 项目根目录
_SRC_MARKER = os.path.join("src", "themes", "data")   # 数据源特征目录
BEE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_WORKSPACE = os.path.dirname(BEE_ROOT)                 # 本仓所在工作区（G:\repos 一类）
THEMES_OUT = os.path.join(BEE_ROOT, "src", "resources", "themes")


def resolve_src_root(explicit=None):
    """解析 pq_multiverse 项目根目录（去本地化）。

    优先级：命令行参数 > 环境变量 PQ_MULTIVERSE_SRC > 由本仓位置推导的候选 > None（调用方 fail-loud）。
    候选均为相对本仓位置推导，不写死任何本机绝对路径。
    """
    if explicit:
        return explicit
    env = os.environ.get(ENV_SRC, "").strip()
    if env:
        return env
    for cand in (os.path.join(_WORKSPACE, "pq_multiverse"),
                 os.path.join(_WORKSPACE, "pq-multiverse"),
                 os.path.join(os.path.dirname(_WORKSPACE), "local", "pq-multiverse")):
        if os.path.isdir(os.path.join(cand, _SRC_MARKER)):
            return cand
    return None

# PQ 前缀分类 → 中文戏谑版（保留 PQ 幽默感；未收录的原文保留）
PQ_PREFIX_TRANS = {
    "Dead": "已死的", "Comatose": "昏迷的", "Crippled": "残废的", "Sick": "病恹恹的",
    "Undernourished": "营养不良的", "Baby": "婴儿期的", "Preadolescent": "还没长大的",
    "Teenage": "青春期的", "Underage": "未成年的", "Greater": "更强的",
    "Massive": "巨型的", "Enormous": "庞大的", "Giant": "巨人般的",
    "Titanic": "泰坦级的", "Veteran": "老练的", "Cursed": "被诅咒的",
    "Warrior": "战士化的", "Undead": "亡灵化的", "Demon": "恶魔化的",
}


def import_theme(theme_id: str, src_dir: str) -> tuple:
    meta_path = os.path.join(src_dir, "meta.json")
    monsters_path = os.path.join(src_dir, "monsters.json")
    with open(meta_path, encoding="utf-8") as f:
        meta = json.load(f)
    with open(monsters_path, encoding="utf-8") as f:
        monsters = json.load(f)

    out = os.path.join(THEMES_OUT, theme_id)
    os.makedirs(out, exist_ok=True)

    # meta.json
    bee_meta = {
        "id": theme_id,
        "name": meta.get("name", theme_id),
        "description": meta.get("description", ""),
        "source": "pq_multiverse",
    }
    with open(os.path.join(out, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(bee_meta, f, ensure_ascii=False, indent=2)

    # enemy_templates.json（bee schema：DDA 会按 BASE_* 重缩放，这里保留基础值）
    race_label = meta.get("monster_label") or "异界生物"
    enemies = []
    for m in monsters:
        lv = int(m.get("level", 1) or 1)
        enemies.append({
            "name": str(m.get("name", "未知生物")),
            "race": race_label,
            "description": f"{bee_meta['name']}世界的生物",
            "hp": int(m.get("hp", 20) or 20),
            "damage": max(1, lv),
            "defense": max(0, lv // 2),
            "exp": int(m.get("exp_reward", 8) or 8),
            "gold": int(m.get("gold_reward", 4) or 4),
            "loot_table": "normal",
        })
    with open(os.path.join(out, "enemy_templates.json"), "w", encoding="utf-8") as f:
        json.dump(enemies, f, ensure_ascii=False, indent=2)

    # prefix_templates.json（主题词缀池，bee 前缀 schema）
    prefixes, seen = [], set()
    for m in monsters:
        for vals in (m.get("prefixes") or {}).values():
            for v in vals:
                zh = PQ_PREFIX_TRANS.get(str(v)) or str(v).strip()
                if zh and zh not in seen:
                    seen.add(zh)
                    prefixes.append({"type": "", "prefix": zh, "effect": "", "value": 0.0})
    with open(os.path.join(out, "prefix_templates.json"), "w", encoding="utf-8") as f:
        json.dump(prefixes, f, ensure_ascii=False, indent=2)

    # spells.json（原样保留）
    spells = []
    spells_path = os.path.join(src_dir, "spells.json")
    if os.path.isfile(spells_path):
        with open(spells_path, encoding="utf-8") as f:
            spells = json.load(f)
    with open(os.path.join(out, "spells.json"), "w", encoding="utf-8") as f:
        json.dump(spells, f, ensure_ascii=False, indent=2)

    return len(enemies), len(prefixes), len(spells)


def main(src_root=None) -> int:
    src_root = resolve_src_root(src_root)
    if not src_root:
        print("✗ 未找到 pq_multiverse 数据源。")
        print("  请用命令行参数指定，或设置环境变量 "
              f"{ENV_SRC} 指向含 {_SRC_MARKER} 的项目根目录。")
        return 1
    themes_dir = os.path.join(src_root, "src", "themes", "data")
    if not os.path.isdir(themes_dir):
        print("未找到 pq_multiverse 主题目录:", themes_dir)
        return 1
    total = 0
    for theme_id in sorted(os.listdir(themes_dir)):
        d = os.path.join(themes_dir, theme_id)
        if not (os.path.isfile(os.path.join(d, "meta.json"))
                and os.path.isfile(os.path.join(d, "monsters.json"))):
            continue
        try:
            n_enemies, n_prefixes, n_spells = import_theme(theme_id, d)
        except Exception as e:
            print(f"✗ {theme_id} 导入失败: {e}")
            continue
        total += n_enemies
        print(f"✓ {theme_id}: 敌人={n_enemies} 前缀={n_prefixes} 法术={n_spells}")
    print(f"完成：共导入 {total} 个敌人 → {THEMES_OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else None))
