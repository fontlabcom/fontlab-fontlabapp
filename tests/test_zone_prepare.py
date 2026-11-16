# this_file: tests/test_zone_prepare.py
"""Own the corrected native-shaped preparation boundary; never load FontLab."""

import copy
import json
from types import SimpleNamespace as NS

import pytest

import fontlabapp.metrics.zones.capture as capture_api
import fontlabapp.metrics.zones.prepare as api
from fontlabapp.metrics.zones.model import Editor
from fontlabapp.metrics.zones.capture_codec import DECLARATION


class Point:
    def __init__(self, x, y):
        self._x, self._y = x, y

    def x(self):
        return self._x

    def y(self):
        return self._y


class Guide:
    next_id = 100

    def __init__(self, x, y, width, name, metadata=None):
        Guide.next_id += 1
        self.id = Guide.next_id
        Guide.next_id += 1
        self.center = NS(id=Guide.next_id, position=Point(x, y))
        Guide.next_id += 1
        self.vector = NS(id=Guide.next_id)
        self.markers = ()
        self.extPosition, self.name = width, name
        self.metadata, self.isZone = copy.deepcopy(metadata or {}), True

    @property
    def centerPoint(self):
        return self.center.position

    def isHorizontal(self):
        return True


class Factory:
    def __init__(self):
        self.constructed = []

    def __call__(self, *args):
        if len(args) == 1:
            return args[0]
        angle, point, flags, style = args
        assert angle == 0 and flags == 1 and style == 7
        result = Guide(point.x(), point.y(), 0, "", {"default": True})
        self.constructed.append(result)
        return result

    @staticmethod
    def isGuideLine(value):
        return isinstance(value, Guide)


class Package:
    id, upm, master, masters = 31, 1000, "Regular", ("Thin", "Regular")

    def __init__(self):
        self.pool = {
            "Thin": [Guide(0, 650.5, 12.5, "caps", {"tags": ["thin"], "locked": True})],
            "Regular": [
                Guide(3, 500, 12, "", {"color": "red", "markers": [1, 2]}),
                Guide(3, 500, 12, "", {"color": "blue"}),
            ],
        }

    def setMaster(self, name, notify):
        assert notify is False
        self.master = name

    @property
    def guidelines(self):
        return self.pool[self.master]


@pytest.fixture
def host(monkeypatch):
    Guide.next_id = 100
    package, factory = Package(), Factory()
    state = NS(decode_calls=0, decoded=[], mutate=None, expire=False)

    def encode(identifier, upm, objects):
        assert identifier == 31 and upm == 1000
        records = [
            (
                float(g.centerPoint.x()),
                float(g.centerPoint.y()),
                float(g.extPosition),
                g.name,
                g.metadata,
            )
            for g in objects
        ]
        return json.dumps(records, sort_keys=True).encode()

    encode.__doc__ = "QByteArray " + DECLARATION

    def decode(buffer):
        state.decode_calls += 1
        result = [Guide(*values) for values in json.loads(buffer)]
        state.decoded.extend(result)
        if state.mutate:
            state.mutate(result)
        return result

    decode.__doc__ = "flObjects/Nothing getObjectsFromData(QByteArray *data)"
    native = NS(
        flModelProducer=NS(getClipboardData=encode, getObjectsFromData=decode),
        flGuideLine=factory,
        flSnaps=NS(SnapLineFlags={"Horizontal": 1}),
        SnapObjectsStyle={"gsCustomFontGuideline": 7},
        FontMetrics=lambda p, name: NS(
            xHeight=400 if p.master == "Thin" else 500,
            capsHeight=650 if p.master == "Thin" else 700,
        ),
    )
    qt = NS(QPointF=Point, QByteArray=lambda data: data)

    def module(name):
        return (
            native
            if name == "fontlab"
            else NS(QtCore=qt)
            if name == "PythonQt"
            else pytest.fail(name)
        )

    for target in (api, capture_api):
        monkeypatch.setattr(target, "_native", module)
        monkeypatch.setattr(target, "current_package", lambda expected_id=None: package)
        monkeypatch.setattr(target, "monotonic", lambda: 5.0 if state.expire else 1.0)
    before = capture_api.capture()
    return package, native, before, state


def test_complete_preparation_retains_metadata_edits_only_owned_copies_and_source(host):
    package, native, before, state = host
    editor = Editor(before.snapshot).add("Thin", "Bottom").remove("Regular", [0])
    result = api.prepare(before, editor.plan())
    assert [m.master for m in result.masters] == ["Thin", "Regular"]
    assert result.plan.before == before and capture_api.capture() == before
    source_ids = {identifier for frame in before.guides for identifier in frame.ids}
    prepared = [guide for master in result.masters for guide in master.guides]
    assert all(g.id not in source_ids for g in prepared)
    assert result.masters[0].guides[0].metadata == {"tags": ["thin"], "locked": True}
    assert result.masters[0].guides[0].centerPoint.y() == 650
    assert result.masters[0].guides[1].metadata == {"default": True}
    assert result.masters[0].guides[1].extPosition == -12
    assert result.masters[1].guides[0].metadata == {"color": "red", "markers": [1, 2]}
    assert result.masters[1].guides[0].centerPoint.x() == 3
    assert state.decode_calls == 4, (
        "One original decode and restoration witness for each retained row"
    )
    assert package.master == "Regular" and len(native.flGuideLine.constructed) == 1


def test_noop_never_accesses_native_or_allocates(monkeypatch, host):
    _, _, before, _ = host
    monkeypatch.setattr(api, "_native", lambda name: pytest.fail("No-op native access"))
    result = api.prepare(before, ())
    assert result.masters == ()


def test_deleted_all_rows_allocates_nothing_and_preserves_source(host):
    _, _, before, state = host
    editor = Editor(before.snapshot).stage("Regular", (), origins=())
    result = api.prepare(before, editor.plan())
    assert result.masters[0].guides == () and state.decode_calls == 0
    assert capture_api.capture() == before


def test_actual_source_identity_is_not_reused_by_prepared_objects(host):
    package, _, before, state = host
    state.mutate = lambda objects: setattr(objects[0], "id", package.pool["Thin"][0].id)
    with pytest.raises(ValueError, match="identity"):
        api.prepare(before, Editor(before.snapshot).add("Thin", "Bottom").plan())
    assert capture_api.capture() == before
