"""确定性随机数（双端同源）。

🔴 禁止 `from __future__ import annotations`（E6）。
🔴 绝不使用 Python 的 `random` 模块 —— 它的算法（Mersenne Twister）在 C++ 端
   无法逐位复现。本模块是一个 64 位 LCG，用**整数运算**定义，Python 与 C++
   可以逐步比对种子序列。

递推式（与 XJ380 C++ 端逐位一致）::

    seed = (seed * 6364136223846793005 + 1442695040888963407) mod 2^64
    out  = (seed >> 32) & 0xFFFFFFFF        # 取高 32 位，低位随机性差

C++ 端等价实现::

    uint64_t seed;
    uint32_t next_u32() {
        seed = seed * 6364136223846793005ULL + 1442695040888963407ULL;  // 自然溢出
        return (uint32_t)(seed >> 32);
    }
"""

_A = 6364136223846793005
_C = 1442695040888963407
_M = 1 << 64
_U32 = 1 << 32

DEFAULT_SEED = 88172645463325252
"""默认初始种子（与 balance.json 的 start.rng_seed 保持一致）。"""


class DetRandom:
    """确定性伪随机源。

    所有方法都只依赖 :meth:`next_u32`，因此 C++ 端只要复现 `next_u32` 与
    本文件的浮点换算顺序，即可得到逐位相同的结果。

    用法::

        rng = DetRandom(12345)
        rng.random()        # [0, 1)
        rng.uniform(1, 3)   # [1, 3)
        rng.randint(0, 5)   # {0,1,2,3,4,5}
        rng.chance(0.12)    # True 的概率 12%
    """

    def __init__(self, seed=DEFAULT_SEED):
        """:param seed: 初始种子（任意整数，内部取模 2^64）。"""
        self.seed = int(seed) % _M
        if self.seed == 0:
            # 全零种子会让 LCG 退化得很慢，用默认种子顶上
            self.seed = DEFAULT_SEED % _M
        self.calls = 0

    # ── 基础 ──

    def next_u32(self):
        """推进一步，返回 32 位无符号整数。"""
        self.seed = (self.seed * _A + _C) % _M
        self.calls += 1
        return (self.seed >> 32) & 0xFFFFFFFF

    def random(self):
        """返回 [0.0, 1.0) 的浮点数。"""
        return self.next_u32() / float(_U32)

    def uniform(self, lo, hi):
        """返回 [lo, hi) 的浮点数；lo >= hi 时直接返回 lo。"""
        lo = float(lo)
        hi = float(hi)
        if hi <= lo:
            return lo
        return lo + (hi - lo) * self.random()

    def randint(self, lo, hi):
        """返回闭区间 [lo, hi] 的整数；lo > hi 时返回 lo。"""
        lo = int(lo)
        hi = int(hi)
        if hi <= lo:
            return lo
        span = hi - lo + 1
        return lo + int(self.next_u32() % span)

    def chance(self, p):
        """以概率 p 返回 True。p <= 0 恒 False，p >= 1 恒 True（不消耗随机数）。"""
        p = float(p)
        if p <= 0.0:
            return False
        if p >= 1.0:
            return True
        return self.random() < p

    def choice(self, seq):
        """从序列中等概率取一项；空序列返回 None。

        ⚠️ 调用方必须先把 seq 排成**确定顺序**（例如按 id 升序），
        否则集合/字典的迭代顺序会破坏双端一致性。
        """
        items = list(seq)
        if not items:
            return None
        return items[self.randint(0, len(items) - 1)]

    def pick_range(self, pair, default_lo=0.0, default_hi=1.0):
        """从 balance 里的 ``[lo, hi]`` 二元组取一个均匀随机值。"""
        if isinstance(pair, (list, tuple)) and len(pair) >= 2:
            return self.uniform(pair[0], pair[1])
        return self.uniform(default_lo, default_hi)

    # ── 快照 ──

    def state(self):
        """导出当前种子（存档用）。"""
        return int(self.seed)

    def restore(self, seed):
        """恢复种子（读档用）。"""
        self.seed = int(seed) % _M
        if self.seed == 0:
            self.seed = DEFAULT_SEED % _M

    def clone(self):
        """复制一个同状态的独立随机源（供纯函数结算使用）。"""
        r = DetRandom(self.seed)
        r.calls = self.calls
        return r

    def __repr__(self):
        return "DetRandom(seed=%d, calls=%d)" % (self.seed, self.calls)
