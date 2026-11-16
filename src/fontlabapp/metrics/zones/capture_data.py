# this_file: src/fontlabapp/metrics/zones/capture_data.py
# SPDX-License-Identifier: Apache-2.0
"""Immutable native zone capture values; no host or native handles."""

from dataclasses import dataclass

from fontlabapp.metrics.zones.data import Snapshot


@dataclass(frozen=True)
class GuideBuffer:
    """One master's ordered runtime ids and uninterpreted native guide buffer."""

    master: str
    ids: tuple[int, ...]
    data: bytes


@dataclass(frozen=True)
class Capture:
    """Raw zone values plus every master's complete serialized guide fence.

    Origin metadata holds the original whole guide payload, including its visible
    cells. A future writer must retain that provenance token while rebasing a
    separate fresh GuideBuffer fence; it must not call it a metadata-only codec.
    No native handles, widget, writer or history guarantee is provided here.
    """

    snapshot: Snapshot
    guides: tuple[GuideBuffer, ...]
