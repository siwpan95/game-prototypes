"""
preset 组合档案（profile）与装配报告
====================================

对应 Cordis 的 bundle/profile 概念：一个 profile 是"有序预设清单"，
一层层装配到同一个 Context 上；config 是声明式覆盖（当前接入点：
audio.backend，其余键被记录进报告供项目侧读取/未来接入）。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from allin_engine.core.context import Context
from allin_engine.core.plugins import (
    preset_core, preset_world, preset_systems,
    preset_combat, preset_audio, preset_ai_brain,
)

__all__ = ["PROFILES", "PRESET_FUNCS", "assemble_profile", "build_report"]


#: 预定义档案（对应 harness 的 profile 模板）
PROFILES: Dict[str, List[str]] = {
    "base": ["core", "world"],
    "headless": ["core", "world"],
    "rogue-lite": ["core", "world", "systems", "combat", "ai_brain"],
    "full": ["core", "world", "systems", "combat", "audio", "ai_brain"],
}

PRESET_FUNCS = {
    "core": preset_core,
    "world": preset_world,
    "systems": preset_systems,
    "combat": preset_combat,
    "audio": preset_audio,
    "ai_brain": preset_ai_brain,
}


def assemble_profile(ctx: Context, plugins: List[str], config: Optional[dict] = None) -> None:
    """按清单顺序装配预设到 ctx。config 目前接入 audio.backend。"""
    config = config or {}
    for name in plugins:
        if name not in PRESET_FUNCS:
            raise ValueError(f"未知预设: '{name}'（可用: {sorted(PRESET_FUNCS)}）")
        if name == "audio":
            PRESET_FUNCS[name](ctx, backend=str(config.get("audio", {}).get("backend", "pygame")))
        elif name == "core":
            PRESET_FUNCS[name](ctx)  # update_cb=None：仅装配，不驱动
        else:
            PRESET_FUNCS[name](ctx)


def build_report(ctx: Context, profile: str, plugins: List[str], config: Optional[dict]) -> Dict[str, Any]:
    """生成装配报告：档案、插件、已注册服务、配置覆盖、可选依赖能力。"""
    from allin_engine.core.deps import feature_flags

    services: Dict[str, str] = {}
    for key in sorted(ctx.keys()):
        value = ctx.get(key)
        services[key] = type(value).__name__
    return {
        "profile": profile,
        "plugins": list(plugins),
        "services": services,
        "config": dict(config or {}),
        "optional_deps": feature_flags(),
    }
