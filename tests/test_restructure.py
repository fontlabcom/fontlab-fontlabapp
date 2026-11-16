# this_file: tests/test_restructure.py
"""The migration preserves bindings and only rewrites reviewed names."""

import importlib.util
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "restructure_tool", Path(__file__).resolve().parents[1] / "tools/restructure.py"
)
tool = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(tool)

MAPPING = {
    "fontlabapp.qtsafe": "fontlabapp.qt.safe",
    "fontlabapp.master_angles": "fontlabapp.masters.angles.model",
    "fontlabapp.masters": "fontlabapp.masters.inspect.model",
}


def test_rewrite_when_import_forms_used_then_bindings_and_exact_names_survive():
    source = """from fontlabapp import qtsafe as qs, _native
from .qtsafe import qt_list
import fontlabapp.qtsafe
x = "fontlabapp.qtsafe.qt_list"
y = "fontlabapp.qtsafe_extra.qt_list"
z = "other.fontlabapp.qtsafe"
w = "fontlabapp.masters.angles.model"
"""
    result = tool.rewrite(source, "fontlabapp", MAPPING)
    assert "from fontlabapp.qt import safe as qs" in result
    assert "from fontlabapp import _native" in result
    assert "from fontlabapp.qt.safe import qt_list" in result
    assert "import fontlabapp.qt.safe" in result
    assert '"fontlabapp.qt.safe.qt_list"' in result
    assert '"fontlabapp.qtsafe_extra.qt_list"' in result
    assert '"other.fontlabapp.qtsafe"' in result
    assert '"fontlabapp.masters.angles.model"' in result
    assert tool.rewrite(result, "fontlabapp", MAPPING) == result


def test_rewrite_when_unicode_and_nested_relative_import_then_bytes_are_preserved():
    source = 'def f():\n    "ą"; from ..qtsafe import qt_list  # preserve\n'
    result = tool.rewrite(source, "fontlabapp.old", MAPPING)
    assert (
        result
        == 'def f():\n    "ą"\n    from fontlabapp.qt.safe import qt_list  # preserve\n'
    )


def test_rewrite_when_names_share_destination_then_merges_without_semicolons():
    result = tool.rewrite(
        "from fontlabapp.qtsafe import qt_list as values, main_window\n",
        "fontlabapp",
        MAPPING,
    )
    assert result == "from fontlabapp.qt.safe import qt_list as values, main_window\n"


def test_rewrite_when_comments_and_nested_scope_exist_then_keeps_them_with_the_import():
    source = """def lazy():
    from fontlabapp.qtsafe import (
        qt_list as values,  # owned values
        main_window,  # caller's existing window
    )  # noqa: F401
"""
    result = tool.rewrite(source, "fontlabapp", MAPPING)
    assert result == source.replace("fontlabapp.qtsafe", "fontlabapp.qt.safe")
    assert tool.rewrite(result, "fontlabapp", MAPPING) == result


def test_batch_assignment_when_reviewed_mapping_read_then_counts_match_rationale():
    import json
    from collections import Counter

    mapping = json.loads((tool.ROOT / "tools/fontlabapp-mapping.json").read_text())
    assert len(mapping) == len(set(mapping.values())) == 382
    assert Counter(tool.batch_of(v) for v in mapping.values()) == dict(
        enumerate((28, 60, 48, 37, 34, 40, 45, 21, 34, 35), 1)
    )


def test_manifest_when_destinations_move_then_historical_hashes_and_reruns_stay_stable(
    tmp_path, monkeypatch
):
    import json

    monkeypatch.setattr(tool, "ROOT", tmp_path)
    rows = [
        {
            "source": "original/__init__.py",
            "destination": "src/fontlabapp/__init__.py",
            "sha256": "original-root",
            "destination_sha256": "historical-root",
        },
        {
            "source": "original/utils/__init__.py",
            "destination": "src/fontlabapp/utils/__init__.py",
            "sha256": "original-utils",
            "destination_sha256": "historical-utils",
        },
    ]
    path = tmp_path / "MIGRATION.json"
    path.write_text(json.dumps({"files": rows, "source_revision": "unchanged"}))
    tool.update_manifest({"fontlabapp.utils": "fontlabapp.core.utils"})
    result = json.loads(path.read_text())
    assert result["source_revision"] == "unchanged"
    for before, after in zip(rows, result["files"]):
        assert after["source"] == before["source"]
        assert after["sha256"] == before["sha256"]
        assert after["destination_sha256"] == before["destination_sha256"]
        assert after["issue_205_move"]["previous_destination"] == before["destination"]
    assert result["files"][1]["destination"] == "src/fontlabapp/core/utils/__init__.py"
    snapshot = path.read_bytes()
    tool.update_manifest({"fontlabapp.utils": "fontlabapp.core.utils"})
    assert path.read_bytes() == snapshot
