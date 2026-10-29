// json_min.cpp —— 见 json_min.h。零系统 include。

#include "json_min.h"

#include "ft_math.h"
#include "ft_str.h"

namespace ft {

namespace {

JsonNode g_none_node = {
    JSON_NONE, 0, 0, 0, -1, -1, 0, FT_NULL, FT_NULL, 0.0, 0ULL
};

inline bool is_ws(char c) {
    return c == ' ' || c == '\t' || c == '\n' || c == '\r';
}

inline bool is_digit(char c) {
    return c >= '0' && c <= '9';
}

inline i32 hex_val(char c) {
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return -1;
}

/// 把码点写成 UTF-8，返回写入字节数（1~4）。
i32 encode_utf8(u32 cp, char* out) {
    if (cp < 0x80U) {
        out[0] = static_cast<char>(cp);
        return 1;
    }
    if (cp < 0x800U) {
        out[0] = static_cast<char>(0xC0U | (cp >> 6));
        out[1] = static_cast<char>(0x80U | (cp & 0x3FU));
        return 2;
    }
    if (cp < 0x10000U) {
        out[0] = static_cast<char>(0xE0U | (cp >> 12));
        out[1] = static_cast<char>(0x80U | ((cp >> 6) & 0x3FU));
        out[2] = static_cast<char>(0x80U | (cp & 0x3FU));
        return 3;
    }
    out[0] = static_cast<char>(0xF0U | (cp >> 18));
    out[1] = static_cast<char>(0x80U | ((cp >> 12) & 0x3FU));
    out[2] = static_cast<char>(0x80U | ((cp >> 6) & 0x3FU));
    out[3] = static_cast<char>(0x80U | (cp & 0x3FU));
    return 4;
}

}  // namespace

// ══════════════════════════════════════════════════════════════
//  生命周期
// ══════════════════════════════════════════════════════════════

JsonDoc::JsonDoc()
    : pool_(FT_NULL), cap_(0), used_(0), text_(FT_NULL), len_(0),
      pos_(0), root_(-1), err_(FT_NULL), err_pos_(0) {}

void JsonDoc::init(JsonNode* pool, i32 capacity) {
    pool_ = pool;
    cap_ = capacity;
    used_ = 0;
    root_ = -1;
    err_ = FT_NULL;
    err_pos_ = 0;
}

bool JsonDoc::fail(const char* msg) {
    if (err_ == FT_NULL) {
        err_ = msg;
        err_pos_ = pos_;
    }
    return false;
}

i32 JsonDoc::alloc_node() {
    if (pool_ == FT_NULL || used_ >= cap_) {
        fail("节点池耗尽：请增大 JsonNode 池容量");
        return -1;
    }
    i32 idx = used_++;
    JsonNode& n = pool_[idx];
    n.type = JSON_NONE;
    n.bval = 0;
    n.is_int = 0;
    n.neg = 0;
    n.first = -1;
    n.next = -1;
    n.count = 0;
    n.key = FT_NULL;
    n.str = FT_NULL;
    n.num = 0.0;
    n.umag = 0ULL;
    return idx;
}

bool JsonDoc::parse(char* text, i32 length) {
    text_ = text;
    len_ = length;
    pos_ = 0;
    used_ = 0;
    root_ = -1;
    err_ = FT_NULL;
    err_pos_ = 0;
    if (text_ == FT_NULL || len_ <= 0) {
        return fail("空输入");
    }
    // 跳过 UTF-8 BOM
    if (len_ >= 3 &&
        static_cast<u8>(text_[0]) == 0xEF &&
        static_cast<u8>(text_[1]) == 0xBB &&
        static_cast<u8>(text_[2]) == 0xBF) {
        pos_ = 3;
    }
    i32 r = -1;
    if (!parse_value(&r)) {
        return false;
    }
    root_ = r;
    skip_ws();
    if (pos_ < len_ && text_[pos_] != '\0') {
        return fail("根值之后存在多余内容");
    }
    return true;
}

// ══════════════════════════════════════════════════════════════
//  扫描
// ══════════════════════════════════════════════════════════════

void JsonDoc::skip_ws() {
    while (pos_ < len_ && is_ws(text_[pos_])) {
        ++pos_;
    }
}

bool JsonDoc::parse_value(i32* out) {
    skip_ws();
    if (pos_ >= len_) {
        return fail("意外的输入结尾");
    }
    i32 idx = alloc_node();
    if (idx < 0) {
        return false;
    }
    *out = idx;
    char c = text_[pos_];
    if (c == '{') {
        return parse_object(idx);
    }
    if (c == '[') {
        return parse_array(idx);
    }
    if (c == '"') {
        const char* s = FT_NULL;
        if (!parse_string(&s)) {
            return false;
        }
        pool_[idx].type = JSON_STR;
        pool_[idx].str = s;
        return true;
    }
    if (c == '-' || is_digit(c)) {
        return parse_number(idx);
    }
    return parse_literal(idx);
}

bool JsonDoc::parse_object(i32 node) {
    pool_[node].type = JSON_OBJ;
    ++pos_;  // 吃掉 '{'
    skip_ws();
    if (pos_ < len_ && text_[pos_] == '}') {
        ++pos_;
        return true;
    }
    i32 prev = -1;
    for (;;) {
        skip_ws();
        if (pos_ >= len_ || text_[pos_] != '"') {
            return fail("对象成员名必须是字符串");
        }
        const char* key = FT_NULL;
        if (!parse_string(&key)) {
            return false;
        }
        skip_ws();
        if (pos_ >= len_ || text_[pos_] != ':') {
            return fail("对象成员缺少冒号");
        }
        ++pos_;
        i32 child = -1;
        if (!parse_value(&child)) {
            return false;
        }
        pool_[child].key = key;
        if (prev < 0) {
            pool_[node].first = child;
        } else {
            pool_[prev].next = child;
        }
        prev = child;
        ++pool_[node].count;

        skip_ws();
        if (pos_ >= len_) {
            return fail("对象未闭合");
        }
        if (text_[pos_] == ',') {
            ++pos_;
            continue;
        }
        if (text_[pos_] == '}') {
            ++pos_;
            return true;
        }
        return fail("对象成员之间需要逗号");
    }
}

bool JsonDoc::parse_array(i32 node) {
    pool_[node].type = JSON_ARR;
    ++pos_;  // 吃掉 '['
    skip_ws();
    if (pos_ < len_ && text_[pos_] == ']') {
        ++pos_;
        return true;
    }
    i32 prev = -1;
    for (;;) {
        i32 child = -1;
        if (!parse_value(&child)) {
            return false;
        }
        if (prev < 0) {
            pool_[node].first = child;
        } else {
            pool_[prev].next = child;
        }
        prev = child;
        ++pool_[node].count;

        skip_ws();
        if (pos_ >= len_) {
            return fail("数组未闭合");
        }
        if (text_[pos_] == ',') {
            ++pos_;
            continue;
        }
        if (text_[pos_] == ']') {
            ++pos_;
            return true;
        }
        return fail("数组元素之间需要逗号");
    }
}

bool JsonDoc::parse_string(const char** out) {
    // 原地反转义：读指针 rp 走原文，写指针 wp 回填同一缓冲区。
    // 反转义结果长度恒 <= 原文长度，所以永远不会越写。
    ++pos_;  // 吃掉开头的 '"'
    i32 wp = pos_;
    *out = text_ + wp;
    while (pos_ < len_) {
        char c = text_[pos_];
        if (c == '"') {
            ++pos_;
            text_[wp] = '\0';
            return true;
        }
        if (c != '\\') {
            text_[wp++] = c;
            ++pos_;
            continue;
        }
        // 转义序列
        ++pos_;
        if (pos_ >= len_) {
            return fail("字符串以反斜杠结尾");
        }
        char e = text_[pos_++];
        switch (e) {
            case '"':  text_[wp++] = '"';  break;
            case '\\': text_[wp++] = '\\'; break;
            case '/':  text_[wp++] = '/';  break;
            case 'b':  text_[wp++] = '\b'; break;
            case 'f':  text_[wp++] = '\f'; break;
            case 'n':  text_[wp++] = '\n'; break;
            case 'r':  text_[wp++] = '\r'; break;
            case 't':  text_[wp++] = '\t'; break;
            case 'u': {
                if (pos_ + 4 > len_) {
                    return fail("\\u 转义长度不足");
                }
                u32 cp = 0;
                for (i32 k = 0; k < 4; ++k) {
                    i32 h = hex_val(text_[pos_ + k]);
                    if (h < 0) {
                        return fail("\\u 转义包含非十六进制字符");
                    }
                    cp = (cp << 4) | static_cast<u32>(h);
                }
                pos_ += 4;
                // 代理对
                if (cp >= 0xD800U && cp <= 0xDBFFU &&
                    pos_ + 6 <= len_ && text_[pos_] == '\\' && text_[pos_ + 1] == 'u') {
                    u32 lo = 0;
                    bool okpair = true;
                    for (i32 k = 0; k < 4; ++k) {
                        i32 h = hex_val(text_[pos_ + 2 + k]);
                        if (h < 0) { okpair = false; break; }
                        lo = (lo << 4) | static_cast<u32>(h);
                    }
                    if (okpair && lo >= 0xDC00U && lo <= 0xDFFFU) {
                        cp = 0x10000U + ((cp - 0xD800U) << 10) + (lo - 0xDC00U);
                        pos_ += 6;
                    }
                }
                wp += encode_utf8(cp, text_ + wp);
                break;
            }
            default:
                return fail("未知的转义字符");
        }
    }
    return fail("字符串未闭合");
}

bool JsonDoc::parse_number(i32 node) {
    JsonNode& n = pool_[node];
    n.type = JSON_NUM;

    i32 start = pos_;
    bool neg = false;
    if (text_[pos_] == '-') {
        neg = true;
        ++pos_;
    }
    // 整数部分
    u64 mant = 0ULL;
    i32 digits = 0;        // 已吸收进 mant 的有效数字个数
    i32 dropped = 0;       // 因超出 19 位而丢弃的整数位数
    bool any = false;
    while (pos_ < len_ && is_digit(text_[pos_])) {
        any = true;
        // 兼容 20 位 u64：MAX_U64 = 18446744073709551615
        if (digits < 19 || (digits == 19 && mant <= 1844674407370955161ULL)) {
            mant = mant * 10ULL + static_cast<u64>(text_[pos_] - '0');
            ++digits;
        } else {
            ++dropped;
        }
        ++pos_;
    }
    if (!any) {
        return fail("数字缺少整数部分");
    }

    bool is_float = false;
    i32 frac_digits = 0;
    if (pos_ < len_ && text_[pos_] == '.') {
        is_float = true;
        ++pos_;
        while (pos_ < len_ && is_digit(text_[pos_])) {
            if (digits < 19 || (digits == 19 && mant <= 1844674407370955161ULL)) {
                mant = mant * 10ULL + static_cast<u64>(text_[pos_] - '0');
                ++digits;
                ++frac_digits;
            }
            ++pos_;
        }
    }
    i32 exp10 = 0;
    if (pos_ < len_ && (text_[pos_] == 'e' || text_[pos_] == 'E')) {
        is_float = true;
        ++pos_;
        bool eneg = false;
        if (pos_ < len_ && (text_[pos_] == '+' || text_[pos_] == '-')) {
            eneg = (text_[pos_] == '-');
            ++pos_;
        }
        i32 ev = 0;
        while (pos_ < len_ && is_digit(text_[pos_])) {
            if (ev < 100000) {
                ev = ev * 10 + (text_[pos_] - '0');
            }
            ++pos_;
        }
        exp10 = eneg ? -ev : ev;
    }
    (void)start;

    n.neg = neg ? 1 : 0;
    if (!is_float) {
        // ★ 精确整数路径：rng_seed 这类 > 2^53 的值必须走这里
        n.is_int = 1;
        n.umag = mant;
        // 同时给出 double 近似，供需要浮点的调用方使用
        f64 v = static_cast<f64>(mant);
        for (i32 i = 0; i < dropped; ++i) {
            v *= 10.0;
        }
        n.num = neg ? -v : v;
        return true;
    }

    n.is_int = 0;
    n.umag = mant;
    i32 e = exp10 - frac_digits + dropped;
    f64 val;
    // 快路径：尾数精确可表示且 10^|e| 精确 → 单次乘/除即正确舍入（同 strtod）
    if (mant <= 9007199254740992ULL && e >= -22 && e <= 22) {
        f64 m = static_cast<f64>(mant);
        if (e >= 0) {
            val = m * pow10_(e);
        } else {
            val = m / pow10_(-e);
        }
    } else {
        val = static_cast<f64>(mant) * pow10_(e);
    }
    n.num = neg ? -val : val;
    return true;
}

bool JsonDoc::parse_literal(i32 node) {
    JsonNode& n = pool_[node];
    if (pos_ + 4 <= len_ &&
        text_[pos_] == 't' && text_[pos_ + 1] == 'r' &&
        text_[pos_ + 2] == 'u' && text_[pos_ + 3] == 'e') {
        pos_ += 4;
        n.type = JSON_BOOL;
        n.bval = 1;
        return true;
    }
    if (pos_ + 5 <= len_ &&
        text_[pos_] == 'f' && text_[pos_ + 1] == 'a' && text_[pos_ + 2] == 'l' &&
        text_[pos_ + 3] == 's' && text_[pos_ + 4] == 'e') {
        pos_ += 5;
        n.type = JSON_BOOL;
        n.bval = 0;
        return true;
    }
    if (pos_ + 4 <= len_ &&
        text_[pos_] == 'n' && text_[pos_ + 1] == 'u' &&
        text_[pos_ + 2] == 'l' && text_[pos_ + 3] == 'l') {
        pos_ += 4;
        n.type = JSON_NULL;
        return true;
    }
    return fail("无法识别的字面量");
}

// ══════════════════════════════════════════════════════════════
//  访问
// ══════════════════════════════════════════════════════════════

const JsonNode& JsonDoc::at(i32 idx) const {
    if (pool_ == FT_NULL || idx < 0 || idx >= used_) {
        return g_none_node;
    }
    return pool_[idx];
}

i32 JsonDoc::member(i32 obj, const char* key) const {
    const JsonNode& n = at(obj);
    if (n.type != JSON_OBJ) {
        return -1;
    }
    for (i32 c = n.first; c >= 0; c = at(c).next) {
        if (str_eq(at(c).key, key)) {
            return c;
        }
    }
    return -1;
}

i32 JsonDoc::elem(i32 arr, i32 index) const {
    const JsonNode& n = at(arr);
    if (n.type != JSON_ARR && n.type != JSON_OBJ) {
        return -1;
    }
    if (index < 0) {
        return -1;
    }
    i32 i = 0;
    for (i32 c = n.first; c >= 0; c = at(c).next, ++i) {
        if (i == index) {
            return c;
        }
    }
    return -1;
}

i32 JsonDoc::path(i32 start, const char* dotted) const {
    // 对偶 data_defs.py::BalanceTable._dig：
    //   dict → 按键取；list → 把段当成整数下标；其它 → 视为不存在。
    if (dotted == FT_NULL) {
        return -1;
    }
    i32 cur = start;
    i32 i = 0;
    char seg[64];
    while (dotted[i] != '\0') {
        i32 s = 0;
        while (dotted[i] != '\0' && dotted[i] != '.' && s < 63) {
            seg[s++] = dotted[i++];
        }
        seg[s] = '\0';
        // 跳过分隔点
        while (dotted[i] != '\0' && dotted[i] != '.') {
            ++i;
        }
        if (dotted[i] == '.') {
            ++i;
        }
        const JsonNode& n = at(cur);
        if (n.type == JSON_OBJ) {
            cur = member(cur, seg);
        } else if (n.type == JSON_ARR) {
            // 纯数字段才当下标
            i32 v = 0;
            bool numeric = (s > 0);
            for (i32 k = 0; k < s; ++k) {
                if (seg[k] < '0' || seg[k] > '9') {
                    numeric = false;
                    break;
                }
                v = v * 10 + (seg[k] - '0');
            }
            cur = numeric ? elem(cur, v) : -1;
        } else {
            return -1;
        }
        if (cur < 0) {
            return -1;
        }
    }
    return cur;
}

i32 JsonDoc::count(i32 idx) const {
    return at(idx).count;
}

bool JsonDoc::present(i32 idx) const {
    const JsonNode& n = at(idx);
    return n.type != JSON_NONE && n.type != JSON_NULL;
}

f64 JsonDoc::num_at(i32 idx, f64 fallback) const {
    const JsonNode& n = at(idx);
    if (n.type == JSON_NUM) {
        return n.num;
    }
    if (n.type == JSON_BOOL) {
        return n.bval ? 1.0 : 0.0;
    }
    return fallback;
}

i64 JsonDoc::int_at(i32 idx, i64 fallback) const {
    const JsonNode& n = at(idx);
    if (n.type == JSON_NUM) {
        if (n.is_int) {
            i64 v = static_cast<i64>(n.umag);
            return n.neg ? -v : v;
        }
        // 浮点转整：对偶 Python 的 int()，向零截断
        f64 x = n.num;
        return static_cast<i64>(x);
    }
    if (n.type == JSON_BOOL) {
        return n.bval ? 1 : 0;
    }
    return fallback;
}

u64 JsonDoc::uint_at(i32 idx, u64 fallback) const {
    const JsonNode& n = at(idx);
    if (n.type == JSON_NUM && n.is_int) {
        if (n.neg) {
            // 负数按 2^64 取模，对偶 Python 的 `int(seed) % 2**64`
            return 0ULL - n.umag;
        }
        return n.umag;
    }
    if (n.type == JSON_NUM) {
        return static_cast<u64>(n.num);
    }
    return fallback;
}

bool JsonDoc::bool_at(i32 idx, bool fallback) const {
    const JsonNode& n = at(idx);
    if (n.type == JSON_BOOL) {
        return n.bval != 0;
    }
    if (n.type == JSON_NUM) {
        return n.num != 0.0;
    }
    return fallback;
}

const char* JsonDoc::str_at(i32 idx, const char* fallback) const {
    const JsonNode& n = at(idx);
    if (n.type == JSON_STR) {
        return n.str;
    }
    return fallback;
}

}  // namespace ft
