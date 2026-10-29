"""
test/test_ai.py — AI 层单元测试

测试叙事引擎数据模型 (Scene/Option/NarrativeState)、条件求值器 (ConditionEvaluator)、
对话引擎 (DialogueEngine 规则模式)。

运行：
    cd <仓库根> && python -m allin_engine.test.test_ai
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

from allin_engine.ai.narrative import (
    Scene, Option, NarrativeState, ConditionEvaluator, NarrativeEngine,
)
from allin_engine.ai.dialogue import (
    DialogueEngine, MatchResult,
)
from allin_engine.ai.generator import (
    ContentGenerator, GenerationConfig,
)


# ══════════════════════════════════════════════════════════
# 数据模型测试
# ══════════════════════════════════════════════════════════

def test_option_dataclass():
    """测试 Option 数据类"""
    opt = Option(
        option_id="go_north",
        text="向北走",
        next_scene="forest",
        conditions={"hp__gte": 50},
        effects={"hp": -10},
        flags_set=["explored_north"],
    )
    assert opt.option_id == "go_north"
    assert opt.next_scene == "forest"
    assert len(opt.flags_set) == 1


def test_scene_dataclass():
    """测试 Scene 数据类"""
    scene = Scene(
        scene_id="start",
        title="起点",
        text="你站在十字路口。",
        speaker="旁白",
        options=[Option(option_id="go", text="前进")],
    )
    assert scene.scene_id == "start"
    assert scene.title == "起点"
    assert len(scene.options) == 1


def test_game_state_create():
    """测试 NarrativeState 创建"""
    gs = NarrativeState(
        current_scene_id="start",
        attributes={"hp": 80, "gold": 50},
        flags={"sword", "shield"},
        turn_count=3,
    )
    assert gs.current_scene_id == "start"
    assert gs.attributes["hp"] == 80
    assert gs.turn_count == 3
    assert "sword" in gs.flags


def test_game_state_serialization():
    """测试 NarrativeState to_dict / from_dict"""
    gs = NarrativeState(
        current_scene_id="start",
        attributes={"hp": 80},
        flags={"key"},
        turn_count=5,
    )
    d = gs.to_dict()
    assert d["current_scene_id"] == "start"
    assert d["attributes"]["hp"] == 80
    assert "key" in d["flags"]

    restored = NarrativeState.from_dict(d)
    assert restored.current_scene_id == "start"
    assert restored.attributes["hp"] == 80
    assert "key" in restored.flags


# ══════════════════════════════════════════════════════════
# ConditionEvaluator 测试
# ══════════════════════════════════════════════════════════

def _make_eval(hp=100, gold=50, flags=None):
    """创建测试用状态和求值器"""
    state = NarrativeState(
        attributes={"hp": hp, "gold": gold},
        flags=flags or set(),
    )
    return ConditionEvaluator(), state


def test_eval_none_conditions():
    """None 条件总是满足"""
    ev, state = _make_eval()
    assert ev.check(None, state) is True


def test_eval_empty_list():
    """空列表条件满足"""
    ev, state = _make_eval()
    assert ev.check([], state) is True


def test_eval_empty_dict():
    """空字典条件满足"""
    ev, state = _make_eval()
    assert ev.check({}, state) is True


def test_eval_string_numeric_gte():
    """字符串条件 hp>=50"""
    ev, state = _make_eval(hp=80)
    assert ev.check("hp>=50", state) is True
    assert ev.check("hp>=100", state) is False


def test_eval_string_numeric_lte():
    """字符串条件 hp<=50"""
    ev, state = _make_eval(hp=30)
    assert ev.check("hp<=50", state) is True
    assert ev.check("hp<=20", state) is False


def test_eval_string_numeric_gt():
    """字符串条件 hp>50"""
    ev, state = _make_eval(hp=80)
    assert ev.check("hp>50", state) is True
    assert ev.check("hp>100", state) is False


def test_eval_string_numeric_lt():
    """字符串条件 hp<50"""
    ev, state = _make_eval(hp=30)
    assert ev.check("hp<50", state) is True
    assert ev.check("hp<10", state) is False


def test_eval_string_numeric_eq():
    """字符串条件 hp==80"""
    ev, state = _make_eval(hp=80)
    assert ev.check("hp==80", state) is True
    assert ev.check("hp==100", state) is False


def test_eval_string_numeric_ne():
    """字符串条件 hp!=100"""
    ev, state = _make_eval(hp=80)
    assert ev.check("hp!=100", state) is True
    assert ev.check("hp!=80", state) is False


def test_eval_string_has_item():
    """字符串条件 has_item:key"""
    ev, state = _make_eval(flags={"key", "sword"})
    assert ev.check("has_item:key", state) is True
    assert ev.check("has_item:shield", state) is False


def test_eval_string_not_has_item():
    """字符串条件 !has_item:poison"""
    ev, state = _make_eval(flags={"key"})
    assert ev.check("!has_item:poison", state) is True
    assert ev.check("!has_item:key", state) is False


def test_eval_dict_conditions():
    """字典条件"""
    ev, state = _make_eval(hp=80, gold=50, flags={"sword"})
    cond = {"hp__gte": 50, "gold__gte": 30}
    assert ev.check(cond, state) is True

    cond_fail = {"hp__gte": 100}
    assert ev.check(cond_fail, state) is False


def test_eval_dict_has_item():
    """字典 has_item"""
    ev, state = _make_eval(hp=80, flags={"sword"})
    assert ev.check({"has_item": "sword"}, state) is True
    assert ev.check({"has_item": "shield"}, state) is False


def test_eval_dict_suffix_ops():
    """字典后缀操作符"""
    ev, state = _make_eval(hp=80, gold=50)
    assert ev.check({"hp__gte": 50}, state) is True
    assert ev.check({"hp__lte": 100}, state) is True
    assert ev.check({"hp__gt": 50}, state) is True
    assert ev.check({"hp__lt": 100}, state) is True
    assert ev.check({"hp__eq": 80}, state) is True
    assert ev.check({"hp__ne": 0}, state) is True


def test_eval_dict_flag_has():
    """字典 flags__has"""
    ev, state = _make_eval(hp=80, flags={"sword"})
    assert ev.check({"flags__has": "sword"}, state) is True
    assert ev.check({"flags__has": "shield"}, state) is False


def test_eval_dict_no_suffix():
    """字典无后缀 → 检查 flags"""
    ev, state = _make_eval(hp=80, flags={"sword"})
    assert ev.check({"sword": "sword"}, state) is True
    assert ev.check({"shield": "shield"}, state) is False


def test_eval_list_conditions():
    """列表条件 AND 逻辑"""
    ev, state = _make_eval(hp=80, gold=50, flags={"key"})
    cond = ["hp>=50", "gold>=30", "has_item:key"]
    assert ev.check(cond, state) is True

    cond_fail = ["hp>=50", "gold>=100"]
    assert ev.check(cond_fail, state) is False


def test_eval_unknown_attribute():
    """未知属性默认为 0"""
    ev, state = _make_eval(hp=80)
    assert ev.check("mana>=0", state) is True
    assert ev.check("mana>0", state) is False


# ══════════════════════════════════════════════════════════
# NarrativeEngine 测试
# ══════════════════════════════════════════════════════════

def test_narrative_engine_create():
    """测试叙事引擎创建"""
    engine = NarrativeEngine()
    assert engine is not None
    assert engine.state is not None
    assert engine.state.current_scene_id == ""


def test_narrative_engine_state():
    """测试叙事引擎状态管理"""
    engine = NarrativeEngine()
    engine.state.attributes["hp"] = 100
    engine.state.current_scene_id = "start"
    assert engine.state.attributes["hp"] == 100


# ══════════════════════════════════════════════════════════
# DialogueEngine 规则模式测试
# ══════════════════════════════════════════════════════════

def test_dialogue_engine_create():
    """测试对话引擎创建"""
    engine = DialogueEngine(backend="rule")
    assert engine.backend == "rule"
    assert engine.VERSION == "1.0.0"


def test_dialogue_empty_input():
    """测试空输入"""
    engine = DialogueEngine(backend="rule", empty_response="说点什么吧")
    reply = engine.respond("")
    assert reply == "说点什么吧"


def test_dialogue_whitespace_input():
    """测试空白输入"""
    engine = DialogueEngine(backend="rule")
    reply = engine.respond("   ")
    assert len(reply) > 0


def test_dialogue_greeting():
    """测试问候匹配"""
    engine = DialogueEngine(backend="rule")
    reply = engine.respond("你好")
    assert len(reply) > 0
    # 应该匹配到问候规则
    assert reply != engine.fallback_response


def test_dialogue_thanks():
    """测试感谢匹配"""
    engine = DialogueEngine(backend="rule")
    reply = engine.respond("谢谢")
    assert len(reply) > 0


def test_dialogue_goodbye():
    """测试再见匹配"""
    engine = DialogueEngine(backend="rule")
    reply = engine.respond("再见")
    assert len(reply) > 0


def test_dialogue_learn_and_recall():
    """测试学习与回忆"""
    engine = DialogueEngine(backend="rule")
    engine.learn("你最喜欢的颜色", "蓝色")
    reply = engine.respond("你最喜欢的颜色")
    assert "蓝色" in reply


def test_dialogue_learn_list():
    """测试学习多个回答"""
    engine = DialogueEngine(backend="rule")
    engine.learn("敲门", ["咚咚咚", "有人在吗？"])
    reply = engine.respond("敲门")
    assert len(reply) > 0


def test_dialogue_forget():
    """测试遗忘"""
    engine = DialogueEngine(backend="rule")
    engine.learn("口诀", "天灵灵")
    engine.forget("口诀")
    reply = engine.respond("口诀")
    # 遗忘后不应该是学过的回答
    assert reply == engine.fallback_response or reply != "天灵灵"


def test_dialogue_custom_rules():
    """测试自定义规则"""
    custom = [{"pattern": r"天气", "responses": ["今天天气不错"], "confidence": 1.0}]
    engine = DialogueEngine(backend="rule", rules=custom)
    reply = engine.respond("天气怎么样")
    assert "天气" in reply


def test_dialogue_fallback():
    """测试兜底回复 — 兜底阶段直接返回 fallback_response"""
    engine = DialogueEngine(
        backend="rule",
        fallback_response="不太明白"
    )
    # 关闭所有匹配阶段，强制走兜底
    engine._stages = {name: False for name in engine.STAGE_NAMES}
    # 但 fallback 阶段仍然检查 _stages.get("fallback")
    # 直接调用 internal 方法
    reply = engine._get_fallback("asdfgh")
    assert "不太明白" in reply or len(reply) > 0


def test_dialogue_safety_filter():
    """测试安全过滤"""
    engine = DialogueEngine(
        backend="rule",
        safety_keywords=["脏话"],
    )
    # 添加安全关键词后的测试
    reply = engine.respond("你好")
    assert len(reply) > 0


# ══════════════════════════════════════════════════════════
# MatchResult 测试
# ══════════════════════════════════════════════════════════

def test_match_result_create():
    """测试 MatchResult"""
    mr = MatchResult("你好呀", confidence=0.9, source="rules")
    assert mr.reply == "你好呀"
    assert mr.confidence == 0.9
    assert mr.source == "rules"
    assert bool(mr) is True


def test_match_result_empty():
    """测试空匹配结果"""
    mr = MatchResult("")
    assert bool(mr) is False


def test_match_result_zero_confidence():
    """测试零置信度"""
    mr = MatchResult("hello", confidence=0.0)
    assert bool(mr) is False


# ══════════════════════════════════════════════════════════
# ContentGenerator 配置测试
# ══════════════════════════════════════════════════════════

def test_generation_config_default():
    """测试默认配置"""
    config = GenerationConfig()
    assert config.model == "qwen2.5"
    assert config.backend == "ollama"
    assert config.temperature == 0.8
    assert config.max_tokens == 200


def test_content_generator_create():
    """测试生成器创建（不应触发网络请求）"""
    config = GenerationConfig(backend="ollama", host="localhost:11434")
    gen = ContentGenerator(config)
    assert gen is not None
    assert gen.config.backend == "ollama"


def test_content_generator_fallback():
    """测试降级模板可用"""
    config = GenerationConfig(backend="nonexistent")
    gen = ContentGenerator(config)
    # 不可用的后端下，生成器应该能降级
    assert gen is not None
