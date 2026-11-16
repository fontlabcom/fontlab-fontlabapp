# this_file: examples/native_smoke.py
"""Run inside FontLab; no preference writes or open-font changes."""
from fly.ap import Application
app = Application(with_ui=True, with_preflib=False)
assert app.main and app.ui
print(app.versions.app_version, app.versions.qt_version)
