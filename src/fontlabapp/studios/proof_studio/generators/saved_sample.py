# this_file: src/fontlabapp/studios/proof_studio/generators/saved_sample.py
# SPDX-License-Identifier: Apache-2.0
"""Saved sample: one reusable proof string, kept across launches and checked against the font.

What: absorbs Examples "Saved Proof Sample" (the author's own Apache-2.0
sample). Same storage: QSettings ("FontLabPythonExamples",
"SavedProofSample"), fallbacks off, the one key ``proof/sample``, default
"Hamburgefontsiv". Save is explicit (Save sample); Reset saved sample
removes only that key. Check coverage captures the whole current font
(``glyphs.catalog`` with a ``min(120, 10 + 0.02 × glyphs)`` second budget) and
reports covered and missing Unicode scalars as the same JSON. Text with NUL,
NBSP, U+2028/U+2029 or lone surrogates is refused, as the original.
"""

import json
from time import monotonic
from typing import Any

from fontlabapp.core.scripting import current_package, proof_studio_backends

from . import Action, Context, Field, Generator, Options, Outcome, Proof

SETTINGS = ("FontLabPythonExamples", "SavedProofSample")
KEY = "proof/sample"
DEFAULT = "Hamburgefontsiv"
UNUSABLE = "The saved sample is unusable. Edit the replacement and Save Sample, or Reset Saved Sample."


def checked(text: str) -> str:
    """Apply the original exact-transfer policy."""
    if any(char in text for char in ("\0", " ", " ", " ")) or any(
        0xD800 <= ord(char) <= 0xDFFF for char in text
    ):
        raise ValueError("Use text without NUL, NBSP, line separators or lone surrogates.")
    return text


def coverage_report(sample: str, rows: tuple[tuple[str, str, str], ...]) -> str:
    """Compare literal proof scalars with all Unicode assignments; the original JSON."""
    needed = set(map(ord, checked(sample)))
    encoded = {int(token.removeprefix("U+"), 16) for _, codes, _ in rows for token in codes.split()}
    return json.dumps(
        {
            "sample": sample,
            "glyph_count": len(rows),
            "missing": [f"U+{point:04X}" for point in sorted(needed - encoded)],
            "covered": [f"U+{point:04X}" for point in sorted(needed & encoded)],
        },
        ensure_ascii=True,
        indent=2,
    )


def persist(settings: Any, sample: str | None) -> None:
    """Save or remove only the owned key; confirm the QSettings sync status."""
    if sample is None:
        settings.remove(KEY)
    else:
        settings.setValue(KEY, checked(sample))
    settings.sync()
    status = settings.status()
    if getattr(status, "value", status) != 0:
        raise RuntimeError("Settings write failed. The sample may not persist; retry Save.")


def make(_choice: str, options: Options) -> Proof:
    """The sample as one part (refused when it cannot pass intact)."""
    return Proof((checked(str(options.values.get("sample", DEFAULT))),))


def load(settings: Any) -> Outcome:
    """The stored sample, or the default with the original notice when it is unusable."""
    stored = str(settings.value(KEY, DEFAULT))
    try:
        sample, status = checked(stored), "Save a reusable proof, check the current font's Unicode coverage, or copy proof text."
    except ValueError:
        sample, status = DEFAULT, UNUSABLE
    if getattr(settings.status(), "value", settings.status()) != 0:
        raise RuntimeError("Cannot read the saved proof sample settings.")
    return Outcome(status, values={"sample": sample})


def save_sample(context: Context) -> Outcome:
    persist(context.settings, str(context.values.get("sample", "")))
    return Outcome("Sample saved for the next launch.")


def reset_sample(context: Context) -> Outcome:
    persist(context.settings, None)
    return Outcome("Saved sample reset.", values={"sample": DEFAULT}, report="")


def check_coverage(context: Context, *, clock: Any = monotonic) -> Outcome:
    """A fresh, complete capture of the current font, then the JSON coverage report."""
    sample = checked(str(context.values.get("sample", "")))
    package = current_package()
    if package is None:
        raise ValueError("Open a font before scanning.")
    count = package.glyphsCount
    count = int(count() if callable(count) else count)
    budget = min(120.0, 10.0 + 0.02 * count)
    rows = tuple(proof_studio_backends().catalog.capture(deadline=clock() + budget).rows)
    return Outcome(
        f"Scanned {count:,} glyphs (budget {budget:g} s). Coverage at the last check.",
        report=coverage_report(sample, rows),
    )


GENERATOR = Generator(
    key="saved-sample",
    title="Saved sample",
    tab="Real text",
    tab_order=40,
    order=30,
    choices=(("Saved proof sample", "saved-sample"),),
    scripts={"saved-sample": "Saved Proof Sample"},
    make=make,
    open=None,
    fields=(Field("sample", "Sample", default=DEFAULT),),
    settings=SETTINGS,
    load=load,
    actions=(
        Action("Save sample", save_sample),
        Action("Reset saved sample", reset_sample),
        Action("Check coverage", check_coverage),
    ),
)
