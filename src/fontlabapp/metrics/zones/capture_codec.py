# this_file: src/fontlabapp/metrics/zones/capture_codec.py
# SPDX-License-Identifier: Apache-2.0
"""Require the corrected native serializer contract; keep payloads uninterpreted.

The legacy three-argument macro verifies two arguments and then indexes a third.
Do not call that profile. A corrected declaration is a necessary API gate, not
proof of the compiled implementation or payload preservation. Native acceptance
must still qualify both before this adapter is used in a practical workflow.
"""

from collections.abc import Callable
from typing import Any

DECLARATION = "getClipboardData(objId package_id, double upm, QList<flObject>)"


def serializer(native: Any) -> Callable:
    """Refuse old/missing ABI metadata before any master switch or native call."""
    method = native.flModelProducer.getClipboardData
    if DECLARATION not in (method.__doc__ or ""):
        raise RuntimeError(
            "Zone capture requires the corrected native three-argument guide serializer; "
            "the legacy binding must not be called."
        )
    return method


def encode(method: Callable, identifier: int, upm: float, guides: tuple) -> bytes:
    """Keep immutable bytes or QByteArray.data() without touching the clipboard.

    Conversion through PythonQt can return a QByteArray wrapper or immutable
    Python bytes. Both represent the same native payload; do not decode either.
    """
    value = method(identifier, upm, list(guides))
    result = value if type(value) is bytes else value.data()
    if type(result) is not bytes or not result:
        raise ValueError("Native guide serialization returned no immutable bytes.")
    return result
