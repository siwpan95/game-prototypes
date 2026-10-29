# -*- coding: utf-8 -*-
"""build_all.py —— 逐游戏分体打包（发行方案①）。

产物布局：
  dist/arcade.exe              选单（onefile，仅 tkinter）
  dist/games/<sub>/<sub>.exe   各游戏（onedir，contents_directory="." 平铺：
                               exe+dll+数据同目录，__file__ 相对与 cwd 相对都成立）
用法：python build_all.py [--only tetris] [--menu-only]
"""
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent
GAMES_DIR = ROOT / "games"
DIST = ROOT / "dist"
BUILD = ROOT / "build"

GAMES = [
    ("tetris", "main.py", False, []),
    ("tictactoe", "井字棋8.py", False, []),
    ("moyuxiaqi", "moyuxiaqi.py", False, []),
    ("kid-a-walker", "kid_a_walker.py", False, []),
    ("ski", "main.py", False, []),
    ("puzzle", "main.py", False, []),
    ("2048", "main.py", True, []),
    ("calculator", "main.py", False, []),
    ("rider", "main.py", False, []),
    ("sixone", "main.py", False, ["sqlalchemy", "torch", "cv2", "numba", "llvmlite", "scipy", "matplotlib", "PIL", "moviepy", "sklearn", "keras", "tensorflow", "ffmpeg"]),
]


def game_datas(sub):
    d = GAMES_DIR / sub
    datas = []
    for f in d.iterdir():
        if f.is_file() and f.suffix.lower() not in {".py", ".pyc", ".spec"}:
            datas.append((str(f), "."))
    return datas


def build_game(sub, entry, console, excludes):
    d = GAMES_DIR / sub
    datas = game_datas(sub)
    # 优先使用游戏自带 spec（复杂游戏需要 hiddenimports/动态库收集，
    # 如 kid-a-walker 的 moderngl/glcontext）；否则自动生成通用 spec。
    own = d / (sub + ".spec")
    if own.exists():
        spec = own
    else:
        spec = BUILD / sub / (sub + ".spec")
        spec.parent.mkdir(parents=True, exist_ok=True)
        body = (
            "# -*- mode: python ; coding: utf-8 -*-\n"
            "# %s —— 逐游戏分体打包（自动生成，勿手改）\n"
            "a = Analysis(\n"
            "    [%r],\n"
            "    pathex=[%r],\n"
            "    binaries=[],\n"
            "    datas=%r,\n"
            "    hiddenimports=[],\n"
            "    hookspath=[],\n"
            "    hooksconfig={},\n"
            "    runtime_hooks=[],\n"
            "    excludes=%r,\n"
            "    noarchive=False,\n"
            ")\n"
            "pyz = PYZ(a.pure)\n"
            "exe = EXE(\n"
            "    pyz,\n"
            "    a.scripts,\n"
            "    [],\n"
            "    exclude_binaries=True,\n"
            "    name='%s',\n"
            "    debug=False,\n"
            "    bootloader_ignore_signals=False,\n"
            "    strip=False,\n"
            "    upx=False,\n"
            "    console=%s,\n"
            "    contents_directory='.',\n"
            ")\n"
            "coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='%s')\n"
        ) % (sub, str(d / entry), str(d), datas, excludes, sub, str(console), sub)
        spec.write_text(body, encoding="utf-8")
    print("[build] " + sub + " ...", flush=True)
    r = subprocess.run(
        [sys.executable, "-m", "PyInstaller", str(spec), "--noconfirm",
         "--distpath", str(DIST / "games"), "--workpath", str(BUILD / sub / "work")],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    ok = r.returncode == 0
    if not ok:
        print((r.stdout or "")[-400:])
        print((r.stderr or "")[-400:])
    print("[%s] %s (exit %d)" % ("OK" if ok else "FAIL", sub, r.returncode), flush=True)
    return ok


def build_menu():
    print("[build] arcade-menu ...", flush=True)
    spec = BUILD / "menu" / "arcade-menu.spec"
    spec.parent.mkdir(parents=True, exist_ok=True)
    body = (
        "# -*- mode: python ; coding: utf-8 -*-\n"
        "# 选单 onefile（仅 tkinter）\n"
        "a = Analysis(\n"
        "    [%r],\n"
        "    pathex=[%r],\n"
        "    binaries=[],\n"
        "    datas=[],\n"
        "    hiddenimports=[],\n"
        "    hookspath=[],\n"
        "    hooksconfig={},\n"
        "    runtime_hooks=[],\n"
        "    excludes=['pygame', 'numpy', 'pandas', 'sounddevice', 'scipy', 'PIL'],\n"
        "    noarchive=False,\n"
        ")\n"
        "pyz = PYZ(a.pure)\n"
        "exe = EXE(\n"
        "    pyz,\n"
        "    a.scripts,\n"
        "    exclude_binaries=True,\n"
        "    name='arcade',\n"
        "    debug=False,\n"
        "    bootloader_ignore_signals=False,\n"
        "    strip=False,\n"
        "    upx=False,\n"
        "    console=False,\n"
        ")\n"
    ) % (str(ROOT / "main.py"), str(ROOT))
    spec.write_text(body, encoding="utf-8")
    r = subprocess.run(
        [sys.executable, "-m", "PyInstaller", str(spec), "--noconfirm",
         "--distpath", str(DIST), "--workpath", str(BUILD / "menu" / "work")],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    ok = r.returncode == 0
    if not ok:
        print((r.stdout or "")[-400:])
        print((r.stderr or "")[-400:])
    else:
        built = BUILD / "menu" / "work" / "arcade-menu" / "arcade.exe"
        if built.exists():
            import shutil as _sh
            DIST.mkdir(parents=True, exist_ok=True)
            _sh.copy2(str(built), str(DIST / "arcade.exe"))
            print("[menu] 已复制 arcade.exe → dist/", flush=True)
    print("[%s] arcade-menu (exit %d)" % ("OK" if ok else "FAIL", r.returncode), flush=True)
    return ok


def main():
    args = sys.argv[1:]
    only = None
    menu_only = "--menu-only" in args
    if "--only" in args:
        i = args.index("--only")
        if i + 1 < len(args):
            only = args[i + 1]
    results = []
    if not menu_only:
        for sub, entry, console, excludes in GAMES:
            if only and sub != only:
                continue
            results.append((sub, build_game(sub, entry, console, excludes)))
    if not only:
        results.append(("arcade-menu", build_menu()))
    fails = [n for n, ok in results if not ok]
    print("== 完成：%d 成功 / %d 失败%s" % (
        len(results) - len(fails), len(fails), ("：" + ", ".join(fails)) if fails else ""), flush=True)
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
