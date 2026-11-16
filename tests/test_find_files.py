# this_file: tests/test_find_files.py
"""Real owned font/script files and independent paired streaming-search policy."""

from pathlib import Path
import pytest
from fontlabapp.qt.find_files.model import Search


def finish(search, pattern=None):
    for _ in range(10000):
        if not search.active:
            return search
        search.step(pattern)
    raise AssertionError("A bounded owned search failed to terminate")


@pytest.mark.parametrize("profile", ["text", "bytes"])
def test_actual_font_and_script_files_and_ceiling_sizes(tmp_path, profile):
    (tmp_path / "font.vfj").write_text(
        '{"font":{"familyName":"Owned orchard","glyphs":[]}}', encoding="utf8"
    )
    (tmp_path / "tool.py").write_text(
        '# owned script, never executed\nneedle = "orchard"\n', encoding="utf8"
    )
    (tmp_path / "other.txt").write_text("none", encoding="utf8")
    (tmp_path / "directory.py").mkdir()
    result = finish(Search(tmp_path, "*", "orchard", profile))
    assert {r.path.name for r in result.results} == {"font.vfj", "tool.py"}
    assert all(r.size_kib == 1 for r in result.results)
    assert result.finished and not result.active and result.stream is None


@pytest.mark.parametrize("profile", ["text", "bytes"])
def test_cross_64k_utf8_and_query_boundaries(tmp_path, profile):
    text = "x" * 65535 + "😀orchard\u00a0end"
    (tmp_path / "fønt.glyphs").write_text(text, encoding="utf8")
    s = Search(tmp_path, "*.glyphs", "😀orchard\u00a0", profile)
    finish(s)
    assert [r.path.name for r in s.results] == ["fønt.glyphs"]


def test_decoder_replacement_is_part2_policy_only(tmp_path):
    (tmp_path / "broken.py").write_bytes(b"prefix\xffsuffix")
    assert len(finish(Search(tmp_path, "*", "\ufffd", "text")).results) == 1
    assert finish(Search(tmp_path, "*", "\ufffd", "bytes")).results == []


@pytest.mark.parametrize("profile,expected", [("text", []), ("bytes", ["a.py"])])
def test_blank_filename_pattern_profile_difference(tmp_path, profile, expected):
    (tmp_path / "a.py").write_text("owned")
    assert [
        r.path.name for r in finish(Search(tmp_path, "", "", profile)).results
    ] == expected


@pytest.mark.parametrize(
    "profile,expected", [("text", {"base.py", "link.py"}), ("bytes", {"base.py"})]
)
def test_symlinks_match_source_profiles_without_recursing(tmp_path, profile, expected):
    (tmp_path / "base.py").write_text("owned")
    (tmp_path / "link.py").symlink_to(tmp_path / "base.py")
    (tmp_path / "broken.py").symlink_to(tmp_path / "missing")
    (tmp_path / "folder").mkdir()
    (tmp_path / "folder" / "nested.py").write_text("owned")
    assert {
        r.path.name for r in finish(Search(tmp_path, "*.py", "", profile)).results
    } == expected


@pytest.mark.parametrize("profile", ["text", "bytes"])
def test_cancel_closes_live_stream_and_iterator_and_preserves_publication_policy(
    tmp_path, profile
):
    (tmp_path / "large.py").write_bytes(b"x" * 200000)
    s = Search(tmp_path, "*", "missing", profile)
    while s.stream is None and s.active:
        s.step()
    assert s.stream is not None
    stream = s.stream
    s.cancel()
    assert stream.closed and s.stream is None and s.entries is None
    assert not s.active and s.cancelled and not s.finished
    s.step()
    assert s.results == []


def test_part2_bounded_entries_live_pattern_and_progressive_results(tmp_path):
    for i in range(40):
        (tmp_path / f"{i:02}.txt").write_text("owned")
    (tmp_path / "last.py").write_text("owned")
    s = Search(tmp_path, "none", "", "text")
    s.step("none")
    assert s.scanned == 32 and not s.results and s.active
    s.step("*")
    assert len(s.results) == 1 and s.active
    assert all(r.path.is_file() for r in finish(s, "*").results)


def test_part3_captures_pattern_and_holds_all_results_until_finished(tmp_path):
    for name in ("a.py", "b.txt"):
        (tmp_path / name).write_text("needle")
    s = Search(tmp_path, "*.py", "needle", "bytes")
    while not s.found and s.active:
        s.step("*.txt")
    assert s.found and not s.results and s.active
    finish(s, "*.txt")
    assert [r.path.name for r in s.results] == ["a.py"] and s.total == 1


@pytest.mark.parametrize("profile", ["text", "bytes"])
def test_unreadable_file_does_not_abort_other_matches(tmp_path, profile, monkeypatch):
    (tmp_path / "bad.py").write_text("needle")
    (tmp_path / "good.py").write_text("needle")
    original = Path.open

    def opening(self, *args, **kwargs):
        if self.name == "bad.py":
            raise PermissionError("owned unreadable file")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", opening)
    s = finish(Search(tmp_path, "*", "needle", profile))
    assert [r.path.name for r in s.results] == ["good.py"] and "unreadable" in s.error


@pytest.mark.parametrize("profile", ["text", "bytes"])
def test_missing_directory_is_a_stopped_visible_error(tmp_path, profile):
    s = finish(Search(tmp_path / "missing", "*", "", profile))
    assert s.error and not s.active and not s.finished and not s.results
    assert s.stream is None and s.entries is None


@pytest.mark.parametrize("profile", ["text", "bytes"])
def test_deleted_match_metadata_and_empty_files_follow_profile_policy(
    tmp_path, profile, monkeypatch
):
    from fontlabapp.qt.find_files.io import result

    missing = tmp_path / "gone.py"
    assert result(missing, strict=False).size == 0
    with pytest.raises(FileNotFoundError):
        result(missing, strict=True)
    (tmp_path / "empty.py").touch()
    assert not finish(Search(tmp_path, "*", "needle", profile)).results
    assert finish(Search(tmp_path, "*", "", profile)).results[0].size_kib == 0


def test_invalid_profile_and_directory_iteration_failure(tmp_path, monkeypatch):
    with pytest.raises(ValueError):
        Search(tmp_path, "*", "", "unknown")

    def broken(self):
        yield tmp_path / "missing"
        raise PermissionError("owned iteration fault")

    monkeypatch.setattr(Path, "iterdir", broken)
    s = finish(Search(tmp_path, "*", "", "bytes"))
    assert "iteration fault" in s.error and not s.active


def test_decoder_eof_flush_and_byte_overlap():
    import io
    import codecs
    from fontlabapp.qt.find_files.io import read_chunk

    stream = io.BytesIO(b"\xe2")
    decoder = codecs.getincrementaldecoder("utf8")("replace")
    assert read_chunk(stream, "\ufffd", "", decoder) == (False, False, "")
    assert read_chunk(stream, "\ufffd", "", decoder) == (True, True, "")
