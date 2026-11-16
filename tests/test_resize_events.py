# this_file: tests/test_resize_events.py
"""Resize forwarding preserves ordering, live owner lookup and failure identity."""

import subprocess
import sys
from types import SimpleNamespace

import pytest
from fontlabapp.qt.events.resize import resize_event_handler


def scenario(stage=None, mutation=None, dimensions=(123, 456)):
    """Build an owned event whose stages and owner changes are observable."""
    trace = []
    error = RuntimeError("owned resize failure")

    def step(name, value=None):
        trace.append(name)
        if stage == name:
            raise error
        if mutation == name:
            widget.owner = replacement
        return value

    def callback(width, height):
        step(("callback", width, height))

    replacement = SimpleNamespace(resized=lambda w, h: step(("replacement", w, h)))
    owner = SimpleNamespace(resized=callback)
    widget = SimpleNamespace(owner=owner)

    class Base:
        def resizeEvent(self, event):
            return step("base", 99)

    def get_owner(widget):
        return step("owner", widget.owner)

    size = SimpleNamespace(
        width=lambda: step("width", dimensions[0]),
        height=lambda: step("height", dimensions[1]),
    )
    event = SimpleNamespace(size=lambda: step("size", size))
    handler = resize_event_handler(Base, get_owner, "resized")
    return handler, widget, event, trace, error


@pytest.mark.parametrize("dimensions", [(0, 0), (1, 2), (-1, -2), (2**32, 2**33)])
def test_resize_when_present_then_base_and_live_owner_precede_dimensions(dimensions):
    handler, widget, event, trace, _ = scenario(dimensions=dimensions)
    assert handler(widget, event) is None
    assert trace == [
        "base",
        "owner",
        "size",
        "owner",
        "width",
        "height",
        ("callback", *dimensions),
    ]


def test_resize_when_no_owner_then_size_is_not_read():
    handler, widget, event, trace, _ = scenario()
    widget.owner = None
    assert handler(widget, event) is None
    assert trace == ["base", "owner"]


@pytest.mark.parametrize(
    "stage", ["base", "owner", "size", "width", "height", ("callback", 123, 456)]
)
def test_resize_when_stage_fails_then_same_exception_stops_remaining_work(stage):
    handler, widget, event, trace, error = scenario(stage=stage)
    with pytest.raises(RuntimeError) as observed:
        handler(widget, event)
    assert observed.value is error
    assert trace[-1] == stage


@pytest.mark.parametrize("mutation", ["base", "size", "width", "height"])
def test_resize_when_owner_changes_then_keep_original_lookup_timing(mutation):
    handler, widget, event, trace, _ = scenario(mutation=mutation)
    handler(widget, event)
    expected = "replacement" if mutation in {"base", "size"} else "callback"
    assert trace[-1] == (expected, 123, 456)


def test_resize_when_owner_removed_during_size_then_attribute_error_is_preserved():
    handler, widget, event, trace, _ = scenario()

    def size():
        widget.owner = None
        return SimpleNamespace(width=lambda: pytest.fail("width read after owner lost"))

    event.size = size
    with pytest.raises(AttributeError):
        handler(widget, event)
    assert trace == ["base", "owner", "owner"]


def test_resize_when_repeated_then_does_not_cache_owner_or_size():
    handler, widget, event, trace, _ = scenario()
    handler(widget, event)
    widget.owner = None
    handler(widget, event)
    assert trace[-2:] == ["base", "owner"]
    assert trace.count("base") == 2 and trace.count("size") == 1


def test_resize_when_imported_then_no_host_or_foreign_packages_load():
    subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; from fontlabapp.qt.events.resize import resize_event_handler; assert not {'PythonQt', 'fontlab', 'fontlab_glyport', 'fontlab_fontport', 'PySide6', 'PySide2'}.intersection(sys.modules)",
        ],
        check=True,
    )
