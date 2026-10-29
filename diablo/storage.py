"""存档/读档、设置持久化、随机装备生成"""
import json
import os
import shutil
import time
import random
from typing import Optional

from paths import get_path
from models import Player, Equipment
from data import WEAPONS, ARMORS


# 当前存档格式版本（load_game 据此兼容旧档）
SAVE_VERSION = 2


def save_path(filename: str = "save.json") -> str:
    """返回存档文件的绝对路径（供界面展示"存档在哪里"）。"""
    return get_path(filename)


def save_game(player: Player, filename: str = "save.json") -> bool:
    """持久化角色。带备份 + 原子写入，写坏时仍可回退。"""
    filepath = get_path(filename)
    backup = get_path("save.backup.json")

    # 1) 先把上一版存档备份，防止写入过程中损坏导致彻底丢失
    if os.path.exists(filepath):
        try:
            shutil.copyfile(filepath, backup)
        except OSError:
            pass

    data = {
        "version": SAVE_VERSION,
        "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "name": player.name, "hp": player.hp, "max_hp": player.max_hp,
        "mp": player.mp, "max_mp": player.max_mp, "base_atk": player.base_atk,
        "base_def": player.base_def, "level": player.level, "exp": player.exp,
        "gold": player.gold, "soul": player.soul, "contract_active": player.contract_active,
        "weapon": player.weapon.name if player.weapon else None,
        "armor": player.armor.name if player.armor else None,
    }
    tmp = filepath + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        # 原子替换：要么成功要么还是旧文件，杜绝半截文件
        os.replace(tmp, filepath)
        return True
    except (PermissionError, IOError) as e:
        print(f"存档失败: {e}")
        return False


def _build_player(data: dict) -> Optional[Player]:
    """从字典构造 Player；字段缺失/损坏返回 None。"""
    required_keys = ["name", "hp", "max_hp", "mp", "max_mp", "base_atk",
                    "base_def", "level", "exp", "gold", "soul"]
    for key in required_keys:
        if key not in data:
            print(f"存档损坏：缺少字段 {key}")
            return None
    weapon = WEAPONS.get(data.get("weapon")) if data.get("weapon") else None
    armor = ARMORS.get(data.get("armor")) if data.get("armor") else None
    p = Player(data["name"], data["hp"], data["max_hp"], data["mp"], data["max_mp"],
               data["base_atk"], data["base_def"], data["level"], data["exp"],
               data["gold"], data["soul"], weapon, armor)
    p.contract_active = data.get("contract_active", False)
    return p


def load_game(filename: str = "save.json") -> Optional[Player]:
    """读取存档；主档损坏时自动回退到备份档。读到死亡角色会原地复活。"""
    filepath = get_path(filename)
    candidates = [filepath, get_path("save.backup.json")]
    last_err = None
    for path in candidates:
        if not os.path.exists(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            p = _build_player(data)
            if p is None:
                continue
            # 读到的若是"死档"（异常退出遗留下来的），原地复活避免卡死
            if not p.is_alive():
                p.hp = p.max_hp
                p.mp = p.max_mp
            return p
        except (PermissionError, IOError, json.JSONDecodeError, KeyError, TypeError) as e:
            last_err = e
            continue
    if last_err:
        print(f"读取存档失败: {last_err}")
    return None


def save_info(filename: str = "save.json") -> dict:
    """存档元信息，供界面展示"存档在哪儿 / 上次何时存"。"""
    filepath = get_path(filename)
    info = {"path": filepath, "exists": os.path.exists(filepath),
            "backup_exists": os.path.exists(get_path("save.backup.json")),
            "saved_at": None, "name": None, "level": None}
    if info["exists"]:
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                d = json.load(f)
            info["saved_at"] = d.get("saved_at")
            info["name"] = d.get("name")
            info["level"] = d.get("level")
        except Exception:
            pass
    return info


def random_equipment(quality_bonus: float = 1.0) -> Optional[Equipment]:
    roll = random.random()
    common_max = min(0.95, 0.6 * quality_bonus)
    rare_max = min(0.98, 0.9 * quality_bonus)
    if roll < common_max:
        return random.choice(list(WEAPONS.values()) + list(ARMORS.values()))
    elif roll < rare_max:
        return random.choice([w for w in WEAPONS.values() if w.quality == "Rare"] +
                             [a for a in ARMORS.values() if a.quality == "Rare"])
    else:
        # 史诗与传说装备归入最高掉落池
        pool = [w for w in WEAPONS.values() if w.quality in ("Epic", "Legendary")] + \
               [a for a in ARMORS.values() if a.quality in ("Epic", "Legendary")]
        if not pool:
            pool = list(WEAPONS.values()) + list(ARMORS.values())
        return random.choice(pool)


def save_settings(settings: dict, filename: str = "settings.json"):
    filepath = get_path(filename)
    tmp = filepath + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
        os.replace(tmp, filepath)
    except (PermissionError, IOError) as e:
        print(f"设置保存失败: {e}")


def load_settings(filename: str = "settings.json") -> dict:
    filepath = get_path(filename)
    if not os.path.exists(filepath):
        return {"language": "zh", "show_tips": True, "auto_save": True}
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            settings = json.load(f)
        # 确保必要键存在
        settings.setdefault("language", "zh")
        settings.setdefault("show_tips", True)
        settings.setdefault("auto_save", True)
        return settings
    except (PermissionError, IOError, json.JSONDecodeError) as e:
        print(f"读取设置失败: {e}")
        return {"language": "zh", "show_tips": True, "auto_save": True}
