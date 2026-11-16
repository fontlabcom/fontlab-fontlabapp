# this_file: src/fontlabapp/studios/encoding_order/__init__.py
"""Encoding and Order: retained task routes in one owned studio."""


def show(*args, **kwargs):
    """Open the task studio lazily in FontLab."""
    from .app import show as open_studio

    return open_studio(*args, **kwargs)
