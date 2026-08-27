"""
expand_shared 运行入口 — 统一扩充工具命令行接口。

用法：
  python -m expand_shared.run --game <game_name> [--dry-run]

支持的游戏通过 --game 参数选择，或直接 import 对应 Expander 子类。
"""

from __future__ import annotations

import argparse
import os
import sys


def get_expander_class(game_name: str):
    """根据游戏名返回对应的 Expander 类。"""
    # 动态导入：每个游戏的 expand/run.py 中定义了 VxExpander
    _CH_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    game_dir = os.path.join(_CH_ROOT, game_name)
    expand_run_path = os.path.join(game_dir, "expand", "run.py")

    if not os.path.exists(expand_run_path):
        raise FileNotFoundError(f"游戏 {game_name} 的 expand/run.py 不存在: {expand_run_path}")

    # 将游戏目录加入路径以便导入
    if game_dir not in sys.path:
        sys.path.insert(0, game_dir)
    if _CH_ROOT not in sys.path:
        sys.path.insert(0, _CH_ROOT)

    import importlib
    spec = importlib.util.spec_from_file_location("expander_run", expand_run_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    # 查找 Expander 类
    for attr_name in dir(mod):
        attr = getattr(mod, attr_name)
        if isinstance(attr, type) and hasattr(attr, '__bases__'):
            for base in getattr(attr, '__bases__', ()):
                base_name = f"{base.__module__}.{base.__name__}" if hasattr(base, '__module__') else ""
                if "BaseExpander" in base_name or "expander_shared" in base_name:
                    return attr

    raise RuntimeError(f"在 {game_name}/expand/run.py 中未找到 BaseExpander 子类")


def main():
    parser = argparse.ArgumentParser(
        description="Hell Below 统一数据扩充工具",
        epilog="示例: python -m expand_shared.run --game AlenAbot_zh --dry-run"
    )
    parser.add_argument("--game", "-g", required=True,
                        help="目标游戏目录名 (如 AlenAbot_zh, BrianSimpson_CN)")
    parser.add_argument("--dry-run", action="store_true",
                        help="预览变更，不实际写入文件")
    args = parser.parse_args()

    try:
        ExpanderClass = get_expander_class(args.game)
        expander = ExpanderClass()
        expander.execute(dry_run=args.dry_run)
    except Exception as e:
        print(f"[FATAL] {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
