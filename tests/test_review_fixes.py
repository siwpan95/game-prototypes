"""评审问题修复的回归测试（#1/#2/#3/#5/#6/#7/#15/#8/A6/#10）。

对应 CODE_REVIEW_Cody.md 的发现项：
- #1 反序列化类型/范围校验（Level>=1 等）
- #2 自动投骰线程在确认时停止（NewGame 侧）
- #3 gzip 炸弹防护（解压大小上限）
- #5 种族/职业属性应用到角色
- #6 本地化字典与数据一致（无漏译/孤儿）
- #7 行动/任务标签前缀替换后继续翻译剩余文本
- #8/A6 新格式信封（version+mac）：篡改拒绝、未知版本细分
- #15 装备生成：负数等级前缀 + 怪物等级归零
- #10 自动存盘节流
"""

import os
import json
import gzip
import tempfile

import pytest

from pq2.game import Game
from pq2.character import Character
from pq2.types import LoadError, GameState, CurrentActionType, SaveError
from pq2.localization import (
    translate, translate_action_label, translate_quest_label, get_cn,
)
from pq2.data.races import get_race_list
from pq2.data.classes import get_class_list
from pq2.data.spells import get_spells
from pq2.newgame import NewGame

from .conftest import good_save_bytes


# ============================ #1 反序列化校验 ============================

def _write_save(obj) -> str:
    path = tempfile.mktemp(suffix=".pq2")
    with open(path, "wb") as f:
        f.write(gzip.compress(json.dumps(obj).encode("utf-8")))
    return path


def test_good_save_loads_ok():
    g = Game()
    path = _write_save(json.loads(good_save_bytes().decode("utf-8")))
    try:
        err = g.load_game(path)
        assert err == LoadError.None_
        assert g.get_state() == GameState.Ready
    finally:
        if os.path.exists(path):
            os.remove(path)


def test_tampered_level_zero_rejected():
    obj = json.loads(good_save_bytes().decode("utf-8"))
    obj.pop("version", None); obj.pop("mac", None)  # 隔离 #1 schema 校验（旧格式兼容路径，跳过 mac 校验）
    obj["level"] = 0  # 触发 _monster_task 的 ZeroDivisionError / integers(0,0)
    path = _write_save(obj)
    g = Game()
    try:
        err = g.load_game(path)
    finally:
        if os.path.exists(path):
            os.remove(path)
    assert err == LoadError.NotValidSaveFile
    assert g.get_state() == GameState.None_   # 状态不被污染


def test_tampered_nonint_level_rejected():
    obj = json.loads(good_save_bytes().decode("utf-8"))
    obj.pop("version", None); obj.pop("mac", None)
    obj["level"] = "oops"
    path = _write_save(obj)
    g = Game()
    try:
        err = g.load_game(path)
    finally:
        if os.path.exists(path):
            os.remove(path)
    assert err == LoadError.NotValidSaveFile


def test_tampered_negative_stat_rejected():
    obj = json.loads(good_save_bytes().decode("utf-8"))
    obj.pop("version", None); obj.pop("mac", None)
    obj["str"] = -5
    path = _write_save(obj)
    g = Game()
    try:
        err = g.load_game(path)
    finally:
        if os.path.exists(path):
            os.remove(path)
    assert err == LoadError.NotValidSaveFile


def test_out_of_range_current_action_rejected():
    obj = json.loads(good_save_bytes().decode("utf-8"))
    obj.pop("version", None); obj.pop("mac", None)
    obj["current_action"] = 999
    path = _write_save(obj)
    g = Game()
    try:
        err = g.load_game(path)
    finally:
        if os.path.exists(path):
            os.remove(path)
    assert err == LoadError.NotValidSaveFile


# ============================ #3 gzip 炸弹防护 ============================

def test_gzip_bomb_rejected():
    # 解压后约 70MB 的重复数据，gzip 后体积极小（典型炸弹形态）。
    # 注意：上限为 64 MiB（64*1024*1024 = 67_108_864 字节），
    # 因此必须 > 64 MiB 才能触发防护（65M 仍低于上限，不会拦截）。
    payload = json.dumps({"pad": "a" * 70_000_000}).encode("utf-8")
    data = gzip.compress(payload)
    path = tempfile.mktemp(suffix=".pq2")
    with open(path, "wb") as f:
        f.write(data)
    g = Game()
    try:
        err = g.load_game(path)
    finally:
        if os.path.exists(path):
            os.remove(path)
    assert err == LoadError.NotValidSaveFile


# ============================ #5 种族/职业属性应用 ============================

def test_race_class_attributes_applied():
    g = Game()
    c = Character()
    race = next(r for r in get_race_list() if r.name == "Hob-Hobbit")  # 授予 DEX, CON
    cls = next(cl for cl in get_class_list() if cl.name == "Vermineer")  # 授予 INT
    c.CharacterRace = race
    c.CharacterClass = cls
    base_dex, base_con, base_int = c.DEX, c.CON, c.INT
    g._on_character_created(c)
    assert c.DEX == base_dex + 1, "种族属性 DEX 应 +1"
    assert c.CON == base_con + 1, "种族属性 CON 应 +1"
    assert c.INT == base_int + 1, "职业属性 INT 应 +1"
    assert c.Level == 1
    assert c.Equipment[0] == "Sharp Rock"


# ============================ #6 本地化与数据一致 ============================

def test_all_data_names_translated():
    for r in get_race_list():
        assert get_cn(r.name) != r.name, f"种族漏译: {r.name}"
    for c in get_class_list():
        assert get_cn(c.name) != c.name, f"职业漏译: {c.name}"
    for s in get_spells():
        assert get_cn(s) != s, f"法术漏译: {s}"


def test_no_orphan_class_translation_keys():
    # 孤儿条目应已删除（与数据文件不一致）
    from pq2.localization import CLASSES_CN
    assert "Puma Burglar" not in CLASSES_CN   # 拼写错孤儿
    assert "Italophobia" not in CLASSES_CN
    assert "Gongfarmer" not in CLASSES_CN


# ============================ #7 行动/任务标签翻译剩余 ============================

def test_action_label_translates_remainder():
    out = translate_action_label("Executing an imaginary Dragon")
    assert "正在对战" in out
    assert "imaginary" not in out   # 前缀之后的剩余文本应被继续翻译
    assert "幻想" in out


def test_quest_label_translates_remainder():
    out = translate_quest_label("Exterminate the Goblin")
    assert "消灭" in out
    assert "Exterminate" not in out


# ============================ #15 装备生成健壮性 ============================

def test_win_equip_no_negative_prefix(monkeypatch):
    import pq2.game as gm

    class FakeItem:
        label = "Fake"
        level = 999   # 远高于角色等级，强制 plus<0 分支

    def fake(_rng):
        return FakeItem()

    monkeypatch.setattr(gm, "get_random_weapon", fake)
    monkeypatch.setattr(gm, "get_random_shield", fake)
    monkeypatch.setattr(gm, "get_random_armor", fake)

    g = Game()
    c = Character()
    g._on_character_created(c)
    g._win_equip()
    for name in c.Equipment:
        if name:
            assert not name.startswith("-"), f"畸形装备名（负数前缀）: {name}"


def test_monster_progress_never_zero(monkeypatch):
    g = Game()
    c = Character()
    g._on_character_created(c)
    c.Level = 50   # 高等级以频繁触发 level-lev>10 的 qty 计算分支
    for _ in range(500):
        g._monster_task()
        # #15：level//qty 在 qty>level 时退化为 0 会导致 MaxProgress=0（卡死/坏状态）
        assert c.MaxProgress >= 1, "怪物推进进度退化为 0"
        assert c.CurrentMonster.level >= 1


# ============================ #2 自动投骰线程（NewGame 侧） ============================

def test_confirm_stops_auto_roll():
    import numpy as np
    rng = np.random.default_rng(0)
    captured = {}

    def cb(ch):
        captured["ch"] = ch

    ng = NewGame(rng, cb)
    ng.set_auto_roll_targets({"STR": 999})  # 不可达目标，避免线程真在测试中空转
    ng.start_auto_roll()
    assert ng.is_auto_rolling()
    ng.confirm_character()                  # #2：确认应停止后台线程
    assert not ng.is_auto_rolling()
    assert "ch" in captured


# ============================ A6 信封 / 版本头 ============================

def test_new_format_roundtrips():
    """A6 新格式（version+mac）能正常存读往返。"""
    g = Game()
    c = Character()
    g._on_character_created(c)
    path = tempfile.mktemp(suffix=".pq2")
    try:
        assert g.save_game(path) == SaveError.None_
        g2 = Game()
        err = g2.load_game(path)
        assert err == LoadError.None_
        assert g2.character.Level == c.Level
    finally:
        if os.path.exists(path):
            os.remove(path)


def test_unknown_version_rejected():
    """未知版本头应返回 UnknownSaveVersion（而非 blanket NotValidSaveFile）。"""
    obj = json.loads(good_save_bytes().decode("utf-8"))
    obj["version"] = 999999
    path = tempfile.mktemp(suffix=".pq2")
    with gzip.open(path, "wb") as f:
        f.write(json.dumps(obj).encode("utf-8"))
    g = Game()
    try:
        err = g.load_game(path)
    finally:
        if os.path.exists(path):
            os.remove(path)
    assert err == LoadError.UnknownSaveVersion


def test_tampered_new_save_rejected():
    """#8：篡改新格式存档（破坏 mac 完整性）应被拒绝。
    mac 不匹配属信封/结构层损坏 -> LoadError.Corrupt（而非数据层 NotValidSaveFile）。
    """
    g = Game()
    c = Character()
    g._on_character_created(c)
    path = tempfile.mktemp(suffix=".pq2")
    try:
        g.save_game(path)
        raw = gzip.open(path, "rb").read()
        obj = json.loads(raw.decode("utf-8"))
        obj["level"] = (obj.get("level") or 1) + 7   # 改动数据使 mac 失效
        with gzip.open(path, "wb") as f:
            f.write(json.dumps(obj).encode("utf-8"))
        g2 = Game()
        err = g2.load_game(path)
        assert err == LoadError.Corrupt
    finally:
        if os.path.exists(path):
            os.remove(path)


# ============================ #10 自动存盘节流 ============================

def test_auto_save_throttled(monkeypatch):
    """#10：距上次成功写盘不足阈值时，_auto_save 应跳过写盘。"""
    import time as _t
    g = Game()
    g._filename = tempfile.mktemp(suffix=".pq2")  # 防御：即便绕过 mock 也不污染仓库存档
    calls = []
    monkeypatch.setattr(g, "save_game",
                          lambda *a, **k: (calls.append(1) or SaveError.None_))
    g._last_save_time = _t.monotonic()   # 模拟“刚刚存过”
    g._auto_save()
    assert calls == []                     # 被节流，未写盘
    g._last_save_time = 0.0
    g._auto_save()
    assert len(calls) == 1                 # 清空时间戳后立即写盘一次


# ============================ A7 启动自愈 / .bak 回退 ============================

def test_recover_from_backup_when_current_corrupt():
    """A7：主档损坏、存在完好 .bak 时，load_game_with_recovery 自愈（返回 (None_, True)）。"""
    base = tempfile.mktemp(suffix=".pq2")
    cur, bak = base, base + ".bak"
    good = good_save_bytes()
    with open(bak, "wb") as f:
        f.write(gzip.compress(good))   # 完好 .bak（必须 gzip，与 load_from_file 一致）
    with open(cur, "wb") as f:
        f.write(good[:500])      # 损坏当前档（截断，非 gzip -> Corrupt）
    g = Game()
    err, recovered = g.load_game_with_recovery(cur)
    try:
        assert err == LoadError.None_
        assert recovered is True
        assert g.get_state() == GameState.Ready
        # 自愈后应已回填主档，且 .bak 应完好保留（未被覆盖）。
        # 注意：断言须在 finally 清理之前执行（否则 .bak 已被清理删除）。
        assert os.path.exists(bak)
    finally:
        for p in (cur, bak, cur + ".corrupt"):
            if os.path.exists(p):
                os.remove(p)


def test_recovery_isolates_corrupt_save():
    """A7：自愈时把损坏主档隔离为 .corrupt（保留取证，不删除）。"""
    base = tempfile.mktemp(suffix=".pq2")
    cur, bak = base, base + ".bak"
    good = good_save_bytes()
    with open(bak, "wb") as f:
        f.write(gzip.compress(good))   # 完好 .bak（gzip）
    with open(cur, "wb") as f:
        f.write(good[:500])
    g = Game()
    try:
        err, recovered = g.load_game_with_recovery(cur)
        assert err == LoadError.None_ and recovered
        assert os.path.exists(cur + ".corrupt")
    finally:
        for p in (cur, bak, cur + ".corrupt"):
            if os.path.exists(p):
                os.remove(p)


def test_no_recovery_when_both_corrupt():
    """A7：主档与 .bak 均损坏 -> 返回错误且 recovered=False（应提示新游戏）。"""
    base = tempfile.mktemp(suffix=".pq2")
    cur, bak = base, base + ".bak"
    good = good_save_bytes()
    with open(bak, "wb") as f:
        f.write(good[:500])
    with open(cur, "wb") as f:
        f.write(good[:300])
    g = Game()
    try:
        err, recovered = g.load_game_with_recovery(cur)
    finally:
        for p in (cur, bak, cur + ".corrupt"):
            if os.path.exists(p):
                os.remove(p)
    assert recovered is False
    assert err in (LoadError.Corrupt, LoadError.NotValidSaveFile)


# ============================ A11 本地化缺键监控 ============================

from pq2.localization import (
    record_missing_key, get_missing_keys, clear_missing_keys,
    audit_translation_coverage,
)


def test_missing_key_recorded_and_counted():
    clear_missing_keys()
    record_missing_key("ZogZogRace")
    record_missing_key("ZogZogRace")
    keys = get_missing_keys()
    assert any(k == "ZogZogRace" and cnt == 2 for k, cnt, _ in keys)


def test_get_cn_records_missing_key():
    clear_missing_keys()
    out = get_cn("NonexistentKeyXYZ")
    assert out == "NonexistentKeyXYZ"   # 仍回退原文（不崩溃）
    assert any(k == "NonexistentKeyXYZ" for k, _, _ in get_missing_keys())


def test_audit_coverage_no_gaps():
    """A11：当前数据文件名应全部已翻译（#6 已修复，无缺键）。"""
    clear_missing_keys()
    missing = audit_translation_coverage()
    assert missing == []


def test_audit_flags_missing_key(monkeypatch):
    """A11：审计能发现数据中存在但未翻译的键。"""
    clear_missing_keys()
    from pq2.localization import TRANSLATION_TABLE
    monkeypatch.delitem(TRANSLATION_TABLE, "Gyp", raising=False)  # 临时摘除一个法术键
    missing = audit_translation_coverage()
    assert "Gyp" in missing
    assert any(k == "Gyp" for k, _, _ in get_missing_keys())
