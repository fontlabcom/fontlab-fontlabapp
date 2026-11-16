# this_file: src/fontlabapp/core/legacy/vanilla.py
# SPDX-License-Identifier: Apache-2.0
"""Tombstone: ``VanillaSession`` left App.

App holds only general FontLab and Qt mechanics, so it keeps no Vanilla shim.
The session class now lives in Glyport.

Migrate:
    old: ``from fontlabapp.core.legacy.vanilla import VanillaSession``
    new: ``from fly.gp.ui.session import VanillaSession``

This module imports nothing, on purpose. A forwarding import would put an
App-to-Glyport edge back. The module remains importable for legacy alias identity. Accessing the removed
VanillaSession class fails and names its new home.
"""

def __getattr__(name: str):
    """Reject the removed session without importing Glyport or native APIs."""
    if name != "VanillaSession":
        raise AttributeError(name)
    raise ImportError(
        "VanillaSession moved to fontlab_glyport.ui.session; "
        "fontlabapp.core.legacy.vanilla holds no Vanilla code."
    )
