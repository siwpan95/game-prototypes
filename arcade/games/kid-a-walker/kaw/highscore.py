# -*- coding: utf-8 -*-
"""最高分本地持久化。"""
import json
import os

# ─────────────────────── 最高分记录（P2-4） ─────────────────────────
HIGHSCORE_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "highscore.json")

def load_highscore() -> int:
    """从本地JSON加载最高分"""
    try:
        if os.path.exists(HIGHSCORE_FILE):
            with open(HIGHSCORE_FILE, 'r') as f:
                data = json.load(f)
                return data.get("highscore", 0)
    except Exception:
        pass
    return 0

def save_highscore(score: int):
    """保存最高分到本地JSON"""
    try:
        current = load_highscore()
        if score > current:
            with open(HIGHSCORE_FILE, 'w') as f:
                json.dump({"highscore": score}, f)
    except Exception:
        pass
