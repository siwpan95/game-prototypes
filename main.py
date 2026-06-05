import sys
import json
import os
from pathlib import Path
from game_engine import GameEngine
from unlock_manager import UnlockManager


def _data_path(rel: str) -> str:
    """获取只读数据文件的绝对路径（兼容 PyInstaller _MEIPASS）"""
    if getattr(sys, 'frozen', False):
        base = sys._MEIPASS  # type: ignore[attr-defined]
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, rel)


def _save_path(rel: str) -> str:
    """获取可写存档文件的绝对路径（始终位于 exe 同级目录）"""
    if getattr(sys, 'frozen', False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, rel)


def _handle_excel_import(args):
    """
    检测 --import-excel / --gen-template 参数并执行对应操作。
    返回 True 表示已处理（主程序应退出），False 表示继续正常启动。
    """
    if "--gen-template" in args:
        # 重新生成模板
        try:
            import generate_template
            generate_template.main()
        except Exception as e:
            print(f"[错误] 生成模板失败：{e}")
            sys.exit(1)
        return True

    import_idx = None
    check_only  = "--check" in args
    for i, a in enumerate(args):
        if a == "--import-excel":
            import_idx = i
            break

    if import_idx is not None:
        xlsx_file = None
        # 下一个参数若不是 flag，则视为 xlsx 路径
        if import_idx + 1 < len(args) and not args[import_idx + 1].startswith("--"):
            xlsx_file = args[import_idx + 1]
        if not xlsx_file:
            base = Path(__file__).parent
            xlsx_file = str(base / "TwelveLabors.xlsx")

        from excel_importer import import_excel
        ok = import_excel(xlsx_file, check_only=check_only)
        sys.exit(0 if ok else 1)
        return True  # unreachable, but explicit

    return False


def main():
    # ── 特殊操作参数（Excel 导入/生成模板）──
    if _handle_excel_import(sys.argv[1:]):
        return

    # 解析启动参数：--ui tkinter/console/pygame（默认 tkinter）
    ui_mode = "tkinter"
    for arg in sys.argv[1:]:
        if arg.startswith("--ui="):
            ui_mode = arg.split("=", 1)[1].lower()
        elif arg in ("--gui", "--pygame"):
            ui_mode = "pygame"
        elif arg == "--console":
            ui_mode = "console"
        elif arg == "--tkinter":
            ui_mode = "tkinter"

    unlock = UnlockManager(
        save_path=_save_path('data/unlocks.json'),
        data_path=_data_path('data')
    )

    if ui_mode == "tkinter":
        # Tkinter 完整流程（含标题选择界面）
        from ui_tkinter import run_with_title
        endings = run_with_title(unlock)
        if endings:
            print("解锁内容已保存。")
        return

    # ── 控制台通用选角/选模式流程 ──
    available_chars = unlock.get_available_characters()

    print("====== 十二试炼：神话重构 ======")
    print("可选择的英雄：")
    with open(_data_path('data/characters.json'), 'r', encoding='utf-8') as f:
        char_data = json.load(f)
    for idx, cid in enumerate(available_chars):
        c = char_data[cid]
        print(f"[{idx+1}] {c['name']} - {c['desc']}")

    choice = input("选择英雄(输入数字): ").strip()
    try:
        cid = available_chars[int(choice) - 1]
    except Exception:
        cid = available_chars[0]

    # 试炼组合选择
    print("\n选择你的试炼之路：")
    print("[0] 随机（命运裁决）")
    print("[1] 均衡（肉体→心智→神性）")
    print("[2] 暴力（全部肉体）")
    print("[3] 智者（全部心智）")
    print("[4] 神眷（全部神性）")
    if cid in ('beowulf', 'kratos'):
        print("[6] 传承之路（角色专属剧情）")
    if unlock.is_unlocked('chaos_mode'):
        print("[5] 混沌（随机混合）")

    combo_map = {
        "0": "random",
        "1": "balanced",
        "2": "all_physical",
        "3": "all_mental",
        "4": "all_divine",
        "5": "chaos",
        "6": "lore",
    }
    combo_choice = input("选择模式(默认0): ").strip() or "0"
    labour_combo = combo_map.get(combo_choice, "random")

    engine = GameEngine(cid, unlock, labour_combo,
                        data_root=_data_path('data'))

    if ui_mode == "pygame":
        from ui_pygame import PygameUI
        ui = PygameUI()
    else:
        from ui_console import ConsoleUI
        ui = ConsoleUI()

    endings = ui.run(engine)

    # 解锁结局
    if endings:
        for e in endings:
            unlock.unlock_ending(e['id'])
        print("解锁内容已保存。")


if __name__ == '__main__':
    main()
