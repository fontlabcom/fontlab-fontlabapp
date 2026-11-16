# this_file: tests/test_zone_capture_codec.py
"""Refuse the legacy binding before any source master switch or native call."""

import pytest
from test_zone_capture import host as shared_host

import fontlabapp.metrics.zones.capture as api


@pytest.fixture
def host(monkeypatch):
    return shared_host.__wrapped__(monkeypatch)


@pytest.mark.parametrize(
    "doc", [None, "", "QByteArray getClipboardData(objId package_id, QList<flObject>)"]
)
def test_legacy_unqualified_signature_never_calls_native_or_switches_master(host, doc):
    package, native, calls, _ = host

    def legacy(*args):
        pytest.fail("Legacy native serializer must never be invoked")

    legacy.__doc__ = doc
    native.flModelProducer.getClipboardData = legacy
    with pytest.raises(RuntimeError, match="three-argument"):
        api.capture()
    assert not package.switches and not calls


def test_exact_corrected_signature_can_capture_with_owned_serializer(host):
    _, _, _, _ = host
    result = api.capture()
    assert result.snapshot.package_id == 31


def test_immutable_bytes_return_is_retained_without_qbytearray_conversion(host):
    _, native, _, _ = host

    def wrong(*args):
        return b"wrong profile"

    wrong.__doc__ = (
        "QByteArray getClipboardData(objId package_id, double upm, QList<flObject>)"
    )
    native.flModelProducer.getClipboardData = wrong
    result = api.capture()
    assert all(item.data == b"wrong profile" for item in result.guides)
