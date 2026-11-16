# this_file: tests/test_glyph_completion.py
"""Complete source vocabulary, lazy menu entrypoints and deadline refusals."""

import sys
from threading import Thread
from types import SimpleNamespace as NS

import pytest

import fontlabapp.glyphs.completion.model as module
from fontlabapp.qt.tables.filter.model import Table


def test_all_exact_names_and_empty_font_are_retained():
    names = (".notdef", "A.alt", "A<bad>", "f_f_i", "é", "😀", "Ж")
    assert (
        module.vocabulary(
            Table(("Name", "Unicode", "Modified"), tuple((n, "", "") for n in names))
        )
        == names
    )
    assert module.vocabulary(Table(("Name", "Unicode", "Modified"), ())) == ()


@pytest.mark.parametrize("rows", [(("",),), (("A",), ("A",))])
def test_ambiguous_vocabulary_is_refused_before_partial_publish(rows):
    with pytest.raises(ValueError, match="empty or duplicate"):
        module.vocabulary(
            Table(
                ("Name", "Unicode", "Modified"), tuple((row[0], "", "") for row in rows)
            )
        )


@pytest.mark.parametrize("rows", [(), (("A",),)])
def test_expired_scan_including_empty_font_has_no_partial_result(rows):
    with pytest.raises(TimeoutError, match="expired"):
        module.vocabulary(
            Table(
                ("Name", "Unicode", "Modified"), tuple((row[0], "", "") for row in rows)
            ),
            deadline=-1,
        )


def test_wrong_capture_type_is_refused():
    with pytest.raises(TypeError, match="complete immutable"):
        module.vocabulary(None)


@pytest.mark.parametrize("official", [False, True])
def test_public_entrypoints_pass_real_capture_and_distinct_registry_key(
    monkeypatch, official
):
    calls = []
    capture = object()
    monkeypatch.setitem(
        sys.modules, "fontlabapp.glyphs.catalog.native", NS(capture=capture)
    )
    monkeypatch.setitem(
        sys.modules,
        "fontlabapp.glyphs.completion.ui",
        NS(GlyphCompletionDialog=lambda *args, **kw: (args, kw)),
    )
    monkeypatch.setitem(
        sys.modules,
        "fontlabapp.core.scripting",
        NS(
            show_script_dialog=lambda factory, key: calls.append(
                (factory("parent"), key)
            )
        ),
    )
    (module.show_official if official else module.show)()
    assert calls == [
        (
            (("parent", capture), {"official": official}),
            "glyph_completion_official" if official else "glyph_completion",
        )
    ]


def test_worker_refuses_before_native_import():
    errors = []

    def run():
        try:
            module.show()
        except RuntimeError as error:
            errors.append(str(error))

    thread = Thread(target=run)
    thread.start()
    thread.join()
    assert errors == ["Open glyph completion on the main UI thread."]
