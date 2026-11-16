# this_file: src/fontlabapp/qt/images/viewer/io.py
# SPDX-License-Identifier: Apache-2.0
"""Own only the viewer's temporary files and the lifetime of one print painter."""
from pathlib import Path
from shutil import rmtree
from tempfile import mkdtemp
from typing import Any
from fontlabapp.qt.properties import value


class Workspace:
    """Keep the original temporary-PDF boundary without changing user settings."""
    def __init__(self, parent: Path | None = None) -> None:
        self.parent, self.path, self.identity = parent, None, None
        self.closed = False

    def verify(self) -> None:
        if self.path is not None:
            if self.path.is_symlink():
                raise RuntimeError("The reference viewer's temporary ownership changed.")
            if self.path.exists():
                stat = self.path.stat()
                if (stat.st_dev, stat.st_ino) != self.identity:
                    raise RuntimeError("The reference viewer's temporary ownership changed.")

    def directory(self) -> Path:
        if self.closed:
            raise RuntimeError("The reference viewer is closed.")
        if self.path is None:
            self.path = Path(mkdtemp(prefix="fontlab-reference-", dir=self.parent))
            stat = self.path.stat()
            self.identity = stat.st_dev, stat.st_ino
        self.verify()
        return self.path

    def destination(self, path: str) -> Path:
        root, target = self.directory().resolve(), Path(path).resolve()
        if target == root or not target.is_relative_to(root):
            raise ValueError("Choose a PDF file inside this viewer's temporary directory.")
        return target

    def close(self) -> None:
        self.verify()
        if self.path is not None and self.path.exists():
            rmtree(self.path)
        self.path, self.identity, self.closed = None, None, True


def render(part: int, image: Any, pixmap: Any, printer: Any, core: Any, gui: Any) -> None:
    """Preserve native-size part2 versus aspect-fit part3; always end QPainter."""
    painter = None
    try:
        painter = gui.QPainter(printer)
        if not value(painter, "isActive"):
            raise RuntimeError("Cannot start the selected printer.")
        if part == 2:
            painter.drawImage(core.QPoint(0, 0), image)
        else:
            rect = value(painter, "viewport")
            size = value(pixmap, "size")
            size.scale(value(rect, "size"), core.Qt.KeepAspectRatio)
            painter.setViewport(value(rect, "x"), value(rect, "y"), value(size, "width"), value(size, "height"))
            painter.setWindow(value(pixmap, "rect"))
            painter.drawPixmap(0, 0, pixmap)
    finally:
        if painter is not None and value(painter, "isActive"):
            painter.end()


def generated_image(gui: Any, width: int = 160, height: int = 120) -> Any:
    """Keep the source's optional geometric sample resource without auto-loading it."""
    result = gui.QImage(width, height, gui.QImage.Format_RGB32)
    result.fill(gui.QColor("#f0e5c8"))
    painter = gui.QPainter(result)
    try:
        for color, kind, bounds in (("#407eaa", "drawEllipse", (20, 15, 80, 80)), ("#ad6851", "drawRect", (80, 55, 60, 45))):
            painter.setBrush(gui.QColor(color))
            getattr(painter, kind)(*bounds)
    finally:
        painter.end()
    return result
