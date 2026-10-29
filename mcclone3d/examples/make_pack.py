# -*- coding: utf-8 -*-
"""生成演示用的资源包（**从程序化基线现算**，仓里不带任何二进制素材）。

    python examples/make_pack.py                    # 写 packs/autumn + packs/retro
    python examples/make_pack.py --kind autumn
    python examples/make_pack.py --out D:/tmp/packs
    python examples/make_pack.py --list             # 只列出仓里现有的包

生成完之后，demo/CLI 就能按 **包 id** 引用它：

    python examples/mcclone3d.py --pack autumn
    python examples/shot_pack.py

`packs/` **不进版本库**（`.gitignore` 里有）—— 与 `textures.py` 的
"磁盘上只有生成规则"同一条纪律：想验"包生效了"不需要先下载任何东西，
跑一遍本脚本就有。
"""
from __future__ import annotations

import argparse
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)         # 支持 `python examples/make_pack.py` 直接跑

for _s in (sys.stdout, sys.stderr):
    _rec = getattr(_s, 'reconfigure', None)
    if _rec is not None:
        try:
            _rec(encoding='utf-8', errors='replace')
        except (ValueError, OSError):
            pass

from mcclone3d import packs as PK           # noqa: E402
from mcclone3d import textures as T         # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description='生成演示资源包（程序化、确定性）')
    ap.add_argument('--out', default=PK.PACK_ROOT, help='写到哪个目录（默认 packs/）')
    ap.add_argument('--kind', default='all',
                    help=f'{", ".join(PK.DEMO_KINDS)} 之一，或 all（默认）')
    ap.add_argument('--list', action='store_true', help='只列出该目录下已有的包')
    args = ap.parse_args(argv)

    if args.list:
        found = PK.discover(args.out)
        if not found:
            print(f'（{args.out} 下还没有包；跑一次不带 --list 的本脚本即可）')
            return 0
        for pid, name, path in found:
            print(f'  {pid:<10} {name:<20} {path}')
        return 0

    kinds = list(PK.DEMO_KINDS) if args.kind == 'all' else [args.kind]
    for kind in kinds:
        dst = os.path.join(args.out, kind)
        pk = PK.write_demo_pack(dst, kind)
        n_png = len(os.listdir(os.path.join(dst, PK.TILE_DIR)))
        total = sum(os.path.getsize(os.path.join(dst, PK.TILE_DIR, f))
                    for f in os.listdir(os.path.join(dst, PK.TILE_DIR)))
        print(f'[make_pack] {pk.report()}（{n_png} 个 PNG，共 {total / 1024:.1f} KB）')
        print(f'            写到 {dst}   基线分辨率 {T.TILE}px')
    print(f'== MAKE_PACK_OK {",".join(kinds)} ==', flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
