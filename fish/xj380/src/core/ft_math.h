// ═══════════════════════════════════════════════════════════════════════
//  ft_math.h —— 自实现数学库（freestanding 无 libm）
// ═══════════════════════════════════════════════════════════════════════
//
// ◆ 对偶：fishtank/economy.py 的 round_half_up / clamp / lerp
//         + pyapp/fish_painter.py 用到的 math.sin / math.sqrt / math.pi
//
// 🔴 取整铁律（ARCHITECTURE §11 第 6 条）
//    金额取整**只能**用 round_half_up(x) = floor(x + 0.5)。
//    * 禁用 std::round —— 它是 round-half-away-from-zero，x.5 处与 Python 不一致；
//    * 禁用 (long long) 强转 —— 那是 trunc-toward-zero，负数处更错；
//    * Python 端也禁用内置 round() —— 那是 banker's rounding。
//    三者在 x = 0.5 / 2.5 / -0.5 处结论全不同，任何一处用错都会让双端金币漂移。
//
// 🔴 编译要求：必须带 `-ffp-contract=off`。否则编译器会把 `a*b + c` 融合成
//    FMA 单指令（中间结果不舍入），与 Python 的两步运算产生 1 ULP 差异，
//    在 89016 步的累加里足以放大成可见偏差。构建脚本 xj_build.py 已强制该标志。

#ifndef FT_CORE_FT_MATH_H
#define FT_CORE_FT_MATH_H

#include "ft_types.h"

namespace ft {

extern const f64 kPi;   // 3.14159265358979323846
extern const f64 kTau;  // 2 * kPi

// ── 基础 ──

/// 绝对值。
f64 fabs_(f64 x);

/// 向下取整（返回 double）。纯位无关实现，不依赖 libm。
f64 floor_(f64 x);

/// 向下取整到 i64。调用方须保证 |x| < 9.2e18。
i64 floor_ll(f64 x);

/// ★ 四舍五入到整数厘：floor(x + 0.5)。
/// 对偶 fishtank/economy.py::round_half_up。**全项目唯一允许的金额取整方式。**
i64 round_half_up(f64 x);

/// Python 内置 round() 的语义：round-half-to-even（银行家舍入）。
/// ⚠️ 只在一处使用 —— offline.py 第 272 行统计 upkeep_milli 时用了内置 round()。
///    那是**上报字段**（不进金币账），为保持双端逐行对偶这里如实复刻。
///    详见 T05_REPORT.md「遗留问题」。任何新代码都不要用它。
i64 round_half_even(f64 x);

/// 钳制到 [lo, hi]；hi < lo 时返回 lo。对偶 economy.py::clamp。
f64 clamp_(f64 v, f64 lo, f64 hi);

/// 线性插值，t 先钳到 [0,1]。对偶 economy.py::lerp。
f64 lerp_(f64 a, f64 b, f64 t);

/// 序列化用的 6 位小数规范化。对偶 fishtank/state.py::r6。
/// ⚠️ 仅作用于鱼的 x/y 坐标（渲染用），不参与任何结算数值。
f64 r6(f64 v);

inline i32 imin(i32 a, i32 b) { return a < b ? a : b; }
inline i32 imax(i32 a, i32 b) { return a > b ? a : b; }
inline i64 llmin(i64 a, i64 b) { return a < b ? a : b; }
inline i64 llmax(i64 a, i64 b) { return a > b ? a : b; }
inline f64 fmin_(f64 a, f64 b) { return a < b ? a : b; }
inline f64 fmax_(f64 a, f64 b) { return a > b ? a : b; }

// ── 超越函数（仅渲染层使用，结算层不碰）──

/// 平方根（牛顿迭代 + 二分指数初值）。x < 0 返回 0。
f64 sqrt_(f64 x);

/// 正弦。Cody-Waite 双段 π 约减 + 11 阶最小二乘多项式，|误差| < 2e-16。
f64 sin_(f64 x);

/// 余弦。
f64 cos_(f64 x);

/// 整数次幂（用于 10^n 换算，n 可负）。
f64 pow10_(i32 n);

}  // namespace ft

#endif  // FT_CORE_FT_MATH_H
