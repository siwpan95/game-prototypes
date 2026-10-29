"""配置表结构校验（规划 T4.4）：列名/ID 唯一/引用有效/数值合法

作为冒烟测试纳入 run_all，配置被改坏时第一时间报错。
"""
import os
import shutil
import sys
import tempfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)
sys.path.insert(0, os.path.join(REPO_ROOT, "tests"))

import tk_stub  # noqa: E402

tk_stub.install()

from data import ConfigLoader  # noqa: E402


def _check_unique(ids, label, errors):
    seen = set()
    for i in ids:
        if i in seen:
            errors.append(f"{label}: ID 重复 {i}")
        seen.add(i)


def _check_refs(refs, valid_ids, label, errors):
    for ref in refs:
        if ref != 0 and ref not in valid_ids:
            errors.append(f"{label}: 引用不存在 {ref}")


def main():
    tmp_dir = tempfile.mkdtemp(prefix="maga_validatetest_")
    errors = []
    try:
        config_path = os.path.join(tmp_dir, "config.xlsx")
        shutil.copy(os.path.join(REPO_ROOT, "config.xlsx"), config_path)
        config = ConfigLoader(config_path)
        if not config.load_all():
            print("配置加载失败")
            return 1

        # ── ID 唯一性 ──
        _check_unique(config.enemies.keys(), "Enemies", errors)
        _check_unique(config.items.keys(), "Items", errors)
        _check_unique(config.chassis.keys(), "Chassis", errors)
        _check_unique(config.engines.keys(), "Engines", errors)
        _check_unique(config.cunits.keys(), "CUnits", errors)
        _check_unique(config.weapons.keys(), "Weapons", errors)
        _check_unique(config.vehicles.keys(), "Vehicles", errors)
        _check_unique(config.maps.keys(), "Maps", errors)
        _check_unique(config.skills.keys(), "Skills", errors)
        _check_unique(config.bounties.keys(), "Bounties", errors)

        # ── 数值合法性 ──
        for e in config.enemies.values():
            if e.hp <= 0:
                errors.append(f"Enemies {e.name}: HP <= 0")
            if not (0 <= e.encounter_rate <= 1):
                errors.append(f"Enemies {e.name}: 遭遇率越界 {e.encounter_rate}")
            if e.drop_item_id and e.drop_item_id not in config.items:
                errors.append(f"Enemies {e.name}: 掉落物品不存在 {e.drop_item_id}")
            if not (0 <= e.drop_rate <= 1):
                errors.append(f"Enemies {e.name}: 掉落率越界 {e.drop_rate}")
            if e.is_bounty and e.encounter_rate != 0:
                errors.append(f"Enemies {e.name}: 赏金首遭遇率必须为 0")
        for it in config.items.values():
            if it.price < 0:
                errors.append(f"Items {it.name}: 价格为负")
            if it.equip_slot and it.equip_slot not in ("武器", "头", "身", "手", "鞋"):
                errors.append(f"Items {it.name}: 装备槽位非法 {it.equip_slot}")
        for v in config.vehicles.values():
            if v.chassis_id not in config.chassis:
                errors.append(f"Vehicles {v.name}: 底盘不存在 {v.chassis_id}")
            if v.engine_id not in config.engines:
                errors.append(f"Vehicles {v.name}: 引擎不存在 {v.engine_id}")
            if v.cunit_id not in config.cunits:
                errors.append(f"Vehicles {v.name}: C装置不存在 {v.cunit_id}")
            for wid in v.main_weapon_ids + v.sub_weapon_ids + v.se_weapon_ids:
                if wid not in config.weapons:
                    errors.append(f"Vehicles {v.name}: 武器不存在 {wid}")
            if v.acquire_type not in ("default", "site", "bounty"):
                errors.append(f"Vehicles {v.name}: 获取方式非法 {v.acquire_type}")
        for m in config.maps.values():
            if m.infinite and (m.entrance_x != -1 or m.entrance_y != -1):
                errors.append(f"Maps {m.name}: 无限地图不应有固定入口")
        for b in config.bounties.values():
            if b.enemy_id not in config.enemies:
                errors.append(f"Bounties {b.name}: 敌人不存在 {b.enemy_id}")
            elif not config.enemies[b.enemy_id].is_bounty:
                errors.append(f"Bounties {b.name}: 引用的敌人不是赏金首专用")
            if b.reward <= 0:
                errors.append(f"Bounties {b.name}: 悬赏金非正")
        for q in config.quests.values():
            if q.type == "kill" and q.target_id not in config.enemies:
                errors.append(f"Quests {q.name}: kill 目标敌人不存在 {q.target_id}")
            if q.type == "collect" and q.target_id not in config.items:
                errors.append(f"Quests {q.name}: collect 目标物品不存在 {q.target_id}")
            if q.type == "explore" and q.target_id not in config.maps:
                errors.append(f"Quests {q.name}: explore 目标地图不存在 {q.target_id}")
        for s in config.shops.values():
            for iid in s.items:
                if iid not in config.items:
                    errors.append(f"Shops {s.name}: 商品不存在 {iid}")
                elif config.items[iid].price <= 0:
                    errors.append(f"Shops {s.name}: 商品 {iid} 价格非正（不可售）")
        for sk in config.skills.values():
            if sk.class_id not in {0} | set(config.classes.keys()):
                errors.append(f"Skills {sk.name}: 职业限定不存在 {sk.class_id}")
        # 赏金首必掉（掉率 1.0）检查四面镜支线可行性
        drops_100 = {e.drop_item_id for e in config.enemies.values()
                     if e.drop_rate >= 1.0}
        if not {21, 22, 23, 24} <= drops_100:
            errors.append("四面镜支线损坏：四镜片必须由赏金首必掉")

        if errors:
            for err in errors:
                print(f"[配置错误] {err}")
            print(f"共 {len(errors)} 处配置问题")
            return 1

        print("SMOKE OK: 配置表校验全部通过"
              f"（{len(config.enemies)}敌/{len(config.items)}品/{len(config.vehicles)}车/"
              f"{len(config.maps)}图/{len(config.quests)}任务/{len(config.bounties)}赏金首）")
        return 0
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
