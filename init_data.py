"""
init_data.py - 数据初始化脚本
运行一次即可生成 rewards.xlsx、qiandao_history.json、backups 目录
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from qiandao import (
    load_config_from_json,
    save_rewards_to_excel,
    save_history,
    EXCEL_PATH,
    HISTORY_PATH,
    BACKUP_DIR,
)


def main():
    print("=" * 45)
    print("  斯金纳箱 · 数据初始化")
    print("=" * 45)

    # 1. 生成 rewards.xlsx（模板列: name, category, rarity, base, gamma, delta, description）
    if os.path.exists(EXCEL_PATH):
        print(f"[已存在] {EXCEL_PATH}")
    else:
        try:
            _, rewards = load_config_from_json()
            save_rewards_to_excel(rewards, EXCEL_PATH)
            print(f"[已生成] {EXCEL_PATH}")
        except Exception as e:
            print(f"[失败] 生成 {EXCEL_PATH}: {e}")
            print("        请先安装依赖: pip install pandas openpyxl")

    # 2. 创建 qiandao_history.json
    if os.path.exists(HISTORY_PATH):
        print(f"[已存在] {HISTORY_PATH}")
    else:
        save_history([])
        print(f"[已创建] {HISTORY_PATH}")

    # 3. 创建 backups 目录
    if os.path.exists(BACKUP_DIR):
        print(f"[已存在] {BACKUP_DIR}")
    else:
        os.makedirs(BACKUP_DIR, exist_ok=True)
        print(f"[已创建] {BACKUP_DIR}")

    print("=" * 45)
    print("  初始化完成")
    print("=" * 45)


if __name__ == "__main__":
    main()
