# this_file: src/fontlabapp/studios/proof_studio/generators/__init__.py
# SPDX-License-Identifier: Apache-2.0
"""Proof Studio generator registry: one module per generator, listed per tab.

What: every non-underscore module in this package defines ``GENERATOR``, a
``Generator``. ``generators()`` imports them (sorted by tab order, then the
generator's ``order``) and ``tab_titles()`` lists the tabs they name. A new
tab or generator is a new module only; nothing here changes.
Why: Phase D A7 absorbs 26 Scriptmix proof scripts in two tasks; T9 adds Real
text, Random, Word finder, Waterfall and By master as further modules.
Contract: ``make(choice, options)`` is pure (no Qt, no host, no writes) and
returns a ``Proof``. ``open(choice)`` opens the new FontLab Glyph tab(s)
exactly as the absorbed script did; it never edits the font. Persistence is
limited to the absorbed tool's own QSettings namespace (``settings``).
Used by ``fontlabapp.studios.proof_studio`` (tab registration, tabs and session).
"""

import pkgutil
from collections.abc import Callable
from dataclasses import dataclass, field
from importlib import import_module
from typing import Any

DEFAULT_SIZE = 72.0  # TMetrics' default px/em


@dataclass(frozen=True)
class Facts:
    """Read-only current-font facts for generators that set text in the font.

    ``cmap`` maps each code point to its first encoded glyph (font order),
    ``names`` holds every glyph name, ``masters`` the master names in order and
    ``master`` the active master.
    """

    cmap: dict[int, str] = field(default_factory=dict)
    names: frozenset[str] = frozenset()
    masters: tuple[str, ...] = ()
    master: str = ""


@dataclass(frozen=True)
class Options:
    """Generator inputs. ``names`` are the ordered selected glyph names, repeats kept.

    ``seed`` seeds Random and Real text (None: unseeded, as the absorbed
    scripts); ``values`` holds the generator's field values by key; ``facts``
    the current-font facts when the generator ``uses_font`` (None: no font).
    """

    names: tuple[str, ...] = ()
    seed: int | None = None
    values: dict[str, Any] = field(default_factory=dict)
    facts: Facts | None = None


@dataclass(frozen=True)
class Proof:
    """One ``parts`` entry per new FontLab Glyph tab the generator opens, in order.

    Each part is the exact text the studio copies. ``preview`` is the same text
    as one TMetrics line (newlines become spaces) unless ``previews`` gives the
    TMetrics text per part. ``labels`` name the parts in the part picker;
    ``sizes``/``layers`` give each part's TMetrics size and layer (master) and
    ``kerning`` the kerning toggle; empty means the TMetrics defaults (72 px,
    default layer). ``note`` is shown in the status line. ``canvas`` is the
    content for the generator's stacked proof view (``Generator.canvas``):
    ``(glyph names, sizes, master)`` for WaterfallView, ``(glyph names, size)``
    for MasterRows; missing glyphs are None.
    """

    parts: tuple[str, ...]
    labels: tuple[str, ...] = ()
    previews: tuple[str, ...] = ()
    sizes: tuple[float, ...] = ()
    layers: tuple[str, ...] = ()
    kerning: bool = True
    note: str = ""
    canvas: tuple[Any, ...] = ()

    def preview(self, index: int) -> str:
        """Part ``index`` as a single TMetrics text line; empty when out of range."""
        if not 0 <= index < len(self.parts):
            return ""
        if self.previews:
            return self.previews[index]
        return " ".join(self.parts[index].split("\n")).strip()

    def view(self, index: int) -> tuple[float, str | None, bool]:
        """``(size, layer, kerning)`` for previewing part ``index`` (defaults: 72 px, None, on)."""
        size = self.sizes[index] if 0 <= index < len(self.sizes) else DEFAULT_SIZE
        layer = self.layers[index] if 0 <= index < len(self.layers) else None
        return size, layer, self.kerning


@dataclass(frozen=True)
class Field:
    """One generator input control.

    ``kind``: ``line`` (one-line text), ``text`` (multi-line text), ``int``
    (spin box ``minimum..maximum``), ``combo`` (``items`` labels; the value is
    the index) or ``master`` (the font's masters; the value is the name,
    default the active master).
    """

    key: str
    label: str
    kind: str = "line"
    default: Any = ""
    minimum: int = 0
    maximum: int = 0
    items: tuple[str, ...] = ()
    placeholder: str = ""


@dataclass(frozen=True)
class Context:
    """What an action or ``open_current`` sees: the choice, field values, settings and proof.

    ``cancelled()`` turns true once the studio window is closed (Master text
    comparison stops its Open then, as the original panel did on Close).
    """

    choice: str
    values: dict[str, Any]
    settings: Any = None
    proof: Proof | None = None
    part: int = 0
    cancelled: Callable[[], bool] = lambda: False

    def text(self) -> str:
        """The exact text of the chosen part ("" when there is none)."""
        if self.proof is None or not 0 <= self.part < len(self.proof.parts):
            return ""
        return self.proof.parts[self.part]


@dataclass(frozen=True)
class Outcome:
    """An action's result: status text, field values and combo items to set, a report to show."""

    status: str = ""
    values: dict[str, Any] = field(default_factory=dict)
    items: dict[str, tuple[str, ...]] = field(default_factory=dict)
    report: str | None = None


@dataclass(frozen=True)
class Action:
    """A generator button: ``run(context) -> Outcome``."""

    label: str
    run: Callable[[Context], Outcome]


@dataclass(frozen=True)
class Generator:
    """A registered generator: picker title, tab, choices and pure ``make``.

    ``choices`` are ``(label, key)`` pairs (character-class source, surround
    string or proof text). ``scripts`` maps each key to the absorbed Scriptmix
    script title. ``uses_selection`` says whether ``Options.names`` matters.
    ``open(choice)`` repeats the absorbed script; ``open_current(choice,
    context)``, when set, opens what the studio shows instead (and may return
    a status). Neither set: the generator has no Glyph tab (Copy only).
    ``choice_label``/``part_label`` caption the choice and part pickers;
    ``seeded`` shows the Seed field; ``uses_font`` supplies ``Options.facts``.
    ``fields`` are extra inputs. ``settings`` is the ``(organization,
    application)`` QSettings namespace of the absorbed tool; ``load(settings)``
    returns the saved field values as an ``Outcome`` and ``save(settings,
    values, proof)`` runs after each user edit. ``actions`` add buttons.
    ``canvas`` names the absorbed panel's own stacked proof view in
    ``fontlabapp.proof.inspect.views`` (``WaterfallView`` or ``MasterRows``),
    drawn from ``Proof.canvas`` beside the TMetrics part preview.
    """

    key: str
    title: str
    tab: str
    tab_order: int
    order: int
    choices: tuple[tuple[str, str], ...]
    scripts: dict[str, str]
    make: Callable[[str, Options], Proof]
    open: Callable[[str], None] | None
    uses_selection: bool = False
    seeded: bool = False
    uses_font: bool = False
    open_current: Callable[[str, Context], str | None] | None = None
    choice_label: str = "Source"
    part_label: str = "Tab"
    fields: tuple[Field, ...] = ()
    settings: tuple[str, str] | None = None
    load: Callable[[Any], Outcome] | None = None
    save: Callable[[Any, dict[str, Any], Proof], None] | None = None
    actions: tuple[Action, ...] = ()
    canvas: str = ""

    @property
    def opens(self) -> bool:
        """True when the generator can open a FontLab Glyph tab."""
        return self.open is not None or self.open_current is not None


def generators() -> tuple[Generator, ...]:
    """Every generator module's ``GENERATOR``, by tab order then generator order."""
    found = []
    for info in pkgutil.iter_modules(__path__):
        if not info.name.startswith("_"):
            found.append(import_module(f"{__name__}.{info.name}").GENERATOR)
    return tuple(sorted(found, key=lambda g: (g.tab_order, g.order, g.key)))


def tab_titles() -> tuple[str, ...]:
    """Tab titles in tab order, each once."""
    return tuple(dict.fromkeys(g.tab for g in generators()))


def for_tab(tab: str) -> tuple[Generator, ...]:
    """The generators shown on ``tab``, in picker order."""
    return tuple(g for g in generators() if g.tab == tab)


__all__ = [
    "DEFAULT_SIZE",
    "Action",
    "Context",
    "Facts",
    "Field",
    "Generator",
    "Options",
    "Outcome",
    "Proof",
    "for_tab",
    "generators",
    "tab_titles",
]
