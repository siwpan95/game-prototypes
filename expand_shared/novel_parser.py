"""Novel Parser — 小说文本解析器（用于从原始小说生成游戏数据）。"""

from __future__ import annotations
import os
import re
from typing import Any


class StoryAnalyzer:
    """
    故事数据分析器。

    加载并分析 assets/data/ 下的 JSON 数据文件，
    为 Generator 提供结构化的故事信息。
    """

    def __init__(self, data_dir: str = ""):
        self.data_dir = data_dir
        self.entries: list[dict] = []
        self.raw_text: str = ""

    def load(self) -> None:
        """加载所有可用的故事数据文件。"""
        if not self.data_dir:
            return

        # 尝试加载 story.json 或 narratives.json
        for filename in ["story.json", "narratives.json"]:
            path = os.path.join(self.data_dir, filename)
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        import json
                        data = json.load(f)
                    if isinstance(data, dict):
                        # narratives 格式: {id: text}
                        for key, value in data.items():
                            if isinstance(value, str):
                                self.entries.append({"id": key, "text": value})
                            elif isinstance(value, (list, dict)):
                                self.entries.append({"id": key, "data": value})
                    elif isinstance(data, list):
                        for item in data:
                            self.entries.append(item)
                except Exception as e:
                    print(f"[StoryAnalyzer] 加载 {filename} 失败: {e}")

    def get_entries_by_chapter(self, chapter_pattern: str) -> list[dict]:
        """按章节过滤条目。"""
        return [e for e in self.entries if chapter_pattern in e.get("id", "")]

    def get_entry_count(self) -> int:
        return len(self.entries)

    def extract_keywords(self) -> dict[str, int]:
        """提取关键词频率。"""
        freq: dict[str, int] = {}
        for entry in self.entries:
            text = entry.get("text", "") or entry.get("data", "")
            if isinstance(text, str):
                for word in re.findall(r'[\u4e00-\u9fff]+', text):
                    freq[word] = freq.get(word, 0) + 1
        return dict(sorted(freq.items(), key=lambda x: -x[1])[:50])


class NovelParser:
    """原始小说文本解析器（用于将纯文本转换为 JSON 数据）。"""

    @staticmethod
    def parse_chapters(text: str, chapter_markers: list[str] | None = None) -> list[dict]:
        """
        将文本按章节标记分割为章节列表。

        Args:
            text: 原始文本
            chapter_markers: 章节标题正则模式列表

        Returns:
            [{"chapter_id": ..., "title": ..., "text": ...}, ...]
        """
        chapters = []
        markers = chapter_markers or [
            r"第[一二三四五六七八九十百千]+章",
            r"Chapter\s*\d+",
            r"第\d+集",
            r"\d+\.\s+[^\n]+",
        ]

        # 简化版：如果无明确标记，整体作为一章
        chapters.append({
            "chapter_id": "main",
            "title": "正文",
            "text": text,
        })
        return chapters

    @staticmethod
    def extract_dialogue(text: str) -> list[dict]:
        """
        从文本中提取对话。

        Returns:
            [{"speaker": ..., "content": ..., "context": ...}, ...]
        """
        dialogues = []
        # 匹配中文对话引号模式
        pattern = r'["「](.+?)["」]'
        for match in re.finditer(pattern, text):
            content = match.group(1)
            if "：" in content and len(content) < 100:
                parts = content.split("：", 1)
                dialogues.append({
                    "speaker": parts[0].strip() if len(parts) > 1 else "",
                    "content": parts[1].strip() if len(parts) > 1 else content,
                    "context": text[max(0, match.start()-20):match.end()+20],
                })
        return dialogues
