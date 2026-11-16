# this_file: tests/test_zone_origins.py
"""Keep distinct owned guide records through the actual zone staging workflow."""

from dataclasses import replace

import pytest

from fontlabapp.metrics.zones.model import Editor, parse_rows
from fontlabapp.metrics.zones.data import Master, Origin, Snapshot, Zone, Zones
from fontlabapp.metrics.zones.editor import check_result


def editor():
    """Two visibly identical zones carry different immutable owned metadata."""
    return Editor(
        Snapshot(
            31,
            "Regular",
            (
                Master("Thin", 400, 650),
                Master(
                    "Regular",
                    500,
                    700,
                    Zones(
                        (
                            Zone(
                                500.5,
                                -12.5,
                                "",
                                Origin("a", b"tags=first;locked=1;color=red"),
                            ),
                            Zone(
                                500.5,
                                -12.5,
                                "",
                                Origin("b", b"tags=second;locked=0;color=blue"),
                            ),
                        )
                    ),
                ),
            ),
        )
    )


def test_duplicate_visible_rows_keep_distinct_origins_after_edit_remove_and_add():
    initial = editor()
    rows = initial.rows("Regular")
    identities = initial.origins("Regular")
    assert rows[0] == rows[1] and identities[0] != identities[1]
    edited = initial.stage(
        "Regular", (("Bottom", 10, 14, "renamed"), rows[1]), origins=identities
    )
    assert edited.zones("Regular").bottom[0].origin == identities[0]
    assert edited.zones("Regular").top[0].origin == identities[1]
    removed = initial.remove("Regular", [0])
    assert removed.origins("Regular") == (identities[1],)
    added = removed.add("Regular", "Top")
    assert set(added.origins("Regular")) == {identities[1], None}
    assert (
        initial.pending() == ()
        and initial.snapshot.masters[1].zones.top[0].width == -12.5
    )


def test_explicit_row_reordering_and_normalized_noop_preserve_metadata():
    initial = editor()
    proposed = initial.stage(
        "Regular",
        reversed(initial.rows("Regular")),
        origins=reversed(initial.origins("Regular")),
    )
    assert proposed.plan() == ()
    assert proposed.origins("Regular") == initial.origins("Regular")
    with pytest.raises(ValueError, match="identit"):
        initial.stage("Regular", initial.rows("Regular"))


@pytest.mark.parametrize(
    "origins",
    [
        (),
        (None,),
        (None, None, None),
        (Origin("foreign", b"x"), None),
        (Origin("a", b"tampered"), None),
    ],
)
def test_stale_missing_or_foreign_row_origins_refuse_complete_stage(origins):
    initial = editor().add("Thin", "Bottom")
    with pytest.raises(ValueError):
        initial.stage("Regular", initial.rows("Regular"), origins=origins)
    assert initial.pending() == ("Thin",)


@pytest.mark.parametrize(
    "origin",
    [
        "bad",
        Origin("", b"x"),
        Origin("bad\x00", b"x"),
        Origin("\ud800", b"x"),
        Origin("ok", bytearray(b"mutable")),
    ],
)
def test_invalid_origin_is_rejected_before_staging(origin):
    with pytest.raises(ValueError, match="row 1"):
        parse_rows((("Top", 500, 12, ""),), origins=(origin,))


def test_duplicate_origin_cannot_alias_two_guides_even_across_kinds():
    origin = Origin("owned", b"metadata")
    with pytest.raises(ValueError, match="identity"):
        parse_rows(
            (("Top", 500, 12, ""), ("Bottom", 0, 12, "")), origins=(origin, origin)
        )


def test_suggest_retains_exact_match_metadata_once_and_replaces_other_rows():
    origin = Origin("existing", b"keep tags locks and color")
    initial = Editor(
        Snapshot(
            31,
            "Regular",
            (
                Master(
                    "Regular",
                    500,
                    700,
                    Zones(
                        (
                            Zone(500, 12, "x-height", origin),
                            Zone(600, 15, "old", Origin("old", b"old")),
                        )
                    ),
                ),
            ),
        )
    )
    result = initial.suggest("Regular", (-10, 512), (-15, 714))
    assert origin in result.origins("Regular")
    assert Origin("old", b"old") not in result.origins("Regular")
    assert result.origins("Regular").count(None) == 2
    assert result.plan()[0].before == initial.snapshot.masters[0].zones
    assert result.suggest("Regular", (-10, 512), (-15, 714)).plan() == result.plan()


def test_complete_writer_result_refuses_metadata_or_identity_loss():
    initial = editor().add("Regular", "Bottom")
    changes = initial.plan()
    after = replace(
        initial.snapshot,
        masters=(
            initial.snapshot.masters[0],
            replace(initial.snapshot.masters[1], zones=changes[0].after),
        ),
    )
    check_result(initial.snapshot, changes, after)
    top = after.masters[1].zones.top
    for replacement in (
        None,
        Origin(top[0].origin.key, b"lost tags"),
        Origin("foreign", top[0].origin.metadata),
    ):
        changed = replace(
            after.masters[1],
            zones=replace(
                after.masters[1].zones,
                top=(replace(top[0], origin=replacement), *top[1:]),
            ),
        )
        with pytest.raises(ValueError, match="differs"):
            check_result(
                initial.snapshot,
                changes,
                replace(after, masters=(after.masters[0], changed)),
            )


def test_staged_metadata_cannot_be_injected_and_origin_source_is_immutable():
    initial = editor()
    altered = replace(
        initial.snapshot.masters[1].zones.top[0], origin=Origin("a", b"new")
    )
    with pytest.raises(ValueError, match="identity"):
        Editor(initial.snapshot, (("Regular", Zones((altered,))),))


@pytest.mark.parametrize("origin", ["bad", Origin("", b"x"), Origin("same", [])])
def test_raw_snapshot_rejects_invalid_origin_at_the_source_boundary(origin):
    with pytest.raises(ValueError, match="identity"):
        Editor(
            Snapshot(
                31, "R", (Master("R", 500, 700, Zones((Zone(500, 12, "", origin),))),)
            )
        )
