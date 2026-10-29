// ═══════════════════════════════════════════════════════════════════════
//  ft_str.h —— 自实现字符串工具（freestanding 无 <string.h>）
// ═══════════════════════════════════════════════════════════════════════
//
// 全部是定长、无分配、无异常的小工具。core/ 与 render/ 共用。
// Python 端对应的是内置 str 操作，无独立文件。

#ifndef FT_CORE_FT_STR_H
#define FT_CORE_FT_STR_H

#include "ft_types.h"

namespace ft {

/// 字符串长度；s 为 NULL 返回 0。
i32 str_len(const char* s);

/// 相等比较（NULL 视为空串）。
bool str_eq(const char* a, const char* b);

/// 字典序比较，返回 <0 / 0 / >0。用于"按 id 升序"排序。
i32 str_cmp(const char* a, const char* b);

/// 复制到定长缓冲并保证 NUL 结尾；返回实际写入长度。
i32 str_copy(char* dst, i32 cap, const char* src);

/// 追加到定长缓冲；返回追加后总长度。
i32 str_append(char* dst, i32 cap, const char* src);

/// 内存拷贝（不重叠）。
void mem_copy(void* dst, const void* src, i32 n);

/// 内存置零。
void mem_zero(void* dst, i32 n);

/// 有符号整数 → 十进制串；返回写入长度。
i32 fmt_i64(char* dst, i32 cap, i64 v);

/// 无符号 64 位整数 → 十进制串；返回写入长度。
/// (u64 超过 i64 上限时必需，例如 rng_seed = 11473018220155547240)
i32 fmt_u64(char* dst, i32 cap, u64 v);

/// 定点小数 → 串，保留 `decimals` 位（用于 HUD 显示，不参与结算）。
i32 fmt_fixed(char* dst, i32 cap, f64 v, i32 decimals);

}  // namespace ft

#endif  // FT_CORE_FT_STR_H
