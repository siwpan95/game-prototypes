// golden_runner.cpp —— P0 验收：与 Python 黄金用例逐位比对
//
// 用宿主 g++ 编译：读 offline_cases.json，对每个用例跑 settle_offline，
// 与 Python 端期望值逐字段比对。全程不依赖 XJ380 SDK，只在宿主环境运行。
//
// 运行（素材根不再写死）：tools/golden_runner [fish仓根]  或  设 FISH_ROOT=<fish仓根>
//
// 编译（在 xj380/ 目录下）：
//   g++ -std=c++11 -fno-exceptions -fno-rtti -ffp-contract=off \
//       -I src/core tools/golden_runner.cpp \
//       src/core/data_defs.cpp src/core/ft_math.cpp src/core/ft_str.cpp \
//       src/core/json_min.cpp src/core/rng.cpp src/core/state.cpp \
//       src/core/economy.cpp src/core/offline.cpp \
//       -o tools/golden_runner

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "ft_types.h"
#include "ft_math.h"
#include "ft_str.h"
#include "json_min.h"
#include "data_defs.h"
#include "rng.h"
#include "state.h"
#include "economy.h"
#include "offline.h"

using namespace ft;

// ── 文件读写 ──────────────────────────────────────────────────

static char* read_file(const char* path, i32* out_len) {
    FILE* f = fopen(path, "rb");
    if (f == NULL) {
        fprintf(stderr, "ERROR: cannot open %s\n", path);
        return NULL;
    }
    if (fseek(f, 0, SEEK_END) != 0) { fclose(f); return NULL; }
    long sz = ftell(f);
    if (sz < 0) { fclose(f); return NULL; }
    rewind(f);
    char* buf = new char[sz + 1];
    if (buf == NULL) { fclose(f); return NULL; }
    size_t rd = fread(buf, 1, (size_t)sz, f);
    fclose(f);
    buf[rd] = '\0';
    *out_len = (i32)rd;
    return buf;
}

// ── 字符串工具 ────────────────────────────────────────────────

static int parse_int_str(const char* s) {
    int v = 0;
    while (*s >= '0' && *s <= '9') {
        v = v * 10 + (int)(*s - '0');
        ++s;
    }
    return v;
}

static bool feq(f64 a, f64 b, f64 tol) {
    f64 d = a - b;
    return (d >= -tol) && (d <= tol);
}

// ── 比较 ──────────────────────────────────────────────────────

static int compare_case(const JsonDoc& doc, i32 case_node,
                        const BalanceTable& bal,
                        const FishLibrary& species_lib,
                        const DecorLibrary& decor_lib,
                        bool verbose) {
    const char* name = doc.str_at(doc.member(case_node, "name"), "?");
    const char* note = doc.str_at(doc.member(case_node, "note"), "");
    i64 away_req = doc.int_at(doc.member(case_node, "away_sec_requested"), 0);

    // 构建初始 GameState
    i32 input_node = doc.member(case_node, "input");
    GameState state;
    state.load_json(doc, input_node);

    // 计算 now
    i64 saved_at = state.saved_at_utc;
    i64 now = saved_at + away_req;

    // ★ 运行 settle_offline
    GameState new_state;
    OfflineReport report;
    settle_offline(state, now, bal, species_lib, decor_lib,
                   new_state, report);

    // 获取期望值
    i32 exp = doc.member(case_node, "expect");
    int errors = 0;

#define CHECK_INT(field, fn) do { \
    i64 expected = doc.int_at(doc.member(exp, field), -999999); \
    i64 actual = (i64)(fn); \
    if (expected != -999999 && actual != expected) { \
        if (verbose || errors == 0) \
            fprintf(stderr, "  MISMATCH %s: expected %lld, got %lld\n", \
                    field, (long long)expected, (long long)actual); \
        ++errors; \
    } \
} while(0)

#define CHECK_U64(field, fn) do { \
    u64 expected = doc.uint_at(doc.member(exp, field), 0); \
    u64 actual = (u64)(fn); \
    /* 只检查期望值非零的情况 */ \
    i32 exp_node = doc.member(exp, field); \
    if (exp_node >= 0 && actual != expected) { \
        if (verbose || errors == 0) \
            fprintf(stderr, "  MISMATCH %s: expected %llu, got %llu\n", \
                    field, (unsigned long long)expected, (unsigned long long)actual); \
        ++errors; \
    } \
} while(0)

#define CHECK_F64(field, fn, tol) do { \
    f64 expected = doc.num_at(doc.member(exp, field), -999.0); \
    f64 actual = (fn); \
    if (expected > -998.0 && !feq(actual, expected, tol)) { \
        if (verbose || errors == 0) \
            fprintf(stderr, "  MISMATCH %s: expected %.12g, got %.12g (diff=%g)\n", \
                    field, expected, actual, (double)(actual - expected)); \
        ++errors; \
    } \
} while(0)

    CHECK_INT("away_sec", report.away_sec);
    {
        bool exp_capped = doc.bool_at(doc.member(exp, "capped"), false);
        if (report.capped != exp_capped) {
            fprintf(stderr, "  MISMATCH capped: expected %d, got %d\n",
                    (int)exp_capped, (int)report.capped);
            ++errors;
        }
    }
    {
        bool exp_cr = doc.bool_at(doc.member(exp, "clock_rollback"), false);
        if (report.clock_rollback != exp_cr) {
            fprintf(stderr, "  MISMATCH clock_rollback: expected %d, got %d\n",
                    (int)exp_cr, (int)report.clock_rollback);
            ++errors;
        }
    }
    CHECK_INT("steps", report.steps);
    CHECK_F64("equivalent_min", report.equivalent_min, 1e-4);
    CHECK_INT("coins_gained_milli", report.coins_gained_milli);
    CHECK_INT("coins_after_milli", new_state.coins_milli);
    CHECK_F64("water_after", new_state.tank.water, 1e-4);
    CHECK_F64("satiety_after", new_state.tank.satiety, 1e-4);
    CHECK_INT("fish_count_after", new_state.n_fishes);
    // rng_seed_after: 直接读 JsonNode::umag 以避免 uint_at 对大 u64 的精度丢失
    {
        i32 rng_node = doc.member(exp, "rng_seed_after");
        if (rng_node >= 0) {
            const JsonNode& rng_n = doc.at(rng_node);
            if (rng_n.type == JSON_NUM && rng_n.is_int && !rng_n.neg) {
                u64 expected = rng_n.umag;
                if (new_state.rng_seed != expected) {
                    fprintf(stderr, "  MISMATCH rng_seed_after: expected %llu, got %llu\n",
                            (unsigned long long)expected, (unsigned long long)new_state.rng_seed);
                    ++errors;
                }
            } else {
                // fallback
                u64 expected = doc.uint_at(rng_node, 0);
                if (new_state.rng_seed != expected) {
                    fprintf(stderr, "  MISMATCH rng_seed_after: expected %llu, got %llu\n",
                            (unsigned long long)expected, (unsigned long long)new_state.rng_seed);
                    ++errors;
                }
            }
        }
    }
    CHECK_INT("next_uid_after", new_state.next_uid);
    CHECK_INT("grown_count", report.n_grown);

    // stages_after: dict uid->stage
    {
        i32 stages_obj = doc.member(exp, "stages_after");
        if (stages_obj >= 0 && doc.at(stages_obj).type == JSON_OBJ) {
            i32 exp_count = doc.at(stages_obj).count;
            if (new_state.n_fishes != exp_count) {
                fprintf(stderr, "  MISMATCH stages_after count: expected %d, got %d\n",
                        exp_count, new_state.n_fishes);
                ++errors;
            } else {
                for (i32 c = doc.at(stages_obj).first; c >= 0; c = doc.at(c).next) {
                    int uid = parse_int_str(doc.at(c).key);
                    const char* exp_stage = doc.str_at(c, "");
                    const FishState* f = new_state.get_fish(uid);
                    if (f == NULL) {
                        fprintf(stderr, "  MISMATCH stages_after: uid %d not found\n", uid);
                        ++errors;
                        break;
                    }
                    if (!ft::str_eq(f->stage, exp_stage)) {
                        fprintf(stderr, "  MISMATCH stages_after[%d]: expected %s, got %s\n",
                                uid, exp_stage, f->stage);
                        ++errors;
                        break;
                    }
                }
            }
        }
    }

    // born_species: array of strings
    {
        i32 born_arr = doc.member(exp, "born_species");
        i32 exp_born_count = 0;
        if (born_arr >= 0 && doc.at(born_arr).type == JSON_ARR)
            exp_born_count = doc.at(born_arr).count;
        if (report.n_born != exp_born_count) {
            fprintf(stderr, "  MISMATCH born_species count: expected %d, got %d\n",
                    exp_born_count, report.n_born);
            ++errors;
        } else if (born_arr >= 0) {
            i32 idx = 0;
            for (i32 c = doc.at(born_arr).first; c >= 0; c = doc.at(c).next) {
                const char* exp_sp = doc.str_at(c, "");
                if (!ft::str_eq(report.born[idx].species, exp_sp)) {
                    fprintf(stderr, "  MISMATCH born_species[%d]: expected %s, got %s\n",
                            idx, exp_sp, report.born[idx].species);
                    ++errors;
                    break;
                }
                ++idx;
            }
        }
    }

    return errors;
}

// ── 素材根解析（2026-09-23 去本地化）──────────────────────────
// 原实现写死 "原路径"，该目录已不存在（fish 仓现为 <工作区>/repos/fish）。
// 解析顺序：argv[1] → 环境变量 FISH_ROOT → 当前工作目录。
static const char* fish_root(int argc, char** argv) {
    if (argc > 1 && argv[1] != NULL && argv[1][0] != '\0') return argv[1];
    const char* env = getenv("FISH_ROOT");
    if (env != NULL && env[0] != '\0') return env;
    return ".";
}

// ── main ──────────────────────────────────────────────────────

int main(int argc, char** argv) {
    const char* root = fish_root(argc, argv);
    char p_balance[512], p_fish[512], p_decor[512], p_cases[512];
    snprintf(p_balance, sizeof(p_balance), "%s/data/balance.json", root);
    snprintf(p_fish,    sizeof(p_fish),    "%s/data/fish_data.json", root);
    snprintf(p_decor,   sizeof(p_decor),   "%s/data/decor_data.json", root);
    snprintf(p_cases,   sizeof(p_cases),   "%s/tests/golden/offline_cases.json", root);

    // 1. 读取文件
    i32 len;
    char* balance_text = read_file(p_balance, &len);
    char* fish_text    = read_file(p_fish, &len);
    char* decor_text   = read_file(p_decor, &len);
    char* cases_text   = read_file(p_cases, &len);

    if (!balance_text || !fish_text || !decor_text || !cases_text) {
        fprintf(stderr, "FATAL: cannot read data files under root=%s\n", root);
        fprintf(stderr, "       用法: golden_runner [fish仓根]   或设 FISH_ROOT=<fish仓根>\n");
        return 2;
    }

    // 2. 解析 JSON
    // 节点池：静态分配，足够容纳全部 JSON 节点
    static JsonNode balance_pool[4096];
    static JsonNode fish_pool[8192];
    static JsonNode decor_pool[2048];
    static JsonNode cases_pool[16384];

    JsonDoc balance_doc; balance_doc.init(balance_pool, 4096);
    JsonDoc fish_doc;    fish_doc.init(fish_pool, 8192);
    JsonDoc decor_doc;   decor_doc.init(decor_pool, 2048);
    JsonDoc cases_doc;   cases_doc.init(cases_pool, 16384);

    if (!balance_doc.parse(balance_text, (i32)strlen(balance_text))) {
        fprintf(stderr, "FATAL: balance.json parse error: %s\n", balance_doc.error());
        return 2;
    }
    if (!fish_doc.parse(fish_text, (i32)strlen(fish_text))) {
        fprintf(stderr, "FATAL: fish_data.json parse error: %s\n", fish_doc.error());
        return 2;
    }
    if (!decor_doc.parse(decor_text, (i32)strlen(decor_text))) {
        fprintf(stderr, "FATAL: decor_data.json parse error: %s\n", decor_doc.error());
        return 2;
    }
    if (!cases_doc.parse(cases_text, (i32)strlen(cases_text))) {
        fprintf(stderr, "FATAL: offline_cases.json parse error: %s\n", cases_doc.error());
        return 2;
    }

    printf("=== golden_runner: JSON parsed OK ===\n");
    printf("  balance: %d nodes, fish: %d nodes, decor: %d nodes, cases: %d nodes\n",
           balance_doc.node_used(), fish_doc.node_used(),
           decor_doc.node_used(), cases_doc.node_used());

    // 3. 装载数据
    BalanceTable bal;
    bal.bind(&balance_doc, balance_doc.root());
    FishLibrary species_lib;
    species_lib.load(fish_doc, fish_doc.root());
    DecorLibrary decor_lib;
    decor_lib.load(decor_doc, decor_doc.root());
    printf("  species: %d, decor: %d\n", species_lib.count(), decor_lib.count());

    // 4. 运行所有用例
    i32 cases_arr = cases_doc.member(cases_doc.root(), "cases");
    if (cases_arr < 0 || cases_doc.at(cases_arr).type != JSON_ARR) {
        fprintf(stderr, "FATAL: no 'cases' array\n");
        return 2;
    }

    int total_pass = 0;
    int total_fail = 0;
    int case_idx = 0;

    for (i32 c = cases_doc.at(cases_arr).first; c >= 0;
         c = cases_doc.at(c).next) {
        ++case_idx;
        const char* name = cases_doc.str_at(cases_doc.member(c, "name"), "?");
        const char* note = cases_doc.str_at(cases_doc.member(c, "note"), "");

        printf("\n[%2d] %s", case_idx, name);
        if (note[0]) printf(" — %s", note);
        printf("\n");

        int err = compare_case(cases_doc, c, bal, species_lib, decor_lib,
                               /*verbose=*/true);

        if (err == 0) {
            printf("  PASS\n");
            ++total_pass;
        } else {
            printf("  FAIL (%d mismatch(es))\n", err);
            ++total_fail;
        }
    }

    // 5. 总结
    printf("\n========================================\n");
    printf("  TOTAL: %d passed, %d failed\n", total_pass, total_fail);
    printf("========================================\n");

    // 清理
    delete[] balance_text;
    delete[] fish_text;
    delete[] decor_text;
    delete[] cases_text;

    return total_fail > 0 ? 1 : 0;
}
