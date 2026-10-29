// ═══════════════════════════════════════════════════════════════════════
//  state.h —— 游戏状态（T05 子任务 5.6）
// ═══════════════════════════════════════════════════════════════════════
//
// ◆ 对偶：fishtank/state.py
//     FishState  ↔ FishState
//     TankState  ↔ TankState
//     GameState  ↔ GameState
//     r6()       ↔ ft_math.h::r6()
//
// 🔴 定长化改写说明（唯一允许偏离 Python 的地方，且**不改变任何数值**）：
//    Python 用 list/dict/set，C++ 端用定长数组 + "始终有序"来等价实现。
//      * `fishes`  → 定长数组，**恒按 uid 升序**存放。
//        Python 里所有参与浮点求和 / 随机数消耗的遍历都走 `fishes_sorted()`，
//        所以"存的时候就有序"与"用的时候排序"结果完全一致。
//        唯一例外是 `repair()`：它按**存档原始顺序**遍历，因此
//        load_json() 的顺序是：按 JSON 数组原序读入 → repair() → 再排序。
//      * `codex`   → 定长数组，按 species 升序（Python 端只用 `in` / `len`
//        / `set(keys)`，与顺序无关；有序只是为了 to_dict 的双端字节一致）。
//      * `stats`   → 定长数组，按 key 升序。
//
// 🔴 金币恒为整数厘（i64）；rng_seed 恒为 u64（可超 i64 上限，见 json_min.h）。

#ifndef FT_CORE_STATE_H
#define FT_CORE_STATE_H

#include "ft_types.h"
#include "data_defs.h"
#include "json_min.h"

// 阶段名字段宽度（"juvenile" = 8 字符 + NUL，取 12 对齐）
#define FT_STAGE_LEN 12
// window_mode 字段宽度（"tank"/"strip"/"panel"）
#define FT_MODE_LEN 12

namespace ft {

/// 存档载荷版本。对偶 constants.py::SCHEMA_VERSION。
extern const i32 kSchemaVersion;

// ══════════════════════════════════════════════════════════════
//  单条鱼
// ══════════════════════════════════════════════════════════════

/// 对偶 state.py::FishState（字段名、默认值逐个对齐）。
struct FishState {
    i32  uid;                       ///< 默认 0
    char species[FT_ID_LEN];        ///< 默认 ""
    i64  born_at;                   ///< 默认 0
    f64  age_sec;                   ///< 默认 0.0
    char stage[FT_STAGE_LEN];       ///< 默认 "fry"
    bool variant;                   ///< 默认 false
    char nickname[FT_NAME_LEN];     ///< 默认 ""
    i64  last_bred_at;              ///< 默认 0
    f64  x;                         ///< 默认 0.5
    f64  y;                         ///< 默认 0.5
    f64  heading;                   ///< 默认 1.0

    /// 置为 Python dataclass 的字段默认值。
    void clear();

    /// 对偶 FishState.from_dict()：缺字段 / 类型错一律降级，绝不失败。
    void load_json(const JsonDoc& doc, i32 node);

    /// 展示名：昵称 > 鱼种中文名 > id。对偶 display_name()。
    const char* display_name(const FishSpeciesDef* sp) const;
};

// ══════════════════════════════════════════════════════════════
//  鱼缸
// ══════════════════════════════════════════════════════════════

/// 对偶 state.py::TankState。
struct TankState {
    f64  water;                                     ///< 默认 100.0
    i32  capacity_level;                            ///< 默认 0
    i32  filter_level;                              ///< 默认 0
    bool feeder_owned;                              ///< 默认 false
    bool feeder_on;                                 ///< 默认 true
    f64  satiety;                                   ///< 默认 1.0
    char decors[FT_MAX_DECOR_SLOT][FT_ID_LEN];      ///< **按 id 升序**
    i32  n_decors;

    void clear();
    void load_json(const JsonDoc& doc, i32 node);

    /// 自动投食器是否在工作。对偶 feeder_active()。
    bool feeder_active() const { return feeder_owned && feeder_on; }

    /// 插入一个装饰（保持 id 升序；已满或重复时返回 false）。
    bool add_decor(const char* id);
    bool has_decor(const char* id) const;
};

// ══════════════════════════════════════════════════════════════
//  图鉴 / 统计条目
// ══════════════════════════════════════════════════════════════

struct CodexEntry {
    char species[FT_ID_LEN];
    i64  unlocked_at;
};

struct StatEntry {
    char key[FT_ID_LEN];
    f64  value;
};

// ══════════════════════════════════════════════════════════════
//  整局状态
// ══════════════════════════════════════════════════════════════

/// 对偶 state.py::GameState。
///
/// ⚠️ 本结构体是 POD 语义（无指针成员、无动态分配），所以
/// `dst = src` 的按位赋值就是 Python `deep_copy()` 的精确对偶。
/// 为了让调用点与 Python 逐行对齐，仍提供显式的 deep_copy_to()。
struct GameState {
    i32  schema;
    i64  saved_at_utc;
    i64  coins_milli;
    u64  rng_seed;
    i32  next_uid;
    f64  breed_timer;
    TankState tank;

    FishState  fishes[FT_MAX_FISH];     ///< **恒按 uid 升序**
    i32        n_fishes;

    CodexEntry codex[FT_MAX_CODEX];     ///< 按 species 升序
    i32        n_codex;

    StatEntry  stats[FT_MAX_STATS];     ///< 按 key 升序
    i32        n_stats;

    // settings 段：Python 是自由 dict，这里只落地实际用到的两项。
    char settings_window_mode[FT_MODE_LEN];
    bool settings_muted;

    /// 定长数组溢出标记。正常路径恒为 false —— 一旦为 true，
    /// 说明状态规模超出 FT_MAX_* 上限，结果已不可信，调用方必须报错。
    bool overflow;

    // ── 生命周期 ──

    /// 置为 Python dataclass 的字段默认值。
    void clear();

    /// 对偶 GameState.from_dict()（内含 repair()）。
    /// :returns: repair() 修补的项数（0 = 存档健康）
    i32 load_json(const JsonDoc& doc, i32 node);

    /// 对偶 GameState.deep_copy()。
    void deep_copy_to(GameState& dst) const;

    // ── 查询 ──

    i32 fish_count() const { return n_fishes; }

    /// 第 i 条鱼（**uid 升序**）。对偶 `fishes_sorted()[i]`。
    FishState&       fish_at(i32 i);
    const FishState& fish_at(i32 i) const;

    /// 按 uid 找鱼；找不到返回 NULL。对偶 get_fish()。
    FishState*       get_fish(i32 uid);
    const FishState* get_fish(i32 uid) const;

    /// 图鉴中是否已有该鱼种。对偶 `species in state.codex`。
    bool has_codex(const char* species) const;
    i32  codex_count() const { return n_codex; }
    const char* codex_species_at(i32 i) const;

    /// 当前容量 / 是否已满。对偶 capacity() / is_full()。
    i32  capacity(const BalanceTable& bal) const;
    bool is_full(const BalanceTable& bal) const;

    /// 金币（浮点，仅展示）。对偶 coins()。
    f64 coins(const BalanceTable& bal) const;

    /// 读 / 累加统计项。对偶 stat() / bump_stat()。
    f64  stat(const char* key, f64 fallback) const;
    void bump_stat(const char* key, f64 delta);

    // ── 变更 ──

    /// 分配新 uid（自增不复用）。对偶 alloc_uid()。
    i32 alloc_uid();

    /// 加入一条鱼并登记图鉴。对偶 add_fish()。
    /// :param when: 图鉴登记时间戳
    /// :returns: 是否**首次**解锁该鱼种
    bool add_fish(const FishState& fish, i64 when);

    /// 移出一条鱼（图鉴保留）。对偶 remove_fish()。
    bool remove_fish(i32 uid);

    /// 增减金币（厘），结果永不为负。对偶 add_coins_milli()。
    i64 add_coins_milli(i64 delta);

    bool can_afford_milli(i64 price_milli) const;
    bool spend_milli(i64 price_milli);

    // ── 自愈 ──

    /// 对偶 repair()：uid 去重 / next_uid 抬高 / 坐标钳位 / 图鉴补登。
    /// :returns: 修补项数
    i32 repair();

    /// 把 fishes 按 uid 升序重排（插入排序，n <= 64）。
    void sort_fishes();

    // ── 新档 ──

    /// 对偶 GameState.new_game()。
    void new_game(const BalanceTable& bal, const FishLibrary& species_lib, i64 when);

private:
    /// 登记图鉴（保持 species 升序）；返回是否首次。
    bool codex_touch(const char* species, i64 when);
};

}  // namespace ft

#endif  // FT_CORE_STATE_H
