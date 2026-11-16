# this_file: tests/test_feature_blocks.py
"""Exercise the App feature-block I/O with owned host doubles."""

import importlib
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

app_scripting = importlib.import_module("fontlabapp.core.scripting")
scripting = importlib.import_module("fontlabapp.fontui.feature_blocks")


@pytest.fixture(
    autouse=True,
    params=[
        "fontlabapp.fontui.feature_blocks",
        "fontlabapp.core.scripting",
        "fontlab_fontport.feature_blocks",
    ],
)
def feature_entry(request, monkeypatch):
    """All shipped entry points preserve the same feature I/O contract."""
    monkeypatch.setattr(
        sys.modules[__name__], "scripting", importlib.import_module(request.param)
    )


@pytest.fixture
def owned(monkeypatch):
    entries = [
        {"feature": "languagesystem DFLT dflt;\n"},
        {"name": "liga", "feature": "feature liga {\n sub f i by f_i;\n} liga;\n"},
    ]
    events = []
    package = NS(id=7, fgId=103, isNull=False, master="Bold")
    native_features = NS(
        clear=lambda: events.append("clear"),
        set_prefix=lambda value: events.append(("prefix", value)),
        set_feature=lambda tag, value: events.append((tag, value)),
    )
    package.fgPackage = NS(features=native_features)
    package.featuresContainer = lambda: "features-container"
    package.checkInitHistoryState = lambda index: events.append(("init", index))
    package.setMaster = lambda name: setattr(package, "master", name)
    native = NS(
        flWorkspace=NS(
            instance=lambda: NS(
                findPackageId=lambda font_id: package if font_id == 103 else None
            )
        ),
        CurrentFont=lambda: NS(glyphs=[NS(name="a"), NS(name="a.sc")]),
        flItems=NS(
            notifyChangesApplied=lambda title, items: events.append(
                ("history", title, items)
            ),
            notifyFeaturesChanged=lambda font_id, flag: events.append(
                ("features", font_id, flag)
            ),
        ),
    )
    monkeypatch.setitem(sys.modules, "fontlab", native)
    monkeypatch.setitem(
        sys.modules,
        "fontpr",
        NS(
            available=lambda: True,
            get_font_info=lambda font_id: {"openTypeFeatures": entries},
        ),
    )
    monkeypatch.setattr(
        app_scripting,
        "current_package",
        lambda expected_id=None: package if expected_id in (None, 7) else None,
    )
    return package, entries, events


def _with_smcp(expected):
    return {
        "prefix": expected["prefix"],
        "features": expected["features"]
        + [("smcp", "feature smcp {\n sub a by a.sc;\n} smcp;\n")],
    }


def test_actual_writer_notifies_only_package_features_and_preserves_master(owned):
    package, _, events = owned
    expected = scripting.read_feature_blocks(package)
    updated = _with_smcp(expected)
    assert scripting.write_feature_blocks(
        package, expected, updated, references=["a", "a.sc"], undo_name="Owned suffix"
    ) == {"changed": 1}
    assert events[0] == ("init", 0)
    history = [
        event for event in events if isinstance(event, tuple) and event[0] == "history"
    ]
    assert history == [("history", "Owned suffix", [package, "features-container"])] * 2
    assert events.count("clear") == 1
    assert ("prefix", expected["prefix"]) in events
    assert ("features", 103, False) in events
    assert package.master == "Bold"


@pytest.mark.parametrize("condition", ["no-fontpr", "empty-slot", "synthesis", "split"])
def test_actual_fontport_safety_refusals_do_not_mutate(owned, monkeypatch, condition):
    package, entries, events = owned
    expected = scripting.read_feature_blocks(package)
    updated = _with_smcp(expected)
    if condition == "no-fontpr":
        monkeypatch.setattr(sys.modules["fontpr"], "available", lambda: False)
    elif condition == "empty-slot":
        entries.append({"name": "salt"})
    elif condition == "synthesis":
        entries[0]["feature"] = "# prefix\n"
        expected = scripting.read_feature_blocks(package)
        updated["prefix"] = expected["prefix"]
    else:
        updated["features"][1] = ("smcp", "# missing feature boundaries\n")
    with pytest.raises((RuntimeError, ValueError)):
        scripting.write_feature_blocks(
            package, expected, updated, references=["a"], undo_name="Owned suffix"
        )
    assert not events, (
        "Fontport must reject unsafe history/source before native allocation or notification"
    )


def test_true_noop_skips_native_history_even_with_empty_slot(owned):
    package, entries, events = owned
    entries.append({"name": "salt"})
    expected = scripting.read_feature_blocks(package)
    assert scripting.write_feature_blocks(
        package, expected, expected, references=[], undo_name="Owned suffix"
    ) == {"changed": 0}
    assert not events


def test_write_when_fontlab_missing_then_backend_import_fails_first(owned, monkeypatch):
    """Fontport's backend constructor imports fontlab before the App's deferred import runs.

    The App-side ``import_module("fontlab")`` in ``write_feature_blocks`` is
    therefore unreachable without the backend failing first; the failure is a
    plain ModuleNotFoundError and nothing is written.
    """
    package, _, events = owned
    expected = scripting.read_feature_blocks(package)
    monkeypatch.setitem(sys.modules, "fontlab", None)
    with pytest.raises(ModuleNotFoundError, match="fontlab") as err:
        scripting.write_feature_blocks(
            package, expected, _with_smcp(expected), references=[], undo_name="x"
        )
    raised_in = err.traceback[-1]
    assert (Path(str(raised_in.path)).name, raised_in.name) != ("feature_blocks.py", "write_feature_blocks"), (
        "the App's own deferred import raised: the backend did not fail first"
    )
    assert any(Path(str(f.path)).name == "host.py" and f.name == "_package" for f in err.traceback), (
        "the failure must originate in Fontport's NativeFontBackend._package"
    )
    assert not events


def test_inactive_font_refuses_read_and_write(owned, monkeypatch):
    package, _, events = owned
    expected = scripting.read_feature_blocks(package)
    monkeypatch.setattr(app_scripting, "current_package", lambda expected_id=None: None)
    with pytest.raises(ValueError, match="Activate the original font before reading"):
        scripting.read_feature_blocks(package)
    with pytest.raises(ValueError, match="Activate the original font before applying"):
        scripting.write_feature_blocks(
            package, expected, expected, references=[], undo_name="x"
        )
    assert not events


def test_changed_source_and_glyphs_refuse_with_exact_messages(owned):
    package, entries, events = owned
    expected = scripting.read_feature_blocks(package)
    with pytest.raises(ValueError, match="Referenced glyphs changed; reopen this tool"):
        scripting.write_feature_blocks(
            package, expected, expected, references=["missing"], undo_name="x"
        )
    entries[0]["feature"] = "languagesystem latn dflt;\n"
    with pytest.raises(ValueError, match="Feature source changed; refresh the preview"):
        scripting.write_feature_blocks(
            package, expected, expected, references=[], undo_name="x"
        )
    assert not events


def test_native_error_is_wrapped_and_master_restored(owned, monkeypatch):
    package, _, _ = owned
    expected = scripting.read_feature_blocks(package)
    updated = _with_smcp(expected)

    def fail(self, blocks, *, undo_name):
        package.master = "Light"
        raise OSError("boom")

    monkeypatch.setattr(
        "fontlab_fontport.host.NativeFontBackend.set_feature_blocks", fail
    )
    with pytest.raises(RuntimeError, match="changes may be partial: boom"):
        scripting.write_feature_blocks(
            package, expected, updated, references=[], undo_name="x"
        )
    assert package.master == "Bold"


def test_module_imports_without_host_or_pythonqt():
    code = (
        "import sys, fontlabapp.fontui.feature_blocks;"
        "bad = [m for m in ('fontlab', 'fontpr', 'PythonQt',"
        " 'fontlab_fontport.host') if m in sys.modules];"
        "sys.exit(1 if bad else 0)"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_scripting_when_imported_then_other_helpers_remain():
    for name in (
        "current_package",
        "select_glyphs",
        "write_font_info",
        "features_dialog_type",
    ):
        assert callable(getattr(app_scripting, name)), name


def test_write_when_new_feature_code_lacks_final_newline_then_it_is_terminated(owned):
    """feature_text() output has no trailing newline; Fontport returns code + newline."""
    package, _, events = owned
    expected = scripting.read_feature_blocks(package)
    code = "feature ss01 {\n sub a by a.sc;\n} ss01;"
    updated = {
        "prefix": expected["prefix"],
        "features": expected["features"] + [("ss01", code)],
    }
    assert scripting.write_feature_blocks(
        package, expected, updated, references=["a", "a.sc"], undo_name="Owned suffix"
    ) == {"changed": 1}
    assert ("ss01", code + "\n") in events


def test_write_when_feature_code_already_terminated_then_no_extra_newline(owned):
    package, _, events = owned
    expected = scripting.read_feature_blocks(package)
    updated = _with_smcp(expected)
    scripting.write_feature_blocks(
        package, expected, updated, references=["a"], undo_name="Owned suffix"
    )
    assert ("smcp", "feature smcp {\n sub a by a.sc;\n} smcp;\n") in events


def test_write_when_feature_code_is_empty_then_it_is_not_given_a_newline(owned):
    from fontlabapp.fontui.feature_blocks import _terminated

    assert _terminated({"prefix": "", "features": [("a", ""), ("b", "x"), ("c", "y\n")]}) == {
        "prefix": "",
        "features": [("a", ""), ("b", "x\n"), ("c", "y\n")],
    }


def test_write_when_unterminated_block_equals_expected_then_it_is_a_noop(owned):
    package, _, events = owned
    expected = scripting.read_feature_blocks(package)
    stripped = {
        "prefix": expected["prefix"],
        "features": [(t, c.rstrip("\n")) for t, c in expected["features"]],
    }
    assert scripting.write_feature_blocks(
        package, expected, stripped, references=[], undo_name="x"
    ) == {"changed": 0}
    assert not events


_SS01 = "feature ss01 {\n sub a by a.sc;\n} ss01;"


@pytest.mark.parametrize(
    ("tail", "stored"),
    [
        ("", "\n"),
        (" ", "\n"),
        ("\t", "\n"),
        ("\n  ", "\n"),
        ("\n\t", "\n"),
        ("\n \t ", "\n"),
        ("\r", "\r\n"),
        ("\f", "\f\n"),
        ("\n", "\n"),
        ("\n\n", "\n\n"),
        ("  \n", "  \n"),
        ("\n \n", "\n \n"),
    ],
)
def test_write_when_block_ends_in_blank_or_spaces_then_fontport_stages_it(owned, tail, stored):
    """Fontport's history split-back keeps a block only if its last line ends in a newline.

    Probed against the real stage_blocks: tails '', ' ', '\\n  ', '\\n\\t' are refused with
    "history code differs"; the normaliser strips trailing spaces/tabs and adds one newline,
    and leaves already-terminated tails (including '\\n\\n' and '  \\n') untouched.
    """
    package, _, events = owned
    expected = scripting.read_feature_blocks(package)
    updated = {
        "prefix": expected["prefix"],
        "features": expected["features"] + [("ss01", _SS01 + tail)],
    }
    assert scripting.write_feature_blocks(
        package, expected, updated, references=["a", "a.sc"], undo_name="Owned suffix"
    ) == {"changed": 1}
    assert ("ss01", _SS01 + stored) in events


def test_fontport_still_refuses_unnormalised_trailing_spaces(owned):
    """The Fontport check is not weakened: the raw tail is refused, only the App normalises."""
    from fontlab_fontport.native_features import stage_blocks

    package, _, _ = owned
    expected = scripting.read_feature_blocks(package)
    raw = {
        "prefix": expected["prefix"],
        "features": [("ss01", _SS01 + "\n  "), ("kern", "feature kern {\n pos a b 1;\n} kern;\n")],
    }
    with pytest.raises(ValueError, match="history code differs"):
        stage_blocks(raw)


def test_terminated_when_code_is_only_blanks_then_it_stays_empty():
    from fontlabapp.fontui.feature_blocks import _terminated

    assert _terminated({"prefix": "", "features": [("a", " \t")]})["features"] == [("a", "")]
