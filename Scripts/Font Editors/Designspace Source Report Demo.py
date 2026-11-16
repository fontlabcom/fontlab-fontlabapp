# this_file: Scripts/Font Editors/Designspace Source Report Demo.py
# SPDX-License-Identifier: Apache-2.0
"""What: Print metrics and structural comparisons for designspace UFO sources.

Use: Call main(path), or run this script with a .designspace path in Python.
Safety: Reads source files without changing fonts or opening a native window.
Discrete axes, multi-axis maps and anisotropic locations are unsupported.
"""

from pathlib import Path


def main(path: str | Path | None = None) -> None:
    """Print a complete read-only report, propagating unreadable-source errors."""
    from fly.ap.fontui.designspace_sources import compare, render

    if path is None:
        import argparse

        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument("path", type=Path, help="Designspace file with UFO sources")
        path = parser.parse_args().path
    print(render(compare(path)))


if __name__ == "__main__":
    main()
