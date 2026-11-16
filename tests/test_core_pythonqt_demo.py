# this_file: tests/test_core_pythonqt_demo.py
"""The App tour opens the real filtering lab through its lazy studio route."""
from pathlib import Path
import runpy


def test_demo_when_inspected_then_lazy_and_when_run_then_opens_filtering_lab(monkeypatch):
    from fontlabapp.studios import core_pythonqt_labs
    calls = []
    result = object()
    monkeypatch.setattr(core_pythonqt_labs, 'show', lambda lab: calls.append(lab) or result)
    path = Path(__file__).resolve().parents[1] / 'Scripts/Font Editors/Core PythonQt Labs Demo.py'
    namespace = runpy.run_path(str(path), run_name='inspection')
    assert calls == []
    assert namespace['main']() is result
    runpy.run_path(str(path), run_name='__main__')
    assert calls == ['E01', 'E01']
