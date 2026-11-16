# this_file: tests/test_guides.py
# SPDX-License-Identifier: Apache-2.0
"""Refuse guide history on automatic dependants before any native mutation."""

from importlib import import_module

import pytest


@pytest.fixture
def api():
    return import_module("fontlabapp.guides.inspect.model")


def test_affected_auto_layers_include_direct_transitive_and_cyclic_dependencies(api):
    records = (
        ("A", False, ()),
        ("manual", False, ("A",)),
        ("Aacute", True, ("A", "acute")),
        ("nested", True, ("manual",)),
        ("cycle1", False, ("cycle2", "A")),
        ("cycle2", True, ("cycle1",)),
        ("safe", True, ("H",)),
    )
    assert api.affected_auto_layers(records, {"A"}) == ["Aacute", "cycle2", "nested"]
    assert api.affected_auto_layers(records, {"H"}) == ["safe"]
    assert api.affected_auto_layers(records, {"zero"}) == []
    assert api.affected_auto_layers(records, set()) == []


def test_repeated_master_records_combine_references_and_auto_roles(api):
    records = (("mix", False, ("A",)), ("mix", True, ("H",)), ("top", True, ("mix",)))
    assert api.affected_auto_layers(records, {"A"}) == ["mix", "top"]
    assert api.affected_auto_layers(records, {"H"}) == ["mix", "top"]


def test_empty_dependency_records_have_no_false_dependants(api):
    assert api.affected_auto_layers((), {"H"}) == []


def test_preflight_refuses_the_entire_mixed_batch_with_auto_dependants(
    api, monkeypatch
):
    records = (("A", False, ()), ("H", False, ()), ("Aacute", True, ("A",)))
    monkeypatch.setattr(api, "dependency_values", lambda package: records)
    with pytest.raises(ValueError, match="Aacute"):
        api.require_safe_targets(object(), {"A", "H"})
    api.require_safe_targets(object(), {"H"})
    api.require_safe_targets(object(), set())


def test_native_dependency_read_fails_closed_on_missing_glyph(api, monkeypatch):
    from types import SimpleNamespace as NS

    package = NS(fgPackage=NS(glyphs=[NS(name="missing")]), findName=lambda name: None)
    with pytest.raises(ValueError, match="source changed"):
        api.dependency_values(package)


def test_native_dependency_read_uses_all_layers_without_fontgate_getters(
    api, monkeypatch
):
    from types import SimpleNamespace as NS

    layer = NS(
        autoLayer=True,
        shapes=[
            NS(isComponent=True, shapeData=NS(componentGlyph="A")),
            NS(isComponent=False),
        ],
    )
    glyph = NS(isNull=False, layers=[layer])
    package = NS(fgPackage=NS(glyphs=[NS(name="Aacute")]), findName=lambda name: glyph)
    assert api.dependency_values(package) == (
        ("Aacute", True, ("A",)),
    )


def test_dependency_values_when_package_is_not_active_then_reads_its_own_glyph_order(
    api, monkeypatch
):
    """Issue 250: names come from the target package, not the active font."""
    from types import SimpleNamespace as NS

    import fontlabapp.masters.inspect.model as masters

    monkeypatch.setattr(masters, "all_names", lambda: ["only_in_active_font"])
    glyphs = {
        name: NS(isNull=False, layers=[NS(autoLayer=False, shapes=[])])
        for name in ("a", "b")
    }
    package = NS(
        fgPackage=NS(glyphs=[NS(name="a"), NS(name="b")]),
        findName=glyphs.get,
    )
    assert api.dependency_values(package) == (("a", False, ()), ("b", False, ()))


def test_preflight_refuses_unknown_target_instead_of_treating_it_as_safe(
    api, monkeypatch
):
    monkeypatch.setattr(api, "dependency_values", lambda package: (("H", False, ()),))
    with pytest.raises(ValueError, match="source changed"):
        api.require_safe_targets(object(), {"missing"})


def test_add_guides_preflights_and_constructs_every_guide_before_one_history_step(
    api, monkeypatch
):
    from types import SimpleNamespace as NS

    calls = []
    g = NS(
        name="H",
        lastModified="before",
        checkInitHistoryState=lambda i: calls.append(("initGlyph", i)),
    )
    a = NS(
        autoLayer=False,
        checkInitHistoryState=lambda i: calls.append(("initA", i)),
        appendGuidelines=lambda values: calls.append(("A", values)),
    )
    b = NS(
        autoLayer=False,
        checkInitHistoryState=lambda i: calls.append(("initB", i)),
        appendGuidelines=lambda values: calls.append(("B", values)),
    )
    monkeypatch.setattr(
        api, "require_safe_targets", lambda p, n: calls.append(("safe", n))
    )
    monkeypatch.setattr(
        api, "new_guide", lambda v: calls.append(("construct", v)) or ("guide", v)
    )
    native = NS(
        flItems=lambda: NS(
            notifyChangesApplied=lambda *args: calls.append(("history", args))
        ),
        UpdateAll=lambda: calls.append(("update",)),
    )
    qt = NS(
        QtCore=NS(
            QDateTime=NS(
                currentDateTimeUtc=lambda: calls.append(("clock",)) or "UTC stamp"
            )
        )
    )
    monkeypatch.setattr(
        api, "_native", lambda name: qt if name == "PythonQt" else native
    )
    assert api.add_guides(
        object(), [(g, a, [1]), (g, b, [2]), (g, a, [])], "Grid Generator"
    ) == {"layers": 2, "guides": 2}
    assert [c[0] for c in calls] == [
        "safe",
        "construct",
        "construct",
        "initA",
        "initB",
        "initGlyph",
        "clock",
        "A",
        "B",
        "history",
        "update",
    ]
    assert calls[9][1] == ("Grid Generator", [a, b, g])
    assert g.lastModified == "UTC stamp"


def test_empty_and_unsafe_guide_jobs_never_enter_history(api, monkeypatch):
    from types import SimpleNamespace as NS

    calls = []
    monkeypatch.setattr(api, "_native", lambda name: calls.append(name))
    assert api.add_guides(object(), []) == {"layers": 0, "guides": 0}
    with pytest.raises(ValueError, match="automatic"):
        api.add_guides(object(), [(NS(name="auto"), NS(autoLayer=True), [1])])

    def refuse(*args):
        raise ValueError("unsafe dependants")

    monkeypatch.setattr(api, "require_safe_targets", refuse)
    with pytest.raises(ValueError, match="unsafe dependants"):
        api.add_guides(object(), [(NS(name="A"), NS(autoLayer=False), [1])])
    assert not calls


def test_guide_construction_failure_prevents_every_write_and_history_notification(
    api, monkeypatch
):
    from types import SimpleNamespace as NS

    calls = []
    monkeypatch.setattr(api, "require_safe_targets", lambda *a: None)

    def construct(value):
        if value == 2:
            raise RuntimeError("owned constructor fault")
        return value

    monkeypatch.setattr(api, "new_guide", construct)
    monkeypatch.setattr(api, "_native", lambda name: calls.append(name))
    with pytest.raises(RuntimeError, match="owned constructor fault"):
        api.add_guides(object(), [(NS(name="H"), NS(autoLayer=False), [1, 2])])
    assert not calls


def test_partial_native_append_failure_still_records_one_recoverable_history_step(
    api, monkeypatch
):
    from types import SimpleNamespace as NS

    calls = []
    glyph = NS(
        name="H", lastModified="before", checkInitHistoryState=lambda index: None
    )
    first = NS(
        autoLayer=False,
        checkInitHistoryState=lambda index: None,
        appendGuidelines=lambda values: calls.append("first write"),
    )

    def broken(values):
        calls.append("second attempted")
        raise RuntimeError("owned append fault")

    second = NS(
        autoLayer=False,
        checkInitHistoryState=lambda index: None,
        appendGuidelines=broken,
    )
    native = NS(
        flItems=lambda: NS(notifyChangesApplied=lambda *args: calls.append("history")),
        UpdateAll=lambda: calls.append("update"),
    )
    qt = NS(QtCore=NS(QDateTime=NS(currentDateTimeUtc=lambda: "UTC stamp")))
    monkeypatch.setattr(
        api, "_native", lambda name: qt if name == "PythonQt" else native
    )
    monkeypatch.setattr(api, "new_guide", lambda value: value)
    monkeypatch.setattr(api, "require_safe_targets", lambda *args: None)
    with pytest.raises(RuntimeError, match="owned append fault"):
        api.add_guides(object(), [(glyph, first, [1]), (glyph, second, [2])])
    assert calls == ["first write", "second attempted", "history", "update"]
    assert glyph.lastModified == "UTC stamp"
