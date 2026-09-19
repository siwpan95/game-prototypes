"""
AI 内容生成器：Ollama/DeepSeek 双后端 + 内置中文模板降级。

提供统一的文本生成接口，AI 不可用时自动回退到预设中文模板。
支持通用生成、房间描述、怪物描述、物品描述、对话生成等快捷方法。

用法：
    from ai.generator import ContentGenerator, GenerationConfig

    config = GenerationConfig(backend="deepseek", model="deepseek-v4-pro")
    gen = ContentGenerator(config)

    if gen.is_available:
        desc = gen.generate_room_desc("黑暗森林", "废弃神殿")
    else:
        desc = gen.generate_room_desc("黑暗森林", "废弃神殿")  # 自动使用模板
"""

import json
import os
import random
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

# ollama 为可选依赖，使用时惰性导入
_ollama = None


def _get_ollama():
    """惰性导入 ollama 库。"""
    global _ollama
    if _ollama is None:
        try:
            import ollama as _o
            _ollama = _o
        except ImportError:
            _ollama = None
    return _ollama


# requests 为可选依赖
_requests = None


def _get_requests():
    """惰性导入 requests 库。"""
    global _requests
    if _requests is None:
        try:
            import requests as _r
            _requests = _r
        except ImportError:
            _requests = None
    return _requests


# ============================================================
# 配置
# ============================================================

@dataclass
class GenerationConfig:
    """AI 生成配置。

    Attributes:
        model: 模型名。ollama 可用 "qwen2.5"、"llama3.2"；deepseek 可用 "deepseek-v4-pro"。
        backend: 后端选择。"ollama"（本地）或 "deepseek"（云端）。
        temperature: 创造性参数，0.0-2.0。
        max_tokens: 最大生成 token 数。
        timeout: 请求超时秒数。
        host: Ollama 服务地址，留空使用默认值。
        api_key: DeepSeek API key。
        deepseek_base_url: DeepSeek API 基础地址。
        fallback_model: AI 不可用时的降级模型。
    """
    model: str = "qwen2.5"
    backend: str = "ollama"
    temperature: float = 0.8
    max_tokens: int = 200
    timeout: int = 30
    host: str = ""
    api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    fallback_model: str = "llama3.2"

    def __post_init__(self) -> None:
        if self.backend == "deepseek" and not self.api_key:
            self.api_key = _load_deepseek_api_key()


def _load_deepseek_api_key() -> str:
    """加载 DeepSeek API key：环境变量 > 本地配置文件。"""
    key = os.environ.get("DEEPSEEK_API_KEY", "")
    if key:
        return key

    config_paths = [
        "deepseek_config.json",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "deepseek_config.json"),
    ]
    for path in config_paths:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if data.get("api_key"):
                    return data["api_key"]
        except (FileNotFoundError, json.JSONDecodeError):
            continue

    return ""


# ============================================================
# 内置中文模板（AI 不可用时的兜底方案）
# ============================================================

_ROOM_TEMPLATES: List[str] = [
    "幽暗的{theme}中，烛火摇曳。墙壁上爬满了不知名的藤蔓，空气中弥漫着潮湿和腐朽的气息。",
    "你进入了一间{theme}风格的大厅。破碎的雕像散落四处，地上有奇怪的符文在微微发光。",
    "这个{theme}空间充满了神秘感。角落里堆放着古老的遗物，似乎在诉说着过去的秘密。",
    "眼前是一片{theme}景象，光线从破损的天花板缝隙中洒落，照在布满灰尘的地面上。"
]

_MONSTER_TEMPLATES: List[str] = [
    "一只{monster}从阴影中现身，挡住了你的去路！它的眼中闪烁着危险的光芒。",
    "{monster}发出低沉的咆哮，锋利的爪子在石地上刮出刺耳的声音。",
    "在{theme}的深处，你发现了{monster}。它似乎早已察觉你的到来。",
    "一阵令人毛骨悚然的声响后，{monster}从黑暗中缓缓走出，空气中弥漫着杀意。"
]

_ITEM_TEMPLATES: List[str] = [
    "一把{item}静静地躺在那里，表面有着复杂的花纹，似乎蕴含着某种力量。",
    "你发现了一件{item}，它在微光中泛着淡淡的{quality}光泽。",
    "这件{item}看起来很普通，但直觉告诉你它绝不简单。上面的铭文已经模糊不清。",
    "角落里闪烁的{item}吸引了你的注意，这是一件{quality}的遗物。"
]

_DIALOGUE_TEMPLATES: List[str] = [
    "\"{text}\" — {speaker}用低沉的嗓音说道。",
    "\"{text}\"，{speaker}微微一笑。",
    "{speaker}突然开口：「{text}」",
    "「{text}」{speaker}的语调带着一丝{emotion}。"
]


# ============================================================
# 系统提示词
# ============================================================

_SYSTEM_PROMPTS: Dict[str, str] = {
    "room": (
        "你是一个地下城冒险游戏的叙事者。"
        "擅长用生动的语言描述场景，包含视觉、听觉、嗅觉等感官细节。"
        "保持紧张刺激的氛围，使用第二人称视角。"
        "请只输出场景描述，不要添加其他内容。"
    ),
    "monster": (
        "你是一个地下城冒险游戏的叙事者。"
        "擅长描述怪物遭遇，创造紧张刺激的战斗氛围。"
        "用生动的语言描绘怪物的外观和行为。"
        "请只输出怪物描述，不要添加其他内容。"
    ),
    "item": (
        "你是一个奇幻游戏的物品描述师。"
        "擅长为道具和装备编写富有想象力的描述。"
        "包含视觉细节和可能蕴含的神秘力量。"
        "请只输出物品描述，不要添加其他内容。"
    ),
    "dialogue": (
        "你是一个奇幻游戏的对白写手。"
        "擅长为NPC编写自然的对话文本。"
        "根据角色性格生成合适语气的台词。"
        "请只输出对话文本，不要添加额外内容。"
    ),
    "general": (
        "你是一个文字冒险游戏的内容生成器。"
        "擅长生成富有沉浸感的中文游戏文本。"
        "内容应生动、具体、富有画面感。"
    ),
}


# ============================================================
# 核心生成器
# ============================================================

class ContentGenerator:
    """通用 AI 内容生成器。

    支持 Ollama 本地模型和 DeepSeek 云端 API 两种后端，
    AI 不可用时自动使用内置中文模板降级。

    用法：
        gen = ContentGenerator(GenerationConfig(backend="ollama", model="qwen2.5"))
        desc = gen.generate_room_desc("黑暗森林", "废弃神殿")
    """

    def __init__(self, config: Optional[GenerationConfig] = None):
        """初始化生成器。

        Args:
            config: 生成配置。为 None 时使用默认配置。
        """
        self.config = config or GenerationConfig()
        self._available: Optional[bool] = None

    # ============================================================
    # 可用性检查
    # ============================================================

    @property
    def is_available(self) -> bool:
        """检查 AI 服务是否可用（结果会被缓存）。

        Returns:
            True 表示 AI 后端可连接。
        """
        if self._available is not None:
            return self._available

        if self.config.backend == "deepseek":
            self._available = bool(self.config.api_key)
        else:
            try:
                ollama = _get_ollama()
                if ollama is None:
                    self._available = False
                else:
                    ollama.list()
                    self._available = True
            except Exception:
                self._available = False
        return self._available

    def refresh_availability(self) -> bool:
        """强制刷新可用性状态。"""
        self._available = None
        return self.is_available

    # ============================================================
    # 底层 API 调用
    # ============================================================

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> str:
        """生成文本（底层通用方法）。

        Args:
            prompt: 用户提示词。
            system_prompt: 系统提示词。
            model: 覆盖默认模型。
            temperature: 覆盖默认温度。

        Returns:
            生成的文本，失败时返回空字符串。
        """
        messages: List[Dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        return self.chat(messages, model=model, temperature=temperature)

    def chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> str:
        """多轮对话生成。

        Args:
            messages: 消息列表，每项含 role("system"/"user"/"assistant") 和 content。
            model: 覆盖默认模型。
            temperature: 覆盖默认温度。

        Returns:
            生成的回复文本，失败返回空字符串。
        """
        use_backend = self.config.backend
        use_model = model or self.config.model

        if use_backend == "deepseek":
            result = self._call_deepseek(messages, use_model, temperature)
            if result:
                return result
            # 降级到 Ollama
            use_backend = "ollama"
            use_model = self.config.fallback_model
            self._available = None

        return self._call_ollama(messages, use_model, temperature) or ""

    def _call_ollama(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: Optional[float] = None,
    ) -> Optional[str]:
        """调用 Ollama 本地模型。"""
        ollama = _get_ollama()
        if ollama is None:
            return None

        try:
            kwargs: Dict[str, Any] = {
                "model": model,
                "messages": messages,
                "options": {
                    "temperature": temperature or self.config.temperature,
                    "num_predict": self.config.max_tokens,
                },
            }
            if self.config.host:
                kwargs["host"] = self.config.host
            response = ollama.chat(**kwargs)
            content = response.get("message", {}).get("content", "")
            return content.strip() if content else None
        except Exception:
            return None

    def _call_deepseek(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: Optional[float] = None,
    ) -> Optional[str]:
        """调用 DeepSeek API。"""
        if not self.config.api_key:
            return None

        requests = _get_requests()
        if requests is None:
            return None

        try:
            url = f"{self.config.deepseek_base_url}/chat/completions"
            headers = {
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": model,
                "messages": messages,
                "temperature": temperature or self.config.temperature,
                "max_tokens": self.config.max_tokens,
            }
            response = requests.post(
                url, headers=headers, json=payload, timeout=self.config.timeout
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            return content.strip() if content else None
        except Exception:
            return None

    # ============================================================
    # 快捷生成方法
    # ============================================================

    def generate_room_desc(self, theme: str, room_type: str = "房间") -> str:
        """生成房间/场景描述。

        Args:
            theme: 主题（如"黑暗森林"、"废弃神殿"）。
            room_type: 房间类型。

        Returns:
            场景描述文本。
        """
        prompt = (
            f"为地下城游戏生成一个{theme}主题的{room_type}的生动描述。\n\n"
            "要求：\n"
            "- 长度适中（50-100字）\n"
            "- 包含视觉、听觉、嗅觉等感官细节\n"
            "- 氛围紧张刺激\n"
            '- 使用第二人称"你"\n\n'
            "直接输出描述，不要其他内容。"
        )
        result = self.generate(prompt, _SYSTEM_PROMPTS["room"])
        return result if result else self._template_room(theme)

    def generate_monster(self, monster_name: str, theme: str, context: str = "") -> str:
        """生成怪物遭遇描述。

        Args:
            monster_name: 怪物名称。
            theme: 场景主题。
            context: 额外上下文信息。

        Returns:
            怪物描述文本。
        """
        extra = f"\n{context}\n" if context else ""
        prompt = (
            f"在{theme}主题的地下城中，你遇到了{monster_name}。{extra}\n"
            "生成一段紧张刺激的怪物遭遇描述，包含：\n"
            "- 怪物的外观细节\n"
            "- 你的反应和感受\n"
            "- 战斗即将开始的氛围\n"
            "长度50-80字，第二人称。"
        )
        result = self.generate(prompt, _SYSTEM_PROMPTS["monster"])
        return result if result else self._template_monster(monster_name, theme)

    def generate_item(self, item_name: str, quality: str = "普通") -> str:
        """生成物品描述。

        Args:
            item_name: 物品名称。
            quality: 品质（普通/稀有/史诗/传说）。

        Returns:
            物品描述文本。
        """
        prompt = (
            f"为一款奇幻游戏中的{item_name}编写一段道具描述。\n"
            f"品质等级：{quality}\n"
            "要求：\n"
            "- 富有想象力的外观描述\n"
            "- 暗示可能蕴含的力量或特性\n"
            "- 40-60字\n"
            "直接输出描述，不要其他内容。"
        )
        result = self.generate(prompt, _SYSTEM_PROMPTS["item"])
        return result if result else self._template_item(item_name, quality)

    def generate_dialogue(
        self,
        speaker: str,
        context: str = "",
        emotion: str = "平静",
        theme: str = "",
    ) -> str:
        """生成 NPC 对话。

        Args:
            speaker: 说话者名称。
            context: 对话上下文/话题。
            emotion: 情绪（愤怒/悲伤/喜悦/平静/恐惧）。
            theme: 场景主题。

        Returns:
            对话文本。
        """
        prompt = (
            f"{speaker}在{theme or '冒险场景'}中说话。\n"
            f"情绪：{emotion}\n"
            f"话题：{context or '随意交谈'}\n"
            "生成一句角色对话：\n"
            "- 符合角色情绪和场景氛围\n"
            "- 30-60字\n"
            "只输出对话内容，不要加引号。"
        )
        result = self.generate(prompt, _SYSTEM_PROMPTS["dialogue"])
        return result if result else self._template_dialogue(speaker, context, emotion)

    def generate_general(self, prompt: str, context: str = "") -> str:
        """通用内容生成。

        Args:
            prompt: 生成指令。
            context: 额外的上下文。

        Returns:
            生成的内容。
        """
        full_prompt = f"{context}\n\n{prompt}" if context else prompt
        result = self.generate(full_prompt, _SYSTEM_PROMPTS["general"])
        return result if result else f"[生成失败] {prompt[:30]}..."

    # ============================================================
    # 内置模板降级
    # ============================================================

    @staticmethod
    def _template_room(theme: str) -> str:
        """房间描述模板。"""
        return random.choice(_ROOM_TEMPLATES).format(theme=theme)

    @staticmethod
    def _template_monster(monster: str, theme: str) -> str:
        """怪物描述模板。"""
        return random.choice(_MONSTER_TEMPLATES).format(monster=monster, theme=theme)

    @staticmethod
    def _template_item(item: str, quality: str) -> str:
        """物品描述模板。"""
        return random.choice(_ITEM_TEMPLATES).format(item=item, quality=quality)

    @staticmethod
    def _template_dialogue(speaker: str, context: str, emotion: str) -> str:
        """对话模板。"""
        short_text = context[:50] if context else "..."
        return random.choice(_DIALOGUE_TEMPLATES).format(
            speaker=speaker, text=short_text, emotion=emotion
        )

    # ============================================================
    # 信息
    # ============================================================

    def __repr__(self) -> str:
        status = "available" if self.is_available else "unavailable"
        return (
            f"<ContentGenerator backend='{self.config.backend}' "
            f"model='{self.config.model}' {status}>"
        )


# ============================================================
# 全局单例
# ============================================================

_generator: Optional[ContentGenerator] = None


def get_generator(config: Optional[GenerationConfig] = None) -> ContentGenerator:
    """获取全局生成器单例。

    Args:
        config: 首次调用时的配置，后续调用忽略。

    Returns:
        全局 ContentGenerator 实例。
    """
    global _generator
    if _generator is None:
        _generator = ContentGenerator(config)
    return _generator


def reset_generator() -> None:
    """重置全局生成器单例。"""
    global _generator
    _generator = None
