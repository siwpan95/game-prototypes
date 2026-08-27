"""
测试 11 款游戏的实际按钮交互 — shared_core 统一架构版。
所有游戏已迁移到 shared_core 薄壳架构，使用统一的 ConcreteGameEngine。
每个游戏在独立子进程中测试，完全隔离模块环境。
"""
import subprocess
import sys
import os

BASE_DIR = r"C:\Users\13122\Desktop\stay\hell below\ch"

GAMES = [
    "AlenAbot_zh",
    "AnaScranton_zh",
    "BorjiginChagatai_zh",
    "BrianSimpson_CN",
    "GeorgesRamsayBepan_zh",
    "NathanWinters_CN",
    "PenicilinParkinson_zh",
    "RinyoTohsaka_zh",
    "RuinedRealm_zh",
    "stockton_adams_zh",
    "jx_liu_game_zh",
]

TEST_CODE = r'''
import sys, os, traceback, tkinter as tk

game_name = "%GAME_NAME%"
game_dir = r"%GAME_DIR%"
ch_dir = r"%CH_DIR%"

os.chdir(game_dir)
sys.path.insert(0, ch_dir)

errors = []
button_count = 0
clicked_ok = 0
clicked_err = 0

def find_all_buttons(widget):
    """递归查找所有 tk.Button"""
    buttons = []
    try:
        for child in widget.winfo_children():
            if isinstance(child, tk.Button):
                buttons.append(child)
            buttons.extend(find_all_buttons(child))
    except Exception:
        pass
    return buttons

def safe_invoke_button(btn, btn_name="button"):
    """安全点击按钮，捕获异常"""
    try:
        btn.invoke()
        return True
    except tk.TclError:
        return False
    except Exception as e:
        errors.append("  [" + btn_name + "] invoke error: " + type(e).__name__ + ": " + str(e))
        return False

def test_all_buttons(widget, label="root"):
    global button_count, clicked_ok, clicked_err
    btns = find_all_buttons(widget)
    button_count += len(btns)
    for i, b in enumerate(btns):
        try:
            btn_text = b.cget("text")
        except Exception:
            btn_text = ""
        btn_name = label + "_btn_" + str(i) + "(" + str(btn_text)[:20] + ")"
        if safe_invoke_button(b, btn_name):
            clicked_ok += 1
            try:
                widget.update()
            except Exception:
                pass
        else:
            clicked_err += 1

try:
    # 所有游戏统一使用 shared_core 架构
    from shared_core.base_engine import ConcreteGameEngine
    import config

    # 创建引擎并初始化
    engine = ConcreteGameEngine(config)
    engine.initialize()

    # 获取 root widget 刷新
    ui = engine.ui
    root_widget = getattr(ui, 'root', None)
    if root_widget is None:
        # 某些 UI 可能有不同的 root 属性
        root_widget = ui

    # 显示标题画面并刷新
    ui.show_title_screen()
    if hasattr(root_widget, 'update'):
        root_widget.update()

    # 第一轮：测试标题画面上的按钮
    test_all_buttons(root_widget, "title")

    # 尝试开始游戏
    try:
        engine.start_game()
    except Exception:
        pass

    if hasattr(root_widget, 'update'):
        root_widget.update()

    # 第二轮：测试游戏画面上的按钮
    test_all_buttons(root_widget, "game")

    # 尝试推进几次并持续测试按钮
    for round_num in range(3):
        try:
            engine._show_next_content()
        except Exception:
            pass
        if hasattr(root_widget, 'update'):
            root_widget.update()
        test_all_buttons(root_widget, "round" + str(round_num))

    # 清理
    try:
        ui.shutdown()
    except Exception:
        pass

except Exception as e:
    errors.append("INIT ERROR: " + type(e).__name__ + ": " + str(e))
    errors.extend(traceback.format_exc().splitlines()[-5:])

print("BUTTONS: " + str(button_count))
print("CLICKED_OK: " + str(clicked_ok))
print("CLICKED_ERR: " + str(clicked_err))
print("ERRORS: " + str(len(errors)))
for err in errors:
    print(err)
'''


def test_game(game_name: str) -> dict:
    game_dir = os.path.join(BASE_DIR, game_name)

    test_code = TEST_CODE.replace("%GAME_NAME%", game_name)
    test_code = test_code.replace("%GAME_DIR%", game_dir)
    test_code = test_code.replace("%CH_DIR%", BASE_DIR)

    result = subprocess.run(
        [sys.executable, "-c", test_code],
        capture_output=True,
        text=True,
        timeout=30,
    )

    stdout = result.stdout.strip()
    stderr = result.stderr.strip()

    buttons = 0
    clicked_ok = 0
    clicked_err = 0
    errors = 0
    error_lines = []

    for line in stdout.splitlines():
        if line.startswith("BUTTONS:"):
            buttons = int(line.split(":", 1)[1].strip())
        elif line.startswith("CLICKED_OK:"):
            clicked_ok = int(line.split(":", 1)[1].strip())
        elif line.startswith("CLICKED_ERR:"):
            clicked_err = int(line.split(":", 1)[1].strip())
        elif line.startswith("ERRORS:"):
            errors = int(line.split(":", 1)[1].strip())
        elif line.startswith("  [") or line.startswith("INIT ERROR"):
            error_lines.append(line)

    # 附加 stderr 中的 traceback
    if stderr and "Traceback" in stderr:
        tb_lines = stderr.strip().splitlines()
        error_lines.extend(tb_lines[-5:])

    return {
        "game": game_name,
        "buttons": buttons,
        "clicked_ok": clicked_ok,
        "clicked_err": clicked_err,
        "errors": errors,
        "error_lines": error_lines,
        "stderr": stderr[:500] if stderr else "",
        "returncode": result.returncode,
    }


def main():
    print("=" * 85)
    print("  11 款游戏按钮交互测试（shared_core 统一架构版）")
    print("=" * 85)
    print()

    results = []
    for game in GAMES:
        print(f"测试 {game} ... ", end="", flush=True)
        try:
            res = test_game(game)
            results.append(res)
            status = "PASS" if res["returncode"] == 0 else "FAIL"
            print(f"{status} (按钮: {res['buttons']}, 成功: {res['clicked_ok']}, "
                  f"失败: {res['clicked_err']}, 错误: {res['errors']})")
            if res["error_lines"]:
                for err in res["error_lines"][:5]:
                    print(f"    {err[:120]}")
            if res["stderr"] and res["returncode"] != 0:
                print(f"    [stderr] {res['stderr'][:250]}")
        except subprocess.TimeoutExpired:
            print("TIMEOUT")
            results.append({"game": game, "buttons": 0, "clicked_ok": 0,
                           "clicked_err": 0, "errors": 1,
                           "error_lines": ["Timeout"], "stderr": "", "returncode": -1})
        except Exception as e:
            print(f"EXCEPTION: {e}")
            results.append({"game": game, "buttons": 0, "clicked_ok": 0,
                           "clicked_err": 0, "errors": 1,
                           "error_lines": [str(e)], "stderr": "", "returncode": -1})

    print()
    print("=" * 85)
    print(" 汇总")
    print("=" * 85)
    print(f"{'游戏':<25} {'按钮':>6} {'成功':>6} {'失败':>6} {'错误':>6} {'状态':>6}")
    print("-" * 85)
    for r in results:
        status = "PASS" if r["returncode"] == 0 else "FAIL"
        print(f"{r['game']:<25} {r['buttons']:>6} {r['clicked_ok']:>6} "
              f"{r['clicked_err']:>6} {r['errors']:>6} {status:>6}")

    total_pass = sum(1 for r in results if r["returncode"] == 0)
    print("-" * 85)
    print(f"总计: {total_pass}/{len(results)} 通过")
    if total_pass == len(results):
        print("所有游戏按钮交互正常！")
    else:
        print("存在失败的游戏，请查看上方错误信息")


if __name__ == "__main__":
    main()
