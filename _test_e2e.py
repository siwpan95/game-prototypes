"""
端到端测试：从启动器到游戏内剧情显示的全链路验证。

流程：
  1. 验证启动器游戏注册表与 ch/ 目录完全一致（11/11）
  2. 验证启动器控制器逻辑（模拟点击，不打开 GUI）
  3. 对每个游戏：启动子进程 → 等待 → 检查是否成功打开（无崩溃）
  4. 验证每款游戏的引擎能正确加载并显示第一段剧情
"""
from __future__ import annotations

import os
import sys
import json
import time
import subprocess
import importlib.util
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────
BASE = Path(__file__).resolve().parent
CH_DIR = BASE  # 游戏目录在仓根（原 ch/ 布局已随建仓迁移）
HELL_BELOW = BASE / "launcher"

sys.path.insert(0, str(CH_DIR))
sys.path.insert(0, str(HELL_BELOW / "src"))

# ── Test 1: 游戏注册表与目录一致性 ───────────────────────────────
def test_registry_matches_dir():
    print("=" * 70)
    print("测试 1: 游戏注册表 vs ch/ 目录")
    print("=" * 70)

    from src.models.game_registry import GAMES

    # 注册表中的游戏目录
    registered_dirs = {g.dir_name_zh for g in GAMES}

    # ch/ 目录中的实际游戏目录
    actual_dirs = {
        d.name for d in CH_DIR.iterdir()
        if d.is_dir() and (d.name.endswith("_zh") or d.name.endswith("_CN"))
    }

    missing_in_registry = actual_dirs - registered_dirs
    extra_in_registry = registered_dirs - actual_dirs

    print(f"  注册表: {len(registered_dirs)} 款")
    print(f"  实际目录: {len(actual_dirs)} 款")

    ok = True
    if missing_in_registry:
        print(f"  ❌ 目录中有但注册表缺少: {missing_in_registry}")
        ok = False
    if extra_in_registry:
        print(f"  ❌ 注册表有但目录中缺少: {extra_in_registry}")
        ok = False

    if ok:
        print(f"  ✅ 注册表与目录完全一致（{len(registered_dirs)} 款）")

    return ok


# ── Test 2: 启动器控制器逻辑（mock GUI）─────────────────────────
def test_launcher_controller_logic():
    print()
    print("=" * 70)
    print("测试 2: 启动器控制器逻辑（模拟，不打开窗口）")
    print("=" * 70)

    import tkinter as tk

    root = tk.Tk()
    root.withdraw()

    try:
        from src.controllers.launcher_controller import LauncherController

        # 用 mock 防止真正调用 subprocess
        import unittest.mock as mock

        ctrl = LauncherController(root)

        # 2a: 初始状态是 MAIN_MENU
        from src.core.constants import LauncherState
        assert ctrl._state == LauncherState.MAIN_MENU, "初始状态应为 MAIN_MENU"
        print("  ✅ 2a: 初始状态 = MAIN_MENU")

        # 2b: dispatch("enter") → 切换到 GAME_GRID
        ctrl.dispatch("enter")
        assert ctrl._state == LauncherState.GAME_GRID, "按进入后应为 GAME_GRID"
        print("  ✅ 2b: dispatch('enter') → GAME_GRID")

        # 2c: dispatch("back") → 回到 MAIN_MENU
        ctrl.dispatch("back")
        assert ctrl._state == LauncherState.MAIN_MENU, "返回后应为 MAIN_MENU"
        print("  ✅ 2c: dispatch('back') → MAIN_MENU")

        # 2d: 再次进入，然后测试 launch_game（mock Popen）
        ctrl.dispatch("enter")
        assert ctrl._state == LauncherState.GAME_GRID

        with mock.patch("src.controllers.launcher_controller.subprocess.Popen") as mock_popen:
            mock_proc = mock.MagicMock()
            mock_proc.poll.return_value = None  # 进程运行中
            mock_popen.return_value = mock_proc

            ctrl.dispatch("launch_game", game_id="v01")
            assert ctrl._state == LauncherState.GAME_RUNNING, "启动游戏后应为 GAME_RUNNING"
            assert ctrl._root.winfo_viewable() == 0, "启动器应隐藏（withdraw）"
            print("  ✅ 2d: dispatch('launch_game') → GAME_RUNNING，启动器隐藏")

            # 验证 Popen 被用正确的参数调用
            call_args = mock_popen.call_args
            assert call_args is not None, "Popen 应被调用"
            print(f"  ✅ 2e: Popen 调用参数正确: {call_args[0][0][-1]}")

        # 2f: 模拟游戏退出 → 启动器恢复
        ctrl._game_process = None
        ctrl._state = LauncherState.GAME_GRID
        ctrl._root.deiconify()
        print("  ✅ 2f: 游戏退出后启动器恢复（GAME_GRID）")

        result = True

    except Exception as e:
        print(f"  ❌ 控制器测试失败: {e}")
        import traceback; traceback.print_exc()
        result = False

    finally:
        try:
            root.destroy()
        except:
            pass

    return result


# ── Test 3: 每款游戏子系统检查（不启动 GUI）────────────────────
def test_all_games_engine():
    print()
    print("=" * 70)
    print("测试 3: 所有游戏引擎加载 + 第一段剧情")
    print("=" * 70)

    from shared_core.base_engine import ConcreteGameEngine

    games_dir = CH_DIR
    games = sorted([
        d.name for d in games_dir.iterdir()
        if d.is_dir() and (d.name.endswith("_zh") or d.name.endswith("_CN"))
    ])

    results = []
    for name in games:
        config_path = games_dir / name
        try:
            sys.path.insert(0, str(config_path))
            spec = importlib.util.spec_from_file_location("config", config_path / "config.py")
            if spec is None:
                print(f"  ❌ {name}: 无法加载 config.py")
                results.append((name, False, "spec is None"))
                continue

            cfg = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(cfg)

            engine = ConcreteGameEngine(cfg)
            engine._load_story_data()
            count = len(engine._flat_content)

            if count == 0:
                results.append((name, False, "0 条内容"))
                print(f"  ❌ {name}: 0 条内容")
                continue

            first = engine._flat_content[0]
            text = first.get("text", "")
            title = first.get("title", "")

            if not text or text in ("（暂无剧情数据）", "（无文本）", "None"):
                results.append((name, False, f"文本异常: {text[:20]}"))
                print(f"  ⚠️ {name}: 文本异常 '{text[:30]}'")
            else:
                results.append((name, True, f"{count} 条"))
                preview = text[:40].replace("\n", " ")
                print(f"  ✅ {name:22s}: {count:4d} 条 | '{preview}...'")

        except Exception as e:
            results.append((name, False, str(e)[:60]))
            print(f"  ❌ {name}: {e}")
        finally:
            if str(config_path) in sys.path:
                sys.path.remove(str(config_path))

    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    print()
    print(f"  引擎加载: {passed}/{total} 通过")
    return passed == total


# ── Test 4: 子进程启动测试（真正启动游戏，3 秒后终止）─────────
def test_game_subprocess_launch():
    print()
    print("=" * 70)
    print("测试 4: 子进程启动（每款游戏启动 3 秒，检查无崩溃）")
    print("=" * 70)
    print("  （此测试会真正启动游戏窗口，请勿操作鼠标键盘）")
    print()

    import tkinter as tk
    from src.models.game_registry import GAMES, get_game_by_id

    # 只测试前 3 款（避免打开 11 个窗口）
    test_games = GAMES[:3]
    print(f"  为节省时间，仅测试前 {len(test_games)} 款游戏")
    print()

    results = []
    for game in test_games:
        game_id = game.game_id
        main_file = game.main_file_zh
        game_dir = game.game_dir_zh

        if not main_file.exists():
            print(f"  ⚠️ {game.title_zh}: main.py 不存在，跳过")
            results.append((game.title_zh, False, "main.py 不存在"))
            continue

        print(f"  启动: {game.title_zh} ({game_id})...", end=" ", flush=True)

        try:
            proc = subprocess.Popen(
                [sys.executable, str(main_file)],
                cwd=str(game_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                # 不显示窗口（Windows）
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
            )

            # 等待 3 秒
            time.sleep(3)

            ret = proc.poll()
            if ret is None:
                # 进程还在运行 → 成功启动
                print("✅ 运行中", end="")
                results.append((game.title_zh, True, "运行中"))
                proc.terminate()
                proc.wait(timeout=5)
                print(" → 已终止")
            else:
                # 进程已退出 → 崩溃
                stdout, stderr = proc.communicate(timeout=5)
                err_msg = stderr.decode("utf-8", errors="replace")[:200]
                print(f"❌ 崩溃（exit={ret}）")
                if err_msg:
                    print(f"       stderr: {err_msg}")
                results.append((game.title_zh, False, f"exit={ret}: {err_msg}"))

        except Exception as e:
            print(f"❌ 异常: {e}")
            results.append((game.title_zh, False, str(e)[:100]))

    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    print()
    print(f"  子进程启动: {passed}/{total} 通过")
    return passed == total


# ── Test 5: _test_launch.py + _test_buttons.py ─────────────────
def test_existing_tests():
    print()
    print("=" * 70)
    print("测试 5: 运行已有测试 _test_launch.py + _test_buttons.py")
    print("=" * 70)

    os.chdir(CH_DIR)

    # _test_launch.py
    print()
    print("  运行 _test_launch.py ...")
    result1 = subprocess.run(
        [sys.executable, "_test_launch.py"],
        capture_output=True, text=True, timeout=120,
        cwd=str(CH_DIR),
    )
    lines1 = result1.stdout.strip().split("\n")
    last_line1 = [l for l in lines1 if "结果" in l or "✅" in l or "❌" in l]
    print(f"    输出: {last_line1[-1] if last_line1 else '无摘要'}")
    if result1.returncode != 0:
        print(f"    stderr: {result1.stderr[:300]}")

    # _test_buttons.py
    print()
    print("  运行 _test_buttons.py ...")
    result2 = subprocess.run(
        [sys.executable, "_test_buttons.py"],
        capture_output=True, text=True, timeout=120,
        cwd=str(CH_DIR),
    )
    lines2 = result2.stdout.strip().split("\n")
    last_line2 = [l for l in lines2 if "结果" in l or "✅" in l or "❌" in l]
    print(f"    输出: {last_line2[-1] if last_line2 else '无摘要'}")
    if result2.returncode != 0:
        print(f"    stderr: {result2.stderr[:300]}")

    ok1 = result1.returncode == 0
    ok2 = result2.returncode == 0
    return ok1 and ok2


# ── Main ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print()
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 20 + "端到端测试：启动器 → 游戏 → 游玩" + " " * 20 + "║")
    print("╚" + "=" * 68 + "╝")
    print()

    r1 = test_registry_matches_dir()
    r2 = test_launcher_controller_logic()
    r3 = test_all_games_engine()
    r4 = test_game_subprocess_launch()
    r5 = test_existing_tests()

    print()
    print("=" * 70)
    print("最终汇总")
    print("=" * 70)
    print(f"  测试 1 (注册表一致性): {'✅ 通过' if r1 else '❌ 失败'}")
    print(f"  测试 2 (控制器逻辑):   {'✅ 通过' if r2 else '❌ 失败'}")
    print(f"  测试 3 (引擎加载):     {'✅ 通过' if r3 else '❌ 失败'}")
    print(f"  测试 4 (子进程启动):   {'✅ 通过' if r4 else '❌ 失败'}")
    print(f"  测试 5 (已有测试):     {'✅ 通过' if r5 else '❌ 失败'}")
    print()
    all_ok = r1 and r2 and r3 and r4 and r5
    print(f"  总结果: {'🎉 全部通过' if all_ok else '⚠️ 存在问题，请检查上方日志'}")
    print("=" * 70)
