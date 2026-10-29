"""
内容注册表加载器 — Cordis / 模组管理思路的落地（独立模块，避免与 engine 包循环导入）。

设计目标（来自 P1 调研，避免 game_data.json 膨胀）：
- 核心包 data/game_data.json 保持不变（core module）。
- 每个 P1 子系统一个独立内容包 data/modules/<id>.json。
- 启动时按文件名顺序合并：extend（数组型内容追加，带跨包重复 key 校验）
  与 add（新增顶层键，带碰撞校验）。
- 无构建步骤、零外部依赖、运行时合并（CordIS 式插件生命周期）。

模组 JSON 约定：
{
  "id": "p1_equipment",
  "description": "...",
  "extend": {                      // 追加到既有数组（按 key 去重）
    "skills": [ ... ],             // 允许的数组键见 EXTENDABLE_ARRAYS
    "heroes": [ ... ],
    "challenges": [ ... ],
    "achievements": [ ... ],
    "upgrades": [ ... ],
    "prestige_upgrades": [ ... ]
  },
  "add": {                         // 全新顶层内容键（禁止与核心/其他包碰撞）
    "equipment_slots": [ ... ],
    "equipment_affixes": [ ... ],
    "equipment_sets": [ ... ],
    "golden_variants": [ ... ],
    "events": [ ... ],
    "daily_tasks": [ ... ]
  }
}
"""


import glob
import json
import os


# 允许被 extend 追加的数组型内容键
EXTENDABLE_ARRAYS = (
    "upgrades",
    "skills",
    "heroes",
    "challenges",
    "prestige_upgrades",
    "achievements",
)


def load_content(base_path: str, achievements_path: str, modules_dir: str):
    """加载并合并核心包 + 所有模组包。

    返回 (merged_data, add_content, issues)
    - merged_data: 合并后的完整游戏数据（含 extend 追加的数组）
    - add_content: 各模组 add 的新顶层键字典
    - issues: 校验告警列表（重复 key / 碰撞，均为非致命，已跳过）
    """
    with open(base_path, encoding="utf-8") as f:
        base = json.load(f)
    with open(achievements_path, encoding="utf-8") as f:
        base_achievements = json.load(f)

    merged = dict(base)  # 顶层浅拷贝，避免污染原文件对象
    for k in EXTENDABLE_ARRAYS:
        merged.setdefault(k, [])
    # 成就来自独立文件，作为 base 数组基线
    merged["achievements"] = list(base_achievements)

    add_content: dict = {}
    issues: list = []

    modules = sorted(glob.glob(os.path.join(modules_dir, "*.json")))
    for path in modules:
        with open(path, encoding="utf-8") as f:
            mod = json.load(f)
        mid = mod.get("id", os.path.basename(path))

        # ---- extend：数组追加 + 跨包重复 key 校验 ----
        for ak, items in (mod.get("extend") or {}).items():
            if ak not in EXTENDABLE_ARRAYS:
                issues.append(f"[{mid}] extend 含未知数组 '{ak}'（已忽略）")
                continue
            existing_keys = {
                x.get("key") for x in merged.get(ak, []) if isinstance(x, dict)
            }
            for it in items:
                ik = it.get("key") if isinstance(it, dict) else None
                if ik is None:
                    issues.append(f"[{mid}] extend.{ak} 存在无 key 条目（已忽略）")
                    continue
                if ik in existing_keys:
                    issues.append(f"[{mid}] 重复 key '{ik}'（已跳过）")
                    continue
                merged[ak].append(it)
                existing_keys.add(ik)

        # ---- add：新顶层键 + 碰撞校验 ----
        for nk, nv in (mod.get("add") or {}).items():
            if nk in merged:
                issues.append(f"[{mid}] add 键 '{nk}' 与核心碰撞（已跳过）")
                continue
            if nk in add_content:
                issues.append(f"[{mid}] add 键 '{nk}' 与其他模组碰撞（已跳过）")
                continue
            add_content[nk] = nv

    return merged, add_content, issues
