# this_file: src/fontlabapp/fontui/detached_transform.py
# SPDX-License-Identifier: Apache-2.0
"""Explicit-layer detached affine preview; borrowed source fonts are never written."""

from copy import deepcopy
from types import SimpleNamespace
from typing import Any

__all__ = ['show']
_HANDLES = []


def _snapshot(font: Any, layer: str, name: str) -> tuple[Any, Any]:
    """Read backend-stored dependencies through a fresh, unregistered layer."""
    from fontlabapp.fontui._fontport import require_fontport

    with require_fontport(__name__):
        from fontlab_fontport.live import RLayer
        from ufoLib2 import Font

    if font is None:
        raise ValueError('No font supplied')
    font._check()
    backend = font._backend
    if not layer or layer not in backend.layer_names():
        raise ValueError('Choose an existing explicit layer')
    if not name or any(character.isspace() for character in name):
        raise ValueError('Choose a glyph name representable by the slash-name proof')
    sources = {}
    RLayer(font, layer)._dependency_sources(name, (), sources)
    if name not in sources:
        raise ValueError('The selected glyph no longer exists in that layer')
    before = Font()
    before.info.unitsPerEm = backend.get_info('unitsPerEm')
    for glyph in sources.values():
        if any(component.baseGlyph not in sources for component in glyph.components):
            raise ValueError('The selected glyph has a missing component base')
        image = glyph.image.fileName
        if image:
            reader = getattr(backend, 'read_image', None)
            data = reader(image) if callable(reader) else None
            if data is None:
                raise ValueError(f'Image resource is unavailable: {image}')
            before.images[image] = bytes(data)
        before.layers.defaultLayer.insertGlyph(deepcopy(glyph))
    return before, deepcopy(before)


class DetachedTransform:
    """Retain the three preview peers and their two private models until ACK."""

    def __init__(self, qt: Any, font: Any) -> None:
        from fontlabapp.core.signals.scope import Scope

        self.qt, self.font = qt, font
        self.problems = []
        self.scope = Scope(self.problems.append)
        self.owned = self.active = None
        self.retired = []
        self.generation = 0
        self.valid = False
        self.published_generation = None
        self._closing = self._released = self._queued = self._releasing = False
        self._busy = 0
        self._pending_target = None
        self._target_queued = False

    def build(self, content: Any) -> None:
        from fontlabapp.fontui.model import FontListState

        self.content = content
        gui = self.qt.QtGui
        self.layout = gui.QVBoxLayout(content)
        self.target = gui.QLabel(content)
        label = 'No font supplied' if self.font is None else FontListState.label(self.font)
        self.target.setText(label)
        self.note = gui.QLabel(
            'Choose a layer and glyph, then Capture. The snapshot is detached; '
            'Refresh reads the same captured font and explicit target. No font '
            'Apply, save or export. Settings Save creates only a chosen new JSON '
            'file; Show script does not execute it. Native metadata/resource '
            'completeness is not guaranteed.', content)
        self.note.setWordWrap(True)
        self.layer_control, self.glyph_control = gui.QComboBox(content), gui.QComboBox(content)
        self.capture_button = gui.QPushButton('Capture snapshot', content)
        self.refresh_button = gui.QPushButton('Refresh snapshot', content)
        self.status = gui.QLabel('Choose a layer and glyph', content)
        for widget in (self.target, self.note, self.layer_control, self.glyph_control,
                       self.capture_button, self.refresh_button, self.status):
            self.layout.addWidget(widget)
        if self.font is not None:
            self.font._check()
            self.layer_control.addItems(list(self.font._backend.layer_names()))
        self.layer_control.setCurrentIndex(-1)
        self.glyph_control.setCurrentIndex(-1)
        self.scope.connect(self.layer_control.currentIndexChanged, lambda *args: self._choose(True))
        self.scope.connect(self.glyph_control.currentIndexChanged, lambda *args: self._choose(False))
        self.scope.connect(self.capture_button.clicked, lambda *args: self.capture())
        self.scope.connect(self.refresh_button.clicked, lambda *args: self.capture())
        self.scope.connect(content.finished, self._finished, closing=True)
        self.scope.connect(content.destroyed, lambda *args: self._destroyed(True), closing=True)

    def _choose(self, layer_changed: bool) -> None:
        if self._closing:
            return
        if self._busy:
            self.valid, self.published_generation = False, None
            self.generation += 1
            self._pending_target = bool(self._pending_target or layer_changed)
            return
        layer_changed = bool(layer_changed or self._pending_target)
        self._pending_target = None
        self._retire()
        if self._closing:
            return
        if layer_changed:
            blocked = self.glyph_control.blockSignals(True)
            try:
                self.glyph_control.clear()
                layer = str(self.layer_control.currentText)
                if self.font is not None and layer:
                    self.font._check()
                    self.glyph_control.addItems(sorted(self.font._backend.glyph_names(layer)))
                self.glyph_control.setCurrentIndex(-1)
            finally:
                self.glyph_control.blockSignals(blocked)
        self.status.setText('Choose a glyph and capture a detached snapshot')

    def _queue_target(self) -> None:
        if (self._pending_target is not None and not self._closing
                and not self._busy and not self._target_queued):
            self._target_queued = True
            self.qt.QtCore.QTimer.singleShot(0, self._flush_target)

    def _flush_target(self) -> None:
        self._target_queued = False
        if self._closing:
            self._pending_target = None
        elif not self._busy and self._pending_target is not None:
            self._choose(self._pending_target)

    def _invalidate(self, stage: Any) -> None:
        if self._closing or stage.retired or stage is not self.active:
            return
        self.valid, self.published_generation = False, None
        self._busy += 1
        try:
            if stage.after is not None:
                stage.after.fail(RuntimeError('Detached transform preview unavailable'))
        finally:
            self._busy -= 1
            self._queue_target()

    def _retire(self) -> None:
        """Fence and clear the old target before any new target/source read."""
        self.valid, self.published_generation = False, None
        self.generation += 1
        stage = self.active
        if stage is None:
            return
        try:
            self._invalidate(stage)
            if stage.before is not None:
                stage.before.fail(RuntimeError('Snapshot target changed'))
        finally:
            self._fence_stage(stage)
            if stage not in self.retired:
                self.retired.append(stage)
            self.active = None

    def capture(self) -> bool:
        """Replace a snapshot only after old UI/model cleanup has acknowledged."""
        if self._closing or self._busy:
            return False
        self._flush_target()
        if self._closing:
            return False
        self._busy += 1
        stage = None
        try:
            self._retire()
            if self._closing or self._pending_target is not None:
                return False
            generation = self.generation
            self._close_retired()
            if self._closing or self._pending_target is not None:
                return False
            layer, name = str(self.layer_control.currentText), str(self.glyph_control.currentText)
            models = _snapshot(self.font, layer, name)
            if (self._closing or self._pending_target is not None
                    or generation != self.generation):
                return False
            stage = SimpleNamespace(models=models, fonts=[], backends=[], peers=[], editor=None,
                                    before=None, after=None, ready=False, pending=None,
                                    layer=layer, name=name, generation=self.generation,
                                    retired=False)
            self.active = stage
            self._build_stage(stage)
            self._check_stage(stage)
            stage.ready = True
            if stage.pending is None:
                raise ValueError('Initial transform preview failed')
            recipe, glyph = stage.pending
            stage.pending = None
            self._publish(stage, recipe, glyph)
            return self.valid
        except BaseException as error:
            self.problems.append(error)
            if stage is not None:
                self._remember_failure(error, stage)
                self._fence_stage(stage)
                if stage not in self.retired:
                    self.retired.append(stage)
                self.active = None
                try:
                    self._close_retired()
                except BaseException as cleanup:
                    self.problems.append(cleanup)
                    error.add_note('Detached snapshot cleanup incomplete; owner retained')
            self.valid, self.published_generation = False, None
            if not self._closing:
                self.status.setText(str(error))
            if not isinstance(error, Exception):
                raise
            return False
        finally:
            self._busy -= 1
            self._queue_target()

    def _check_stage(self, stage: Any) -> None:
        if (self._closing or stage.retired or stage is not self.active
                or stage.generation != self.generation
                or self._pending_target is not None):
            raise RuntimeError('Detached snapshot capture was superseded')

    def _build_stage(self, stage: Any) -> None:
        from fontlab_fontport.live import RFont
        from fontlab_fontport.memory import UFOBackend
        from fontlabapp.fontui import transform_editor, glyph_sequence

        for model in stage.models:
            backend = UFOBackend(model)
            stage.backends.append(backend)
            self._check_stage(stage)
            stage.fonts.append(RFont(backend))
            self._check_stage(stage)
        stage.editor = transform_editor(
            stage.models[0], stage.name, self.content,
            lambda recipe, glyph: self._publish(stage, recipe, glyph),
            lambda: self._invalidate(stage))
        stage.peers.append(stage.editor)
        self._check_stage(stage)
        stage.editor.glyph_control.setEnabled(False)
        self._check_stage(stage)
        self.layout.addWidget(stage.editor.widget)
        self._check_stage(stage)
        for index, font in enumerate(stage.fonts):
            peer = glyph_sequence(font, parent=self.content)
            stage.peers.append(peer)
            if index == 0:
                stage.before = peer
            else:
                stage.after = peer
            self._check_stage(stage)
            self.layout.addWidget(peer.widget)
            self._check_stage(stage)
            peer.mode_control.setCurrentIndex(1)
            self._check_stage(stage)
            peer.text_control.setText('/' + stage.name)
            self._check_stage(stage)
            peer.text_control.setReadOnly(True)
            self._check_stage(stage)
            peer.mode_control.setEnabled(False)
            self._check_stage(stage)
            if peer.run is None or [glyph.name for glyph in peer.run.glyphs] != [stage.name]:
                raise ValueError('The selected name cannot be represented by the proof')

    def _publish(self, stage: Any, recipe: Any, glyph: Any) -> None:
        if self._closing or stage.retired or stage is not self.active:
            return
        if not stage.ready:
            stage.pending = recipe, deepcopy(glyph)
            return
        self._busy += 1
        self.valid, self.published_generation = False, None
        try:
            if stage.generation != self.generation or glyph.name != stage.name:
                raise ValueError('Detached target or generation changed')
            if any(peer.closed for peer in stage.peers):
                raise ValueError('An owned preview peer is closed')
            stage.models[1].layers.defaultLayer.insertGlyph(deepcopy(glyph), overwrite=True)
            stage.fonts[1].refresh()
            stage.after.refresh()
            if self._closing or stage.retired:
                return
            if (stage is not self.active or stage.generation != self.generation
                    or any(peer.closed or peer._close_complete for peer in stage.peers)):
                if not stage.after.closed:
                    stage.after.fail(RuntimeError('An owned preview peer is closed or stale'))
                return
            if (stage.after.run is None
                    or [item.name for item in stage.after.run.glyphs] != [stage.name]
                    or stage.name not in stage.after.outlines
                    or stage.after.outlines[stage.name].recording != stage.editor.result.recording):
                raise ValueError('The detached result was not published')
            self.valid, self.published_generation = True, stage.generation
            self.status.setText(f'Detached snapshot: {stage.layer} / {stage.name}; Refresh reads the captured font')
        except Exception as error:
            if not self._closing and not stage.after.closed:
                stage.after.fail(error)
            raise
        finally:
            self._busy -= 1
            self._queue_target()

    def _fence_stage(self, stage: Any) -> None:
        stage.retired = True
        stage.ready = False
        stage.pending = None
        for peer in stage.peers:
            peer.closed = True
            if peer is stage.editor:
                peer.on_change = peer.on_invalidate = None
            else:
                peer.on_select = peer.on_update = None

    def _remember_failure(self, error: BaseException, stage: Any = None) -> None:
        from fontlabapp.qt.widgets import OwnedWidget
        from fontlabapp.fontui.lifecycle import Owned

        pending = [error]
        while pending:
            failure = pending.pop()
            owner = getattr(failure, 'owner', None)
            if isinstance(owner, OwnedWidget):
                self.owned = owner
            elif stage is not None and isinstance(owner, Owned) and owner not in stage.peers:
                stage.peers.append(owner)
            if isinstance(failure, BaseExceptionGroup):
                pending.extend(failure.exceptions)

    def _close_retired(self) -> None:
        for stage in tuple(self.retired):
            for peer in stage.peers:
                if not peer._close_complete:
                    peer.close()
                if not peer._close_complete:
                    raise RuntimeError('Preview child cleanup incomplete; snapshot retained')
            for index, backend in enumerate(stage.backends):
                if not backend.closed:
                    font = stage.fonts[index] if index < len(stage.fonts) else None
                    if font is not None and not font._closed:
                        font.close()
                    else:
                        # A failed constructor or a refusing backend may leave
                        # no usable wrapper; this backend is still ours to close.
                        backend.close()
                if not backend.closed:
                    raise RuntimeError('Detached backend cleanup incomplete; snapshot retained')
            self.retired.remove(stage)

    def _fence(self) -> None:
        self._closing = True
        self.valid, self.published_generation = False, None
        if self.active is not None:
            self._fence_stage(self.active)
            self.retired.append(self.active)
            self.active = None
        for stage in self.retired:
            self._fence_stage(stage)

    def _finished(self, *args: Any) -> None:
        self._fence()
        if not self._released and not self._queued:
            self._queued = True
            self.qt.QtCore.QTimer.singleShot(0, self._release_queued)

    def _destroyed(self, parent_destroyed: bool = False) -> None:
        self._fence()
        self.scope.finish(destroyed=True)
        # The parent's destroyed signal precedes destruction of its children.
        # Let the existing owners acknowledge while their signal senders live.
        if parent_destroyed:
            for stage in self.retired:
                for peer in stage.peers:
                    if not peer._close_complete:
                        peer._parent_destroyed()
                        try:
                            peer.close()
                        except BaseException as error:
                            self.problems.append(error)
        self._finished()

    def _release_queued(self) -> None:
        self._queued = False
        try:
            self._release_now()
        except BaseException as error:
            self.problems.append(error)

    def release(self) -> bool:
        if self._released:
            return True
        self._finished()
        return False

    def _release_now(self) -> bool:
        from fontlabapp.qt.widgets import release_owned

        if self._released:
            return True
        self._fence()
        if self._busy:
            self._finished()
            return False
        if self._releasing:
            return False
        self._releasing = True
        try:
            complete = release_owned(self.scope, self.owned, self.problems,
                                     (SimpleNamespace(close=self._close_retired),))
        except Exception as error:
            self.problems.append(error)
            return False
        finally:
            self._releasing = False
        if not complete:
            return False
        self._released = True
        _HANDLES.remove(self)
        self.font = self.owned = None
        return True


def show(font: Any, parent: Any = None) -> DetachedTransform:
    """Open one retained explicit-target preview over the exact borrowed font."""
    from fontlabapp import _native
    from fontlabapp.qt.safe import main_window
    from fontlabapp.qt.widgets import create_dialog

    qt = _native('PythonQt')
    owner = DetachedTransform(qt, font)
    _HANDLES.append(owner)
    owner._busy = 1
    try:
        host = parent if parent is not None else main_window(_native('fontlab'), qt)
        owner.owned = create_dialog(host, 'Detached Transform Preview', owner.build)
    except BaseException as error:
        owner.problems.append(error)
        owner._remember_failure(error)
        owner._busy = 0
        try:
            complete = owner._release_now()
        except BaseException as cleanup:
            owner.problems.append(cleanup)
            error.add_note('Detached preview cleanup interrupted; controller retained')
        else:
            if not complete:
                error.add_note('Detached preview cleanup incomplete; controller retained')
        raise
    finally:
        owner._busy = 0
    return owner
