# this_file: src/fontlabapp/studios/font_identity/__init__.py
"""Font Identity: retained task routes in one owned studio."""


def show(*args, **kwargs):
    """Open the task studio lazily in FontLab."""
    from .app import show as open_studio

    return open_studio(*args, **kwargs)
