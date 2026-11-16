# this_file: Scripts/Widgets/Table Filter Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Read-only table filtering demonstration.

What: Open App's source/proxy panel on eight fixed sample rows.
Use: Run from Scripts, filter or sort the rows, limit dates, Refresh or Close.
Safety: The shared App demo reads no font or selection and writes no preferences,
Output, clipboard or files. Refresh reuses the same complete immutable table.
"""


def main() -> None:
    """Load and open the shared fixed-data demonstration."""
    from fly.ap.qt.tables.filter.model import show_demo

    show_demo()


if __name__ == "__main__":
    main()
