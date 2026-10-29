// ═══════════════════════════════════════════════════════════════════════
//  economy.h —— 经济与成长的纯函数内核（双端同源）
// ═══════════════════════════════════════════════════════════════════════
//
// ◆ 对偶：fishtank/economy.py
//     每一个函数都是纯函数：不读全局、不改参数（除非显式标注）、不做 IO。
//     XJ380 C++ 端只要照抄公式即可得到逐位一致的结果。
//
// 🔴 数值约定（ARCHITECTURE §2）：
//    * 金币一律用整数"厘"（milli），1 金币 = coin_scale 厘（默认 1000）。
//    * 取整一律用 round_half_up(x) = floor(x + 0.5)，禁用 std::round。
//    * 遍历鱼一律按 uid 升序（GameState 内部已保持有序）。

#ifndef FT_CORE_ECONOMY_H
#define FT_CORE_ECONOMY_H

#include "ft_types.h"
#include "ft_math.h"
#include "data_defs.h"
#include "state.h"

namespace ft {

// ══════════════════════════════════════════════════════════════
//  成长阶段
// ══════════════════════════════════════════════════════════════

/// 成长进度 p = age / cycle（可以 > 1）。cycle <= 0 返回 0。
f64 growth_progress(f64 age_sec, f64 cycle_sec);

/// 由累计成长秒数判定成长阶段。对偶 economy.py::stage_of。
/// :returns: kStageFry / kStageJuvenile / kStageAdult / kStageMature
const char* stage_of(f64 age_sec, f64 cycle_sec, const BalanceTable& bal);

/// 判断 stage 是否已达到 min_stage（含）。对偶 stage_reached。
bool stage_reached(const char* stage, const char* min_stage);

// ══════════════════════════════════════════════════════════════
//  水质
// ══════════════════════════════════════════════════════════════

/// 水质 → 产出系数，线性映射到 [quality_floor, 1.0]。
f64 quality_factor(f64 water, const BalanceTable& bal);

/// 每分钟的水质变化量（正 = 变好）。
f64 water_delta_per_min(i32 fish_count, i32 filter_level,
                        const BalanceTable& bal, bool offline);

/// 推进水质一个时间步，钳制在 [water.min, water.max]。
f64 step_water(f64 water, i32 fish_count, i32 filter_level,
               f64 step_sec, const BalanceTable& bal, bool offline);

// ══════════════════════════════════════════════════════════════
//  饱食度（自动投食器）
// ══════════════════════════════════════════════════════════════

/// 饱食度 → 产出系数，线性映射到 [feeder.output_floor, 1.0]。
f64 satiety_factor(f64 satiety, const BalanceTable& bal);

/// 饱食度自然衰减一个时间步（不含自动投食）。
f64 step_satiety(f64 satiety, f64 step_sec, const BalanceTable& bal);

/// 自动投食器的维护费速率（厘/分钟）。
f64 feeder_upkeep_rate_milli(i32 fish_count, const BalanceTable& bal);

/// 自动投食器的喂食判定。
struct AutoFeedResult {
    f64  satiety;
    bool fed;
};
AutoFeedResult auto_feed(f64 satiety, const BalanceTable& bal);

// ══════════════════════════════════════════════════════════════
//  加成
// ══════════════════════════════════════════════════════════════

/// 装饰加成之和（tank.decors 已按 id 升序去重）。
f64 decor_bonus(const TankState& tank, const DecorLibrary& decor_lib);

/// 已集齐的族群数。对偶 len(completed_groups(...))。
i32 completed_groups_count(const GameState& state, const FishLibrary& species_lib);

/// 图鉴族群加成 = 已集齐族群数 × codex.group_bonus。
f64 codex_bonus(const GameState& state, const FishLibrary& species_lib,
                const BalanceTable& bal);

/// 装饰 + 图鉴的总加成，封顶 bonus_cap。
f64 total_bonus(const GameState& state, const FishLibrary& species_lib,
                const DecorLibrary& decor_lib, const BalanceTable& bal);

/// 总加成的记忆化包装（纯性能优化，不改变任何数值）。
struct BonusCache {
    const BalanceTable*  bal;
    const FishLibrary*   species;
    const DecorLibrary*  decor;

    char last_decors[FT_MAX_DECOR_SLOT][FT_ID_LEN];
    i32  last_n_decors;
    i32  last_codex_count;
    f64  val;
    bool valid;

    BonusCache() : bal(FT_NULL), species(FT_NULL), decor(FT_NULL),
                   last_n_decors(0), last_codex_count(0), val(0.0), valid(false) {}

    void init(const BalanceTable& b, const FishLibrary& s, const DecorLibrary& d) {
        bal = &b; species = &s; decor = &d; valid = false;
    }

    f64 value(const GameState& state);
};

// ══════════════════════════════════════════════════════════════
//  产出速率
// ══════════════════════════════════════════════════════════════

/// 全缸裸产出（金币/分钟），按 uid 升序求和。
f64 tank_base_per_min(const GameState& state, const FishLibrary& species_lib,
                      const BalanceTable& bal);

/// 当前每分钟产出（厘，浮点，未取整）。
/// :param bonus: 预先算好的总加成；NULL 表示现算。
f64 income_rate_milli(const GameState& state, const BalanceTable& bal,
                      const FishLibrary& species_lib, const DecorLibrary& decor_lib,
                      const f64* bonus);

/// 扣掉投食器维护费后的净产出速率（厘/分钟），下限钳到 0。
f64 net_rate_milli(const GameState& state, const BalanceTable& bal,
                   const FishLibrary& species_lib, const DecorLibrary& decor_lib,
                   const f64* bonus);

/// 一个时间步的净收益（整数厘，已四舍五入）。
/// 🔴 全流程只在这里取整一次。
i64 step_gain_milli(const GameState& state, const BalanceTable& bal,
                    const FishLibrary& species_lib, const DecorLibrary& decor_lib,
                    f64 step_sec, f64 efficiency, const f64* bonus);

// ══════════════════════════════════════════════════════════════
//  离线效率分段
// ══════════════════════════════════════════════════════════════

/// 按"已离线时长"查分段效率系数。
/// [0, 480min) → 1.00; [480, 1440min) → 0.60; [1440, ∞) → 0.35
f64 offline_efficiency(f64 elapsed_sec, const BalanceTable& bal);

}  // namespace ft

#endif  // FT_CORE_ECONOMY_H
