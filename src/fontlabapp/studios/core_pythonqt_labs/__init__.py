# this_file: src/fontlabapp/studios/core_pythonqt_labs/__init__.py
# SPDX-License-Identifier: Apache-2.0
"""Public studio route for the nine shared PythonQt labs."""


def show(lab_id, *, profile=None, parent=None, font=None, package=None):
    """Open a lab, optionally selecting an exact original lesson title."""
    import fontlabapp.fontui

    return fontlabapp.fontui.core_pythonqt_lab(lab_id, profile=profile, parent=parent,
                                   font=font, package=package)
