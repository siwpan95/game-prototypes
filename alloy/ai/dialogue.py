"""
对话引擎：6阶段管道 + 规则匹配 + AI驱动，支持自动降级。

融合 easy-ai 的 ResponsePipeline 架构和 ollama_generator 的AI后端，
提供统一的对话管理和响应生成接口。

管道阶段：
1. 空输入检查 — 空消息直接返回提示
2. 安全过滤 — 敏感词拦截
3. 专用响应器 — 可选的自定义处理函数
4. 精确记忆匹配 — 已学过的问答对
5. 规则匹配 — 正则 + 模糊匹配（置信度竞争模式）
6. 兜底回复 — 内置或 AI 生成

用法：
    from ai.dialogue import DialogueEngine

    engine = DialogueEngine(backend="rule")  # 纯规则模式
    reply = engine.respond("你好")
    engine.learn("你叫什么", "我叫小明")

    # AI 驱动模式（需要 ollama 或 deepseek）
    engine = DialogueEngine(backend="ai", model="qwen2.5")
    reply = engine.respond("讲个故事")
"""

import json
import random
import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple


# ============================================================
# 规则配置
# ============================================================

_DEFAULT_RULES: List[Dict[str, Any]] = [
    {
        "pattern": r"你好|嗨|hello|hi|哈喽",
        "responses": ["你好呀！", "嗨！有什么可以帮你的？", "你好，很高兴见到你！"],
        "confidence": 0.9,
    },
    {
        "pattern": r"谢谢|多谢|感谢|thanks?",
        "responses": ["不客气！", "能帮到你就好。", "随时为你效劳。"],
        "confidence": 0.9,
    },
    {
        "pattern": r"再见|拜拜|bye|回头见",
        "responses": ["再见！", "下次见！", "祝你冒险顺利！"],
        "confidence": 0.9,
    },
    {
        "pattern": r"你叫什么|你的名字|你是谁",
        "responses": [
            "我是冒险助手，随时为你提供帮助。",
            "你可以叫我AI助手，有什么需要吗？",
        ],
        "confidence": 0.85,
    },
    {
        "pattern": r"帮助|help|怎么玩|教程",
        "responses": [
            "你可以和我对话来探索这个世界。试试说'查看周围'或'向前走'吧！",
            "这是一个文字冒险游戏。你可以通过对话来推进剧情、探索场景、和角色互动。",
        ],
        "confidence": 0.8,
    },
    {
        "pattern": r".*",
        "responses": [
            "这个话题很有意思，能再详细说说吗？",
            "嗯，我在听。",
            "不太确定该怎么回应，但你可以教我。",
            "原来如此……有什么我可以帮你的吗？",
        ],
        "confidence": 0.2,
    },
]


# ============================================================
# 匹配结果
# ============================================================

class MatchResult:
    """匹配结果，包含回复文本和置信度。

    Attributes:
        reply: 回复文本。
        confidence: 置信度，0.0-1.0。
        source: 匹配来源名称（用于调试）。
    """

    __slots__ = ("reply", "confidence", "source")

    def __init__(self, reply: str, confidence: float = 1.0, source: str = ""):
        self.reply = reply
        self.confidence = confidence
        self.source = source

    def __bool__(self) -> bool:
        return bool(self.reply) and self.confidence > 0

    def __repr__(self) -> str:
        return f"<MatchResult '{self.reply[:20]}...' conf={self.confidence:.2f} src={self.source}>"


# ============================================================
# 对话引擎
# ============================================================

class DialogueEngine:
    """对话管理和响应生成引擎。

    支持两种驱动模式：
    - "rule"：纯规则驱动（正则匹配 + 模糊匹配 + 记忆库）
    - "ai"：AI 驱动（ollama/deepseek），不可用时自动降级为规则模式

    用法：
        engine = DialogueEngine(backend="rule")
        engine.load_rules("rules.json")
        reply = engine.respond("你好，这里是什么地方？")
    """

    VERSION = "1.0.0"

    # 管道阶段名称
    STAGE_NAMES = ("empty", "safety", "specialized", "memory", "rules", "fallback")

    def __init__(
        self,
        *,
        backend: str = "rule",
        model: str = "qwen2.5",
        rules: Optional[List[Dict[str, Any]]] = None,
        safety_keywords: Optional[List[str]] = None,
        empty_response: str = "请说点什么吧。",
        fallback_response: str = "我不太明白，你能换个方式说吗？",
    ):
        """初始化对话引擎。

        Args:
            backend: 驱动模式。"rule"（纯规则）或 "ai"（AI驱动）。
            model: AI 模式下的模型名。
            rules: 自定义规则列表，覆盖默认规则。
            safety_keywords: 安全过滤关键词列表。
            empty_response: 空输入时的回复。
            fallback_response: 所有阶段都未匹配时的兜底回复。
        """
        self.backend = backend
        self.model = model
        self.empty_response = empty_response
        self.fallback_response = fallback_response

        # 记忆库：问题 → 答案列表
        self._memory: Dict[str, List[str]] = {}
        # 规则列表
        self._rules: List[Dict[str, Any]] = rules or _DEFAULT_RULES.copy()
        # 安全关键词
        self._safety_keywords: List[str] = safety_keywords or []
        # 专用响应器
        self._specialized_responders: List[Callable[[str], Optional[str]]] = []
        # 自定义匹配器
        self._custom_matchers: List[Callable[[str], Optional[MatchResult]]] = []
        # 管道阶段开关
        self._stages: Dict[str, bool] = {
            name: True for name in self.STAGE_NAMES
        }

        # AI 生成器（延迟初始化）
        self._generator: Any = None

    # ============================================================
    # 主接口
    # ============================================================

    def respond(self, message: str, context: Optional[Dict[str, Any]] = None) -> str:
        """处理用户输入，返回回复。

        按管道阶段顺序处理：空输入 → 安全 → 专用 → 记忆 → 规则 → 兜底。

        Args:
            message: 用户输入的文本。
            context: 可选的对话上下文。

        Returns:
            AI/规则的回复文本。
        """
        if not message or not message.strip():
            return self.empty_response

        message = message.strip()

        # 阶段 1: 空输入检查
        if self._stages.get("empty") and not message:
            return self.empty_response

        # 阶段 2: 安全过滤
        if self._stages.get("safety"):
            result = self._safety_check(message)
            if result:
                return result

        # 阶段 3: 专用响应器
        if self._stages.get("specialized"):
            for responder in self._specialized_responders:
                try:
                    reply = responder(message)
                    if reply:
                        return reply
                except Exception:
                    continue

        # 阶段 4: 精确记忆匹配
        if self._stages.get("memory"):
            reply = self._memory_match(message)
            if reply:
                return reply

        # 阶段 5: 规则匹配（置信度竞争）
        if self._stages.get("rules"):
            best = self._competitive_match(message)
            if best:
                return best.reply

        # 阶段 6: 兜底回复
        if self._stages.get("fallback"):
            return self._get_fallback(message)

        return self.fallback_response

    # ============================================================
    # 学习 & 记忆
    # ============================================================

    def learn(self, question: str, answer: str) -> bool:
        """教对话引擎一个新的问答对。

        Args:
            question: 问题文本。
            answer: 对应的答案。

        Returns:
            True 表示学到了新内容。
        """
        question = question.strip()
        if not question:
            return False

        if question not in self._memory:
            self._memory[question] = []

        if answer not in self._memory[question]:
            self._memory[question].append(answer)
            return True
        return False

    def forget(self, question: str) -> bool:
        """忘记某个问题和它的所有答案。

        Args:
            question: 要忘记的问题。

        Returns:
            True 表示成功忘记。
        """
        if question in self._memory:
            del self._memory[question]
            return True
        return False

    def clear_memory(self) -> None:
        """清空所有记忆。"""
        self._memory.clear()

    def search_memory(self, keyword: str) -> List[str]:
        """按关键词搜索记忆中的问题。

        Args:
            keyword: 搜索关键词。

        Returns:
            匹配的问题列表。
        """
        return [q for q in self._memory if keyword in q]

    # ============================================================
    # 规则管理
    # ============================================================

    def add_rule(
        self,
        pattern: str,
        responses: List[str],
        confidence: float = 0.5,
    ) -> None:
        """动态添加一条匹配规则。

        Args:
            pattern: 正则表达式模式。
            responses: 匹配成功时的回复候选列表。
            confidence: 置信度（0-1）。
        """
        self._rules.append({
            "pattern": pattern,
            "responses": responses,
            "confidence": confidence,
        })

    def remove_rule(self, pattern: str) -> bool:
        """删除匹配规则。

        Args:
            pattern: 要删除的规则的正则表达式。

        Returns:
            True 表示成功删除。
        """
        for i, rule in enumerate(self._rules):
            if rule.get("pattern") == pattern:
                self._rules.pop(i)
                return True
        return False

    def load_rules(self, filepath: str) -> None:
        """从 JSON 文件加载规则。

        文件格式：
        {
            "rules": [
                {"pattern": "正则", "responses": ["回复1", "回复2"], "confidence": 0.8},
                ...
            ]
        }
        """
        path = Path(filepath)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        loaded = data.get("rules", data if isinstance(data, list) else [])
        self._rules = loaded
        if not self._rules:
            self._rules = _DEFAULT_RULES.copy()

    def export_rules(self, filepath: str) -> None:
        """导出当前规则到 JSON 文件。"""
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(
                {"rules": self._rules, "version": self.VERSION},
                f,
                ensure_ascii=False,
                indent=2,
            )

    # ============================================================
    # 管道控制
    # ============================================================

    def enable_stage(self, name: str) -> None:
        """启用管道阶段。

        Args:
            name: 阶段名称。
        """
        if name in self._stages:
            self._stages[name] = True

    def disable_stage(self, name: str) -> None:
        """禁用管道阶段。

        Args:
            name: 阶段名称。
        """
        if name in self._stages:
            self._stages[name] = False

    # ============================================================
    # 匹配器扩展
    # ============================================================

    def add_specialized_responder(self, responder: Callable[[str], Optional[str]]) -> None:
        """添加专用响应器。在规则匹配之前执行。

        Args:
            responder: 接收消息文本，返回回复或 None。
        """
        self._specialized_responders.append(responder)

    def add_matcher(self, matcher: Callable[[str], Optional[MatchResult]]) -> None:
        """添加自定义匹配器。参与置信度竞争。

        Args:
            matcher: 接收消息文本，返回 MatchResult 或 None。
        """
        self._custom_matchers.append(matcher)

    def set_safety_keywords(self, keywords: List[str]) -> None:
        """设置安全过滤关键词列表。"""
        self._safety_keywords = keywords

    # ============================================================
    # 管道阶段实现
    # ============================================================

    def _safety_check(self, text: str) -> Optional[str]:
        """安全过滤检查。"""
        if not self._safety_keywords:
            return None
        for kw in self._safety_keywords:
            if kw in text:
                return "抱歉，这个话题我不了解。"
        return None

    def _memory_match(self, text: str) -> Optional[str]:
        """精确记忆匹配。"""
        if text in self._memory and self._memory[text]:
            return random.choice(self._memory[text])
        return None

    def _competitive_match(self, text: str) -> Optional[MatchResult]:
        """置信度竞争匹配：收集所有匹配结果，选置信度最高的。"""
        all_results: List[MatchResult] = []

        # 正则规则匹配
        for rule in self._rules:
            try:
                pattern = rule.get("pattern", "")
                if re.fullmatch(pattern, text) or re.search(pattern, text):
                    responses = rule.get("responses", [])
                    if responses:
                        confidence = rule.get("confidence", 0.5)
                        all_results.append(MatchResult(
                            reply=random.choice(responses),
                            confidence=confidence,
                            source=f"regex({pattern[:20]})",
                        ))
            except re.error:
                continue

        # 模糊匹配
        fuzzy = self._fuzzy_match(text)
        if fuzzy:
            all_results.append(MatchResult(
                reply=random.choice(fuzzy),
                confidence=0.6,
                source="fuzzy",
            ))

        # 自定义匹配器
        for matcher in self._custom_matchers:
            try:
                result = matcher(text)
                if result:
                    all_results.append(result)
            except Exception:
                continue

        if not all_results:
            return None

        # 按置信度降序排列
        all_results.sort(key=lambda r: r.confidence, reverse=True)
        return all_results[0]

    def _fuzzy_match(self, text: str) -> Optional[List[str]]:
        """模糊匹配：检查 text 是否部分匹配记忆中的问题。"""
        for q in self._memory:
            # 文本包含判断
            if text in q or q in text:
                return self._memory[q]
            # 序列匹配（相似度 >= 0.6）
            if SequenceMatcher(None, text, q).ratio() >= 0.6:
                return self._memory[q]
        return None

    def _get_fallback(self, message: str) -> str:
        """获取最终兜底回复。"""
        # AI 后端可用时尝试生成
        if self.backend == "ai":
            ai_reply = self._try_ai_fallback(message)
            if ai_reply:
                return ai_reply

        # 从低置信度规则中随机选择
        low_conf_rules = [r for r in self._rules if r.get("confidence", 0) <= 0.3]
        if low_conf_rules:
            rule = random.choice(low_conf_rules)
            responses = rule.get("responses", [self.fallback_response])
            if responses:
                return random.choice(responses)

        return self.fallback_response

    def _try_ai_fallback(self, message: str) -> Optional[str]:
        """尝试使用 AI 生成回复。"""
        if self._generator is None:
            try:
                from .generator import ContentGenerator, GenerationConfig
                self._generator = ContentGenerator(
                    GenerationConfig(
                        backend="ollama",
                        model=self.model,
                        temperature=0.7,
                    )
                )
            except Exception:
                return None

        if not self._generator.is_available:
            return None

        system_prompt = (
            "你是一个文字冒险游戏中的对话助手。"
            "请用简短、自然的中文回复玩家的问题。"
            "保持友好、有帮助的语气。"
        )
        return self._generator.generate(message, system_prompt)

    # ============================================================
    # 状态持久化
    # ============================================================

    def save_memory(self, filepath: str) -> None:
        """将记忆保存到文件。"""
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(
                {"memory": self._memory, "version": self.VERSION},
                f,
                ensure_ascii=False,
                indent=2,
            )

    def load_memory(self, filepath: str) -> None:
        """从文件加载记忆。"""
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        self._memory = data.get("memory", {})

    # ============================================================
    # 信息
    # ============================================================

    @property
    def memory_count(self) -> int:
        """记忆库中的问答对数量。"""
        return len(self._memory)

    @property
    def rule_count(self) -> int:
        """规则数量。"""
        return len(self._rules)

    @property
    def stage_info(self) -> Dict[str, bool]:
        """管道阶段状态。"""
        return dict(self._stages)

    def get_info(self) -> Dict[str, Any]:
        """获取引擎完整信息。"""
        return {
            "version": self.VERSION,
            "backend": self.backend,
            "model": self.model,
            "memory_count": self.memory_count,
            "rule_count": self.rule_count,
            "stages": dict(self._stages),
            "safety_keywords": self._safety_keywords,
        }

    def __repr__(self) -> str:
        return (
            f"<DialogueEngine backend='{self.backend}' "
            f"memories={self.memory_count} "
            f"rules={self.rule_count}>"
        )
