// ═══════════════════════════════════════════════════════════════════════
//  json_min.h —— 极简 JSON 解析器（T05 子任务 5.5）
// ═══════════════════════════════════════════════════════════════════════
//
// ◆ 对偶：Python 端的 `json.load()`（标准库）
//
// 设计取舍（ARCHITECTURE §8.4 + X7）：
//   * **不用** SDK 的 `algorithm/json.h` —— 它是 4 层相对路径的转发壳，易碎。
//   * 原地解析（in-place）：字符串直接在源缓冲区里反转义 + NUL 结尾，
//     零拷贝、零分配。因此源缓冲区必须在 JsonDoc 存活期间保持有效且可写。
//   * 节点池由调用方提供（XJ 端静态数组 / 宿主端静态数组），不 malloc。
//
// 🔴 整数精度关键点
//    存档里的 `rng_seed` 可以取到 11473018220155547240 —— 既超过 i64 上限，
//    也远超 double 的 2^53 精确整数范围。若按 double 解析会**静默丢精度**，
//    双端 RNG 立刻错位。因此本解析器对不含 `.`/`e` 的 token 一律走
//    u64 精确路径（umag + neg），只在需要浮点时才转 double。
//
// 🔴 浮点精度关键点
//    尾数 <= 2^53 且十进制指数 |exp| <= 22 时，`mant * 10^exp` 单次乘/除即为
//    正确舍入结果（10^0..10^22 在 double 里精确），与 CPython 的 strtod 逐位相同。
//    data/*.json 里的全部数值（0.03 / 1.45 / 0.012 / 315360000 …）都落在此范围。

#ifndef FT_CORE_JSON_MIN_H
#define FT_CORE_JSON_MIN_H

#include "ft_types.h"

namespace ft {

enum JsonType {
    JSON_NONE = 0,
    JSON_NULL = 1,
    JSON_BOOL = 2,
    JSON_NUM  = 3,
    JSON_STR  = 4,
    JSON_ARR  = 5,
    JSON_OBJ  = 6
};

/// 一个 JSON 节点。对象成员通过 `key` 携带键名，兄弟节点用 `next` 串成链表。
struct JsonNode {
    u8  type;      ///< JsonType
    u8  bval;      ///< JSON_BOOL 的值
    u8  is_int;    ///< JSON_NUM：token 中无 '.'/'e'，umag/neg 为精确值
    u8  neg;       ///< JSON_NUM：是否带负号
    i32 first;     ///< 首个子节点下标，无子节点为 -1
    i32 next;      ///< 下一个兄弟下标，无则 -1
    i32 count;     ///< 子节点个数
    const char* key;  ///< 对象成员键名（数组元素 / 根节点为 NULL）
    const char* str;  ///< JSON_STR 的值
    f64 num;       ///< JSON_NUM 的双精度值
    u64 umag;      ///< JSON_NUM 且 is_int 时的精确幅值
};

/// JSON 文档。持有节点池引用与原地解析后的文本缓冲。
class JsonDoc {
public:
    JsonDoc();

    /// 绑定调用方提供的节点池。必须在 parse 之前调用。
    void init(JsonNode* pool, i32 capacity);

    /// 原地解析。`text` 必须可写且在 JsonDoc 使用期间保持有效。
    /// :returns: 成功返回 true；失败返回 false 并可用 error() 查看原因。
    bool parse(char* text, i32 length);

    bool ok() const { return err_ == FT_NULL; }
    const char* error() const { return err_ == FT_NULL ? "" : err_; }
    i32 error_pos() const { return err_pos_; }
    i32 node_used() const { return used_; }

    /// 根节点下标；未解析成功返回 -1。
    i32 root() const { return root_; }

    /// 取节点（下标非法时返回一个静态的 JSON_NONE 节点，绝不越界）。
    const JsonNode& at(i32 idx) const;

    // ── 导航 ──

    /// 取对象成员下标；不是对象 / 键不存在返回 -1。
    i32 member(i32 obj, const char* key) const;

    /// 取数组元素下标（也可用于遍历对象成员）；越界返回 -1。
    i32 elem(i32 arr, i32 index) const;

    /// 点号路径查找，对偶 data_defs.py::BalanceTable._dig。
    /// 数字段用于数组下标，例如 "water.filter_gain.2"。
    i32 path(i32 start, const char* dotted) const;

    /// 子节点个数（非容器返回 0）。
    i32 count(i32 idx) const;

    // ── 取值（带兜底，绝不抛异常）──

    f64  num_at(i32 idx, f64 fallback) const;
    i64  int_at(i32 idx, i64 fallback) const;
    u64  uint_at(i32 idx, u64 fallback) const;
    bool bool_at(i32 idx, bool fallback) const;
    const char* str_at(i32 idx, const char* fallback) const;

    /// 节点是否存在且不是 null。
    bool present(i32 idx) const;

private:
    i32  alloc_node();
    void skip_ws();
    bool parse_value(i32* out);
    bool parse_object(i32 node);
    bool parse_array(i32 node);
    bool parse_string(const char** out);
    bool parse_number(i32 node);
    bool parse_literal(i32 node);
    bool fail(const char* msg);

    JsonNode* pool_;
    i32 cap_;
    i32 used_;
    char* text_;
    i32 len_;
    i32 pos_;
    i32 root_;
    const char* err_;
    i32 err_pos_;
};

}  // namespace ft

#endif  // FT_CORE_JSON_MIN_H
