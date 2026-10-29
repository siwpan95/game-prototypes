// ═══════════════════════════════════════════════════════════════════════
//  offline.h —— ★ 离线结算：全项目唯一的时间推进权威实现
// ═══════════════════════════════════════════════════════════════════════
//
// ◆ 对偶：fishtank/offline.py
//     settle_offline()  ↔ settle_offline()
//     advance_step()   ↔ advance_step()
//     attempt_breed()  ↔ attempt_breed()
//     OfflineReport    ↔ OfflineReport
//
// 🔴 settle_offline 是纯函数：深拷贝入参、返回新状态，绝不修改调用方传入的 state。
// 🔴 五个阶段的顺序是双端契约的一部分，不得调整：
//    成长 → 水质 → 饱食 → 收益 → 繁殖。

#ifndef FT_CORE_OFFLINE_H
#define FT_CORE_OFFLINE_H

#include "ft_types.h"
#include "data_defs.h"
#include "state.h"
#include "economy.h"
#include "rng.h"

namespace ft {

// ── 常量 ──
static const i32 kMaxSteps     = 200000;  // 步数保险丝
static const i64 kMinReportSec = 60;      // 少于此时长不弹离线卡片

// ══════════════════════════════════════════════════════════════
//  结算报告
// ══════════════════════════════════════════════════════════════

struct GrownEntry {
    i32  uid;
    char species[FT_ID_LEN];
    char from_stage[FT_STAGE_LEN];
    char to_stage[FT_STAGE_LEN];
};

struct BornEntry {
    i32  uid;
    char species[FT_ID_LEN];
    bool variant;
};

struct OfflineReport {
    i64  now_utc;
    i64  anchor_utc;
    i64  raw_away_sec;
    i64  away_sec;
    bool capped;
    bool clock_rollback;
    i32  steps;
    f64  equivalent_min;
    i64  coins_gained_milli;
    i64  upkeep_milli;
    f64  water_before;
    f64  water_after;
    f64  satiety_before;
    f64  satiety_after;

    GrownEntry grown[FT_MAX_FISH];
    i32        n_grown;

    BornEntry  born[FT_MAX_FISH];
    i32        n_born;

    char       new_codex[FT_MAX_FISH][FT_ID_LEN];
    i32        n_new_codex;

    void clear() {
        now_utc = 0; anchor_utc = 0; raw_away_sec = 0; away_sec = 0;
        capped = false; clock_rollback = false; steps = 0;
        equivalent_min = 0.0; coins_gained_milli = 0; upkeep_milli = 0;
        water_before = 0.0; water_after = 0.0;
        satiety_before = 0.0; satiety_after = 0.0;
        n_grown = 0; n_born = 0; n_new_codex = 0;
    }
};

// ══════════════════════════════════════════════════════════════
//  单步输出
// ══════════════════════════════════════════════════════════════

struct StepOutput {
    i64  gain_milli;
    i64  upkeep_milli;
    GrownEntry grown[FT_MAX_FISH];
    i32        n_grown;
    BornEntry  born[FT_MAX_FISH];
    i32        n_born;
    char       new_codex[FT_MAX_FISH][FT_ID_LEN];
    i32        n_new_codex;

    void clear() {
        gain_milli = 0; upkeep_milli = 0;
        n_grown = 0; n_born = 0; n_new_codex = 0;
    }
};

// ══════════════════════════════════════════════════════════════
//  单步推进
// ══════════════════════════════════════════════════════════════

/// 把 state 就地推进一个时间步。
/// 🔴 五个阶段的顺序固定：成长 → 水质 → 饱食 → 收益 → 繁殖。
void advance_step(GameState& state, f64 step_sec, i64 now,
                  const BalanceTable& bal, const FishLibrary& species_lib,
                  const DecorLibrary& decor_lib, DetRandom& rng,
                  f64 efficiency, bool offline, bool do_breed,
                  BonusCache* bonus_cache, StepOutput& out);

// ══════════════════════════════════════════════════════════════
//  ★ 离线结算主函数
// ══════════════════════════════════════════════════════════════

/// ★ 纯函数离线结算。深拷贝入参，返回新状态。
/// :param state: 读档得到的 GameState（不会被修改）
/// :param now: 当前 UTC 整秒
/// :param out_state: 结算后的新状态
/// :param out_report: 结算报告
void settle_offline(const GameState& state, i64 now,
                    const BalanceTable& bal, const FishLibrary& species_lib,
                    const DecorLibrary& decor_lib,
                    GameState& out_state, OfflineReport& out_report);

}  // namespace ft

#endif  // FT_CORE_OFFLINE_H
