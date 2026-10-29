"""
统一公式引擎 — 安全数学表达式求值 + 内置曲线模板

特性:
    1. 安全求值（asteval 优先，纯 Python 回退）
    2. NumPy 向量化计算（可用时）
    3. 内置公式模板库：cardioid, rose, lemniscate, spiral, lissajous
    4. 编译缓存加速

从 pywallpaper/engine/formula_engine.py 提取并独立化。
"""

from __future__ import annotations

import math
import re
from typing import Any, Callable, Dict, List, Optional, Tuple

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
    np = None  # type: ignore

# 尝试导入 asteval，不可用时使用纯 Python 回退
try:
    from asteval import Interpreter
    _HAS_ASTEVAL = True
except ImportError:
    _HAS_ASTEVAL = False


# ================================================================
#  内置安全命名空间（asteval 不可用时的回退）
# ================================================================

_SAFE_BUILTINS = {
    "abs": abs, "round": round, "min": min, "max": max,
    "int": int, "float": float, "len": len, "range": range,
    "pow": pow, "sum": sum, "True": True, "False": False,
    "None": None,
}

_SAFE_MATH = {
    "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "asin": math.asin, "acos": math.acos, "atan": math.atan,
    "atan2": math.atan2,
    "sinh": math.sinh, "cosh": math.cosh, "tanh": math.tanh,
    "exp": math.exp, "log": math.log, "log10": math.log10,
    "sqrt": math.sqrt, "ceil": math.ceil, "floor": math.floor,
    "pi": math.pi, "e": math.e, "tau": math.tau,
    "degrees": math.degrees, "radians": math.radians,
    "hypot": math.hypot,
}


# ================================================================
#  FormulaEngine
# ================================================================

class FormulaEngine:
    """公式引擎 — 安全数学表达式求值。

    使用示例:
        engine = FormulaEngine()

        # 直接求值
        result = engine.evaluate("sin(t) * cos(t)", t=np.linspace(0, np.pi, 100))

        # 使用模板
        x_vals = engine.evaluate_template("cardioid", var_name="x", t=np.linspace(0, 2*math.pi, 200))

        # 添加自定义模板
        engine.add_template("my_curve", {"x": "t*cos(t)", "y": "t*sin(t)"})
    """

    # 内置公式模板库
    TEMPLATES: Dict[str, Dict[str, Any]] = {
        "cardioid": {
            "type": "curve",
            "x": "16*sin(t)**3 / 16.0",
            "y": "-(13*cos(t)-5*cos(2*t)-2*cos(3*t)-cos(4*t)) / 16.0",
        },
        "rose": {
            "type": "curve",
            "r": "cos(k*t)",
            "x": "r*cos(t)",
            "y": "r*sin(t)",
        },
        "lemniscate": {
            "type": "curve",
            "x": "cos(t) / (1 + sin(t)**2)",
            "y": "sin(t)*cos(t) / (1 + sin(t)**2)",
        },
        "spiral": {
            "type": "curve",
            "x": "t*cos(t) / (2*pi)",
            "y": "t*sin(t) / (2*pi)",
        },
        "lissajous": {
            "type": "curve",
            "x": "sin(a*t + delta)",
            "y": "sin(b*t)",
        },
    }

    def __init__(self):
        if _HAS_ASTEVAL:
            self._aeval = Interpreter()
        else:
            self._aeval = None
        self._cache: Dict[Tuple[str, ...], Callable] = {}

    # ── 编译 ──

    def compile(self, formula_str: str, variables: List[str]) -> Callable:
        """编译公式为可调用函数。

        参数:
            formula_str: 公式字符串（Python 语法）
            variables: 变量名列表，如 ['x', 'y', 't']

        返回:
            可调用函数 func(**kwargs) -> np.ndarray 或标量
        """
        cache_key = (formula_str, tuple(variables))
        if cache_key in self._cache:
            return self._cache[cache_key]

        processed = self._translate(formula_str)

        if _HAS_ASTEVAL and self._aeval is not None:
            func_code = f"def _func({','.join(variables)}): return {processed}"
            self._aeval.eval(func_code)
            func = self._aeval.symtable["_func"]
        else:
            func = self._build_fallback_func(processed, variables)

        self._cache[cache_key] = func
        return func

    def compile_template(self, template_name: str, var_name: Optional[str] = None) -> Callable:
        """编译内置模板。

        参数:
            template_name: 模板名称 (cardioid, rose, lemniscate, spiral, lissajous)
            var_name: 变量名（curve 类型模板需指定 'x' 或 'y'）

        返回:
            可调用函数
        """
        if template_name not in self.TEMPLATES:
            raise ValueError(f"模板 '{template_name}' 不存在，可用: {list(self.TEMPLATES.keys())}")

        template = self.TEMPLATES[template_name]

        if template.get("type") == "curve":
            if var_name is None:
                raise ValueError("curve 类型模板需要指定 var_name ('x', 'y', 或 'r')")
            expr = template.get(var_name)
            if expr is None:
                raise ValueError(f"模板 '{template_name}' 无变量 '{var_name}'，可用: {[k for k in template if k != 'type']}")
        else:
            expr = template["expression"]

        variables = self._extract_variables(expr)
        return self.compile(expr, variables)

    # ── 求值 ──

    def evaluate(self, formula_str_or_func: str | Callable, **kwargs) -> np.ndarray:
        """执行公式并返回结果。

        参数:
            formula_str_or_func: 公式字符串 或 编译后的函数
            **kwargs: 变量值（标量或 NumPy 数组）

        返回:
            NumPy 数组
        """
        if isinstance(formula_str_or_func, str):
            variables = self._extract_variables(formula_str_or_func)
            func = self.compile(formula_str_or_func, variables)
        else:
            func = formula_str_or_func

        try:
            result = func(**kwargs)
            if HAS_NUMPY:
                return np.asarray(result, dtype=np.float64)
            else:
                # 纯 Python 回退：确保返回 float 或 float 列表
                if hasattr(result, '__iter__'):
                    return [float(x) for x in result]
                return float(result)
        except Exception as e:
            import sys
            print(f"[FormulaEngine] 求值错误: {e}", file=sys.stderr, flush=True)
            if HAS_NUMPY:
                return np.float64(0.0)
            return 0.0

    def evaluate_template(self, template_name: str, var_name: Optional[str] = None, **kwargs) -> np.ndarray:
        """执行内置模板。

        参数:
            template_name: 模板名称
            var_name: 变量名（curve 模板需指定）
            **kwargs: 变量值

        返回:
            NumPy 数组
        """
        func = self.compile_template(template_name, var_name)
        return self.evaluate(func, **kwargs)

    # ── 模板管理 ──

    def add_template(self, name: str, template: Dict[str, Any]):
        """添加自定义模板。

        参数:
            name: 模板名称
            template: 模板配置字典
                curve 类型: {'type': 'curve', 'x': '...', 'y': '...'}
                通用类型:   {'expression': '...', 'variables': [...]}
        """
        self.TEMPLATES[name] = template

    def list_templates(self) -> List[str]:
        """列出所有可用模板名称。"""
        return list(self.TEMPLATES.keys())

    # ── 内部方法 ──

    def _translate(self, expr: str) -> str:
        """转换 Python 语法为 NumPy 兼容表达式。

        注意: 仅在 NumPy 可用时执行向量化转换；
              无 NumPy 时保持纯 Python 语法，公式将作用于标量值。
        """
        if not HAS_NUMPY:
            return expr

        # 处理 if-else 三元表达式
        expr = self._ifelse_to_where(expr)

        # min/max → np.minimum / np.maximum
        expr = re.sub(r'\bmin\(', 'minimum(', expr)
        expr = re.sub(r'\bmax\(', 'maximum(', expr)

        # and/or/not → &/|/~
        expr = re.sub(r'\band\b', '&', expr)
        expr = re.sub(r'\bor\b', '|', expr)
        expr = re.sub(r'\bnot\b', '~', expr)

        return expr

    def _ifelse_to_where(self, expr: str) -> str:
        """将 Python 三元表达式转换为 NumPy where()。"""
        for _ in range(10):
            if_pos = expr.rfind(" if ")
            if if_pos == -1:
                break

            else_pos = expr.find(" else ", if_pos)
            if else_pos == -1:
                break

            # 向左找条件开始
            cond_start = if_pos
            for i in range(if_pos - 1, -1, -1):
                if expr[i] in " \t\n":
                    cond_start = i + 1
                    break

            condition = expr[cond_start:if_pos].strip()
            true_val = expr[if_pos + 4:else_pos].strip()

            # 向右找假值结束
            false_end = len(expr)
            depth = 0
            for i in range(else_pos + 6, len(expr)):
                if expr[i] == "(":
                    depth += 1
                elif expr[i] == ")":
                    if depth == 0:
                        false_end = i
                        break
                    depth -= 1
                elif expr[i] == "," and depth == 0:
                    false_end = i
                    break

            false_val = expr[else_pos + 6:false_end].strip()

            replacement = f"where({condition}, {true_val}, {false_val})"
            expr = expr[:cond_start] + replacement + expr[false_end:]

        return expr

    def _extract_variables(self, expr: str) -> List[str]:
        """从公式表达式中提取变量名。"""
        math_keywords = {
            "sin", "cos", "tan", "asin", "acos", "atan", "atan2",
            "sinh", "cosh", "tanh",
            "exp", "log", "log10", "sqrt", "abs",
            "pi", "e", "tau",
            "ceil", "floor",
            "minimum", "maximum", "where", "clip",
            "True", "False", "None",
            "int", "float", "str", "bool",
            "random",
        }

        tokens = re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", expr)
        variables = [t for t in tokens if t not in math_keywords]

        seen: set = set()
        result: List[str] = []
        for v in variables:
            if v not in seen:
                seen.add(v)
                result.append(v)

        return result

    def _build_fallback_func(self, expr: str, variables: List[str]) -> Callable:
        """不使用 asteval 时的回退编译。"""
        # 构建安全命名空间
        ns = {}
        ns.update(_SAFE_MATH)
        ns.update(_SAFE_BUILTINS)

        if HAS_NUMPY:
            # 注入 NumPy 向量化函数
            ns.update({
                "sin": np.sin, "cos": np.cos, "tan": np.tan,
                "asin": np.arcsin, "acos": np.arccos, "atan": np.arctan,
                "atan2": np.arctan2,
                "sinh": np.sinh, "cosh": np.cosh, "tanh": np.tanh,
                "exp": np.exp, "log": np.log, "log10": np.log10,
                "sqrt": np.sqrt, "abs": np.abs,
                "ceil": np.ceil, "floor": np.floor,
                "pi": np.pi, "e": np.e,
                "minimum": np.minimum, "maximum": np.maximum,
                "where": np.where, "clip": np.clip,
                "array": np.array,
            })
        else:
            # 纯 Python 回退：使用 math 模块（标量运算）
            ns.update({
                "minimum": min, "maximum": max,
                "where": lambda cond, x, y: x if cond else y,
                "clip": lambda a, a_min, a_max: max(a_min, min(a, a_max)),
                "array": list,
            })

        # 安全加固：清空 __builtins__，阻断通过表达式注入任意代码
        # （如 __import__('os').system(...)）。公式只允许使用上方注入的安全
        # 数学 / NumPy 名称，禁用一切内建函数。
        ns["__builtins__"] = {}

        code = f"def _func({','.join(variables)}):\n    return {expr}"
        compiled = compile(code, "<formula_engine>", "exec")
        exec(compiled, ns)
        return ns["_func"]
