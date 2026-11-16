# this_file: src/fontlabapp/masters/__init__.py
"""masters domain helpers; children load only when explicitly imported.

Legacy compatibility: missing attribute reads and model writes/deletes forward to
fontlabapp.masters.inspect.model. The implementation loads on first access as a normal,
separate module; this package retains its own children and metadata."""

from fontlabapp._legacy import configure_facade as _configure_facade

_configure_facade(__name__, "fontlabapp.masters.inspect.model")
