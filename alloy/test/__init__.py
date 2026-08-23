"""
alloy.test — 测试工具子包

提供：
  - TestRunner: 测试执行引擎
  - Probe / ProbeManager: 测试探针系统
  - test_core / test_world / test_systems: 单元测试
  - run_all: 批量运行所有测试
"""

from alloy.test.runner import TestRunner, TestResult
from alloy.test.probe import Probe, ProbeManager

__all__ = ["TestRunner", "TestResult", "Probe", "ProbeManager"]
