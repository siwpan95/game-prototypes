// state.cpp —— 见 state.h。◆ 对偶 fishtank/state.py

#include "state.h"

#include "ft_math.h"
#include "ft_str.h"
#include "rng.h"

namespace ft {

const i32 kSchemaVersion = 1;

// ══════════════════════════════════════════════════════════════
//  FishState
// ══════════════════════════════════════════════════════════════

void FishState::clear() {
    uid = 0;
    species[0] = '\0';
    born_at = 0;
    age_sec = 0.0;
    str_copy(stage, FT_STAGE_LEN, kStageFry);
    variant = false;
    nickname[0] = '\0';
    last_bred_at = 0;
    x = 0.5;
    y = 0.5;
    heading = 1.0;
}

void FishState::load_json(const JsonDoc& doc, i32 node) {
    uid = static_cast<i32>(doc.int_at(doc.member(node, "uid"), 0));
    str_copy(species, FT_ID_LEN, doc.str_at(doc.member(node, "species"), ""));
    born_at = doc.int_at(doc.member(node, "born_at"), 0);
    f64 age = doc.num_at(doc.member(node, "age_sec"), 0.0);
    age_sec = (age < 0.0) ? 0.0 : age;
    str_copy(stage, FT_STAGE_LEN, doc.str_at(doc.member(node, "stage"), kStageFry));
    variant = doc.bool_at(doc.member(node, "variant"), false);
    str_copy(nickname, FT_NAME_LEN, doc.str_at(doc.member(node, "nickname"), ""));
    last_bred_at = doc.int_at(doc.member(node, "last_bred_at"), 0);
    x = doc.num_at(doc.member(node, "x"), 0.5);
    y = doc.num_at(doc.member(node, "y"), 0.5);
    heading = doc.num_at(doc.member(node, "heading"), 1.0);
}

const char* FishState::display_name(const FishSpeciesDef* sp) const {
    if (nickname[0] != '\0') return nickname;
    if (sp != FT_NULL && sp->name_zh[0] != '\0') return sp->name_zh;
    return species;
}

// ══════════════════════════════════════════════════════════════
//  TankState
// ══════════════════════════════════════════════════════════════

void TankState::clear() {
    water = 100.0;
    capacity_level = 0;
    filter_level = 0;
    feeder_owned = false;
    feeder_on = true;
    satiety = 1.0;
    n_decors = 0;
}

void TankState::load_json(const JsonDoc& doc, i32 node) {
    water = doc.num_at(doc.member(node, "water"), 100.0);
    i32 cl = static_cast<i32>(doc.int_at(doc.member(node, "capacity_level"), 0));
    capacity_level = (cl < 0) ? 0 : cl;
    i32 fl = static_cast<i32>(doc.int_at(doc.member(node, "filter_level"), 0));
    filter_level = (fl < 0) ? 0 : fl;
    feeder_owned = doc.bool_at(doc.member(node, "feeder_owned"), false);
    feeder_on = doc.bool_at(doc.member(node, "feeder_on"), true);
    satiety = doc.num_at(doc.member(node, "satiety"), 1.0);

    // decors: 按原序读入，add_decor 保持 id 升序 + 去重
    n_decors = 0;
    i32 arr = doc.member(node, "decors");
    if (arr >= 0 && doc.at(arr).type == JSON_ARR) {
        for (i32 c = doc.at(arr).first; c >= 0; c = doc.at(c).next) {
            const char* did = doc.str_at(c, "");
            if (did[0] != '\0') {
                add_decor(did);
            }
        }
    }
}

bool TankState::add_decor(const char* id) {
    if (id == FT_NULL || id[0] == '\0') return false;
    for (i32 i = 0; i < n_decors; ++i) {
        i32 c = str_cmp(decors[i], id);
        if (c == 0) return false;  // 重复
        if (c > 0) {
            if (n_decors >= FT_MAX_DECOR_SLOT) return false;
            for (i32 j = n_decors; j > i; --j) {
                str_copy(decors[j], FT_ID_LEN, decors[j - 1]);
            }
            str_copy(decors[i], FT_ID_LEN, id);
            ++n_decors;
            return true;
        }
    }
    if (n_decors >= FT_MAX_DECOR_SLOT) return false;
    str_copy(decors[n_decors], FT_ID_LEN, id);
    ++n_decors;
    return true;
}

bool TankState::has_decor(const char* id) const {
    if (id == FT_NULL || id[0] == '\0') return false;
    for (i32 i = 0; i < n_decors; ++i) {
        if (str_eq(decors[i], id)) return true;
    }
    return false;
}

// ══════════════════════════════════════════════════════════════
//  GameState
// ══════════════════════════════════════════════════════════════

void GameState::clear() {
    schema = kSchemaVersion;
    saved_at_utc = 0;
    coins_milli = 0;
    rng_seed = 0;
    next_uid = 1;
    breed_timer = 0.0;
    tank.clear();
    n_fishes = 0;
    n_codex = 0;
    n_stats = 0;
    str_copy(settings_window_mode, FT_MODE_LEN, "tank");
    settings_muted = false;
    overflow = false;
}

i32 GameState::load_json(const JsonDoc& doc, i32 node) {
    clear();

    schema = static_cast<i32>(doc.int_at(doc.member(node, "schema"), kSchemaVersion));
    saved_at_utc = doc.int_at(doc.member(node, "saved_at_utc"), 0);
    i64 cm = doc.int_at(doc.member(node, "coins_milli"), 0);
    coins_milli = (cm < 0) ? 0 : cm;
    rng_seed = doc.uint_at(doc.member(node, "rng_seed"), 0);
    i32 nu = static_cast<i32>(doc.int_at(doc.member(node, "next_uid"), 1));
    next_uid = (nu < 1) ? 1 : nu;
    f64 bt = doc.num_at(doc.member(node, "breed_timer"), 0.0);
    breed_timer = (bt < 0.0) ? 0.0 : bt;

    // Tank
    tank.load_json(doc, doc.member(node, "tank"));

    // Fishes — 按 JSON 原序读入（repair 需要原序遍历）
    i32 fishes_arr = doc.member(node, "fishes");
    if (fishes_arr >= 0 && doc.at(fishes_arr).type == JSON_ARR) {
        for (i32 c = doc.at(fishes_arr).first; c >= 0; c = doc.at(c).next) {
            if (n_fishes >= FT_MAX_FISH) { overflow = true; break; }
            fishes[n_fishes].clear();
            fishes[n_fishes].load_json(doc, c);
            ++n_fishes;
        }
    }

    // Codex — 按 species 升序
    i32 codex_obj = doc.member(node, "codex");
    if (codex_obj >= 0 && doc.at(codex_obj).type == JSON_OBJ) {
        for (i32 c = doc.at(codex_obj).first; c >= 0; c = doc.at(c).next) {
            if (n_codex >= FT_MAX_CODEX) { overflow = true; break; }
            const char* sp = doc.at(c).key;
            i64 ts = doc.int_at(c, 0);
            i32 pos = n_codex;
            while (pos > 0 && str_cmp(codex[pos - 1].species, sp) > 0) {
                codex[pos] = codex[pos - 1];
                --pos;
            }
            str_copy(codex[pos].species, FT_ID_LEN, sp);
            codex[pos].unlocked_at = ts;
            ++n_codex;
        }
    }

    // Stats — 按 key 升序
    i32 stats_obj = doc.member(node, "stats");
    if (stats_obj >= 0 && doc.at(stats_obj).type == JSON_OBJ) {
        for (i32 c = doc.at(stats_obj).first; c >= 0; c = doc.at(c).next) {
            if (n_stats >= FT_MAX_STATS) { overflow = true; break; }
            const char* key = doc.at(c).key;
            f64 val = doc.num_at(c, 0.0);
            i32 pos = n_stats;
            while (pos > 0 && str_cmp(stats[pos - 1].key, key) > 0) {
                stats[pos] = stats[pos - 1];
                --pos;
            }
            str_copy(stats[pos].key, FT_ID_LEN, key);
            stats[pos].value = val;
            ++n_stats;
        }
    }

    // Settings
    i32 settings_obj = doc.member(node, "settings");
    str_copy(settings_window_mode, FT_MODE_LEN, "tank");
    settings_muted = false;
    if (settings_obj >= 0 && doc.at(settings_obj).type == JSON_OBJ) {
        const char* mode = doc.str_at(doc.member(settings_obj, "window_mode"), "tank");
        str_copy(settings_window_mode, FT_MODE_LEN, mode);
        settings_muted = doc.bool_at(doc.member(settings_obj, "muted"), false);
    }

    // Repair + sort
    i32 fixed = repair();
    sort_fishes();
    return fixed;
}

void GameState::deep_copy_to(GameState& dst) const {
    dst = *this;
}

FishState& GameState::fish_at(i32 i) {
    static FishState s_empty;
    if (i < 0 || i >= n_fishes) { s_empty.clear(); return s_empty; }
    return fishes[i];
}

const FishState& GameState::fish_at(i32 i) const {
    static FishState s_empty;
    if (i < 0 || i >= n_fishes) { s_empty.clear(); return s_empty; }
    return fishes[i];
}

FishState* GameState::get_fish(i32 uid) {
    for (i32 i = 0; i < n_fishes; ++i) {
        if (fishes[i].uid == uid) return &fishes[i];
    }
    return FT_NULL;
}

const FishState* GameState::get_fish(i32 uid) const {
    for (i32 i = 0; i < n_fishes; ++i) {
        if (fishes[i].uid == uid) return &fishes[i];
    }
    return FT_NULL;
}

bool GameState::has_codex(const char* species) const {
    if (species == FT_NULL || species[0] == '\0') return false;
    for (i32 i = 0; i < n_codex; ++i) {
        if (str_eq(codex[i].species, species)) return true;
    }
    return false;
}

const char* GameState::codex_species_at(i32 i) const {
    if (i < 0 || i >= n_codex) return "";
    return codex[i].species;
}

i32 GameState::capacity(const BalanceTable& bal) const {
    return bal.capacity_of(tank.capacity_level);
}

bool GameState::is_full(const BalanceTable& bal) const {
    return fish_count() >= capacity(bal);
}

f64 GameState::coins(const BalanceTable& bal) const {
    i32 scale = bal.coin_scale();
    if (scale == 0) scale = 1000;
    return static_cast<f64>(coins_milli) / static_cast<f64>(scale);
}

f64 GameState::stat(const char* key, f64 fallback) const {
    for (i32 i = 0; i < n_stats; ++i) {
        if (str_eq(stats[i].key, key)) return stats[i].value;
    }
    return fallback;
}

void GameState::bump_stat(const char* key, f64 delta) {
    for (i32 i = 0; i < n_stats; ++i) {
        if (str_eq(stats[i].key, key)) {
            stats[i].value += delta;
            return;
        }
    }
    if (n_stats >= FT_MAX_STATS) { overflow = true; return; }
    i32 pos = n_stats;
    while (pos > 0 && str_cmp(stats[pos - 1].key, key) > 0) {
        stats[pos] = stats[pos - 1];
        --pos;
    }
    str_copy(stats[pos].key, FT_ID_LEN, key);
    stats[pos].value = delta;
    ++n_stats;
}

i32 GameState::alloc_uid() {
    i32 uid = next_uid;
    next_uid = uid + 1;
    return uid;
}

bool GameState::codex_touch(const char* species, i64 when) {
    for (i32 i = 0; i < n_codex; ++i) {
        if (str_eq(codex[i].species, species)) return false;
    }
    if (n_codex >= FT_MAX_CODEX) { overflow = true; return false; }
    i32 pos = n_codex;
    while (pos > 0 && str_cmp(codex[pos - 1].species, species) > 0) {
        codex[pos] = codex[pos - 1];
        --pos;
    }
    str_copy(codex[pos].species, FT_ID_LEN, species);
    codex[pos].unlocked_at = when;
    ++n_codex;
    return true;
}

bool GameState::add_fish(const FishState& fish, i64 when) {
    if (n_fishes >= FT_MAX_FISH) { overflow = true; return false; }
    // 插入排序保持 uid 升序
    i32 pos = n_fishes;
    while (pos > 0 && fishes[pos - 1].uid > fish.uid) {
        fishes[pos] = fishes[pos - 1];
        --pos;
    }
    fishes[pos] = fish;
    ++n_fishes;
    return codex_touch(fish.species, when);
}

bool GameState::remove_fish(i32 uid) {
    for (i32 i = 0; i < n_fishes; ++i) {
        if (fishes[i].uid == uid) {
            for (i32 j = i; j < n_fishes - 1; ++j) {
                fishes[j] = fishes[j + 1];
            }
            --n_fishes;
            return true;
        }
    }
    return false;
}

i64 GameState::add_coins_milli(i64 delta) {
    coins_milli = llmax(0, coins_milli + delta);
    return coins_milli;
}

bool GameState::can_afford_milli(i64 price_milli) const {
    return price_milli >= 0 && coins_milli >= price_milli;
}

bool GameState::spend_milli(i64 price_milli) {
    if (!can_afford_milli(price_milli)) return false;
    coins_milli -= price_milli;
    return true;
}

i32 GameState::repair() {
    i32 fixed = 0;

    // 找最大 uid
    i32 max_uid = 0;
    for (i32 i = 0; i < n_fishes; ++i) {
        if (fishes[i].uid > 0) {
            max_uid = imax(max_uid, fishes[i].uid);
        }
    }
    i32 next_free = imax(imax(max_uid + 1, next_uid), 1);

    // 修 uid 重复 / 非正 / 坐标越界 / age 负
    for (i32 i = 0; i < n_fishes; ++i) {
        bool dup = (fishes[i].uid <= 0);
        if (!dup) {
            for (i32 j = 0; j < i; ++j) {
                if (fishes[j].uid == fishes[i].uid) { dup = true; break; }
            }
        }
        if (dup) {
            fishes[i].uid = next_free;
            ++next_free;
            ++fixed;
        }
        max_uid = imax(max_uid, fishes[i].uid);

        if (!(0.0 <= fishes[i].x && fishes[i].x <= 1.0)) {
            fishes[i].x = clamp_(fishes[i].x, 0.0, 1.0);
            ++fixed;
        }
        if (!(0.0 <= fishes[i].y && fishes[i].y <= 1.0)) {
            fishes[i].y = clamp_(fishes[i].y, 0.0, 1.0);
            ++fixed;
        }
        if (fishes[i].age_sec < 0.0) {
            fishes[i].age_sec = 0.0;
            ++fixed;
        }
    }

    if (next_uid <= max_uid) {
        next_uid = max_uid + 1;
        ++fixed;
    }

    // 图鉴补登
    for (i32 i = 0; i < n_fishes; ++i) {
        if (fishes[i].species[0] != '\0' && !has_codex(fishes[i].species)) {
            codex_touch(fishes[i].species, fishes[i].born_at);
            ++fixed;
        }
    }

    if (coins_milli < 0) {
        coins_milli = 0;
        ++fixed;
    }

    return fixed;
}

void GameState::sort_fishes() {
    // 插入排序（n <= 64）
    for (i32 i = 1; i < n_fishes; ++i) {
        FishState tmp = fishes[i];
        i32 j = i;
        while (j > 0 && fishes[j - 1].uid > tmp.uid) {
            fishes[j] = fishes[j - 1];
            --j;
        }
        fishes[j] = tmp;
    }
}

void GameState::new_game(const BalanceTable& bal, const FishLibrary& species_lib, i64 when) {
    clear();
    schema = kSchemaVersion;
    saved_at_utc = when;
    coins_milli = bal.intv("start.coins_milli", 0);
    rng_seed = static_cast<u64>(bal.intv("start.rng_seed", static_cast<i64>(kDefaultSeed)));
    next_uid = 1;
    breed_timer = 0.0;

    tank.water = bal.num("water.init", 100.0);
    tank.capacity_level = static_cast<i32>(bal.intv("start.capacity_level", 0));
    tank.filter_level = 0;
    tank.feeder_owned = false;
    tank.feeder_on = true;
    tank.satiety = bal.num("feeder.satiety_max", 1.0);
    tank.n_decors = 0;

    bump_stat("born", 0.0);
    bump_stat("bred", 0.0);
    bump_stat("sessions", 0.0);

    str_copy(settings_window_mode, FT_MODE_LEN, "tank");
    settings_muted = false;

    // 起始鱼种
    i32 fishes_arr = bal.node("start.fishes");
    if (fishes_arr >= 0 && bal.doc() != FT_NULL && bal.doc()->at(fishes_arr).type == JSON_ARR) {
        const JsonDoc* d = bal.doc();
        i32 n = imax(1, d->at(fishes_arr).count);
        i32 idx = 0;
        for (i32 c = d->at(fishes_arr).first; c >= 0; c = d->at(c).next) {
            const char* sid = d->str_at(c, "");
            if (sid[0] != '\0' && species_lib.get(sid) != FT_NULL) {
                FishState f;
                f.clear();
                f.uid = alloc_uid();
                str_copy(f.species, FT_ID_LEN, sid);
                f.born_at = when;
                f.age_sec = 0.0;
                str_copy(f.stage, FT_STAGE_LEN, kStageFry);
                f.variant = false;
                f.last_bred_at = 0;
                f.x = r6(0.3 + 0.4 * (static_cast<f64>(idx) + 0.5) / static_cast<f64>(n));
                f.y = 0.5;
                f.heading = (idx % 2 == 0) ? 1.0 : -1.0;
                add_fish(f, when);
                bump_stat("born", 1.0);
            }
            ++idx;
        }
    }
}

}  // namespace ft
