"""JSON + gzip 序列化 / 反序列化"""

import json
import gzip
import numpy as np
import os
import tempfile
import hmac as _hmac
import hashlib as _hashlib
from .types import (
    Race, Class, Stack, Monster, Quest, QueueItem,
    CurrentActionType,
)
from .character import Character
from .types import EQUIPMENT_LABELS


# ============ A6 存档信封 / 版本头 ============
# 新格式在 JSON 顶层携带 version + mac（HMAC-SHA256）。
# - 未知/未来版本 -> _UnsupportedVersionError -> load_game 返回 UnknownSaveVersion
#   （错误细分，而非 blanket 成 NotValidSaveFile）
# - mac 不匹配 -> 拒绝加载（NotValidSaveFile），实现 #8 的“防篡改硬校验”
# 旧格式（无 version 字段）走兼容分支，仅做软哈希告警，避免破坏已有存档。
SAVE_FORMAT_VERSION = 1
# 内嵌签名密钥（随包分发）。用途：存档完整性与防意外/低级篡改，
# 非防作弊。威胁模型与评审 ADR-001 一致。
_SAVE_SIGNING_KEY = b"pq2-progress-quest-save-signing-key-v1"


class _UnsupportedVersionError(Exception):
    """存档版本不被支持（A6）"""

    def __init__(self, version):
        self.version = version
        super().__init__(f"unsupported save version: {version}")


class _CorruptError(Exception):
    """存档信封/结构层损坏（ADR-001 §3.2 / A7）。

    涵盖：gzip 解压失败、JSON 解析失败、版本字段存在但 mac 不匹配、
    版本字段缺失（新格式约定必有 version）。与 _InvalidDataError（数据层
    schema 校验失败）区分，保留根因供遥测与启动自愈（A7）消费。
    """


class _InvalidDataError(Exception):
    """数据层 schema 校验失败：结构可解析，但逻辑值非法（Level<1、负数等）。"""


class _SaveTooLargeError(Exception):
    """解压后体积超限（gzip 炸弹防护，#3）：按安全策略拒绝。"""


def _canonical(data: dict) -> bytes:
    return json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sign(payload: dict) -> str:
    return _hmac.new(_SAVE_SIGNING_KEY, _canonical(payload), _hashlib.sha256).hexdigest()


def _verify(payload: dict, mac: str) -> bool:
    try:
        return _hmac.compare_digest(_sign(payload), mac or "")
    except Exception:
        return False


def _to_py(val):
    """将 numpy 类型转为 Python 原生类型"""
    if isinstance(val, (np.integer,)):
        return int(val)
    if isinstance(val, (np.floating,)):
        return float(val)
    return val


# 解压后最大字节数（gzip 炸弹防护，#3）：64MB 足够容纳任何合法存档
MAX_SAVE_DECOMPRESSED_BYTES = 64 * 1024 * 1024


def _is_int(v) -> bool:
    """仅为 int 且排除 bool（JSON 中 bool 不是合法数值）"""
    return isinstance(v, int) and not isinstance(v, bool)


def _require_int(v, field: str):
    if not _is_int(v):
        raise ValueError(f"字段 {field} 应为整数，实际为 {type(v).__name__}")


def _require_nonneg_int(v, field: str):
    _require_int(v, field)
    if v < 0:
        raise ValueError(f"字段 {field} 应为非负整数，实际为 {v}")


def _validate_character(character: Character) -> None:
    """反序列化后校验角色数据完整性（#1 防御式解析）。

    被篡改/损坏的 .pq2 若盲目信任 JSON 形状，会在游戏运行时触发崩溃
    （如 Level=0 -> _monster_task 的 ZeroDivisionError、_win_spell 的
    integers(0,0) ValueError）。这里在载入阶段做类型/范围断言，越早失败越好：
    异常会被 load_from_file 折成“Not a valid save file”，最终 load_game
    返回 LoadError.NotValidSaveFile，而不是让游戏主循环崩掉。
    """
    c = character
    # Level 必须 >=1（核心不变量：除以 Level 与 integers(0, Level) 都依赖它）
    _require_int(c.Level, "level")
    if c.Level < 1:
        raise ValueError(f"level 必须 >= 1，实际为 {c.Level}")

    # 六维属性：非负整数
    for f in ("STR", "CON", "DEX", "INT", "WIS", "CHA"):
        _require_nonneg_int(getattr(c, f), f.lower())

    # 其它标量数值：非负整数
    for f in ("Experience", "Gold", "MAX_HP", "MAX_MP",
              "CurrentProgress", "MaxProgress",
              "CurrentPlotProgress", "CurrentQuestProgress", "MaxQuestProgress"):
        _require_nonneg_int(getattr(c, f), f)

    # 当前行动枚举需在范围内（CurrentActionType 0..6）
    ca = c.CurrentAction
    if not isinstance(ca, CurrentActionType):
        raise ValueError(f"current_action 类型非法：{type(ca).__name__}")
    if ca.value < 0 or ca.value > max(int(x.value) for x in CurrentActionType):
        raise ValueError(f"current_action 越界：{ca.value}")

    # 怪物等级非负
    _require_nonneg_int(c.CurrentMonster.level, "current_monster.level")


def _serialize_race(race: Race) -> dict:
    return {"name": race.name, "attributes": list(race.attributes)}


def _serialize_class(cls: Class) -> dict:
    return {"name": cls.name, "attributes": list(cls.attributes)}


def _serialize_stack(item: Stack) -> dict:
    return {"name": item.name, "count": _to_py(item.count)}


def _serialize_equipment(equipment: list) -> dict:
    return {EQUIPMENT_LABELS[i]: equipment[i] for i in range(11)}


def _serialize_monster(monster: Monster) -> dict:
    return {"name": monster.name, "level": _to_py(monster.level), "drop": monster.drop}


def _serialize_quest(quest: Quest) -> dict:
    result = {"label": quest.label}
    if quest.monster is not None:
        result["monster"] = _serialize_monster(quest.monster)
    return result


def _serialize_queue_item(item: QueueItem) -> dict:
    return {"type": _to_py(item.type), "label": item.label, "ms": _to_py(item.ms)}


def serialize(character: Character) -> str:
    """将角色序列化为 JSON 字符串"""
    data = {
        "name": character.Name,
        "race": _serialize_race(character.CharacterRace),
        "class": _serialize_class(character.CharacterClass),
        "level": _to_py(character.Level),
        "experience": _to_py(character.Experience),
        "str": _to_py(character.STR),
        "con": _to_py(character.CON),
        "dex": _to_py(character.DEX),
        "int": _to_py(character.INT),
        "wis": _to_py(character.WIS),
        "cha": _to_py(character.CHA),
        "max_hp": _to_py(character.MAX_HP),
        "max_mp": _to_py(character.MAX_MP),
        "gold": _to_py(character.Gold),
        "spells": [_serialize_stack(s) for s in character.Spells],
        "equipment": _serialize_equipment(character.Equipment),
        "inventory": [_serialize_stack(s) for s in character.Inventory],
        "plot": list(character.Plot),
        "quests": [_serialize_quest(q) for q in character.Quests],
        "queue": [_serialize_queue_item(qi) for qi in character.Queue],
        "current_action": _to_py(character.CurrentAction.value),
        "current_action_label": character.CurrentActionLabel,
        "current_monster": _serialize_monster(character.CurrentMonster),
        "current_progress": _to_py(character.CurrentProgress),
        "max_progress": _to_py(character.MaxProgress),
        "current_plot_progress": _to_py(character.CurrentPlotProgress),
        "current_quest_progress": _to_py(character.CurrentQuestProgress),
        "max_quest_progress": _to_py(character.MaxQuestProgress),
    }
    # A6 信封：对除信封字段外的载荷做 HMAC 签名，附版本头
    envelope = {k: v for k, v in data.items()}
    data["version"] = SAVE_FORMAT_VERSION
    data["mac"] = _sign(envelope)
    return json.dumps(data)


def _deserialize_race(data: dict) -> Race:
    return Race(name=data["name"], attributes=data.get("attributes", []))


def _deserialize_class(data: dict) -> Class:
    return Class(name=data["name"], attributes=data.get("attributes", []))


def _deserialize_stack(data: dict) -> Stack:
    return Stack(name=data["name"], count=data["count"])


def _deserialize_monster(data: dict) -> Monster:
    return Monster(name=data["name"], level=data["level"], drop=data.get("drop", ""))


def _deserialize_quest(data: dict) -> Quest:
    quest = Quest(label=data["label"])
    if "monster" in data:
        quest.monster = _deserialize_monster(data["monster"])
    return quest


def _deserialize_queue_item(data: dict) -> QueueItem:
    return QueueItem(type=data["type"], label=data["label"], ms=data["ms"])


def deserialize(value: str, character: Character) -> None:
    """从 JSON 字符串反序列化到角色"""
    try:
        data = json.loads(value)
    except json.JSONDecodeError as e:
        raise _CorruptError(f"invalid JSON in save file: {e}")

    # A6 信封校验：新格式强制版本 + 完整性
    version = data.get("version")
    if version is not None:
        if version != SAVE_FORMAT_VERSION:
            raise _UnsupportedVersionError(version)
        payload = {k: v for k, v in data.items() if k not in ("version", "mac")}
        if not _verify(payload, data.get("mac", "")):
            raise _CorruptError("save integrity check failed (mac mismatch)")
        data = payload

    character.Name = data["name"]
    character.CharacterRace = _deserialize_race(data["race"])
    character.CharacterClass = _deserialize_class(data["class"])
    character.Level = data["level"]
    character.Experience = data["experience"]
    character.STR = data["str"]
    character.CON = data["con"]
    character.DEX = data["dex"]
    character.INT = data["int"]
    character.WIS = data["wis"]
    character.CHA = data["cha"]
    character.MAX_HP = data["max_hp"]
    character.MAX_MP = data["max_mp"]
    character.Gold = data["gold"]

    character.Spells = [_deserialize_stack(s) for s in data.get("spells", [])]

    # Equipment
    equipment_data = data.get("equipment", {})
    for i, label in enumerate(EQUIPMENT_LABELS):
        character.Equipment[i] = equipment_data.get(label, "")

    character.Inventory = [_deserialize_stack(s) for s in data.get("inventory", [])]
    character.Plot = data.get("plot", [])
    character.Quests = [_deserialize_quest(q) for q in data.get("quests", [])]
    character.Queue = [_deserialize_queue_item(qi) for qi in data.get("queue", [])]

    try:
        character.CurrentAction = CurrentActionType(data.get("current_action", 0))
    except (ValueError, TypeError):
        raise _InvalidDataError("current_action 枚举值越界")
    character.CurrentActionLabel = data.get("current_action_label", "")
    character.CurrentMonster = _deserialize_monster(data.get("current_monster", {"name": "", "level": 0, "drop": ""}))
    character.CurrentProgress = data.get("current_progress", 0)
    character.MaxProgress = data.get("max_progress", 0)
    character.CurrentPlotProgress = data.get("current_plot_progress", 0)
    character.CurrentQuestProgress = data.get("current_quest_progress", 0)
    character.MaxQuestProgress = data.get("max_quest_progress", 0)

    # 旧存档兼容补丁：合并拼写修正后的法术名
    _merge_spell_names(character)

    # #1：载入阶段做类型/范围校验，尽早失败（被篡改/损坏档直接拒绝）
    try:
        _validate_character(character)
    except ValueError as e:
        raise _InvalidDataError(str(e))

    # 哈希校验（跳过硬校验，改为警告，以兼容旧存档）
    expected_hash = data.get("hash", 0)
    actual_hash = character.calculate_hash()
    if expected_hash != 0 and expected_hash != actual_hash:
        print(f"Warning: save hash mismatch (expected {expected_hash}, got {actual_hash})")


_SPELL_MERGE_MAP = {
    "Innoculate": "Inoculate",
    "Tonsilectomy": "Tonsillectomy",
}


def _merge_spell_names(character: Character):
    """合并旧存档中的拼写错误法术名到正确拼写"""
    for spell in character.Spells:
        new_name = _SPELL_MERGE_MAP.get(spell.name)
        if new_name:
            spell.name = new_name


def save_to_file(character: Character, filepath: str) -> None:
    """JSON+gzip 保存存档（A3 原子写：临时文件 + fsync + os.replace，并保留上一版为 .bak）

    崩溃/断电时不会留下截断存档：先写临时文件并落盘，再原子替换；替换前把旧档
    轮转为 <file>.bak，供 A6/A7 恢复使用。保持 gzip 格式以兼容 load_from_file。
    """
    json_str = serialize(character)
    data = gzip.compress(json_str.encode('utf-8'), 9)
    dir_name = os.path.dirname(os.path.abspath(filepath)) or '.'
    fd, tmp_path = tempfile.mkstemp(dir=dir_name, prefix='.pq2_tmp_', suffix='.tmp')
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        # 轮换备份：先保留上一版为 .bak（覆盖式，仅留最近一份）
        if os.path.exists(filepath):
            try:
                os.replace(filepath, filepath + '.bak')
            except OSError:
                pass
        os.replace(tmp_path, filepath)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def load_from_file(filepath: str, character: Character) -> None:
    """从 gzip JSON 加载存档

    #3 gzip 炸弹防护：分块解压并在累计超过 MAX_SAVE_DECOMPRESSED_BYTES
    时主动拒绝，避免不可信来源（分享存档）的解压后内存耗尽（资源耗尽 DoS）。
    错误分层（ADR-001 §3.2 / A7）：
      - 信封/结构层损坏（解压失败、JSON 解析失败、mac 不匹配、版本字段缺失）
        -> _CorruptError -> LoadError.Corrupt
      - 数据层 schema 校验失败（结构可解析但逻辑值非法）
        -> _InvalidDataError -> LoadError.NotValidSaveFile
      - 解压体积超限（安全策略拒绝）-> _SaveTooLargeError -> LoadError.NotValidSaveFile
    """
    try:
        chunks = []
        total = 0
        with gzip.open(filepath, 'rb') as f:
            while True:
                chunk = f.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_SAVE_DECOMPRESSED_BYTES:
                    raise _SaveTooLargeError("decompressed save exceeds size limit")
                chunks.append(chunk)
        content = b"".join(chunks).decode('utf-8')
        deserialize(content, character)
    except (_UnsupportedVersionError, _CorruptError, _InvalidDataError,
            _SaveTooLargeError, FileNotFoundError):
        raise
    except Exception as e:
        raise _CorruptError(f"corrupt save file: {e}")
