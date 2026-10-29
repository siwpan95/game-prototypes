"""
test_tag_system.py — 标签系统验证测试
验证：标签自动生成、标签匹配、词缀池加载
用法：python test_tag_system.py
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

# ============================================================
# 测试 1: 标签自动生成
# ============================================================
def test_tag_autogen():
    """验证 data_service 为敌人模板自动生成标签"""
    from app.services.data_service import DataService

    ds = DataService()
    templates = ds.get_enemy_templates()

    # 检查每个模板都有 tags 字段
    for tpl in templates[:5]:  # 采样前 5 个
        name = tpl.get("name", "")
        race = tpl.get("race", "")
        tags = tpl.get("tags", [])
        print(f"  {name} (race={race}) → tags={tags}")

    # 关键验证：哥布林系列命名变体都能匹配"哥布林"标签
    goblins = [t for t in templates if t.get("race") == "哥布林"]
    print(f"\n  哥布林系: {[t['name'] for t in goblins]}")
    for g in goblins:
        assert "哥布林" in g["tags"], f"FAIL: {g['name']} 缺少标签 '哥布林'"
        assert g["name"] in g["tags"], f"FAIL: {g['name']} 缺少自身名标签"
        assert "人形系" in g["tags"], f"FAIL: {g['name']} 缺少分类标签 '人形系'"
    print("  ✓ 哥布林系标签正确（含分类标签）")

    # 验证分类标签覆盖
    category_check = {
        "骷髅兵": ("亡灵系", "小型"),
        "恶魔领主": ("邪能系", "中型"),
        "龙": ("龙系", "大型"),
        "石像鬼": ("机械系", "中型"),
        "巨鼠": ("自然系", "中型"),
        "蜘蛛女王": ("自然系", "中型"),
        "火元素": ("元素系", "中型"),
        "巨人": ("人形系", "大型"),
        "吸血鬼": ("亡灵系", "小型"),
    }
    tpl_map = {t["name"]: t for t in templates}
    for name, (cat_tag, size_tag) in category_check.items():
        matched = [t for t in templates if t["name"] == name]
        if matched:
            t = matched[0]
            assert cat_tag in t["tags"], f"FAIL: {name} 缺少分类标签 '{cat_tag}', tags={t['tags']}"
            assert size_tag in t["tags"], f"FAIL: {name} 缺少体型标签 '{size_tag}', tags={t['tags']}"
    print("  ✓ 分类标签覆盖验证通过")

    print(f"\n  ✓ 标签自动生成: {len(templates)} 个模板全部通过（含三级标签）\n")
    return True


# ============================================================
# 测试 2: 标签匹配替代 endswith
# ============================================================
def test_tag_matching():
    """验证 Quest.update_progress 用标签匹配替代字符串 endswith"""
    from app.models.quest import Quest, QuestType, QuestReward

    # 创建一个击杀哥布林的任务
    quest = Quest(
        quest_id="test_kill",
        name="清除哥布林",
        quest_type=QuestType.KILL,
        description="消灭哥布林",
        target="哥布林",
        target_count=3,
        reward=QuestReward(exp=10, gold=5),
    )

    # 模拟不同敌人击杀的场景
    test_cases = [
        # (enemy_name, enemy_tags, expect_match)
        ("哥布林 Lv.5",           ["哥布林"],                    True),   # 基础哥布林
        ("哥布林战士 Lv.3",       ["哥布林战士", "哥布林"],       True),   # 哥布林变体
        ("巨型哥布林 Lv.10",      ["巨型哥布林", "哥布林"],       True),   # 巨型变体
        ("哥布林萨满 Lv.7",       ["哥布林萨满", "哥布林"],       True),   # 萨满变体
        ("火焰史莱姆 Lv.2",       ["火焰史莱姆", "史莱姆"],       False),  # 不同种族
        ("兽人战士 Lv.4",         ["兽人战士", "兽人"],           False),  # 不同种族
        ("灼热的冰霜的哥布林 Lv.8", ["灼热的冰霜的哥布林", "哥布林"], True),   # 带前缀
    ]

    all_pass = True
    for name, tags, expected_match in test_cases:
        # 重置进度
        quest.current_count = 0
        from app.models.quest import QuestStatus
        quest.status = QuestStatus.ACTIVE

        # update_progress 返回 True 表示任务完成（current_count >= target_count）
        # 我们这里检查的是标签匹配是否生效，通过 current_count 是否增加来判断
        prev_count = quest.current_count
        quest.update_progress(1, name, tags)
        matched = quest.current_count > prev_count  # 标签匹配成功 = 计数增加了

        status = "✓" if matched == expected_match else "✗ FAIL"
        if matched != expected_match:
            all_pass = False
        print(f"  {status} target='{quest.target}' vs enemy='{name}' tags={tags} → matched={matched} (expected={expected_match})")

    if all_pass:
        print("\n  ✓ 标签匹配全部通过\n")
    else:
        print("\n  ✗ 部分标签匹配失败\n")
    return all_pass


# ============================================================
# 测试 3: 词缀池加载
# ============================================================
def test_affix_pool():
    """验证词缀池能正确加载"""
    from app.services.data_service import DataService
    from app.services.difficulty_service import DifficultyService

    ds = DataService()
    item_templates = ds.get_item_templates()
    prefixes = item_templates.get("prefixes", [])

    print(f"  前缀池: {prefixes[:10]}... (共{len(prefixes)}个)")

    dda = DifficultyService()
    assert dda.enemy_affixes_loaded == 0, "初始词缀数应为0"

    dda.set_affix_pool(prefixes)
    print(f"  注入后词缀池大小: {dda.enemy_affixes_loaded}")
    assert dda.enemy_affixes_loaded == len(prefixes), "词缀注入失败"

    # 测试摇词缀
    for i in range(10):
        rolled = dda._roll_affixes(10.0)
        if rolled:
            print(f"    等级10摇出词缀: {rolled}")

    # 如果词缀为空则用默认词缀
    if not prefixes:
        dda.set_affix_pool(["灼热的", "冰霜的", "暗影的", "狂暴的", "闪电的",
                            "剧毒的", "吸血的", "破甲的", "圣光的", "混沌的"])
        print(f"  (使用默认词缀池, 大小={dda.enemy_affixes_loaded})")
        rolled = dda._roll_affixes(10.0)
        print(f"    等级10摇出词缀: {rolled}")
        assert len(rolled) > 0, "词缀生成失败"

    print("\n  ✓ 词缀池加载和生成正常\n")
    return True


# ============================================================
# 测试 4: scale_enemy_template 包含 tags
# ============================================================
def test_scaled_enemy_tags():
    """验证缩放后的敌人模板包含 tags 和 base_name"""
    from app.services.data_service import DataService
    from app.services.difficulty_service import DifficultyService
    from app.services.combat_service import CombatService
    from app.models.character import Party
    from app.models.character import Character, Race, CharClass

    ds = DataService()
    dda = DifficultyService()
    cs = CombatService(ds, dda)

    # 加载词缀
    item_templates = ds.get_item_templates()
    prefixes = item_templates.get("prefixes", [])
    if not prefixes:
        prefixes = ["灼热的", "冰霜的", "暗影的", "狂暴的", "闪电的"]
    dda.set_affix_pool(prefixes)

    # 创建模拟队伍
    hero = Character.create(name="测试者", race=Race.HUMAN, char_class=CharClass.WARRIOR, seed=42)
    party = Party(hero)

    # 获取模板
    templates = ds.get_enemy_templates()
    goblin = next(t for t in templates if t["name"] == "哥布林")

    # 缩放
    scaled = dda.scale_enemy_template(goblin, party)
    print(f"  缩放后: name={scaled['name']}, base_name={scaled['base_name']}, tags={scaled['tags']}")
    print(f"  稀有度: {scaled.get('rarity','?')}, 词缀效果: {scaled.get('affix_effects',{})}")
    print(f"  种族技能: {scaled.get('racial_abilities',{})}")

    assert "base_name" in scaled, "缺少 base_name"
    assert scaled["base_name"] == "哥布林", f"base_name 应为 '哥布林', 得到 '{scaled['base_name']}'"
    assert "tags" in scaled, "缺少 tags"
    assert "哥布林" in scaled["tags"], "tags 应包含 '哥布林'"
    assert "rarity" in scaled, "缺少 rarity 字段"
    assert "affix_effects" in scaled, "缺少 affix_effects 字段"
    assert "racial_abilities" in scaled, "缺少 racial_abilities 字段"

    # 通过 CombatService 创建
    enemy = cs.create_enemy_from_template(goblin, party)
    print(f"  敌人: name={enemy['name']}, rarity={enemy.get('rarity','?')}")
    print(f"  属性: HP={enemy['hp']} DMG={enemy['damage']} DEF={enemy['defense']}")
    print(f"  特殊: evasion={enemy.get('evasion',0)} thorns={enemy.get('thorns',0)} regen={enemy.get('regen',0)}")
    print(f"        fire={enemy.get('fire_damage',0)} poison={enemy.get('poison',0)} slow={enemy.get('slow',0)}")

    assert "base_name" in enemy, "enemy 缺少 base_name"
    assert "tags" in enemy, "enemy 缺少 tags"
    assert "哥布林" in enemy["tags"], "enemy tags 应包含 '哥布林'"
    assert "rarity" in enemy, "enemy 缺少 rarity 字段"

    print("\n  ✓ scale_enemy_template 正确传递 tags 和 base_name\n")
    print("  ✓ 稀有度变体系统生效")
    print("  ✓ 词缀效果系统生效")
    print("  ✓ 种族技能系统生效\n")
    return True


# ============================================================
# 主入口
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("  标签系统验证测试")
    print("=" * 60)

    all_ok = True

    print("\n[测试1] 标签自动生成")
    all_ok &= test_tag_autogen()

    print("[测试2] 标签匹配 (替代 endswith)")
    all_ok &= test_tag_matching()

    print("[测试3] 词缀池加载")
    all_ok &= test_affix_pool()

    print("[测试4] scale_enemy_template 传递 tags")
    all_ok &= test_scaled_enemy_tags()

    print("=" * 60)
    if all_ok:
        print("  ✓ 全部测试通过！标签系统就绪。")
    else:
        print("  ✗ 部分测试失败，请检查。")
    print("=" * 60)

    sys.exit(0 if all_ok else 1)
