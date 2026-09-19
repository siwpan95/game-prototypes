"""
测试探针系统：轻量级检测点，用于冒烟测试和快速健康检查。

探针（Probe）是在关键路径上插入的只读检查点，不改变被测代码逻辑。
适合 CI/CD 冒烟测试、部署后健康检查、快速回归验证。

用法：
    from test.probe import Probe, ProbeManager, TestResult

    mgr = ProbeManager()

    def check_db():
        return True, "数据库连接正常"

    mgr.register(Probe("db_check", check_db, category="数据库", priority=1))
    results = mgr.run_smoke()  # 仅 priority=1 的探针
    results = mgr.run_category("数据库")
"""

import time
import traceback
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from .runner import TestResult, ErrorType


# ============================================================
# 探针
# ============================================================

@dataclass
class Probe:
    """单个测试探针。

    探针是无副作用的只读检查点。其 check 函数返回 (通过与否, 详情文本)。

    Attributes:
        name: 探针名称（唯一标识）。
        check: 检查函数，返回 (passed: bool, detail: str)。
        category: 探针分类（如"启动"、"数据库"、"API"、"UI"、"文件系统"）。
        priority: 优先级 1-5，1 最高（数字越小越优先扫描）。
        tags: 标签集合，用于按标签筛选探针。
        timeout: 超时秒数（未在当前版本使用，预留）。
    """
    name: str
    check: Callable[[], Tuple[bool, str]]
    category: str = "通用"
    priority: int = 3
    tags: Set[str] = field(default_factory=set)
    timeout: float = 3.0

    def run(self) -> TestResult:
        """执行探针检测，返回 TestResult。

        Returns:
            TestResult 对象。探针通过 → success=True, error_type=PASS；
            探针失败 → success=False, error_type=PROBE_FAIL；
            探针抛异常 → success=False, error_type=PROBE_FAIL 带堆栈。
        """
        start = time.perf_counter()
        try:
            passed, detail = self.check()
        except Exception as e:
            duration = time.perf_counter() - start
            return TestResult(
                success=False,
                error_type=ErrorType.UNKNOWN_ERROR,
                message=f"{type(e).__name__}: {e}",
                duration=duration,
                test_name=f"[探针] {self.name}",
                traceback_text=traceback.format_exc(),
            )

        duration = time.perf_counter() - start
        if passed:
            return TestResult(
                success=True,
                error_type=ErrorType.PASS,
                message=f"{detail} ({duration:.3f}s)",
                duration=duration,
                test_name=f"[探针] {self.name}",
            )
        else:
            return TestResult(
                success=False,
                error_type=ErrorType.UNKNOWN_ERROR,
                message=f"{detail} ({duration:.3f}s)",
                duration=duration,
                test_name=f"[探针] {self.name}",
            )


# ============================================================
# 探针管理器
# ============================================================

class ProbeManager:
    """探针管理器 — 注册、筛选、批量执行。

    用法：
        mgr = ProbeManager()

        # 注册探针
        mgr.register(Probe("app_started", lambda: (True, "应用已启动"), priority=1))
        mgr.register(Probe("db_connected", lambda: (True, "数据库正常"), category="数据库"))

        # 执行
        results = mgr.run_smoke()            # 冒烟测试（priority=1）
        results = mgr.run_category("数据库")  # 按分类执行
        results = mgr.run_all()               # 全部执行
    """

    def __init__(self):
        """初始化探针管理器。"""
        self._probes: List[Probe] = []

    # ============================================================
    # 注册
    # ============================================================

    def register(self, probe: Probe) -> None:
        """注册一个探针。

        Args:
            probe: 探针对象。
        """
        self._probes.append(probe)

    def register_batch(self, probes: List[Probe]) -> None:
        """批量注册探针。

        Args:
            probes: 探针列表。
        """
        self._probes.extend(probes)

    def unregister(self, name: str) -> bool:
        """按名称移除探针。

        Args:
            name: 探针名称。

        Returns:
            True 表示成功移除。
        """
        for i, p in enumerate(self._probes):
            if p.name == name:
                self._probes.pop(i)
                return True
        return False

    @property
    def count(self) -> int:
        """已注册的探针总数。"""
        return len(self._probes)

    # ============================================================
    # 筛选
    # ============================================================

    def filter(
        self,
        *,
        category: Optional[str] = None,
        tags: Optional[Set[str]] = None,
        max_priority: Optional[int] = None,
        min_priority: Optional[int] = None,
        name_contains: Optional[str] = None,
    ) -> List[Probe]:
        """按条件筛选探针。

        Args:
            category: 按分类筛选（精确匹配）。
            tags: 按标签筛选（包含任一标签即匹配）。
            max_priority: 最大优先级（返回 priority <= 此值的探针）。
            min_priority: 最小优先级（返回 priority >= 此值的探针）。
            name_contains: 名称包含此字符串的探针。

        Returns:
            筛选后的探针列表。
        """
        result = self._probes

        if category is not None:
            result = [p for p in result if p.category == category]

        if tags is not None:
            result = [p for p in result if p.tags & tags]

        if max_priority is not None:
            result = [p for p in result if p.priority <= max_priority]

        if min_priority is not None:
            result = [p for p in result if p.priority >= min_priority]

        if name_contains is not None:
            result = [p for p in result if name_contains in p.name]

        return result

    def smoke_probes(self) -> List[Probe]:
        """获取冒烟探针：仅 priority=1 的关键路径探针。

        Returns:
            优先级为 1 的探针列表。
        """
        return self.filter(max_priority=1)

    def quick_probes(self) -> List[Probe]:
        """获取快速探针：priority <= 2。

        Returns:
            优先级为 1 或 2 的探针列表。
        """
        return self.filter(max_priority=2)

    # ============================================================
    # 执行
    # ============================================================

    def run_all(self) -> List[TestResult]:
        """执行所有已注册的探针。

        Returns:
            TestResult 列表。
        """
        return self._run(self._probes)

    def run_smoke(self) -> List[TestResult]:
        """执行冒烟测试（仅 priority=1 的关键探针）。

        Returns:
            TestResult 列表。
        """
        probes = self.smoke_probes()
        return self._run(probes)

    def run_category(self, category: str) -> List[TestResult]:
        """按分类执行探针。

        Args:
            category: 探针分类名称。

        Returns:
            TestResult 列表。
        """
        probes = self.filter(category=category)
        return self._run(probes)

    def _run(self, probes: List[Probe]) -> List[TestResult]:
        """内部执行方法：批量执行探针列表。

        Ctrl+C 中断后保留已完成的结果并返回。
        """
        results: List[TestResult] = []
        total = len(probes)

        try:
            for i, probe in enumerate(probes, 1):
                tag_str = f"[{probe.category}]" if probe.category else ""
                result = probe.run()
                symbol = "PASS" if result.success else "FAIL"
                print(f"  [{i}/{total}] [{symbol}] {tag_str} {probe.name}")
                results.append(result)

        except KeyboardInterrupt:
            print(f"\n  用户中断 — 已扫描 {len(results)}/{total} 个探针")

        passed = sum(1 for r in results if r.success)
        failed = len(results) - passed
        print(f"\n  探针结果: {passed}/{len(results)} 通过, {failed} 失败")
        return results

    # ============================================================
    # 分类统计
    # ============================================================

    def categories(self) -> List[str]:
        """列出所有探针分类（去重）。"""
        return sorted({p.category for p in self._probes})

    def category_counts(self) -> Dict[str, int]:
        """按分类统计探针数量。"""
        counts: Dict[str, int] = {}
        for p in self._probes:
            counts[p.category] = counts.get(p.category, 0) + 1
        return counts

    # ============================================================
    # 快捷工厂
    # ============================================================

    @staticmethod
    def simple(
        name: str,
        condition: bool,
        detail: str = "",
        *,
        category: str = "通用",
        priority: int = 3,
        tags: Optional[Set[str]] = None,
    ) -> Probe:
        """快速创建条件探针。

        Args:
            name: 探针名称。
            condition: 检查条件（True = 通过）。
            detail: 详情描述文本。
            category: 分类。
            priority: 优先级。
            tags: 标签集合。

        Returns:
            探针对象。
        """
        if not detail:
            detail = f"条件{'满足' if condition else '不满足'}"

        return Probe(
            name=name,
            check=lambda c=condition, d=detail: (c, d),
            category=category,
            priority=priority,
            tags=tags or set(),
        )

    @staticmethod
    def from_lambda(
        name: str,
        fn: Callable[[], bool],
        detail: str = "",
        *,
        category: str = "通用",
        priority: int = 3,
    ) -> Probe:
        """从简单布尔函数创建探针。

        Args:
            name: 探针名称。
            fn: 返回 bool 的检查函数。
            detail: 详情描述。
            category: 分类。
            priority: 优先级。

        Returns:
            探针对象。
        """
        return Probe(
            name=name,
            check=lambda: (fn(), detail or f"{name} 检查完成"),
            category=category,
            priority=priority,
        )

    def __repr__(self) -> str:
        return f"<ProbeManager probes={self.count} categories={len(self.categories())}>"
