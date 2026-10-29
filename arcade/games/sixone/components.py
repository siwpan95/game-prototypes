"""
组件定义 (Components) - 纯数据
所有组件只负责存储数据，不包含任何逻辑。
"""


class Transform:
    """位置与尺寸"""
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.size = 32


class Render:
    """渲染信息：颜色、图形类型、标签文字、轮廓色"""
    def __init__(self, color="yellow", shape="circle", label="*", outline="#333333"):
        self.color = color       # 填充色
        self.shape = shape       # circle / square / diamond / triangle / star
        self.label = label       # 图形中央的短文本（单字母）
        self.outline = outline   # 轮廓线颜色


class Movement:
    """移动速度与方向"""
    def __init__(self, speed=5):
        self.speed = speed
        self.vx = 0
        self.vy = 0


class Health:
    """生命值"""
    def __init__(self, hp=100):
        self.hp = hp


class Score:
    """得分"""
    def __init__(self):
        self.value = 0


class Collider:
    """碰撞体半径"""
    def __init__(self, radius=15):
        self.radius = radius


class GameState:
    """游戏全局状态"""
    def __init__(self):
        self.is_over = False
        self.is_win = False
        self.level = 1


class SnackData:
    """存储从 Excel 读取的零食属性"""
    def __init__(self, name, shape="circle", label="?", snack_type="heal",
                 hp_change=0, score=0, color="white",
                 duration=0, value=0, rarity="common", unlock_level=1):
        # 兼容两种调用方式：
        # data_loader:  (name, shape, label, type, hp_change, score, color, duration, value, rarity, unlock) — 11个位置参数
        # main.py 手动: (name="力量糖果", shape="diamond", label="P", snack_type="power", hp_change=5, ...) — 关键字参数
        self.name = name
        self.shape = shape
        self.label = label
        self.type = snack_type
        self.hp_change = hp_change
        self.score_value = score
        self.color = color
        self.duration = duration
        self.value = value


class StatusEffect:
    """存储玩家的异常状态"""
    def __init__(self):
        self.is_invincible = False
        self.is_reversed = False
        self.effect_end_time = 0


class Shield:
    """护盾组件"""
    def __init__(self, value):
        self.value = value
