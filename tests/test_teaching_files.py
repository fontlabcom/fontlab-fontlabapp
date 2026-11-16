# this_file: tests/test_teaching_files.py
"""Real search and viewer profiles inside their shared teaching shells."""
import importlib
import sys
from types import SimpleNamespace as NS

import pytest
pytest_plugins = ["_studio_qt"]


@pytest.fixture
def files(studio_qt, monkeypatch):
    for suffix in ('host','files'):
        monkeypatch.delitem(sys.modules, 'fontlabapp.fontui.teaching.'+suffix, raising=False)
    module=importlib.import_module('fontlabapp.fontui.teaching.files')
    qt=sys.modules['PythonQt']
    import fontlabapp
    import fontlabapp.core.scripting as scripts
    monkeypatch.setattr(fontlabapp, '_native', lambda name:qt)
    monkeypatch.setattr(scripts, '_native', lambda name:qt if name=='PythonQt' else NS(MainWindow=lambda:None))
    yield module,qt
    for shell in tuple(module.host.OPEN):
        shell.close()


def test_search_profiles_sort_numerically_and_activate_stored_paths(files,tmp_path,monkeypatch):
    module,qt=files
    paths=[tmp_path/'z.glyphs',tmp_path/'a.glyphs']
    paths[0].write_bytes(b'x'*1000)
    paths[1].write_bytes(b'x'*11000)
    opened=[]
    monkeypatch.setattr(qt.QtGui,'QDesktopServices',NS(openUrl=lambda url:opened.append(url.toLocalFile()) or True))
    shell=module.show_search()
    assert [shell.tabs.tabText(i) for i in range(shell.tabs.count())]==['Text search','Bytes profile','About']
    for owner in shell.children:
        panel=owner.panel
        panel.directory.setEditText(str(tmp_path))
        panel.pattern.setEditText('*.glyphs')
        panel.find_button.click()
        for _ in range(100):
            panel.tick()
            if not panel._timer.isActive():
                break
        assert panel.table.rowCount()==2
        panel.table.sortItems(1,qt.QtCore.Qt.DescendingOrder)
        assert panel.table.item(0,0).text()=='a.glyphs'
        panel.table.item(0,0).setText('edited display')
        panel.table.cellActivated.emit(0,0)
        assert opened[-1]==str(paths[1])
        panel._action(module.actions.activate,-1)
        assert len(opened)==shell.children.index(owner)+1
        panel.find_button.click()
        panel.tick()
    shell.close()


def test_image_profiles_keep_original_controls(files,tmp_path):
    module,qt=files
    shell=module.show_images()
    assert [shell.tabs.tabText(i) for i in range(shell.tabs.count())]==['Full viewer','Bounded zoom','About']
    path=tmp_path/'reference.png'
    image=qt.QtGui.QImage(20,20,qt.QtGui.QImage.Format_ARGB32)
    image.fill(qt.QtGui.QColor('red'))
    assert image.save(str(path))
    for owner in shell.children:
        panel=owner.panel
        assert not panel.isWindow() and panel.load(str(path))
        panel.commands['zoom_in'].trigger()
        assert panel.scale==1.25
        assert not panel.commands['exit'].isVisible()
    shell.close()
