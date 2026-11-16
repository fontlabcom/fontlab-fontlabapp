# this_file: src/fontlabapp/fontui/_fontport.py
# SPDX-License-Identifier: Apache-2.0
"""One place that names the ``fontport`` extra when Fontport is missing."""

from collections.abc import Iterator
from contextlib import contextmanager


@contextmanager
def require_fontport(module: str) -> Iterator[None]:
    """Re-raise a missing ``fontlab_fontport`` as an ImportError naming the extra.

    Wrap the Fontport imports at the top of an editor module, so that both
    ``import fly.ap.fontui.kerning`` and a factory call give the same hint.
    Any other missing module passes through unchanged.
    """
    try:
        yield
    except ModuleNotFoundError as error:
        if (error.name or "").partition(".")[0] != "fontlab_fontport":
            raise
        raise ImportError(
            f"{module} needs fontlab-fontport; "
            "install it with: pip install 'fontlab-fontlabapp[fontport]'"
        ) from error
