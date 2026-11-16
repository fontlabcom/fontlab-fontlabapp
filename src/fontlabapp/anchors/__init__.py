# this_file: src/fontlabapp/anchors/__init__.py
"""anchors domain helpers; children load only when explicitly imported.

Legacy compatibility: missing attribute reads and model writes/deletes forward to
fontlabapp.anchors.inspect.model. The implementation loads on first access as a normal,
separate module; this package retains its own children and metadata."""

from fontlabapp._legacy import configure_facade as _configure_facade

_configure_facade(__name__, "fontlabapp.anchors.inspect.model")
