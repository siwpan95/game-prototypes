"""懒人桌面养鱼模拟器 —— Python 端入口。

🔴 `import fishtank.engine_bootstrap` 必须早于任何其他项目模块
   （E3：引擎 paths.py 在导入期读取 ALLIN_USER_DATA）。

命令行：
    python main.py                    正常启动桌宠窗口
    python main.py --no-tray          强制禁用系统托盘（走 NullTray 降级路径）
    python main.py --safe             安全自检：引擎就绪 + 数据加载 + 校验，然后退出
    python main.py --headless 60      无头运行 60 秒（不建窗口），打印模拟摘要
    python main.py --data-dir D:\\x    自定义用户数据目录（存档写到该目录的 saves/）
"""

import os
import sys


def _preparse_data_dir(argv):
    """在 import 引擎之前手动扫一遍 argv，取出 --data-dir。

    必须先于 `import fishtank.engine_bootstrap`，因为引擎 paths.py 在导入期
    就读取 ALLIN_USER_DATA（E3），argparse 跑完再设就晚了。

    :param argv: sys.argv[1:]
    :returns: 用户指定的数据目录，未指定则空串
    """
    for i, a in enumerate(argv):
        if a == "--data-dir" and i + 1 < len(argv):
            return argv[i + 1]
        if a.startswith("--data-dir="):
            return a.split("=", 1)[1]
    return ""


def _force_utf8_stdout():
    """Windows 控制台默认 GBK，中文日志会抛 UnicodeEncodeError。尽力切到 UTF-8。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError, ValueError):
            pass


_force_utf8_stdout()

_DATA_DIR = _preparse_data_dir(sys.argv[1:])
if _DATA_DIR:
    os.environ["ALLIN_USER_DATA"] = _DATA_DIR

import fishtank.engine_bootstrap as boot  # noqa: E402  ★ 必须最先

import argparse  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402

from fishtank.game import FishTankGame  # noqa: E402

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"


def build_parser():
    """构造命令行解析器。"""
    p = argparse.ArgumentParser(
        prog="lazy_fish_tank",
        description="懒人桌面养鱼模拟器",
    )
    p.add_argument("--no-tray", action="store_true", help="禁用系统托盘，走窗口菜单降级模式")
    p.add_argument("--safe", action="store_true", help="安全自检：引擎与数据就绪即退出，不建窗口")
    p.add_argument("--headless", type=float, default=0.0, metavar="SEC",
                   help="无头模拟指定秒数后退出（用于验证，不建窗口）")
    p.add_argument("--data-dir", default="", help="用户数据目录（存档位置）")
    p.add_argument("--no-save", action="store_true", help="本次运行不写存档（自检/测试用）")
    return p


def run_safe(game):
    """`--safe`：打印引擎与数据就绪状态，返回退出码。"""
    print("[1/4] 引擎就绪")
    print("      engine_home = %s" % boot.engine_home())
    print("      user_data   = %s" % boot.user_data_dir())
    print("      save_dir    = %s" % boot.save_dir())
    flags = {m: boot.deps.has(m) for m in ("numpy", "scipy", "asteval", "PIL", "pystray", "tkinter")}
    print("      deps        = %s" % flags)

    game.start()

    print("[2/4] 数据加载")
    print("      balance.json  keys=%d" % len(game.bal.raw))
    print("      fish_data     %d 种" % len(game.species.all_items))
    print("      decor_data    %d 件" % len(game.decor.ids()))
    print("      ui_text       %d 组" % len(game.text.raw))

    print("[3/4] 数值表校验")
    if game.balance_problems:
        for p in game.balance_problems:
            print("      [警告] %s" % p)
    else:
        print("      balance.json 全部校验通过")

    print("[4/4] 领域内核自检")
    res = game.offline_report
    snap = game.hud_snapshot()
    print("      离线结算     = %d 厘 / 离开 %ds / 等效 %.2f 小时"
          % (res.coins_gained_milli, res.away_sec, res.equivalent_hours()))
    print("      金币         = %s" % snap["coins_text"])
    print("      鱼           = %d 条 / 容量 %d" % (snap["fish_count"], snap["capacity"]))
    print("      水质         = %.4f" % snap["water"])
    print("      系统         = %s" % ", ".join(sorted(game.systems)))
    print("自检完成：引擎就绪、数据加载。")
    return 0


def run_headless(game, seconds):
    """`--headless`：无头推进模拟，打印首尾对比，返回退出码。

    用于在没有显示器/不弹窗的前提下验证 ECS 与经济系统真的在跑。
    """
    game.start()
    res = game.offline_report
    bal = game.bal
    hz = float(bal.get("loop.logic_hz", 20) or 20)
    dt = 1.0 / hz
    steps = int(seconds * hz)

    def snap():
        fs = sorted(game.state.fishes, key=lambda f: f.uid)
        return {
            "coins": game.state.coins_milli,
            "water": game.state.tank.water,
            "satiety": game.state.tank.satiety,
            "fish": [(f.uid, f.species, f.stage, round(f.age_sec, 2)) for f in fs],
            "pos": [(v["uid"], round(v["x"], 4), round(v["y"], 4)) for v in
                    sorted(game.fish_views(), key=lambda v: v["uid"])],
        }

    print("无头模拟：%.1f 秒 / logic_hz=%g / steps=%d" % (seconds, hz, steps))
    print("离线结算：+%d 厘 / 离开 %ds / 等效 %.2f 小时"
          % (res.coins_gained_milli, res.away_sec, res.equivalent_hours()))
    before = snap()
    t0 = time.perf_counter()
    for _ in range(steps):
        game.update(dt)
    cost = time.perf_counter() - t0
    after = snap()

    scale = float(bal.get("economy.coin_scale", 1000) or 1000)
    print("耗时 %.3fs（模拟 %.1fs，实时倍率 %.1fx，%.0f fps）"
          % (cost, seconds, seconds / cost if cost else 0.0, steps / cost if cost else 0.0))
    print("金币  %d -> %d 厘（+%d 厘 = %.3f 金币）"
          % (before["coins"], after["coins"], after["coins"] - before["coins"],
             (after["coins"] - before["coins"]) / scale))
    print("水质  %.4f -> %.4f（Δ %+.4f）"
          % (before["water"], after["water"], after["water"] - before["water"]))
    print("饱食  %.4f -> %.4f（Δ %+.4f）"
          % (before["satiety"], after["satiety"], after["satiety"] - before["satiety"]))
    for (uid, sid, st0, a0), (_, _, st1, a1) in zip(before["fish"], after["fish"]):
        print("鱼#%d %-12s 阶段 %s -> %s  年龄 %.2fs -> %.2fs" % (uid, sid, st0, st1, a0, a1))
    for (uid, x0, y0), (_, x1, y1) in zip(before["pos"], after["pos"]):
        print("鱼#%d 位置 (%.4f,%.4f) -> (%.4f,%.4f)" % (uid, x0, y0, x1, y1))
    moved = any(p0[1:] != p1[1:] for p0, p1 in zip(before["pos"], after["pos"]))
    print("游动检测：%s" % ("鱼在动 ✓" if moved else "鱼没动 ✗"))
    return 0


def main(argv=None):
    """程序主入口。"""
    args = build_parser().parse_args(argv)

    # --safe / --headless / --no-save 一律不写存档，避免自检污染玩家进度。
    save_enabled = not (args.no_save or args.safe or args.headless > 0)
    game = FishTankGame(
        data_dir=str(DATA_DIR),
        save_dir=boot.save_dir(),
        save_enabled=save_enabled,
    )

    if args.safe:
        return run_safe(game)
    if args.headless > 0:
        return run_headless(game, args.headless)

    # GUI 路径：此处才允许 import tkinter 相关模块
    from pyapp.app import FishTankApp
    app = FishTankApp(game, no_tray=args.no_tray)
    return app.run()


if __name__ == "__main__":
    sys.exit(main())
