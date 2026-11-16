# this_file: src/fontlabapp/studios/outline_doctor/checks.py
# SPDX-License-Identifier: Apache-2.0
"""The Outline Doctor check registry: one ``Check`` per absorbed Scriptmix script.

What: ``CHECKS`` lists the fourteen checks in tab order with their options,
thresholds and default master scope exactly as the scripts had them.
Structural fixes (they add or remove nodes or contours) default to All
masters with Keep masters compatible ticked; Retract Handles and Round
Coordinates default to the current master; Curve All Straights and
Straighten All Curves default to All masters; the three reports are read-only.
Why: ``session`` and ``tabs`` look checks up here; ``by_key`` and ``in_tab``
are the only lookups.
"""

from . import fixes, reports
from .model import Check, Option

TABS = ("Scan", "Handles", "Points", "Segments", "Overlaps")

CHECKS: tuple[Check, ...] = (
    Check("open_contours", "Open Contours", "Scan", "List", "Open Contours.py", reports.plan_open,
          scope="all", whole_font=True, columns=("Contour", "Nodes", "Gap")),
    Check("near_miss", "Close But No Cigar", "Scan", "List", "Close But No Cigar.py", reports.plan_near,
          columns=("Where", "Check", "Value")),
    Check("dangerous_offcurves", "Dangerous Offcurves", "Scan", "List", "Dangerous Offcurves.py",
          reports.plan_dangerous, scope="all", whole_font=True,
          options=(Option("threshold", "Closer than", "spin", reports.THRESHOLD, 0.0, 10.0, 2, " units"),),
          columns=("Contour", "Handle", "Distance")),
    Check("fix_zero_handles", "Fix Zero Handles", "Handles", "fix zero handles", "Fix Zero Handles.py",
          fixes.plan_zero, fixes.write_zero, fixes.verify_zero, structural=True, scope="all",
          options=(Option("pull", "Pull single handles out to ⅓ (changes the curve slightly)", "tick", False),),
          bases=True, columns=("Contour", "Found", "Fix")),
    Check("retract_handles", "Retract Handles", "Handles", "retract handles", "Retract Handles.py",
          fixes.plan_retract, fixes.write_moves, fixes.verify_moves,
          options=(Option("selected", "Only at selected on-curve nodes", "tick", False),),
          bases=True, columns=("Item", "Handles", "Fix")),
    Check("add_extremes", "Add Extremes", "Points", "add extremes", "Add Extremes.py",
          fixes.plan_extremes, fixes.write_extremes, fixes.verify_counts, structural=True, scope="all",
          bases=True, columns=("Contour", "Now", "Adds")),
    Check("delete_close_points", "Delete Close Points", "Points", "delete close points", "Delete Close Points.py",
          fixes.plan_close, fixes.write_close, fixes.verify_close, structural=True, scope="all", bases=True,
          options=(Option("distance", "Distance up to", "spin", 5.0, 0.01, 1000.0, 2, " units"),),
          columns=("Contour", "Segments", "Fix")),
    Check("round_coordinates", "Round Coordinates", "Points", "round coordinates", "Round Coordinates.py",
          fixes.plan_round, fixes.write_round, fixes.verify_round,
          options=(Option("grid", "Grid", "spin", 1, 1, 100, 0, " units"),
                   Option("anchors", "Anchors", "tick", True),
                   Option("offsets", "Component offsets", "tick", True)),
          bases=True, columns=("Item", "Now", "After")),
    Check("straighten_short_curves", "Straighten Short Curves", "Segments", "straighten short curves",
          "Straighten Short Curves.py", fixes.plan_short, fixes.write_lines, fixes.verify_counts,
          structural=True, scope="all",
          options=(Option("chord", "Chord up to", "spin", 60, 1, 2000, 0, " units"),
                   Option("handles", "Handles within", "spin", 2.0, 0, 50, 1, " units")),
          bases=True, columns=("Contour", "Curves", "Fix")),
    Check("curve_all_straights", "Curve All Straights", "Segments", "curve all straights", "Curve All Straights.py",
          fixes.plan_curve_all, fixes.write_curves, fixes.verify_curves, scope="all", bases=True,
          columns=("Contour", "Segments", "Fix")),
    Check("straighten_all_curves", "Straighten All Curves", "Segments", "straighten all curves",
          "Straighten All Curves.py", fixes.plan_straighten_all, fixes.write_lines, fixes.verify_counts,
          scope="all", bases=True, columns=("Contour", "Segments", "Fix")),
    Check("remove_overlap", "Remove Overlap", "Overlaps", "remove overlap", "Remove Overlap.py",
          fixes.plan_overlap, fixes.write_overlap, fixes.verify_overlap, structural=True, scope="all",
          bases=True, advise=fixes.advise_overlap, columns=("Shape", "Now", "After")),
    Check("delete_small_contours", "Delete Small Contours", "Overlaps", "delete small contours",
          "Delete Small Contours.py", fixes.plan_small, fixes.write_removals, fixes.verify_removals,
          structural=True, scope="all",
          options=(Option("threshold", "Smaller than", "spin", 400, 1, 1000000, 0, " units²"),),
          bases=True, columns=("Contour", "Area", "Fix")),
    Check("delete_duplicate_contours", "Delete Duplicate Contours", "Overlaps", "delete duplicate contours",
          "Delete Duplicate Contours.py", fixes.plan_duplicates, fixes.write_removals, fixes.verify_removals,
          structural=True, scope="all",
          options=(Option("tolerance", "Tolerance", "spin", 0.5, 0, 20, 1, " units"),),
          bases=True, columns=("Contour", "Same as", "Fix")),
)  # fmt: skip


def by_key(key: str) -> Check:
    for check in CHECKS:
        if check.key == key:
            return check
    raise KeyError(f"No Outline Doctor check named {key}.")


def in_tab(tab: str) -> tuple[Check, ...]:
    return tuple(check for check in CHECKS if check.tab == tab)
