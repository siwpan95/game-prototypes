"""
探险日志 - 自动演示截图脚本
模拟用户操作，在各个页面截图，用于制作宣传视频
"""
import sys
import os
import time
import json
from PIL import ImageGrab

# 确保能导入游戏模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import tkinter as tk
from tkinter import ttk

# 导入游戏核心模块
from core.config import *
from data.loader import DataLoader
from core.models import *
from core.engine import GameEngine
from core.battle import BattleSystem

# 输出目录
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo_shots")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 全局状态
shots = []
current_step = 0

def take_screenshot(root, name, delay=0.3):
    """截取当前窗口"""
    global current_step
    time.sleep(delay)
    root.update_idletasks()
    root.update()

    # 获取窗口位置
    root.update()
    x = root.winfo_rootx()
    y = root.winfo_rooty()
    w = root.winfo_width()
    h = root.winfo_height()

    # 边界检查
    if w <= 0 or h <= 0:
        print(f"  [截图跳过] {name}: 窗口尺寸无效 {w}x{h}")
        return

    # 截取窗口区域
    img = ImageGrab.grab(bbox=(x, y, x + w, y + h))
    path = os.path.join(OUTPUT_DIR, f"{current_step:02d}_{name}.png")
    img.save(path)
    shots.append((name, path))
    print(f"  [截图] {name} -> {path}")
    current_step += 1


def create_demo_save():
    """创建一个演示用存档（有角色、有进度）"""
    loader = DataLoader()
    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
    config_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config")
    loader.load_all(data_dir, config_dir)

    # 创建测试角色
    hero1 = Hero(
        name="艾莉丝",
        job=loader.jobs[0],
        race=loader.races[0],
        level=5,
        exp=200,
        hp=80, max_hp=80,
        mp=40, max_mp=40,
        atk=22, defense=15, spd=18,
        skills=[loader.skills[0]] if loader.skills else [],
        equipment={"weapon": None, "armor": None, "accessory": None},
        sp=10,
        gold=350,
    )
    hero2 = Hero(
        name="格勒",
        job=loader.jobs[1] if len(loader.jobs) > 1 else loader.jobs[0],
        race=loader.races[1] if len(loader.races) > 1 else loader.races[0],
        level=4,
        exp=150,
        hp=65, max_hp=65,
        mp=55, max_mp=55,
        atk=18, defense=12, spd=20,
        skills=[],
        equipment={"weapon": None, "armor": None, "accessory": None},
        sp=8,
        gold=350,
    )
    hero3 = Hero(
        name="瑟兰",
        job=loader.jobs[2] if len(loader.jobs) > 2 else loader.jobs[0],
        race=loader.races[2] if len(loader.races) > 2 else loader.races[0],
        level=3,
        exp=80,
        hp=50, max_hp=50,
        mp=30, max_mp=30,
        atk=15, defense=10, spd=14,
        skills=[],
        equipment={"weapon": None, "armor": None, "accessory": None},
        sp=5,
        gold=350,
    )

    save_data = {
        "heroes": [h.to_dict() for h in [hero1, hero2, hero3]],
        "gold": 350,
        "day": 3,
        "story_flags": {},
        "unlocked_dungeons": [d.id for d in loader.dungeons[:3]],
        "cleared_dungeons": [],
        "floor_progress": {},
        "_hash": "",
    }
    # 计算哈希
    import hashlib, json as j
    hash_content = j.dumps({k: v for k, v in save_data.items() if k != "_hash"}, ensure_ascii=False, sort_keys=True)
    save_data["_hash"] = hashlib.sha256(hash_content.encode("utf-8")).hexdigest()

    save_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "save.json")
    with open(save_path, "w", encoding="utf-8") as f:
        j.dump(save_data, f, ensure_ascii=False, indent=2)
    print(f"[演示存档] 已创建: {save_path}")
    return save_path


def run_demo():
    """运行自动演示"""
    print("=" * 60)
    print("探险日志 - 自动演示截图")
    print("=" * 60)

    # 先创建演示存档
    create_demo_save()

    # 导入主应用（需要修改导入方式以避免直接 mainloop）
    from gui.app import App

    root = tk.Tk()
    root.title("探险日志 - 演示模式")
    root.geometry("1100x750")

    # 创建应用实例但不启动 mainloop
    app = App(root)

    # 等待窗口渲染
    root.update()
    time.sleep(0.5)

    print("\n[阶段 1] 酒馆页面")
    take_screenshot(root, "01_酒馆_初始")

    # 模拟输入角色名
    print("  模拟招募操作...")
    # 找到酒馆页面的名字输入框
    # 由于是 Mixin 模式，直接调用 recruit 相关方法
    # 先截图当前状态
    take_screenshot(root, "02_酒馆_准备招募")

    print("\n[阶段 2] 切换到郊外页面")
    # 找到 ttk.Notebook 并切换到郊外 tab
    def find_notebook(widget):
        if isinstance(widget, ttk.Notebook):
            return widget
        for child in widget.winfo_children():
            result = find_notebook(child)
            if result:
                return result
        return None

    nb = find_notebook(root)
    if nb:
        nb.select(1)  # 郊外 tab
        root.update()
        time.sleep(0.5)
        take_screenshot(root, "03_郊外_初始")

        # 选择地下城并开始探索
        print("  模拟选择地下城...")
        take_screenshot(root, "04_郊外_选择地下城")

        # 如果有开始探索按钮，点击它
        # 由于无法直接模拟点击，我们截图当前状态
        print("  (需要手动操作来推进演示)")
    else:
        print("  [警告] 未找到 Notebook 控件")

    print("\n[阶段 3] 切换到旅店页面")
    if nb:
        nb.select(2)
        root.update()
        time.sleep(0.5)
        take_screenshot(root, "05_旅店")

    print("\n[阶段 4] 切换到商店页面")
    if nb:
        nb.select(3)
        root.update()
        time.sleep(0.5)
        take_screenshot(root, "06_商店")

    print("\n[阶段 5] 切换到仓库页面")
    if nb:
        nb.select(4)
        root.update()
        time.sleep(0.5)
        take_screenshot(root, "07_仓库")

    print("\n[阶段 6] 回到酒馆，模拟掷骰")
    if nb:
        nb.select(0)
        root.update()
        time.sleep(0.5)
        take_screenshot(root, "08_酒馆_掷骰界面")

    print("\n" + "=" * 60)
    print(f"截图完成！共 {len(shots)} 张")
    print(f"输出目录: {OUTPUT_DIR}")
    print("=" * 60)

    # 生成截图清单
    manifest_path = os.path.join(OUTPUT_DIR, "manifest.txt")
    with open(manifest_path, "w", encoding="utf-8") as f:
        f.write("# 探险日志演示截图清单\n\n")
        for name, path in shots:
            f.write(f"{name}: {os.path.basename(path)}\n")

    print(f"\n清单已保存到: {manifest_path}")

    # 不启动主循环，直接退出
    root.destroy()


if __name__ == "__main__":
    run_demo()
