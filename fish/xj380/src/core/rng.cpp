// rng.cpp —— 见 rng.h。◆ 对偶 fishtank/rng.py

#include "rng.h"

namespace ft {

namespace {
const u64 kA = 6364136223846793005ULL;
const u64 kC = 1442695040888963407ULL;
const f64 kU32Scale = 4294967296.0;  // 2^32，与 Python 的 float(1 << 32) 相同
}  // namespace

const u64 kDefaultSeed = 88172645463325252ULL;

DetRandom::DetRandom(u64 seed) : seed_(seed), calls_(0ULL) {
    // 对偶 Python：`self.seed = int(seed) % 2**64`，为 0 则退回默认种子
    if (seed_ == 0ULL) {
        seed_ = kDefaultSeed;
    }
}

u32 DetRandom::next_u32() {
    // u64 无符号乘加天然模 2^64，与 Python 的 `% (1 << 64)` 等价
    seed_ = seed_ * kA + kC;
    ++calls_;
    return static_cast<u32>((seed_ >> 32) & 0xFFFFFFFFULL);
}

f64 DetRandom::random() {
    return static_cast<f64>(next_u32()) / kU32Scale;
}

f64 DetRandom::uniform(f64 lo, f64 hi) {
    if (hi <= lo) {
        return lo;  // 不消耗随机数
    }
    return lo + (hi - lo) * random();
}

i32 DetRandom::randint(i32 lo, i32 hi) {
    if (hi <= lo) {
        return lo;  // 🔴 不消耗随机数 —— choice() 单元素池依赖这条
    }
    u32 span = static_cast<u32>(hi - lo + 1);
    return lo + static_cast<i32>(next_u32() % span);
}

bool DetRandom::chance(f64 p) {
    if (p <= 0.0) {
        return false;  // 不消耗
    }
    if (p >= 1.0) {
        return true;   // 不消耗
    }
    return random() < p;
}

void DetRandom::restore(u64 seed) {
    seed_ = seed;
    if (seed_ == 0ULL) {
        seed_ = kDefaultSeed;
    }
}

}  // namespace ft
