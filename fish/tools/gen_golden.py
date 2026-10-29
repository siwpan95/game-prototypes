"""生成离线结算金标准用例 `tests/golden/offline_cases.json`。

用法::

    python tools/gen_golden.py            # 生成/覆盖金标准
    python tools/gen_golden.py --check    # 只校验当前代码是否仍与金标准一致

🔴 金标准的意义：这份 JSON 是 **XJ380 C++ 端的验收基准**。
   C++ 端读入同样的 `input` 与同样的 `data/balance.json`，
   必须逐字段算出同样的 `expect`。任何一项对不上就是双端不一致。

🔴 生成时使用固定时间锚点，绝不调用 `time.time()`。
"""

import argparse
import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from fishtank.data_defs import load_all                      # noqa: E402
from fishtank.offline import settle_offline                  # noqa: E402
from fishtank.state import FishState, GameState, TankState   # noqa: E402

T0 = 1700000000
"""固定锚点，与 tests/conftest.py 保持一致。"""

OUT_PATH = os.path.join(_ROOT, "tests", "golden", "offline_cases.json")


def _fish(uid, species, age_sec, stage, x=0.5, y=0.5, last_bred_at=0):
    """构造一条确定的鱼。"""
    return FishState(uid=uid, species=species, born_at=T0 - int(age_sec),
                     age_sec=float(age_sec), stage=stage, variant=False,
                     nickname="", last_bred_at=int(last_bred_at),
                     x=x, y=y, heading=1.0)


def _state(coins_milli=0, water=100.0, fishes=(), decors=(), filter_level=0,
           feeder=False, satiety=1.0, capacity_level=0, seed=88172645463325252,
           next_uid=100, codex=None):
    """构造一份确定的 GameState。"""
    st = GameState(
        schema=1, saved_at_utc=T0, coins_milli=int(coins_milli),
        rng_seed=int(seed), next_uid=int(next_uid), breed_timer=0.0,
        tank=TankState(water=water, capacity_level=capacity_level,
                       filter_level=filter_level, feeder_owned=feeder,
                       feeder_on=feeder, satiety=satiety,
                       decors=sorted(decors)),
        fishes=list(fishes),
        codex=dict(codex or {}),
        stats={}, settings={},
    )
    for f in st.fishes:
        st.codex.setdefault(f.species, f.born_at)
    return st


def build_cases():
    """构造全部金标准输入用例。

    :returns: [(case_name, GameState, away_sec, note), ...]
    """
    cases = []

    # C01 空缸：任何时长都不产币（除零 / 空集合边界）
    cases.append(("empty_tank_1d", _state(), 86400,
                  "空缸离线 1 天：收益必须为 0，不得因除零崩溃"))

    # C02 单条成鱼、满水、无过滤、无繁殖可能（只有 1 条）
    cases.append(("single_adult_1h",
                  _state(fishes=[_fish(1, "neon_tetra", 7200 * 0.6, "adult")]),
                  3600, "单条 R1 成鱼离线 1 小时（全速段）"))

    # C03 ★ 金标准：1 天离线 = 17.6 等效小时
    cases.append(("single_mature_1d",
                  _state(fishes=[_fish(1, "neon_tetra", 7200 * 3, "mature")],
                         filter_level=3),
                  86400, "★ 1 天离线：等效 1056 分钟 = 17.6 小时"))

    # C04 ★ 金标准：7 天离线 = 68.0 等效小时（与 C03 之比 = 3.86）
    cases.append(("single_mature_7d",
                  _state(fishes=[_fish(1, "neon_tetra", 7200 * 3, "mature")],
                         filter_level=3),
                  604800, "★ 7 天离线：等效 4080 分钟 = 68.0 小时"))

    # C05 水质自然下滑（无过滤 + 多鱼）：验证 quality_floor 兜底
    cases.append(("water_decay_floor_1d",
                  _state(fishes=[_fish(i, "zebra_danio", 21600 * 3, "mature")
                                 for i in range(1, 7)],
                         capacity_level=1),
                  86400, "6 条鱼无过滤离线 1 天：水质应触底 50 且收益仍为正"))

    # C06 过滤器把水质拉满：验证水质上限钳制
    cases.append(("filter_keeps_water_1d",
                  _state(water=60.0, filter_level=3,
                         fishes=[_fish(1, "guppy", 7200 * 3, "mature")]),
                  86400, "高级过滤离线 1 天：水质回到 100 并被钳住"))

    # C07 自动投食器：验证维护费扣除且净收益 >= 0
    cases.append(("feeder_upkeep_1d",
                  _state(fishes=[_fish(i, "guppy", 7200 * 3, "mature")
                                 for i in range(1, 5)],
                         feeder=True, satiety=0.2, filter_level=2,
                         capacity_level=1),
                  86400, "开投食器离线 1 天：饱食度被自动拉起，净收益不为负"))

    # C08 成长跨阶段：fry -> mature
    cases.append(("growth_fry_to_mature",
                  _state(fishes=[_fish(1, "neon_tetra", 0.0, "fry")]),
                  7200 * 2, "鱼苗离线 4 小时：应跨越 fry→juvenile→adult"))

    # C09 繁殖：两条同种成鱼 + 容量足够
    cases.append(("breeding_pair_1d",
                  _state(fishes=[_fish(1, "neon_tetra", 7200 * 3, "mature", x=0.4),
                                 _fish(2, "neon_tetra", 7200 * 3, "mature", x=0.6)],
                         filter_level=3),
                  86400, "同种成鱼对离线 1 天：应有确定数量的新生鱼"))

    # C10 装饰 + 图鉴加成封顶
    cases.append(("bonus_capped_1d",
                  _state(fishes=[_fish(1, "neon_tetra", 7200 * 3, "mature")],
                         decors=["pebble_substrate", "lucky_shrine"],
                         filter_level=3),
                  86400, "带装饰离线 1 天：加成参与产出且不超过 bonus_cap"))

    # C11 时钟回拨：不结算、不丢币、锚点不动
    cases.append(("clock_rollback",
                  _state(coins_milli=123456,
                         fishes=[_fish(1, "neon_tetra", 7200 * 3, "mature")]),
                  -5000, "系统时钟回拨：收益为 0、金币不减、锚点保持不变"))

    # C12 零时长
    cases.append(("zero_elapsed",
                  _state(coins_milli=1000,
                         fishes=[_fish(1, "neon_tetra", 7200 * 3, "mature")]),
                  0, "离线 0 秒：什么都不该发生"))

    # C13 超硬上限：应被 hard_cap_sec 截断
    cases.append(("beyond_hard_cap",
                  _state(fishes=[_fish(1, "neon_tetra", 7200 * 3, "mature")],
                         filter_level=3),
                  315360000 + 12345, "超过 hard_cap：away 被截断且 capped=True"))

    # C14 R5 高稀有度 + 满配
    cases.append(("r5_full_kit_3d",
                  _state(fishes=[_fish(1, "coelacanth", 172800 * 3, "mature")],
                         filter_level=3, feeder=True, capacity_level=2,
                         decors=["pebble_substrate"]),
                  259200, "R5 成鱼满配离线 3 天"))

    return cases


def make_golden():
    """跑一遍全部用例，生成金标准结构。"""
    bal, species, decor, _text = load_all(os.path.join(_ROOT, "data"))
    problems = bal.validate()
    if problems:
        raise SystemExit("balance.json 校验未通过，拒绝生成金标准：\n  "
                         + "\n  ".join(problems))

    out = {
        "_meta": {
            "note": "离线结算金标准。XJ380 C++ 端必须逐字段复现 expect。",
            "anchor_utc": T0,
            "algorithm": "fishtank/offline.py :: settle_offline (S0-S4)",
            "step_order": ["growth", "water", "satiety", "income", "breeding"],
            "rounding": "round_half_up(x) = floor(x + 0.5)",
            "rng": "LCG64: seed = seed*6364136223846793005 + 1442695040888963407 (mod 2^64), out = seed >> 32",
        },
        "cases": [],
    }
    for name, st, away, note in build_cases():
        new_st, rep = settle_offline(st, T0 + away, bal, species, decor)
        out["cases"].append({
            "name": name,
            "note": note,
            "away_sec_requested": away,
            "input": st.to_dict(),
            "expect": {
                "away_sec": rep.away_sec,
                "capped": rep.capped,
                "clock_rollback": rep.clock_rollback,
                "steps": rep.steps,
                "equivalent_min": round(rep.equivalent_min, 6),
                "coins_gained_milli": rep.coins_gained_milli,
                "coins_after_milli": new_st.coins_milli,
                "water_after": round(new_st.tank.water, 6),
                "satiety_after": round(new_st.tank.satiety, 6),
                "fish_count_after": new_st.fish_count(),
                "rng_seed_after": new_st.rng_seed,
                "next_uid_after": new_st.next_uid,
                "stages_after": {str(f.uid): f.stage for f in new_st.fishes_sorted()},
                "born_species": [b["species"] for b in rep.born],
                "grown_count": len(rep.grown),
            },
        })
    return out


def write_golden(path=OUT_PATH):
    """生成并写入金标准文件。"""
    data = make_golden()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return path, len(data["cases"])


def check_golden(path=OUT_PATH):
    """校验当前代码与磁盘上的金标准是否一致。

    :returns: 不一致的用例名列表（空 = 通过）
    """
    if not os.path.isfile(path):
        return ["<金标准文件不存在：%s>" % path]
    with open(path, "r", encoding="utf-8") as f:
        old = json.load(f)
    new = make_golden()
    old_map = {c["name"]: c["expect"] for c in old.get("cases", [])}
    bad = []
    for case in new["cases"]:
        if old_map.get(case["name"]) != case["expect"]:
            bad.append(case["name"])
    for name in old_map:
        if name not in {c["name"] for c in new["cases"]}:
            bad.append(name + " (已从用例集中消失)")
    return bad


def main(argv=None):
    """命令行入口。"""
    ap = argparse.ArgumentParser(description="生成/校验离线结算金标准")
    ap.add_argument("--check", action="store_true", help="只校验，不写文件")
    ap.add_argument("--out", default=OUT_PATH, help="输出路径")
    args = ap.parse_args(argv)

    if args.check:
        bad = check_golden(args.out)
        if bad:
            print("✗ 金标准不一致：" + ", ".join(bad))
            return 1
        print("✓ 金标准一致")
        return 0

    path, n = write_golden(args.out)
    print("✓ 已生成 %d 条金标准用例 -> %s" % (n, path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
