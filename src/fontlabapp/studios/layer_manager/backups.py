# this_file: src/fontlabapp/studios/layer_manager/backups.py
# SPDX-License-Identifier: Apache-2.0
"""Backups tab: back up, restore and promote layers.

Three modes, one absorbed Scriptmix script each (Scripts/Masters/):
"Back up" (Duplicate Current Layer), "Restore" (Restore Backup Layer)
and "Use as master" (Use Layer As Master). All three work on the backup
layers that the App's shared naming rule recognises, so they share one
tab. Each mode lists its plan first and writes one labelled Undo step.
"""

from ._duplicate import DuplicatePanel
from ._modes import ModesPanel
from ._restore import RestorePanel
from ._use_master import UseMasterPanel


class BackupsPanel(ModesPanel):
    MODES = (
        ("Back up", DuplicatePanel),
        ("Restore", RestorePanel),
        ("Use as master", UseMasterPanel),
    )


__all__ = ["BackupsPanel"]
