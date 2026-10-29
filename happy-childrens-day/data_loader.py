"""
Excel 数据加载器
使用 pandas 读取 snacks.xlsx，把零食配置变成数据驱动的配置表。
"""
import os
import pandas as pd
from components import SnackData

# 稀有度配置：rarity -> (unlock_level, 名称)
RARITY_TABLE = [
    ("common",    1,   "普通"),
    ("uncommon",  2,   "稀有"),
    ("rare",      4,   "精品"),
    ("epic",      6,   "史诗"),
    ("legendary", 8,   "传说"),
]


def _score_to_rarity(score):
    """根据分数分档返回稀有度和解锁等级"""
    if score <= 60:    return ("common", 1)
    elif score <= 120: return ("uncommon", 2)
    elif score <= 200: return ("rare", 4)
    elif score <= 399: return ("epic", 6)
    else:              return ("legendary", 8)


class SnackConfig:
    def __init__(self, file_path=None):
        if file_path is None:
            file_path = os.path.join(os.path.dirname(__file__), "snacks.xlsx")
        self.df = pd.read_excel(file_path)
        # 过滤掉占位符行（name 为 '_' 的无效行）
        self.df = self.df[self.df['name'] != '_']
        # 按等级解锁阈值排序 score 列用于过滤
        self.df['_score_int'] = self.df['score'].astype(int)
        self.df = self.df.sort_values('_score_int')
        # 将 DataFrame 转换为字典，方便通过 ID 查找
        self.config_map = self.df.set_index('id').T.to_dict()

    def get_snack_by_id(self, snack_id):
        """根据 ID 获取零食配置"""
        if snack_id in self.config_map:
            cfg = self.config_map[snack_id]
            score_val = int(cfg['score'])
            rarity, unlock = _score_to_rarity(score_val)
            return SnackData(
                cfg['name'], cfg['shape'], cfg['label'], cfg['type'],
                int(cfg['hp_change']), score_val, cfg['color'],
                int(cfg.get('duration', 0)), int(cfg.get('value', 0)),
                rarity, unlock,
            )
        return None

    def get_random_snack_id(self):
        """随机获取一个零食 ID"""
        return self.df.sample(1).iloc[0]['id']

    def get_random_snack_id_for_level(self, level):
        """根据玩家等级，随机获取一个已解锁的零食 ID"""
        eligible = self.df[self.df['_score_int'].apply(
            lambda s: _score_to_rarity(s)[1] <= level
        )]
        if eligible.empty:
            return self.get_random_snack_id()
        return eligible.sample(1).iloc[0]['id']
