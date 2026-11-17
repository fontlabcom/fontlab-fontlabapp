# this_file: tests/test_install_extensions.py
"""install.vfpy is the fontlab-instamix stub; the release carries it with valid metadata."""

import re
import subprocess
import tarfile
import tomllib
from email.parser import BytesParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def canonical_stub() -> bytes | None:
    """instamix's own stub bytes, from the package or a sibling checkout."""
    try:
        from fontlab_instamix import stub
    except ImportError:
        sibling = ROOT.parent / "fontlab-python-instamix" / "stub" / "install.vfpy"
        return sibling.read_bytes() if sibling.is_file() else None
    return stub.text().encode("utf-8")


STUB_HEADER = b"#FLM: Install into FontLab with fontlab-instamix\n"
ID_PATTERN = re.compile(r"^[a-z][a-z0-9-]*(\.[a-z0-9][a-z0-9-]*)+$")


def test_installer_when_read_then_it_is_the_small_instamix_stub():
    installer = (ROOT / "install.vfpy").read_bytes()
    assert installer.startswith(STUB_HEADER), installer[:80]
    assert b"bootstrap.install_project(__file__)" in installer
    assert len(installer.splitlines()) < 250, "legacy installer body must not return"
    canonical = canonical_stub()
    if canonical is not None:
        assert installer == canonical, "install.vfpy must match instamix's canonical stub"


def test_pyproject_when_read_then_install_table_names_this_extension():
    table = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["tool"]["fontlab-install"]
    assert ID_PATTERN.match(table["id"]), table["id"]
    assert table["id"] == "com.fontlab.fontlabapp"


def test_sdist_when_built_then_it_ships_the_stub_and_install_table(tmp_path):
    output = tmp_path / "dist"
    subprocess.run(
        ["uv", "build", "--sdist", "--out-dir", str(output), str(ROOT)],
        check=True, capture_output=True, text=True, timeout=120,
    )
    archives = list(output.glob("*.tar.gz"))
    assert len(archives) == 1
    with tarfile.open(archives[0]) as archive:
        prefix = archive.getnames()[0].split("/")[0] + "/"
        installer = archive.extractfile(prefix + "install.vfpy").read()
        info = archive.extractfile(prefix + "PKG-INFO").read()
        config = tomllib.loads(archive.extractfile(prefix + "pyproject.toml").read().decode("utf-8"))
    assert installer == (ROOT / "install.vfpy").read_bytes()
    metadata = BytesParser().parsebytes(info)
    assert metadata["Name"] == config["project"]["name"]
    assert metadata["Version"], "sdist must carry a genuine version"
    assert config["tool"]["fontlab-install"]["id"] == "com.fontlab.fontlabapp"
