# this_file: tests/test_kerning_group_proof_native.py
"""Real class-map and proof symbol mechanics, with only native data replaced."""

from types import SimpleNamespace as NS

import fontlabapp.kerning.group_proof.native as native
import fontlabapp.kerning.group_proof.model as api
import pytest
from fontlabapp.kerning.group_proof.selection import First


class Symbol:
    def __init__(self, value):
        self.value = value
        self.layerName = ""


def owned(monkeypatch, *, selected=True, groups=None):
    glyphs = [
        NS(id=12, name="right.peer"),
        NS(id=11, name="current"),
        NS(id=13, name="left.unencoded"),
    ]
    groups = (
        groups
        if groups is not None
        else {
            "nativeLeft": (["current", "right.peer"], "KernLeft"),
            "nativeRight": (
                ["left.unencoded", "current", "missing.member"],
                "KernRight",
            ),
        }
    )
    package = NS(id=42, fgId=777, kerning=lambda master: NS(groups=groups))
    first = NS(package=package, glyph=NS(fgGlyphId=11), glyph_name="current")
    second = NS(package=package, glyph=NS(fgGlyphId=13), glyph_name="left.unencoded")
    selection = NS(
        context=(42, "Regular", "editor", 88),
        occurrences=(first, second) if selected else (),
    )
    font = NS(id=777, glyphs=glyphs)
    state = NS(
        package=package,
        selection=selection,
        font=font,
        groups=groups,
        opened=[],
        messages=[],
        native_requests=[],
    )
    monkeypatch.setattr(native, "current_package", lambda: state.package)

    def first_selection(deadline):
        value = state.selection
        if not value.occurrences:
            return None
        first = value.occurrences[0]
        return First(
            value.context,
            int(first.glyph.fgGlyphId),
            first.glyph_name,
            0,
            0,
            first.package,
        )

    monkeypatch.setattr(native, "first_selection", first_selection)
    provider = NS(
        CurrentFont=lambda: state.font,
        fgSymbol=Symbol,
        fgSymbolList=lambda values: tuple(values),
        MainWindow=lambda: None,
    )
    monkeypatch.setattr(native, "_native", lambda name: provider)
    monkeypatch.setattr(
        native.named,
        "_open_symbols",
        lambda provider, symbols, pid, master, deadline: state.opened.append(
            (symbols, pid, master)
        ),
    )
    monkeypatch.setattr(
        native,
        "diagnose",
        lambda title, message: state.messages.append((title, message)),
    )
    return state


def test_complete_action_uses_first_selected_glyph_and_opposite_native_pair_sides(
    monkeypatch,
):
    state = owned(monkeypatch)
    proof = api.run()
    assert (
        proof.current == "current"
        and proof.left == ("left.unencoded",)
        and proof.right == ("right.peer",)
    )
    symbols, pid, master = state.opened[0]
    assert (pid, master) == (42, "Regular")
    assert [(s.value, s.layerName) for s in symbols] == [
        (v, "Regular")
        for v in [
            "current",
            10,
            76,
            58,
            32,
            "left.unencoded",
            10,
            82,
            58,
            32,
            "right.peer",
            10,
        ]
    ]
    assert not state.messages


def test_both_side_and_nonkerning_memberships_are_filtered_correctly(monkeypatch):
    state = owned(
        monkeypatch,
        groups={
            "first": (["current", "left.unencoded"], "KernBothSide"),
            "nonkerning": (["current", "right.peer"], "NoKerningMode"),
            "otherNonkerning": (["current", "right.peer"], "OpenType"),
        },
    )
    proof = api.run()
    assert proof.left == proof.right == ("left.unencoded",)
    assert len(state.opened) == 1


def test_no_groups_or_singletons_diagnose_without_a_tab(monkeypatch):
    for groups in [{}, {"solo": (["current"], "KernBothSide")}]:
        state = owned(monkeypatch, groups=groups)
        result = api.run()
        assert not result.has_peers and not state.opened
        assert state.messages[0][0] == "No Kerning Groups"


def test_no_font_or_selected_glyph_uses_original_script_error_diagnosis(monkeypatch):
    state = owned(monkeypatch, selected=False)
    assert api.run() is None and state.messages[0][0] == "Script Error"
    state = owned(monkeypatch)
    state.package = None
    assert api.run() is None and not state.opened


@pytest.mark.parametrize(
    "change", ["font", "order", "name", "membership", "selected", "missing-current"]
)
def test_capture_refuses_changes_before_new_tab(monkeypatch, change):
    state = owned(monkeypatch)
    original = native._read
    calls = []

    def read(selection, deadline):
        result = original(selection, deadline)
        calls.append(True)
        if len(calls) == 1:
            if change == "font":
                state.font.id = 999
            elif change == "order":
                state.font.glyphs.reverse()
            elif change == "name":
                state.font.glyphs[0].name = "changed"
            elif change == "membership":
                state.groups.clear()
            elif change == "selected":
                state.selection = NS(
                    context=(42, "Other"), occurrences=state.selection.occurrences
                )
            else:
                state.font.glyphs.pop(1)
        return result

    monkeypatch.setattr(native, "_read", read)
    with pytest.raises(ValueError):
        api.run()
    assert not state.opened


def test_unrelated_metadata_getters_are_never_used(monkeypatch):
    state = owned(monkeypatch)

    class Glyph:
        def __init__(self, ident, name):
            self.id = ident
            self.name = name

        @property
        def fgGlyph(self):
            raise AssertionError("cache-mutating mirror getter")

        @property
        def mark(self):
            raise AssertionError("unrelated mark getter")

        @property
        def unicodes(self):
            raise AssertionError("Unicode substitution")

    state.font.glyphs = [Glyph(g.id, g.name) for g in state.font.glyphs]
    assert api.run().left == ("left.unencoded",)


def test_missing_selected_glyph_or_name_is_diagnosed_before_tab(monkeypatch):
    state = owned(monkeypatch)
    state.font.glyphs.pop(1)
    with pytest.raises(ValueError, match="selected glyph"):
        api.run()
    state = owned(monkeypatch)
    state.font.glyphs[0].name = ""
    with pytest.raises(ValueError, match="glyph name"):
        api.run()
    assert not state.opened


def test_deadline_refuses_whole_capture_and_tab(monkeypatch):
    state = owned(monkeypatch)
    with pytest.raises(TimeoutError):
        native.capture(-1)
    assert not state.opened


def test_source_changed_after_plan_is_refused(monkeypatch):
    state = owned(monkeypatch)
    original = api.build

    def changed(*args):
        result = original(*args)
        state.groups.clear()
        return result

    monkeypatch.setattr(api, "build", changed)
    with pytest.raises(ValueError, match="changed"):
        api.run()
    assert not state.opened


def test_named_tab_failure_propagates_without_replacing_current_tab(monkeypatch):
    state = owned(monkeypatch)

    def fail(*args):
        raise RuntimeError("Owned fresh-tab refusal")

    monkeypatch.setattr(native.named, "_open_symbols", fail)
    with pytest.raises(RuntimeError, match="fresh-tab"):
        api.run()
    assert not state.opened


def test_symbol_deadline_and_duplicate_name_spacing(monkeypatch):
    state = owned(monkeypatch)
    proof = api.build(
        (
            api.GlyphGroups(1, "cur", "L", None),
            api.GlyphGroups(2, "same", "L", None),
            api.GlyphGroups(3, "same", "L", None),
        ),
        1,
    )
    with pytest.raises(TimeoutError):
        native.open_proof(NS(package_id=42, master="Regular"), proof, -1)
    native.open_proof(NS(package_id=42, master="Regular"), proof, 10**30)
    assert [s.value for s in state.opened[0][0]] == [
        "cur",
        10,
        76,
        58,
        32,
        "same",
        32,
        "same",
        10,
        10,
    ]


def test_absent_native_font_and_lost_selection_refuse_before_tab(monkeypatch):
    state = owned(monkeypatch)
    state.font = None
    with pytest.raises(ValueError, match="font changed"):
        api.run()
    state = owned(monkeypatch)
    original = native._read

    def read(selection, deadline):
        result = original(selection, deadline)
        state.selection = NS(context=selection.context, occurrences=())
        return result

    monkeypatch.setattr(native, "_read", read)
    with pytest.raises(ValueError, match="changed"):
        api.run()
    assert not state.opened


@pytest.mark.parametrize("failure", [False, True])
def test_owned_diagnosis_cleans_up_on_normal_or_failed_execution(monkeypatch, failure):
    calls = []
    parent = object()

    class Box:
        Information, Ok = 1, 2

        def __init__(self, actual):
            assert actual is parent

        def windowFlags(self):
            return 1

        def setWindowFlags(self, value):
            assert value == 1 | 0x40000

        def setText(self, value):
            calls.append(("text", value))

        def setInformativeText(self, value):
            calls.append(("message", value))

        def setIcon(self, value):
            calls.append(("icon", value))

        def setWindowTitle(self, value):
            calls.append(("title", value))

        def setStandardButtons(self, value):
            calls.append(("buttons", value))

        def exec(self):
            if failure:
                raise RuntimeError("owned execution failure")
            return 1

        def deleteLater(self):
            calls.append(("deleted", True))

    monkeypatch.setattr(
        native,
        "_native",
        lambda name: (
            NS(QtGui=NS(QMessageBox=Box), QtCore=NS(Qt=NS(WindowStaysOnTopHint=0x40000)))
            if name == "PythonQt"
            else NS(MainWindow=lambda: parent)
        ),
    )
    if failure:
        with pytest.raises(RuntimeError, match="execution failure"):
            native.diagnose("No Kerning Groups", "No peers")
    else:
        native.diagnose("No Kerning Groups", "No peers")
    assert ("title", "No Kerning Groups") in calls
    assert calls[-1] == ("deleted", True)


@pytest.mark.parametrize("side", ["KernLeft", "KernRight", "KernBothSide"])
def test_ambiguous_native_groups_are_diagnosed_before_tab_creation(monkeypatch, side):
    messages = []
    for reverse in [False, True]:
        rows = [
            ("one", (["current", "right.peer"], side)),
            ("two", (["current", "left.unencoded"], side)),
        ]
        state = owned(monkeypatch, groups=dict(reversed(rows) if reverse else rows))
        assert api.run() is None
        assert not state.opened and state.messages[0][0] == "Ambiguous Kerning Groups"
        messages.append(state.messages[0][1])
    assert messages[0] == messages[1]


def test_duplicate_same_group_is_not_ambiguous_and_missing_members_are_ignored(
    monkeypatch,
):
    state = owned(
        monkeypatch,
        groups={
            "both": (["current", "current", "left.unencoded"], "KernBothSide"),
            "missingOne": (["absent"], "KernBothSide"),
            "missingTwo": (["absent"], "KernBothSide"),
        },
    )
    assert api.run().left == ("left.unencoded",)
    assert len(state.opened) == 1
