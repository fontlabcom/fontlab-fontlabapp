# this_file: tests/test_fontui_kerning_groups.py
"""Actual borrowed RFont kerning workflow and complete owned-font preservation."""

from copy import deepcopy
import base64
import importlib
import pickle
from types import SimpleNamespace

import pytest
import _cov_qt as fq
import test_fontui_glyph_metrics as _fixtures

composition_env = _fixtures.composition_env

PAIR = ("public.kern1.A", "public.kern2.V")
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP4z8DwHwAFAAH/iZk9HQAAAABJRU5ErkJggg=="
)


@pytest.fixture
def real_fonts(composition_env, monkeypatch):
    from fontlab_fontport.live import RFont
    from fontlab_fontport.memory import UFOBackend

    from ufoLib2.objects import Anchor, Guideline, Image

    source = fq.ufo_font()
    source.info.familyName, source.info.styleName = "Owned group explorer", "Regular"
    source.lib["owned"] = {"nested": [True, 1, "preserve"]}
    source.features.text = "feature liga { sub A V by A; } liga;"
    source.images["owned.png"] = PNG
    source.data["owned/payload.bin"] = b"owned\0\xff"
    glyph = source["A"]
    glyph.note, glyph.lib["owned"] = "Preserve note", [1, 2, 3]
    glyph.image = Image("owned.png", (1.25, 0.2, -0.1, 0.9, 13.5, -17.75))
    glyph.anchors = [Anchor(100, 700, "top", identifier="owned-anchor")]
    glyph.guidelines = [Guideline(25, 0, 90, "owned-guide")]
    source.newGlyph("B").width = 420
    glyph.getPointPen().addComponent("B", (1, 0, 0, 1, 10, 20))
    source.layers.newLayer("owned.background").newGlyph("untouched").width = 333
    source.kerning[("B", "V")] = 7
    source.glyphOrder = ["A", "B", "V"]
    backends = [UFOBackend(source), UFOBackend(deepcopy(source))]
    fonts = [RFont(backend) for backend in backends]
    expected = [deepcopy(backend.font) for backend in backends]
    writes, group_writes, closes, owners, forbidden = [], [], [], [], []

    def refuse(name):
        def unexpected(*args, **kwargs):
            forbidden.append(name)
            raise AssertionError("Unexpected borrowed-font mutator: " + name)

        return unexpected

    for backend in backends:
        group_setter = backend.set_groups

        def apply_groups(values, *, _setter=group_setter, _backend=backend, **kwargs):
            group_writes.append((_backend, dict(values)))
            return _setter(values, **kwargs)

        monkeypatch.setattr(backend, "set_groups", apply_groups)
        setter = backend.set_kerning

        def apply(values, *, _setter=setter, _backend=backend, **kwargs):
            writes.append((_backend, dict(values)))
            return _setter(values, **kwargs)

        monkeypatch.setattr(backend, "set_kerning", apply)
        monkeypatch.setattr(backend, "close", lambda: closes.append(True))
        for name in (
            "write_glyph",
            "edit_image",
            "new_glyph",
            "remove_glyph",
            "rename_glyph",
            "new_layer",
            "remove_layer",
            "rename_layer",
            "set_info",
            "set_info_many",
            "set_lib",
            "set_features",
            "set_feature_blocks",
            "save_options",
            "save",
        ):
            monkeypatch.setattr(backend, name, refuse(name))
    state = SimpleNamespace(
        env=composition_env,
        fonts=fonts,
        backends=backends,
        expected=expected,
        writes=writes,
        group_writes=group_writes,
        closes=closes,
        owners=owners,
    )
    yield state
    for owner in reversed(owners):
        if hasattr(owner, "release"):
            assert owner._release_now()
        else:
            owner.close()
            assert owner._close_complete and owner.preview._close_complete
    assert not closes, "UI must never close borrowed fonts"
    assert not forbidden, "UI attempted an unrelated backend mutation"
    for backend, before in zip(backends, expected):
        assert backend.font.groups == before.groups, (
            backend.font.groups,
            before.groups,
        )
        assert backend.font == before, "Complete font/resources changed unexpectedly"
        assert pickle.dumps(backend.font) == pickle.dumps(before)
        assert backend.font.images["owned.png"] == PNG and not backend.closed


def window_for(state):
    module = importlib.import_module("fontlabapp.fontui.kerning_groups")
    owner = module.show(state.fonts[0], state.env.parent)
    state.owners.append(owner)
    return owner


def choose(owner, name):
    owner.groups.group_list.setCurrentRow(owner.groups.names.index(name))


def pair(owner, left=PAIR[0], right=PAIR[1], value="-80"):
    for control, text in zip(
        (
            owner.kerning.left_control,
            owner.kerning.right_control,
            owner.kerning.value_control,
        ),
        (left, right, value),
    ):
        control.setText(text)


@pytest.mark.parametrize("side", ["left", "right"])
@pytest.mark.parametrize("equal", [False, True])
def test_use_selected_group_when_actual_control_then_one_inspect_and_drafts(
    real_fonts, monkeypatch, side, equal
):
    c = window_for(real_fonts)
    selected = PAIR[side == "right"]
    choose(c, selected)
    c.groups.name_control.setText("typed rename is not selection")
    pair(
        c,
        PAIR[0] if equal or side == "right" else "A",
        PAIR[1] if equal or side == "left" else "V",
        "-27.5",
    )
    original, calls = c.kerning.inspect, []

    def inspect(*args):
        calls.append(args)
        return original(*args)

    monkeypatch.setattr(c.kerning, "inspect", inspect)
    before = (
        c.kerning.left_control.text,
        c.kerning.right_control.text,
        c.kerning.value_control.text,
    )
    getattr(c, "use_" + side).clicked.emit()
    assert len(calls) == 1
    after = (
        c.kerning.left_control.text,
        c.kerning.right_control.text,
        c.kerning.value_control.text,
    )
    expected = list(before)
    expected[side == "right"] = selected
    assert after == tuple(expected)
    assert [g.name for g in c.kerning.preview.run.glyphs] == ["A", "V"]
    assert not real_fonts.writes and not real_fonts.group_writes


def test_group_apply_when_representative_removed_then_real_proof_recomputed(real_fonts):
    c = window_for(real_fonts)
    choose(c, PAIR[0])
    c.groups.members_control.setText("B")
    real_fonts.expected[0].groups = {
        name: tuple(members) for name, members in real_fonts.expected[0].groups.items()
    }
    real_fonts.expected[0].groups[PAIR[0]] = ("A", "B")
    assert c.groups.edit("add_members")
    pair(c)
    assert [g.name for g in c.kerning.preview.run.glyphs] == ["A", "V"]
    c.groups.member_list.setCurrentRow(0)
    real_fonts.expected[0].groups[PAIR[0]] = ("B",)
    assert c.groups.edit("remove_members")
    assert [(g.name, g.x) for g in c.kerning.preview.run.glyphs] == [
        ("B", 0),
        ("V", 427),
    ]
    assert len(real_fonts.group_writes) == 2 and not real_fonts.writes


def test_release_when_first_preview_refuses_then_both_editors_fenced(
    real_fonts, monkeypatch
):
    c = window_for(real_fonts)
    choose(c, PAIR[0])
    c.groups.name_control.setText("ordinary-new")
    original = c.groups.preview.close
    monkeypatch.setattr(c.groups.preview, "close", lambda: None)
    try:
        assert not c._release_now()
        assert all(
            o.closed for o in (c.groups, c.groups.preview, c.kerning, c.kerning.preview)
        )
        assert c.groups.on_apply is None and c.kerning.on_apply is None
        assert not c.groups.edit("add") and not c.kerning.edit("set")
        assert not real_fonts.writes and not real_fonts.group_writes
    finally:
        monkeypatch.setattr(c.groups.preview, "close", original)


def expect_groups(state, values):
    """Specify the accepted complete group map independently of backend readback."""
    state.expected[0].groups = {
        name: tuple(members) for name, members in values.items()
    }


def test_show_when_real_fonts_then_four_distinct_owners_and_no_implicit_selection(
    real_fonts,
):
    c = window_for(real_fonts)
    assert c.groups.font is c.kerning.font is real_fonts.fonts[0]
    assert c.groups.preview.font is c.kerning.preview.font is c.font
    assert (
        len({id(o) for o in (c.groups, c.kerning, c.groups.preview, c.kerning.preview)})
        == 4
    )
    assert c.groups.selected is None and c.kerning.selected is None
    assert c.owned.content.modal is False
    assert not real_fonts.writes and not real_fonts.group_writes


@pytest.mark.parametrize("kind", ["none", "empty", "unavailable_label"])
def test_show_when_no_or_empty_font_then_target_is_explicit(
    composition_env, monkeypatch, kind
):
    from fontlab_fontport.live import RFont
    from fontlab_fontport.memory import UFOBackend
    from ufoLib2 import Font
    from fontlabapp.fontui import kerning_groups, model

    font = None if kind == "none" else RFont(UFOBackend(Font()))
    if kind == "unavailable_label":
        monkeypatch.setattr(
            model.FontListState,
            "label",
            lambda font: (_ for _ in ()).throw(OSError("label unavailable")),
        )
    c = kerning_groups.show(font, composition_env.parent)
    try:
        assert c.font is font and c.groups.font is font and c.kerning.font is font
        c.use_left.clicked.emit()
        assert c.diagnostic.text == "Select a group first."
        assert c.groups.editable is (font is not None)
        if kind == "unavailable_label":
            assert "label unavailable" in c.target.text
    finally:
        assert c._release_now()


def test_no_selection_when_use_then_no_model_read(real_fonts, monkeypatch):
    c = window_for(real_fonts)
    with monkeypatch.context() as patch:
        patch.setattr(
            real_fonts.backends[0],
            "get_groups",
            lambda: pytest.fail("No selected group must not read model"),
        )
        patch.setattr(
            real_fonts.backends[0],
            "get_kerning",
            lambda: pytest.fail("No selected group must not read pairs"),
        )
        c.use_left.clicked.emit()
        c.use_right.clicked.emit()
    assert c.diagnostic.text == "Select a group first."
    assert not real_fonts.writes and not real_fonts.group_writes


def test_members_when_selected_then_only_group_preview_changes(real_fonts):
    c = window_for(real_fonts)
    pair(c)
    prior = c.kerning.preview.run
    choose(c, PAIR[0])
    assert c.groups.preview.name == "A"
    choose(c, PAIR[1])
    assert c.groups.preview.name == "V" and c.kerning.preview.run is prior
    assert not real_fonts.writes and not real_fonts.group_writes


@pytest.mark.parametrize(
    "action", ["add", "rename", "delete", "add_members", "remove_members"]
)
def test_group_action_when_accepted_then_one_write_and_changed_callback(
    real_fonts, monkeypatch, action
):
    c = window_for(real_fonts)
    choose(c, PAIR[0])
    pair(c, "A", "V", "-27.5")
    before_pair = dict(real_fonts.expected[0].kerning)
    values = dict(real_fonts.expected[0].groups)
    if action == "add":
        c.groups.name_control.setText("ordinary-new")
        values["ordinary-new"] = ()
    elif action == "rename":
        c.groups.name_control.setText("public.kern1.Renamed")
        values["public.kern1.Renamed"] = values.pop(PAIR[0])
    elif action == "delete":
        del values[PAIR[0]]
    elif action == "add_members":
        c.groups.members_control.setText("B")
        values[PAIR[0]] = ("A", "B")
    else:
        c.groups.member_list.setCurrentRow(0)
        values[PAIR[0]] = ()
    calls, original = [], c.kerning._changed

    def changed():
        calls.append(True)
        original()

    monkeypatch.setattr(c.kerning, "_changed", changed)
    expect_groups(real_fonts, values)
    c.groups.buttons[action].clicked.emit()
    assert calls == [True] and len(real_fonts.group_writes) == 1
    assert not real_fonts.writes
    assert real_fonts.backends[0].font.kerning == before_pair
    assert (
        c.kerning.left_control.text,
        c.kerning.right_control.text,
        c.kerning.value_control.text,
    ) == ("A", "V", "-27.5")
    assert c.kerning.preview.run is not None
    if action == "rename":
        c.use_left.clicked.emit()
        assert c.kerning.left_control.text == "public.kern1.Renamed"
        assert (
            c.kerning.right_control.text == "V"
            and c.kerning.value_control.text == "-27.5"
        )


@pytest.mark.parametrize(
    "route",
    ["same_rename", "duplicate_member", "unknown_member", "overlap", "opposite_side"],
)
def test_group_noop_or_validation_when_requested_then_exact_write_policy(
    real_fonts, route
):
    c = window_for(real_fonts)
    choose(c, PAIR[0])
    action = "add_members"
    if route == "same_rename":
        action = "rename"
    elif route == "duplicate_member":
        c.groups.members_control.setText("A")
    elif route == "unknown_member":
        c.groups.members_control.setText("Missing")
    else:
        # Seed an independently specified imported group for same-side overlap.
        name = "public.kern1.Other" if route == "overlap" else "public.kern2.Other"
        for font in (real_fonts.backends[0].font, real_fonts.expected[0]):
            font.groups[name] = ("B",)
        c.groups.members_control.setText("B")
        if route == "opposite_side":
            values = dict(real_fonts.expected[0].groups)
            values[PAIR[0]] = ("A", "B")
            expect_groups(real_fonts, values)
    result = c.groups.edit(action)
    assert result is (route == "opposite_side")
    assert len(real_fonts.group_writes) == int(route == "opposite_side")
    assert not real_fonts.writes


@pytest.mark.parametrize(
    "left,right",
    [("Missing", "V"), (PAIR[1], "V"), ("A", PAIR[0]), ("ordinary", "V"), ("", "V")],
)
def test_pair_when_invalid_then_existing_apply_refuses_without_setter(
    real_fonts, left, right
):
    for font in (real_fonts.backends[0].font, real_fonts.expected[0]):
        font.groups["ordinary"] = ("A",)
    c = window_for(real_fonts)
    pair(c, left, right, "0")
    assert not c.kerning.edit("apply")
    assert not real_fonts.writes and not real_fonts.group_writes
    assert c.kerning.diagnostic.text


@pytest.mark.parametrize("members", [(), ("Missing",), ("A", "A")])
def test_imported_group_when_empty_absent_or_duplicate_then_truthful_proof(
    real_fonts, members
):
    for font in (real_fonts.backends[0].font, real_fonts.expected[0]):
        font.groups[PAIR[0]] = members
    c = window_for(real_fonts)
    choose(c, PAIR[0])
    pair(c)
    c.use_left.clicked.emit()
    assert not real_fonts.writes and not real_fonts.group_writes
    if not members or members == ("Missing",):
        assert [g.name for g in c.kerning.preview.run.glyphs] == [None, "V"]
        assert "Missing" in c.kerning.preview.diagnostic.text
    else:
        assert not c.kerning.edit("apply")


@pytest.mark.parametrize("failure", ["ignored", "partial", "throw", "partial_throw"])
def test_group_write_when_backend_refuses_or_partially_changes_then_truthful_no_replay(
    real_fonts, monkeypatch, failure
):
    c = window_for(real_fonts)
    c.groups.name_control.setText("ordinary-new")
    backend = real_fonts.backends[0]
    calls, callbacks = [], []
    c.groups.on_apply = lambda *args: callbacks.append(args)
    if failure.startswith("partial"):
        values = dict(real_fonts.expected[0].groups)
        values["partial-owned"] = ("B",)
        expect_groups(real_fonts, values)

    def broken(values, **kwargs):
        calls.append(dict(values))
        if failure.startswith("partial"):
            backend.font.groups = {
                name: tuple(members) for name, members in backend.font.groups.items()
            }
            backend.font.groups["partial-owned"] = ("B",)
        if failure in {"throw", "partial_throw"}:
            raise OSError("owned write failure")

    monkeypatch.setattr(backend, "set_groups", broken)
    assert not c.groups.edit("add")
    assert len(calls) == 1 and not callbacks and not real_fonts.writes
    assert (
        "differs" in c.groups.diagnostic.text
        if failure in {"ignored", "partial"}
        else "owned write failure" in c.groups.diagnostic.text
    )


@pytest.mark.parametrize("failure", [None, "read", "stale", "escape"])
def test_group_callback_when_read_or_callback_fails_then_accepted_write_not_replayed(
    real_fonts, monkeypatch, failure
):
    from fontlab_fontport.errors import StaleObjectError

    c = window_for(real_fonts)
    pair(c)
    c.kerning.preview.select_key(real_fonts.env.qt.QtCore.Qt.Key_Home)
    c.groups.name_control.setText("ordinary-new")
    values = dict(real_fonts.expected[0].groups)
    values["ordinary-new"] = ()
    expect_groups(real_fonts, values)
    backend, observations = real_fonts.backends[0], []
    original = backend.get_kerning

    def read():
        observations.append(
            (
                c.kerning.preview.run,
                dict(c.kerning.preview.outlines),
                c.kerning.preview.selected_index,
            )
        )
        if failure == "read":
            raise OSError("owned callback read")
        if failure == "stale":
            raise StaleObjectError("owned callback stale")
        return original()

    with monkeypatch.context() as patch:
        if failure == "escape":
            patch.setattr(
                c.kerning,
                "_changed",
                lambda: (_ for _ in ()).throw(OSError("escaped callback")),
            )
        else:
            patch.setattr(backend, "get_kerning", read)
        assert c.groups.edit("add")
    assert len(real_fonts.group_writes) == 1 and not real_fonts.writes
    if failure == "escape":
        assert "Applied groups; refresh callback failed" in c.groups.diagnostic.text
    else:
        assert observations[0] == (None, {}, None)
        assert c.groups.diagnostic.text == "Applied font groups."
        if failure:
            assert c.kerning.preview.run is None and not c.kerning.editable
        else:
            assert c.kerning.preview.run is not None


def test_callback_when_foreign_or_nested_then_no_write_or_revalidation(
    real_fonts, monkeypatch
):
    c = window_for(real_fonts)
    calls = []
    monkeypatch.setattr(c.kerning, "_changed", lambda: calls.append(True))
    with pytest.raises(ValueError, match="captured font"):
        c._groups_applied(real_fonts.fonts[1], {})
    c._busy = 1
    c._groups_applied(c.font, {})
    c.use("left")
    c._busy = 0
    assert not calls
    assert c._release_now()
    c._groups_applied(real_fonts.fonts[0], {})
    c.use("right")
    assert not calls


def test_kerning_when_zero_noop_fraction_and_delete_then_existing_real_semantics(
    real_fonts,
):
    c = window_for(real_fonts)
    calls = []
    c.kerning.on_apply = lambda *args: calls.append(args)
    pair(c, "A", "V", "0")
    real_fonts.expected[0].kerning[("A", "V")] = 0.0
    assert c.kerning.edit("apply")
    assert not c.kerning.edit("apply")
    c.kerning.value_control.setText("-10.25")
    real_fonts.expected[0].kerning[("A", "V")] = -10.25
    assert c.kerning.edit("apply")
    del real_fonts.expected[0].kerning[("A", "V")]
    assert c.kerning.edit("delete")
    assert not c.kerning.edit("delete")
    assert len(real_fonts.writes) == len(calls) == 3 and not real_fonts.group_writes
    assert [(g.name, g.x) for g in c.kerning.preview.run.glyphs] == [
        ("A", 0),
        ("V", 520),
    ]


def test_stale_captured_font_when_actions_then_never_falls_back_to_other_font(
    real_fonts, monkeypatch
):
    c = window_for(real_fonts)
    pair(c)
    choose(c, PAIR[0])
    with monkeypatch.context() as patch:
        patch.setattr(real_fonts.backends[0], "closed", True)
        c.use_left.clicked.emit()
        assert not c.groups.edit("delete") and not c.kerning.edit("apply")
        assert c.groups.font is c.kerning.font is real_fonts.fonts[0]
    assert not real_fonts.writes and not real_fonts.group_writes


@pytest.mark.parametrize(
    "which", ["groups", "group_preview", "kerning", "pair_preview"]
)
@pytest.mark.parametrize(
    "fault",
    ["no_ack", "exception", "interrupt", "disconnect", "hide", "delete", "reentrant"],
)
def test_release_when_each_actual_owner_fails_then_fence_all_and_retry(
    real_fonts, monkeypatch, which, fault
):
    c = window_for(real_fonts)
    choose(c, PAIR[0])
    pair(c, "A", "V", "0")
    c.groups.name_control.setText("ordinary-new")
    owners = {
        "groups": c.groups,
        "group_preview": c.groups.preview,
        "kerning": c.kerning,
        "pair_preview": c.kerning.preview,
    }
    target = owners[which]
    callback_calls = []
    c.groups.on_apply = c.kerning.on_apply = lambda *args: callback_calls.append(args)

    def fail(*args):
        if fault == "interrupt":
            raise KeyboardInterrupt("owned interruption")
        raise OSError("owned cleanup error")

    with monkeypatch.context() as patch:
        if fault in {"exception", "interrupt"}:
            patch.setattr(target, "close", fail)
        elif fault == "no_ack":
            patch.setattr(target, "close", lambda: None)
        elif fault == "disconnect":
            signal, _ = target.connections[-1]
            patch.setattr(signal, "disconnect", lambda slot: False)
        elif fault in {"hide", "delete"}:
            patch.setattr(
                target.widget,
                "hide" if fault == "hide" else "deleteLater",
                lambda: False,
            )
        else:
            original = target.close

            def reenter():
                assert not c._release_now()
                original()

            patch.setattr(target, "close", reenter)
        if fault == "interrupt":
            with pytest.raises(KeyboardInterrupt, match="owned interruption"):
                c._release_now()
        else:
            assert c._release_now() is (fault == "reentrant")
        assert all(owner.closed for owner in owners.values())
        assert owners["groups"].on_apply is None and owners["kerning"].on_apply is None
        assert not owners["groups"].edit("add") and not owners["kerning"].edit("apply")
        c.use_left.clicked.emit()
        c.use_right.clicked.emit()
        assert (
            not callback_calls and not real_fonts.writes and not real_fonts.group_writes
        )
        if fault != "reentrant":
            assert (
                c
                in importlib.import_module("fontlabapp.fontui.kerning_groups")._HANDLES
            )
            assert getattr(c, "groups") is owners["groups"]
    assert c._release_now() and all(owner._close_complete for owner in owners.values())


@pytest.mark.parametrize("fault", ["refuse", "interrupt"])
def test_scope_disconnect_when_fails_then_all_owners_fenced_before_cleanup(
    real_fonts, monkeypatch, fault
):
    c = window_for(real_fonts)
    owners = (c.groups, c.groups.preview, c.kerning, c.kerning.preview)
    signal = c.use_right.clicked

    def disconnect(slot):
        assert all(owner.closed for owner in owners)
        if fault == "interrupt":
            raise KeyboardInterrupt("owned scope interruption")
        return False

    with monkeypatch.context() as patch:
        patch.setattr(signal, "disconnect", disconnect)
        if fault == "interrupt":
            with pytest.raises(KeyboardInterrupt):
                c._release_now()
        else:
            assert not c._release_now()
        assert not c.groups.edit("add") and not c.kerning.edit("apply")
        assert c.groups.on_apply is None and c.kerning.on_apply is None
    assert c._release_now()


@pytest.mark.parametrize("dispatch", ["use", "group_callback"])
@pytest.mark.parametrize("route", ["release", "finished", "destroyed"])
def test_close_when_inside_active_dispatch_then_deletion_deferred(
    real_fonts, monkeypatch, dispatch, route
):
    c = window_for(real_fonts)
    choose(c, PAIR[0])
    pair(c)
    owners = (c.groups, c.groups.preview, c.kerning, c.kerning.preview)
    original = c.kerning.inspect if dispatch == "use" else c.kerning._changed

    def during(*args):
        assert c._busy == 1
        if route == "release":
            assert not c.release()
        else:
            getattr(c.owned.content, route).emit()
        assert all(owner.closed and not owner._close_complete for owner in owners)
        assert not c.groups.edit("delete") and not c.kerning.edit("apply")
        c.use_right.clicked.emit()
        return original(*args)

    monkeypatch.setattr(
        c.kerning, "inspect" if dispatch == "use" else "_changed", during
    )
    if dispatch == "use":
        c.use_left.clicked.emit()
    else:
        c.groups.name_control.setText("ordinary-new")
        values = dict(real_fonts.expected[0].groups)
        values["ordinary-new"] = ()
        expect_groups(real_fonts, values)
        assert c.groups.edit("add")
    assert c._busy == 0 and c._queued and not c._released
    assert len(real_fonts.env.queue) == 1
    real_fonts.env.queue.pop()()
    assert c._released and all(owner._close_complete for owner in owners)


@pytest.mark.parametrize("which", ["groups", "kerning"])
@pytest.mark.parametrize("cleanup", ["success", "refuse", "interrupt"])
def test_constructor_when_actual_factory_fails_then_partial_owner_retained(
    real_fonts, monkeypatch, which, cleanup
):
    from fontlabapp.fontui import kerning_groups

    module = importlib.import_module("fontlabapp.fontui." + which)
    cls = module.GroupsEditor if which == "groups" else module.KerningEditor
    original_init, original_close = cls.__init__, cls.close
    partial = []
    primary = ValueError("owned constructor failure")

    def init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        partial.append(self)
        if cleanup == "refuse":
            patch.setattr(self.preview.widget, "hide", lambda: False)
        raise primary

    def close(self):
        if cleanup == "interrupt":
            raise KeyboardInterrupt("owned constructor cleanup interruption")
        return original_close(self)

    with monkeypatch.context() as patch:
        patch.setattr(cls, "__init__", init)
        patch.setattr(cls, "close", close)
        with pytest.raises(BaseException) as caught:
            kerning_groups.show(real_fonts.fonts[0], real_fonts.env.parent)
        assert partial
        failure = caught.value
        pending, found = [failure], False
        while pending:
            item = pending.pop()
            found |= item is primary
            if isinstance(item, BaseExceptionGroup):
                pending.extend(item.exceptions)
        assert found, "Primary construction error must survive cleanup"
        if cleanup != "success":
            retained = kerning_groups._HANDLES[-1]
            real_fonts.owners.append(retained)
            assert partial[0] in retained._failed_owners
            assert partial[0].closed and partial[0].preview.closed
    assert (
        partial[0]._close_complete
        if cleanup == "success"
        else real_fonts.owners[-1]._release_now()
    )


def test_constructor_when_second_factory_cleanup_calls_first_editor_then_already_fenced(
    real_fonts, monkeypatch
):
    from fontlabapp.fontui import kerning_groups
    from fontlabapp.fontui.kerning import KerningEditor

    original_init, original_close = KerningEditor.__init__, KerningEditor.close
    attempts = []

    def init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        raise ValueError("second factory build")

    def close(self):
        c = kerning_groups._HANDLES[-1]
        attempts.append((c.groups.closed, c.groups.preview.closed, c.groups.on_apply))
        assert c.groups.closed and c.groups.preview.closed and c.groups.on_apply is None
        return original_close(self)

    with monkeypatch.context() as patch:
        patch.setattr(KerningEditor, "__init__", init)
        patch.setattr(KerningEditor, "close", close)
        with pytest.raises(BaseException):
            kerning_groups.show(real_fonts.fonts[0], real_fonts.env.parent)
        # Preserve any controller retained by the pre-wiring failure for cleanup.
        real_fonts.owners.extend(kerning_groups._HANDLES)
    assert attempts and all(
        closed and preview and callback is None
        for closed, preview, callback in attempts
    )


def test_constructor_when_layout_fails_then_outer_cleanup_observes_four_fences(
    real_fonts, monkeypatch
):
    from fontlabapp.fontui import kerning_groups

    layout = real_fonts.env.qt.QtGui.QVBoxLayout
    original_add = fq.FakeWidget.__getattr__
    original_close = real_fonts.env.qt.QtGui.QDialog.close
    observations = []

    def add(self, widget):
        c = kerning_groups._HANDLES[-1]
        if c.kerning is not None and widget is c.kerning.widget:
            raise ValueError("final layout attach")
        return original_add(self, "addWidget")(widget)

    def close(self):
        c = kerning_groups._HANDLES[-1]
        observations.append(
            tuple(
                o.closed
                for o in (c.groups, c.groups.preview, c.kerning, c.kerning.preview)
            )
        )
        return original_close(self)

    with monkeypatch.context() as patch:
        patch.setattr(layout, "addWidget", add, raising=False)
        patch.setattr(real_fonts.env.qt.QtGui.QDialog, "close", close)
        with pytest.raises(ValueError, match="final layout attach"):
            kerning_groups.show(real_fonts.fonts[0], real_fonts.env.parent)
    assert observations and all(all(row) for row in observations)


@pytest.mark.parametrize("route", ["finished", "destroyed"])
def test_terminal_when_fresh_then_fence_and_one_queued_release(real_fonts, route):
    c = window_for(real_fonts)
    owners = (c.groups, c.groups.preview, c.kerning, c.kerning.preview)
    getattr(c.owned.content, route).emit()
    c._finished()
    assert all(owner.closed for owner in owners) and len(real_fonts.env.queue) == 1
    real_fonts.env.queue.pop()()
    assert c._released
    c._finished()
    assert not real_fonts.env.queue


@pytest.mark.parametrize("fault", ["false", "exception", "interrupt"])
def test_outer_release_when_fails_then_children_acknowledged_and_owner_retained(
    real_fonts, monkeypatch, fault
):
    c = window_for(real_fonts)
    outer = c.owned
    owners = (c.groups, c.groups.preview, c.kerning, c.kerning.preview)

    def close():
        assert all(owner.closed and owner._close_complete for owner in owners)
        if fault == "false":
            return False
        if fault == "interrupt":
            raise KeyboardInterrupt("outer interruption")
        raise OSError("outer error")

    with monkeypatch.context() as patch:
        patch.setattr(outer, "close", close)
        if fault == "interrupt":
            with pytest.raises(KeyboardInterrupt):
                c._release_now()
        else:
            assert not c._release_now()
        assert c.owned is outer and not c._released
    assert c._release_now()


def test_cold_module_when_optional_imports_forbidden_then_inert(monkeypatch):
    import builtins
    import runpy
    from pathlib import Path

    original = builtins.__import__

    def guarded(name, *args, **kwargs):
        assert not name.startswith(("PythonQt", "fontlab_fontport", "fontlabapp")), name
        return original(name, *args, **kwargs)

    path = (
        Path(__file__).resolve().parents[1] / "src/fontlabapp/fontui/kerning_groups.py"
    )
    with monkeypatch.context() as patch:
        patch.setattr(builtins, "__import__", guarded)
        namespace = runpy.run_path(str(path))
    assert namespace["__all__"] == ("show",) and not namespace["_HANDLES"]


@pytest.mark.parametrize("which", ["preview", "sequence"])
def test_constructor_when_nested_preview_fails_then_exact_partial_child_recovered(
    real_fonts, monkeypatch, which
):
    from fontlabapp.fontui import kerning_groups

    module = importlib.import_module("fontlabapp.fontui." + which)
    cls = module.Preview if which == "preview" else module.Sequence
    original = cls.__init__
    partial = []

    def init(self, *args, **kwargs):
        original(self, *args, **kwargs)
        partial.append(self)
        patch.setattr(self.widget, "hide", lambda: False)
        raise ValueError("nested preview constructor")

    with monkeypatch.context() as patch:
        patch.setattr(cls, "__init__", init)
        with pytest.raises(BaseExceptionGroup):
            kerning_groups.show(real_fonts.fonts[0], real_fonts.env.parent)
        c = kerning_groups._HANDLES[-1]
        real_fonts.owners.append(c)
        assert partial[0] in c._failed_owners and partial[0].closed
        assert not partial[0]._close_complete
    assert c._release_now() and partial[0]._close_complete


@pytest.mark.parametrize("route", ["finished", "destroyed"])
def test_constructor_when_terminal_signal_during_second_factory_then_never_reopens(
    real_fonts, monkeypatch, route
):
    from fontlabapp.fontui import kerning_groups
    from fontlabapp.fontui.kerning import KerningEditor

    original, partial = KerningEditor.__init__, []

    def init(self, font, parent, callback):
        original(self, font, parent, callback)
        partial.append(self)
        getattr(parent, route).emit()

    with monkeypatch.context() as patch:
        patch.setattr(KerningEditor, "__init__", init)
        if route == "destroyed":
            with pytest.raises(RuntimeError):
                kerning_groups.show(real_fonts.fonts[0], real_fonts.env.parent)
            assert partial[0]._close_complete
        else:
            c = kerning_groups.show(real_fonts.fonts[0], real_fonts.env.parent)
            real_fonts.owners.append(c)
            assert c._closing and c.groups.closed and c.kerning.closed
            assert c.groups.on_apply is None
            assert not c.release()
            assert len(real_fonts.env.queue) == 1
            real_fonts.env.queue.pop()()
            assert c.release() and partial[0]._close_complete


def test_release_when_repeated_during_use_dispatch_then_only_one_deferred_cleanup(real_fonts, monkeypatch):
    c = window_for(real_fonts)
    choose(c, PAIR[0])
    pair(c)

    def inspect():
        assert c._busy == 1
        assert not c.release()
        assert not c.release()
        assert len(real_fonts.env.queue) == 1

    monkeypatch.setattr(c.kerning, "inspect", inspect)
    c.use("left")
    assert len(real_fonts.env.queue) == 1
    real_fonts.env.queue.pop()()
    assert c._released


def test_group_rename_when_stored_pair_selected_then_row_identity_and_value_draft_survive(real_fonts):
    c = window_for(real_fonts)
    choose(c, PAIR[0])
    c.kerning.pair_list.setCurrentRow(c.kerning.rows.index(PAIR))
    assert c.kerning.selected == PAIR
    c.kerning.value_control.setText("-27.5")
    c.groups.name_control.setText("public.kern1.Renamed")
    values = dict(real_fonts.expected[0].groups)
    values["public.kern1.Renamed"] = values.pop(PAIR[0])
    expect_groups(real_fonts, values)
    assert c.groups.edit("rename")
    assert c.kerning.selected == PAIR
    assert (c.kerning.left_control.text, c.kerning.right_control.text) == PAIR
    assert c.kerning.value_control.text == "-27.5"
    assert c.kerning.preview.run.glyphs[0].name is None
    assert len(real_fonts.group_writes) == 1 and not real_fonts.writes
    c.use_left.clicked.emit()
    assert c.kerning.left_control.text == "public.kern1.Renamed"
    assert c.kerning.right_control.text == PAIR[1] and c.kerning.value_control.text == "-27.5"


def test_use_when_selected_group_removed_externally_then_stage_exact_name_and_refuse_apply(real_fonts):
    c = window_for(real_fonts)
    choose(c, PAIR[0])
    pair(c, "A", "V", "0")
    del real_fonts.backends[0].font.groups[PAIR[0]]
    del real_fonts.expected[0].groups[PAIR[0]]
    c.use_left.clicked.emit()
    assert c.kerning.left_control.text == PAIR[0]
    assert c.kerning.preview.run.glyphs[0].name is None
    assert not c.kerning.edit("apply")
    c.groups.reload_button.clicked.emit()
    assert c.groups.selected is None
    assert not real_fonts.group_writes and not real_fonts.writes


@pytest.mark.parametrize("members", [None, 7])
def test_imported_mapping_when_members_not_iterable_then_both_editors_report_refusal(real_fonts, members):
    for font in (real_fonts.backends[0].font, real_fonts.expected[0]):
        font.groups[PAIR[0]] = members
    c = window_for(real_fonts)
    pair(c)
    assert not c.groups.editable and c.groups.diagnostic.text
    assert c.kerning.preview.run is None and c.kerning.diagnostic.text
    assert not c.groups.edit("delete") and not c.kerning.edit("apply")
    assert not real_fonts.group_writes and not real_fonts.writes


@pytest.mark.parametrize("callback_route", ["kerning_apply", "sequence_update"])
@pytest.mark.parametrize("terminal", ["release", "finished", "destroyed"])
def test_standalone_callback_when_release_requested_then_children_wait_for_return(real_fonts, callback_route, terminal):
    c = window_for(real_fonts)
    pair(c, "A", "V", "0")
    owners = (c.groups, c.groups.preview, c.kerning, c.kerning.preview)
    before_connections = [tuple(owner.connections) for owner in owners]
    observations = []

    def callback(*args):
        assert c._busy == 0, "This actual callback bypasses the new action guards"
        if terminal == "release":
            c.release()
        else:
            getattr(c.owned.content, terminal).emit()
        observations.append((
            [owner.closed for owner in owners],
            [tuple(owner.connections) for owner in owners],
            [(owner._hidden, owner._delete_scheduled, owner._close_complete) for owner in owners],
        ))

    if callback_route == "kerning_apply":
        c.kerning.on_apply = callback
        real_fonts.expected[0].kerning[("A", "V")] = 0.0
        assert c.kerning.edit("apply")
    else:
        c.kerning.preview.on_update = callback
        c.kerning.preview.refresh()
    assert observations == [([True] * 4, before_connections, [(False, False, False)] * 4)]
    assert len(real_fonts.writes) == int(callback_route == "kerning_apply")
    assert not real_fonts.group_writes
    assert c.font is real_fonts.fonts[0] and not c._released
    assert len(real_fonts.env.queue) == 1
    real_fonts.env.queue.pop()()
    assert c._released and all(owner._close_complete for owner in owners)
    assert c.release() and not real_fonts.env.queue


@pytest.mark.parametrize("boundary", ["scope", "child", "outer"])
@pytest.mark.parametrize("error_type", [KeyboardInterrupt, SystemExit])
def test_queued_cleanup_when_interrupted_then_contain_same_error_and_explicit_retry(real_fonts, monkeypatch, boundary, error_type):
    from fontlabapp.fontui import kerning_groups

    c = window_for(real_fonts)
    owners = (c.groups, c.groups.preview, c.kerning, c.kerning.preview)
    top = c.owned
    error = error_type("owned queued cleanup interruption")
    escaped = []

    def interrupt(*args):
        raise error

    with monkeypatch.context() as patch:
        if boundary == "scope":
            patch.setattr(c.use_right.clicked, "disconnect", interrupt)
        elif boundary == "child":
            patch.setattr(c.groups.preview.widget, "hide", interrupt)
        else:
            patch.setattr(top.widget, "close", interrupt)
        c.owned.content.finished.emit()
        assert len(real_fonts.env.queue) == 1
        try:
            real_fonts.env.queue.pop()()
        except BaseException as failure:
            escaped.append(failure)
        assert not escaped, "A Qt timer callback must contain BaseException"
        assert any(problem is error for problem in c.problems)
        assert all(owner.closed for owner in owners)
        assert c.groups.on_apply is None and c.kerning.on_apply is None
        assert c in kerning_groups._HANDLES and c.owned is top and not c._released
        assert not real_fonts.env.queue, "Failed cleanup must not retry automatically"
        assert not c.groups.edit("delete") and not c.kerning.edit("apply")
        assert not real_fonts.group_writes and not real_fonts.writes
    assert c.release() is False
    assert len(real_fonts.env.queue) == 1
    real_fonts.env.queue.pop()()
    assert c._released and all(owner._close_complete for owner in owners)
    assert c.release() and c not in kerning_groups._HANDLES
    assert any(problem is error for problem in c.problems)
