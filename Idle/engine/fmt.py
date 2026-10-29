"""
数字格式化 — 处理放置游戏中超大数字的显示。
统一采用「尾数 + 指数」科学记法：超过阈值后用 2 位小数尾数 + 整数指数
（如 1.23e45），避免超长整数字符串与浮点溢出（>10³⁰⁸）。
"""
import math

# 超过此值改用科学记法（尾数+指数），避免千分位字符串过长。
SCIENTIFIC_THRESHOLD = 10 ** 15


def _exponent(num) -> int:
    """求 num 的以 10 为底的指数（整数部分位数 - 1）。

    对超大 Python int 用字符串长度（精确、不受浮点上限限制）；
    对有限 float 用 log10。inf/nan 已在调用方拦截。
    """
    if isinstance(num, int):
        return len(str(num)) - 1
    return int(math.floor(math.log10(num)))


def fmt_num(num) -> str:
    """格式化超大数字，处理浮点溢出与科学记法显示。"""
    if not isinstance(num, (int, float)):
        num = float(num)
    # 防御：指数乘区后期可能出现 inf/nan，直接返回 ∞，避免死循环。
    # 仅对 float 校验（int 永远有限；对超大 int 调 isinf/isnan 反而抛 OverflowError）。
    if isinstance(num, float) and (math.isinf(num) or math.isnan(num)):
        return "∞"
    if num < 0:
        return "-" + fmt_num(-num)
    if num < SCIENTIFIC_THRESHOLD:
        return f"{int(num):,}"
    # 超大数字：统一「尾数 + 指数」科学记法（含 >10³⁰⁸ 的任意大整数）。
    exp = _exponent(num)
    mantissa = num / (10 ** exp)
    if mantissa >= 10:  # 浮点舍入导致尾数触顶，进位指数
        mantissa /= 10
        exp += 1
    return f"{mantissa:.2f}e{exp}"


def fmt_gold(amount) -> str:
    """格式化金币数量。"""
    if amount < SCIENTIFIC_THRESHOLD:
        return f"{int(amount):,}"
    return fmt_num(amount)


def fmt_dps(val) -> str:
    """格式化 DPS 数值。"""
    return fmt_num(val)
