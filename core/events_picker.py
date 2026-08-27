# -*- coding: utf-8 -*-
"""
core/events_picker.py — 人生事件双通道取样器（B2a）

两个通道
--------
1. 自动匹配 pick_auto(player)：按玩家的年龄档 / 财富 / 人格 / 特质 / 职业类别
   自动选池，语义与 main.py::life_event() 的既有分支完全一致
   （generic + by_wealth + by_personality + by_age.<age_group> +
   by_career.<category> + by_trait.<trait>），保证行为不漂移。

2. 按池名点名 pick_from(pool_name)：显式指定分组，例如 'by_age.childhood'。

   为什么必须有点名通道：background_choice() 里硬编码了 player.age = 20，
   冒险循环 age += 10，所以年龄恒为 20/30/…/90。将来新增的
   childhood / teenage / youth 三个池**永远匹配不到**自动通道，
   必须由出身流程的「早年回顾」钩子显式点名消费。

池名规范
--------
    列表型分组（如 generic）        -> "generic"
    字典型分组（如 by_age）         -> "by_age.20s" / "by_wealth.rich"

同样接 AntiRepeatEngine，同样遵守 4 级降级与 pick() 契约：
永远返回非空 PickResult、永不抛异常、永不返回 None。

兼容性说明
----------
ContentLoader._build_index() 目前只索引 dict 型分组，列表型的 generic 分组会被丢弃，
因此本模块优先直接读取 ContentLoader.raw['event_templates'] 自建索引（同时兼容
两种形状），并在读不到时回退到 ContentLoader.events_dict()。这样既不改动
content_loader.py（避免与并行批次冲突），又能完整覆盖全部 22 条存量事件。

本模块零 UI 依赖：禁止 import tkinter / print / 读取标准输入 / time.sleep。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from core.antirepeat import AntiRepeatEngine, PickResult
from core.constants import FALLBACK_EVENT

# 池名分隔符：<group><SEP><sub>
POOL_SEP: str = "."

# 事件分组键（与 content_loader.EVENT_GROUP_KEYS 保持一致，R8 不得删改）
EVENT_GROUP_KEYS: Tuple[str, ...] = (
    "generic",
    "by_wealth",
    "by_personality",
    "by_age",
    "by_career",
    "by_trait",
)

# MBTI 大类分组（复刻 main.py::life_event 的判定）
MBTI_NT: Tuple[str, ...] = ("INTJ", "INTP", "ENTJ", "ENTP")
MBTI_NF: Tuple[str, ...] = ("INFP", "INFJ", "ENFP", "ENFJ")

# 早年池：自动通道永远匹配不到，只能由出身流程点名消费
EARLY_LIFE_POOLS: Tuple[str, ...] = (
    "by_age.childhood",
    "by_age.teenage",
    "by_age.youth",
)


def age_group(age: Any) -> str:
    """复刻 main.py::get_age_group 的年龄档语义。非法输入回退 '20s'。"""
    try:
        value = int(age)
    except (TypeError, ValueError):
        return "20s"
    if value < 30:
        return "20s"
    if value < 40:
        return "30s"
    if value < 50:
        return "40s"
    if value < 60:
        return "50s"
    return "60+"


def make_pool_name(group: str, sub: Optional[str] = None) -> str:
    """拼装池名：无子组返回 group，有子组返回 'group.sub'。"""
    if not sub:
        return str(group)
    return f"{group}{POOL_SEP}{sub}"


def split_pool_name(pool_name: str) -> Tuple[str, Optional[str]]:
    """拆解池名为 (group, sub)。无分隔符时 sub 为 None。"""
    text = str(pool_name or "")
    if POOL_SEP in text:
        group, sub = text.split(POOL_SEP, 1)
        return group, sub
    return text, None


@dataclass
class PoolInfo:
    """一个事件池的元信息。"""

    name: str = ""
    """池名，如 'generic' 或 'by_age.20s'。"""

    group: str = ""
    """所属分组键。"""

    sub: Optional[str] = None
    """子组名（列表型分组为 None）。"""

    size: int = 0
    """池内事件数量。"""

    event_ids: List[str] = field(default_factory=list)
    """池内事件 id 列表。"""


class EventPicker:
    """人生事件取样器：自动匹配通道 + 按池名点名通道。"""

    def __init__(
        self,
        content: Any = None,
        anti_repeat: Optional[AntiRepeatEngine] = None,
        profile: Any = None,
    ) -> None:
        """构造取样器并建立池索引。

        Args:
            content: core.content_loader.ContentLoader 实例（可为 None）。
            anti_repeat: 共享的 AntiRepeatEngine；为 None 时自建一个纯内存实例。
            profile: core.profile.Profile 实例（可为 None）。
        """
        self.content: Any = content
        self.anti_repeat: AntiRepeatEngine = (
            anti_repeat if anti_repeat is not None else AntiRepeatEngine(profile)
        )
        self.profile: Any = profile
        self._pools: Dict[str, List[Dict[str, Any]]] = {}
        self.refresh()

    # ───────────────────────────────────────────────────────
    # 索引构建
    # ───────────────────────────────────────────────────────
    def refresh(self) -> "EventPicker":
        """（重新）建立池索引。内容缺失/损坏时得到空索引，不抛异常。"""
        self._pools = {}
        templates = self._read_templates()
        for group_key, group in templates.items():
            if isinstance(group, list):
                items = self._normalize_items(group, group_key, None)
                if items:
                    self._pools[make_pool_name(group_key)] = items
            elif isinstance(group, dict):
                for sub_key, raw_items in group.items():
                    if not isinstance(raw_items, list):
                        continue
                    items = self._normalize_items(raw_items, group_key, sub_key)
                    if items:
                        self._pools[make_pool_name(group_key, sub_key)] = items
        return self

    def _read_templates(self) -> Dict[str, Any]:
        """读取 event_templates。优先 ContentLoader.raw（含列表型 generic 分组），
        回退 ContentLoader.events_dict()。"""
        if self.content is None:
            return {}
        raw_templates: Dict[str, Any] = {}
        try:
            raw = getattr(self.content, "raw", None)
            if isinstance(raw, dict):
                candidate = raw.get("event_templates", None)
                if isinstance(candidate, dict):
                    raw_templates = dict(candidate)
        except Exception:
            raw_templates = {}
        if raw_templates:
            return raw_templates
        try:
            merged = self.content.events_dict()
            if isinstance(merged, dict):
                return dict(merged)
        except Exception:
            pass
        return {}

    @staticmethod
    def _normalize_items(
        raw_items: Iterable[Any], group_key: str, sub_key: Optional[str]
    ) -> List[Dict[str, Any]]:
        """过滤非 dict 项，并为缺失 id 的事件补一个稳定的合成 id。"""
        out: List[Dict[str, Any]] = []
        index = 0
        for item in raw_items or []:
            if not isinstance(item, dict):
                continue
            event = dict(item)
            if not event.get("id"):
                event["id"] = f"ev_auto_{group_key}_{sub_key or 'root'}_{index}"
            out.append(event)
            index += 1
        return out

    # ───────────────────────────────────────────────────────
    # 池查询
    # ───────────────────────────────────────────────────────
    def pools(self) -> List[str]:
        """返回全部可用池名（已排序）。"""
        return sorted(self._pools.keys())

    def has_pool(self, pool_name: str) -> bool:
        """判断某池名是否存在且非空。"""
        return bool(self._pools.get(str(pool_name)))

    def pool_items(self, pool_name: str) -> List[Dict[str, Any]]:
        """返回某池的事件列表（副本）。池不存在返回空列表。"""
        return list(self._pools.get(str(pool_name), []))

    def pool_info(self, pool_name: str) -> PoolInfo:
        """返回某池的元信息。池不存在时 size 为 0。"""
        name = str(pool_name)
        group, sub = split_pool_name(name)
        items = self._pools.get(name, [])
        return PoolInfo(
            name=name,
            group=group,
            sub=sub,
            size=len(items),
            event_ids=[str(e.get("id", "")) for e in items],
        )

    def all_event_ids(self) -> List[str]:
        """返回全部事件 id（跨池去重，按池名 + 顺序稳定输出）。"""
        seen: set = set()
        out: List[str] = []
        for name in self.pools():
            for event in self._pools[name]:
                eid = str(event.get("id", ""))
                if eid and eid not in seen:
                    seen.add(eid)
                    out.append(eid)
        return out

    # ───────────────────────────────────────────────────────
    # 自动匹配通道
    # ───────────────────────────────────────────────────────
    def match_pools(self, player: Any) -> List[str]:
        """按玩家状态自动选池，语义与 main.py::life_event 的分支一致。

        Args:
            player: 玩家对象（鸭子类型，缺字段一律用安全默认值）。

        Returns:
            匹配到的池名列表（去重、保持判定顺序）。
        """
        names: List[str] = ["generic"]

        wealth = self._num(player, "wealth", 0.0)
        if wealth >= 7:
            names.append("by_wealth.rich")
        elif wealth <= 2:
            names.append("by_wealth.poor")

        ei = self._num(player, "EI", 0.0)
        names.append("by_personality.extrovert" if ei > 0 else "by_personality.introvert")

        mbti = str(getattr(player, "mbti_code", "") or "").upper()
        if mbti in MBTI_NT:
            names.append("by_personality.nt_rational")
        if mbti in MBTI_NF:
            names.append("by_personality.nf_idealist")

        if self._num(player, "strength", 0.0) >= 8:
            names.append("by_personality.strong_warrior")
        if self._num(player, "intelligence", 0.0) >= 8:
            names.append("by_personality.smart_scholar")

        traits = getattr(player, "traits", None) or []
        if isinstance(traits, (list, tuple, set)) and "冒险精神" in set(str(t) for t in traits):
            names.append("by_personality.adventurer")

        # 按职业类别：career_id -> category（需 ContentLoader 且玩家已选定职业）
        career_id = getattr(player, "career_id", None)
        if career_id and self.content is not None:
            try:
                career = self.content.career(str(career_id))
                if career is not None:
                    cat = getattr(career, "category", None)
                    if cat:
                        names.append(make_pool_name("by_career", str(cat)))
            except Exception:
                pass

        # 按特质：玩家拥有的每个特质若有对应池则接入
        for t in set(str(x) for x in traits):
            name = make_pool_name("by_trait", t)
            if self.has_pool(name):
                names.append(name)

        names.append(make_pool_name("by_age", age_group(getattr(player, "age", 20))))

        out: List[str] = []
        for name in names:
            if name not in out and self.has_pool(name):
                out.append(name)
        return out

    def pick_auto(
        self,
        player: Any,
        extra_pools: Optional[Iterable[str]] = None,
        exclude_pools: Optional[Iterable[str]] = None,
        talent_mult_of: Optional[Callable[[Any], float]] = None,
        mark: bool = True,
    ) -> PickResult:
        """自动匹配通道：按玩家状态选池并抽一条事件。

        契约：永远返回非空 PickResult，永不抛异常，永不返回 None。

        Args:
            player: 玩家对象。
            extra_pools: 额外并入的池名（如临时活动池）。
            exclude_pools: 本次排除的池名。
            talent_mult_of: 天赋倍率取值器（B2b 注入），签名 (event_dict) -> float。
            mark: 抽中后是否回写防重复状态。

        Returns:
            PickResult，item 为事件 dict。
        """
        try:
            names = self.match_pools(player)
            for name in extra_pools or ():
                if name not in names and self.has_pool(name):
                    names.append(name)
            blocked = set(exclude_pools or ())
            names = [n for n in names if n not in blocked]
            candidates = self._merge_pools(names)
        except Exception:
            return self.anti_repeat.pick([], fallback=dict(FALLBACK_EVENT))
        return self._pick(candidates, player, talent_mult_of, mark)

    # ───────────────────────────────────────────────────────
    # 点名通道
    # ───────────────────────────────────────────────────────
    def pick_from(
        self,
        pool_name: Any,
        player: Any = None,
        talent_mult_of: Optional[Callable[[Any], float]] = None,
        mark: bool = True,
    ) -> PickResult:
        """点名通道：从显式指定的池（可多个）抽一条事件。

        池不存在时不报错，直接走 L3 兜底 —— 这样 B3 尚未落地 childhood /
        teenage / youth 内容时，出身流程的「早年回顾」钩子也能安全先接上。

        Args:
            pool_name: 池名字符串，或池名可迭代集合。
            player: 玩家对象（用于事件条件判定，可为 None）。
            talent_mult_of: 天赋倍率取值器。
            mark: 抽中后是否回写防重复状态。

        Returns:
            PickResult，item 为事件 dict。
        """
        if isinstance(pool_name, str):
            names: List[str] = [pool_name]
        else:
            try:
                names = [str(n) for n in (pool_name or [])]
            except Exception:
                names = []
        candidates = self._merge_pools(names)
        return self._pick(candidates, player, talent_mult_of, mark)

    def pick_early_life(
        self,
        player: Any = None,
        stage: Optional[str] = None,
        talent_mult_of: Optional[Callable[[Any], float]] = None,
        mark: bool = True,
    ) -> PickResult:
        """「早年回顾」专用快捷入口（出身流程钩子）。

        Args:
            player: 玩家对象。
            stage: 'childhood' / 'teenage' / 'youth'；为 None 时三池合并抽取。
            talent_mult_of: 天赋倍率取值器。
            mark: 抽中后是否回写防重复状态。
        """
        if stage:
            names: List[str] = [make_pool_name("by_age", str(stage))]
        else:
            names = list(EARLY_LIFE_POOLS)
        return self.pick_from(names, player, talent_mult_of, mark)

    # ───────────────────────────────────────────────────────
    # 内部：合并与抽取
    # ───────────────────────────────────────────────────────
    def _merge_pools(self, names: Iterable[str]) -> List[Dict[str, Any]]:
        """合并多个池的事件，按 id 去重并保持顺序。"""
        out: List[Dict[str, Any]] = []
        seen: set = set()
        for name in names or ():
            for event in self._pools.get(str(name), []):
                eid = str(event.get("id", ""))
                if eid and eid in seen:
                    continue
                if eid:
                    seen.add(eid)
                out.append(event)
        return out

    def _pick(
        self,
        candidates: List[Dict[str, Any]],
        player: Any,
        talent_mult_of: Optional[Callable[[Any], float]],
        mark: bool,
    ) -> PickResult:
        """统一抽取入口，绑定条件判定与兜底事件。"""
        return self.anti_repeat.pick(
            candidates,
            condition_ok=(lambda ev: self.event_conditions_ok(ev, player)),
            talent_mult_of=talent_mult_of,
            fallback=dict(FALLBACK_EVENT),
            mark=mark,
        )

    # ───────────────────────────────────────────────────────
    # 事件条件判定
    # ───────────────────────────────────────────────────────
    def event_conditions_ok(self, event: Any, player: Any = None) -> bool:
        """判定事件的可选 conditions 是否满足。无 conditions 恒为 True。

        支持的键：
            min_<stat> / max_<stat>   数值下限 / 上限（stat 为 player 的小写属性名）
            min_age / max_age         年龄区间
            required_traits           必须全部具备的特质
            forbidden_traits          不得具备的特质
        未知键一律忽略（前向兼容），任何异常都判为满足，绝不因条件判定而阻断游戏。
        """
        try:
            if not isinstance(event, dict):
                return True
            conditions = event.get("conditions", {})
            if not isinstance(conditions, dict) or not conditions:
                return True
            if player is None:
                return True

            owned = set()
            traits = getattr(player, "traits", None) or []
            if isinstance(traits, (list, tuple, set)):
                owned = set(str(t) for t in traits)

            for trait in conditions.get("required_traits", []) or []:
                if str(trait) not in owned:
                    return False
            for trait in conditions.get("forbidden_traits", []) or []:
                if str(trait) in owned:
                    return False

            for key, threshold in conditions.items():
                if not isinstance(key, str):
                    continue
                if key.startswith("min_"):
                    stat = key[4:]
                    if not self._has_stat(player, stat):
                        continue
                    if self._num(player, stat, 0.0) < float(threshold):
                        return False
                elif key.startswith("max_"):
                    stat = key[4:]
                    if not self._has_stat(player, stat):
                        continue
                    if self._num(player, stat, 0.0) > float(threshold):
                        return False
            return True
        except Exception:
            return True

    @staticmethod
    def _has_stat(player: Any, stat: str) -> bool:
        """玩家是否具备该属性（同时接受原名与小写名）。"""
        return hasattr(player, stat) or hasattr(player, str(stat).lower())

    @staticmethod
    def _num(player: Any, stat: str, default: float = 0.0) -> float:
        """安全读取玩家数值属性。"""
        value = getattr(player, stat, None)
        if value is None:
            value = getattr(player, str(stat).lower(), None)
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    # ───────────────────────────────────────────────────────
    # 状态回写与生命周期
    # ───────────────────────────────────────────────────────
    def notify_picked(self, event_id: str, cooldown_runs: Optional[int] = None) -> None:
        """事件被实际消费后回写防重复状态（mark=False 抽取时使用）。"""
        if not event_id or event_id == FALLBACK_EVENT.get("id"):
            return
        self.anti_repeat.mark_picked(event_id, cooldown_runs)

    def begin_run(self) -> None:
        """一局开始钩子（转发给 AntiRepeatEngine）。"""
        self.anti_repeat.begin_run()

    def end_run(self, result: Optional[Dict[str, Any]] = None) -> None:
        """一局结束钩子（转发给 AntiRepeatEngine）。"""
        self.anti_repeat.end_run(result)


__all__ = [
    "EventPicker",
    "PoolInfo",
    "age_group",
    "make_pool_name",
    "split_pool_name",
    "EARLY_LIFE_POOLS",
    "EVENT_GROUP_KEYS",
    "POOL_SEP",
]
