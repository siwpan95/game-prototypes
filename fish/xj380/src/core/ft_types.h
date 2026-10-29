// ═══════════════════════════════════════════════════════════════════════
//  ft_types.h —— 纯逻辑层的基础类型（零 include）
// ═══════════════════════════════════════════════════════════════════════
//
// 🔴 本文件以及整个 core/ 目录**不允许 #include 任何系统头**。
//    原因：XJ380 端编译标志是 `-ffreestanding -fno-builtin -nostdinc`，
//    标准库不可用；而 golden_runner 又要用宿主 clang++/g++ 编译同一批 .cpp。
//    只有"零系统依赖的 C++ 子集"才能同时满足两边。
//
// 约束清单（core/ 全体遵守）：
//    * 不用 STL 容器 / 不用 std::string / 不用 iostream
//    * 不用异常（-fno-exceptions）、不用 RTTI（-fno-rtti）
//    * 不用 new / delete / malloc —— 一律定长数组或调用方提供缓冲区
//    * 不用 <cmath>：floor / sqrt / sin 自己实现（见 ft_math.h）
//
// 对偶关系：Python 端无此文件（Python 自带这些）；这是 C++ 侧的补齐层。

#ifndef FT_CORE_FT_TYPES_H
#define FT_CORE_FT_TYPES_H

namespace ft {

typedef signed char        i8;
typedef unsigned char      u8;
typedef short              i16;
typedef unsigned short     u16;
typedef int                i32;
typedef unsigned int       u32;
typedef long long          i64;
typedef unsigned long long u64;
typedef double             f64;

// ── 编译期宽度自检（C++98 兼容写法：负长度数组即编译失败）──
namespace detail {
typedef char ft_check_u8 [(sizeof(u8)  == 1) ? 1 : -1];
typedef char ft_check_u16[(sizeof(u16) == 2) ? 1 : -1];
typedef char ft_check_u32[(sizeof(u32) == 4) ? 1 : -1];
typedef char ft_check_u64[(sizeof(u64) == 8) ? 1 : -1];
typedef char ft_check_f64[(sizeof(f64) == 8) ? 1 : -1];
}  // namespace detail

}  // namespace ft

// 不引 <cstddef>，自己给一个空指针常量
#define FT_NULL 0

// 字符串字段的统一上限（鱼种 id / 装饰 id / 族群名，均为短 UTF-8）
#define FT_ID_LEN     40
#define FT_NAME_LEN   48

// 定长实体表上限（ARCHITECTURE §11 第 17 条：禁用 STL，用定长数组）
#define FT_MAX_FISH        64   // shop.capacity 最大 36，留足冗余
#define FT_MAX_DECOR_SLOT  16   // 缸内装饰槽位
#define FT_MAX_CODEX       64   // 图鉴条目
#define FT_MAX_STATS       16   // 统计计数器
#define FT_MAX_SPECIES     64   // fish_data.json 鱼种数（当前 24）
#define FT_MAX_DECOR_DEF   32   // decor_data.json 装饰数（当前 12）
#define FT_MAX_GROUP       16   // 族群数（当前 3）

#endif  // FT_CORE_FT_TYPES_H
