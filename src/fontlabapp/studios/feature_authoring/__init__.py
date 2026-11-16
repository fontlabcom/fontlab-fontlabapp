# this_file: src/fontlabapp/studios/feature_authoring/__init__.py
# SPDX-License-Identifier: Apache-2.0
"""Consolidated native feature tool; imports stay lazy."""

def show(*args, **kwargs):
    """Open the owned studio and optionally select its original task tab."""
    from .app import show as launch
    return launch(*args, **kwargs)
