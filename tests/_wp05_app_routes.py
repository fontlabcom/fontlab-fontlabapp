# this_file: tests/_wp05_app_routes.py
"""Locate the App route modules that the behaviour tests execute."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TITLES = {
    'Transform', 'Slant', 'Smart Slant', 'Rotate Selection',
    'Reflect Horizontally', 'Reflect Vertically', 'Align And Distribute',
    'Interpolated Nudge', 'Overlap Nodes', 'Superaligner',
    'Add Extremes', 'Correct Contour Direction', 'Delete Close Points',
    'Delete Duplicate Contours', 'Delete Small Contours', 'Fix Zero Handles',
    'Optimize Start Points', 'Remove Overlap', 'Round Coordinates',
    'Curve All Straights', 'Straighten All Curves', 'Straighten Short Curves',
    'Retract Handles', 'Simplify Selected Nodes',
}


def route_path(title: str) -> Path:
    base = ROOT / 'src/fontlabapp/fontui'
    if title == 'Superaligner':
        return base / 'superaligner.py'
    return base / 'outline_routes' / (title.lower().replace(' ', '_') + '.py')
