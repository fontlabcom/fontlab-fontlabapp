# this_file: tests/test_zone_capture.py
"""Exercise actual adapter capture against owned native-shaped data only."""

import json
from types import SimpleNamespace as NS

import pytest

import fontlabapp.metrics.zones.capture as api
from fontlabapp.metrics.zones.capture_codec import DECLARATION


class Package:
    """No clipboard, files, history, glyphs or updates exist on this double."""

    id, upm, master, masters = 31, 1000, "Regular", ("Thin", "Regular")

    def __init__(self):
        self.switches = []
        self.pool = {
            "Thin": [guide(1, 650.5, 12.5, "cap", tags=["first"], locked=True)],
            "Regular": [
                guide(2, 500.5, 12.5, "", tags=["a"]),
                guide(3, 500.5, 12.5, "", tags=["b"]),
                guide(4, 0, -15, "base"),
                guide(5, 300, 0, "other", zone=False),
            ],
        }

    def setMaster(self, name, notify):
        assert notify is False, "Capture must not notify the UI"
        self.switches.append(name)
        self.master = name

    @property
    def guidelines(self):
        return self.pool[self.master]


def guide(identifier, y, width, name, *, zone=True, horizontal=True, **metadata):
    return NS(
        id=identifier,
        isZone=zone,
        isHorizontal=lambda: horizontal,
        centerPoint=NS(y=lambda: y),
        extPosition=width,
        name=name,
        metadata=metadata,
    )


def qualified(method):
    """Model the corrected native declaration on an owned callable only."""
    method.__doc__ = "QByteArray " + DECLARATION
    return method


@pytest.fixture
def host(monkeypatch):
    package = Package()
    calls, after = [], []

    def encode(identifier, upm, objects):
        assert identifier == 31 and upm == 1000
        calls.append((package.master, tuple(g.id for g in objects)))
        payload = json.dumps(
            [
                (g.id, g.centerPoint.y(), g.extPosition, g.name, g.metadata)
                for g in objects
            ],
            sort_keys=True,
        ).encode()
        if after:
            after.pop(0)()
        return NS(data=lambda: payload)

    native = NS(
        flModelProducer=NS(getClipboardData=qualified(encode)),
        FontMetrics=lambda p, name: NS(
            xHeight=400.5 if p.master == "Thin" else 500.5,
            capsHeight=650.5 if p.master == "Thin" else 700.5,
        ),
    )
    monkeypatch.setattr(
        api,
        "current_package",
        lambda expected_id=None: package if expected_id in (None, 31) else None,
    )
    monkeypatch.setattr(
        api, "_native", lambda name: native if name == "fontlab" else pytest.fail(name)
    )
    monkeypatch.setattr(api, "monotonic", lambda: 1.0)
    return package, native, calls, after


def test_all_master_capture_preserves_raw_values_order_duplicates_and_full_payload(
    host,
):
    package, _, calls, _ = host
    result = api.capture()
    assert (
        result.snapshot.package_id == 31 and result.snapshot.current_master == "Regular"
    )
    assert [m.name for m in result.snapshot.masters] == ["Thin", "Regular"]
    assert result.snapshot.masters[0].zones.top[0].position == 650.5
    assert result.snapshot.masters[0].zones.top[0].width == 12.5
    duplicates = result.snapshot.masters[1].zones.top
    assert duplicates[0].name == duplicates[1].name == ""
    assert duplicates[0].origin != duplicates[1].origin
    assert (
        b'"a"' in duplicates[0].origin.metadata
        and b'"b"' in duplicates[1].origin.metadata
    )
    assert b'"locked": true' in result.snapshot.masters[0].zones.top[0].origin.metadata
    assert result.snapshot.masters[1].zones.bottom[0].width == 15
    assert b'"other"' in result.guides[1].data, "Fence every nonzone guide too"
    assert package.master == "Regular" and package.switches[-1] == "Regular"
    assert len(calls) == 12, "Two complete passes; whole-master plus each zone"


def test_complete_guide_payload_change_between_passes_refuses_capture(host):
    package, _, _, after = host
    after.extend(
        [lambda: None] * 5
        + [lambda: package.pool["Regular"][-1].metadata.update(color="changed")]
    )
    with pytest.raises(ValueError, match="changed"):
        api.capture()
    assert package.master == "Regular"


@pytest.mark.parametrize(
    "attribute, value",
    [
        ("masters", ()),
        ("masters", ("Regular", "Regular")),
        ("master", "foreign"),
        ("id", True),
        ("upm", 0),
    ],
)
def test_invalid_source_domain_refuses_before_switching(host, attribute, value):
    package, _, _, _ = host
    setattr(package, attribute, value)
    with pytest.raises(ValueError):
        api.capture()
    assert not package.switches


def test_no_font_and_foreign_expected_package_are_refused(host, monkeypatch):
    with pytest.raises(ValueError, match="font"):
        api.capture(999)
    monkeypatch.setattr(api, "current_package", lambda expected_id=None: None)
    with pytest.raises(ValueError, match="font"):
        api.capture()


def test_serializer_failure_restores_starting_master(host):
    package, native, _, _ = host

    def fail(*args):
        raise RuntimeError("owned serialization failure")

    native.flModelProducer.getClipboardData = qualified(fail)
    with pytest.raises(RuntimeError, match="serialization"):
        api.capture()
    assert package.master == "Regular"


def test_deadline_during_scan_restores_master_and_returns_no_prefix(host, monkeypatch):
    package, _, _, _ = host
    ticks = iter([1.0, 1.0, 1.0, 4.0])
    monkeypatch.setattr(api, "monotonic", lambda: next(ticks, 4.0))
    with pytest.raises(TimeoutError):
        api.capture()
    assert package.master == "Regular"


@pytest.mark.parametrize(
    "width,name,position,top",
    [
        (0, "asc", 0, True),
        (0, "caps", 0, True),
        (0, "T: 0", 0, True),
        (0, "base", 500, False),
        (0, "B: 500", 500, False),
        (0, "", 500, False),
        (0, "custom", 500, True),
        (0, "custom", -10, False),
        (0.000001, "B", 500, False),
    ],
)
def test_native_zero_width_kind_rule_keeps_native_name_semantics(
    host, width, name, position, top
):
    package, _, _, _ = host
    package.pool["Thin"] = [guide(1, position, width, name)]
    zones = api.capture().snapshot.masters[0].zones
    assert bool(zones.top) is top and bool(zones.bottom) is not top


def test_nonhorizontal_zone_is_not_an_editable_alignment_zone_but_remains_fenced(host):
    package, _, _, _ = host
    package.pool["Thin"] = [guide(1, 650, 12, "angled", horizontal=False)]
    result = api.capture()
    assert (
        not result.snapshot.masters[0].zones.top and b"angled" in result.guides[0].data
    )
