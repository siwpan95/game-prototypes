"""
import_excel.py - 命令行导入 Excel 配置脚本
用法:
    python import_excel.py <excel_path>    导入并覆盖 rewards.xlsx
    python import_excel.py --backup        仅备份当前 rewards.xlsx
    python import_excel.py --show          显示当前配置摘要
"""
import os
import sys
import shutil

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from qiandao import (
    load_config,
    sync_config_to_json,
    backup_excel,
    EXCEL_PATH,
    JSON_PATH,
)

try:
    import pandas as pd
except ImportError:
    pd = None


def import_from_excel(src_path):
    if pd is None:
        print("错误: pandas 未安装，请先执行: pip install pandas openpyxl")
        return

    if not os.path.exists(src_path):
        print(f"错误: 文件不存在: {src_path}")
        return

    try:
        df = pd.read_excel(src_path)
        required = {"name", "base", "gamma", "delta"}
        if not required.issubset(set(df.columns)):
            print("错误: Excel 必须包含列: name, base, gamma, delta")
            print("       可选列: category, rarity, description")
            return

        if os.path.exists(EXCEL_PATH):
            backup_excel()
            print("[备份] 旧 rewards.xlsx 已备份到 backups/")

        shutil.copy2(src_path, EXCEL_PATH)
        print(f"[复制] {src_path}  ->  {EXCEL_PATH}")

        g, rewards = load_config()
        sync_config_to_json(g, rewards)
        print(f"[同步] JSON 已更新: {JSON_PATH}")
        print(f"[完成] 共 {len(rewards)} 个奖励配置\n")
        _print_summary(rewards)
    except Exception as e:
        print(f"错误: {e}")


def _print_summary(rewards):
    print(f"{'名称':<16} {'分类':<6} {'稀有度':<6} {'base':>7} {'gamma':>7} {'delta':>7}")
    print("-" * 58)
    for rw in rewards:
        print(f"{rw['name']:<16} {rw.get('category',''):<6} {rw.get('rarity',''):<6} "
              f"{rw['base']:>7.3f} {rw['gamma']:>7.3f} {rw['delta']:>7.4f}")


def only_backup():
    if os.path.exists(EXCEL_PATH):
        path = backup_excel()
        if path:
            print(f"[备份] 已备份到: {path}")
    else:
        print(f"[跳过] {EXCEL_PATH} 不存在，无需备份")


def show_config():
    g, rewards = load_config()
    print("=== 全局参数 ===")
    for k, v in g.items():
        print(f"  {k}: {v}")
    print(f"\n=== 奖励列表（{len(rewards)} 项）===")
    _print_summary(rewards)


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return
    cmd = args[0]
    if cmd == "--backup":
        only_backup()
    elif cmd == "--show":
        show_config()
    else:
        import_from_excel(cmd)


if __name__ == "__main__":
    main()
