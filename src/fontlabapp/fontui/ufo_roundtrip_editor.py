# this_file: src/fontlabapp/fontui/ufo_roundtrip_editor.py
# SPDX-License-Identifier: Apache-2.0
"""Owned temporary UFO interchange and complete comparisons of readable UFO data."""

from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic
from typing import Any

from attrs import asdict
from fontTools.misc.transform import Transform
from fontTools.ufoLib import fontInfoAttributesVersion3
from PythonQt import QtGui
from ufoLib2 import Font

from ._fontport import require_fontport

with require_fontport(__name__):
    from fontlab_fontport.interchange import ExportSession, import_ufo
    from fontlab_fontport.memory import UFOBackend

from fontlabapp.proof.reports.model import format_report

from .lifecycle import Owned


def _plain_transform(instance: Any, field: Any, value: Any) -> Any:
    """Keep Transform values as plain 6-tuples; attrs rebuilds namedtuples with one list argument."""
    return tuple(value) if isinstance(value, Transform) else value


def _glif_note(note: str | None) -> str | None:
    """The note a GLIF file can hold: lines stripped, blanks dropped, empty is absent (None)."""
    lines = [line.strip() for line in (note or '').split('\n') if line.strip()]
    return '\n'.join(lines) or None


def _snapshot(font: Font, check: Any) -> dict:
    """Read every persisted UFO family, excluding transient reader/cache state."""
    result = {
        'info': {key: deepcopy(getattr(font.info, key)) for key in sorted(fontInfoAttributesVersion3)},
        'features': font.features.text,
        'groups': {name: tuple(members) for name, members in font.groups.items()},
        'kerning': deepcopy(dict(font.kerning)),
        'lib': deepcopy(dict(font.lib)),
        'defaultLayer': font.layers.defaultLayer.name,
        'layerOrder': tuple(layer.name for layer in font.layers),
        'layers': {},
        'images': {name: bytes(font.images[name]) for name in font.images},
        'data': {name: bytes(font.data[name]) for name in font.data},
    }
    for layer in font.layers:
        check()
        data = {'color': layer.color, 'lib': deepcopy(dict(layer.lib)), 'glyphs': {}}
        for glyph in layer:
            check()
            fields = asdict(glyph, filter=lambda field, value: field.name != '_tempLib',
                            value_serializer=_plain_transform)
            fields['note'] = _glif_note(fields.get('note'))  # glifLib stores no empty note and strips lines
            data['glyphs'][glyph.name] = fields
        result['layers'][layer.name] = data
    check()
    return result


def _differences(before: Any, after: Any, path: str = '') -> list:
    """Keep every differing semantic field, including absent versus explicit None."""
    if isinstance(before, dict) and isinstance(after, dict):
        rows = []
        for key in sorted(before.keys() | after.keys(), key=repr):
            name = f'{path}/{key!r}'
            if key not in before or key not in after:
                rows.append({'path': name, 'before': repr(before[key]) if key in before else '<absent>',
                             'after': repr(after[key]) if key in after else '<absent>'})
            else:
                rows.extend(_differences(before[key], after[key], name))
        return rows
    return [] if before == after else [{'path': path, 'before': repr(before), 'after': repr(after)}]


_DEFAULT_DEADLINE_SECONDS = 120.0


def inspect(font: Any, *, cancelled: Any = lambda: False, seconds: float = _DEFAULT_DEADLINE_SECONDS) -> dict:
    """Export, reopen and import into owned memory; never save or close the source.

    Native comparisons cover the adapter-readable UFO model and explicitly list
    its losses. UFO sources additionally compare every persistent source family.
    Blocking backend/storage calls are checked on return, not preempted. The
    default deadline is generous (120 s) so a real native font is not refused.
    """
    deadline = monotonic() + seconds

    def check() -> None:
        if cancelled():
            raise InterruptedError('UFO inspection cancelled')
        if monotonic() >= deadline:
            raise TimeoutError('UFO inspection exceeded its deadline; no report published')

    check()
    if font is None:
        raise ValueError('No font supplied')
    font._check()
    font._check_pending()
    backend = font._backend
    source = _snapshot(backend.font, check) if isinstance(backend, UFOBackend) else None
    export = ExportSession(backend)
    for _ in export.steps():
        check()
    staged = _snapshot(export.font, check)
    with TemporaryDirectory(prefix='fontlab-ufo-inspector-') as directory:
        path = export.save(Path(directory) / 'export.ufo')
        check()
        with Font.open(path, lazy=False) as reopened:
            saved = _snapshot(reopened, check)
            destination = UFOBackend()
            with import_ufo(reopened, lambda: destination) as (_imported, steps):
                for _ in steps:
                    check()
                restored = _snapshot(destination.font, check)
        font._check()
        if font._backend is not backend:
            raise RuntimeError('Borrowed font backend changed during inspection')
        current = _snapshot(backend.font, check) if source is not None else None
        if source is not None and current != source:
            raise RuntimeError('Borrowed font changed during inspection; retry')
        report = {
            'scope': 'Complete persisted UFO model' if source is not None else 'Adapter-readable native UFO model only',
            'native_preservation_verified': False,
            'source_written': False,
            'staging': 'Owned temporary directory; removed before this report is published',
            'limitations': list(export.losses),
            'source_to_export': _differences(source, staged) if source is not None else None,
            'export_to_reopened': _differences(staged, saved),
            'reopened_to_imported': _differences(saved, restored),
            'source_to_imported': _differences(source, restored) if source is not None else None,
            'families_checked': list(staged),
            'layers_checked': {name: len(value['glyphs']) for name, value in staged['layers'].items()},
        }
        check()
    check()
    return report


class RoundtripEditor(Owned):
    """Run explicit inspection and retain the complete report until closed."""

    def __init__(self, font: Any, parent: Any = None) -> None:
        self.font, self.report, self.on_closed = font, None, None
        self._busy = False
        super().__init__(parent)
        self.inspect_button = QtGui.QPushButton('Inspect owned UFO roundtrip', self.widget)
        self.status = QtGui.QLabel('Export/import uses temporary files and a detached font. Source is never overwritten.', self.widget)
        self.status.setWordWrap(True)
        self.text = QtGui.QPlainTextEdit(self.widget)
        self.text.setReadOnly(True)
        for widget in (self.inspect_button, self.status, self.text):
            self.layout.addWidget(widget)
        self.connect(self.inspect_button.clicked, lambda *args: self.run())

    def run(self) -> bool:
        if self.closed or self._busy:
            return False
        self.report = None
        self.text.setPlainText('')
        self._busy = True
        try:
            report = inspect(self.font, cancelled=lambda: self.closed)
            text = format_report(report)
            if self.closed:
                return False
            self.report = report
            self.text.setPlainText(text)
            self.status.setText('Inspection complete; all differences and adapter limitations are listed. Temporary staging removed.')
            return True
        except Exception as error:  # noqa: BLE001 - contain borrowed-model errors in Qt callbacks
            if not self.closed:
                self.status.setText(str(error))
            return False
        finally:
            self._busy = False
            if self.closed:
                self.close()

    def close(self) -> None:
        self.closed = True
        if self._busy:
            return
        super().close()
        self.font = None
        if self.on_closed is not None:
            self.on_closed(self)
            self.on_closed = None
