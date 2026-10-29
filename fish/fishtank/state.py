"""游戏状态：唯一的**权威数据源**（single source of truth）。

🔴 禁止 `from __future__ import annotations`（E6：会让引擎 Serializable 的
   嵌套反序列化拿到字符串类型注解，静默写坏存档）。
🔴 状态里**不存任何派生值**（产出速率、加成等一律实时算），避免读档后漂移。
🔴 所有浮点在序列化时统一保留 6 位小数（ARCHITECTURE §2：JSON ≤6 位），
   保证同一状态在 Python / C++ 两端序列化出**逐字节相同**的文本。

存档 Schema（state_data 载荷）::

    {
      "schema": 1,
      "saved_at_utc": 1730000000,        # 🔴 冗余存一份：引擎 load() 会丢掉信封 timestamp（E4）
      "coins_milli": 60000,
      "rng_seed": 88172645463325252,
      "next_uid": 3,
      "breed_timer": 0.0,
      "autosell_timer": 0.0,
      "tank":  {...},
      "fishes": [ {...}, ... ],          # 按 uid 升序
      "codex": { "neon_tetra": 1730000000, ... },
      "stats": {...},
      "settings": {...}
    }
"""

import time
from dataclasses import dataclass, field

from fishtank.constants import (
    MODE_TANK, SCHEMA_VERSION, STAGE_FRY,
)

FLOAT_NDIGITS = 6
"""序列化时浮点保留的小数位（双端一致性要求）。"""


def now_utc():
    """当前 UTC 整秒。全项目**只从这里取时间**，便于测试注入。"""
    return int(time.time())


def _f(v, default=0.0):
    """宽松转 float。"""
    try:
        if v is None:
            return default
        return float(v)
    except (TypeError, ValueError):
        return default


def _i(v, default=0):
    """宽松转 int。"""
    try:
        if v is None:
            return default
        return int(v)
    except (TypeError, ValueError):
        return default


def _b(v, default=False):
    """宽松转 bool。"""
    if v is None:
        return default
    if isinstance(v, str):
        return v.strip().lower() in ("1", "true", "yes", "on")
    return bool(v)


def r6(v):
    """浮点规范化到 6 位小数（序列化专用）。

    还顺手把 ``-0.0`` 归一成 ``0.0``，避免两端文本不一致。
    """
    out = round(float(v), FLOAT_NDIGITS)
    return 0.0 if out == 0.0 else out


# ══════════════════════════════════════════════════════════════
#  单条鱼
# ══════════════════════════════════════════════════════════════

@dataclass
class FishState:
    """一条鱼的持久化状态。

    ⚠️ 这里**不存**产出速率、缩放比例等派生值 —— 全部由 economy.py 实时算出。
    """

    uid: int = 0
    species: str = ""
    born_at: int = 0
    age_sec: float = 0.0
    stage: str = STAGE_FRY
    variant: bool = False
    nickname: str = ""
    last_bred_at: int = 0
    x: float = 0.5
    y: float = 0.5
    heading: float = 1.0

    def to_dict(self):
        """序列化（浮点统一 6 位小数）。"""
        return {
            "uid": int(self.uid),
            "species": str(self.species),
            "born_at": int(self.born_at),
            "age_sec": r6(self.age_sec),
            "stage": str(self.stage),
            "variant": bool(self.variant),
            "nickname": str(self.nickname),
            "last_bred_at": int(self.last_bred_at),
            "x": r6(self.x),
            "y": r6(self.y),
            "heading": r6(self.heading),
        }

    @classmethod
    def from_dict(cls, d):
        """反序列化；字段缺失/类型错误一律降级为默认值，绝不抛异常。"""
        if not isinstance(d, dict):
            d = {}
        return cls(
            uid=_i(d.get("uid"), 0),
            species=str(d.get("species", "")),
            born_at=_i(d.get("born_at"), 0),
            age_sec=max(0.0, _f(d.get("age_sec"), 0.0)),
            stage=str(d.get("stage", STAGE_FRY)),
            variant=_b(d.get("variant"), False),
            nickname=str(d.get("nickname", "")),
            last_bred_at=_i(d.get("last_bred_at"), 0),
            x=_f(d.get("x"), 0.5),
            y=_f(d.get("y"), 0.5),
            heading=_f(d.get("heading"), 1.0),
        )

    def copy(self):
        """浅层足够（全是不可变标量）。"""
        return FishState(
            uid=self.uid, species=self.species, born_at=self.born_at,
            age_sec=self.age_sec, stage=self.stage, variant=self.variant,
            nickname=self.nickname, last_bred_at=self.last_bred_at,
            x=self.x, y=self.y, heading=self.heading,
        )

    def display_name(self, species_def=None):
        """展示名：优先昵称，其次鱼种中文名，最后 id。"""
        if self.nickname:
            return self.nickname
        if species_def is not None and species_def.name_zh:
            return species_def.name_zh
        return self.species


# ══════════════════════════════════════════════════════════════
#  鱼缸
# ══════════════════════════════════════════════════════════════

@dataclass
class TankState:
    """鱼缸设备与环境状态。"""

    water: float = 100.0
    capacity_level: int = 0
    filter_level: int = 0
    feeder_owned: bool = False
    feeder_on: bool = True
    satiety: float = 1.0
    decors: list = field(default_factory=list)

    def to_dict(self):
        """序列化（decors 按 id 升序，保证双端文本一致）。"""
        return {
            "water": r6(self.water),
            "capacity_level": int(self.capacity_level),
            "filter_level": int(self.filter_level),
            "feeder_owned": bool(self.feeder_owned),
            "feeder_on": bool(self.feeder_on),
            "satiety": r6(self.satiety),
            "decors": sorted(str(d) for d in self.decors),
        }

    @classmethod
    def from_dict(cls, d):
        """反序列化，带容错。"""
        if not isinstance(d, dict):
            d = {}
        raw_decors = d.get("decors")
        decors = sorted(str(x) for x in raw_decors) if isinstance(raw_decors, list) else []
        return cls(
            water=_f(d.get("water"), 100.0),
            capacity_level=max(0, _i(d.get("capacity_level"), 0)),
            filter_level=max(0, _i(d.get("filter_level"), 0)),
            feeder_owned=_b(d.get("feeder_owned"), False),
            feeder_on=_b(d.get("feeder_on"), True),
            satiety=_f(d.get("satiety"), 1.0),
            decors=decors,
        )

    def copy(self):
        """深拷贝（decors 是列表）。"""
        return TankState(
            water=self.water, capacity_level=self.capacity_level,
            filter_level=self.filter_level, feeder_owned=self.feeder_owned,
            feeder_on=self.feeder_on, satiety=self.satiety,
            decors=list(self.decors),
        )

    def feeder_active(self):
        """自动投食器是否正在工作。"""
        return bool(self.feeder_owned and self.feeder_on)


# ══════════════════════════════════════════════════════════════
#  整局状态
# ══════════════════════════════════════════════════════════════

@dataclass
class GameState:
    """整局游戏的权威状态。"""

    schema: int = SCHEMA_VERSION
    saved_at_utc: int = 0
    coins_milli: int = 0
    rng_seed: int = 0
    next_uid: int = 1
    breed_timer: float = 0.0
    autosell_timer: float = 0.0
    tank: TankState = field(default_factory=TankState)
    fishes: list = field(default_factory=list)
    codex: dict = field(default_factory=dict)
    stats: dict = field(default_factory=dict)
    settings: dict = field(default_factory=dict)
    _fish_index: dict = field(default_factory=dict, init=False, repr=False)
    """uid → FishState 的瞬态索引（不入档），将 get_fish 从 O(n) 降到 O(1)。"""
    _fishes_sorted_cache: list = field(default_factory=list, init=False, repr=False)
    """fishes_sorted() 的缓存（不入档），add_fish/remove_fish 时置脏。"""
    _fishes_sorted_dirty: bool = field(default=True, init=False, repr=False)
    """fishes_sorted 缓存是否已失效。"""

    # ── 序列化 ──

    def to_dict(self):
        """序列化为存档载荷（键序固定、鱼按 uid 升序、浮点 6 位）。"""
        return {
            "schema": int(self.schema),
            "saved_at_utc": int(self.saved_at_utc),
            "coins_milli": int(self.coins_milli),
            "rng_seed": int(self.rng_seed),
            "next_uid": int(self.next_uid),
            "breed_timer": r6(self.breed_timer),
            "autosell_timer": r6(self.autosell_timer),
            "tank": self.tank.to_dict(),
            "fishes": [f.to_dict() for f in self.fishes_sorted()],
            "codex": {str(k): int(v) for k, v in sorted(self.codex.items())},
            "stats": dict(sorted(self.stats.items())),
            "settings": dict(sorted(self.settings.items())),
        }

    @classmethod
    def from_dict(cls, d):
        """从存档载荷还原；任何字段异常都降级而不抛异常。

        🔴 准则：存档损坏也绝不让玩家丢进度 —— 能救多少救多少。
        """
        if not isinstance(d, dict):
            d = {}
        fishes = []
        raw_fishes = d.get("fishes")
        if isinstance(raw_fishes, list):
            for item in raw_fishes:
                if isinstance(item, dict):
                    fishes.append(FishState.from_dict(item))
        codex = {}
        raw_codex = d.get("codex")
        if isinstance(raw_codex, dict):
            for k, v in raw_codex.items():
                codex[str(k)] = _i(v, 0)
        st = cls(
            schema=_i(d.get("schema"), SCHEMA_VERSION),
            saved_at_utc=_i(d.get("saved_at_utc"), 0),
            coins_milli=max(0, _i(d.get("coins_milli"), 0)),
            rng_seed=_i(d.get("rng_seed"), 0),
            next_uid=max(1, _i(d.get("next_uid"), 1)),
            breed_timer=max(0.0, _f(d.get("breed_timer"), 0.0)),
            autosell_timer=max(0.0, _f(d.get("autosell_timer"), 0.0)),
            tank=TankState.from_dict(d.get("tank")),
            fishes=fishes,
            codex=codex,
            stats=dict(d["stats"]) if isinstance(d.get("stats"), dict) else {},
            settings=dict(d["settings"]) if isinstance(d.get("settings"), dict) else {},
        )
        st.repair()
        st._rebuild_index()
        return st

    def deep_copy(self):
        """深拷贝。:func:`fishtank.offline.settle_offline` 的纯函数性依赖它。"""
        cp = GameState(
            schema=self.schema,
            saved_at_utc=self.saved_at_utc,
            coins_milli=self.coins_milli,
            rng_seed=self.rng_seed,
            next_uid=self.next_uid,
            breed_timer=self.breed_timer,
            autosell_timer=self.autosell_timer,
            tank=self.tank.copy(),
            fishes=[f.copy() for f in self.fishes],
            codex=dict(self.codex),
            stats=dict(self.stats),
            settings=dict(self.settings),
        )
        cp._rebuild_index()
        return cp

    # ── 查询 ──

    def fishes_sorted(self):
        """按 uid 升序返回鱼列表（惰性缓存，add_fish/remove_fish 时自动失效）。

        🔴 所有涉及浮点求和 / 随机数消耗的遍历都**必须**走这个方法，
        否则 Python 的字典顺序变化会破坏双端一致性。
        """
        if self._fishes_sorted_dirty:
            self._fishes_sorted_cache = sorted(self.fishes, key=lambda f: f.uid)
            self._fishes_sorted_dirty = False
        return self._fishes_sorted_cache

    def fish_count(self):
        """当前鱼数。"""
        return len(self.fishes)

    def get_fish(self, uid):
        """按 uid 找鱼，O(1) 索引查找。"""
        return self._fish_index.get(int(uid))

    def owned_species(self):
        """当前**在缸内**的鱼种 id 集合。"""
        return {f.species for f in self.fishes}

    def codex_species(self):
        """图鉴中**曾经拥有过**的鱼种 id 集合（卖掉/送走也不会清除）。"""
        return set(self.codex.keys())

    def capacity(self, bal):
        """当前鱼缸容量。"""
        return bal.capacity_of(self.tank.capacity_level)

    def is_full(self, bal):
        """鱼缸是否已满。"""
        return self.fish_count() >= self.capacity(bal)

    def coins(self, bal):
        """当前金币（浮点，仅用于展示）。"""
        return float(self.coins_milli) / float(bal.coin_scale() or 1000)

    def stat(self, key, default=0):
        """读一个统计项。"""
        v = self.stats.get(key, default)
        return v if isinstance(v, (int, float)) else default

    def bump_stat(self, key, delta=1):
        """累加一个统计项。"""
        self.stats[key] = self.stat(key, 0) + delta

    def _rebuild_index(self):
        """从 fishes 列表重建瞬态索引（读档 / 深拷贝 / repair 后调用）。"""
        self._fish_index.clear()
        for f in self.fishes:
            self._fish_index[f.uid] = f
        self._fishes_sorted_dirty = True

    # ── 变更 ──

    def alloc_uid(self):
        """分配一个新的鱼 uid（自增，不复用）。"""
        uid = int(self.next_uid)
        self.next_uid = uid + 1
        return uid

    def add_fish(self, fish, when=None):
        """加入一条鱼并顺手登记图鉴。

        :param fish: FishState
        :param when: 登记图鉴的 UTC 秒；None 用鱼的 born_at
        :returns: 是否是**首次**解锁该鱼种
        """
        self.fishes.append(fish)
        self._fish_index[fish.uid] = fish
        self._fishes_sorted_dirty = True
        ts = int(when) if when is not None else int(fish.born_at)
        first = fish.species not in self.codex
        if first:
            self.codex[fish.species] = ts
        return first

    def remove_fish(self, uid):
        """移出一条鱼（图鉴记录**保留**）。返回被移出的 FishState 或 None。"""
        f = self.get_fish(uid)
        if f is not None:
            self.fishes.remove(f)
            self._fish_index.pop(int(uid), None)
            self._fishes_sorted_dirty = True
        return f

    def add_coins_milli(self, delta):
        """增减金币（厘）。**结果永不为负**（准则 L2）。"""
        self.coins_milli = max(0, int(self.coins_milli) + int(delta))
        return self.coins_milli

    def can_afford_milli(self, price_milli):
        """是否买得起。价格为负（不可购买）时返回 False。"""
        return price_milli >= 0 and self.coins_milli >= int(price_milli)

    def spend_milli(self, price_milli):
        """扣款；余额不足返回 False 且不改变状态。"""
        if not self.can_afford_milli(price_milli):
            return False
        self.coins_milli -= int(price_milli)
        return True

    # ── 自愈 ──

    def repair(self):
        """修补不一致的字段（读档后立即调用）。

        修补内容：
        * uid 重复 / 非正 → 重新分配
        * next_uid 落后于现有最大 uid → 抬高
        * 位置越界 → 钳回 [0,1]
        * codex 缺少在缸鱼种 → 补登记

        :returns: 修补项数量（0 = 存档健康）
        """
        fixed = 0
        # 先摸清现有的最大 uid，再从它之后开始补发，避免"补发的又撞车"
        max_uid = 0
        for f in self.fishes:
            if f.uid > 0:
                max_uid = max(max_uid, int(f.uid))
        next_free = max(max_uid + 1, int(self.next_uid), 1)

        seen = set()
        for f in self.fishes:
            if f.uid <= 0 or f.uid in seen:
                f.uid = next_free
                next_free += 1
                fixed += 1
            seen.add(f.uid)
            max_uid = max(max_uid, f.uid)
            if not (0.0 <= f.x <= 1.0):
                f.x = min(1.0, max(0.0, f.x))
                fixed += 1
            if not (0.0 <= f.y <= 1.0):
                f.y = min(1.0, max(0.0, f.y))
                fixed += 1
            if f.age_sec < 0.0:
                f.age_sec = 0.0
                fixed += 1
        if self.next_uid <= max_uid:
            self.next_uid = max_uid + 1
            fixed += 1
        for f in self.fishes:
            if f.species and f.species not in self.codex:
                self.codex[f.species] = int(f.born_at)
                fixed += 1
        if self.coins_milli < 0:
            self.coins_milli = 0
            fixed += 1
        if fixed:
            self._rebuild_index()
        return fixed

    # ── 新档 ──

    @classmethod
    def new_game(cls, bal, species_lib, when=None):
        """按 ``balance.json`` 的 ``start`` 段创建一份新档。

        🔴 初始金币、初始鱼种全部来自配置，代码里一个数字都不写死。
        """
        ts = int(when) if when is not None else now_utc()
        st = cls(
            schema=SCHEMA_VERSION,
            saved_at_utc=ts,
            coins_milli=_i(bal.get("start.coins_milli"), 0),
            rng_seed=_i(bal.get("start.rng_seed"), 88172645463325252),
            next_uid=1,
            breed_timer=0.0,
            autosell_timer=0.0,
            tank=TankState(
                water=_f(bal.get("water.init"), 100.0),
                capacity_level=_i(bal.get("start.capacity_level"), 0),
                filter_level=0,
                feeder_owned=False,
                feeder_on=True,
                satiety=_f(bal.get("feeder.satiety_max"), 1.0),
                decors=[],
            ),
            fishes=[],
            codex={},
            stats={"born": 0, "bred": 0, "sessions": 0},
            settings={"window_mode": MODE_TANK, "muted": False},
        )
        starters = bal.get("start.fishes")
        if not isinstance(starters, list):
            starters = []
        n = max(1, len(starters))
        for idx, sid in enumerate(starters):
            sid = str(sid)
            if species_lib.get(sid) is None:
                continue
            st.add_fish(FishState(
                uid=st.alloc_uid(),
                species=sid,
                born_at=ts,
                age_sec=0.0,
                stage=STAGE_FRY,
                variant=False,
                nickname="",
                last_bred_at=0,
                # 起始位置按序号均匀铺开，避免全部重叠（确定性，不用随机）
                x=r6(0.3 + 0.4 * (idx + 0.5) / n),
                y=0.5,
                heading=1.0 if idx % 2 == 0 else -1.0,
            ), when=ts)
            st.bump_stat("born", 1)
        return st
