"""从 docs/FISH_CONTENT.md §2 解析 24 条鱼，生成 data/fish_data.json。

设计意图：鱼种 id / 配色 / 体型 / 行为 / 文案的**唯一真源是 FISH_CONTENT.md**，
本脚本负责机械转录，避免人工抄写导致 id 不一致（主理人裁决 Δ5、任务 1.6）。

用法：
    python tools/gen_fish_data.py                 # 写入 data/fish_data.json
    python tools/gen_fish_data.py --check         # 只校验，不写文件（CI 用）
"""

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "FISH_CONTENT.md"
OUT = ROOT / "data" / "fish_data.json"

RARITY_HEAD = re.compile(r"^###\s+(R[1-5])")
ENTRY_HEAD = re.compile(r"^\*\*\d+\.\s+([a-z][a-z0-9_]*)\s+(.+?)\*\*\s*$")
FIELD_LINE = re.compile(r"^-\s*([^：]+)：\s*(.*)$")
BACKTICK = re.compile(r"`([^`]+)`")
KV_PAIR = re.compile(r"([A-Za-z_]+)\s*`([^`]+)`")

EXPECT_RARITY = {"R1": 6, "R2": 6, "R3": 5, "R4": 4, "R5": 3}
EXPECT_GROUP = {"淡水": 9, "热带": 9, "深海": 6}
TAILS = {"fan", "fork", "round", "long"}
SPEEDS = {"slow", "normal", "fast"}
HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


def _strip_paren(text):
    """去掉中文名末尾的括注，例如 '非洲慈鲷（黄王子）' -> '非洲慈鲷'（保留原文用于展示）。"""
    return text.strip()


def parse_doc(md_text):
    """解析 FISH_CONTENT.md 全文，返回鱼种字典列表（按文档出现顺序）。

    :param md_text: markdown 全文
    :returns: list[dict]，字段严格符合 FISH_CONTENT §0 的 schema
    """
    fishes = []
    rarity = ""
    cur = None
    in_section2 = False

    for raw in md_text.splitlines():
        line = raw.rstrip()

        if line.startswith("## "):
            # 进入 §2 鱼种内容库，离开则停止收集
            in_section2 = line.startswith("## 2.")
            if not in_section2 and cur is not None:
                fishes.append(cur)
                cur = None
            continue
        if not in_section2:
            continue

        m = RARITY_HEAD.match(line)
        if m:
            rarity = m.group(1)
            continue

        m = ENTRY_HEAD.match(line)
        if m:
            if cur is not None:
                fishes.append(cur)
            cur = {
                "id": m.group(1),
                "name_zh": _strip_paren(m.group(2)),
                "name_la": "",
                "rarity": rarity,
                "group": "",
                "color": {},
                "shape": {},
                "behavior": {},
                "science": "",
                "codex_unlock": "",
            }
            continue

        if cur is None:
            continue

        m = FIELD_LINE.match(line)
        if not m:
            continue
        key, val = m.group(1).strip(), m.group(2).strip()

        if key == "学名":
            hit = BACKTICK.search(val)
            cur["name_la"] = hit.group(1) if hit else val
        elif key == "族群":
            cur["group"] = val
        elif key == "配色":
            for name, hexv in KV_PAIR.findall(val):
                cur["color"][name] = hexv
        elif key == "体型":
            for name, v in KV_PAIR.findall(val):
                if name in ("length", "height_ratio"):
                    cur["shape"][name] = float(v)
                else:
                    cur["shape"][name] = v
        elif key == "游动":
            for name, v in KV_PAIR.findall(val):
                cur["behavior"][name] = v
        elif key == "科普":
            cur["science"] = val
        elif key == "图鉴":
            cur["codex_unlock"] = val

    if cur is not None:
        fishes.append(cur)
    return fishes


def validate(fishes):
    """执行 FISH_CONTENT §6 灌库校验清单，返回问题列表（空 = 全部通过）。"""
    problems = []

    ids = [f["id"] for f in fishes]
    if len(ids) != len(set(ids)):
        dup = sorted({i for i in ids if ids.count(i) > 1})
        problems.append("id 重复: %s" % dup)
    if len(fishes) != sum(EXPECT_RARITY.values()):
        problems.append("鱼种总数应为 %d，实际 %d" % (sum(EXPECT_RARITY.values()), len(fishes)))

    rc = {}
    gc = {}
    for f in fishes:
        rc[f["rarity"]] = rc.get(f["rarity"], 0) + 1
        gc[f["group"]] = gc.get(f["group"], 0) + 1

        for ck in ("body", "belly", "fin", "pattern"):
            v = f["color"].get(ck, "")
            if not HEX_RE.match(v):
                problems.append("%s color.%s 非法: %r" % (f["id"], ck, v))
        if f["shape"].get("tail") not in TAILS:
            problems.append("%s shape.tail 非法: %r" % (f["id"], f["shape"].get("tail")))
        if f["behavior"].get("speed") not in SPEEDS:
            problems.append("%s behavior.speed 非法: %r" % (f["id"], f["behavior"].get("speed")))
        if not f["behavior"].get("layer"):
            problems.append("%s behavior.layer 缺失" % f["id"])
        if not f["behavior"].get("schooling"):
            problems.append("%s behavior.schooling 缺失" % f["id"])
        if not f["name_la"]:
            problems.append("%s name_la 缺失" % f["id"])
        if not (0.85 <= float(f["shape"].get("length", 0)) <= 2.2):
            problems.append("%s shape.length 越界: %r" % (f["id"], f["shape"].get("length")))
        if not (0.22 <= float(f["shape"].get("height_ratio", 0)) <= 0.8):
            problems.append("%s shape.height_ratio 越界: %r" % (f["id"], f["shape"].get("height_ratio")))
        n = len(f["science"])
        if not (20 <= n <= 60):
            problems.append("%s science 字数异常(%d)" % (f["id"], n))
        if not f["codex_unlock"]:
            problems.append("%s codex_unlock 缺失" % f["id"])

    for r, n in EXPECT_RARITY.items():
        if rc.get(r, 0) != n:
            problems.append("稀有度分布错误 %s: 期望 %d 实际 %d" % (r, n, rc.get(r, 0)))
    for g, n in EXPECT_GROUP.items():
        if gc.get(g, 0) != n:
            problems.append("族群分布错误 %s: 期望 %d 实际 %d" % (g, n, gc.get(g, 0)))
    return problems


def main(argv=None):
    """入口：解析 → 校验 → 写文件。校验失败返回非零退出码。"""
    ap = argparse.ArgumentParser(description="从 FISH_CONTENT.md 生成 fish_data.json")
    ap.add_argument("--check", action="store_true", help="只校验不写文件")
    ap.add_argument("--doc", default=str(DOC), help="FISH_CONTENT.md 路径")
    ap.add_argument("--out", default=str(OUT), help="输出 JSON 路径")
    args = ap.parse_args(argv)

    text = Path(args.doc).read_text(encoding="utf-8")
    fishes = parse_doc(text)
    problems = validate(fishes)

    print("解析到 %d 条鱼" % len(fishes))
    if problems:
        print("校验失败：")
        for p in problems:
            print("  - " + p)
        return 1
    print("校验通过：24 条 / R1x6 R2x6 R3x5 R4x4 R5x3 / 淡水9 热带9 深海6")

    if not args.check:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(fishes, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("已写入 %s" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
