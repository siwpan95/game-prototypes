// offline.cpp —— 见 offline.h。◆ 对偶 fishtank/offline.py

#include "offline.h"

#include "ft_str.h"

namespace ft {

// ══════════════════════════════════════════════════════════════
//  繁殖辅助
// ══════════════════════════════════════════════════════════════

/// 在同族群里找一个高一档稀有度的鱼种；没有则返回 NULL。
/// 对偶 _rarity_up_candidate。候选按 id 升序排列后再抽。
static const char* rarity_up_candidate(const char* base_species,
                                       const FishLibrary& species_lib,
                                       DetRandom& rng) {
    const FishSpeciesDef* base = species_lib.get(base_species);
    if (base == FT_NULL) return FT_NULL;

    const char* nxt = rarity_at(rarity_index(base->rarity) + 1);
    if (str_eq(nxt, base->rarity)) return FT_NULL;  // 已是最高档

    // 收集同族群 + 同稀有度的鱼种（已按 id 升序，因为 group_member_at 按 id 升序返回）
    const char* pool[FT_MAX_SPECIES];
    i32 n_pool = 0;
    i32 n_members = species_lib.group_member_count(base->group);
    for (i32 k = 0; k < n_members; ++k) {
        const FishSpeciesDef* m = species_lib.group_member_at(base->group, k);
        if (m != FT_NULL && str_eq(m->rarity, nxt)) {
            pool[n_pool++] = m->id;
        }
    }
    if (n_pool == 0) return FT_NULL;

    // rng.choice(pool) = pool[randint(0, n_pool-1)]
    i32 idx = rng.randint(0, n_pool - 1);
    return pool[idx];
}

/// 尝试繁殖一次（就地修改 state）。对偶 attempt_breed。
/// :returns: (新生鱼 uid, 新生鱼 species, 是否首次解锁) — uid 为 0 表示未繁殖
struct BreedResult {
    i32  uid;
    char species[FT_ID_LEN];
    bool variant;
    bool first_unlock;
};

static BreedResult attempt_breed(GameState& state, const BalanceTable& bal,
                                 const FishLibrary& species_lib, DetRandom& rng,
                                 i64 now) {
    BreedResult result;
    result.uid = 0;
    result.species[0] = '\0';
    result.variant = false;
    result.first_unlock = false;

    if (state.is_full(bal)) {
        return result;
    }

    const char* min_stage = bal.text("breeding.min_parent_stage", "adult");
    i64 cooldown = bal.intv("breeding.same_species_cooldown_sec", 10800);

    // 收集 eligible（已按 uid 升序，因为 fishes 有序）
    FishState* eligible[FT_MAX_FISH];
    i32 n_eligible = 0;
    for (i32 i = 0; i < state.n_fishes; ++i) {
        FishState& f = state.fishes[i];
        if (stage_reached(f.stage, min_stage) && (now - f.last_bred_at) >= cooldown) {
            eligible[n_eligible++] = &f;
        }
    }
    if (n_eligible < 2) {
        return result;
    }

    // 同种配对：按鱼种 id 升序，取每种里 uid 最小的两条
    // Python: by_species.setdefault(f.species, []).append(f)
    //         same_pairs = [(v[0], v[1]) for _k, v in sorted(by_species.items()) if len(v) >= 2]
    FishState* same_pair_a = FT_NULL;
    FishState* same_pair_b = FT_NULL;

    // 遍历 eligible 按 species 分组（eligible 已按 uid 升序）
    // 同 species 的前两条就是 uid 最小的
    for (i32 i = 0; i < n_eligible; ++i) {
        if (same_pair_a != FT_NULL) break;
        for (i32 j = i + 1; j < n_eligible; ++j) {
            if (str_eq(eligible[i]->species, eligible[j]->species)) {
                // 找到了同种对。但 Python 是按 species id 升序取第一对。
                // 由于 eligible 按 uid 升序，species 顺序不一定升序。
                // 需要找 species id 最小的那对。
                // 先记住这对，继续扫描看有没有 species id 更小的对。
                same_pair_a = eligible[i];
                same_pair_b = eligible[j];
                break;
            }
        }
    }

    // 如果有多对同种，需要取 species id 最小的那对
    // 重新扫描：找所有同种对中 species id 最小的
    if (same_pair_a != FT_NULL) {
        const char* best_species = same_pair_a->species;
        FishState* best_a = same_pair_a;
        FishState* best_b = same_pair_b;
        for (i32 i = 0; i < n_eligible; ++i) {
            for (i32 j = i + 1; j < n_eligible; ++j) {
                if (str_eq(eligible[i]->species, eligible[j]->species)) {
                    if (str_cmp(eligible[i]->species, best_species) < 0) {
                        best_species = eligible[i]->species;
                        best_a = eligible[i];
                        best_b = eligible[j];
                    }
                    break;  // 只取每个 species 的前两条
                }
            }
        }
        same_pair_a = best_a;
        same_pair_b = best_b;
    }

    FishState* pair_a = FT_NULL;
    FishState* pair_b = FT_NULL;
    bool cross = false;

    // 1. 同种配对判定
    if (same_pair_a != FT_NULL) {
        if (rng.chance(bal.num("breeding.same_species_chance", 0.12))) {
            pair_a = same_pair_a;
            pair_b = same_pair_b;
        }
    }

    // 2. 异种配对判定
    if (pair_a == FT_NULL) {
        if (rng.chance(bal.num("breeding.cross_species_chance", 0.03))) {
            FishState* a = eligible[0];
            FishState* b = FT_NULL;
            for (i32 i = 1; i < n_eligible; ++i) {
                if (!str_eq(eligible[i]->species, a->species)) {
                    b = eligible[i];
                    break;
                }
            }
            if (b != FT_NULL) {
                pair_a = a;
                pair_b = b;
                cross = true;
            }
        }
    }

    if (pair_a == FT_NULL || pair_b == FT_NULL) {
        return result;
    }

    // 3. 选亲本鱼种
    const char* child_species;
    if (cross) {
        child_species = (rng.randint(0, 1) == 0) ? pair_a->species : pair_b->species;
    } else {
        child_species = pair_a->species;
    }

    // 4. 稀有度提升
    if (rng.chance(bal.num("breeding.rarity_up_chance", 0.15))) {
        const char* up = rarity_up_candidate(child_species, species_lib, rng);
        if (up != FT_NULL) {
            child_species = up;
        }
    }

    // 5. 变异
    bool variant = rng.chance(bal.num("breeding.variant_chance", 0.05));

    // 创建新生鱼
    FishState child;
    child.clear();
    child.uid = state.alloc_uid();
    str_copy(child.species, FT_ID_LEN, child_species);
    child.born_at = now;
    child.age_sec = 0.0;
    str_copy(child.stage, FT_STAGE_LEN, kStageFry);
    child.variant = variant;
    child.nickname[0] = '\0';
    child.last_bred_at = now;
    child.x = r6((pair_a->x + pair_b->x) * 0.5);
    child.y = r6((pair_a->y + pair_b->y) * 0.5);
    child.heading = pair_a->heading;

    pair_a->last_bred_at = now;
    pair_b->last_bred_at = now;

    bool first = state.add_fish(child, now);
    state.bump_stat("bred", 1.0);
    state.bump_stat("born", 1.0);

    result.uid = child.uid;
    str_copy(result.species, FT_ID_LEN, child_species);
    result.variant = variant;
    result.first_unlock = first;
    return result;
}

// ══════════════════════════════════════════════════════════════
//  单步推进
// ══════════════════════════════════════════════════════════════

void advance_step(GameState& state, f64 step_sec, i64 now,
                  const BalanceTable& bal, const FishLibrary& species_lib,
                  const DecorLibrary& decor_lib, DetRandom& rng,
                  f64 efficiency, bool offline, bool do_breed,
                  BonusCache* bonus_cache, StepOutput& out) {
    out.clear();

    // ① 成长（不打折：准则 L7 —— 离线也照常长大）
    for (i32 i = 0; i < state.n_fishes; ++i) {
        FishState& f = state.fishes[i];
        f.age_sec += step_sec;
        const FishSpeciesDef* sp = species_lib.get(f.species);
        const char* rarity = (sp != FT_NULL) ? sp->rarity : "R1";
        f64 cycle = static_cast<f64>(bal.growth_cycle_sec(rarity));
        const char* new_stage = stage_of(f.age_sec, cycle, bal);
        if (!str_eq(new_stage, f.stage)) {
            if (out.n_grown < FT_MAX_FISH) {
                GrownEntry& g = out.grown[out.n_grown];
                g.uid = f.uid;
                str_copy(g.species, FT_ID_LEN, f.species);
                str_copy(g.from_stage, FT_STAGE_LEN, f.stage);
                str_copy(g.to_stage, FT_STAGE_LEN, new_stage);
                ++out.n_grown;
            }
            str_copy(f.stage, FT_STAGE_LEN, new_stage);
        }
    }

    // ② 水质
    state.tank.water = step_water(state.tank.water, state.fish_count(),
                                  state.tank.filter_level, step_sec, bal,
                                  offline);

    // ③ 饱食度 + 自动投食
    state.tank.satiety = step_satiety(state.tank.satiety, step_sec, bal);
    if (state.tank.feeder_active()) {
        AutoFeedResult af = auto_feed(state.tank.satiety, bal);
        state.tank.satiety = af.satiety;
        // BUG-01: Python offline.py:272 用了内置 round()（银行家舍入）。
        // 这是上报字段（不进金币账），为保持双端逐行对偶这里如实复刻。
        // 一旦 Python 端修复为 round_half_up，此处同步改为 round_half_up。
        out.upkeep_milli = round_half_even(
            feeder_upkeep_rate_milli(state.fish_count(), bal)
            * (step_sec / 60.0) * efficiency);
    }

    // ④ 收益（全流程唯一一次取整）
    f64 bonus_val;
    const f64* bonus_ptr = FT_NULL;
    if (bonus_cache != FT_NULL) {
        bonus_val = bonus_cache->value(state);
        bonus_ptr = &bonus_val;
    }
    i64 gain = step_gain_milli(state, bal, species_lib, decor_lib,
                               step_sec, efficiency, bonus_ptr);
    state.add_coins_milli(gain);
    out.gain_milli = gain;

    // ⑤ 繁殖
    if (do_breed) {
        i32 interval = static_cast<i32>(bal.intv("breeding.check_interval_sec", 600));
        if (interval < 1) interval = 1;
        state.breed_timer += step_sec;
        while (state.breed_timer >= static_cast<f64>(interval)) {
            state.breed_timer -= static_cast<f64>(interval);
            BreedResult br = attempt_breed(state, bal, species_lib, rng, now);
            if (br.uid != 0) {
                if (out.n_born < FT_MAX_FISH) {
                    BornEntry& b = out.born[out.n_born];
                    b.uid = br.uid;
                    str_copy(b.species, FT_ID_LEN, br.species);
                    b.variant = br.variant;
                    ++out.n_born;
                }
                if (br.first_unlock && out.n_new_codex < FT_MAX_FISH) {
                    str_copy(out.new_codex[out.n_new_codex], FT_ID_LEN, br.species);
                    ++out.n_new_codex;
                }
            }
        }
    }
}

// ══════════════════════════════════════════════════════════════
//  ★ 离线结算主函数
// ══════════════════════════════════════════════════════════════

void settle_offline(const GameState& state, i64 now,
                    const BalanceTable& bal, const FishLibrary& species_lib,
                    const DecorLibrary& decor_lib,
                    GameState& out_state, OfflineReport& out_report) {
    out_report.clear();

    // ── S0 准备 ──
    state.deep_copy_to(out_state);
    GameState& st = out_state;  // 别名，方便书写

    now = static_cast<i64>(now);
    i64 anchor = st.saved_at_utc;
    out_report.now_utc = now;
    out_report.anchor_utc = anchor;
    out_report.water_before = st.tank.water;
    out_report.satiety_before = st.tank.satiety;

    if (anchor <= 0) {
        // 新档 / 无锚点：只补锚点，不结算
        st.saved_at_utc = now;
        out_report.water_after = st.tank.water;
        out_report.satiety_after = st.tank.satiety;
        return;
    }

    i64 raw_away = now - anchor;
    out_report.raw_away_sec = raw_away;
    if (raw_away <= 0) {
        // 时钟回拨：既不结算也不动锚点
        out_report.clock_rollback = true;
        out_report.water_after = st.tank.water;
        out_report.satiety_after = st.tank.satiety;
        return;
    }

    i64 hard_cap = bal.hard_cap_sec();
    if (hard_cap < 1) hard_cap = 1;
    i64 away = (raw_away < hard_cap) ? raw_away : hard_cap;
    out_report.capped = (away < raw_away);
    out_report.away_sec = away;

    // ── S1 分步 ──
    i32 fine_step = static_cast<i32>(bal.intv("offline.fine_step_sec", 60));
    if (fine_step < 1) fine_step = 1;
    i32 coarse_step = static_cast<i32>(bal.intv("offline.coarse_step_sec", 3600));
    if (coarse_step < fine_step) coarse_step = fine_step;
    i64 fine_limit = bal.intv("offline.fine_limit_sec", 86400);
    if (fine_limit < 0) fine_limit = 0;

    DetRandom rng(st.rng_seed);
    BonusCache bonus_cache;
    bonus_cache.init(bal, species_lib, decor_lib);

    // 记录每条鱼的初始阶段（用于 S3 汇总 grown）
    struct StageBefore {
        i32  uid;
        char stage[FT_STAGE_LEN];
    };
    StageBefore stage_before[FT_MAX_FISH];
    i32 n_stage_before = st.n_fishes;
    for (i32 i = 0; i < st.n_fishes; ++i) {
        stage_before[i].uid = st.fishes[i].uid;
        str_copy(stage_before[i].stage, FT_STAGE_LEN, st.fishes[i].stage);
    }

    i64 coins_before = st.coins_milli;

    i64 elapsed = 0;
    i32 steps = 0;
    f64 equivalent_min = 0.0;
    i64 upkeep_total = 0;

    // born / new_codex 累积在 report 里
    out_report.n_born = 0;
    out_report.n_new_codex = 0;

    while (elapsed < away && steps < kMaxSteps) {
        i64 step;
        if (elapsed < fine_limit) {
            step = fine_step;
        } else {
            step = coarse_step;
        }
        if (elapsed + step > away) {
            step = away - elapsed;
        }
        f64 k = offline_efficiency(static_cast<f64>(elapsed), bal);

        // ── S2 单步推进 ──
        i64 now_step = anchor + elapsed + step;
        StepOutput out;
        advance_step(st, static_cast<f64>(step), now_step, bal,
                     species_lib, decor_lib, rng,
                     k, true, true, &bonus_cache, out);

        upkeep_total += out.upkeep_milli;

        // 累积 born
        for (i32 i = 0; i < out.n_born; ++i) {
            if (out_report.n_born < FT_MAX_FISH) {
                out_report.born[out_report.n_born] = out.born[i];
                ++out_report.n_born;
            }
        }

        // 累积 new_codex（不在这里去重，S3 再去重排序）
        for (i32 i = 0; i < out.n_new_codex; ++i) {
            if (out_report.n_new_codex < FT_MAX_FISH) {
                str_copy(out_report.new_codex[out_report.n_new_codex],
                         FT_ID_LEN, out.new_codex[i]);
                ++out_report.n_new_codex;
            }
        }

        equivalent_min += (static_cast<f64>(step) / 60.0) * k;

        elapsed += step;
        ++steps;
    }

    // ── S3 汇总 ──
    st.rng_seed = rng.state();
    st.saved_at_utc = now;

    // grown：比较初始阶段与最终阶段
    out_report.n_grown = 0;
    for (i32 i = 0; i < st.n_fishes; ++i) {
        const FishState& f = st.fishes[i];
        const char* old = FT_NULL;
        for (i32 j = 0; j < n_stage_before; ++j) {
            if (stage_before[j].uid == f.uid) {
                old = stage_before[j].stage;
                break;
            }
        }
        if (old != FT_NULL && !str_eq(old, f.stage)) {
            if (out_report.n_grown < FT_MAX_FISH) {
                GrownEntry& g = out_report.grown[out_report.n_grown];
                g.uid = f.uid;
                str_copy(g.species, FT_ID_LEN, f.species);
                str_copy(g.from_stage, FT_STAGE_LEN, old);
                str_copy(g.to_stage, FT_STAGE_LEN, f.stage);
                ++out_report.n_grown;
            }
        }
    }

    // new_codex 去重 + 排序（对偶 sorted(set(new_codex))）
    // 插入排序 + 去重
    for (i32 i = 0; i < out_report.n_new_codex; ++i) {
        for (i32 j = i + 1; j < out_report.n_new_codex; ) {
            if (str_eq(out_report.new_codex[j], out_report.new_codex[i])) {
                // 删除 j
                for (i32 k = j; k < out_report.n_new_codex - 1; ++k) {
                    str_copy(out_report.new_codex[k], FT_ID_LEN,
                             out_report.new_codex[k + 1]);
                }
                --out_report.n_new_codex;
            } else {
                ++j;
            }
        }
    }
    // 排序
    for (i32 i = 1; i < out_report.n_new_codex; ++i) {
        char tmp[FT_ID_LEN];
        str_copy(tmp, FT_ID_LEN, out_report.new_codex[i]);
        i32 j = i;
        while (j > 0 && str_cmp(out_report.new_codex[j - 1], tmp) > 0) {
            str_copy(out_report.new_codex[j], FT_ID_LEN,
                     out_report.new_codex[j - 1]);
            --j;
        }
        str_copy(out_report.new_codex[j], FT_ID_LEN, tmp);
    }

    out_report.steps = steps;
    out_report.equivalent_min = equivalent_min;
    out_report.coins_gained_milli = st.coins_milli - coins_before;
    out_report.upkeep_milli = upkeep_total;
    out_report.water_after = st.tank.water;
    out_report.satiety_after = st.tank.satiety;

    st.bump_stat("offline_sec", static_cast<f64>(away));

    // ── S4 返回 ──
    // out_state 已通过别名 st 直接修改，无需额外拷贝
}

}  // namespace ft
