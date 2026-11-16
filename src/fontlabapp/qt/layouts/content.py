# this_file: src/fontlabapp/qt/layouts/content.py
"""Fit an injected child to a container's current contents rectangle.

No Qt import is needed. Call on the UI thread with objects that expose the
usual rectangle accessors and ``setGeometry``. Values and exceptions pass
through unchanged; title/style and child layout remain with the caller.
"""

from typing import Any


def fit_contents(container: Any, content: Any) -> tuple[Any, Any]:
    """Set child geometry once; return width/height only after success."""
    rect = container.contentsRect()
    frame = (rect.x(), rect.y(), rect.width(), rect.height())
    content.setGeometry(*frame)
    return frame[2:]
