"""核心模块：签到逻辑、表情引擎、风扇引擎、映射、音频"""
from .qiandao import QiandaoState, reinforcement_prob, choose_reward, load_rewards_config
from .face_engine import FaceEngine
from .fan_engine import FanEngine
from .expression_map import result_to_expression, RARITY_EXPRESSION_MAP, NO_REWARD_EXPRESSION_MAP
from .audio import AudioManager
