"""状态序列化 / 存档读写测试。

重点：
* `to_dict → from_dict` 必须**无损**（双端存档互通的前提）
* 序列化输出必须**稳定**（同一状态两次序列化逐字节相同）
* 原子落盘：主档损坏能从 `.bak` 恢复
* E4：引擎 `load()` 丢掉信封 timestamp，我们靠载荷里的 `saved_at_utc` 兜底
"""

import json
import os

import pytest

from fishtank.constants import SCHEMA_VERSION
from fishtank.save import SaveManager
from fishtank.state import FishState, GameState, TankState, r6
from tests.conftest import T0


# ══════════════════════════════════════════════════════════════
#  序列化往返
# ══════════════════════════════════════════════════════════════

def test_roundtrip_new_game(new_state):
    d1 = new_state.to_dict()
    st2 = GameState.from_dict(d1)
    assert st2.to_dict() == d1


def test_roundtrip_rich_state(bal, species):
    st = GameState(
        schema=SCHEMA_VERSION, saved_at_utc=T0, coins_milli=1234567,
        rng_seed=98765432109876543, next_uid=42, breed_timer=123.456789123,
        tank=TankState(water=73.4567891, capacity_level=2, filter_level=3,
                       feeder_owned=True, feeder_on=False, satiety=0.3333333333,
                       decors=["lucky_shrine", "pebble_substrate"]),
        fishes=[
            FishState(uid=1, species="neon_tetra", born_at=T0 - 5000,
                      age_sec=4999.9999991, stage="adult", variant=True,
                      nickname="小蓝", last_bred_at=T0 - 100,
                      x=0.1234567891, y=0.9876543219, heading=-1.0),
            FishState(uid=7, species="coelacanth", born_at=T0 - 90000,
                      age_sec=90000.0, stage="mature", variant=False,
                      nickname="", last_bred_at=0, x=0.5, y=0.5, heading=1.0),
        ],
        codex={"neon_tetra": T0 - 5000, "coelacanth": T0 - 90000},
        stats={"born": 9, "bred": 3},
        settings={"window_mode": "tank", "muted": True},
    )
    d1 = st.to_dict()
    st2 = GameState.from_dict(d1)
    assert st2.to_dict() == d1
    assert st2.coins_milli == st.coins_milli
    assert st2.rng_seed == st.rng_seed
    assert st2.tank.feeder_on is False
    assert st2.get_fish(1).nickname == "小蓝"
    assert st2.get_fish(1).variant is True


def test_serialization_is_byte_stable(new_state):
    """同一状态序列化两次，JSON 文本逐字节相同（双端 diff 的前提）。"""
    a = json.dumps(new_state.to_dict(), ensure_ascii=False, sort_keys=False)
    b = json.dumps(new_state.to_dict(), ensure_ascii=False, sort_keys=False)
    assert a == b


def test_fishes_always_sorted_by_uid(bal, species):
    st = GameState.new_game(bal, species, when=T0)
    st.fishes.reverse()
    uids = [f["uid"] for f in st.to_dict()["fishes"]]
    assert uids == sorted(uids)


def test_decors_always_sorted():
    t = TankState(decors=["z_item", "a_item", "m_item"])
    assert t.to_dict()["decors"] == ["a_item", "m_item", "z_item"]


def test_floats_capped_at_six_decimals():
    """JSON 里浮点最多 6 位小数（ARCHITECTURE §2）。"""
    f = FishState(uid=1, age_sec=1.23456789012, x=0.111111119, y=1e-9)
    d = f.to_dict()
    for key in ("age_sec", "x", "y"):
        text = repr(d[key])
        if "." in text and "e" not in text:
            assert len(text.split(".")[1]) <= 6, "%s=%s 小数位超过 6" % (key, text)
    assert d["y"] == 0.0


def test_r6_normalizes_negative_zero():
    assert r6(-0.0) == 0.0
    assert repr(r6(-0.0)) == "0.0"
    assert repr(r6(-1e-9)) == "0.0"


# ══════════════════════════════════════════════════════════════
#  容错
# ══════════════════════════════════════════════════════════════

def test_from_dict_tolerates_garbage():
    """存档损坏也绝不抛异常（准则：不因数据问题崩溃）。"""
    for bad in ({}, None, {"fishes": "not a list"}, {"coins_milli": "abc"},
                {"tank": 123}, {"fishes": [None, 5, {"uid": "x"}]},
                {"codex": ["not", "a", "dict"]}, {"schema": "v9"}):
        st = GameState.from_dict(bad)
        assert isinstance(st, GameState)
        assert st.coins_milli >= 0
        assert st.next_uid >= 1


def test_from_dict_negative_coins_clamped():
    st = GameState.from_dict({"coins_milli": -99999})
    assert st.coins_milli == 0


def test_repair_fixes_duplicate_uids():
    st = GameState(next_uid=1, fishes=[
        FishState(uid=5, species="guppy"),
        FishState(uid=5, species="guppy"),
        FishState(uid=0, species="guppy"),
    ])
    n = st.repair()
    assert n > 0
    uids = [f.uid for f in st.fishes]
    assert len(set(uids)) == len(uids), "uid 必须两两不同"
    assert st.next_uid > max(uids)
    assert len(st.fishes) == 3, "准则 L1：修复不能删鱼"


def test_repair_clamps_positions():
    st = GameState(fishes=[FishState(uid=1, species="guppy", x=5.0, y=-3.0)])
    st.repair()
    assert 0.0 <= st.fishes[0].x <= 1.0
    assert 0.0 <= st.fishes[0].y <= 1.0


def test_repair_backfills_codex():
    st = GameState(fishes=[FishState(uid=1, species="guppy", born_at=T0)], codex={})
    st.repair()
    assert st.codex["guppy"] == T0


def test_deep_copy_is_independent(new_state):
    c = new_state.deep_copy()
    c.coins_milli += 999
    c.tank.water = 1.0
    c.tank.decors.append("x")
    c.fishes[0].age_sec += 100
    c.stats["born"] = 999
    assert new_state.coins_milli != c.coins_milli
    assert new_state.tank.water != c.tank.water
    assert "x" not in new_state.tank.decors
    assert new_state.fishes[0].age_sec != c.fishes[0].age_sec
    assert new_state.stats.get("born") != 999


# ══════════════════════════════════════════════════════════════
#  金币操作
# ══════════════════════════════════════════════════════════════

def test_add_coins_never_negative(new_state):
    new_state.coins_milli = 100
    assert new_state.add_coins_milli(-99999) == 0


def test_spend_requires_balance(new_state):
    new_state.coins_milli = 1000
    assert not new_state.spend_milli(1001)
    assert new_state.coins_milli == 1000
    assert new_state.spend_milli(1000)
    assert new_state.coins_milli == 0
    assert not new_state.spend_milli(-1), "负价格不可购买"


def test_alloc_uid_is_monotonic(new_state):
    a = new_state.alloc_uid()
    b = new_state.alloc_uid()
    assert b == a + 1


def test_add_fish_registers_codex(new_state):
    f = FishState(uid=new_state.alloc_uid(), species="coelacanth", born_at=T0)
    first = new_state.add_fish(f, when=T0)
    assert first is True
    assert new_state.codex["coelacanth"] == T0
    f2 = FishState(uid=new_state.alloc_uid(), species="coelacanth", born_at=T0 + 1)
    assert new_state.add_fish(f2, when=T0 + 1) is False


def test_remove_fish_keeps_codex(new_state):
    f = new_state.fishes[0]
    new_state.remove_fish(f.uid)
    assert new_state.get_fish(f.uid) is None
    assert f.species in new_state.codex, "准则 L1/L2：卖鱼不该抹掉图鉴进度"


# ══════════════════════════════════════════════════════════════
#  存档落盘
# ══════════════════════════════════════════════════════════════

def test_save_load_roundtrip(new_state, tmp_save_dir):
    sm = SaveManager(directory=tmp_save_dir)
    assert sm.save(new_state, when=T0)
    assert os.path.isfile(sm.path())
    loaded = sm.load()
    assert loaded is not None
    assert loaded.to_dict() == new_state.to_dict()


def test_save_is_atomic_no_temp_left(new_state, tmp_save_dir):
    sm = SaveManager(directory=tmp_save_dir)
    sm.save(new_state, when=T0)
    assert not os.path.exists(sm.temp_path()), "临时文件必须被 os.replace 消费掉"


def test_save_creates_backup_on_second_write(new_state, tmp_save_dir):
    sm = SaveManager(directory=tmp_save_dir)
    sm.save(new_state, when=T0)
    assert not os.path.exists(sm.backup_path())
    new_state.coins_milli += 5000
    sm.save(new_state, when=T0 + 60)
    assert os.path.isfile(sm.backup_path()), "第二次保存应把旧主档转成 .bak"


def test_load_falls_back_to_backup(new_state, tmp_save_dir):
    sm = SaveManager(directory=tmp_save_dir)
    sm.save(new_state, when=T0)                 # 第一份
    new_state.coins_milli += 5000
    sm.save(new_state, when=T0 + 60)            # 第二份 → 旧的成为 .bak
    with open(sm.path(), "w", encoding="utf-8") as f:
        f.write("{ this is not json")           # 主档损坏
    loaded = sm.load()
    assert loaded is not None, "主档坏了必须能从备份救回来"
    assert loaded.coins_milli == new_state.coins_milli - 5000


def test_load_missing_returns_none(tmp_save_dir):
    sm = SaveManager(directory=tmp_save_dir)
    assert sm.load() is None
    assert not sm.exists()


def test_load_totally_corrupt_returns_none(new_state, tmp_save_dir):
    sm = SaveManager(directory=tmp_save_dir)
    sm.save(new_state, when=T0)
    for p in (sm.path(), sm.backup_path()):
        with open(p, "w", encoding="utf-8") as f:
            f.write("!!!")
    assert sm.load() is None


def test_saved_at_utc_survives_engine_envelope(new_state, tmp_save_dir):
    """★ E4：引擎 load() 丢掉信封 timestamp，我们必须靠载荷里的 saved_at_utc。"""
    sm = SaveManager(directory=tmp_save_dir)
    new_state.saved_at_utc = T0
    sm.save(new_state, when=T0)
    with open(sm.path(), "r", encoding="utf-8") as f:
        raw = json.load(f)
    assert raw["state_data"]["saved_at_utc"] == T0, "载荷里必须冗余存一份时间锚点"
    del raw["timestamp"]                       # 模拟引擎丢弃信封时间戳
    with open(sm.path(), "w", encoding="utf-8") as f:
        json.dump(raw, f, ensure_ascii=False)
    loaded = sm.load()
    assert loaded.saved_at_utc == T0


def test_save_anchor_is_monotonic(new_state, tmp_save_dir):
    """时钟回拨时锚点不后退（准则 L2：不凭空损失离线收益）。"""
    sm = SaveManager(directory=tmp_save_dir)
    new_state.saved_at_utc = T0
    sm.save(new_state, when=T0 - 100000)
    assert new_state.saved_at_utc == T0


def test_save_disabled_is_noop(new_state, tmp_save_dir):
    sm = SaveManager(directory=tmp_save_dir, enabled=False)
    assert sm.save(new_state, when=T0)
    assert not os.path.isfile(sm.path())


def test_delete_removes_all(new_state, tmp_save_dir):
    sm = SaveManager(directory=tmp_save_dir)
    sm.save(new_state, when=T0)
    sm.save(new_state, when=T0 + 1)
    assert sm.delete() >= 2
    assert not sm.exists()


def test_bare_payload_is_readable(new_state, tmp_save_dir):
    """手工导入的裸载荷（没有信封）也要能读。"""
    sm = SaveManager(directory=tmp_save_dir)
    with open(sm.path(), "w", encoding="utf-8") as f:
        json.dump(new_state.to_dict(), f, ensure_ascii=False)
    loaded = sm.load()
    assert loaded is not None
    assert loaded.coins_milli == new_state.coins_milli


def test_save_info(new_state, tmp_save_dir):
    sm = SaveManager(directory=tmp_save_dir)
    assert sm.info()["exists"] is False
    sm.save(new_state, when=T0)
    info = sm.info()
    assert info["exists"] is True and info["size"] > 0


# ══════════════════════════════════════════════════════════════
#  new_game 初始配置全部来自 balance.json
# ══════════════════════════════════════════════════════════════

def test_new_game_reads_config_only(bal, species):
    st = GameState.new_game(bal, species, when=T0)
    assert st.coins_milli == int(bal.get("start.coins_milli"))
    assert st.tank.water == pytest.approx(float(bal.get("water.init")))
    assert st.rng_seed == int(bal.get("start.rng_seed"))
    starters = list(bal.get("start.fishes"))
    assert [f.species for f in st.fishes_sorted()] == starters
    assert set(st.codex.keys()) == set(starters)


def test_new_game_fish_positions_are_spread(bal, species):
    st = GameState.new_game(bal, species, when=T0)
    xs = [f.x for f in st.fishes_sorted()]
    assert len(set(xs)) == len(xs), "初始鱼不能全部重叠在同一点"
    assert all(0.0 <= x <= 1.0 for x in xs)
