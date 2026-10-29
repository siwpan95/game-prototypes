"""数据定义层：鱼种 / 装饰 / 平衡表 / UI 文案 的加载与访问。

🔴 禁止 `from __future__ import annotations`（E6）。
🔴 本模块是"零硬编码数值"的守门人：所有玩法数值都必须经 BalanceTable 从
   data/balance.json 读出。模块内的 `_FALLBACK` 仅是**数据文件损坏时的救生圈**
   （准则：绝不因数据问题崩溃），不是玩法数值来源。
"""

import copy
import json
import os
from dataclasses import dataclass, field

from fishtank.engine_bootstrap import DataLibrary, get_logger

_log = get_logger("fishtank")


# ══════════════════════════════════════════════════════════════
#  鱼种 / 装饰定义
# ══════════════════════════════════════════════════════════════

@dataclass
class FishSpeciesDef:
    """一条鱼种的静态定义（对应 fish_data.json 的一项）。

    字段严格对齐 FISH_CONTENT.md §0 的 schema。
    """

    id: str = ""
    name_zh: str = ""
    name_la: str = ""
    rarity: str = "R1"
    group: str = ""
    color: dict = field(default_factory=dict)
    shape: dict = field(default_factory=dict)
    behavior: dict = field(default_factory=dict)
    science: str = ""
    codex_unlock: str = ""

    @classmethod
    def from_dict(cls, d):
        """从 JSON 字典构建；缺字段用默认值补齐，绝不抛异常。"""
        d = d or {}
        return cls(
            id=str(d.get("id", "")),
            name_zh=str(d.get("name_zh", "")),
            name_la=str(d.get("name_la", "")),
            rarity=str(d.get("rarity", "R1")),
            group=str(d.get("group", "")),
            color=dict(d.get("color") or {}),
            shape=dict(d.get("shape") or {}),
            behavior=dict(d.get("behavior") or {}),
            science=str(d.get("science", "")),
            codex_unlock=str(d.get("codex_unlock", "")),
        )

    def to_dict(self):
        """序列化回字典（供工具脚本回写使用）。"""
        return {
            "id": self.id, "name_zh": self.name_zh, "name_la": self.name_la,
            "rarity": self.rarity, "group": self.group,
            "color": dict(self.color), "shape": dict(self.shape),
            "behavior": dict(self.behavior),
            "science": self.science, "codex_unlock": self.codex_unlock,
        }

    def speed_key(self):
        """行为速度档：slow / normal / fast。"""
        return str(self.behavior.get("speed", "normal"))

    def layer_key(self):
        """常驻水层字符串（可能是 '底'/'中'/'上'，也可能是组合）。"""
        return str(self.behavior.get("layer", "中"))

    def schooling_key(self):
        """群游倾向：高 / 中 / 低。"""
        return str(self.behavior.get("schooling", "低"))

    def tail(self):
        """尾鳍形状：fan / fork / round / long。"""
        return str(self.shape.get("tail", "fork"))


@dataclass
class DecorDef:
    """一件装饰的静态定义（对应 decor_data.json 的一项）。"""

    id: str = ""
    name: str = ""
    bonus: float = 0.0
    price: int = 0
    draw: str = ""
    color: list = field(default_factory=list)
    anchor: str = "bottom"
    desc: str = ""

    @classmethod
    def from_dict(cls, d):
        """从 JSON 字典构建；类型错误一律降级为默认值。"""
        d = d or {}
        return cls(
            id=str(d.get("id", "")),
            name=str(d.get("name", "")),
            bonus=_as_float(d.get("bonus"), 0.0),
            price=_as_int(d.get("price"), 0),
            draw=str(d.get("draw", "")),
            color=list(d.get("color") or []),
            anchor=str(d.get("anchor", "bottom")),
            desc=str(d.get("desc", "")),
        )

    def to_dict(self):
        """序列化回字典。"""
        return {
            "id": self.id, "name": self.name, "bonus": self.bonus,
            "price": self.price, "draw": self.draw, "color": list(self.color),
            "anchor": self.anchor, "desc": self.desc,
        }


def _as_float(v, default):
    """宽松转 float，失败返回 default（容错原则：不抛异常）。"""
    try:
        if v is None:
            return default
        return float(v)
    except (TypeError, ValueError):
        return default


def _as_int(v, default):
    """宽松转 int，失败返回 default。"""
    try:
        if v is None:
            return default
        return int(v)
    except (TypeError, ValueError):
        return default


# ══════════════════════════════════════════════════════════════
#  数据库（继承引擎 DataLibrary）
# ══════════════════════════════════════════════════════════════

class FishLibrary(DataLibrary):
    """鱼种库。继承引擎 `DataLibrary`，补 by_rarity / by_group 查询。

    引擎的 `_load_from_list` 用 `getattr(item, "id")` 作为键，
    我们的 `FishSpeciesDef.id` 正好满足（任务要求的 item_key="id" 语义）。
    """

    def __init__(self, logger=None):
        super().__init__(
            factory=FishSpeciesDef.from_dict,
            item_key="id",
            item_name="鱼种",
            logger=logger,
        )
        self._idx = None

    def _index(self):
        """惰性建立族群 / 稀有度索引。

        ⚠️ 性能：离线结算每步都要算图鉴加成，若每次都 O(鱼种数×族群数) 地重扫，
        10 年硬上限那种极端存档会跑到 5 秒。数据加载后是**只读**的，
        所以这里一次性建索引；:meth:`load_from_json` 之后会自动失效重建。
        """
        if self._idx is None or self._idx[0] != len(self.all_items):
            by_group = {}
            by_rarity = {}
            for f in self.all_items.values():
                if f.group:
                    by_group.setdefault(f.group, set()).add(f.id)
                by_rarity.setdefault(f.rarity, []).append(f)
            groups = sorted(by_group.keys())
            for lst in by_rarity.values():
                lst.sort(key=lambda x: x.id)
            self._idx = (len(self.all_items), by_group, by_rarity, groups)
        return self._idx

    def by_rarity(self, rarity):
        """按稀有度筛选，结果按 id 升序（保证遍历确定性）。"""
        return list(self._index()[2].get(str(rarity), ()))

    def by_group(self, group):
        """按族群筛选，结果按 id 升序。"""
        ids = self._index()[1].get(str(group), set())
        return [self.all_items[i] for i in sorted(ids)]

    def groups(self):
        """返回全部族群名（按名称排序）。"""
        return list(self._index()[3])

    def group_members(self, group):
        """返回某族群的全部鱼种 id 集合（**只读**，调用方不要修改）。"""
        return self._index()[1].get(str(group), frozenset())

    def ids(self):
        """全部鱼种 id，升序。"""
        return sorted(self.all_items.keys())


class DecorLibrary(DataLibrary):
    """装饰库。"""

    def __init__(self, logger=None):
        super().__init__(
            factory=DecorDef.from_dict,
            item_key="id",
            item_name="装饰",
            logger=logger,
        )

    def ids(self):
        """全部装饰 id，升序。"""
        return sorted(self.all_items.keys())

    def bonus_of(self, decor_id):
        """查某装饰的加成；未知 id 返回 0.0（容错，不抛）。"""
        d = self.get(decor_id)
        return d.bonus if d else 0.0

    def sorted_by_price(self):
        """按价格升序列出（商店展示用）。"""
        return sorted(self.list_all(), key=lambda d: (d.price, d.id))


# ══════════════════════════════════════════════════════════════
#  平衡表
# ══════════════════════════════════════════════════════════════

# 🔴 救生圈：仅在 balance.json 缺失/损坏时启用，保证程序仍能跑起来（准则：不崩）。
#    正常运行时这里一个值都不会被读到 —— 玩法数值的唯一来源是 data/balance.json。
_FALLBACK = {
    "economy": {
        "base_income": {"R1": 1.0, "R2": 3.5, "R3": 12.0, "R4": 40.0, "R5": 130.0},
        "bonus_cap": 0.40, "coin_scale": 1000, "online_step_sec": 1.0,
        "_experimental_formula": None,
    },
    "growth": {
        "cycle_sec": {"R1": 7200, "R2": 21600, "R3": 50400, "R4": 100800, "R5": 172800},
        "thresholds": {"fry": 0.15, "juvenile": 0.45, "adult": 1.45},
        "stage_coef": {"fry": 0.30, "juvenile": 0.60, "adult": 1.00, "mature": 1.25},
        "stage_scale": {"fry": 0.45, "juvenile": 0.70, "adult": 1.00, "mature": 1.10},
        "stage_order": ["fry", "juvenile", "adult", "mature"],
    },
    "water": {
        "min": 50.0, "max": 100.0, "init": 100.0, "decay_per_fish": 0.03,
        "filter_gain": [0.0, 0.2, 0.5, 1.2], "offline_scale": 0.5,
        "quality_floor": 0.5, "bands": [50, 60, 70, 80, 90, 100],
    },
    "offline": {
        "segments": [[0, 480, 1.00], [480, 1440, 0.60], [1440, None, 0.35]],
        "fine_step_sec": 60, "fine_limit_sec": 86400,
        "coarse_step_sec": 3600, "hard_cap_sec": 315360000,
    },
    "codex": {"group_bonus": 0.08},
}

_MISSING = object()


class BalanceTable:
    """balance.json 的点号路径访问器 + 自校验。

    用法::

        bal = BalanceTable.load("data/balance.json")
        bal.get("economy.bonus_cap")        -> 0.40
        bal.get("water.filter_gain.1")      -> 0.2      （列表下标也走点号）
        bal.base_income("R3")               -> 12.0

    容错原则：任何路径缺失都返回调用方给的 default（或救生圈里的值），**绝不抛异常**。
    """

    def __init__(self, raw=None, logger=None):
        self.raw = raw if isinstance(raw, dict) else {}
        self._log = logger or _log
        self._cache = {}

    # ── 加载 ──

    @classmethod
    def load(cls, path, logger=None):
        """从文件加载；文件缺失或 JSON 损坏时用救生圈 + 告警，绝不崩溃。"""
        lg = logger or _log
        raw = None
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except (OSError, json.JSONDecodeError, ValueError) as e:
            lg.warning("balance.json 加载失败(%s)，启用内置默认值：%s" % (path, e))
        if not isinstance(raw, dict):
            raw = copy.deepcopy(_FALLBACK)
        return cls(raw, logger=lg)

    # ── 访问 ──

    def get(self, path, default=None):
        """点号路径取值。列表下标用数字段（如 ``water.filter_gain.2``）。

        :param path: 形如 ``"economy.base_income.R3"``
        :param default: 路径不存在时的返回值；为 None 时会再回退到内置救生圈
        :returns: 取到的值
        """
        key = (path, default)
        if key in self._cache:
            return self._cache[key]
        val = self._dig(self.raw, path)
        if val is _MISSING:
            val = self._dig(_FALLBACK, path)
            if val is _MISSING:
                val = default
            elif default is not None and val is None:
                val = default
        self._cache[key] = val
        return val

    @staticmethod
    def _dig(root, path):
        """沿点号路径下钻，找不到返回哨兵 `_MISSING`。"""
        cur = root
        for part in path.split("."):
            if isinstance(cur, dict):
                if part not in cur:
                    return _MISSING
                cur = cur[part]
            elif isinstance(cur, (list, tuple)):
                try:
                    cur = cur[int(part)]
                except (ValueError, IndexError):
                    return _MISSING
            else:
                return _MISSING
        return cur

    # ── 常用快捷访问（避免调用方到处写字符串路径）──

    def base_income(self, rarity):
        """某稀有度成鱼的基础产出（金币/分钟）。"""
        return _as_float(self.get("economy.base_income." + str(rarity)), 0.0)

    def growth_cycle_sec(self, rarity):
        """某稀有度的成长周期秒数。"""
        return _as_int(self.get("growth.cycle_sec." + str(rarity)), 1)

    def thresholds(self):
        """成长阶段阈值 {fry, juvenile, adult}（比例 p = age/cycle）。"""
        t = self.get("growth.thresholds")
        return t if isinstance(t, dict) else dict(_FALLBACK["growth"]["thresholds"])

    def stage_coef_table(self):
        """各阶段的产出系数表。"""
        t = self.get("growth.stage_coef")
        return t if isinstance(t, dict) else dict(_FALLBACK["growth"]["stage_coef"])

    def stage_scale_table(self):
        """各阶段的渲染缩放表。"""
        t = self.get("growth.stage_scale")
        return t if isinstance(t, dict) else dict(_FALLBACK["growth"]["stage_scale"])

    def offline_segments(self):
        """离线效率分段表 [[lo_min, hi_min|None, k], ...]。"""
        s = self.get("offline.segments")
        return s if isinstance(s, list) and s else copy.deepcopy(_FALLBACK["offline"]["segments"])

    def coin_scale(self):
        """金币 → 厘 的换算比例（默认 1000）。"""
        return _as_int(self.get("economy.coin_scale"), 1000)

    def bonus_cap(self):
        """装饰 + 族群加成的总上限。"""
        return _as_float(self.get("economy.bonus_cap"), 0.40)

    def water_min(self):
        """水质下限（硬地板，鱼永不因此死亡）。"""
        return _as_float(self.get("water.min"), 50.0)

    def water_max(self):
        """水质上限。"""
        return _as_float(self.get("water.max"), 100.0)

    def quality_floor(self):
        """水质触底时的产出系数下限（准则 L4：永不归零）。"""
        return _as_float(self.get("water.quality_floor"), 0.5)

    def filter_gain(self, level):
        """某过滤器等级的水质增益（点/分钟）；越界自动钳到合法范围。"""
        gains = self.get("water.filter_gain")
        if not isinstance(gains, list) or not gains:
            gains = list(_FALLBACK["water"]["filter_gain"])
        idx = max(0, min(int(level), len(gains) - 1))
        return _as_float(gains[idx], 0.0)

    def capacity_of(self, level):
        """某扩容等级对应的鱼缸容量。"""
        caps = self.get("shop.capacity")
        if not isinstance(caps, list) or not caps:
            return 6
        idx = max(0, min(int(level), len(caps) - 1))
        return _as_int(caps[idx], 6)

    def group_bonus(self):
        """集齐一个族群的加成。"""
        return _as_float(self.get("codex.group_bonus"), 0.08)

    def hard_cap_sec(self):
        """离线时长硬上限（仅防整数溢出，不是收益封顶）。"""
        return _as_int(self.get("offline.hard_cap_sec"), 315360000)

    # ── 校验 ──

    def validate(self):
        """启动即校验。返回问题描述列表（空 = 全部通过）。

        🔴 只返回列表 + 记日志，**绝不抛异常**（准则：数据问题不崩溃）。
        """
        problems = []

        # base_income 必须随稀有度单调递增
        rarities = ["R1", "R2", "R3", "R4", "R5"]
        vals = [self.base_income(r) for r in rarities]
        for i in range(1, len(vals)):
            if not vals[i] > vals[i - 1]:
                problems.append(
                    "economy.base_income 非单调递增：%s=%g 未大于 %s=%g"
                    % (rarities[i], vals[i], rarities[i - 1], vals[i - 1]))

        # stage_coef 各值必须 > 0
        for k, v in sorted(self.stage_coef_table().items()):
            if _as_float(v, 0.0) <= 0:
                problems.append("growth.stage_coef.%s 必须 > 0，实际 %r" % (k, v))

        # stage_scale 各值必须 > 0
        for k, v in sorted(self.stage_scale_table().items()):
            if _as_float(v, 0.0) <= 0:
                problems.append("growth.stage_scale.%s 必须 > 0，实际 %r" % (k, v))

        # thresholds 必须递增
        th = self.thresholds()
        order = [_as_float(th.get("fry"), 0.0), _as_float(th.get("juvenile"), 0.0),
                 _as_float(th.get("adult"), 0.0)]
        if not (order[0] < order[1] < order[2]):
            problems.append("growth.thresholds 必须 fry < juvenile < adult，实际 %r" % (order,))

        # 水质区间
        if not self.water_min() < self.water_max():
            problems.append("water.min(%g) 必须小于 water.max(%g)" % (self.water_min(), self.water_max()))
        if not 0.0 < self.quality_floor() <= 1.0:
            problems.append("water.quality_floor 必须在 (0,1]，实际 %g" % self.quality_floor())

        # 离线分段：首段 lo=0、末段 hi=None、区间连续无缝
        segs = self.offline_segments()
        if not segs:
            problems.append("offline.segments 为空")
        else:
            if _as_float(segs[0][0], -1.0) != 0.0:
                problems.append("offline.segments 首段 lo 必须为 0，实际 %r" % (segs[0][0],))
            if segs[-1][1] is not None:
                problems.append("offline.segments 末段 hi 必须为 null，实际 %r" % (segs[-1][1],))
            for i in range(1, len(segs)):
                prev_hi = segs[i - 1][1]
                cur_lo = segs[i][0]
                if prev_hi is None or _as_float(prev_hi, -1.0) != _as_float(cur_lo, -2.0):
                    problems.append(
                        "offline.segments 第 %d/%d 段不连续：%r -> %r" % (i, i + 1, prev_hi, cur_lo))
            for i, s in enumerate(segs):
                if _as_float(s[2], -1.0) < 0:
                    problems.append("offline.segments[%d] 效率必须 >= 0，实际 %r" % (i, s[2]))

        # 步长
        if _as_int(self.get("offline.fine_step_sec"), 0) <= 0:
            problems.append("offline.fine_step_sec 必须 > 0")
        if _as_int(self.get("offline.coarse_step_sec"), 0) < _as_int(self.get("offline.fine_step_sec"), 0):
            problems.append("offline.coarse_step_sec 不应小于 fine_step_sec")

        # 加成上限
        cap = self.bonus_cap()
        if not 0.0 <= cap <= 1.0:
            problems.append("economy.bonus_cap 必须在 [0,1]，实际 %g" % cap)

        # 容量表与价格表等长
        caps = self.get("shop.capacity") or []
        prices = self.get("shop.capacity_price") or []
        if len(caps) != len(prices):
            problems.append("shop.capacity(%d) 与 shop.capacity_price(%d) 长度不一致"
                            % (len(caps), len(prices)))
        fp = self.get("shop.filter_price") or []
        fg = self.get("water.filter_gain") or []
        if len(fp) != len(fg):
            problems.append("shop.filter_price(%d) 与 water.filter_gain(%d) 长度不一致"
                            % (len(fp), len(fg)))

        # 公式沙盒必须关闭（E10：不安全且 C++ 端无法同源）
        if self.get("economy._experimental_formula") is not None:
            problems.append("economy._experimental_formula 必须为 null（发布配置禁止启用公式沙盒）")

        if problems:
            for p in problems:
                self._log.warning("[balance] %s" % p)
        return problems


# ══════════════════════════════════════════════════════════════
#  UI 文案
# ══════════════════════════════════════════════════════════════

class UIText:
    """ui_text.json 访问器。点号路径 + `{}` 占位符格式化。

    🔴 准则 L6：代码内禁止中文字面量，所有面向用户的字符串都从这里取。
    """

    def __init__(self, raw=None, logger=None):
        self.raw = raw if isinstance(raw, dict) else {}
        self._log = logger or _log

    @classmethod
    def load(cls, path, logger=None):
        """从文件加载；失败返回空表 + 告警（取不到文案时回退为路径本身，便于定位）。"""
        lg = logger or _log
        raw = None
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except (OSError, json.JSONDecodeError, ValueError) as e:
            lg.warning("ui_text.json 加载失败(%s)：%s" % (path, e))
        return cls(raw, logger=lg)

    def get(self, path, default=None, **fmt):
        """取文案。

        :param path: 点号路径，如 ``"buttons.claim"``
        :param default: 缺失时的回退值；None 则回退为 path 本身（方便一眼看出漏配）
        :param fmt: 传给 ``str.format`` 的占位符
        """
        val = BalanceTable._dig(self.raw, path)
        if val is _MISSING or not isinstance(val, (str, list)):
            return default if default is not None else path
        if isinstance(val, list):
            return val
        if fmt:
            try:
                return val.format(**fmt)
            except (KeyError, IndexError, ValueError):
                return val
        return val

    def pick(self, path, index, default=""):
        """从字符串数组里按索引取一条（用于离线卡片的文案变体）。"""
        arr = BalanceTable._dig(self.raw, path)
        if not isinstance(arr, list) or not arr:
            return default
        return str(arr[int(index) % len(arr)])


# ══════════════════════════════════════════════════════════════
#  一次性加载全部数据
# ══════════════════════════════════════════════════════════════

def load_all(data_dir, logger=None):
    """加载 data/ 下四个文件。

    :param data_dir: data 目录路径
    :returns: (BalanceTable, FishLibrary, DecorLibrary, UIText)
    """
    lg = logger or _log
    bal = BalanceTable.load(os.path.join(data_dir, "balance.json"), logger=lg)

    species = FishLibrary(logger=lg)
    fish_path = os.path.join(data_dir, "fish_data.json")
    if os.path.isfile(fish_path):
        species.load_from_json(fish_path)
    else:
        lg.warning("fish_data.json 缺失：%s" % fish_path)

    decor = DecorLibrary(logger=lg)
    decor_path = os.path.join(data_dir, "decor_data.json")
    if os.path.isfile(decor_path):
        decor.load_from_json(decor_path)
    else:
        lg.warning("decor_data.json 缺失：%s" % decor_path)

    text = UIText.load(os.path.join(data_dir, "ui_text.json"), logger=lg)
    return bal, species, decor, text
