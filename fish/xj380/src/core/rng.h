// ═══════════════════════════════════════════════════════════════════════
//  rng.h —— 确定性随机数（双端同源）
// ═══════════════════════════════════════════════════════════════════════
//
// ◆ 对偶：fishtank/rng.py::DetRandom（逐方法一一对应）
//
// 递推式（rng.py 文件头已给出 C++ 参考实现，这里就是它）::
//
//     seed = seed * 6364136223846793005 + 1442695040888963407   // u64 自然溢出
//     out  = (u32)(seed >> 32)
//
// 🔴 随机数**消耗顺序**是双端契约的一部分。
//    * chance(p)：p<=0 与 p>=1 **不消耗**随机数，中间才消耗 1 次；
//    * randint(lo,hi)：hi<=lo **不消耗**，直接返回 lo；
//    * choice(seq)：转调 randint(0, n-1)，所以 n==1 时**不消耗**。
//    这三条早退分支若漏写，种子立刻错位，后续所有繁殖结果全错。

#ifndef FT_CORE_RNG_H
#define FT_CORE_RNG_H

#include "ft_types.h"

namespace ft {

extern const u64 kDefaultSeed;  // 88172645463325252

class DetRandom {
public:
    /// :param seed: 初始种子；0 会被替换成 kDefaultSeed（对偶 Python 行为）
    explicit DetRandom(u64 seed = 0ULL);

    /// 推进一步，返回 32 位无符号整数。
    u32 next_u32();

    /// [0.0, 1.0) 的浮点数 = next_u32() / 2^32。
    f64 random();

    /// [lo, hi) 的浮点数；lo >= hi 时直接返回 lo（**不消耗**随机数）。
    f64 uniform(f64 lo, f64 hi);

    /// 闭区间 [lo, hi] 的整数；hi <= lo 时返回 lo（**不消耗**随机数）。
    i32 randint(i32 lo, i32 hi);

    /// 以概率 p 返回 true。p<=0 恒 false、p>=1 恒 true，两者都**不消耗**随机数。
    bool chance(f64 p);

    /// 当前种子（存档用）。对偶 DetRandom.state()。
    u64 state() const { return seed_; }

    /// 恢复种子（读档用）。0 → kDefaultSeed。
    void restore(u64 seed);

    /// 已消耗次数（仅调试对拍用，不参与结算）。
    u64 calls() const { return calls_; }

private:
    u64 seed_;
    u64 calls_;
};

}  // namespace ft

#endif  // FT_CORE_RNG_H
