# this_file: src/fontlabapp/studios/kerning_batch/scale.py
# SPDX-License-Identifier: Apache-2.0
"""Kerning Batch Scale tab: Scriptmix Scale Values ("Scale Kerning").

What: multiply every explicit pair on the current master (default) or all
masters by 0–400 % (one decimal, default 100 %) and round to whole units,
halves away from zero. "Delete pairs that become 0" (on by default) deletes
pairs that scale to 0; an existing explicit zero is kept, as the original
did. The plan is the shared ``kerning.edit.model.scale_plan`` rule over the snapshot.
Apply writes exactly the listed set as one ``Kerning Batch: Scale kerning on
<masters>`` Undo step.
Used by ``fontlabapp.studios.kerning_batch`` (tab builder).
"""

from typing import Any

from .._kerning_ui import get, spin
from .rounding import ValuesPanel

TITLE = "Scale Kerning"


class ScalePanel(ValuesPanel):
    ACTION = "Scale"
    PARAMETER = "Scale by"
    ZERO = "Delete pairs that become 0"

    def make_parameter(self) -> Any:
        return spin(self.widget, 0.0, 400.0, 100.0, suffix=" %", decimals=1, slot=self.refresh)

    def value(self) -> float:
        return get(self.parameter.value)

    def explain(self) -> str:
        return f"Every value is multiplied by {self.value():g} % and rounded to whole units."

    SNAP = False


__all__ = ["TITLE", "ScalePanel"]
