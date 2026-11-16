# this_file: tests/test_install_copies.py
"""tools/check_install_copies.py compares workspace install.vfpy copies."""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_check_install_copies_when_copy_differs_then_exit_1_and_excluded_never_touched(tmp_path, capsys, monkeypatch):
    import importlib.util

    spec = importlib.util.spec_from_file_location("cic", ROOT / "tools" / "check_install_copies.py")
    cic = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cic)
    for name, body in (("a", (ROOT / "install.vfpy").read_bytes()), ("b", b"other"), ("FontRig", b"x"), ("TypeRig-Icons", b"y")):
        (tmp_path / name).mkdir()
        (tmp_path / name / "install.vfpy").write_bytes(body)
    touched = []
    real = {n: getattr(os, n) for n in ("stat", "lstat", "scandir", "listdir")}

    def guard(name):
        def wrapper(path, *a, **k):
            if any(x in str(path) for x in ("FontRig", "TypeRig-Icons")):
                touched.append((name, str(path)))
            return real[name](path, *a, **k)
        return wrapper

    for n in real:
        monkeypatch.setattr(os, n, guard(n))
    assert cic.main([str(tmp_path)]) == 1
    out = capsys.readouterr().out
    assert "same" in out and "DIFF" in out and "FontRig" not in out and "TypeRig-Icons" not in out
    assert touched == [], touched
    (tmp_path / "b" / "install.vfpy").write_bytes((ROOT / "install.vfpy").read_bytes())
    assert cic.main([str(tmp_path)]) == 0
