# this_file: tests/_widget_qt.py
"""A small PythonQt stand-in for the Widget Gallery tests (Issue 208).

What: ``make_qt()`` returns ``QtGui`` and ``QtCore`` namespaces whose names are
classes. A few classes behave like Qt where a demo or the fontlabapp.qt helper
under it depends on the behavior (line edits, combo boxes, sliders, an item
model with an integer spin box delegate, a calendar, a regular expression, a
timer whose single shots are collected). Every other name becomes a plain class
whose methods are recorded calls and whose signals are ``FakeSignal`` objects.
Use: ``qt = make_qt()``; read ``qt.shots`` and ``qt.painters`` after a run.
Why: the demos run the real fontlabapp.qt helpers over these classes, so the
tests check the demo's wiring and the helper's contract, not a mock's.
Offline behavior is not native FontLab proof.
"""

import re
import zlib
from types import SimpleNamespace
from typing import Any

from _demo_support import FakeSignal, Recorder

SIGNALS = frozenset(
    {
        "activated", "clicked", "closeEditor", "colorSelected", "currentIndexChanged",
        "currentPageChanged", "dataChanged", "dateChanged", "destroyed", "editingFinished",
        "editTextChanged", "finished", "selectionChanged", "textChanged", "timeout",
        "toggled", "topLevelChanged", "valueChanged",
    }
)
KNOWN_CONSTANTS = {"Key_Escape": 0x01000000}


class Signal(FakeSignal):
    """A signal that accepts Qt's optional connection-type argument."""

    def connect(self, slot: Any, *flags: Any) -> None:
        super().connect(slot)


class Constants(type):
    """Capitalized class attributes are stable integer enums; lowercase ones are calls."""

    def __getattr__(cls, name: str) -> Any:
        if name.startswith("__"):
            raise AttributeError(name)
        if name[0].islower():
            return Recorder()
        return KNOWN_CONSTANTS.get(name, zlib.crc32(name.encode()))


class Widget(metaclass=Constants):
    """Any Qt class: signals are FakeSignal, every other method is a recorded call."""

    def __init__(self, *args: Any) -> None:
        self.args = args

    def __getattr__(self, name: str) -> Any:
        if name.startswith("__"):
            raise AttributeError(name)
        item = Signal() if name in SIGNALS else Recorder()
        self.__dict__[name] = item
        return item

    @property
    def palette(self) -> Any:
        return self.__dict__.setdefault("_palette", Widget())


class Label(Widget):
    def __init__(self, *args: Any) -> None:
        super().__init__(*args)
        self.shown = args[0] if args and isinstance(args[0], str) else ""

    def setText(self, text: str) -> None:
        self.shown = text


class LineEdit(Widget):
    maxLength = 32767

    def __init__(self, *args: Any) -> None:
        super().__init__(*args)
        self.text_value, self.modified, self.base_keys = "", False, []

    @property
    def text(self) -> str:
        return self.text_value

    def setText(self, text: str) -> None:
        self.text_value = text
        self.textChanged.emit(text)

    def clear(self) -> None:
        self.setText("")

    def isModified(self) -> bool:
        return self.modified

    def setModified(self, flag: bool) -> None:
        self.modified = flag

    def keyPressEvent(self, event: Any) -> None:
        self.base_keys.append(event)

    def dropEvent(self, event: Any) -> None:
        """Deliver the dragged MIME payload through textChanged, as Qt's drop does."""
        self.textChanged.emit(event.args[2].payload)


class MimeData(Widget):
    payload = ""

    def setText(self, text: str) -> None:
        self.payload = text

    def setData(self, kind: str, data: Any) -> None:
        self.payload = data.args[0].decode("utf-8")


class DropEvent(Widget):
    def isAccepted(self) -> bool:
        return True


class CheckBox(Widget):
    def __init__(self, *args: Any) -> None:
        super().__init__(*args)
        self.state = False

    @property
    def checked(self) -> bool:
        return self.state

    def isChecked(self) -> bool:
        return self.state

    def setChecked(self, flag: bool) -> None:
        self.state = flag


class Combo(Widget):
    def __init__(self, *args: Any) -> None:
        super().__init__(*args)
        self.line, self.items, self.index = LineEdit(), [], 0

    @property
    def currentIndex(self) -> int:
        return self.index

    @property
    def currentText(self) -> str:
        return self.line.text_value

    def addItems(self, items: list) -> None:
        self.items += list(items)
        if self.items and not self.line.text_value:
            self.line.text_value = self.items[0]

    def lineEdit(self) -> LineEdit:
        return self.line

    def setEditText(self, text: str) -> None:
        self.line.text_value = text

    def setCurrentIndex(self, index: int) -> None:
        self.index = index


class AbstractSlider(Widget):
    def __init__(self, *args: Any) -> None:
        super().__init__(*args)
        self.number, self.limits = 0, (0, 99)

    def setRange(self, low: int, high: int) -> None:
        self.limits = (low, high)

    def setValue(self, number: int) -> None:
        if number != self.number:
            self.number = number
            self.valueChanged.emit(number)


class ProgressBar(Widget):
    def __init__(self, *args: Any) -> None:
        super().__init__(*args)
        self.limits, self.number = None, None

    def setRange(self, low: int, high: int) -> None:
        self.limits = (low, high)

    def setValue(self, number: int) -> None:
        self.number = number


class SpinBox(Widget):
    def __init__(self, *args: Any) -> None:
        super().__init__(*args)
        self.number, self.low, self.high = 0, 0, 99  # QSpinBox defaults

    @property
    def value(self) -> int:
        return self.number

    def setRange(self, low: int, high: int) -> None:
        self.low, self.high = low, high

    def setValue(self, number: int) -> None:
        self.number = min(max(number, self.low), self.high)  # Qt clamps to the range


class Effect(Recorder):
    """A recorded call that also changes the fake's state."""

    def __init__(self, effect: Any, result: Any = None) -> None:
        super().__init__(result)
        self.effect = effect

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        self.effect()
        return super().__call__(*args, **kwargs)


class MessageBox(Widget):
    """A box that is visible from show() until close(), as a real QMessageBox is."""

    Information = 1

    def __init__(self, *args: Any) -> None:
        super().__init__(*args)
        self.visible = False
        self.show = Effect(lambda: setattr(self, "visible", True))
        self.close = Effect(lambda: setattr(self, "visible", False), True)

    def isVisible(self) -> bool:
        return self.visible


class Index(Widget):
    def __init__(self, owner: Any, row: int, column: int) -> None:
        super().__init__(owner, row, column)
        self.owner, self.row_number, self.column_number = owner, row, column

    def isValid(self) -> bool:
        return True

    def model(self) -> Any:
        return self.owner

    def row(self) -> int:
        return self.row_number

    def column(self) -> int:
        return self.column_number


class StandardItem(Widget):
    def __init__(self, *args: Any) -> None:
        super().__init__(*args)
        self.stored = None

    def setData(self, value: Any, role: Any = None) -> None:
        self.stored = value


class StandardItemModel(Widget):
    def __init__(self, rows: int, columns: int, *args: Any) -> None:
        super().__init__(rows, columns, *args)
        self.cells = {}

    def setItem(self, row: int, column: int, item: StandardItem) -> None:
        self.cells[(row, column)] = item.stored

    def index(self, row: int, column: int) -> Index:
        return Index(self, row, column)

    def data(self, index: Index, role: Any = None) -> Any:
        return self.cells[(index.row(), index.column())]

    def setData(self, index: Index, value: Any, role: Any = None) -> bool:
        self.cells[(index.row(), index.column())] = value
        return True

    def blockSignals(self, flag: bool) -> bool:
        return False


class Completer(Widget):
    def __init__(self, *args: Any) -> None:
        super().__init__(*args)
        self.list_popup = Widget()

    def popup(self) -> Widget:
        return self.list_popup


class Rect(Widget):
    def __init__(self, width: int, height: int) -> None:
        super().__init__(width, height)
        self.size_pair = (width, height)

    def x(self) -> int:
        return 0

    def y(self) -> int:
        return 0

    def width(self) -> int:
        return self.size_pair[0]

    def height(self) -> int:
        return self.size_pair[1]


class Frame(Widget):
    def __init__(self, *args: Any) -> None:
        super().__init__(*args)
        self.base_resizes = []

    def contentsRect(self) -> Rect:
        return Rect(300, 80)

    def resizeEvent(self, event: Any) -> None:
        self.base_resizes.append(event)


class Calendar(Frame):
    yearShown, monthShown = 2026, 5
    minimumDate, maximumDate, selectedDate = "1900-01-01", "2100-12-31", "2026-05-17"

    def __init__(self, *args: Any) -> None:
        super().__init__(*args)
        self.locale = Locale()


class Color(Widget):
    def red(self) -> int:
        return self.args[0]

    def green(self) -> int:
        return self.args[1]

    def blue(self) -> int:
        return self.args[2]

    def alpha(self) -> int:
        return self.args[3]


class Locale(Widget):
    """A QLocale; matchingLocales returns two entries, as the official calendar needs."""

    def __init__(self, language: str = "English", country: str = "United States") -> None:
        super().__init__(language, country)
        self.language, self.country = language, country

    @classmethod
    def matchingLocales(cls, *flags: Any) -> list:
        return [cls("English", "United States"), cls("Polish", "Poland")]

    def nativeLanguageName(self) -> str:
        return self.language

    def nativeTerritoryName(self) -> str:
        return self.country


class RegExp(Widget):
    """A QRegExp over Python's re, enough for the pattern tester's evaluate."""

    def __init__(self, pattern: str = "") -> None:
        super().__init__(pattern)
        self.pattern, self.flags, self.match, self.error = pattern, re.IGNORECASE, None, ""

    def setPatternSyntax(self, syntax: Any) -> None:
        pass

    def setCaseSensitivity(self, sensitivity: Any) -> None:
        self.flags = re.IGNORECASE if sensitivity == Widget.CaseInsensitive else 0

    def setMinimal(self, flag: bool) -> None:
        pass

    def isValid(self) -> bool:
        try:
            re.compile(self.pattern)
        except re.error as error:
            self.error = str(error)
            return False
        return True

    def errorString(self) -> str:
        return self.error

    def indexIn(self, text: str) -> int:
        self.match = re.search(self.pattern, text, self.flags) if self.isValid() else None
        return self.match.start() if self.match else -1

    def matchedLength(self) -> int:
        return len(self.match.group(0))

    def captureCount(self) -> int:
        return self.match.re.groups

    def cap(self, index: int) -> str:
        return self.match.group(index)


def make_qt() -> SimpleNamespace:
    """Build one fake PythonQt; ``shots`` and ``painters`` collect what it was asked."""
    shots, painters = [], []

    class Timer(Widget):
        @staticmethod
        def singleShot(delay: int, call: Any) -> None:
            shots.append((delay, call))

    class Painter(Widget):
        def __init__(self, *args: Any) -> None:
            super().__init__(*args)
            painters.append(self)

    def namespace(known: dict) -> SimpleNamespace:
        classes = dict(known)

        class Names:
            def __getattr__(self, name: str) -> Any:
                if name.startswith("__"):
                    raise AttributeError(name)
                return classes.setdefault(name, type(name, (Widget,), {}))

        return Names()

    def model_index(*args: Any) -> Any:
        """QModelIndex(): an invalid index; QModelIndex(index): a copy of it."""
        return args[0] if args else Widget()

    gui = namespace(
        {
            "QCalendarWidget": Calendar, "QCheckBox": CheckBox, "QColor": Color, "QComboBox": Combo,
            "QCompleter": Completer,
            "QDial": AbstractSlider, "QDropEvent": DropEvent, "QFrame": Frame, "QLabel": Label,
            "QLineEdit": LineEdit, "QMessageBox": MessageBox, "QPainter": Painter, "QProgressBar": ProgressBar,
            "QScrollBar": AbstractSlider, "QSlider": AbstractSlider, "QSpinBox": SpinBox,
            "QStandardItem": StandardItem, "QStandardItemModel": StandardItemModel,
        }
    )
    core = namespace(
        {"QLocale": Locale, "QMimeData": MimeData, "QModelIndex": model_index, "QRegExp": RegExp, "QTimer": Timer}
    )
    return SimpleNamespace(QtGui=gui, QtCore=core, shots=shots, painters=painters)
