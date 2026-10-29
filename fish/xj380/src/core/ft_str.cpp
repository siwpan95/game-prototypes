// ft_str.cpp —— 见 ft_str.h。零系统 include。

#include "ft_str.h"

#include "ft_math.h"

namespace ft {

i32 str_len(const char* s) {
    if (s == FT_NULL) {
        return 0;
    }
    i32 n = 0;
    while (s[n] != '\0') {
        ++n;
    }
    return n;
}

bool str_eq(const char* a, const char* b) {
    return str_cmp(a, b) == 0;
}

i32 str_cmp(const char* a, const char* b) {
    const char* pa = (a == FT_NULL) ? "" : a;
    const char* pb = (b == FT_NULL) ? "" : b;
    i32 i = 0;
    for (;; ++i) {
        u8 ca = static_cast<u8>(pa[i]);
        u8 cb = static_cast<u8>(pb[i]);
        if (ca != cb) {
            return (ca < cb) ? -1 : 1;
        }
        if (ca == 0) {
            return 0;
        }
    }
}

i32 str_copy(char* dst, i32 cap, const char* src) {
    if (dst == FT_NULL || cap <= 0) {
        return 0;
    }
    if (src == FT_NULL) {
        dst[0] = '\0';
        return 0;
    }
    i32 i = 0;
    while (i < cap - 1 && src[i] != '\0') {
        dst[i] = src[i];
        ++i;
    }
    dst[i] = '\0';
    return i;
}

i32 str_append(char* dst, i32 cap, const char* src) {
    if (dst == FT_NULL || cap <= 0) {
        return 0;
    }
    i32 n = str_len(dst);
    if (src == FT_NULL) {
        return n;
    }
    i32 i = 0;
    while (n < cap - 1 && src[i] != '\0') {
        dst[n++] = src[i++];
    }
    dst[n] = '\0';
    return n;
}

void mem_copy(void* dst, const void* src, i32 n) {
    u8* d = static_cast<u8*>(dst);
    const u8* s = static_cast<const u8*>(src);
    for (i32 i = 0; i < n; ++i) {
        d[i] = s[i];
    }
}

void mem_zero(void* dst, i32 n) {
    u8* d = static_cast<u8*>(dst);
    for (i32 i = 0; i < n; ++i) {
        d[i] = 0;
    }
}

i32 fmt_u64(char* dst, i32 cap, u64 v) {
    if (dst == FT_NULL || cap <= 1) {
        if (dst != FT_NULL && cap > 0) {
            dst[0] = '\0';
        }
        return 0;
    }
    char tmp[24];
    i32 n = 0;
    if (v == 0) {
        tmp[n++] = '0';
    }
    while (v > 0 && n < 24) {
        tmp[n++] = static_cast<char>('0' + static_cast<i32>(v % 10ULL));
        v /= 10ULL;
    }
    i32 out = 0;
    while (n > 0 && out < cap - 1) {
        dst[out++] = tmp[--n];
    }
    dst[out] = '\0';
    return out;
}

i32 fmt_i64(char* dst, i32 cap, i64 v) {
    if (dst == FT_NULL || cap <= 1) {
        if (dst != FT_NULL && cap > 0) {
            dst[0] = '\0';
        }
        return 0;
    }
    if (v >= 0) {
        return fmt_u64(dst, cap, static_cast<u64>(v));
    }
    dst[0] = '-';
    // 取负数绝对值时先转 u64 再取补，避免 LLONG_MIN 溢出。
    u64 mag = static_cast<u64>(-(v + 1)) + 1ULL;
    i32 n = fmt_u64(dst + 1, cap - 1, mag);
    return n + 1;
}

i32 fmt_fixed(char* dst, i32 cap, f64 v, i32 decimals) {
    if (dst == FT_NULL || cap <= 1) {
        if (dst != FT_NULL && cap > 0) {
            dst[0] = '\0';
        }
        return 0;
    }
    if (decimals < 0) {
        decimals = 0;
    }
    if (decimals > 9) {
        decimals = 9;
    }
    bool neg = v < 0.0;
    f64 a = neg ? -v : v;
    f64 scale = pow10_(decimals);
    // 显示用途，允许 half-up
    u64 scaled = static_cast<u64>(round_half_up(a * scale));
    u64 ip = scaled / static_cast<u64>(scale);
    u64 fp = scaled - ip * static_cast<u64>(scale);

    i32 n = 0;
    if (neg && (ip != 0 || fp != 0)) {
        dst[n++] = '-';
        dst[n] = '\0';
    } else {
        dst[0] = '\0';
    }
    char buf[24];
    fmt_u64(buf, 24, ip);
    n = str_append(dst, cap, buf);
    if (decimals > 0) {
        n = str_append(dst, cap, ".");
        // 前导零补齐
        fmt_u64(buf, 24, fp);
        i32 flen = str_len(buf);
        for (i32 i = flen; i < decimals && n < cap - 1; ++i) {
            n = str_append(dst, cap, "0");
        }
        n = str_append(dst, cap, buf);
    }
    return n;
}

}  // namespace ft
