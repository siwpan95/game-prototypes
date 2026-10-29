# -*- coding: utf-8 -*-
"""
core/talents.py — 天赋系统（两级抽样 / 互斥组 / 解锁制 / 继承置顶 / 效果落地）

设计要点（B2b）：
- 两级抽样：先按 constants.RARITY_PROBABILITIES 抽稀有度桶（legendary 1% /
  epic 8% / rare 26% / common 65%），再在桶内按 weight 做轮盘赌选具体天赋。
  → weight 只在同稀有度桶内有意义，不参与跨稀有度比较。
- 互斥组：同一 mutex_group 的天赋绝不同时出现在候选池里（抽取时即排除，
  而非选完后拦截）。
- 解锁制：unlock_condition 非空的天赋，仅当 Profile.is_unlocked() 为真时入池。
- 继承：Profile 的 inherited_talent 若合法，占据候选第 1 位且不受随机影响。
- 效果落地：apply / apply_effects 把 effects 写回玩家对象（dict 或对象皆可）。

两套键名体系并存：
- 玩家属性小写（strength/intelligence/charisma/wealth/health/happiness）→ effects.init
- 王权维度大写（11 个，见 constants.DIMENSIONS）→ effects.init_dimensions
两者由本模块自动联动：维度 ÷5 折算到小写属性；小写属性 ×5 折算到维度。
内容里写一套即可，不需要手工同步。

本模块零 UI 依赖：禁止 import tkinter / print / input / time.sleep。仅标准库。
"""

from __future__ import annotations

import random
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from core.constants import DIMENSIONS, RARITY_PROBABILITIES
from core.models import Talent

# ─────────────────────────────────────────────────────────────
# 常量
# ─────────────────────────────────────────────────────────────
RARITY_ORDER: Tuple[str, ...] = ("legendary", "epic", "rare", "common")
"""稀有度从高到低。用于降级回退（目标桶为空时向下找非空桶）。"""

DIMENSION_TO_STAT: Dict[str, str] = {
    "STRENGTH": "strength",
    "INTELLIGENCE": "intelligence",
    "CHARISMA": "charisma",
    "WEALTH": "wealth",
    "HEALTH": "health",
    "HAPPINESS": "happiness",
}
"""大写王权维度 → 小写玩家属性的映射（只有 6 个维度有对应属性）。
MORALITY / STABILITY / CHURCH / NOBLES / COMMONERS 是王朝篇专属，无小写对应。"""

STAT_TO_DIMENSION: Dict[str, str] = {v: k for k, v in DIMENSION_TO_STAT.items()}
"""小写玩家属性 → 大写王权维度（DIMENSION_TO_STAT 的反向表）。"""

DIMENSION_TO_STAT_DIVISOR: float = 5.0
"""维度 ÷5 换算成小写属性（引擎约定，见 §7.5）。"""

DEFAULT_DRAW_COUNT: int = 10
"""默认 10 连抽。"""

DEFAULT_PICK_COUNT: int = 3
"""玩家从候选中选 3 个。"""


# ─────────────────────────────────────────────────────────────
# 玩家读写适配（player 可能是 dict，也可能是对象）
# ─────────────────────────────────────────────────────────────
def _player_get(player: Any, key: str, default: Any = 0) -> Any:
    """从 player 读取属性，兼容 dict 与普通对象。读不到返回 default。"""
    if player is None:
        return default
    if isinstance(player, dict):
        return player.get(key, default)
    return getattr(player, key, default)


def _player_set(player: Any, key: str, value: Any) -> None:
    """向 player 写入属性，兼容 dict 与普通对象。player 为 None 时静默忽略。"""
    if player is None:
        return
    if isinstance(player, dict):
        player[key] = value
    else:
        setattr(player, key, value)


def _as_number(value: Any, default: float = 0.0) -> float:
    """尽力把任意值转成 float，失败返回 default。绝不抛异常。"""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


# ─────────────────────────────────────────────────────────────
# TalentSystem
# ─────────────────────────────────────────────────────────────
class TalentSystem:
    """天赋系统。负责抽样、互斥过滤、解锁过滤、继承置顶与效果落地。

    典型用法::

        loader = ContentLoader().load()
        ts = TalentSystem(loader.talents(), profile=profile)
        candidates = ts.draw(10)          # 10 连抽候选（第 1 位可能是继承天赋）
        chosen = candidates[:3]           # 玩家选 3 个
        for t in chosen:
            ts.apply(player, t.id)
    """

    def __init__(
        self,
        talents: Optional[Iterable[Talent]] = None,
        profile: Any = None,
        rng: Optional[random.Random] = None,
    ) -> None:
        """构造天赋系统。

        Args:
            talents: Talent 列表（通常来自 ContentLoader.talents()）。None 视为空池。
            profile: core.profile.Profile 实例，提供 is_unlocked / get。可为 None。
            rng: 随机源，便于测试注入固定种子。None 时用模块级 random.Random()。
        """
        self.profile: Any = profile
        self.rng: random.Random = rng if rng is not None else random.Random()
        self._all: List[Talent] = []
        self._by_id: Dict[str, Talent] = {}
        self._by_rarity: Dict[str, List[Talent]] = {r: [] for r in RARITY_ORDER}
        self.errors: List[str] = []
        self.load(talents or [])

    # ───────────────────────────────────────────────────────
    # 载入 / 索引
    # ───────────────────────────────────────────────────────
    def load(self, talents: Iterable[Talent]) -> "TalentSystem":
        """（重新）载入天赋池并建索引。幂等，返回自身便于链式调用。"""
        self._all = []
        self._by_id = {}
        self._by_rarity = {r: [] for r in RARITY_ORDER}
        self.errors = []

        for t in talents:
            if not isinstance(t, Talent):
                self.errors.append(f"非 Talent 实例，已跳过: {t!r}")
                continue
            if not t.id:
                self.errors.append("天赋缺少 id，已跳过")
                continue
            if t.id in self._by_id:
                self.errors.append(f"天赋 id 重复，已跳过: {t.id}")
                continue
            rarity = t.rarity if t.rarity in self._by_rarity else "common"
            if t.rarity not in self._by_rarity:
                self.errors.append(f"未知稀有度 {t.rarity!r}，按 common 处理: {t.id}")
            self._by_id[t.id] = t
            self._all.append(t)
            self._by_rarity[rarity].append(t)
        return self

    # ───────────────────────────────────────────────────────
    # 查询
    # ───────────────────────────────────────────────────────
    def all_talents(self) -> List[Talent]:
        """返回全部天赋（副本列表，防止外部改动内部索引）。"""
        return list(self._all)

    def get(self, talent_id: str) -> Optional[Talent]:
        """按 id 取天赋，不存在返回 None。"""
        return self._by_id.get(talent_id)

    def by_rarity(self, rarity: str) -> List[Talent]:
        """返回某稀有度桶的全部天赋（副本）。未知稀有度返回空列表。"""
        return list(self._by_rarity.get(rarity, []))

    def by_category(self, category: str) -> List[Talent]:
        """返回某 category 的全部天赋。"""
        return [t for t in self._all if t.category == category]

    # ───────────────────────────────────────────────────────
    # 解锁过滤
    # ───────────────────────────────────────────────────────
    def is_available(self, talent: Talent) -> bool:
        """判断天赋是否可进入抽奖池。

        unlock_condition 为空 → 永远可用；
        非空 → 需要 Profile.is_unlocked(unlock_condition) 为真。
        没有 profile 时，带解锁条件的天赋一律视为未解锁（保守策略）。
        """
        cond = talent.unlock_condition
        if not cond:
            return True
        if self.profile is None:
            return False
        checker = getattr(self.profile, "is_unlocked", None)
        if not callable(checker):
            return False
        try:
            return bool(checker(cond))
        except Exception:
            # Profile 实现异常不应打断抽卡，按未解锁处理
            return False

    def available_pool(self) -> List[Talent]:
        """返回当前 profile 下所有可抽取的天赋。"""
        return [t for t in self._all if self.is_available(t)]

    # ───────────────────────────────────────────────────────
    # 继承天赋
    # ───────────────────────────────────────────────────────
    def inherited_talent(self) -> Optional[Talent]:
        """返回 Profile 中记录的继承天赋（必须存在于池中且标记 inheritable）。

        Profile 字段名为 inherited_talent（见 core/profile.py 默认结构）。
        非法 / 缺失 / 不可继承 → 返回 None。
        """
        if self.profile is None:
            return None
        getter = getattr(self.profile, "get", None)
        if not callable(getter):
            return None
        try:
            tid = getter("inherited_talent", None)
        except Exception:
            return None
        if not tid or not isinstance(tid, str):
            return None
        talent = self._by_id.get(tid)
        if talent is None:
            return None
        if not talent.inheritable:
            return None
        return talent

    def set_inherited(self, talent_id: Optional[str]) -> bool:
        """把某天赋写入 Profile 作为下局继承天赋。

        talent_id 为 None 表示清除继承。返回 True 表示写入成功。
        天赋不存在或不可继承时返回 False（不写入）。
        """
        if self.profile is None:
            return False
        setter = getattr(self.profile, "set", None)
        if not callable(setter):
            return False
        if talent_id is None:
            setter("inherited_talent", None)
            return True
        talent = self._by_id.get(talent_id)
        if talent is None or not talent.inheritable:
            return False
        setter("inherited_talent", talent_id)
        return True

    # ───────────────────────────────────────────────────────
    # 两级抽样核心
    # ───────────────────────────────────────────────────────
    def _pick_rarity(self, available_rarities: Sequence[str]) -> Optional[str]:
        """第一级：按 RARITY_PROBABILITIES 在仍有货的桶之间抽稀有度。

        只在 available_rarities（非空桶）之间按原始概率归一化后抽取，
        保证桶抽干时不会白抽，同时维持相对比例。
        """
        if not available_rarities:
            return None
        weights = [max(0.0, float(RARITY_PROBABILITIES.get(r, 0.0)))
                   for r in available_rarities]
        total = sum(weights)
        if total <= 0.0:
            # 概率表异常时退化为等概率，保证功能不中断
            return self.rng.choice(list(available_rarities))
        roll = self.rng.random() * total
        acc = 0.0
        for rarity, w in zip(available_rarities, weights):
            acc += w
            if roll < acc:
                return rarity
        return available_rarities[-1]

    def _roulette(self, pool: Sequence[Talent]) -> Optional[Talent]:
        """第二级：桶内按 weight 轮盘赌。weight <= 0 视为 0（不可能被选中）。

        全部 weight 为 0 时退化为等概率随机，避免死锁。
        """
        if not pool:
            return None
        weights = [max(0.0, _as_number(t.weight, 1.0)) for t in pool]
        total = sum(weights)
        if total <= 0.0:
            return self.rng.choice(list(pool))
        roll = self.rng.random() * total
        acc = 0.0
        for talent, w in zip(pool, weights):
            acc += w
            if roll < acc:
                return talent
        return pool[-1]

    def draw(
        self,
        n: int = DEFAULT_DRAW_COUNT,
        include_inherited: bool = True,
    ) -> List[Talent]:
        """抽取 n 个候选天赋。

        规则：
        1. 若存在合法继承天赋且 include_inherited 为真，它固定占据结果第 0 位，
           不参与随机，并且其 mutex_group 会立即锁死（同组其他天赋不再入池）。
        2. 其余名额走两级抽样：先按稀有度概率选桶，再在桶内按 weight 轮盘赌。
        3. 已抽中的天赋与其所属互斥组会从后续候选中剔除。
        4. 池子不够 n 个时返回实际能给出的数量（不重复、不报错）。

        Args:
            n: 候选总数（含继承天赋）。<=0 时返回空列表。
            include_inherited: 是否把继承天赋置顶。测试时可关掉。

        Returns:
            候选 Talent 列表，长度 <= n，元素互不重复且互斥组两两不冲突。
        """
        if n <= 0:
            return []

        result: List[Talent] = []
        used_ids: set = set()
        used_groups: set = set()

        # ① 继承天赋置顶（不受随机影响）
        if include_inherited:
            inherited = self.inherited_talent()
            if inherited is not None:
                result.append(inherited)
                used_ids.add(inherited.id)
                if inherited.mutex_group:
                    used_groups.add(inherited.mutex_group)

        # ② 构建可用池（解锁过滤 + 去掉已在结果中的）
        pool_by_rarity: Dict[str, List[Talent]] = {r: [] for r in RARITY_ORDER}
        for talent in self._all:
            if talent.id in used_ids:
                continue
            if not self.is_available(talent):
                continue
            if talent.mutex_group and talent.mutex_group in used_groups:
                continue
            rarity = talent.rarity if talent.rarity in pool_by_rarity else "common"
            pool_by_rarity[rarity].append(talent)

        # ③ 逐个抽取，边抽边剔除互斥组
        while len(result) < n:
            non_empty = [r for r in RARITY_ORDER if pool_by_rarity[r]]
            if not non_empty:
                break
            rarity = self._pick_rarity(non_empty)
            if rarity is None:
                break
            picked = self._roulette(pool_by_rarity[rarity])
            if picked is None:
                # 理论不可达（桶非空必能选出），保险起见清空该桶防死循环
                pool_by_rarity[rarity] = []
                continue

            result.append(picked)
            used_ids.add(picked.id)
            if picked.mutex_group:
                used_groups.add(picked.mutex_group)

            # 剔除：本体 + 同互斥组全部成员
            for bucket in pool_by_rarity.values():
                bucket[:] = [
                    t for t in bucket
                    if t.id != picked.id
                    and not (t.mutex_group and t.mutex_group in used_groups)
                ]

        return result

    def draw_ids(
        self,
        n: int = DEFAULT_DRAW_COUNT,
        include_inherited: bool = True,
    ) -> List[str]:
        """draw() 的便捷版，只返回 id 列表（表现层拼 UI 用）。"""
        return [t.id for t in self.draw(n, include_inherited=include_inherited)]

    def validate_selection(self, talent_ids: Sequence[str]) -> Tuple[bool, str]:
        """校验玩家最终选择是否合法（存在、不重复、互斥组不冲突）。

        Returns:
            (是否合法, 失败原因)。合法时原因为空串。
        """
        seen_ids: set = set()
        seen_groups: Dict[str, str] = {}
        for tid in talent_ids:
            talent = self._by_id.get(tid)
            if talent is None:
                return False, f"天赋不存在: {tid}"
            if tid in seen_ids:
                return False, f"天赋重复选择: {tid}"
            seen_ids.add(tid)
            grp = talent.mutex_group
            if grp:
                if grp in seen_groups:
                    return False, f"互斥冲突: {seen_groups[grp]} 与 {tid} 同属 {grp}"
                seen_groups[grp] = tid
        return True, ""

    # ───────────────────────────────────────────────────────
    # 效果落地
    # ───────────────────────────────────────────────────────
    def apply(self, player: Any, talent_id: str) -> bool:
        """按 id 把单个天赋的效果应用到 player。

        Returns:
            True 表示已应用；天赋不存在返回 False。
        """
        talent = self._by_id.get(talent_id)
        if talent is None:
            return False
        self.apply_effects(player, talent)
        return True

    def apply_all(self, player: Any, talent_ids: Sequence[str]) -> int:
        """批量应用多个天赋，返回实际成功应用的数量。"""
        count = 0
        for tid in talent_ids:
            if self.apply(player, tid):
                count += 1
        return count

    def apply_effects(self, player: Any, talent: Talent) -> None:
        """把单个 Talent 的 effects 落到 player 上。

        处理四类：
        - init: 小写玩家属性增量，同时联动折算到大写维度（×5）
        - init_dimensions: 大写维度增量，同时联动折算到小写属性（÷5）
        - init_traits: 追加到 player.traits（去重）
        - modifiers: 累积到 player.talent_modifiers（供事件/职业系统读取）

        player 为 None 或 effects 结构异常时静默跳过，绝不抛异常。
        """
        if player is None or not isinstance(talent.effects, dict):
            return
        effects = talent.effects

        init = effects.get("init") or {}
        if isinstance(init, dict):
            self._apply_init_stats(player, init)

        init_dims = effects.get("init_dimensions") or {}
        if isinstance(init_dims, dict):
            self._apply_init_dimensions(player, init_dims)

        traits = effects.get("init_traits") or []
        if isinstance(traits, list):
            self._apply_traits(player, traits)

        modifiers = effects.get("modifiers") or {}
        if isinstance(modifiers, dict):
            self._apply_modifiers(player, modifiers)

        # 记录已获得的天赋 id，便于结算 / 成就判定
        owned = _player_get(player, "talents", None)
        if not isinstance(owned, list):
            owned = []
        if talent.id and talent.id not in owned:
            owned = owned + [talent.id]
        _player_set(player, "talents", owned)

    def _apply_init_stats(self, player: Any, init: Dict[str, Any]) -> None:
        """应用小写属性增量，并联动到对应大写维度（×5）。"""
        dims = _player_get(player, "dimensions", None)
        dims_is_dict = isinstance(dims, dict)
        for key, delta in init.items():
            if not isinstance(key, str):
                continue
            amount = _as_number(delta, 0.0)
            if amount == 0.0:
                continue
            current = _as_number(_player_get(player, key, 0), 0.0)
            _player_set(player, key, self._round_stat(current + amount))
            # 联动大写维度
            dim = STAT_TO_DIMENSION.get(key)
            if dim and dims_is_dict:
                dim_cur = _as_number(dims.get(dim, 0), 0.0)
                dims[dim] = self._round_stat(
                    dim_cur + amount * DIMENSION_TO_STAT_DIVISOR
                )
        if dims_is_dict:
            _player_set(player, "dimensions", dims)

    def _apply_init_dimensions(self, player: Any, init_dims: Dict[str, Any]) -> None:
        """应用大写维度增量，并联动到对应小写属性（÷5）。"""
        dims = _player_get(player, "dimensions", None)
        if not isinstance(dims, dict):
            dims = {}
        for key, delta in init_dims.items():
            if not isinstance(key, str) or key not in DIMENSIONS:
                continue
            amount = _as_number(delta, 0.0)
            if amount == 0.0:
                continue
            dim_cur = _as_number(dims.get(key, 0), 0.0)
            dims[key] = self._round_stat(dim_cur + amount)
            # 联动小写属性
            stat = DIMENSION_TO_STAT.get(key)
            if stat:
                cur = _as_number(_player_get(player, stat, 0), 0.0)
                _player_set(
                    player, stat,
                    self._round_stat(cur + amount / DIMENSION_TO_STAT_DIVISOR),
                )
        _player_set(player, "dimensions", dims)

    def _apply_traits(self, player: Any, traits: Sequence[Any]) -> None:
        """追加特质到 player.traits（列表，去重保序）。"""
        current = _player_get(player, "traits", None)
        if not isinstance(current, list):
            current = []
        else:
            current = list(current)
        for tr in traits:
            if isinstance(tr, str) and tr and tr not in current:
                current.append(tr)
        _player_set(player, "traits", current)

    def _apply_modifiers(self, player: Any, modifiers: Dict[str, Any]) -> None:
        """累积修正器到 player.talent_modifiers。

        累积规则：
        - event_weight: 列表拼接（多天赋的权重修正共存）
        - career_bonus: dict 内同键相乘
        - stat_gain / stat_loss / relationship_decay 等标量：相乘
        - 其他未知键：后者覆盖前者（保守）
        """
        store = _player_get(player, "talent_modifiers", None)
        if not isinstance(store, dict):
            store = {}
        else:
            store = dict(store)

        for key, val in modifiers.items():
            if not isinstance(key, str):
                continue
            if key == "event_weight":
                if not isinstance(val, list):
                    continue
                existing = store.get(key)
                merged = list(existing) if isinstance(existing, list) else []
                for rule in val:
                    if isinstance(rule, dict):
                        merged.append(dict(rule))
                store[key] = merged
            elif key == "career_bonus":
                if not isinstance(val, dict):
                    continue
                existing = store.get(key)
                merged = dict(existing) if isinstance(existing, dict) else {}
                for career, mult in val.items():
                    if not isinstance(career, str):
                        continue
                    base = _as_number(merged.get(career, 1.0), 1.0)
                    merged[career] = round(base * _as_number(mult, 1.0), 4)
                store[key] = merged
            elif isinstance(val, (int, float)) and not isinstance(val, bool):
                base = _as_number(store.get(key, 1.0), 1.0)
                store[key] = round(base * _as_number(val, 1.0), 4)
            else:
                store[key] = val

        _player_set(player, "talent_modifiers", store)

    @staticmethod
    def _round_stat(value: float) -> Any:
        """数值收敛：能取整就取整（避免 5.000000001 这类脏数据）。"""
        rounded = round(value, 4)
        if abs(rounded - round(rounded)) < 1e-9:
            return int(round(rounded))
        return rounded

    # ───────────────────────────────────────────────────────
    # 统计（调参 / 自测用，不产生副作用）
    # ───────────────────────────────────────────────────────
    def rarity_counts(self) -> Dict[str, int]:
        """返回各稀有度桶的天赋数量。"""
        return {r: len(self._by_rarity.get(r, [])) for r in RARITY_ORDER}

    def mutex_groups(self) -> Dict[str, List[str]]:
        """返回互斥组 → 成员 id 列表的映射（不含无组天赋）。"""
        groups: Dict[str, List[str]] = {}
        for t in self._all:
            if t.mutex_group:
                groups.setdefault(t.mutex_group, []).append(t.id)
        return groups
