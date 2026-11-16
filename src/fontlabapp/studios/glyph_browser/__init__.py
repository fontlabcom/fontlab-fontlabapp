# this_file: src/fontlabapp/studios/glyph_browser/__init__.py
"""WP07 glyph browser studio; Qt loads only when shown."""
from typing import Any


def show(**kwargs: Any) -> Any:
    from .app import show as open_studio
    return open_studio(**kwargs)


__all__ = ["show"]
