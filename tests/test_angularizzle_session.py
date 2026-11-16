# this_file: tests/test_angularizzle_session.py
"""Exercise original Angularizzle single/batch actions with owned snapshots."""

from dataclasses import replace
from itertools import pairwise

import pytest

from fontlabapp.contours.angularizzle.model import Path, Segment
from fontlabapp.contours.angularizzle.session import (
    Capture,
    LayerSnapshot,
    Session,
    parse_plane,
)


def layer(key="A", size=160):
    points = ((0, 0), (size, 0), (size, size), (0, size), (0, 0))
    path = Path(tuple(Segment((a, b)) for a, b in pairwise(points)))
    return LayerSnapshot(key, (path,), 2)


class OwnedBackend:
    def __init__(self, layers):
        self.source = Capture("owned-font/selection", tuple(layers))
        self.current = {item.key: item for item in layers}
        self.calls = []
        self.stale = False
        self.failure = False

    def capture(self, deadline):
        return self.source

    def check(self, source, *, selection, deadline):
        self.calls.append(("check", selection))
        if self.stale:
            raise ValueError("Source changed")

    def apply(self, source, before, after, *, restore, deadline):
        self.calls.append(("apply", restore))
        assert all(self.current[row.key] == row for row in before)
        if self.failure:
            raise RuntimeError("Owned write refused before mutation")
        self.current.update((row.key, row) for row in after)


def test_single_process_restarts_original_paths_and_cancel_restores_paths_not_source_color():
    backend = OwnedBackend((layer(),))
    session = Session(backend)
    assert session.batch is False and not session.closed
    session.process("80", True)
    first = backend.current["A"]
    assert first.color == 8 and first.paths != layer().paths
    assert not session.closed, "Single source action keeps the panel open for preview"
    session.process("40", True)
    second = backend.current["A"]
    fresh = OwnedBackend((layer(),))
    Session(fresh).process("40", True)
    assert second == fresh.current["A"], "Repeated preview must use opening geometry"
    session.cancel()
    assert session.closed and backend.current["A"].paths == layer().paths
    assert backend.current["A"].color == 8, "Original Cancel restores paths only"
    assert backend.calls[-1] == ("apply", True), (
        "Backend restores retained native originals"
    )


def test_batch_processes_all_selected_records_then_closes_and_cancel_before_process_is_safe():
    backend = OwnedBackend((layer("A"), layer("B", 200)))
    session = Session(backend)
    assert session.batch
    session.process("80", True)
    assert session.closed and all(row.color == 8 for row in backend.current.values())
    untouched = OwnedBackend((layer("A"), layer("B")))
    Session(untouched).cancel()
    assert not any(row[0] == "apply" for row in untouched.calls)


def test_duplicate_batch_records_reprocess_previous_result_in_original_order():
    backend = OwnedBackend((layer(), layer()))
    session = Session(backend)
    session.process("80", True)
    one = OwnedBackend((layer(),))
    Session(one).process("80", True)
    two = OwnedBackend((one.current["A"],))
    Session(two).process("80", True)
    assert backend.current == two.current
    assert session.batch and session.closed


def test_empty_selection_and_conflicting_duplicate_snapshots_are_refused():
    with pytest.raises(ValueError, match="Select"):
        Session(OwnedBackend(()))
    with pytest.raises(ValueError, match="conflicting"):
        Session(OwnedBackend((layer(), layer(size=200))))


@pytest.mark.parametrize("text", ["", " 80", "+80", "-1", "0", "4", "2.5", "x", "²"])
def test_invalid_plane_has_no_partial_native_action(text):
    backend = OwnedBackend((layer(),))
    session = Session(backend)
    with pytest.raises(ValueError, match="plane"):
        session.process(text, True)
    assert backend.current["A"] == layer()
    assert not any(row[0] == "apply" for row in backend.calls)


def test_unicode_decimal_and_minimum_plane_follow_source_integer_input():
    assert parse_plane("٨٠") == 80
    assert parse_plane("5") == 5


def test_failed_or_stale_write_keeps_session_open_and_baseline_unchanged():
    backend = OwnedBackend((layer(),))
    session = Session(backend)
    backend.failure = True
    with pytest.raises(RuntimeError):
        session.process("80", True)
    assert not session.closed and session.processed is False
    assert backend.current["A"] == layer()
    backend.failure = False
    session.process("80", True)
    backend.stale = True
    with pytest.raises(ValueError):
        session.cancel()
    assert not session.closed and backend.current["A"].paths != layer().paths


def test_close_keeps_processed_geometry_and_retained_actions_are_inert():
    backend = OwnedBackend((layer(),))
    session = Session(backend)
    session.process("80", True)
    session.close()
    before = dict(backend.current)
    calls = tuple(backend.calls)
    session.process("garbage", True)
    session.cancel()
    session.close()
    assert backend.current == before and tuple(backend.calls) == calls


def test_open_paths_are_untouched_when_no_closed_path_is_sampled_but_color_changes():
    original = replace(layer(), paths=(replace(layer().paths[0], closed=False),))
    backend = OwnedBackend((original,))
    Session(backend).process("80", True)
    assert backend.current["A"].paths == original.paths
    assert backend.current["A"].color == 8


def test_mixed_open_closed_source_replaces_all_paths_and_exposes_collapsed_counter():
    original = replace(
        layer(), paths=(*layer().paths, replace(layer().paths[0], closed=False))
    )
    backend = OwnedBackend((original,))
    Session(backend).process("80", False)
    assert backend.current["A"].paths == (Path(()),), (
        "Keep the original explicit empty path result"
    )


def test_batch_failure_never_publishes_a_prefix_or_closes_panel():
    invalid = replace(layer("B"), paths=(Path((Segment(((1, 1), (1, 1))),)),))
    backend = OwnedBackend((layer("A"), invalid))
    session = Session(backend)
    with pytest.raises(ValueError, match="coincident"):
        session.process("80", True)
    assert not session.closed and backend.current["A"] == layer("A")
    assert not any(row[0] == "apply" for row in backend.calls)


def test_single_selected_input_and_first_layer_target_remain_distinct():
    target, selected = layer("first", 160), layer("selected", 200)
    backend = OwnedBackend((target,))
    backend.source = Capture("owned", (target,), (selected,))
    session = Session(backend)
    session.process("80", True)
    source_control = OwnedBackend((selected,))
    Session(source_control).process("80", True)
    assert backend.current["first"].paths == source_control.current["selected"].paths
    assert "selected" not in backend.current, (
        "Process writes first target, not selected input"
    )
    session.cancel()
    assert backend.current["first"].paths == target.paths, (
        "Repair Cancel to restore the actual overwritten target"
    )
    bad = OwnedBackend((target,))
    bad.source = Capture("owned", (target,), ())
    with pytest.raises(ValueError, match="input"):
        Session(bad)
