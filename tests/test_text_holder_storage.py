# this_file: tests/test_text_holder_storage.py
"""Real I/O is restricted to pytest-owned temporary directories."""

import json
from pathlib import Path
from types import SimpleNamespace as NS

import pytest
from fontlabapp.proof.text_holder.storage import TextStore, default_path


def test_missing_content_and_size_are_readonly_and_unicode_save_recovers(tmp_path):
    path = tmp_path / "missing" / "Text holder.txt"
    store = TextStore(path)
    assert store.load() == "" and store.size() is None and not path.parent.exists()
    text = "😀 Ae\u0301 אב\n\t\x00中\n"
    store.save(text)
    assert path.read_bytes() == text.encode("utf-8") and TextStore(path).load() == text
    store.save_size((720, 550))
    assert TextStore(path).size() == (720, 550)
    store.save("")
    assert store.load() == "" and store.size() == (720, 550)


def test_atomic_save_failure_preserves_saved_bytes_and_removes_only_owned_temp(
    tmp_path, monkeypatch
):
    path = tmp_path / "Text holder.txt"
    store = TextStore(path)
    store.save("before😀")

    def fail(*args):
        raise PermissionError("owned injected failure")

    monkeypatch.setattr(Path, "replace", fail)
    with pytest.raises(PermissionError):
        store.save("new text")
    assert path.read_text() == "before😀" and list(tmp_path.iterdir()) == [path]


def test_bad_saved_encoding_and_window_size_are_not_silently_overwritten(tmp_path):
    path = tmp_path / "Text holder.txt"
    path.write_bytes(b"\xff")
    store = TextStore(path)
    with pytest.raises(UnicodeError):
        store.load()
    assert path.read_bytes() == b"\xff"
    for size in [(1, 2), (False, 500), [700], "700,500"]:
        path.with_suffix(".window.json").write_text(json.dumps(size))
        with pytest.raises(ValueError):
            store.size()
    with pytest.raises(TypeError):
        store.save(None)
    with pytest.raises(ValueError):
        store.save_size((1300, 500))


def test_default_store_uses_bound_application_data_location_without_creating_it(
    tmp_path,
):
    calls = []
    paths = NS(
        AppDataLocation=17,
        writableLocation=lambda kind: calls.append(kind) or str(tmp_path / "unused"),
    )
    assert (
        default_path(NS(QtCore=NS(QStandardPaths=paths)))
        == tmp_path / "unused/Text holder.txt"
    )
    assert calls == [17] and not (tmp_path / "unused").exists()
    paths.writableLocation = lambda kind: ""
    with pytest.raises(OSError):
        default_path(NS(QtCore=NS(QStandardPaths=paths)))


def test_temp_creation_failure_preserves_old_file_without_unlinking_it(
    tmp_path, monkeypatch
):
    import fontlabapp.proof.text_holder.storage as storage

    path = tmp_path / "Text holder.txt"
    path.write_text("before")

    def fail(**kwargs):
        raise PermissionError("cannot create owned temp")

    monkeypatch.setattr(storage, "NamedTemporaryFile", fail)
    with pytest.raises(PermissionError):
        TextStore(path).save("after")
    assert path.read_text() == "before" and list(tmp_path.iterdir()) == [path]


def test_original_disk_read_uses_universal_newlines_but_save_keeps_authored_bytes(
    tmp_path,
):
    store = TextStore(tmp_path / "literal.txt")
    store.path.write_bytes("A\r\nB\rC\nD\u2028E\u2029F\u00a0😀".encode("utf-8"))
    assert store.load() == "A\nB\nC\nD\u2028E\u2029F\u00a0😀"
    authored = "A\r\nB\rC\nD\u2028E\u2029F\u00a0😀"
    store.save(authored)
    assert store.path.read_bytes().decode("utf-8") == authored
