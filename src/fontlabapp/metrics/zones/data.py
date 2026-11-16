# this_file: src/fontlabapp/metrics/zones/data.py
# SPDX-License-Identifier: Apache-2.0
"""Immutable alignment-zone source values and explicit all-master edit batches.

These plain values own no native handles. Snapshots retain raw source numbers;
the editor rounds displayed/staged rows separately. A native adapter must compare
the complete raw baseline before applying any batch and qualify guideline metadata,
history, caches and persistence independently. These types confer no host proof.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Origin:
    """Opaque source-row identity and immutable hidden metadata from an adapter.

    The key identifies one guide within one master's captured domain. Metadata
    contains adapter-owned bytes, not a declared native serialization format.
    Capture must encode every hidden field it promises to preserve; these bytes
    travel unchanged through edits. New zones have no source origin. This value
    neither holds a native guide nor proves complete/native metadata capture.
    """

    key: str
    metadata: bytes


@dataclass(frozen=True)
class Zone:
    """One position, outward width and label; duplicate entries remain distinct."""

    position: float
    width: float
    name: str
    origin: Origin | None = None


@dataclass(frozen=True)
class Zones:
    """Separate top/bottom rows without merging repeated positions or labels."""

    top: tuple[Zone, ...] = ()
    bottom: tuple[Zone, ...] = ()


@dataclass(frozen=True)
class Master:
    """One source master's zones and the two metrics used by Add and Suggest."""

    name: str
    x_height: float
    caps_height: float
    zones: Zones = Zones()


@dataclass(frozen=True)
class Snapshot:
    """Ordered source domain; retain raw zones and the original current master."""

    package_id: int
    current_master: str
    masters: tuple[Master, ...]


@dataclass(frozen=True)
class Change:
    """One explicit changed master, with raw before and normalized after values."""

    master: str
    before: Zones
    after: Zones
