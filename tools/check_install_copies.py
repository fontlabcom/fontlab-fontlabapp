# this_file: tools/check_install_copies.py
"""List every workspace repo's install.vfpy with its sha256 and whether it matches this repo's copy.

Usage: python tools/check_install_copies.py [WORKSPACE_ROOT]   (default: parent of this repo)
Exit 1 if any copy differs. Read-only; skips FontRig and TypeRig-Icons (owner exclusion).
"""

import hashlib
import os
import sys
from pathlib import Path

EXCLUDED = {"FontRig", "TypeRig-Icons"}
HERE = Path(__file__).resolve().parents[1]


def copies(root: Path) -> dict[str, str]:
    """{repo name: sha256} for each root/<repo>/install.vfpy.

    Lists root with os.listdir and drops excluded names before any path to them exists,
    so FontRig and TypeRig-Icons are never stat'ed, scanned or opened.
    """
    found = {}
    for name in sorted(os.listdir(root)):
        if name in EXCLUDED:
            continue
        target = Path(root) / name / "install.vfpy"
        if target.is_file():
            found[name] = hashlib.sha256(target.read_bytes()).hexdigest()
    return found


def main(argv: list[str]) -> int:
    root = Path(argv[0]) if argv else HERE.parent
    found = copies(root)
    reference = hashlib.sha256((HERE / "install.vfpy").read_bytes()).hexdigest()
    for name, digest in found.items():
        print(f"{'same' if digest == reference else 'DIFF'}  {digest}  {name}")
    print(f"reference {reference}  ({HERE.name})")
    return int(any(digest != reference for digest in found.values()))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
