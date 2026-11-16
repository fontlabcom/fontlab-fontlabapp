# this_file: src/fontlabapp/plugins/startup.py
"""Preserve user startup bytes while installing App's one owned launch block."""

import os
from pathlib import Path
import re
import stat
import tempfile

BEGIN = b"# BEGIN fontlabapp.plugins (owned separator)"
END = b"# END fontlabapp.plugins"
HOOK = b"\n".join(
    (
        BEGIN,
        b"try:",
        b"    from fly.ap.plugins import install as _fontlab_plugins_install",
        b"    _fontlab_plugins_install()",
        b"except Exception as _fontlab_plugins_error:",
        b"    print('FontLab plugins startup:', _fontlab_plugins_error)",
        END,
        b"",
    )
)


def _updated(contents: bytes, remove: bool) -> bytes:
    """The extra newline preceding BEGIN is owned, including on a new file."""
    begins, ends = contents.count(BEGIN), contents.count(END)
    if begins or ends:
        block = re.search(
            rb"\r?\n"
            + re.escape(BEGIN)
            + rb"\r?\n.*?"
            + rb"(?m:^"
            + re.escape(END)
            + rb"\r?\n)",
            contents,
            re.DOTALL,
        )
        if begins != 1 or ends != 1 or block is None:
            raise ValueError(
                "Malformed or duplicate fontlabapp.plugins startup markers"
            )
        if not remove:
            return contents
        return contents[: block.start()] + contents[block.end() :]
    if remove:
        return contents
    newline = b"\r\n" if b"\r\n" in contents else b"\n"
    return contents + newline + HOOK.replace(b"\n", newline)


def update_startup(data_dir: str | Path, *, remove: bool = False) -> bool:
    """Add/remove only App's marked block; return whether bytes changed."""
    path = Path(data_dir) / "initScript.py"
    if path.is_symlink():
        raise ValueError("Refusing a symlink initScript.py")
    try:
        contents = path.read_bytes()
        mode = stat.S_IMODE(path.stat().st_mode)
    except FileNotFoundError:
        contents, mode = b"", 0o644
    updated = _updated(contents, remove)
    if updated == contents:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".initScript-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(updated)
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return True
