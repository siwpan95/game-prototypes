"""一键拉取 BGM 资源（CC0）

来源：SoundHelix 示范曲（https://www.soundhelix.com，CC0 许可）。
用法：python scripts/fetch_music.py
产物：assets/music/{title,town,battle,dungeon}.mp3
"""
import os
import sys
import urllib.request

BASE = "https://www.soundhelix.com/examples/mp3"
TRACKS = {
    "title": "SoundHelix-Song-1.mp3",
    "town": "SoundHelix-Song-2.mp3",
    "battle": "SoundHelix-Song-3.mp3",
    "dungeon": "SoundHelix-Song-4.mp3",
}

CREDITS = """BGM 来源与许可
==============
全部曲目来自 SoundHelix (https://www.soundhelix.com)
许可：CC0 (Public Domain Dedication)，可自由使用与再分发。
曲目映射（原曲 → 游戏用途）：
  SoundHelix-Song-1.mp3 -> title.mp3   (标题/菜单)
  SoundHelix-Song-2.mp3 -> town.mp3    (城镇)
  SoundHelix-Song-3.mp3 -> battle.mp3  (战斗)
  SoundHelix-Song-4.mp3 -> dungeon.mp3 (遗迹/神殿)
"""


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    music_dir = os.path.join(root, "assets", "music")
    os.makedirs(music_dir, exist_ok=True)
    for name, remote in TRACKS.items():
        dest = os.path.join(music_dir, name + ".mp3")
        if os.path.exists(dest) and os.path.getsize(dest) > 1024 * 512:
            print(f"跳过 {name}（已存在）")
            continue
        url = f"{BASE}/{remote}"
        print(f"下载 {name} <- {url} ...")
        try:
            urllib.request.urlretrieve(url, dest)
            print(f"  完成: {os.path.getsize(dest) // 1024} KB")
        except Exception as e:
            print(f"  失败: {e}")
            return 1
    with open(os.path.join(music_dir, "CREDITS.txt"), "w", encoding="utf-8") as f:
        f.write(CREDITS)
    print("全部 BGM 就绪（含 CREDITS.txt）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
