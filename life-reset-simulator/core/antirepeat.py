# -*- coding: utf-8 -*-
"""
core/antirepeat.py — 防重复三件套 + 4 级降级抽样引擎（B2a）

三件套
------
1. 单局已见集合 seen_this_run：本局抽中过的 id 永不再抽（生命周期 = 单局）。
2. 跨局冷却 cooldown：抽中后置为条目声明的 cooldown_runs（缺省 DEFAULT_COOLDOWN_RUNS），
   每开新局递减 1，归零后解除。
3. 权重衰减 decay：抽中后 decay[id] *= DECAY_FACTOR（不低于 DECAY_FLOOR）；
   每开新局 decay[id] = min(1.0, decay[id] + DECAY_RECOVER)。

有效权重公式
------------
    W_eff = base_weight x decay[id] x talent_mult x context_mult
    若 id in seen_this_run   -> W_eff = 0
    若 cooldown[id] > 0      -> W_eff = 0
    若 条件不满足             -> W_eff = 0

4 级降级阶梯（卡池耗尽绝不崩溃）
-------------------------------
    L0 正常：全部规则生效
    L1 忽略 cooldown
    L2 忽略 seen_this_run（按 last_seen_run 取最久未见的一批，再按权重抽）
    L3 返回 fallback 兜底条目（FALLBACK_CARD / FALLBACK_EVENT）

硬性契约
--------
    pick() 永远返回非空 PickResult、永不抛异常、永不返回 None，
    并在 PickResult.degraded 里携带降级级别（0-3）供表现层提示。

持久化
------
    decay / cooldown / last_seen_run / run_index 落在 Profile.data["content_state"]，跨局保留；
    seen_this_run 只在内存，每局 begin_run() 清空（也可经 to_save_dict/from_save_dict 随存档走）。

注意（避免 decay 被恢复两次）
    Profile.begin_run() 自身也会做一次 decay 恢复。本引擎在构造时一次性把 content_state
    读入内存并以内存副本为准，之后只会 sync_to_profile() 覆盖写回，因此即便表现层额外调用了
    Profile.begin_run()，也不会造成双倍恢复。推荐表现层只调用 AntiRepeatEngine.begin_run()。

本模块零 UI 依赖：禁止 import tkinter / print / 读取标准输入 / time.sleep。
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from core.constants import (
    DECAY_FACTOR,
    DECAY_FLOOR,
    DECAY_RECOVER,
    DEFAULT_COOLDOWN_RUNS,
    FALLBACK_CARD,
)

# ─────────────────────────────────────────────────────────────
# 降级级别常量
# ─────────────────────────────────────────────────────────────
DEGRADE_NORMAL: int = 0
"""L0：全部规则生效。"""

DEGRADE_IGNORE_COOLDOWN: int = 1
"""L1：忽略跨局冷却。"""

DEGRADE_IGNORE_SEEN: int = 2
"""L2：忽略单局已见集合，按 last_seen_run 取最久未见。"""

DEGRADE_FALLBACK: int = 3
"""L3：返回内置兜底条目。"""

DEGRADE_LABELS: Dict[int, str] = {
    DEGRADE_NORMAL: "正常",
    DEGRADE_IGNORE_COOLDOWN: "已放宽冷却限制",
    DEGRADE_IGNORE_SEEN: "内容将开始重复",
    DEGRADE_FALLBACK: "内容已耗尽，使用兜底",
}
"""降级级别 → 表现层可直接展示的中文提示。"""


# ─────────────────────────────────────────────────────────────
# 抽样结果
# ─────────────────────────────────────────────────────────────
@dataclass
class PickResult:
    """一次抽样的完整结果。pick() 永远返回本类型的非空实例。"""

    item: Any = None
    """选中的条目原件（dict 或 CardItem 等）。永不为 None。"""

    item_id: str = ""
    """选中条目的 id。"""

    degraded: int = DEGRADE_NORMAL
    """降级级别 0-3，见 DEGRADE_* 常量。"""

    reason: str = ""
    """降级原因/提示文案，表现层可直接展示。"""

    pool_size: int = 0
    """本次参与竞争的候选数量（该级别下有效权重 > 0 的条目数）。"""

    weight: float = 0.0
    """选中条目的有效权重。"""

    is_fallback: bool = False
    """是否为 L3 兜底条目。"""

    def __bool__(self) -> bool:
        """PickResult 永远为真（契约：永不返回空结果）。"""
        return True


# ─────────────────────────────────────────────────────────────
# 默认取值器
# ─────────────────────────────────────────────────────────────
def default_id_of(item: Any) -> str:
    """默认 id 取值器：dict 取 ['id']，对象取 .id。取不到返回空串。"""
    if isinstance(item, dict):
        return str(item.get("id") or "")
    return str(getattr(item, "id", "") or "")


def default_weight_of(item: Any) -> float:
    """默认基础权重取值器，缺省 1.0，非法值回退 1.0。"""
    if isinstance(item, dict):
        raw = item.get("weight", 1.0)
    else:
        raw = getattr(item, "weight", 1.0)
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return 1.0
    return value if value >= 0.0 else 0.0


def default_cooldown_of(item: Any) -> int:
    """默认冷却局数取值器：条目声明 cooldown_runs 优先，否则 DEFAULT_COOLDOWN_RUNS。"""
    if isinstance(item, dict):
        raw = item.get("cooldown_runs", DEFAULT_COOLDOWN_RUNS)
    else:
        raw = getattr(item, "cooldown_runs", DEFAULT_COOLDOWN_RUNS)
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_COOLDOWN_RUNS
    return max(0, value)


# ─────────────────────────────────────────────────────────────
# 引擎
# ─────────────────────────────────────────────────────────────
class AntiRepeatEngine:
    """防重复抽样引擎。所有内容系统（卡池 / 事件池 / 天赋池）共用一份实例。"""

    def __init__(self, profile: Any = None, rng: Optional[random.Random] = None) -> None:
        """构造引擎。

        Args:
            profile: core.profile.Profile 实例（可为 None，此时纯内存运行）。
            rng: 随机源，测试时可注入固定种子的 random.Random。
        """
        self.profile: Any = profile
        self.rng: random.Random = rng if rng is not None else random.Random()

        self.decay: Dict[str, float] = {}
        self.cooldown: Dict[str, int] = {}
        self.last_seen_run: Dict[str, int] = {}
        self.seen_this_run: set = set()
        self.run_index: int = 0
        self.in_run: bool = False

        self.load_from_profile()

    # ───────────────────────────────────────────────────────
    # 生命周期
    # ───────────────────────────────────────────────────────
    def begin_run(self) -> Dict[str, Any]:
        """一局开始：清空已见集合、冷却 -1、衰减 +DECAY_RECOVER、run_index +1。

        Returns:
            本次生命周期变更的摘要（供调试/日志，表现层可忽略）。
        """
        self.seen_this_run = set()
        self.run_index = int(self.run_index) + 1
        self.in_run = True

        # 冷却递减，归零即移除
        expired: List[str] = []
        for key in list(self.cooldown.keys()):
            try:
                left = int(self.cooldown[key]) - 1
            except (TypeError, ValueError):
                left = 0
            if left > 0:
                self.cooldown[key] = left
            else:
                expired.append(key)
                self.cooldown.pop(key, None)

        # 衰减恢复
        recovered: List[str] = []
        for key in list(self.decay.keys()):
            try:
                value = float(self.decay[key])
            except (TypeError, ValueError):
                value = 1.0
            new_value = min(1.0, value + DECAY_RECOVER)
            if new_value != value:
                recovered.append(key)
            self.decay[key] = new_value

        self.sync_to_profile()
        return {
            "run_index": self.run_index,
            "cooldown_expired": expired,
            "decay_recovered": recovered,
        }

    def end_run(self, result: Optional[Dict[str, Any]] = None) -> None:
        """一局结束：落盘状态。seen_this_run 保留到下次 begin_run() 再清。

        Args:
            result: 本局结算数据（本引擎不消费，仅为签名对齐 Profile.end_run）。
        """
        self.in_run = False
        self.sync_to_profile()

    def reset_run(self) -> None:
        """仅清空单局已见集合（读档回到局中等场景使用）。"""
        self.seen_this_run = set()

    def reset_all(self) -> None:
        """清空全部状态（新建档案 / 测试用）。"""
        self.decay = {}
        self.cooldown = {}
        self.last_seen_run = {}
        self.seen_this_run = set()
        self.run_index = 0
        self.sync_to_profile()

    # ───────────────────────────────────────────────────────
    # 状态查询
    # ───────────────────────────────────────────────────────
    def get_decay(self, item_id: str) -> float:
        """取某 id 的当前衰减系数，未记录返回 1.0。"""
        try:
            return float(self.decay.get(item_id, 1.0))
        except (TypeError, ValueError):
            return 1.0

    def get_cooldown(self, item_id: str) -> int:
        """取某 id 的剩余冷却局数，未记录返回 0。"""
        try:
            return max(0, int(self.cooldown.get(item_id, 0)))
        except (TypeError, ValueError):
            return 0

    def get_last_seen_run(self, item_id: str) -> int:
        """取某 id 上次被抽中的局序号，从未抽中返回 -1。"""
        try:
            return int(self.last_seen_run.get(item_id, -1))
        except (TypeError, ValueError):
            return -1

    def is_seen(self, item_id: str) -> bool:
        """判断某 id 本局是否已被抽中过。"""
        return item_id in self.seen_this_run

    def is_available(self, item_id: str, level: int = DEGRADE_NORMAL) -> bool:
        """在给定降级级别下，某 id 是否未被防重复规则屏蔽。"""
        if level < DEGRADE_IGNORE_SEEN and self.is_seen(item_id):
            return False
        if level < DEGRADE_IGNORE_COOLDOWN and self.get_cooldown(item_id) > 0:
            return False
        return True

    # ───────────────────────────────────────────────────────
    # 有效权重
    # ───────────────────────────────────────────────────────
    def effective_weight(
        self,
        item_id: str,
        base_weight: float = 1.0,
        talent_mult: float = 1.0,
        context_mult: float = 1.0,
        condition_ok: bool = True,
        level: int = DEGRADE_NORMAL,
    ) -> float:
        """计算有效权重 W_eff。

        W_eff = base_weight x decay[id] x talent_mult x context_mult；
        已见 / 冷却中 / 条件不满足 一律归零（已见与冷却按 level 放宽）。

        Args:
            item_id: 条目 id。
            base_weight: 条目声明的基础权重。
            talent_mult: 天赋带来的倍率（B2b 天赋系统注入，缺省 1.0）。
            context_mult: 情境倍率（危机 / 特质 / 年龄等，缺省 1.0）。
            condition_ok: 条目条件是否满足。
            level: 当前降级级别，见 DEGRADE_* 常量。

        Returns:
            非负浮点有效权重；被屏蔽时为 0.0。
        """
        if not condition_ok:
            return 0.0
        if not self.is_available(item_id, level):
            return 0.0
        try:
            base = float(base_weight)
        except (TypeError, ValueError):
            base = 1.0
        try:
            t_mult = float(talent_mult)
        except (TypeError, ValueError):
            t_mult = 1.0
        try:
            c_mult = float(context_mult)
        except (TypeError, ValueError):
            c_mult = 1.0
        value = base * self.get_decay(item_id) * t_mult * c_mult
        return value if value > 0.0 else 0.0

    # ───────────────────────────────────────────────────────
    # 抽样（核心契约）
    # ───────────────────────────────────────────────────────
    def pick(
        self,
        candidates: Optional[Iterable[Any]],
        id_of: Optional[Callable[[Any], str]] = None,
        weight_of: Optional[Callable[[Any], float]] = None,
        condition_ok: Optional[Callable[[Any], bool]] = None,
        talent_mult_of: Optional[Callable[[Any], float]] = None,
        context_mult_of: Optional[Callable[[Any], float]] = None,
        cooldown_of: Optional[Callable[[Any], int]] = None,
        fallback: Optional[Any] = None,
        mark: bool = True,
        exclude: Optional[Iterable[str]] = None,
        max_level: int = DEGRADE_FALLBACK,
    ) -> PickResult:
        """按 4 级降级阶梯抽取一个条目。

        硬性契约：永远返回非空 PickResult，永不抛异常，永不返回 None。

        Args:
            candidates: 候选条目序列（dict 或对象）。为 None / 空时直接 L3。
            id_of: id 取值器，缺省 default_id_of。
            weight_of: 基础权重取值器，缺省 default_weight_of。
            condition_ok: 条件判定器，返回 False 的条目 W_eff 归零。缺省全部通过。
            talent_mult_of: 天赋倍率取值器，缺省恒 1.0。
            context_mult_of: 情境倍率取值器，缺省恒 1.0。
            cooldown_of: 冷却局数取值器，缺省 default_cooldown_of。
            fallback: L3 兜底条目，缺省 FALLBACK_CARD 的副本。
            mark: 抽中后是否立即回写状态（已见 / 冷却 / 衰减）。
            exclude: 本次额外排除的 id 集合（不影响持久状态）。
            max_level: 允许降级到的最高级别，缺省 DEGRADE_FALLBACK。

        Returns:
            PickResult，其 item 永不为 None。
        """
        try:
            return self._pick_impl(
                candidates=candidates,
                id_of=id_of or default_id_of,
                weight_of=weight_of or default_weight_of,
                condition_ok=condition_ok,
                talent_mult_of=talent_mult_of,
                context_mult_of=context_mult_of,
                cooldown_of=cooldown_of or default_cooldown_of,
                fallback=fallback,
                mark=mark,
                exclude=set(exclude or ()),
                max_level=max_level,
            )
        except Exception as exc:  # 兜底：任何意外都不得让抽样崩溃
            return self._fallback_result(fallback, f"抽样异常已兜底：{type(exc).__name__}")

    def _pick_impl(
        self,
        candidates: Optional[Iterable[Any]],
        id_of: Callable[[Any], str],
        weight_of: Callable[[Any], float],
        condition_ok: Optional[Callable[[Any], bool]],
        talent_mult_of: Optional[Callable[[Any], float]],
        context_mult_of: Optional[Callable[[Any], float]],
        cooldown_of: Callable[[Any], int],
        fallback: Optional[Any],
        mark: bool,
        exclude: set,
        max_level: int,
    ) -> PickResult:
        """pick() 的实现体，异常由 pick() 统一兜底。"""
        items: List[Any] = [c for c in (candidates or []) if c is not None]
        if not items:
            return self._fallback_result(fallback, "候选池为空")

        top_level = max(DEGRADE_NORMAL, min(int(max_level), DEGRADE_FALLBACK))

        for level in (DEGRADE_NORMAL, DEGRADE_IGNORE_COOLDOWN, DEGRADE_IGNORE_SEEN):
            if level > top_level:
                break
            pairs = self._build_pairs(
                items, level, id_of, weight_of, condition_ok,
                talent_mult_of, context_mult_of, exclude,
            )
            if not pairs:
                continue
            if level == DEGRADE_IGNORE_SEEN:
                pairs = self._oldest_seen_subset(pairs, id_of)
            chosen, chosen_weight = self._weighted_choice(pairs)
            if chosen is None:
                continue
            chosen_id = id_of(chosen)
            if mark:
                self.mark_picked(chosen_id, cooldown_of(chosen))
            return PickResult(
                item=chosen,
                item_id=chosen_id,
                degraded=level,
                reason=DEGRADE_LABELS.get(level, ""),
                pool_size=len(pairs),
                weight=chosen_weight,
                is_fallback=False,
            )

        return self._fallback_result(fallback, "候选池已耗尽")

    def _build_pairs(
        self,
        items: Sequence[Any],
        level: int,
        id_of: Callable[[Any], str],
        weight_of: Callable[[Any], float],
        condition_ok: Optional[Callable[[Any], bool]],
        talent_mult_of: Optional[Callable[[Any], float]],
        context_mult_of: Optional[Callable[[Any], float]],
        exclude: set,
    ) -> List[Tuple[Any, float]]:
        """在给定降级级别下构造 (条目, 有效权重) 列表，只保留 W_eff > 0 的项。"""
        pairs: List[Tuple[Any, float]] = []
        for item in items:
            item_id = id_of(item)
            if item_id and item_id in exclude:
                continue
            ok = True
            if condition_ok is not None:
                try:
                    ok = bool(condition_ok(item))
                except Exception:
                    ok = False
            t_mult = 1.0
            if talent_mult_of is not None:
                try:
                    t_mult = float(talent_mult_of(item))
                except Exception:
                    t_mult = 1.0
            c_mult = 1.0
            if context_mult_of is not None:
                try:
                    c_mult = float(context_mult_of(item))
                except Exception:
                    c_mult = 1.0
            w_eff = self.effective_weight(
                item_id=item_id,
                base_weight=weight_of(item),
                talent_mult=t_mult,
                context_mult=c_mult,
                condition_ok=ok,
                level=level,
            )
            if w_eff > 0.0:
                pairs.append((item, w_eff))
        return pairs

    def _oldest_seen_subset(
        self,
        pairs: List[Tuple[Any, float]],
        id_of: Callable[[Any], str],
    ) -> List[Tuple[Any, float]]:
        """L2 专用：只保留 last_seen_run 最小（最久未见）的那一批。"""
        if not pairs:
            return pairs
        scored = [(self.get_last_seen_run(id_of(item)), item, w) for item, w in pairs]
        oldest = min(s for s, _, _ in scored)
        return [(item, w) for s, item, w in scored if s == oldest]

    def _weighted_choice(
        self, pairs: Sequence[Tuple[Any, float]]
    ) -> Tuple[Optional[Any], float]:
        """按权重随机取一个 (条目, 权重)。总权重为 0 时退化为均匀随机。"""
        if not pairs:
            return None, 0.0
        total = sum(w for _, w in pairs)
        if total <= 0.0:
            item, weight = pairs[self.rng.randrange(len(pairs))]
            return item, weight
        threshold = self.rng.uniform(0.0, total)
        upto = 0.0
        for item, weight in pairs:
            upto += weight
            if upto >= threshold:
                return item, weight
        return pairs[-1][0], pairs[-1][1]

    def _fallback_result(self, fallback: Optional[Any], reason: str) -> PickResult:
        """构造 L3 兜底结果。兜底条目不写入任何防重复状态。"""
        item = fallback if fallback is not None else dict(FALLBACK_CARD)
        return PickResult(
            item=item,
            item_id=default_id_of(item),
            degraded=DEGRADE_FALLBACK,
            reason=f"{DEGRADE_LABELS[DEGRADE_FALLBACK]}（{reason}）",
            pool_size=0,
            weight=0.0,
            is_fallback=True,
        )

    def pick_many(
        self,
        candidates: Optional[Iterable[Any]],
        count: int = 3,
        **kwargs: Any,
    ) -> List[PickResult]:
        """连续抽取 count 个互不重复的条目（本次调用内不重复）。

        每个结果独立携带自己的 degraded 级别。永不抛异常，长度恒为 max(0, count)。
        """
        results: List[PickResult] = []
        used: set = set(kwargs.pop("exclude", None) or ())
        for _ in range(max(0, int(count))):
            res = self.pick(candidates, exclude=used, **kwargs)
            if res.item_id:
                used.add(res.item_id)
            results.append(res)
        return results

    # ───────────────────────────────────────────────────────
    # 状态回写
    # ───────────────────────────────────────────────────────
    def mark_picked(self, item_id: str, cooldown_runs: Optional[int] = None) -> None:
        """标记某 id 被抽中：加入已见集合、设置冷却、衰减权重、记录 last_seen_run。"""
        if not item_id:
            return
        self.seen_this_run.add(item_id)
        cd = DEFAULT_COOLDOWN_RUNS if cooldown_runs is None else int(cooldown_runs)
        if cd > 0:
            self.cooldown[item_id] = cd
        else:
            self.cooldown.pop(item_id, None)
        self.decay[item_id] = max(DECAY_FLOOR, self.get_decay(item_id) * DECAY_FACTOR)
        self.last_seen_run[item_id] = self.run_index

    # ───────────────────────────────────────────────────────
    # 持久化
    # ───────────────────────────────────────────────────────
    def load_from_profile(self) -> None:
        """从 Profile.data['content_state'] 载入跨局状态。缺失/损坏一律回退空表。"""
        state: Dict[str, Any] = {}
        if self.profile is not None:
            try:
                raw = self.profile.get("content_state", {})
                if isinstance(raw, dict):
                    state = raw
            except Exception:
                state = {}
        self.decay = self._coerce_float_map(state.get("decay"))
        self.cooldown = self._coerce_int_map(state.get("cooldown"))
        self.last_seen_run = self._coerce_int_map(state.get("last_seen_run"))
        try:
            self.run_index = int(state.get("run_index", 0))
        except (TypeError, ValueError):
            self.run_index = 0

    def sync_to_profile(self, save: bool = False) -> bool:
        """把跨局状态写回 Profile.data['content_state']。

        Args:
            save: 是否顺带把 profile 落盘。

        Returns:
            是否成功写入（无 profile 时返回 False）。
        """
        if self.profile is None:
            return False
        try:
            state = self.profile.get("content_state", None)
            if not isinstance(state, dict):
                state = {}
                self.profile.set("content_state", state)
            state["decay"] = dict(self.decay)
            state["cooldown"] = dict(self.cooldown)
            state["last_seen_run"] = dict(self.last_seen_run)
            state["run_index"] = int(self.run_index)
            if save:
                self.profile.save()
            return True
        except Exception:
            return False

    def to_save_dict(self) -> Dict[str, Any]:
        """导出全部状态（含 seen_this_run），供存档序列化。"""
        return {
            "decay": dict(self.decay),
            "cooldown": dict(self.cooldown),
            "last_seen_run": dict(self.last_seen_run),
            "seen_this_run": sorted(self.seen_this_run),
            "run_index": int(self.run_index),
        }

    def from_save_dict(self, data: Optional[Dict[str, Any]]) -> None:
        """从存档字典恢复全部状态。任何字段缺失/类型不符均安全回退。"""
        if not isinstance(data, dict):
            return
        self.decay = self._coerce_float_map(data.get("decay"))
        self.cooldown = self._coerce_int_map(data.get("cooldown"))
        self.last_seen_run = self._coerce_int_map(data.get("last_seen_run"))
        seen = data.get("seen_this_run")
        self.seen_this_run = set(str(s) for s in seen) if isinstance(seen, (list, tuple, set)) else set()
        try:
            self.run_index = int(data.get("run_index", 0))
        except (TypeError, ValueError):
            self.run_index = 0

    @staticmethod
    def _coerce_float_map(raw: Any) -> Dict[str, float]:
        """把任意值安全转成 {str: float}。"""
        out: Dict[str, float] = {}
        if not isinstance(raw, dict):
            return out
        for key, value in raw.items():
            try:
                out[str(key)] = float(value)
            except (TypeError, ValueError):
                continue
        return out

    @staticmethod
    def _coerce_int_map(raw: Any) -> Dict[str, int]:
        """把任意值安全转成 {str: int}。"""
        out: Dict[str, int] = {}
        if not isinstance(raw, dict):
            return out
        for key, value in raw.items():
            try:
                out[str(key)] = int(value)
            except (TypeError, ValueError):
                continue
        return out

    # ───────────────────────────────────────────────────────
    # 调试辅助
    # ───────────────────────────────────────────────────────
    def stats(self) -> Dict[str, Any]:
        """返回状态摘要（调试 / 开发者面板用，不含 UI 依赖）。"""
        return {
            "run_index": self.run_index,
            "in_run": self.in_run,
            "seen_count": len(self.seen_this_run),
            "cooldown_count": len(self.cooldown),
            "decayed_count": sum(1 for v in self.decay.values() if v < 1.0),
        }


__all__ = [
    "AntiRepeatEngine",
    "PickResult",
    "DEGRADE_NORMAL",
    "DEGRADE_IGNORE_COOLDOWN",
    "DEGRADE_IGNORE_SEEN",
    "DEGRADE_FALLBACK",
    "DEGRADE_LABELS",
    "default_id_of",
    "default_weight_of",
    "default_cooldown_of",
]
