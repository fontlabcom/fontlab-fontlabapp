#!/usr/bin/env python3
# this_file: tools/restructure.py
"""Historical one-off issue-205 migration, retained to document the moves.

Stdlib only; Python 3.11. The original migration used --batch 1 through 10
with gates between batches. This is not a maintenance command for the current
source tree. No Git/index operations are performed.
"""

import argparse
import ast
import importlib.util
import json
from pathlib import Path
import pprint
import re

_FORMAT_SPEC = importlib.util.spec_from_file_location(
    "restructure_import_formatter", Path(__file__).with_name("format_imports.py")
)
_FORMATTER = importlib.util.module_from_spec(_FORMAT_SPEC)
_FORMAT_SPEC.loader.exec_module(_FORMATTER)

ROOT = Path(__file__).resolve().parents[1]
PACKAGES = {
    f"fontlabapp.{n}": f"fontlabapp.core.{n}"
    for n in ("application", "hotkey", "utils")
}
BATCHES = (
    "core",
    "qt",
    "glyphs",
    "proof-fonts",
    "masters",
    "components-anchors",
    "contours",
    "master-background-text",
    "metrics",
    "kerning-guides-features-hints",
)


def batch_of(target: str) -> int:
    """Assign every target to exactly one reviewed batch."""
    domain = target.split(".")[1]
    if target.startswith(
        ("fontlabapp.masters.background.", "fontlabapp.masters.text.")
    ):
        return 8
    return {
        "core": 1,
        "qt": 2,
        "glyphs": 3,
        "proof": 4,
        "fonts": 4,
        "masters": 5,
        "components": 6,
        "anchors": 6,
        "contours": 7,
        "metrics": 9,
        "kerning": 10,
        "guides": 10,
        "features": 10,
        "hints": 10,
    }[domain]


def module_file(name: str) -> Path:
    """Return the source path for a dotted module."""
    return ROOT / "src" / (name.replace(".", "/") + ".py")


def replace_name(name: str, mapping: dict[str, str]) -> str:
    """Map an exact old module or its attributes, never a canonical path twice."""
    if name in mapping:
        return mapping[name]
    for target in mapping.values():
        if (
            name == target
            or name.startswith(target + ".")
            or target.startswith(name + ".")
        ):
            return name
    for old in sorted(mapping, key=len, reverse=True):
        if name.startswith(old + "."):
            return mapping[old] + name[len(old) :]
    return name


def rewrite(source: str, package: str, mapping: dict[str, str]) -> str:
    """Rewrite AST-located imports, then exact dotted/path tokens in text.

    Resolve relative imports in their ORIGINAL package before applying moves.
    Preserve local import bindings, indentation, comments and all other code.
    AST columns are UTF-8 byte offsets; edits use byte offsets too.
    """
    source = _FORMATTER.format_imports(source)
    raw = source.encode()
    lines = raw.splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))
    edits = []
    for node in ast.walk(ast.parse(source)):
        statements = []
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = replace_name(alias.name, mapping)
                statements.append(
                    "import " + name + (f" as {alias.asname}" if alias.asname else "")
                )
        elif isinstance(node, ast.ImportFrom):
            name = node.module or ""
            if node.level:
                if not package.startswith("fontlabapp"):
                    continue
                name = importlib.util.resolve_name("." * node.level + name, package)
            for alias in node.names:
                full = name + "." + alias.name
                if full in mapping:
                    parent, _, child = mapping[full].rpartition(".")
                    binding = alias.asname or alias.name
                    statements.append(
                        f"from {parent} import {child}"
                        + (f" as {binding}" if binding != child else "")
                    )
                else:
                    statements.append(
                        f"from {replace_name(name, mapping)} import {alias.name}"
                        + (f" as {alias.asname}" if alias.asname else "")
                    )
        else:
            continue
        # Only rewrite imports affected by this batch (or relatives in moved files).
        original = ast.get_source_segment(source, node)
        replacement = _FORMATTER.format_imports("\n".join(statements)).rstrip("\n")
        if ast.dump(ast.parse(original)) == ast.dump(ast.parse(replacement)):
            continue
        start = offsets[node.lineno - 1] + node.col_offset
        end = offsets[node.end_lineno - 1] + node.end_col_offset
        # A common destination permits token edits, retaining parenthesized comments.
        parsed = ast.parse(replacement).body
        if (
            isinstance(node, ast.ImportFrom)
            and len(parsed) == 1
            and isinstance(parsed[0], ast.ImportFrom)
        ):
            target = parsed[0]
            import_keyword = next(
                t
                for t in _FORMATTER.tokenize.generate_tokens(
                    _FORMATTER.io.StringIO(original).readline
                )
                if t.type == _FORMATTER.tokenize.NAME and t.string == "import"
            )
            fragment_lines = original.splitlines(keepends=True)
            head_end = (
                sum(map(len, fragment_lines[: import_keyword.start[0] - 1]))
                + import_keyword.start[1]
            )
            fragment_edits = [
                (
                    0,
                    len(original[:head_end].encode()),
                    f"from {'.' * target.level}{target.module or ''} ".encode(),
                )
            ]
            for old, new in zip(node.names, target.names):
                if (old.name, old.asname) == (new.name, new.asname):
                    continue
                begin = offsets[old.lineno - 1] + old.col_offset - start
                finish = offsets[old.end_lineno - 1] + old.end_col_offset - start
                text = new.name + (f" as {new.asname}" if new.asname else "")
                fragment_edits.append((begin, finish, text.encode()))
            fragment = original.encode()
            for begin, finish, text in sorted(fragment_edits, reverse=True):
                fragment = fragment[:begin] + text + fragment[finish:]
            replacement = fragment.decode()
        else:
            # Fan-out imports keep interior annotations in their lexical order.
            comments = [
                t
                for t in _FORMATTER.tokenize.generate_tokens(
                    _FORMATTER.io.StringIO(original).readline
                )
                if t.type == _FORMATTER.tokenize.COMMENT
            ]
            if comments:
                replacement = "\n".join([*(t.string for t in comments), replacement])
            tail = lines[node.end_lineno - 1][node.end_col_offset :].decode().strip()
            if len(parsed) > 1 and re.match(r"#\s*noqa\b", tail):
                # A line-wide pragma must follow every import produced by fan-out.
                r_lines, r_offsets = _FORMATTER.positions(replacement)
                nodes = ast.parse(replacement).body
                ends = [
                    _FORMATTER.offset(
                        r_lines, r_offsets, n.end_lineno, n.end_col_offset
                    )
                    for n in nodes[:-1]
                ]
                for position in reversed(ends):
                    replacement = (
                        replacement[:position] + "  " + tail + replacement[position:]
                    )
            indent = lines[node.lineno - 1][: node.col_offset].decode()
            replacement = replacement.replace("\n", "\n" + indent)
        edits.append((start, end, replacement.encode()))
    for start, end, replacement in sorted(edits, reverse=True):
        raw = raw[:start] + replacement + raw[end:]
    source = raw.decode()
    pattern = r"(?<![\w.])fontlabapp(?:\.[A-Za-z_]\w*)+"
    source = re.sub(pattern, lambda m: replace_name(m[0], mapping), source)
    for old, new in mapping.items():
        old_path = old.replace(".", "/") + ".py"
        new_path = new.replace(".", "/") + ".py"
        source = source.replace("src/" + old_path, "src/" + new_path)
    return _FORMATTER.format_imports(source)


def write_changed(path: Path, text: str) -> None:
    """Write only changed bytes, retaining stable reruns."""
    if not path.exists() or path.read_text() != text:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)


def install_root_hook() -> None:
    """Add lazy legacy resolution without changing the root's public exports."""
    path = ROOT / "src/fontlabapp/__init__.py"
    source = path.read_text()
    if "import ALIASES as _LEGACY_ALIASES" not in source:
        anchor = "from importlib.metadata import PackageNotFoundError, version\n"
        if anchor not in source:
            raise ValueError("root import layout changed; review legacy hook placement")
        source = source.replace(
            anchor,
            anchor
            + (
                "from ._legacy import ALIASES as _LEGACY_ALIASES, install as _install_legacy\n\n"
                "_install_legacy()\n"
            ),
            1,
        )
    if 'legacy_name = "fontlabapp." + name' not in source:
        anchor = "def __getattr__(name: str) -> Any:\n"
        if anchor not in source:
            raise ValueError("root getattr changed; review legacy hook placement")
        source = source.replace(
            anchor,
            anchor
            + (
                '    legacy_name = "fontlabapp." + name\n'
                "    if legacy_name in _LEGACY_ALIASES:\n"
                "        value = import_module(legacy_name)\n"
                "        globals()[name] = value\n"
                "        return value\n"
            ),
            1,
        )
    write_changed(path, source)


def ensure_packages(mapping: dict[str, str]) -> None:
    """Create documented packages; collision facades lazily forward model names."""
    parents = set()
    for target in mapping.values():
        parts = target.split(".")
        parents.update(".".join(parts[:i]) for i in range(2, len(parts)))
    for name in sorted(parents):
        path = ROOT / "src" / name.replace(".", "/") / "__init__.py"
        if path.exists():
            continue
        doc = f"{name.removeprefix('fontlabapp.')} domain helpers; children load only when explicitly imported."
        body = ""
        if name in mapping:
            doc += (
                "\n\nLegacy compatibility: missing attribute reads and model writes/deletes forward to\n"
                f"{mapping[name]}. The implementation loads on first access as a normal,\n"
                "separate module; this package retains its own children and metadata."
            )
            body = (
                "\nfrom fontlabapp._legacy import configure_facade as _configure_facade\n"
                f"_configure_facade(__name__, {mapping[name]!r})\n"
            )
        write_changed(
            path, f'# this_file: {path.relative_to(ROOT)}\n"""{doc}"""\n' + body
        )


def update_manifest(mapping: dict[str, str]) -> None:
    """Relocate provenance destinations without changing historical hash fields."""
    path = ROOT / "MIGRATION.json"
    manifest = json.loads(path.read_text())
    for row in manifest["files"]:
        old_path = row["destination"]
        if old_path == "src/fontlabapp/__init__.py":
            row.setdefault(
                "issue_205_move",
                {
                    "previous_destination": old_path,
                    "note": "Root exports retained; other modules relocated per tools/fontlabapp-mapping.json. Historical hashes unchanged.",
                },
            )
        old = old_path.removeprefix("src/").removesuffix(".py").replace("/", ".")
        package = old.endswith(".__init__")
        old = old.removesuffix(".__init__")
        if old not in mapping:
            continue
        new_path = (
            "src/"
            + mapping[old].replace(".", "/")
            + ("/__init__.py" if package else ".py")
        )
        row["destination"] = new_path
        row["issue_205_move"] = {
            "previous_destination": old_path,
            "note": "Domain relocation; sha256 fields retain historical provenance.",
        }
    write_changed(path, json.dumps(manifest, indent=2) + "\n")


def run(mapping_path: Path, batch: int) -> None:
    """Move a batch, rewrite cumulative imports and generate its alias table."""
    reviewed = json.loads(mapping_path.read_text())
    if len(set(reviewed.values())) != len(reviewed):
        raise ValueError("mapping targets must be unique")
    selected = {k: v for k, v in reviewed.items() if batch_of(v) == batch}
    if batch == 6:
        selected = dict(
            sorted(
                selected.items(),
                key=lambda item: (
                    not item[1].startswith("fontlabapp.components."),
                    item[1],
                ),
            )
        )
    active = {k: v for k, v in reviewed.items() if module_file(v).is_file()}
    if any(batch_of(v) < batch and k not in active for k, v in reviewed.items()):
        raise ValueError("run earlier batches first")
    active.update(selected)
    if any(batch_of(v) == 1 for v in active.values()):
        active.update(PACKAGES)
    install_root_hook()
    # Capture original relative-import contexts before moving anything.
    contexts = {}
    for path in sorted((ROOT / "src").rglob("*.py")):
        rel = path.relative_to(ROOT / "src").with_suffix("")
        name = ".".join(rel.parts)
        contexts[path] = name.rpartition(".")[0]
    for old, new in selected.items():
        src, dst = module_file(old), module_file(new)
        if src.exists() and dst.exists():
            raise FileExistsError(f"both old and new sources exist: {old}, {new}")
        if src.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            src.rename(dst)
            contexts[dst] = contexts.pop(src)
        elif not dst.exists():
            raise FileNotFoundError(src)
    if batch == 1:
        for old, new in PACKAGES.items():
            src = ROOT / "src" / old.replace(".", "/") / "__init__.py"
            dst = ROOT / "src" / new.replace(".", "/") / "__init__.py"
            if src.exists():
                dst.parent.mkdir(parents=True, exist_ok=True)
                src.rename(dst)
                contexts[dst] = contexts.pop(src)
                if not any(src.parent.iterdir()):
                    src.parent.rmdir()
    ensure_packages(active)
    if "fontlabapp.application" in active:
        app_init = ROOT / "src/fontlabapp/core/application/__init__.py"
        write_changed(
            app_init,
            app_init.read_text().replace(
                '"Application": "application"', '"Application": "context"'
            ),
        )
        bodies = json.loads(Path(__file__).with_name("lazy-packages.json").read_text())
        for name, body in bodies.items():
            path = ROOT / f"src/fontlabapp/core/{name}/__init__.py"
            source = path.read_text()
            if '"""' not in source:
                start = source.index("import sys" if name == "hotkey" else "try:")
                write_changed(path, source[:start] + body)
    for filename, consumer in (
        ("random_proof_words.json", "fontlabapp.random_proof"),
        ("kerning_proof_texts.json", "fontlabapp.kerning_proofs"),
    ):
        if consumer in active:
            domain = active[consumer].split(".")[1]
            src = ROOT / "src/fontlabapp" / filename
            dst = src.parent / domain / filename
            if src.exists():
                if dst.exists():
                    raise FileExistsError(dst)
                src.rename(dst)
            consumer_path = module_file(active[consumer])
            write_changed(
                consumer_path,
                consumer_path.read_text().replace(
                    f'.joinpath("{filename}")', f'.joinpath("{domain}", "{filename}")'
                ),
            )
    for path in sorted(
        [*(ROOT / "src").rglob("*.py"), *(ROOT / "tests").rglob("*.py")]
    ):
        if path.name in {"_legacy.py", "test_legacy.py", "test_restructure.py"}:
            continue
        source = rewrite(path.read_text(), contexts.get(path, ""), active)
        if path.is_relative_to(ROOT / "src"):
            source = re.sub(
                r"(?m)^# this_file: .*",
                f"# this_file: {path.relative_to(ROOT)}",
                source,
            )
        write_changed(path, source)
    update_manifest(active)
    legacy_path = ROOT / "src/fontlabapp/_legacy.py"
    template = (Path(__file__).with_name("legacy_template.py")).read_text()
    table = "ALIASES = " + pprint.pformat(
        dict(sorted(active.items())), width=100, sort_dicts=True
    )
    write_changed(
        legacy_path,
        template.replace("ALIASES = {}  # ALIAS_TABLE", table).replace(
            "# this_file: tools/legacy_template.py",
            "# this_file: src/fontlabapp/_legacy.py",
        ),
    )
    print(
        f"Batch {batch} ({BATCHES[batch - 1]}): {len(selected)} modules; {len(active)} active aliases"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mapping",
        type=Path,
        default=Path(__file__).with_name("fontlabapp-mapping.json"),
    )
    parser.add_argument("--batch", required=True, type=int, choices=range(1, 11))
    args = parser.parse_args()
    run(args.mapping, args.batch)
