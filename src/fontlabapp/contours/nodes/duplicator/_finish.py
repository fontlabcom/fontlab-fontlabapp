# this_file: src/fontlabapp/contours/nodes/duplicator/_finish.py
# SPDX-License-Identifier: Apache-2.0
"""Bound owned recovery and final history notification by the caller's deadline.

No native call can be preempted here. Check immediately after it returns, and
never begin another mutation after the budget expires. A caller retains exact
owned node/contour handles when cleanup or history publication is incomplete.
"""

from typing import Any

from fontlabapp.contours.nodes.duplicator._capture import check
from fontlabapp.core.edit_guards import require_history_scope


def ready(deadline: float, errors: list) -> bool:
    """Keep timeout/interrupt evidence and refuse further native work."""
    try:
        check(deadline)
    except BaseException as error:
        errors.append(error)
        return False
    return True


def remove_owned(attempted: list, layers: list, deadline: float, errors: list) -> bool:
    """Remove only exact new identities, preserving failures and bounded work."""
    complete = True
    for contour, node in reversed(attempted):
        if not ready(deadline, errors):
            return False
        try:
            present = False
            for current in contour.nodes():
                check(deadline)
                if int(current.id) == int(node.id):
                    present = True
                    break
            check(deadline)
            if present:
                contour.removeOne(node)
            check(deadline)
        except BaseException as error:
            errors.append(error)
            complete = False
    for layer in layers:
        if not ready(deadline, errors):
            return False
        try:
            layer.changed()
            check(deadline)
            if layer.update() is False:
                raise RuntimeError("Recovery layer cache update failed.")
            check(deadline)
        except BaseException as error:
            errors.append(error)
            complete = False
    return complete


def _stamp(glyphs: list, stamp: Any, deadline: float, errors: list) -> bool:
    """Stamp only edited owners and check before/after each native setter."""
    for glyph in glyphs if stamp is not None else ():
        if not ready(deadline, errors):
            return False
        try:
            glyph.lastModified = stamp
            check(deadline)
        except BaseException as error:
            errors.append(error)
    return True


def notify(
    glyphs: list, items: list, stamp: Any, native: Any, deadline: float, errors: list
) -> bool:
    """Publish one history notification only with current safe scope and budget."""
    if not ready(deadline, errors):
        return False
    try:
        require_history_scope(glyphs, native=native)
        check(deadline)
    except BaseException as error:
        errors.append(error)
        return False
    if not _stamp(glyphs, stamp, deadline, errors) or not ready(deadline, errors):
        return False
    published = False
    try:
        notifier = native.flItems()
        check(deadline)
        notifier.notifyChangesApplied("Duplicate Nodes", items, True)
        published = True
        check(deadline)
    except BaseException as error:
        errors.append(error)
    _stamp(glyphs, stamp, deadline, errors)
    return published
