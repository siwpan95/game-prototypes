"""
测试运行器：测试执行引擎，支持超时控制和 setUp/tearDown 生命周期。

融合 py_test_runner 的 TestRunner 架构，提供简洁的测试执行接口。

用法：
    from test.runner import TestRunner, TestResult, ErrorType

    def test_addition():
        assert 1 + 1 == 2

    runner = TestRunner(timeout=5.0)
    runner.set_setup(lambda: print("准备中..."))
    result = runner.run_test(test_addition)
    print(result)

    results = runner.run_tests([test_addition, test_subtraction])
"""

import time
import traceback
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional, Tuple, Type


# ============================================================
# 错误类型
# ============================================================

class ErrorType(Enum):
    """测试错误类型枚举。

    涵盖通过、断言失败、运行时错误、超时、框架错误等各类情况。
    每种类型有唯一标识码和中文描述。
    """

    # 通过
    PASS = ("PASS", "测试通过")

    # 断言失败
    ASSERT_EQUAL = ("FAIL-001", "断言相等失败：期望值与实际值不符")
    ASSERT_TRUE = ("FAIL-002", "断言为真失败：表达式求值为 False")
    ASSERT_FALSE = ("FAIL-003", "断言为假失败：表达式求值为 True")
    ASSERT_IN = ("FAIL-004", "断言包含失败：值不在集合中")
    ASSERT_RAISES = ("FAIL-005", "断言异常失败：未抛出预期异常")
    UNEXPECTED_RESULT = ("FAIL-006", "意外结果：返回值与预期不符")

    # 运行时错误
    RUNTIME_ERROR = ("ERR-001", "运行时错误")
    ATTRIBUTE_ERROR = ("ERR-002", "属性错误：对象没有该属性或方法")
    TYPE_ERROR = ("ERR-003", "类型错误：操作数类型不匹配")
    VALUE_ERROR = ("ERR-004", "值错误：参数值不合法")
    KEY_ERROR = ("ERR-005", "键错误：字典中不存在该键")
    INDEX_ERROR = ("ERR-006", "索引错误：序列索引越界")
    ZERO_DIVISION = ("ERR-007", "零除错误：除数为零")
    NAME_ERROR = ("ERR-008", "名称错误：变量未定义")
    OS_ERROR = ("ERR-009", "系统错误：操作系统相关异常")
    IO_ERROR = ("ERR-010", "IO 错误：文件读写失败")
    RECURSION_ERROR = ("ERR-011", "递归错误：递归深度超限")
    MEMORY_ERROR = ("ERR-012", "内存错误：内存不足")

    # 语法/导入错误
    SYNTAX_ERROR = ("ERR-101", "语法错误：代码无法解析")
    IMPORT_ERROR = ("ERR-102", "导入错误：模块不存在或无法加载")
    MODULE_NOT_FOUND = ("ERR-104", "模块未找到：依赖缺失")

    # 超时
    TIMEOUT_ERROR = ("ERR-201", "超时错误：执行超过时间限制")

    # 框架错误
    SETUP_ERROR = ("ERR-301", "准备阶段错误：setUp 方法异常")
    TEARDOWN_ERROR = ("ERR-302", "清理阶段错误：tearDown 方法异常")

    # 跳过
    TEST_SKIP = ("SKIP-000", "测试跳过")

    # 未知
    UNKNOWN_ERROR = ("ERR-999", "未知错误：无法归类的异常")

    @classmethod
    def from_exception(cls, exc: Exception) -> "ErrorType":
        """根据异常类型自动匹配 ErrorType。"""
        mapping: Dict[Type[BaseException], "ErrorType"] = {
            AssertionError: cls.ASSERT_EQUAL,
            AttributeError: cls.ATTRIBUTE_ERROR,
            TypeError: cls.TYPE_ERROR,
            ValueError: cls.VALUE_ERROR,
            KeyError: cls.KEY_ERROR,
            IndexError: cls.INDEX_ERROR,
            ZeroDivisionError: cls.ZERO_DIVISION,
            NameError: cls.NAME_ERROR,
            OSError: cls.OS_ERROR,
            IOError: cls.IO_ERROR,
            RecursionError: cls.RECURSION_ERROR,
            MemoryError: cls.MEMORY_ERROR,
            SyntaxError: cls.SYNTAX_ERROR,
            ImportError: cls.IMPORT_ERROR,
            ModuleNotFoundError: cls.MODULE_NOT_FOUND,
            TimeoutError: cls.TIMEOUT_ERROR,
        }
        return mapping.get(type(exc), cls.UNKNOWN_ERROR)

    @property
    def code(self) -> str:
        """错误类型代码。"""
        return self.value[0]

    @property
    def description(self) -> str:
        """错误类型中文描述。"""
        return self.value[1]


# ============================================================
# 跳过机制
# ============================================================

def skip(reason: str = "跳过") -> "Callable[[Callable], Callable]":
    """标记测试为跳过。被装饰测试不会执行，报告中记为 SKIP。

    用于可选依赖缺失（如 pygame / tkinter）时，避免「静默通过」掩盖问题。

    用法：
        @skip("需要 pygame")
        def test_load_font(): ...
    """
    def deco(fn: "Callable") -> "Callable":
        fn.skip = reason  # type: ignore[attr-defined]
        return fn
    return deco


def skip_if_missing(module_name: str, reason: str | None = None) -> "Callable":
    """当可选依赖模块不可用时，自动跳过测试。

    用法：
        @skip_if_missing("pygame")
        def test_render(): ...
    """
    import importlib
    try:
        importlib.import_module(module_name)
        _missing = False
    except Exception:
        _missing = True
    msg = reason or f"缺少可选依赖: {module_name}"

    def deco(fn: "Callable") -> "Callable":
        if _missing:
            fn.skip = msg  # type: ignore[attr-defined]
        return fn
    return deco


# ============================================================
# 测试结果
# ============================================================

@dataclass
class TestResult:
    """单条测试执行结果。

    Attributes:
        success: 测试是否通过。
        error_type: 错误类型（通过时为 ErrorType.PASS）。
        message: 结果描述信息。
        duration: 执行耗时（秒）。
        test_name: 测试函数名称。
        traceback_text: 异常堆栈文本（失败时）。
    """
    success: bool = True
    error_type: ErrorType = ErrorType.PASS
    message: str = ""
    duration: float = 0.0
    test_name: str = ""
    traceback_text: Optional[str] = None

    def summary(self) -> str:
        """一行摘要。"""
        symbol = "PASS" if self.success else "FAIL"
        return f"[{symbol}] {self.test_name} ({self.duration:.3f}s) {self.message}"

    def detail(self) -> str:
        """多行详情。"""
        lines = [
            f"{'='*50}",
            f"  测试   : {self.test_name}",
            f"  结果   : {'通过' if self.success else '失败'}",
            f"  错误码 : {self.error_type.code}",
            f"  耗时   : {self.duration:.3f}s",
            f"  消息   : {self.message}",
        ]
        if self.traceback_text:
            lines.append(f"  堆栈   :\n{self.traceback_text}")
        lines.append(f"{'='*50}")
        return "\n".join(lines)

    def __bool__(self) -> bool:
        return self.success


# ============================================================
# 测试运行器
# ============================================================

class TestRunner:
    """测试执行引擎。

    支持特性：
    - setUp / tearDown 生命周期
    - 超时控制（独立线程 + join 超时）
    - 异常自动归类
    - 执行时间统计

    用法：
        runner = TestRunner(timeout=5.0)
        runner.set_setup(lambda: prepare())
        runner.set_teardown(lambda: cleanup())

        result = runner.run_test(my_test_function)
        results = runner.run_tests([test1, test2, test3])
    """

    def __init__(self, timeout: float = 30.0):
        """初始化运行器。

        Args:
            timeout: 单个测试的超时时间（秒）。
        """
        self.timeout = timeout
        self._setup_fn: Optional[Callable[[], None]] = None
        self._teardown_fn: Optional[Callable[[], None]] = None

    # ----------------------------------------------------------
    # 生命周期钩子
    # ----------------------------------------------------------

    def set_setup(self, fn: Callable[[], None]) -> None:
        """设置 setUp 函数：每个测试执行前调用。

        Args:
            fn: 无参数、无返回值的准备函数。
        """
        self._setup_fn = fn

    def set_teardown(self, fn: Callable[[], None]) -> None:
        """设置 tearDown 函数：每个测试执行后调用。

        Args:
            fn: 无参数、无返回值的清理函数。
        """
        self._teardown_fn = fn

    # ----------------------------------------------------------
    # 测试执行
    # ----------------------------------------------------------

    def run_test(self, test_fn: Callable[[], None]) -> TestResult:
        """执行单个测试函数。

        Args:
            test_fn: 无参数、无返回值的测试函数（通过 assert/raise 报告失败）。

        Returns:
            TestResult 对象。
        """
        test_name = test_fn.__name__
        start = time.perf_counter()

        # 跳过标记：被 @skip / @skip_if_missing 标记的测试直接记为 SKIP
        skip_reason = getattr(test_fn, "skip", None)
        if skip_reason:
            return TestResult(
                success=False,
                error_type=ErrorType.TEST_SKIP,
                message=f"跳过: {skip_reason}",
                duration=time.perf_counter() - start,
                test_name=test_name,
            )

        # setUp
        if self._setup_fn:
            try:
                self._setup_fn()
            except Exception as e:
                return TestResult(
                    success=False,
                    error_type=ErrorType.SETUP_ERROR,
                    message=f"setUp 失败: {e}",
                    duration=time.perf_counter() - start,
                    test_name=test_name,
                    traceback_text=traceback.format_exc(),
                )

        # 执行测试（带超时）
        result = self._execute_with_timeout(test_fn, test_name)
        duration = time.perf_counter() - start

        # tearDown
        if self._teardown_fn:
            try:
                self._teardown_fn()
            except Exception as e:
                # tearDown 异常记录但不影响测试结果
                if result.success:
                    result = TestResult(
                        success=False,
                        error_type=ErrorType.TEARDOWN_ERROR,
                        message=f"tearDown 失败: {e}",
                        duration=duration,
                        test_name=test_name,
                        traceback_text=traceback.format_exc(),
                    )

        result.duration = duration
        result.test_name = test_name
        return result

    def run_tests(self, test_fns: List[Callable[[], None]]) -> List[TestResult]:
        """批量执行测试。

        Ctrl+C 中断后保留已完成的结果并返回。

        Args:
            test_fns: 测试函数列表。

        Returns:
            TestResult 列表。
        """
        results: List[TestResult] = []
        total = len(test_fns)
        start_all = time.perf_counter()

        try:
            for i, fn in enumerate(test_fns, 1):
                name = fn.__name__
                result = self.run_test(fn)
                if result.error_type == ErrorType.TEST_SKIP:
                    symbol = "SKIP"
                elif result.success:
                    symbol = "PASS"
                else:
                    symbol = "FAIL"
                print(f"  [{i}/{total}] [{symbol}] {name} ({result.duration:.3f}s)")
                results.append(result)

        except KeyboardInterrupt:
            print(f"\n  用户中断 — 已执行 {len(results)}/{total} 个测试")

        total_time = time.perf_counter() - start_all
        passed = sum(1 for r in results if r.success)
        print(f"\n  完成: {passed}/{len(results)} 通过, 耗时 {total_time:.2f}s")
        return results

    def _execute_with_timeout(
        self, test_fn: Callable[[], None], test_name: str
    ) -> TestResult:
        """在独立线程中执行测试，进行超时控制。"""
        exception_info: List[Optional[Tuple[str, Exception]]] = [None]
        done = threading.Event()

        def _runner() -> None:
            try:
                test_fn()
            except AssertionError as e:
                exception_info[0] = ("assert", e)
            except Exception as e:
                exception_info[0] = ("exception", e)
            finally:
                done.set()

        thread = threading.Thread(target=_runner, daemon=True)
        thread.start()

        finished = done.wait(timeout=self.timeout)

        if not finished:
            return TestResult(
                success=False,
                error_type=ErrorType.TIMEOUT_ERROR,
                message=f"测试超时（>{self.timeout}s）",
                test_name=test_name,
            )

        err = exception_info[0]
        if err is None:
            return TestResult(
                success=True,
                error_type=ErrorType.PASS,
                message="通过",
                test_name=test_name,
            )
        else:
            err_type, err_value = err
            error_code = ErrorType.from_exception(err_value)
            return TestResult(
                success=False,
                error_type=error_code,
                message=f"{type(err_value).__name__}: {err_value}",
                test_name=test_name,
                traceback_text=traceback.format_exc(),
            )

    # ----------------------------------------------------------
    # 汇总
    # ----------------------------------------------------------

    @staticmethod
    def summarize(results: List[TestResult]) -> Dict[str, int]:
        """汇总测试结果统计。

        Args:
            results: TestResult 列表。

        Returns:
            {"total": N, "passed": N, "failed": N, "errors": N, "duration": total_s}
        """
        passed = sum(1 for r in results if r.success)
        skipped = sum(1 for r in results if r.error_type == ErrorType.TEST_SKIP)
        failed = sum(
            1 for r in results
            if not r.success and r.error_type != ErrorType.TEST_SKIP
        )
        errors = sum(1 for r in results if not r.success and r.error_type not in (
            ErrorType.ASSERT_EQUAL, ErrorType.ASSERT_TRUE,
            ErrorType.ASSERT_FALSE, ErrorType.ASSERT_IN,
            ErrorType.ASSERT_RAISES, ErrorType.UNEXPECTED_RESULT,
            ErrorType.TEST_SKIP,
        ))
        total_duration = sum(r.duration for r in results)
        return {
            "total": len(results),
            "passed": passed,
            "skipped": skipped,
            "failed": failed,
            "errors": errors,
            "duration": total_duration,
        }

    def __repr__(self) -> str:
        return f"<TestRunner timeout={self.timeout}s>"
