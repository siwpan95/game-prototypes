// ═══════════════════════════════════════════════════════════════════════
//  data_defs.h —— 数据定义层（T05 子任务 5.7）
// ══════════════���════════════════════════════════════════════════════════
//
// ◆ 对偶：fishtank/data_defs.py
//     FishSpeciesDef  ↔ FishSpeciesDef
//     DecorDef        ↔ DecorDef
//     FishLibrary     ↔ FishLibrary
//     DecorLibrary    ↔ DecorLibrary
//     BalanceTable    ↔ BalanceTable
//
// 🔴 零硬编码玩法数值：所有数值都经 BalanceTable 从 data/balance.json 读。
//    函数签名里出现的默认值是**数据文件损坏时的救生圈**（对偶 Python 的
//    `_FALLBACK` 常量 + `bal.get(path, default)` 的 default 实参），
//    正常运行路径上一个都不会被取到。
//
// 🔴 排序契约：FishLibrary / DecorLibrary 内部按 id **升序**存储。
//    Python 端到处用 `sorted(...)`，C++ 端靠"存的时候就有序"来等价实现，
//    保证 by_group / groups / 遍历顺序双端逐项一致（浮点求和顺序敏感）。
//
// 🔴 静态解析、运行期零 IO：启动时一次性把 data/*.json 解析进定长结构体数组。

#ifndef FT_CORE_DATA_DEFS_H
#define FT_CORE_DATA_DEFS_H

#include "ft_types.h"
#include "json_min.h"

namespace ft {

// ── 稀有度 / 阶段常量（对偶 fishtank/constants.py，只放字符串枚举）──
extern const char* const kRarities[5];   // R1..R5
extern const char* const kStages[4];     // fry / juvenile / adult / mature

extern const char* const kStageFry;
extern const char* const kStageJuvenile;
extern const char* const kStageAdult;
extern const char* const kStageMature;

// ══════════════════════════════════════════════════════════════
//  鱼种定义（对应 fish_data.json 的一项）
// ══════════════════════════════════════════════════════════════

struct FishSpeciesDef {
    char id[FT_ID_LEN];
    char name_zh[FT_NAME_LEN];
    char rarity[8];
    char group[FT_ID_LEN];

    // shape 段（fish_painter 契约输入）
    f64  shape_length;
    f64  shape_height_ratio;
    char shape_tail[8];        // fan / fork / round / long

    // color 段，0xRRGGBB
    u32  color_body;
    u32  color_belly;
    u32  color_fin;
    u32  color_pattern;

    // behavior 段
    char speed[8];             // slow / normal / fast

    void clear();
};

// ══════════════════════════════════════════════════════════════
//  装饰定义（对应 decor_data.json 的一项）
// ══════════════════════════════════════════════════════════════

struct DecorDef {
    char id[FT_ID_LEN];
    char name[FT_NAME_LEN];
    f64  bonus;
    i32  price;
    char draw[FT_ID_LEN];
    u32  color0;
    u32  color1;
    char anchor[8];

    void clear();
};

// ══════════════════════════════════════════════════════════════
//  鱼种库
// ══════════════════════════════════════════════════════════════

class FishLibrary {
public:
    FishLibrary();

    /// 从已解析的 JSON 数组根节点装载。重复调用会先清空。
    /// :returns: 装入的鱼种数
    i32 load(const JsonDoc& doc, i32 array_root);

    i32 count() const { return n_; }
    /// 按下标取（**按 id 升序**）。
    const FishSpeciesDef& at(i32 i) const;
    /// 按 id 查；不存在返回 NULL。对偶 DataLibrary.get()。
    const FishSpeciesDef* get(const char* id) const;

    /// 族群数（**按名称升序**）。对偶 FishLibrary.groups()。
    i32 group_count() const { return n_groups_; }
    const char* group_at(i32 i) const;

    /// 某族群的成员数。对偶 group_members(g) 的 len。
    i32 group_member_count(const char* group) const;
    /// 某族群第 k 个成员（**id 升序**）。对偶 by_group(g)[k]。
    const FishSpeciesDef* group_member_at(const char* group, i32 k) const;

private:
    void rebuild_groups();

    FishSpeciesDef items_[FT_MAX_SPECIES];
    i32 n_;
    char groups_[FT_MAX_GROUP][FT_ID_LEN];
    i32 n_groups_;
};

// ══════════════════════════════════════════════════════════════
//  装饰库
// ══════════════════════════════════════════════════════════════

class DecorLibrary {
public:
    DecorLibrary();

    i32 load(const JsonDoc& doc, i32 array_root);

    i32 count() const { return n_; }
    const DecorDef& at(i32 i) const;
    const DecorDef* get(const char* id) const;

    /// 查某装饰的加成；未知 id 返回 0.0。对偶 DecorLibrary.bonus_of()。
    f64 bonus_of(const char* id) const;

private:
    DecorDef items_[FT_MAX_DECOR_DEF];
    i32 n_;
};

// ══════════════════════════════════════════════════════════════
//  平衡表
// ══════════════════════════════════════════════════════════════

/// balance.json 的点号路径访问器。对偶 data_defs.py::BalanceTable。
/// 所有取值都带兜底，路径缺失绝不崩溃（准则：数据问题不崩）。
class BalanceTable {
public:
    BalanceTable();

    /// 绑定已解析的 balance.json 根节点。
    void bind(const JsonDoc* doc, i32 root);
    bool bound() const { return doc_ != FT_NULL; }

    // ── 通用取值 ──
    f64  num(const char* path, f64 fallback) const;
    i64  intv(const char* path, i64 fallback) const;
    const char* text(const char* path, const char* fallback) const;
    /// 取子节点下标（用于 offline.segments 这类结构化数据）。
    i32  node(const char* path) const;
    const JsonDoc* doc() const { return doc_; }

    /// 拼 "prefix.key" 后再取数（避免调用方到处手拼字符串）。
    f64  num2(const char* prefix, const char* key, f64 fallback) const;
    i64  intv2(const char* prefix, const char* key, i64 fallback) const;

    // ── 快捷访问（逐个对偶 Python 的同名方法）──
    f64 base_income(const char* rarity) const;      // economy.base_income.<R>
    i64 growth_cycle_sec(const char* rarity) const; // growth.cycle_sec.<R>
    f64 threshold(const char* stage) const;         // growth.thresholds.<stage>
    f64 stage_coef(const char* stage) const;        // growth.stage_coef.<stage>
    f64 stage_scale(const char* stage) const;       // growth.stage_scale.<stage>
    i32 coin_scale() const;                         // economy.coin_scale
    f64 bonus_cap() const;                          // economy.bonus_cap
    f64 water_min() const;                          // water.min
    f64 water_max() const;                          // water.max
    f64 quality_floor() const;                      // water.quality_floor
    f64 filter_gain(i32 level) const;               // water.filter_gain[level]
    i32 capacity_of(i32 level) const;               // shop.capacity[level]
    f64 group_bonus() const;                        // codex.group_bonus
    i64 hard_cap_sec() const;                       // offline.hard_cap_sec
    i32 offline_segment_count() const;              // len(offline.segments)
    /// 取第 i 段：lo（分钟）、hi（分钟，无穷时 has_hi=false）、k。
    void offline_segment(i32 i, f64* lo, f64* hi, bool* has_hi, f64* k) const;

private:
    const JsonDoc* doc_;
    i32 root_;
};

// ── 稀有度 / 阶段序号工具（对偶 economy.py 的同名函数）──

/// R1..R5 → 0..4；未知返回 0。对偶 economy.py::rarity_index。
i32 rarity_index(const char* rarity);
/// 0..4 → "R1".."R5"；越界钳到端点。对偶 economy.py::rarity_at。
const char* rarity_at(i32 index);
/// 阶段名 → 序号（fry=0 … mature=3）；未知返回 0。对偶 economy.py::stage_index。
i32 stage_index(const char* stage);

}  // namespace ft

#endif  // FT_CORE_DATA_DEFS_H
