// economy.cpp —— 见 economy.h。◆ 对偶 fishtank/economy.py

#include "economy.h"

#include "ft_str.h"

namespace ft {

// ══════════════════════════════════════════════════════════════
//  成长阶段
// ══════════════════════════════════════════════════════════════

f64 growth_progress(f64 age_sec, f64 cycle_sec) {
    if (cycle_sec <= 0.0) return 0.0;
    return age_sec / cycle_sec;
}

const char* stage_of(f64 age_sec, f64 cycle_sec, const BalanceTable& bal) {
    f64 p = growth_progress(age_sec, cycle_sec);
    f64 fry = bal.threshold(kStageFry);       // 默认 0.15
    f64 juv = bal.threshold(kStageJuvenile);  // 默认 0.45
    f64 adu = bal.threshold(kStageAdult);     // 默认 1.45
    if (p < fry) return kStageFry;
    if (p < juv) return kStageJuvenile;
    if (p < adu) return kStageAdult;
    return kStageMature;
}

bool stage_reached(const char* stage, const char* min_stage) {
    return stage_index(stage) >= stage_index(min_stage);
}

// ══════════════════════════════════════════════════════════════
//  水质
// ══════════════════════════════════════════════════════════════

f64 quality_factor(f64 water, const BalanceTable& bal) {
    f64 lo = bal.water_min();
    f64 hi = bal.water_max();
    f64 floor = bal.quality_floor();
    if (hi <= lo) return 1.0;
    f64 t = clamp_((water - lo) / (hi - lo), 0.0, 1.0);
    return floor + (1.0 - floor) * t;
}

f64 water_delta_per_min(i32 fish_count, i32 filter_level,
                        const BalanceTable& bal, bool offline) {
    f64 decay = bal.num("water.decay_per_fish", 0.03) * static_cast<f64>(imax(0, fish_count));
    f64 gain = bal.filter_gain(filter_level);
    f64 delta = gain - decay;
    if (offline) {
        delta *= bal.num("water.offline_scale", 0.5);
    }
    return delta;
}

f64 step_water(f64 water, i32 fish_count, i32 filter_level,
               f64 step_sec, const BalanceTable& bal, bool offline) {
    f64 delta = water_delta_per_min(fish_count, filter_level, bal, offline);
    f64 nxt = water + delta * (step_sec / 60.0);
    return clamp_(nxt, bal.water_min(), bal.water_max());
}

// ══════════════════════════════════════════════════════════════
//  饱食度
// ══════════════════════════════════════════════════════════════

f64 satiety_factor(f64 satiety, const BalanceTable& bal) {
    f64 floor = bal.num("feeder.output_floor", 0.85);
    f64 s_min = bal.num("feeder.satiety_min", 0.0);
    f64 s_max = bal.num("feeder.satiety_max", 1.0);
    if (s_max <= s_min) return 1.0;
    f64 t = clamp_((satiety - s_min) / (s_max - s_min), 0.0, 1.0);
    return floor + (1.0 - floor) * t;
}

f64 step_satiety(f64 satiety, f64 step_sec, const BalanceTable& bal) {
    f64 dec = bal.num("feeder.decay_per_min", 0.012) * (step_sec / 60.0);
    return clamp_(satiety - dec,
                  bal.num("feeder.satiety_min", 0.0),
                  bal.num("feeder.satiety_max", 1.0));
}

f64 feeder_upkeep_rate_milli(i32 fish_count, const BalanceTable& bal) {
    f64 per = bal.num("feeder.upkeep_per_fish_per_min", 0.05);
    return per * static_cast<f64>(imax(0, fish_count)) * static_cast<f64>(bal.coin_scale());
}

AutoFeedResult auto_feed(f64 satiety, const BalanceTable& bal) {
    AutoFeedResult res;
    res.satiety = satiety;
    res.fed = false;

    f64 level = bal.num("feeder.auto_feed_level", 0.6);
    f64 s_max = bal.num("feeder.satiety_max", 1.0);
    f64 s_min = bal.num("feeder.satiety_min", 0.0);

    if (satiety >= level) {
        return res;
    }
    f64 gain = bal.num("feeder.feed_gain", 0.5);
    res.satiety = clamp_(satiety + gain, s_min, s_max);
    res.fed = true;
    return res;
}

// ══════════════════════════════════════════════════════════════
//  加成
// ══════════════════════════════════════════════════════════════

f64 decor_bonus(const TankState& tank, const DecorLibrary& decor_lib) {
    f64 total = 0.0;
    // tank.decors 已按 id 升序去重，等价于 Python 的 sorted(set(...))
    for (i32 i = 0; i < tank.n_decors; ++i) {
        total += decor_lib.bonus_of(tank.decors[i]);
    }
    return total;
}

i32 completed_groups_count(const GameState& state, const FishLibrary& species_lib) {
    i32 count = 0;
    for (i32 i = 0; i < species_lib.group_count(); ++i) {
        const char* g = species_lib.group_at(i);
        i32 n_members = species_lib.group_member_count(g);
        if (n_members == 0) continue;
        bool all_owned = true;
        for (i32 k = 0; k < n_members; ++k) {
            const FishSpeciesDef* m = species_lib.group_member_at(g, k);
            if (m == FT_NULL || !state.has_codex(m->id)) {
                all_owned = false;
                break;
            }
        }
        if (all_owned) ++count;
    }
    return count;
}

f64 codex_bonus(const GameState& state, const FishLibrary& species_lib,
                const BalanceTable& bal) {
    return static_cast<f64>(completed_groups_count(state, species_lib)) * bal.group_bonus();
}

f64 total_bonus(const GameState& state, const FishLibrary& species_lib,
                const DecorLibrary& decor_lib, const BalanceTable& bal) {
    f64 raw = decor_bonus(state.tank, decor_lib) +
              codex_bonus(state, species_lib, bal);
    return clamp_(raw, 0.0, bal.bonus_cap());
}

// ── BonusCache ──

f64 BonusCache::value(const GameState& state) {
    // 检查缓存是否命中：decor 集合 + codex 条目数
    bool match = valid;
    if (match && state.n_codex != last_codex_count) match = false;
    if (match && state.tank.n_decors != last_n_decors) match = false;
    if (match) {
        for (i32 i = 0; i < last_n_decors; ++i) {
            if (!str_eq(last_decors[i], state.tank.decors[i])) {
                match = false;
                break;
            }
        }
    }
    if (!match) {
        val = total_bonus(state, *species, *decor, *bal);
        last_codex_count = state.n_codex;
        last_n_decors = state.tank.n_decors;
        for (i32 i = 0; i < last_n_decors; ++i) {
            str_copy(last_decors[i], FT_ID_LEN, state.tank.decors[i]);
        }
        valid = true;
    }
    return val;
}

// ══════════════════════════════════════════════════════════════
//  产出速率
// ══════════════════════════════════════════════════════════════

f64 tank_base_per_min(const GameState& state, const FishLibrary& species_lib,
                      const BalanceTable& bal) {
    f64 total = 0.0;
    // state.fishes 已按 uid 升序，等价于 Python 的 fishes_sorted()
    for (i32 i = 0; i < state.n_fishes; ++i) {
        const FishState& f = state.fishes[i];
        const FishSpeciesDef* sp = species_lib.get(f.species);
        const char* rarity = (sp != FT_NULL) ? sp->rarity : "R1";
        total += bal.base_income(rarity) * bal.stage_coef(f.stage);
    }
    return total;
}

f64 income_rate_milli(const GameState& state, const BalanceTable& bal,
                      const FishLibrary& species_lib, const DecorLibrary& decor_lib,
                      const f64* bonus) {
    f64 base = tank_base_per_min(state, species_lib, bal);
    f64 rate = base * static_cast<f64>(bal.coin_scale());
    rate *= quality_factor(state.tank.water, bal);
    rate *= satiety_factor(state.tank.satiety, bal);

    f64 b;
    if (bonus != FT_NULL) {
        b = *bonus;
    } else {
        b = total_bonus(state, species_lib, decor_lib, bal);
    }
    rate *= (1.0 + b);
    return rate;
}

f64 net_rate_milli(const GameState& state, const BalanceTable& bal,
                   const FishLibrary& species_lib, const DecorLibrary& decor_lib,
                   const f64* bonus) {
    f64 gross = income_rate_milli(state, bal, species_lib, decor_lib, bonus);
    f64 upkeep = 0.0;
    if (state.tank.feeder_active()) {
        upkeep = feeder_upkeep_rate_milli(state.fish_count(), bal);
    }
    return fmax_(0.0, gross - upkeep);
}

i64 step_gain_milli(const GameState& state, const BalanceTable& bal,
                    const FishLibrary& species_lib, const DecorLibrary& decor_lib,
                    f64 step_sec, f64 efficiency, const f64* bonus) {
    f64 rate = net_rate_milli(state, bal, species_lib, decor_lib, bonus);
    // 🔴 运算顺序与 Python 逐位一致：(rate * (step/60)) * efficiency
    return llmax(0, round_half_up(rate * (step_sec / 60.0) * efficiency));
}

// ══════════════════════════════════════════════════════════════
//  离线效率分段
// ══════════════════════════════════════════════════════════════

f64 offline_efficiency(f64 elapsed_sec, const BalanceTable& bal) {
    f64 minutes = elapsed_sec / 60.0;
    i32 n_segs = bal.offline_segment_count();
    f64 last_k = 1.0;
    for (i32 i = 0; i < n_segs; ++i) {
        f64 lo, hi, k;
        bool has_hi;
        bal.offline_segment(i, &lo, &hi, &has_hi, &k);
        if (k < 0.0) continue;  // 哨兵：无效段，跳过
        last_k = k;
        if (minutes < lo) continue;
        if (!has_hi || minutes < hi) {
            return k;
        }
    }
    return last_k;
}

}  // namespace ft
