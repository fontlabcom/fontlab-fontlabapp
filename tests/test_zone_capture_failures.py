# this_file: tests/test_zone_capture_failures.py
"""Reject unstable native domains and incomplete guide captures without prefixes."""

from types import SimpleNamespace as NS

import pytest
from test_zone_capture import guide, qualified, host as shared_host

import fontlabapp.metrics.zones.capture as api


@pytest.fixture
def host(monkeypatch):
    """Use the same owned native-shaped fixture without plugin registration."""
    return shared_host.__wrapped__(monkeypatch)


@pytest.mark.parametrize("data", [b"", "not bytes", bytearray(b"mutable")])
def test_unreadable_native_buffer_refuses_and_restores(host, data):
    package, native, _, _ = host
    native.flModelProducer.getClipboardData = qualified(
        lambda *a: NS(data=lambda: data)
    )
    with pytest.raises(ValueError, match="immutable bytes"):
        api.capture()
    assert package.master == "Regular"


@pytest.mark.parametrize("ids", [(0,), (True,), (None,), (1, 1)])
def test_bad_or_duplicate_guide_ids_refuse_before_serializing_that_master(host, ids):
    package, _, calls, _ = host
    package.pool["Thin"] = [guide(i, 500, 12, "test") for i in ids]
    with pytest.raises(ValueError, match="guide identity"):
        api.capture()
    assert not calls and package.master == "Regular"


def test_declined_native_master_switch_is_not_a_valid_snapshot(host):
    package, _, _, _ = host
    package.setMaster = lambda *a: None
    with pytest.raises(ValueError, match="switch"):
        api.capture()
    assert package.master == "Regular"


def test_failed_starting_master_restoration_is_reported_explicitly(host):
    package, _, _, _ = host
    switch = package.setMaster

    def fail_restore(name, notify):
        if name != "Regular":
            switch(name, notify)

    package.setMaster = fail_restore
    with pytest.raises(RuntimeError, match="restore"):
        api.capture()


@pytest.mark.parametrize("boundary", [1, 2])
def test_font_closed_at_either_registry_fence_refuses(host, monkeypatch, boundary):
    package, _, _, _ = host
    calls = 0

    def current(expected_id=None):
        nonlocal calls
        calls += 1
        return None if calls == boundary + 1 else package

    monkeypatch.setattr(api, "current_package", current)
    with pytest.raises(ValueError, match="changed"):
        api.capture()
    assert package.master == "Regular"


@pytest.mark.parametrize("boundary", [1, 2])
def test_master_domain_changed_at_either_registry_fence_refuses(
    host, monkeypatch, boundary
):
    package, _, _, _ = host
    calls = 0

    def current(expected_id=None):
        nonlocal calls
        calls += 1
        if calls == boundary + 1:
            package.masters = ("Regular", "Thin")
        return package

    monkeypatch.setattr(api, "current_package", current)
    with pytest.raises(ValueError, match="changed"):
        api.capture()
    assert package.master == "Regular"


def test_wrong_zone_flag_profile_is_not_silently_treated_as_true(host):
    package, _, _, _ = host
    package.pool["Thin"][0].isZone = lambda: True
    with pytest.raises(ValueError, match="zone flag"):
        api.capture()
    assert package.master == "Regular"


@pytest.mark.parametrize(
    "attribute,value",
    [("masters", "Regular"), ("masters", (12,)), ("upm", True), ("upm", float("inf"))],
)
def test_bad_native_domain_types_refuse_before_any_master_switch(
    host, attribute, value
):
    package, _, _, _ = host
    setattr(package, attribute, value)
    with pytest.raises(ValueError):
        api.capture()
    assert package.switches == []


def test_deadline_after_second_full_scan_still_returns_no_capture(host, monkeypatch):
    package, _, _, after = host
    expired = False

    def expire():
        nonlocal expired
        expired = True

    after.extend([lambda: None] * 11 + [expire])
    monkeypatch.setattr(api, "monotonic", lambda: 4.0 if expired else 1.0)
    with pytest.raises(TimeoutError):
        api.capture()
    assert package.master == "Regular"


def test_empty_guide_lists_still_have_complete_master_buffer_fences(host):
    package, _, calls, _ = host
    package.pool = {name: [] for name in package.masters}
    result = api.capture()
    assert len(result.guides) == 2 and all(item.data == b"[]" for item in result.guides)
    assert all(not m.zones.top and not m.zones.bottom for m in result.snapshot.masters)
    assert len(calls) == 4 and package.master == "Regular"


@pytest.mark.parametrize("identifier", [0, -1, True, "31", 31.0])
def test_invalid_expected_identity_is_refused_before_native_access(
    host, monkeypatch, identifier
):
    monkeypatch.setattr(
        api,
        "current_package",
        lambda *a: pytest.fail("Invalid input reached native lookup"),
    )
    with pytest.raises(ValueError, match="identity"):
        api.capture(identifier)


@pytest.mark.parametrize("suffix", [": alternate", "#alternate", "@alternate"])
def test_exact_master_metrics_do_not_alias_layer_suffix_prefixes(host, suffix):
    package, native, _, _ = host
    alternate = "Regular" + suffix
    package.masters = ("Regular", alternate)
    package.pool[alternate] = [guide(9, 800, 12, "cap")]
    values = {"Regular": (500, 700), alternate: (600, 800)}

    def metrics(p, layer_name):
        # Independent owned reproduction of the inspected native name lookup.
        prefix = layer_name
        for marker in (":", "#", "@"):
            prefix = prefix.split(marker)[0]
        selected = prefix if prefix in values else p.master
        x_height, caps_height = values[selected]
        return NS(xHeight=x_height, capsHeight=caps_height)

    native.FontMetrics = metrics
    result = api.capture()
    assert [(m.name, m.x_height, m.caps_height) for m in result.snapshot.masters] == [
        ("Regular", 500, 700),
        (alternate, 600, 800),
    ]
    assert package.master == "Regular"
