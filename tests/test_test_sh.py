# this_file: tests/test_test_sh.py
"""Pin that ./test.sh runs Qt offscreen unless the caller chose a platform."""

import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def run_test_sh(tmp_path):
    """Run a copy of test.sh beside a fake pens checkout with a stub `uv` that echoes the Qt platform."""
    app = tmp_path / "app"
    app.mkdir()
    shutil.copy(ROOT / "test.sh", app / "test.sh")
    (tmp_path / "fontlab-python-pens").mkdir()
    (tmp_path / "fontlab-python-pens" / "pyproject.toml").write_text("")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    uv = bin_dir / "uv"
    uv.write_text('#!/bin/sh\necho "QT=${QT_QPA_PLATFORM-<unset>}"\n')
    uv.chmod(uv.stat().st_mode | stat.S_IXUSR)

    def run(platform: str | None) -> str:
        env = {k: v for k, v in os.environ.items() if k != "QT_QPA_PLATFORM"}
        env["PATH"] = f"{bin_dir}:{env['PATH']}"
        if platform is not None:
            env["QT_QPA_PLATFORM"] = platform
        done = subprocess.run(["sh", str(app / "test.sh")], env=env, capture_output=True, text=True, check=True)
        return done.stdout.strip()

    return run


def test_test_sh_when_platform_unset_then_offscreen(run_test_sh):
    assert run_test_sh(None) == "QT=offscreen"


def test_test_sh_when_caller_sets_platform_then_kept(run_test_sh):
    assert run_test_sh("cocoa") == "QT=cocoa"
    assert run_test_sh("") == "QT="
