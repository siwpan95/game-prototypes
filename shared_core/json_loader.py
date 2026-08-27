"""
JSON Loader — 通用 JSON 数据加载器（带缓存）。
"""

from __future__ import annotations

import json
import os
from typing import Any, Optional


class JSONLoader:
    """加载并缓存 JSON 数据文件。"""

    def __init__(self, data_dir: str = ""):
        self.data_dir = data_dir or ""
        self._cache: dict[str, Any] = {}

    def load(self, filename: str) -> Optional[Any]:
        """加载 JSON 文件（带缓存）。"""
        if filename in self._cache:
            return self._cache[filename]

        path = os.path.join(self.data_dir, filename) if self.data_dir else filename
        if not os.path.exists(path):
            return None

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._cache[filename] = data
            return data
        except (json.JSONDecodeError, OSError) as e:
            print(f"[JSONLoader] 加载失败 {path}: {e}")
            return None

    def load_mandatory(self, filename: str) -> Any:
        """必须加载 — 缺失则抛出异常。"""
        data = self.load(filename)
        if data is None:
            raise FileNotFoundError(f"必需数据文件缺失: {filename}")
        return data

    def clear_cache(self) -> None:
        self._cache.clear()

    def reload(self, filename: str) -> Optional[Any]:
        self._cache.pop(filename, None)
        return self.load(filename)

    def list_available(self, pattern: str = "*.json") -> list[str]:
        """列出 data_dir 下所有匹配的文件名。"""
        if not self.data_dir or not os.path.isdir(self.data_dir):
            return []
        import glob
        full_pattern = os.path.join(self.data_dir, pattern)
        return [os.path.basename(f) for f in glob.glob(full_pattern)]
