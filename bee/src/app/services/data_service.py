# -*- coding: utf-8 -*-
"""Re-export shim — 真实实现已迁移至 src.sim_core.services.data_service

非破坏性迁移（M1）：原文件内容已移至 sim_core 包，此 shim 仅做再导出，
保证 src.app / 内容工具等既有导入路径保持不变。请勿手改此文件。
"""
from src.sim_core.services.data_service import *  # noqa: F401,F403
