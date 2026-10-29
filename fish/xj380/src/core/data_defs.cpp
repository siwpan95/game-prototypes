// data_defs.cpp —— 见 data_defs.h。◆ 对偶 fishtank/data_defs.py

#include "data_defs.h"

#include "ft_math.h"
#include "ft_str.h"

namespace ft {

const char* const kStageFry      = "fry";
const char* const kStageJuvenile = "juvenile";
const char* const kStageAdult    = "adult";
const char* const kStageMature   = "mature";

const char* const kRarities[5] = { "R1", "R2", "R3", "R4", "R5" };
const char* const kStages[4]   = { "fry", "juvenile", "adult", "mature" };

namespace {

/// "#RRGGBB" → 0xRRGGBB；解析失败返回 fallback。
u32 parse_hex_color(const char* s, u32 fallback) {
    if (s == FT_NULL) {
        return fallback;
    }
    i32 i = 0;
    if (s[0] == '#') {
        i = 1;
    }
    u32 v = 0;
    i32 k = 0;
    for (; k < 6; ++k) {
        char c = s[i + k];
        i32 h;
        if (c >= '0' && c <= '9') {
            h = c - '0';
        } else if (c >= 'a' && c <= 'f') {
            h = c - 'a' + 10;
        } else if (c >= 'A' && c <= 'F') {
            h = c - 'A' + 10;
        } else {
            return fallback;
        }
        v = (v << 4) | static_cast<u32>(h);
    }
    return v;
}

/// 把 "prefix.key" 拼进 buf。
void join_path(char* buf, i32 cap, const char* prefix, const char* key) {
    i32 n = str_copy(buf, cap, prefix);
    (void)n;
    str_append(buf, cap, ".");
    str_append(buf, cap, key);
}

}  // namespace

// ══════════════════════════════════════════════════════════════
//  结构体
// ══════════════════════════════════════════════════════════════

void FishSpeciesDef::clear() {
    id[0] = '\0';
    name_zh[0] = '\0';
    str_copy(rarity, 8, "R1");
    group[0] = '\0';
    shape_length = 1.0;
    shape_height_ratio = 0.4;
    str_copy(shape_tail, 8, "fork");
    color_body = 0x8899AAU;
    color_belly = 0xB8C4CEU;
    color_fin = 0x9AA7B2U;
    color_pattern = 0x2B2F36U;
    str_copy(speed, 8, "normal");
}

void DecorDef::clear() {
    id[0] = '\0';
    name[0] = '\0';
    bonus = 0.0;
    price = 0;
    draw[0] = '\0';
    color0 = 0x808080U;
    color1 = 0x606060U;
    str_copy(anchor, 8, "bottom");
}

// ══════════════════════════════════════════════════════════════
//  FishLibrary
// ══════════════════════════════════════════════════════════════

FishLibrary::FishLibrary() : n_(0), n_groups_(0) {}

const FishSpeciesDef& FishLibrary::at(i32 i) const {
    static FishSpeciesDef s_empty;
    if (i < 0 || i >= n_) {
        s_empty.clear();
        return s_empty;
    }
    return items_[i];
}

const FishSpeciesDef* FishLibrary::get(const char* id) const {
    if (id == FT_NULL || id[0] == '\0') {
        return FT_NULL;
    }
    // items_ 按 id 升序 → 二分查找
    i32 lo = 0;
    i32 hi = n_ - 1;
    while (lo <= hi) {
        i32 mid = (lo + hi) / 2;
        i32 c = str_cmp(items_[mid].id, id);
        if (c == 0) {
            return &items_[mid];
        }
        if (c < 0) {
            lo = mid + 1;
        } else {
            hi = mid - 1;
        }
    }
    return FT_NULL;
}

i32 FishLibrary::load(const JsonDoc& doc, i32 array_root) {
    n_ = 0;
    n_groups_ = 0;
    const JsonNode& arr = doc.at(array_root);
    if (arr.type != JSON_ARR) {
        return 0;
    }
    for (i32 c = arr.first; c >= 0; c = doc.at(c).next) {
        if (n_ >= FT_MAX_SPECIES) {
            break;
        }
        if (doc.at(c).type != JSON_OBJ) {
            continue;
        }
        FishSpeciesDef d;
        d.clear();
        str_copy(d.id, FT_ID_LEN, doc.str_at(doc.member(c, "id"), ""));
        if (d.id[0] == '\0') {
            continue;  // 无 id 的条目直接跳过（容错，不崩）
        }
        str_copy(d.name_zh, FT_NAME_LEN, doc.str_at(doc.member(c, "name_zh"), ""));
        str_copy(d.rarity, 8, doc.str_at(doc.member(c, "rarity"), "R1"));
        str_copy(d.group, FT_ID_LEN, doc.str_at(doc.member(c, "group"), ""));

        i32 shape = doc.member(c, "shape");
        d.shape_length = doc.num_at(doc.member(shape, "length"), 1.0);
        d.shape_height_ratio = doc.num_at(doc.member(shape, "height_ratio"), 0.4);
        str_copy(d.shape_tail, 8, doc.str_at(doc.member(shape, "tail"), "fork"));

        i32 color = doc.member(c, "color");
        d.color_body = parse_hex_color(doc.str_at(doc.member(color, "body"), ""), 0x8899AAU);
        d.color_belly = parse_hex_color(doc.str_at(doc.member(color, "belly"), ""), 0xB8C4CEU);
        d.color_fin = parse_hex_color(doc.str_at(doc.member(color, "fin"), ""), 0x9AA7B2U);
        d.color_pattern = parse_hex_color(doc.str_at(doc.member(color, "pattern"), ""), 0x2B2F36U);

        i32 beh = doc.member(c, "behavior");
        str_copy(d.speed, 8, doc.str_at(doc.member(beh, "speed"), "normal"));

        // ★ 插入排序保持 id 升序（对偶 Python 各处的 sorted(...)）
        i32 pos = n_;
        while (pos > 0 && str_cmp(items_[pos - 1].id, d.id) > 0) {
            items_[pos] = items_[pos - 1];
            --pos;
        }
        items_[pos] = d;
        ++n_;
    }
    rebuild_groups();
    return n_;
}

void FishLibrary::rebuild_groups() {
    n_groups_ = 0;
    for (i32 i = 0; i < n_; ++i) {
        const char* g = items_[i].group;
        if (g[0] == '\0') {
            continue;  // 对偶 Python：`if f.group:` 才登记
        }
        bool seen = false;
        for (i32 k = 0; k < n_groups_; ++k) {
            if (str_eq(groups_[k], g)) {
                seen = true;
                break;
            }
        }
        if (seen || n_groups_ >= FT_MAX_GROUP) {
            continue;
        }
        // 插入排序保持族群名升序（对偶 sorted(by_group.keys())）
        i32 pos = n_groups_;
        while (pos > 0 && str_cmp(groups_[pos - 1], g) > 0) {
            str_copy(groups_[pos], FT_ID_LEN, groups_[pos - 1]);
            --pos;
        }
        str_copy(groups_[pos], FT_ID_LEN, g);
        ++n_groups_;
    }
}

const char* FishLibrary::group_at(i32 i) const {
    if (i < 0 || i >= n_groups_) {
        return "";
    }
    return groups_[i];
}

i32 FishLibrary::group_member_count(const char* group) const {
    i32 n = 0;
    for (i32 i = 0; i < n_; ++i) {
        if (str_eq(items_[i].group, group)) {
            ++n;
        }
    }
    return n;
}

const FishSpeciesDef* FishLibrary::group_member_at(const char* group, i32 k) const {
    i32 n = 0;
    for (i32 i = 0; i < n_; ++i) {
        if (str_eq(items_[i].group, group)) {
            if (n == k) {
                return &items_[i];
            }
            ++n;
        }
    }
    return FT_NULL;
}

// ══════════════════════════════════════════════════════════════
//  DecorLibrary
// ══════════════════════════════════════════════════════════════

DecorLibrary::DecorLibrary() : n_(0) {}

const DecorDef& DecorLibrary::at(i32 i) const {
    static DecorDef s_empty;
    if (i < 0 || i >= n_) {
        s_empty.clear();
        return s_empty;
    }
    return items_[i];
}

const DecorDef* DecorLibrary::get(const char* id) const {
    if (id == FT_NULL || id[0] == '\0') {
        return FT_NULL;
    }
    i32 lo = 0;
    i32 hi = n_ - 1;
    while (lo <= hi) {
        i32 mid = (lo + hi) / 2;
        i32 c = str_cmp(items_[mid].id, id);
        if (c == 0) {
            return &items_[mid];
        }
        if (c < 0) {
            lo = mid + 1;
        } else {
            hi = mid - 1;
        }
    }
    return FT_NULL;
}

f64 DecorLibrary::bonus_of(const char* id) const {
    const DecorDef* d = get(id);
    return (d != FT_NULL) ? d->bonus : 0.0;
}

i32 DecorLibrary::load(const JsonDoc& doc, i32 array_root) {
    n_ = 0;
    const JsonNode& arr = doc.at(array_root);
    if (arr.type != JSON_ARR) {
        return 0;
    }
    for (i32 c = arr.first; c >= 0; c = doc.at(c).next) {
        if (n_ >= FT_MAX_DECOR_DEF) {
            break;
        }
        if (doc.at(c).type != JSON_OBJ) {
            continue;
        }
        DecorDef d;
        d.clear();
        str_copy(d.id, FT_ID_LEN, doc.str_at(doc.member(c, "id"), ""));
        if (d.id[0] == '\0') {
            continue;
        }
        str_copy(d.name, FT_NAME_LEN, doc.str_at(doc.member(c, "name"), ""));
        d.bonus = doc.num_at(doc.member(c, "bonus"), 0.0);
        d.price = static_cast<i32>(doc.int_at(doc.member(c, "price"), 0));
        str_copy(d.draw, FT_ID_LEN, doc.str_at(doc.member(c, "draw"), ""));
        i32 col = doc.member(c, "color");
        d.color0 = parse_hex_color(doc.str_at(doc.elem(col, 0), ""), 0x808080U);
        d.color1 = parse_hex_color(doc.str_at(doc.elem(col, 1), ""), 0x606060U);
        str_copy(d.anchor, 8, doc.str_at(doc.member(c, "anchor"), "bottom"));

        i32 pos = n_;
        while (pos > 0 && str_cmp(items_[pos - 1].id, d.id) > 0) {
            items_[pos] = items_[pos - 1];
            --pos;
        }
        items_[pos] = d;
        ++n_;
    }
    return n_;
}

// ══════════════════════════════════════════════════════════════
//  BalanceTable
// ══════════════════════════════════════════════════════════════

BalanceTable::BalanceTable() : doc_(FT_NULL), root_(-1) {}

void BalanceTable::bind(const JsonDoc* doc, i32 root) {
    doc_ = doc;
    root_ = root;
}

i32 BalanceTable::node(const char* path) const {
    if (doc_ == FT_NULL) {
        return -1;
    }
    return doc_->path(root_, path);
}

f64 BalanceTable::num(const char* path, f64 fallback) const {
    if (doc_ == FT_NULL) {
        return fallback;
    }
    return doc_->num_at(doc_->path(root_, path), fallback);
}

i64 BalanceTable::intv(const char* path, i64 fallback) const {
    if (doc_ == FT_NULL) {
        return fallback;
    }
    return doc_->int_at(doc_->path(root_, path), fallback);
}

const char* BalanceTable::text(const char* path, const char* fallback) const {
    if (doc_ == FT_NULL) {
        return fallback;
    }
    return doc_->str_at(doc_->path(root_, path), fallback);
}

f64 BalanceTable::num2(const char* prefix, const char* key, f64 fallback) const {
    char buf[96];
    join_path(buf, 96, prefix, key);
    return num(buf, fallback);
}

i64 BalanceTable::intv2(const char* prefix, const char* key, i64 fallback) const {
    char buf[96];
    join_path(buf, 96, prefix, key);
    return intv(buf, fallback);
}

// 下面每个默认值都与 fishtank/data_defs.py 的 _FALLBACK / 实参默认值逐一对应。
f64 BalanceTable::base_income(const char* rarity) const {
    return num2("economy.base_income", rarity, 0.0);
}

i64 BalanceTable::growth_cycle_sec(const char* rarity) const {
    return intv2("growth.cycle_sec", rarity, 1);
}

f64 BalanceTable::threshold(const char* stage) const {
    // 对偶 economy.py::stage_of 里的 th.get(STAGE_x, 默认)
    f64 fb = 1.45;
    if (str_eq(stage, kStageFry)) {
        fb = 0.15;
    } else if (str_eq(stage, kStageJuvenile)) {
        fb = 0.45;
    }
    return num2("growth.thresholds", stage, fb);
}

f64 BalanceTable::stage_coef(const char* stage) const {
    return num2("growth.stage_coef", stage, 1.0);
}

f64 BalanceTable::stage_scale(const char* stage) const {
    return num2("growth.stage_scale", stage, 1.0);
}

i32 BalanceTable::coin_scale() const {
    return static_cast<i32>(intv("economy.coin_scale", 1000));
}

f64 BalanceTable::bonus_cap() const {
    return num("economy.bonus_cap", 0.40);
}

f64 BalanceTable::water_min() const {
    return num("water.min", 50.0);
}

f64 BalanceTable::water_max() const {
    return num("water.max", 100.0);
}

f64 BalanceTable::quality_floor() const {
    return num("water.quality_floor", 0.5);
}

f64 BalanceTable::filter_gain(i32 level) const {
    // 对偶 BalanceTable.filter_gain：越界钳到合法范围
    i32 arr = node("water.filter_gain");
    if (doc_ == FT_NULL || doc_->at(arr).type != JSON_ARR || doc_->at(arr).count <= 0) {
        static const f64 kFb[4] = { 0.0, 0.2, 0.5, 1.2 };
        i32 idx = imax(0, imin(level, 3));
        return kFb[idx];
    }
    i32 n = doc_->at(arr).count;
    i32 idx = imax(0, imin(level, n - 1));
    return doc_->num_at(doc_->elem(arr, idx), 0.0);
}

i32 BalanceTable::capacity_of(i32 level) const {
    i32 arr = node("shop.capacity");
    if (doc_ == FT_NULL || doc_->at(arr).type != JSON_ARR || doc_->at(arr).count <= 0) {
        return 6;
    }
    i32 n = doc_->at(arr).count;
    i32 idx = imax(0, imin(level, n - 1));
    return static_cast<i32>(doc_->int_at(doc_->elem(arr, idx), 6));
}

f64 BalanceTable::group_bonus() const {
    return num("codex.group_bonus", 0.08);
}

i64 BalanceTable::hard_cap_sec() const {
    return intv("offline.hard_cap_sec", 315360000);
}

i32 BalanceTable::offline_segment_count() const {
    i32 arr = node("offline.segments");
    if (doc_ == FT_NULL || doc_->at(arr).type != JSON_ARR) {
        return 0;
    }
    return doc_->at(arr).count;
}

void BalanceTable::offline_segment(i32 i, f64* lo, f64* hi, bool* has_hi, f64* k) const {
    *lo = 0.0;
    *hi = 0.0;
    *has_hi = false;
    *k = 1.0;
    if (doc_ == FT_NULL) {
        return;
    }
    i32 arr = node("offline.segments");
    i32 seg = doc_->elem(arr, i);
    const JsonNode& sn = doc_->at(seg);
    if (sn.type != JSON_ARR || sn.count < 3) {
        // 对偶 Python：`if not isinstance(seg,(list,tuple)) or len(seg)<3: continue`
        *k = -1.0;  // 哨兵：调用方据此跳过本段
        return;
    }
    i32 n0 = doc_->elem(seg, 0);
    i32 n1 = doc_->elem(seg, 1);
    i32 n2 = doc_->elem(seg, 2);
    // lo：None → 0.0
    *lo = doc_->present(n0) ? doc_->num_at(n0, 0.0) : 0.0;
    // hi：None → 无穷
    if (doc_->present(n1)) {
        *has_hi = true;
        *hi = doc_->num_at(n1, 0.0);
    }
    *k = doc_->num_at(n2, 1.0);
}

// ══════════════════════════════════════════════════════════════
//  枚举工具
// ══════════════════════════════════════════════════════════════

i32 rarity_index(const char* rarity) {
    for (i32 i = 0; i < 5; ++i) {
        if (str_eq(kRarities[i], rarity)) {
            return i;
        }
    }
    return 0;
}

const char* rarity_at(i32 index) {
    i32 i = imax(0, imin(index, 4));
    return kRarities[i];
}

i32 stage_index(const char* stage) {
    for (i32 i = 0; i < 4; ++i) {
        if (str_eq(kStages[i], stage)) {
            return i;
        }
    }
    return 0;
}

}  // namespace ft
