# this_file: src/fontlabapp/qt/images/resources.py
"""Host-free resource lookup and injected Qt image rendering.

Qt is supplied explicitly; macOS PDF conversion invokes sips only on request.
Resource folder policy and Cocoa value types belong to caller adapters.
"""

import os
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

IMAGE_TYPES = ("pdf", "tiff", "tif", "png", "svg", "icns", "jpg", "jpeg", "gif")
RASTER_TYPES = ("tiff", "tif", "png", "jpg", "jpeg", "gif")
SIPS = "/usr/bin/sips"
SIPS_TIMEOUT = 5.0


def find_image(
    name: str | None,
    resources: str | Path | None,
    *,
    extensions: tuple[str, ...] = IMAGE_TYPES,
    folders: tuple[str, ...] = ("",),
) -> Path | None:
    """Find a resource using the caller's ordered folders and extensions."""
    if not name or resources is None:
        return None
    root = Path(resources)
    names = [name] if Path(name).suffix else [f"{name}.{kind}" for kind in extensions]
    for folder in folders:
        for candidate in names:
            path = root / folder / candidate
            if path.is_file():
                return path
    return None


def retina_variant(
    path: str | Path, *, raster_types: tuple[str, ...] = RASTER_TYPES
) -> Path | None:
    """Find a raster's ``name@2x`` sibling using ordered format candidates."""
    path = Path(path)
    if path.suffix.lower().lstrip(".") not in raster_types:
        return None
    for kind in (path.suffix.lstrip("."), *raster_types):
        candidate = path.with_name(f"{path.stem}@2x.{kind}")
        if candidate.is_file():
            return candidate
    return None


def run_sips(
    argv: list[str],
    run: Callable,
    *,
    executable: str = SIPS,
    timeout: float = SIPS_TIMEOUT,
) -> Any:
    """Run the bounded macOS image converter, returning None on launch/timeout errors."""
    try:
        return run([executable, *argv], capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return None


def pdf_dimensions(
    path: str | Path,
    *,
    run: Callable = subprocess.run,
    executable: str = SIPS,
    timeout: float = SIPS_TIMEOUT,
) -> tuple[float, float] | None:
    """The first page's size in points, or None when sips cannot read it."""
    done = run_sips(
        ["-g", "pixelWidth", "-g", "pixelHeight", str(path)],
        run,
        executable=executable,
        timeout=timeout,
    )
    if done is None or done.returncode:
        return None
    facts = dict(
        line.strip().split(": ", 1) for line in done.stdout.splitlines() if ": " in line
    )
    try:
        return float(facts["pixelWidth"]), float(facts["pixelHeight"])
    except (KeyError, ValueError):
        return None


def render_pdf(
    path: str | Path,
    width: int,
    height: int,
    *,
    run: Callable = subprocess.run,
    executable: str = SIPS,
    timeout: float = SIPS_TIMEOUT,
    scratch_prefix: str = "fontlabapp-pdf-",
) -> bytes | None:
    """PNG bytes of the page rasterised at ``width`` x ``height`` pixels."""
    handle, out = tempfile.mkstemp(prefix=scratch_prefix, suffix=".png")
    os.close(handle)
    try:
        argv = [
            "-s",
            "format",
            "png",
            "-z",
            str(height),
            str(width),
            str(path),
            "--out",
            out,
        ]
        done = run_sips(argv, run, executable=executable, timeout=timeout)
        if done is None or done.returncode:
            return None
        return Path(out).read_bytes() or None
    finally:
        Path(out).unlink(missing_ok=True)


def raster_image(qt: Any, path: str | Path, width: int, height: int) -> Any:
    """Read the smallest frame covering the target, or the largest available."""
    path = Path(path)
    gui, core = qt.QtGui, qt.QtCore
    # The smallest frame covering the target, else the largest frame.
    reader, frames = gui.QImageReader(str(path)), []
    for index in range(max(1, reader.imageCount())):
        reader.jumpToImage(index)
        size = reader.size()
        covers = size.width() >= width and size.height() >= height
        frames.append(
            (
                not covers,
                size.width() * size.height() * (1 if covers else -1),
                index,
            )
        )
    best = min(frames)[2]
    reader = gui.QImageReader(str(path))
    reader.jumpToImage(best)
    image = reader.read()
    if image.isNull():
        raise OSError(f"cannot read image {path.name}: {reader.errorString()}")
    if (image.width(), image.height()) != (width, height):
        image = image.scaled(
            core.QSize(width, height),
            core.Qt.IgnoreAspectRatio,
            core.Qt.SmoothTransformation,
        )
    return image


def svg_image(qt: Any, renderer: Callable[[], Any], width: int, height: int) -> Any:
    """Render onto transparent pixels and always end the owned painter."""
    gui, core = qt.QtGui, qt.QtCore
    image = gui.QImage(
        core.QSize(width, height), gui.QImage.Format_ARGB32_Premultiplied
    )
    image.fill(0)
    painter = gui.QPainter(image)
    try:
        renderer().render(painter)
    finally:
        painter.end()
    return image
