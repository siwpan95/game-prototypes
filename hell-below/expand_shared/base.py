"""
Base Expander — 所有游戏扩充工具的抽象基类。

提供：
  - JSON 备份/恢复
  - UTF-8 安全读写（避免 Windows sed 破坏 CJK 字符）
  - 变更追踪日志
  - dry-run 模式支持

子类只需实现 run() 方法即可。
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from datetime import datetime
from typing import Any, Optional


class BaseExpander:
    """
    数据扩充工具基类。

    使用方式：
      1. 子类继承并设置 DATA_DIR
      2. 实现 run() 方法（在其中调用 self.load_json / self.save_json / self.backup_json）
      3. 调用 execute(dry_run=False) 执行
    """

    # 子类必须设置
    DATA_DIR: str = ""

    def __init__(self):
        if not self.DATA_DIR:
            raise ValueError("子类必须设置 DATA_DIR 类属性")
        self._changes: list[dict] = []
        self._backup_dir: str = os.path.join(self.DATA_DIR, "_backups")
        self._dry_run: bool = False

    # ========== 核心 API ==========

    def execute(self, dry_run: bool = False) -> None:
        """执行扩充流程。"""
        self._dry_run = dry_run
        self._changes.clear()

        print(f"\n{'='*50}")
        print(f"  Expander: {self.__class__.__name__}")
        print(f"  数据目录: {self.DATA_DIR}")
        print(f"  模式: {'DRY-RUN (预览)' if dry_run else 'LIVE (实际写入)'}")
        print(f"{'='*50}\n")

        try:
            self.run()
            self._print_summary()
        except Exception as e:
            print(f"[ERROR] 扩充失败: {e}")
            import traceback
            traceback.print_exc()

    def run(self) -> None:
        """子类实现 — 具体的扩充逻辑。"""
        raise NotImplementedError("子类必须实现 run() 方法")

    # ========== JSON 操作（UTF-8 安全）==========

    def load_json(self, filename: str) -> Any:
        """
        加载 JSON 文件。

        Returns:
            解析后的 Python 对象，或 {} / [] 如果文件不存在
        """
        path = os.path.join(self.DATA_DIR, filename)
        if not os.path.exists(path):
            print(f"  [LOAD] {filename} 不存在（跳过），返回空")
            if filename.endswith(".json"):
                return {} if not filename.startswith(("narratives", "puzzles")) else []
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            print(f"  [LOAD] {filename}: 已加载 ({_count_data(data)} 条记录)")
            return data
        except (json.JSONDecodeError, OSError) as e:
            print(f"  [LOAD] {filename} 加载失败: {e}")
            return {}

    def save_json(self, filename: str, data: Any) -> bool:
        """
        保存 JSON 文件（UTF-8，ensure_ascii=False）。

        在 dry-run 模式下只打印预览不写入。
        """
        if self._dry_run:
            print(f"  [SAVE|DRY-RUN] {filename}: 将写入 ({_count_data(data)} 条记录)")
            return True

        path = os.path.join(self.DATA_DIR, filename)
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(path) or self.DATA_DIR, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            record = f"已保存 {_count_data(data)} 条记录"
            self.record_change(filename, record)
            return True
        except (OSError, TypeError) as e:
            print(f"  [SAVE|ERROR] {filename} 写入失败: {e}")
            return False

    def backup_json(self, filename: str) -> str | None:
        """
        备份 JSON 文件到 _backups 目录。

        Returns:
            备份文件路径，或 None 如果源文件不存在
        """
        src = os.path.join(self.DATA_DIR, filename)
        if not os.path.exists(src):
            return None

        os.makedirs(self._backup_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{ts}_{filename}"
        dst = os.path.join(self._backup_dir, backup_name)

        try:
            shutil.copy2(src, dst)
            print(f"  [BACKUP] {filename} → _backups/{backup_name}")
            return dst
        except OSError as e:
            print(f"  [BACKUP|ERROR] {filename} 备份失败: {e}")
            return None

    def restore_backup(self, filename: str, backup_path: str | None = None) -> bool:
        """从备份恢复文件。"""
        if backup_path is None:
            # 找最新备份
            pattern = f"*_{filename}"
            import glob
            candidates = glob.glob(os.path.join(self._backup_dir, pattern))
            if not candidates:
                print(f"  [RESTORE] 无 {filename} 的备份")
                return False
            backup_path = max(candidates, key=os.path.getmtime)

        src = os.path.join(self.DATA_DIR, filename)
        try:
            shutil.copy2(backup_path, src)
            print(f"  [RESTORE] _backups/{os.path.basename(backup_path)} → {filename}")
            return True
        except OSError as e:
            print(f"  [RESTORE|ERROR] 恢复失败: {e}")
            return False

    # ========== 变更追踪 ==========

    def record_change(self, filename: str, message: str) -> None:
        """记录一条变更。"""
        self._changes.append({
            "file": filename,
            "message": message,
            "time": datetime.now().isoformat(),
        })

    def _print_summary(self) -> None:
        """打印变更摘要。"""
        print(f"\n{'─'*50}")
        print(f"  变更摘要:")
        print(f"{'─'*50}")

        by_file: dict[str, list[str]] = {}
        for c in self._changes:
            by_file.setdefault(c["file"], []).append(c["message"])

        for fname, messages in sorted(by_file.items()):
            print(f"\n  📄 {fname}:")
            for msg in messages:
                print(f"      • {msg}")

        total = len(self._changes)
        mode_text = "DRY-RUN（无文件被修改）" if self._dry_run else "LIVE（文件已修改）"
        print(f"\n  总计 {total} 条变更 [{mode_text}]")
        print(f"{'='*50}\n")


def _count_data(data: Any) -> int:
    """估算数据条目数。"""
    if isinstance(data, dict):
        return len(data)
    if isinstance(data, (list, tuple)):
        return len(data)
    if isinstance(data, str):
        return len(data)
    return 1
