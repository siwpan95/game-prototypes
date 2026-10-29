# -*- coding: utf-8 -*-
"""release 打包：每游戏一个 zip（gitee 单文件发布用）+ 全量 zip（本地/网盘分发）。

    python make_release.py                     # 全部游戏 + 全量包，v1.0.0 命名
    python make_release.py --only kid-a-walker # 只重打一个游戏
    python make_release.py --ver v1.1.0        # 自定义版本号
"""
import argparse
import shutil
import sys
import zipfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ap = argparse.ArgumentParser()
ap.add_argument("--only", default=None, help="只打包指定游戏目录名")
ap.add_argument("--ver", default="v1.0.0", help="zip 文件名里的版本号")
args = ap.parse_args()
VER = args.ver

ROOT = Path(__file__).resolve().parent
DIST = ROOT / "dist"
REL = ROOT / "release"
REL.mkdir(exist_ok=True)

# 1) 每游戏 zip
for gdir in sorted((DIST / "games").iterdir()):
    if not gdir.is_dir():
        continue
    if args.only and gdir.name != args.only:
        continue
    out = REL / ("arcade-%s-%s-win64.zip" % (gdir.name, VER))
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for f in gdir.rglob("*"):
            if f.is_file():
                z.write(f, gdir.name + "/" + str(f.relative_to(gdir)))
    print("%s  %.1f MB" % (out.name, out.stat().st_size / 1e6))

# 2) 全量 zip（菜单 + 全部游戏）——--only 时不重打全量
if not args.only:
    full = REL / ("arcade-collection-%s-win64-full.zip" % VER)
    with zipfile.ZipFile(full, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for p in DIST.rglob("*"):
            if p.is_file():
                z.write(p, str(p.relative_to(DIST)))
    print("%s  %.1f MB" % (full.name, full.stat().st_size / 1e6))
print("完成")
