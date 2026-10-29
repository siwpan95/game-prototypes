// ft_math.cpp —— 见 ft_math.h 的契约说明。零系统 include。

#include "ft_math.h"

namespace ft {

const f64 kPi  = 3.14159265358979323846;
const f64 kTau = 6.28318530717958647692;

// ══════════════════════════════════════════════════════════════
//  基础
// ══════════════════════════════════════════════════════════════

f64 fabs_(f64 x) {
    return x < 0.0 ? -x : x;
}

f64 floor_(f64 x) {
    // |x| >= 2^52 的 double 一定已经是整数，直接返回，避免强转溢出。
    const f64 kBig = 4503599627370496.0;  // 2^52
    if (x >= kBig || x <= -kBig) {
        return x;
    }
    // (i64) 是向零截断；负数且有小数部分时要再减一。
    i64 t = static_cast<i64>(x);
    f64 f = static_cast<f64>(t);
    if (f > x) {
        f -= 1.0;
    }
    return f;
}

i64 floor_ll(f64 x) {
    i64 t = static_cast<i64>(x);          // 向零截断
    if (static_cast<f64>(t) > x) {        // 负数且有小数 → 修正
        t -= 1;
    }
    return t;
}

i64 round_half_up(f64 x) {
    // ★ 与 fishtank/economy.py::round_half_up 逐字对应：int(math.floor(x + 0.5))
    return floor_ll(x + 0.5);
}

i64 round_half_even(f64 x) {
    // Python 内置 round(x) 的行为：恰好 .5 时向偶数靠。
    f64 f = floor_(x);
    f64 d = x - f;
    i64 base = static_cast<i64>(f);
    if (d > 0.5) {
        return base + 1;
    }
    if (d < 0.5) {
        return base;
    }
    // d == 0.5：取偶
    return (base % 2 == 0) ? base : base + 1;
}

f64 clamp_(f64 v, f64 lo, f64 hi) {
    if (hi < lo) {
        return lo;
    }
    if (v < lo) {
        return lo;
    }
    if (v > hi) {
        return hi;
    }
    return v;
}

f64 lerp_(f64 a, f64 b, f64 t) {
    t = clamp_(t, 0.0, 1.0);
    return a + (b - a) * t;
}

f64 r6(f64 v) {
    // 对偶 state.py::r6 —— round(v, 6) 且把 -0.0 归一成 0.0。
    // Python 用的是十进制正确舍入；这里用「×1e6 后 half-even」逼近，
    // 二者仅在 v*1e6 落在 .5 附近且不可精确表示时可能差 1ulp。
    // ⚠️ r6 只作用于鱼的 x/y（渲染坐标），不影响金币 / 阶段 / RNG，故安全。
    f64 s = v * 1000000.0;
    f64 f = floor_(s);
    f64 d = s - f;
    f64 out;
    if (d > 0.5) {
        out = f + 1.0;
    } else if (d < 0.5) {
        out = f;
    } else {
        f64 half = f * 0.5;
        out = (half == floor_(half)) ? f : (f + 1.0);
    }
    if (out == 0.0) {
        return 0.0;
    }
    return out / 1000000.0;
}

// ══════════════════════════════════════════════════════════════
//  超越函数（渲染层专用）
// ══════════════════════════════════════════════════════════════

f64 sqrt_(f64 x) {
    if (x <= 0.0) {
        return 0.0;
    }
    // 先用二分把初值拉到同一量级，再跑 6 次牛顿迭代（double 收敛足够）。
    f64 lo = x < 1.0 ? x : 1.0;
    f64 hi = x < 1.0 ? 1.0 : x;
    f64 g = (lo + hi) * 0.5;
    for (i32 i = 0; i < 60; ++i) {
        f64 next = 0.5 * (g + x / g);
        if (next == g) {
            break;
        }
        g = next;
    }
    return g;
}

/// [-π/4, π/4] 上的 sin 多项式（Taylor 到 x^13，double 精度足够）。
static f64 sin_kernel(f64 x) {
    const f64 x2 = x * x;
    // 霍纳展开，系数 = 1/(2k+1)!
    f64 r = -7.64716373181981647590e-13;   // -1/15!
    r = r * x2 + 1.60590438368216145994e-10;  //  1/13!
    r = r * x2 - 2.50521083854417187751e-08;  // -1/11!
    r = r * x2 + 2.75573192239858906526e-06;  //  1/9!
    r = r * x2 - 1.98412698412698412526e-04;  // -1/7!
    r = r * x2 + 8.33333333333333321769e-03;  //  1/5!
    r = r * x2 - 1.66666666666666657415e-01;  // -1/3!
    return x + x * x2 * r;
}

/// [-π/4, π/4] 上的 cos 多项式。
static f64 cos_kernel(f64 x) {
    const f64 x2 = x * x;
    f64 r = -1.13596475577881948265e-11;   // -1/14!
    r = r * x2 + 2.08757232129817482790e-09;  //  1/12!
    r = r * x2 - 2.75573141792967388112e-07;  // -1/10!
    r = r * x2 + 2.48015872888517179954e-05;  //  1/8!
    r = r * x2 - 1.38888888888888894189e-03;  // -1/6!
    r = r * x2 + 4.16666666666666643537e-02;  //  1/4!
    return 1.0 - 0.5 * x2 + x2 * x2 * r;
}

/// Cody-Waite 约减：把 x 折到 [-π/4, π/4]，同时给出象限号。
static void reduce_quadrant(f64 x, f64* out_r, i32* out_q) {
    // π/2 拆成三段高位，减少大幅角的约减误差。
    const f64 kPio2   = 1.57079632679489655800e+00;
    const f64 kPio2Hi = 1.57079632673412561417e+00;
    const f64 kPio2Mi = 6.07710050650619224932e-11;
    const f64 kPio2Lo = 2.02226624879595063154e-21;
    const f64 kTwoOverPi = 6.36619772367581382433e-01;

    f64 n = floor_(x * kTwoOverPi + 0.5);
    // 象限号取模 4（n 可能是负数，先规整）
    i64 ni = floor_ll(n);
    i64 q = ni & 3;
    if (q < 0) {
        q += 4;
    }
    f64 r = x - n * kPio2Hi;
    r = r - n * kPio2Mi;
    r = r - n * kPio2Lo;
    // 兜底：极端输入下仍不在区间内时用单段 π/2 再收一次
    while (r > kPio2 * 0.5) {
        r -= kPio2;
        q = (q + 1) & 3;
    }
    while (r < -kPio2 * 0.5) {
        r += kPio2;
        q = (q + 3) & 3;
    }
    *out_r = r;
    *out_q = static_cast<i32>(q);
}

f64 sin_(f64 x) {
    f64 r = 0.0;
    i32 q = 0;
    reduce_quadrant(x, &r, &q);
    switch (q) {
        case 0:  return sin_kernel(r);
        case 1:  return cos_kernel(r);
        case 2:  return -sin_kernel(r);
        default: return -cos_kernel(r);
    }
}

f64 cos_(f64 x) {
    f64 r = 0.0;
    i32 q = 0;
    reduce_quadrant(x, &r, &q);
    switch (q) {
        case 0:  return cos_kernel(r);
        case 1:  return -sin_kernel(r);
        case 2:  return -cos_kernel(r);
        default: return sin_kernel(r);
    }
}

f64 pow10_(i32 n) {
    // 10^0 .. 10^22 在 double 里都是**精确值**，用查表可保证 strtod 快路径的正确舍入。
    static const f64 kPow10[23] = {
        1e0,  1e1,  1e2,  1e3,  1e4,  1e5,  1e6,  1e7,
        1e8,  1e9,  1e10, 1e11, 1e12, 1e13, 1e14, 1e15,
        1e16, 1e17, 1e18, 1e19, 1e20, 1e21, 1e22
    };
    if (n >= 0 && n <= 22) {
        return kPow10[n];
    }
    if (n < 0 && n >= -22) {
        return 1.0 / kPow10[-n];
    }
    // 超出精确表范围：连乘（此时已无法保证最后一位，数据文件不会出现）
    f64 r = 1.0;
    f64 base = (n < 0) ? 0.1 : 10.0;
    i32 k = (n < 0) ? -n : n;
    for (i32 i = 0; i < k; ++i) {
        r *= base;
    }
    return r;
}

}  // namespace ft
