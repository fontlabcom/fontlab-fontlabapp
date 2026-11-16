# this_file: tests/_fake_gui.py
"""Minimal PythonQt-style widget fakes: ``text`` and ``rowCount`` are properties, signals record slots."""

from types import SimpleNamespace as NS


class Signal:
    def __init__(self):
        self.slots = []

    def emit(self, *args):
        for slot in list(self.slots):
            slot(*args)


class Widget:
    def __init__(self, *args, **kw):
        self.args = args
        self.text = args[0] if args and isinstance(args[0], str) else ""
        self.checked = False
        self.plain = ""
        self.clicked, self.textChanged, self.toggled, self.cellChanged = Signal(), Signal(), Signal(), Signal()
        self.children = []

    def __getattr__(self, name):
        if name.startswith("__") or name in ("master_names", "lab_refresh_preview", "lab_check_target"):
            raise AttributeError(name)
        return lambda *a, **k: None

    def setChecked(self, value):
        self.checked = bool(value)

    def isChecked(self):
        return self.checked

    def setText(self, value):
        self.text = value

    def setPlainText(self, value):
        self.plain = value

    def addWidget(self, widget, *rest):
        self.children.append(widget)

    def toPlainText(self):
        return self.plain


class Item:
    def __init__(self, text=""):
        self._text = text

    def text(self):
        return self._text

    def setText(self, value):
        self._text = value


class Table(Widget):
    def __init__(self, rows=0, cols=0):
        super().__init__()
        self.rowCount, self.cells, self.items = rows, {}, {}

    def setRowCount(self, count):
        self.rowCount = count

    def setCellWidget(self, row, col, widget):
        self.cells[row, col] = widget

    def cellWidget(self, row, col):
        return self.cells[row, col]

    def setItem(self, row, col, item):
        self.items[row, col] = item

    def item(self, row, col):
        return self.items[row, col]


class Dialog(Widget):
    def __init__(self, parent=None):
        super().__init__()


def gui():
    return NS(
        QDialog=Dialog, QVBoxLayout=Widget, QHBoxLayout=Widget, QLabel=Widget, QLineEdit=Widget,
        QPlainTextEdit=Widget, QCheckBox=Widget, QPushButton=Widget, QTableWidget=Table,
        QTableWidgetItem=Item, QComboBox=Widget, QFormLayout=Widget, QTransform=Widget,
    )
