"""Integration test: run the real game headless via subprocess.

Verifies the full program boots, renders 30 frames across all modes, and exits
cleanly (return code 0). Two scenarios are exercised:
  * ``DISABLE_AUDIO=1`` (audio explicitly disabled).
  * Audio path left enabled (headless degrades gracefully without a device).
"""
import os
import subprocess
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN_PY = os.path.join(REPO_ROOT, "main.py")


def _run_headless(frames=30, disable_audio=True, timeout=120):
    env = os.environ.copy()
    env["SDL_VIDEODRIVER"] = "dummy"
    if disable_audio:
        env["DISABLE_AUDIO"] = "1"
    else:
        env.pop("DISABLE_AUDIO", None)
    proc = subprocess.run(
        [sys.executable, MAIN_PY, "--headless", str(frames)],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return proc


class TestHeadlessRun:
    def test_headless_30_frames_with_audio_disabled(self):
        proc = _run_headless(frames=30, disable_audio=True)
        assert proc.returncode == 0, (
            f"main.py --headless 30 exited {proc.returncode}\n"
            f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )
        # The self-validation should report all four modes rendered.
        assert "modes rendered" in proc.stdout

    def test_headless_30_frames_audio_degradation_path(self):
        proc = _run_headless(frames=30, disable_audio=False)
        assert proc.returncode == 0, (
            f"main.py (audio enabled) exited {proc.returncode}\n"
            f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )
