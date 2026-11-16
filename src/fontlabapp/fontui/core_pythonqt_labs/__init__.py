# this_file: src/fontlabapp/fontui/core_pythonqt_labs/__init__.py
# SPDX-License-Identifier: Apache-2.0
"""Nine PythonQt labs composed from their distinct original lesson profiles."""


def show(lab_id, *, profile=None, parent=None, font=None, package=None):
    """Open a lab; optionally select the exact original menu's profile title."""
    from .app import show as open_lab

    return open_lab(lab_id, profile=profile, parent=parent, font=font, package=package)
