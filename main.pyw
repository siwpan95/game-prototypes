"""
Progress Quest v2 — 主入口 + 游戏循环。

改动：
- 移除章节限怪逻辑，改为按等级生成怪物
- 全自动角色创建（无存档时随机生成）
- PQ 风格的法术/装备/特殊宝物
- 章节改为纯进度标记
"""
import time
import random
import json
import os
import threading
import pystray
from PIL import Image, ImageDraw
from game_engine import (
    Player, Monster, Spell, Quest, SpecialItem,
    pq_random_spell,
)
from excel_writer import write_game_to_excel
from config_loader import load_all_config
from data import ACTS, generate_name, generate_special
from data.pq_acts import get_current_act as pq_get_act
from data.pq_monsters import get_target_level

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SAVE_FILE = os.path.join(BASE_DIR, "save.json")
MAX_ACTIVE_QUESTS = 5


# ==================== 图标 ====================

def _create_icon_image():
    img = Image.new("RGBA", (64, 64), (30, 30, 30, 255))
    draw = ImageDraw.Draw(img)
    draw.polygon([(32, 4), (56, 32), (32, 60), (8, 32)],
                 fill=(218, 165, 32, 255))
    draw.polygon([(32, 12), (48, 32), (32, 52), (16, 32)],
                 fill=(40, 40, 40, 255))
    draw.text((18, 18), "PQ", fill=(218, 165, 32, 255))
    return img


# ==================== 存档 ====================

def load_or_auto_create(config: dict) -> Player:
    """读档 / Excel 配置创角 / 全自动创角"""
    # 优先读档
    if os.path.exists(SAVE_FILE):
        try:
            with open(SAVE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            player = Player.from_save_dict(data)
            if player.hp <= 0:
                player.hp = player.max_hp // 2
                player.combat_log.append("💀 从存档恢复，HP减半")
            print(f"[存档] 读取：{player.name} Lv.{player.level} "
                  f"金币:{player.gold}")
            return player
        except Exception as e:
            print(f"[存档] 损坏 ({e})，重新创建")

    # Excel 配置创角（如果 config.xlsx 有角色配置）
    player_config = config.get("player", {})
    if player_config and player_config.get("姓名"):
        return Player.from_config(
            player_config, config.get("equipment", {}),
            config.get("inventory", {}), config.get("quests", []),
        )

    # 全自动创建
    player = Player.auto_create()
    print(f"[新角色] {player.name} — {player.race} {player.klass}")
    return player


def save_player(player: Player):
    with open(SAVE_FILE, "w", encoding="utf-8") as f:
        json.dump(player.to_save_dict(), f, ensure_ascii=False, indent=2)


# ==================== 辅助 ====================

def _build_lookup(quest_list: list):
    """构建任务名称查找字典"""
    return {q["name"]: q for q in quest_list}


def _fill_quests(player: Player, quests_by_name: dict):
    """维持 MAX_ACTIVE_QUESTS 个活跃任务，优先选玩家等级±5范围内的"""
    active = [q for q in player.quests if not q.completed]
    needed = MAX_ACTIVE_QUESTS - len(active)
    if needed <= 0:
        return

    # 从所有任务池中选未接过的
    pool = [n for n in quests_by_name
            if n not in [q.name for q in player.quests]]

    if not pool:
        pool = list(quests_by_name.keys())

    # 按目标等级与玩家等级的匹配度排序：±5级内优先
    def _level_score(quest_name: str) -> int:
        tpl = quests_by_name.get(quest_name, {})
        target_level = get_target_level(
            tpl.get("target", ""), tpl.get("target_type", "击杀"))
        diff = abs(target_level - player.level)
        return diff  # 越小越好

    pool.sort(key=_level_score)

    for name in pool:
        if needed <= 0:
            break
        tpl = quests_by_name[name]
        q = Quest(
            tpl["name"],
            tpl.get("target_type", "收集"),
            tpl["target"],
            tpl["required"],
            tpl.get("reward_type", "金币"),
            tpl.get("reward_value", "50"),
        )
        player.quests.append(q)
        player.combat_log.append(f"📋 接受任务：{q.name}")
        needed -= 1


def _generate_quest_from_pq(player: Player):
    """
    无 config.xlsx 任务时，动态生成 PQ 风格任务。
    根据玩家当前状态生成收集/击杀任务。
    """
    quest_types = ["收集", "击杀"]
    qtype = random.choice(quest_types)

    if qtype == "收集":
        # 收集怪物的掉落物
        drops = ["鼠尾巴", "兽皮", "骨片", "黏液", "尖牙", "羽毛", "水晶", "符文石"]
        target = random.choice(drops)
        required = random.randint(3, 10)
    else:
        # 击杀怪物
        monster_names = [
            "狗头人", "哥布林", "兽人", "巨魔", "骷髅",
            "蜘蛛", "蝙蝠", "怨灵", "魔像", "幼龙",
        ]
        target = random.choice(monster_names)
        required = random.randint(1, 5)

    reward_types = ["金币", "装备", "特殊宝物", "属性", "法术"]
    rtype = random.choice(reward_types)

    if rtype == "金币":
        rval = str(random.randint(50, 500))
    elif rtype == "装备":
        rval = "随机装备"
    elif rtype == "特殊宝物":
        rval = "特殊宝物"
    elif rtype == "属性":
        stats = ["力量", "体质", "敏捷", "智力", "智慧", "魅力"]
        rval = f"{random.choice(stats)}+{random.randint(1, 3)}"
    else:  # 法术
        rval = "随机法术"

    return Quest(
        name=f"{'击败' if qtype == '击杀' else '收集'} {target}",
        target_type=qtype,
        target=target,
        required=required,
        reward_type=rtype,
        reward_value=rval,
    )


def _auto_fill_quests(player: Player, quests_by_name: dict):
    """自动填充任务：优先 config 任务池，否则动态生成"""
    active = [q for q in player.quests if not q.completed]
    needed = MAX_ACTIVE_QUESTS - len(active)
    if needed <= 0:
        return

    if quests_by_name:
        _fill_quests(player, quests_by_name)
    else:
        for _ in range(needed):
            q = _generate_quest_from_pq(player)
            player.quests.append(q)
            player.combat_log.append(f"📋 接受任务：{q.name}")


def _on_level_up(player: Player, spell_templates: list):
    """升级时送一个法术（优先 PQ 随机法术，其次 config 法术）"""
    # 50% 概率用 PQ 随机法术，50% 用 config 法术
    if random.random() < 0.5 or not spell_templates:
        spell_data = pq_random_spell()
        spell = Spell(spell_data["name"], spell_data["spell_type"],
                      spell_data["power"], spell_data["mp_cost"],
                      spell_data["description"])
    else:
        # spell_templates 中的元素可能是 dict 或 Spell 对象
        tmpl = random.choice(spell_templates)
        if isinstance(tmpl, Spell):
            spell = Spell(tmpl.name, tmpl.spell_type, tmpl.power,
                          tmpl.mp_cost, tmpl.description)
        else:
            spell = Spell(tmpl["name"], tmpl["spell_type"], tmpl["power"],
                          tmpl["mp_cost"], tmpl.get("description", ""))

    player.learn_spell(spell)


def _update_act_marker(player: Player):
    """根据等级更新章节标记（纯进度展示）"""
    act = pq_get_act(player.level)
    if act["name"] != player.current_act:
        old_act = player.current_act
        player.current_act = act["name"]
        if old_act:
            player.combat_log.append(
                f"🏰 进入：{act['name']}！")


# ==================== 游戏主循环 ====================

def run_game(stop_event: threading.Event, update_interval: int = 5):
    config = load_all_config()

    # 任务查找表（如果 config 有任务）
    quest_list = config.get("quests", [])
    quests_by_name = _build_lookup(quest_list) if quest_list else {}

    # 法术模板（如果 config 有法术）— 用 dict 格式，_on_level_up 自动处理
    spell_list = config.get("spells", [])
    spell_templates = spell_list if spell_list else []

    # 商店目录
    shop_catalog = config.get("shop_items", [])

    # 创建/读取角色
    player = load_or_auto_create(config)

    # 章节标记
    if not player.current_act:
        player.current_act = pq_get_act(player.level)["name"]
        player.combat_log.append(f"🏰 {player.current_act}")

    # 初始任务
    _auto_fill_quests(player, quests_by_name)

    # 初始怪物
    current_monster = Monster.spawn(player.level)

    # 初始法术
    if not player.spells:
        for _ in range(2):
            spell_data = pq_random_spell()
            player.learn_spell(Spell(
                spell_data["name"], spell_data["spell_type"],
                spell_data["power"], spell_data["mp_cost"],
                spell_data["description"]))

    prev_level = player.level

    print(f"\nProgress Quest v2 已启动（右键托盘图标可停止）")
    print(f"角色: {player.name} Lv.{player.level} "
          f"| {player.race} {player.klass}")
    print(f"属性: 力量{player.strength} 体质{player.constitution} "
          f"敏捷{player.dexterity} 智力{player.intelligence} "
          f"智慧{player.wisdom} 魅力{player.charisma}")
    print(f"金币: {player.gold} | 法术: {len(player.spells)}个\n")

    while not stop_event.is_set():
        # ---- 3 次战斗 ----
        for _ in range(3):
            if current_monster.hp <= 0:
                current_monster = Monster.spawn(player.level)
            player.combat_tick(current_monster)

        if stop_event.is_set():
            break

        # ---- 升级事件 ----
        if player.level > prev_level:
            _on_level_up(player, spell_templates)
            prev_level = player.level
        _update_act_marker(player)

        # ---- 任务流 ----
        _auto_fill_quests(player, quests_by_name)

        # ---- 城镇 ----
        if player.inv_count >= player.max_encumbrance:
            player.visit_town(shop_catalog)

        # ---- 输出 ----
        write_game_to_excel(player, shop_catalog)
        save_player(player)

        if stop_event.wait(update_interval):
            break

    save_player(player)
    print("游戏引擎已停止，存档已保存。")


# ==================== 托盘 ====================

def _on_stop(icon: pystray.Icon, stop_event: threading.Event):
    stop_event.set()
    icon.stop()


def _create_tray(stop_event: threading.Event) -> pystray.Icon:
    menu = pystray.Menu(
        pystray.MenuItem("停止游戏", lambda icon: _on_stop(icon, stop_event)),
    )
    return pystray.Icon("progress_quest", _create_icon_image(),
                        "Progress Quest", menu)


# ==================== 入口 ====================

if __name__ == "__main__":
    stop_event = threading.Event()
    game_thread = threading.Thread(
        target=run_game, args=(stop_event, 5), daemon=False, name="game")
    game_thread.start()
    tray = _create_tray(stop_event)
    tray.run()
    game_thread.join(timeout=10)
    print("Progress Quest 已完全关闭。")
