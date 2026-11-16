# this_file: src/fontlabapp/plugins/plugin.py
"""Host-independent identity shared by plugmix plugin kinds."""

from typing import ClassVar


class Plugin:
    """A named, discoverable plugin; subclasses define their own host contract."""

    kind: ClassVar[str] = ""
    name: ClassVar[str] = ""
    title: ClassVar[str] = ""
    since: ClassVar[str] = ""
    requires: ClassVar[str] = ""
