"""Pytest configuration: make the project root importable.

When pytest collects ``tests/test_*.py`` it loads this file first. We inject the
project root (the parent of ``tests/``) into ``sys.path`` so every test module can
do ``from models.xxx import ...`` / ``from core.xxx import ...`` without the package
being pip-installed.

The same bootstrap is also inlined at the top of each test module and in
``tests/run_manual.py`` so the tests run on a machine that has **no pytest**
installed (e.g. ``python tests/run_manual.py``).
"""
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
