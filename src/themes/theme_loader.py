"""
Progress Quest Multiverse - 主题加载器

类似 mod 管理器：自动扫描 data/ 目录下的子文件夹，
每个子文件夹是一个完整主题，包含固定名称的 JSON 文件。

主题文件夹结构（8 个标准文件，名称和数量统一）：
  data/
    warcraft/
      meta.json        - 主题元数据（id, name, description, 标签）
      races.json       - 种族列表
      classes.json     - 职业列表
      spells.json      - 法术池
      tasks.json       - 任务目标池
      monsters.json    - 怪物定义
      equipment.json   - 商店装备
      quests.json      - 任务模板
    genshin/
      meta.json
      races.json
      ...（同上 8 个文件）
    pokemon/
      meta.json
      races.json
      ...（同上 8 个文件）

新增主题只需复制一个现有主题文件夹，修改内容即可，无需改任何 Python 代码。
"""

import json
import os
import sys
from typing import Dict, List, Optional

# 添加 src 目录到路径，使 from themes.xxx import xxx 可用
_src_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _src_path not in sys.path:
    sys.path.insert(0, _src_path)

from themes.theme_base import GameTheme, ThemeItem, ThemeMonster, ThemeQuest


# ── 标准 JSON 文件名 ──────────────────────────────────────────

# 每个主题文件夹必须包含的 8 个文件，名称和数量统一
THEME_FILES = [
    "meta.json",        # 主题元数据
    "races.json",       # 种族列表
    "classes.json",     # 职业列表
    "spells.json",      # 法术池
    "tasks.json",       # 任务目标池
    "monsters.json",    # 怪物定义
    "equipment.json",   # 商店装备
    "quests.json",      # 任务模板
]


# ── JSON 字段 → dataclass 的解析函数 ──────────────────────────

def _parse_item(data: dict) -> ThemeItem:
    """将 JSON 字典解析为 ThemeItem"""
    return ThemeItem(
        name=data.get("name", "未知物品"),
        value=data.get("value", 0),
        item_type=data.get("item_type", "misc"),
        stat_bonus=data.get("stat_bonus", {}),
        count=data.get("count", 1),
        level=data.get("level", 1),
    )


def _parse_loot_table(loot_data: list) -> list:
    """将 JSON 战利品表解析为 List[Tuple[ThemeItem, float]]"""
    result = []
    for entry in loot_data:
        item = _parse_item(entry.get("item", {}))
        chance = entry.get("drop_chance", 0.0)
        result.append((item, chance))
    return result


def _parse_monster(data: dict) -> ThemeMonster:
    """将 JSON 字典解析为 ThemeMonster"""
    return ThemeMonster(
        name=data.get("name", "未知怪物"),
        level=data.get("level", 1),
        hp=data.get("hp", 10),
        exp_reward=data.get("exp_reward", 0),
        loot_table=_parse_loot_table(data.get("loot_table", [])),
    )


def _parse_quest(data: dict) -> ThemeQuest:
    """将 JSON 字典解析为 ThemeQuest"""
    reward_item = None
    if data.get("reward_item"):
        reward_item = _parse_item(data["reward_item"])
    return ThemeQuest(
        name=data.get("name", "未知任务"),
        description=data.get("description", ""),
        target_monster=data.get("target_monster", ""),
        target_count=data.get("target_count", 1),
        reward_exp=data.get("reward_exp", 0),
        reward_gold=data.get("reward_gold", 0),
        reward_item=reward_item,
    )


# ── 核心：从主题文件夹加载 ────────────────────────────────────

def _read_json(folder_path: str, filename: str):
    """读取主题文件夹内的某个 JSON 文件

    Returns:
        解析后的 Python 对象，失败返回 None
    """
    fpath = os.path.join(folder_path, filename)
    try:
        with open(fpath, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"[ThemeLoader] 加载 {filename} 失败: {e}")
        return None


def load_theme_from_folder(folder_path: str) -> Optional[GameTheme]:
    """从主题文件夹加载完整主题

    读取文件夹内的 8 个标准 JSON 文件，组装为 GameTheme 实例。

    Args:
        folder_path: 主题文件夹的绝对路径

    Returns:
        GameTheme 实例，缺少必需文件则返回 None
    """
    # 检查必需文件
    missing = [f for f in THEME_FILES
               if not os.path.isfile(os.path.join(folder_path, f))]
    if missing:
        print(f"[ThemeLoader] 主题文件夹 {folder_path} 缺少文件: {missing}")
        return None

    # 读取 meta
    meta = _read_json(folder_path, "meta.json")
    if meta is None:
        return None

    theme = GameTheme(
        name=meta.get("name", "未知主题"),
        description=meta.get("description", ""),
    )
    theme.meta_id = meta.get("id", os.path.basename(folder_path))
    theme.race_label = meta.get("race_label", "种族")
    theme.class_label = meta.get("class_label", "职业")
    theme.monster_label = meta.get("monster_label", "怪物")

    # 读取基础数据
    theme.races = _read_json(folder_path, "races.json") or []
    theme.classes = _read_json(folder_path, "classes.json") or []
    theme.spell_pool = _read_json(folder_path, "spells.json") or []

    # task_targets: JSON 中是 [[verb, noun], ...]，转为 List[Tuple[str, str]]
    raw_targets = _read_json(folder_path, "tasks.json") or []
    theme.task_targets = [tuple(t) for t in raw_targets]

    # 怪物
    monsters_data = _read_json(folder_path, "monsters.json") or []
    theme.monsters = [_parse_monster(m) for m in monsters_data]

    # 商店物品
    shop_data = _read_json(folder_path, "equipment.json") or []
    theme.shop_items = [_parse_item(item) for item in shop_data]

    # 任务模板
    quests_data = _read_json(folder_path, "quests.json") or []
    theme.quest_templates = [_parse_quest(q) for q in quests_data]

    return theme


# ── 主题注册表：自动扫描 data/ 子文件夹 ──────────────────────

# 主题数据根目录（本文件同级 data/ 文件夹）
_THEMES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

# 缓存：theme_id → GameTheme 实例
_theme_cache: Dict[str, GameTheme] = {}


def discover_themes() -> Dict[str, dict]:
    """扫描 data/ 目录下的子文件夹，返回所有可用主题的元信息

    每个子文件夹只要包含 meta.json 就被视为一个主题。

    Returns:
        {theme_id: {"id": ..., "name": ..., "description": ..., "folder": ...}}
    """
    result = {}
    if not os.path.isdir(_THEMES_DIR):
        return result

    for dirname in sorted(os.listdir(_THEMES_DIR)):
        folder_path = os.path.join(_THEMES_DIR, dirname)
        if not os.path.isdir(folder_path):
            continue

        # 检查是否有 meta.json（主题的最低要求）
        meta_path = os.path.join(folder_path, "meta.json")
        if not os.path.isfile(meta_path):
            continue

        # 轻量读取 meta 部分（不解析全部数据）
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue

        theme_id = meta.get("id", dirname)
        result[theme_id] = {
            "id": theme_id,
            "name": meta.get("name", theme_id),
            "description": meta.get("description", ""),
            "race_label": meta.get("race_label", "种族"),
            "class_label": meta.get("class_label", "职业"),
            "monster_label": meta.get("monster_label", "怪物"),
            "folder": folder_path,
        }

    return result


def get_theme(theme_id: str) -> Optional[GameTheme]:
    """按 ID 获取主题实例（带缓存）

    Args:
        theme_id: 主题唯一标识（对应 meta.json 中的 id）

    Returns:
        GameTheme 实例，不存在则返回 None
    """
    if theme_id in _theme_cache:
        return _theme_cache[theme_id]

    themes_info = discover_themes()
    if theme_id not in themes_info:
        return None

    folder = themes_info[theme_id]["folder"]
    theme = load_theme_from_folder(folder)
    if theme:
        _theme_cache[theme_id] = theme

    return theme


def list_theme_ids() -> List[str]:
    """返回所有可用主题 ID 列表"""
    return list(discover_themes().keys())


def list_theme_names() -> Dict[str, str]:
    """返回 {theme_id: display_name} 映射"""
    return {tid: info["name"] for tid, info in discover_themes().items()}


def clear_cache():
    """清空主题缓存（调试/热重载时使用）"""
    _theme_cache.clear()


# ── 自测 ─────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=== Theme Loader 自测 ===\n")

    # 列出所有主题
    themes = discover_themes()
    print(f"发现 {len(themes)} 个主题:")
    for tid, info in themes.items():
        print(f"  - {tid}: {info['name']} ({info['description']})")
        print(f"    文件夹: {info['folder']}")

    # 逐个加载并验证
    print()
    for tid in themes:
        theme = get_theme(tid)
        if not theme:
            print(f"  ❌ {tid}: 加载失败")
            continue

        print(f"  ✅ {tid}: {theme.name}")
        print(f"     种族({theme.race_label}): {len(theme.races)} 个")
        print(f"     职业({theme.class_label}): {len(theme.classes)} 个")
        print(f"     法术池: {len(theme.spell_pool)} 个")
        print(f"     任务目标: {len(theme.task_targets)} 条")
        print(f"     怪物({theme.monster_label}): {len(theme.monsters)} 只")
        print(f"     商店物品: {len(theme.shop_items)} 件")
        print(f"     任务模板: {len(theme.quest_templates)} 个")

        # 测试随机怪物/任务
        m = theme.get_random_monster(10)
        q = theme.get_random_quest()
        print(f"     随机怪物: {m.name if m else '无'}")
        print(f"     随机任务: {q.name if q else '无'}")
        print()

    print("=== 全部通过 ===")
