# this_file: tests/test_import_formatting.py
"""Import formatting preserves side effects, scopes, aliases and original code."""

import importlib.util
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1] / "tools"


def load(name):
    spec = importlib.util.spec_from_file_location(name, TOOLS / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


formatter = load("format_imports")
checker = load("check_imports")


def test_adjacent_imports_when_merged_then_bindings_and_order_stay_exact():
    source = """from first import B as b; from first import A, B as again
import side_effect
from first import C
from second import D
from first import E
"""
    expected = """from first import B as b, A, B as again
import side_effect
from first import C
from second import D
from first import E
"""
    assert formatter.format_imports(source) == expected
    checker.assert_equivalent(source, expected)
    assert formatter.format_imports(expected) == expected


def test_nested_imports_when_wrapped_then_scope_and_unicode_are_preserved():
    source = (
        "if TYPE_CHECKING:\n"
        "    from ..very_long_module_name_for_wrapping import FirstLongName as local; "
        "from ..very_long_module_name_for_wrapping import SecondLongName\n"
        """try:
    import side_effect; from somewhere import value
except ImportError:
    from elsewhere import fallback
def lazy():
    'ą'; from package import name; from package import other as alias
"""
    )
    result = formatter.format_imports(source)
    assert (
        "    from ..very_long_module_name_for_wrapping import (\n"
        "        FirstLongName as local,\n        SecondLongName,\n    )"
        in result
    )
    assert "    import side_effect\n    from somewhere import value" in result
    assert "    'ą'\n    from package import name, other as alias" in result
    checker.assert_equivalent(source, result)
    assert formatter.format_imports(result) == result


def test_comments_when_present_then_blanks_and_noqa_stay_attached():
    source = """from module import a  # first purpose
from module import b

from module import c  # noqa: F401
# separate purpose
from module import (
    d,  # keep this annotation
    e,
)
text = 'from module import a; from module import b'
"""
    result = formatter.format_imports(source)
    assert result == source
    checker.assert_equivalent(source, result)


def test_multiline_crlf_when_formatted_then_newlines_and_name_order_are_retained():
    source = "from module import (\r\n    b,\r\n    a as alias,\r\n)\r\n"
    result = formatter.format_imports(source)
    assert result == "from module import b, a as alias\r\n"
    checker.assert_equivalent(source, result)


def test_inline_suites_when_split_then_imports_stay_in_scope():
    source = """if condition: import a; import b
def lazy(): import c; from relative import d
"""
    result = formatter.format_imports(source)
    assert (
        result
        == """if condition:
    import a
    import b
def lazy():
    import c
    from relative import d
"""
    )
    checker.assert_equivalent(source, result)


@pytest.mark.parametrize(
    "after",
    [
        "from module import a as changed\nvalue = 1\n",
        "from module import a as alias\nvalue = 2\n",
        "value = 1\nfrom module import a as alias\n",
        "def moved():\n    from module import a as alias\nvalue = 1\n",
    ],
)
def test_verifier_when_bindings_nonimports_order_or_scope_change_then_rejects(after):
    with pytest.raises(AssertionError):
        checker.assert_equivalent("from module import a as alias\nvalue = 1\n", after)


def test_snapshot_when_verified_then_checks_all_changed_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    root, saved = Path("src"), Path("before")
    root.mkdir()
    path = root / "example.py"
    path.write_text("from module import a; from module import b\n")
    checker.check(saved, [root], write=True)
    path.write_text(formatter.format_imports(path.read_text()))
    assert checker.check(saved, [root]) == 1
    path.write_text("value = 'changed'\n")
    with pytest.raises(AssertionError, match="src/example.py"):
        checker.check(saved, [root])
