# this_file: tests/test_bound_slot_guard.py
"""FontLab's PythonQt silently ignores ``signal.connect(widget.close)``.

PySide6 accepts a signal connected to a bound C++ Qt method, so only a source
check catches it. Wrap the call in a lambda or a Python function instead.
"""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ("src", "Scripts", "examples")
QT_SLOTS = frozenset(
    "close hide show showNormal showMaximized showMinimized showFullScreen accept reject done "
    "deleteLater setFocus clear update repaint raise_ lower setVisible setHidden setEnabled "
    "setDisabled setChecked toggle click animateClick selectAll copy cut paste undo redo "
    "open exec exec_ activateWindow setFocus stop start quit".split()
)


def bound_slots(tree: ast.AST) -> list[tuple[int, str]]:
    """Return (line, text) of ``x.connect(<expr>.<qt-slot>)`` where ``<expr>`` is not bare self.

    Bare ``self.<slot>`` is exempt on purpose: many of our classes define their own Python ``close``/``show``.
    If ``self`` is itself a QWidget subclass that does not override the method, PythonQt ignores that connect
    too, and this scan cannot tell; use a lambda or a plain function there.
    """
    found = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "connect"):
            continue
        for arg in node.args:
            if not (isinstance(arg, ast.Attribute) and arg.attr in QT_SLOTS):
                continue
            if isinstance(arg.value, ast.Name) and arg.value.id in {"self", "cls"}:
                continue  # a Python method of our own class
            found.append((node.lineno, ast.unparse(arg)))
    return found


def test_bound_slots_when_connect_gets_qt_method_then_detected():
    tree = ast.parse("a.clicked.connect(dialog.close)\nb.x.connect( self.view.hide )\nc.connect(self.close)\nd.connect(lambda: w.close())")
    assert bound_slots(tree) == [(1, "dialog.close"), (2, "self.view.hide")]


def test_sources_when_scanned_then_no_signal_connects_to_bound_qt_slot():
    offenders = []
    for top in SOURCES:
        for path in sorted((ROOT / top).rglob("*.py")):
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except SyntaxError:
                continue
            offenders += [f"{path.relative_to(ROOT)}:{line}: {text}" for line, text in bound_slots(tree)]
    assert not offenders, "PythonQt ignores connect(<widget>.<slot>); use a lambda:\n" + "\n".join(offenders)
