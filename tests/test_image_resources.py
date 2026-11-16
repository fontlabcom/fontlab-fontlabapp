# this_file: tests/test_image_resources.py
"""Generic resource lookup and subprocess rendering need no host imports."""

import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import fontlabapp.qt.images.resources as resources
import pytest


def test_lookup_when_ordered_folders_and_extensions_then_first_existing_file(tmp_path):
    (tmp_path / "localized").mkdir()
    for name in ("icon.png", "icon.pdf", "localized/icon.pdf"):
        (tmp_path / name).write_bytes(b"image")
    assert resources.find_image("icon", tmp_path) == tmp_path / "icon.pdf"
    assert (
        resources.find_image("icon", tmp_path, folders=("localized", ""))
        == tmp_path / "localized/icon.pdf"
    )
    assert (
        resources.find_image("icon", tmp_path, extensions=("png", "pdf"))
        == tmp_path / "icon.png"
    )
    assert resources.find_image("icon.png", tmp_path) == tmp_path / "icon.png"
    assert resources.find_image("missing", tmp_path) is None
    assert resources.find_image(None, tmp_path) is None
    assert resources.find_image("", tmp_path) is None
    assert resources.find_image("icon", None) is None


def test_retina_when_siblings_then_format_order_and_vector_refusal(tmp_path):
    for name in ("icon@2x.PNG", "icon@2x.tiff", "other@2x.tif", "vector@2x.pdf"):
        (tmp_path / name).write_bytes(b"image")
    assert resources.retina_variant(tmp_path / "icon.PNG") == tmp_path / "icon@2x.PNG"
    assert (
        resources.retina_variant(tmp_path / "other.tiff") == tmp_path / "other@2x.tif"
    )
    assert resources.retina_variant(tmp_path / "none.png") is None
    assert resources.retina_variant(tmp_path / "vector.pdf") is None


@pytest.mark.parametrize(
    "stdout,expected",
    [
        ("file.pdf\n pixelWidth: 15.0\n pixelHeight: 18.0\n", (15.0, 18.0)),
        ("pixelWidth: nope\npixelHeight: 18", None),
        ("pixelWidth: 15", None),
    ],
)
def test_pdf_dimensions_when_output_parsed_then_plain_numeric_pair(stdout, expected):
    def run(argv, **kwargs):
        assert argv == ["renderer", "-g", "pixelWidth", "-g", "pixelHeight", "file.pdf"]
        assert kwargs == {"capture_output": True, "text": True, "timeout": 2}
        return SimpleNamespace(returncode=0, stdout=stdout)

    assert (
        resources.pdf_dimensions("file.pdf", run=run, executable="renderer", timeout=2)
        == expected
    )


@pytest.mark.parametrize("outcome", ["status", "oserror", "timeout"])
def test_pdf_when_process_fails_then_none_and_scratch_removed(outcome):
    paths = []

    def run(argv, **kwargs):
        if "--out" in argv:
            paths.append(Path(argv[-1]))
        if outcome == "oserror":
            raise OSError("missing executable")
        if outcome == "timeout":
            raise subprocess.TimeoutExpired(argv, kwargs["timeout"])
        return SimpleNamespace(returncode=1, stdout="")

    assert resources.pdf_dimensions("file.pdf", run=run) is None
    assert resources.render_pdf("file.pdf", 30, 36, run=run) is None
    assert paths and all(not path.exists() for path in paths), (
        "failed renders must release scratch files"
    )


@pytest.mark.parametrize("payload", [b"PNG", b""])
def test_render_pdf_when_complete_then_payload_and_owned_scratch_cleanup(payload):
    paths = []

    def run(argv, **kwargs):
        paths.append(Path(argv[-1]))
        assert argv[:2] == ["renderer", "-s"]
        assert argv[argv.index("-z") + 1 : argv.index("-z") + 3] == ["36", "30"]
        assert paths[-1].name.startswith("owned-")
        paths[-1].write_bytes(payload)
        return SimpleNamespace(returncode=0, stdout="")

    assert resources.render_pdf(
        "file.pdf", 30, 36, run=run, executable="renderer", scratch_prefix="owned-"
    ) == (payload or None)
    assert not paths[0].exists(), "successful renders must release scratch files"


def test_render_pdf_when_unexpected_runner_error_then_error_and_cleanup():
    paths = []

    def run(argv, **kwargs):
        paths.append(Path(argv[-1]))
        raise ValueError("runner defect")

    with pytest.raises(ValueError, match="runner defect"):
        resources.render_pdf("file.pdf", 1, 1, run=run)
    assert not paths[0].exists(), "unexpected failures must still release scratch files"


def test_import_when_host_free_then_only_stdlib_dependencies():
    root = str((Path(__file__).resolve().parents[1] / "src"))
    script = """
import importlib.abc, sys
class StdlibOnly(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] not in sys.stdlib_module_names | {'fontlabapp'}:
            raise AssertionError('Foreign import: ' + fullname)
sys.meta_path.insert(0, StdlibOnly())
sys.path.insert(0, sys.argv[1])
import fontlabapp.qt.images.resources
"""
    result = subprocess.run(
        [sys.executable, "-I", "-S", "-c", script, root],
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr
