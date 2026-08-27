# -*- coding: utf-8 -*-
"""
core/deck.py — 决策卡池绑定器（B2a，零侵入接管引擎卡池）

接管原理
--------
decision_tree.DecisionTree 的 self.decision_cards 是一个**普通可写 list 属性**
（在 __init__ 里由 self._load_decision_cards() 赋值）。因此完全不需要改引擎的抽卡逻辑：
只要在每次引擎取卡之前，把「已按篇章过滤 + 已按 AntiRepeat 计算好有效权重」的卡池
写回 dt.decision_cards，就完成了接管。

    binder.bind(dt, era="dynasty")      # 写回 dt.decision_cards
    cards = dt.get_available_cards()    # 引擎照常工作，但吃的是我们的池子
    ...玩家做出选择后...
    binder.notify_picked(card["id"])    # 回写防重复状态

双卡池零串池
------------
绑定 dynasty 时绝不会出现 modern 的卡，反之亦然。
卡的 era 字段缺失 / 为空 / 非法时一律视为 dynasty（存量 16 张已全部标注 era="dynasty"）。
era == "any" 的卡两篇通用。

降级
----
bind() 与 pick_card() 都遵守 AntiRepeatEngine 的 4 级降级阶梯，
卡池耗尽时写入 FALLBACK_CARD 兜底，绝不产生空卡池、绝不抛异常。

本模块零 UI 依赖：禁止 import tkinter / print / 读取标准输入 / time.sleep。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from core.antirepeat import (
    DEGRADE_FALLBACK,
    DEGRADE_IGNORE_COOLDOWN,
    DEGRADE_IGNORE_SEEN,
    DEGRADE_LABELS,
    DEGRADE_NORMAL,
    AntiRepeatEngine,
    PickResult,
)
from core.constants import FALLBACK_CARD
from core.models import CardItem

# 合法篇章取值
ERA_DYNASTY: str = "dynasty"
ERA_MODERN: str = "modern"
ERA_ANY: str = "any"
VALID_ERAS: Tuple[str, ...] = (ERA_DYNASTY, ERA_MODERN, ERA_ANY)


def normalize_era(value: Any) -> str:
    """把任意 era 取值归一化为合法篇章。

    缺失 / 空串 / 非法值一律视为 dynasty（存量卡兼容），不抛异常。
    """
    try:
        text = str(value or "").strip().lower()
    except Exception:
        return ERA_DYNASTY
    return text if text in VALID_ERAS else ERA_DYNASTY


@dataclass
class BindResult:
    """一次 bind() 的结果摘要，供表现层展示与调试。"""

    era: str = ERA_DYNASTY
    """本次绑定的篇章。"""

    size: int = 0
    """写回 dt.decision_cards 的卡片数量。"""

    degraded: int = DEGRADE_NORMAL
    """达成非空卡池所用的降级级别 0-3。"""

    reason: str = ""
    """降级提示文案。"""

    card_ids: List[str] = field(default_factory=list)
    """写回卡池的卡 id 列表（按写回顺序）。"""

    weights: Dict[str, float] = field(default_factory=dict)
    """每张卡的有效权重 W_eff。"""

    pool_total: int = 0
    """该篇章下的卡池总量（未经防重复过滤）。"""


class DeckBinder:
    """决策卡池绑定器。与 AntiRepeatEngine 协作，零侵入接管引擎卡池。"""

    def __init__(
        self,
        content: Any = None,
        anti_repeat: Optional[AntiRepeatEngine] = None,
        profile: Any = None,
    ) -> None:
        """构造绑定器。

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
        self.era: str = ERA_DYNASTY
        self.last_bind: Optional[BindResult] = None
        self._origin_cards: Dict[int, List[Dict[str, Any]]] = {}

    # ───────────────────────────────────────────────────────
    # 卡池查询
    # ───────────────────────────────────────────────────────
    def pool(self, era: str = ERA_DYNASTY) -> List[CardItem]:
        """返回指定篇章的全部卡（含 era='any' 的通用卡），零串池。

        Args:
            era: 'dynasty' 或 'modern'（其它取值归一化为 dynasty）。

        Returns:
            CardItem 列表；内容加载器缺失时返回空列表。
        """
        target = normalize_era(era)
        if self.content is None:
            return []
        try:
            all_cards = self.content.cards(None)
        except Exception:
            return []
        result: List[CardItem] = []
        for card in all_cards or []:
            card_era = normalize_era(getattr(card, "era", ERA_DYNASTY))
            if card_era == target or card_era == ERA_ANY:
                result.append(card)
        return result

    def pool_ids(self, era: str = ERA_DYNASTY) -> List[str]:
        """返回指定篇章卡池的 id 列表。"""
        return [c.id for c in self.pool(era)]

    # ───────────────────────────────────────────────────────
    # 条件与倍率（复刻引擎语义，只读，不改引擎）
    # ───────────────────────────────────────────────────────
    @staticmethod
    def dimensions_of(dt: Any) -> Dict[str, float]:
        """从 DecisionTree 实例抽取 {维度名大写: 当前值}，取不到返回空 dict。"""
        out: Dict[str, float] = {}
        dims = getattr(dt, "dimensions", None)
        if not isinstance(dims, dict):
            return out
        for key, value in dims.items():
            name = getattr(key, "name", None) or str(key)
            try:
                out[str(name).upper()] = float(value)
            except (TypeError, ValueError):
                continue
        return out

    @staticmethod
    def traits_of(dt: Any, player: Any = None) -> List[str]:
        """取玩家特质列表（优先用显式传入的 player，其次 dt.player）。"""
        target = player if player is not None else getattr(dt, "player", None)
        traits = getattr(target, "traits", None)
        if isinstance(traits, (list, tuple, set)):
            return [str(t) for t in traits]
        return []

    def card_conditions_ok(
        self,
        card: Any,
        dimensions: Optional[Dict[str, float]] = None,
        traits: Optional[List[str]] = None,
    ) -> bool:
        """复刻 DecisionTree._check_card_conditions 的判定语义（只读，不改引擎）。

        规则：required_traits 必须全部具备；conditions 中形如 min_<dimension> 的键，
        对应维度当前值必须 >= 阈值；非法维度后缀直接跳过（与引擎一致）。
        """
        conditions = self._conditions_of(card)
        if not conditions:
            return True
        owned = set(traits or [])
        required = conditions.get("required_traits", []) or []
        if isinstance(required, (list, tuple, set)):
            for trait in required:
                if str(trait) not in owned:
                    return False
        dims = dimensions or {}
        for key, threshold in conditions.items():
            if not isinstance(key, str) or not key.startswith("min_"):
                continue
            dim_name = key[4:].upper()
            if dim_name not in dims:
                continue  # 非法/未知维度：与引擎一致地跳过
            try:
                if dims[dim_name] < float(threshold):
                    return False
            except (TypeError, ValueError):
                continue
        return True

    @staticmethod
    def _conditions_of(card: Any) -> Dict[str, Any]:
        """统一取 conditions（兼容 CardItem 与 raw dict）。"""
        if isinstance(card, dict):
            conds = card.get("conditions", {})
        else:
            conds = getattr(card, "conditions", {})
        return conds if isinstance(conds, dict) else {}

    @staticmethod
    def engine_context_mult(card: Any, dt: Any = None, player: Any = None) -> float:
        """复刻引擎 get_available_cards 里的特质 / 危机权重倍率。

        仅供 pick_card() 这类**不经过引擎**的直抽路径使用。
        bind() 不应用它 —— 因为引擎自己会再乘一次，重复应用会导致倍率翻倍。
        """
        if isinstance(card, dict):
            description = str(card.get("description", "") or "")
            title = str(card.get("title", "") or "")
        else:
            description = str(getattr(card, "description", "") or "")
            title = str(getattr(card, "title", "") or "")
        mult = 1.0
        target = player if player is not None else getattr(dt, "player", None)
        traits = getattr(target, "traits", None) or []
        for trait in traits:
            if trait in ("仁慈", "慷慨") and "赈济" in description:
                mult *= 1.5
            elif trait in ("残暴", "吝啬") and "镇压" in description:
                mult *= 1.5
        if getattr(dt, "crisis_imminent", False) and "危机" in title:
            mult *= 2.0
        return mult

    # ───────────────────────────────────────────────────────
    # 绑定（核心）
    # ───────────────────────────────────────────────────────
    def bind(
        self,
        dt: Any,
        era: str = ERA_DYNASTY,
        player: Any = None,
        talent_mult_of: Optional[Callable[[Any], float]] = None,
        context_mult_of: Optional[Callable[[Any], float]] = None,
    ) -> BindResult:
        """按篇章过滤卡池、计算有效权重，并写回 dt.decision_cards。

        绝不抛异常；卡池为空时写入 FALLBACK_CARD 兜底并把 degraded 置为 3。

        Args:
            dt: DecisionTree 实例（需具备可写属性 decision_cards）。
            era: 'dynasty' 或 'modern'。
            player: 玩家对象；缺省用 dt.player。
            talent_mult_of: 天赋倍率取值器（B2b 注入），签名 (CardItem) -> float。
            context_mult_of: 额外情境倍率取值器，签名 (CardItem) -> float。
                注意不要在此重复引擎自带的特质/危机倍率。

        Returns:
            BindResult 摘要。
        """
        target_era = normalize_era(era)
        self.era = target_era
        try:
            result = self._bind_impl(dt, target_era, player, talent_mult_of, context_mult_of)
        except Exception as exc:
            result = self._bind_fallback(dt, target_era, f"绑定异常：{type(exc).__name__}")
        self.last_bind = result
        return result

    def _bind_impl(
        self,
        dt: Any,
        target_era: str,
        player: Any,
        talent_mult_of: Optional[Callable[[Any], float]],
        context_mult_of: Optional[Callable[[Any], float]],
    ) -> BindResult:
        """bind() 的实现体。"""
        cards = self.pool(target_era)
        if not cards:
            return self._bind_fallback(dt, target_era, "该篇章无可用卡")

        self._remember_origin(dt)
        dims = self.dimensions_of(dt)
        traits = self.traits_of(dt, player)

        for level in (DEGRADE_NORMAL, DEGRADE_IGNORE_COOLDOWN, DEGRADE_IGNORE_SEEN):
            pairs = self._weighted_pool(
                cards, level, dims, traits, talent_mult_of, context_mult_of
            )
            if not pairs:
                continue
            engine_cards: List[Dict[str, Any]] = []
            weights: Dict[str, float] = {}
            for card, w_eff in pairs:
                raw = card.to_engine_dict()
                raw["weight"] = w_eff
                engine_cards.append(raw)
                weights[card.id] = w_eff
            dt.decision_cards = engine_cards
            return BindResult(
                era=target_era,
                size=len(engine_cards),
                degraded=level,
                reason=DEGRADE_LABELS.get(level, ""),
                card_ids=[c["id"] for c in engine_cards],
                weights=weights,
                pool_total=len(cards),
            )

        return self._bind_fallback(dt, target_era, "卡池已耗尽", pool_total=len(cards))

    def _weighted_pool(
        self,
        cards: List[CardItem],
        level: int,
        dims: Dict[str, float],
        traits: List[str],
        talent_mult_of: Optional[Callable[[Any], float]],
        context_mult_of: Optional[Callable[[Any], float]],
    ) -> List[Tuple[CardItem, float]]:
        """在给定降级级别下计算 (卡, 有效权重) 列表，只保留 W_eff > 0 的卡。"""
        pairs: List[Tuple[CardItem, float]] = []
        for card in cards:
            ok = self.card_conditions_ok(card, dims, traits)
            t_mult = 1.0
            if talent_mult_of is not None:
                try:
                    t_mult = float(talent_mult_of(card))
                except Exception:
                    t_mult = 1.0
            c_mult = 1.0
            if context_mult_of is not None:
                try:
                    c_mult = float(context_mult_of(card))
                except Exception:
                    c_mult = 1.0
            w_eff = self.anti_repeat.effective_weight(
                item_id=card.id,
                base_weight=card.weight,
                talent_mult=t_mult,
                context_mult=c_mult,
                condition_ok=ok,
                level=level,
            )
            if w_eff > 0.0:
                pairs.append((card, w_eff))
        return pairs

    def _bind_fallback(
        self, dt: Any, target_era: str, reason: str, pool_total: int = 0
    ) -> BindResult:
        """卡池不可用时写入兜底卡，保证 dt.decision_cards 永不为空。"""
        fallback = dict(FALLBACK_CARD)
        fallback["era"] = target_era
        try:
            self._remember_origin(dt)
            dt.decision_cards = [fallback]
        except Exception:
            pass
        return BindResult(
            era=target_era,
            size=1,
            degraded=DEGRADE_FALLBACK,
            reason=f"{DEGRADE_LABELS[DEGRADE_FALLBACK]}（{reason}）",
            card_ids=[str(fallback.get("id", ""))],
            weights={str(fallback.get("id", "")): 1.0},
            pool_total=pool_total,
        )

    def _remember_origin(self, dt: Any) -> None:
        """首次绑定前记住引擎原始卡池，供 restore() 还原。"""
        key = id(dt)
        if key in self._origin_cards:
            return
        origin = getattr(dt, "decision_cards", None)
        if isinstance(origin, list):
            self._origin_cards[key] = list(origin)

    def restore(self, dt: Any) -> bool:
        """还原引擎原始卡池（撤销接管）。未绑定过返回 False。"""
        origin = self._origin_cards.pop(id(dt), None)
        if origin is None:
            return False
        try:
            dt.decision_cards = list(origin)
            return True
        except Exception:
            return False

    # ───────────────────────────────────────────────────────
    # 直抽（不经过引擎）
    # ───────────────────────────────────────────────────────
    def pick_card(
        self,
        era: str = ERA_DYNASTY,
        dt: Any = None,
        player: Any = None,
        talent_mult_of: Optional[Callable[[Any], float]] = None,
        mark: bool = True,
        exclude: Optional[List[str]] = None,
    ) -> PickResult:
        """直接从指定篇章抽一张卡（走 AntiRepeat 的 4 级降级）。

        与 bind() 的区别：本方法不经过引擎，因此会自行应用引擎的特质/危机倍率。
        契约同 AntiRepeatEngine.pick()：永远返回非空 PickResult，永不抛异常。

        Returns:
            PickResult，其 item 为 CardItem（L3 兜底时为 FALLBACK_CARD 的 dict 副本）。
        """
        target_era = normalize_era(era)
        cards = self.pool(target_era)
        dims = self.dimensions_of(dt)
        traits = self.traits_of(dt, player)
        fallback = dict(FALLBACK_CARD)
        fallback["era"] = target_era
        return self.anti_repeat.pick(
            cards,
            id_of=lambda c: getattr(c, "id", ""),
            weight_of=lambda c: getattr(c, "weight", 1.0),
            condition_ok=lambda c: self.card_conditions_ok(c, dims, traits),
            talent_mult_of=talent_mult_of,
            context_mult_of=(lambda c: self.engine_context_mult(c, dt, player)),
            fallback=fallback,
            mark=mark,
            exclude=exclude,
        )

    def pick_hand(
        self,
        count: int = 3,
        era: str = ERA_DYNASTY,
        dt: Any = None,
        player: Any = None,
        talent_mult_of: Optional[Callable[[Any], float]] = None,
    ) -> List[PickResult]:
        """一次抽 count 张互不重复的卡（引擎 get_available_cards 的直抽等价物）。"""
        target_era = normalize_era(era)
        cards = self.pool(target_era)
        dims = self.dimensions_of(dt)
        traits = self.traits_of(dt, player)
        fallback = dict(FALLBACK_CARD)
        fallback["era"] = target_era
        return self.anti_repeat.pick_many(
            cards,
            count=count,
            id_of=lambda c: getattr(c, "id", ""),
            weight_of=lambda c: getattr(c, "weight", 1.0),
            condition_ok=lambda c: self.card_conditions_ok(c, dims, traits),
            talent_mult_of=talent_mult_of,
            context_mult_of=(lambda c: self.engine_context_mult(c, dt, player)),
            fallback=fallback,
        )

    # ───────────────────────────────────────────────────────
    # 状态回写
    # ───────────────────────────────────────────────────────
    def notify_picked(self, card_id: str, cooldown_runs: Optional[int] = None) -> None:
        """玩家实际消费了某张卡之后调用，回写防重复状态。

        走 bind() + 引擎抽卡路径时，引擎不会通知我们，必须由表现层在结算后显式调用。
        """
        if not card_id or card_id == FALLBACK_CARD.get("id"):
            return
        if cooldown_runs is None:
            card = None
            if self.content is not None:
                try:
                    card = self.content.card(card_id)
                except Exception:
                    card = None
            cooldown_runs = getattr(card, "cooldown_runs", None)
        self.anti_repeat.mark_picked(card_id, cooldown_runs)

    def begin_run(self) -> None:
        """一局开始钩子（转发给 AntiRepeatEngine，便于表现层统一调用）。"""
        self.anti_repeat.begin_run()

    def end_run(self, result: Optional[Dict[str, Any]] = None) -> None:
        """一局结束钩子（转发给 AntiRepeatEngine）。"""
        self.anti_repeat.end_run(result)


__all__ = [
    "DeckBinder",
    "BindResult",
    "normalize_era",
    "ERA_DYNASTY",
    "ERA_MODERN",
    "ERA_ANY",
    "VALID_ERAS",
]
