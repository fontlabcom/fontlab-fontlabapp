# this_file: tests/test_issue205_application.py
"""Application startup, platform paths, version parsing and persisted preferences."""

import importlib
from pathlib import Path
import runpy
from types import SimpleNamespace as NS

import pytest

from test_application_messages import app as app


@pytest.mark.parametrize("platform,callable_name", [("darwin", True), ("win32", False)])
def test_paths_when_platform_varies_then_native_locations_and_preference_paths_are_exact(
    monkeypatch, tmp_path, platform, callable_name
):
    import fontlabapp

    module = importlib.import_module("fontlabapp.core.application.paths")
    calls = []
    locations = NS(
        **{
            name: name
            for name in (
                "ApplicationsLocation",
                "FontsLocation",
                "GenericCacheLocation",
                "GenericDataLocation",
                "DesktopLocation",
                "DocumentsLocation",
                "DownloadLocation",
                "HomeLocation",
                "MoviesLocation",
                "MusicLocation",
                "PicturesLocation",
                "TempLocation",
                "ConfigLocation",
            )
        }
    )
    locations.standardLocations = lambda key: [str(tmp_path / key)]
    locations.writableLocation = lambda key: calls.append(key) or str(tmp_path / key)
    monkeypatch.setattr(
        fontlabapp, "_native", lambda name: NS(QtCore=NS(QStandardPaths=locations))
    )
    monkeypatch.setattr(module, "sys", NS(platform=platform))
    app = NS(
        qapp=NS(
            applicationDirPath=lambda: "/Applications/Owned.app/Contents/MacOS",
            applicationName=(lambda: "Owned") if callable_name else "Owned",
        ),
        pref=NS(
            pathAutoSave="autosave",
            dataPathDefault="default",
            dataPath="custom",
            dsigCertificatePath="cert",
            dsigPrivateKeyPath="key",
        ),
    )
    paths = module.ApplicationPaths(app)
    expected = (
        "/Applications/Owned.app"
        if platform == "darwin"
        else "/Applications/Owned.app/Contents/MacOS"
    )
    assert paths.appFolder == Path(expected)
    assert paths.appDataFolder == Path(expected) / "Resources"
    assert paths.sysAppsFolders == [tmp_path / "ApplicationsLocation"]
    assert paths.sysFontFolders == [tmp_path / "FontsLocation"]
    assert paths.userAutoSaveFolder == Path("autosave")
    assert paths.userDsigCertificatePath == Path(
        "cert"
    ) and paths.userDsigPrivateKeyPath == Path("key")
    folder = (
        tmp_path / "ConfigLocation" if platform == "darwin" else Path("custom/Data")
    )
    assert paths.appPrefLibPath == folder / "com.fontlab.Owned.lib.json"
    assert len(calls) == (11 if platform == "darwin" else 10)


@pytest.mark.parametrize(
    "platform,version", [("darwin", "14.2"), ("linux", "14.2"), ("win32", "14.2.10.0")]
)
def test_versions_when_native_info_available_then_all_runtime_versions_are_decoded(
    monkeypatch, platform, version
):
    import fontlabapp

    module = importlib.import_module("fontlabapp.core.application.versions")
    info = NS(
        buildCpuArchitecture=lambda: "arm64",
        currentCpuArchitecture=lambda: "arm64",
        prettyProductName=lambda: "Owned OS",
        productVersion=lambda: "14.2",
    )
    monkeypatch.setattr(
        fontlabapp,
        "_native",
        lambda name: NS(QtCore=NS(QSysInfo=lambda: info, qVersion=lambda: "5.15.2")),
    )
    monkeypatch.setattr(
        module,
        "sys",
        NS(platform=platform, version_info=NS(major=3, minor=11, micro=14, serial=0)),
    )
    monkeypatch.setattr(
        module, "platform", NS(version=lambda: "10.0", python_version=lambda: "3.11.14")
    )
    result = module.Versions(
        NS(qapp=NS(applicationName="Owned", applicationVersion="9.0.1b.9792"))
    )
    assert result.app_version_info == (9, 0, 1, 9792)
    assert result.os_version == version
    assert result.qt_version_info == (5, 15, 2, 0)
    assert result.py_version_info == (3, 11, 14, 0)
    assert result.app_arch == result.os_arch == "arm64"
    with pytest.raises(ValueError, match="numeric components"):
        result._get_version_info_from_str("bad.1")


@pytest.mark.parametrize("optional", [False, True])
def test_application_when_started_then_services_share_the_workspace_and_are_cached(
    app, monkeypatch, optional
):
    application, output, _, module = app
    main = NS(menuBar=lambda: "menus")
    workspace = NS(mainWindow=main)
    qapp = object()
    pref = object()
    monkeypatch.setattr(
        module,
        "fontlab",
        NS(
            flWorkspace=NS(instance=lambda: workspace),
            flItems="items",
            flPreferences=lambda: pref,
        ),
    )
    monkeypatch.setattr(
        module.QtGui, "QApplication", NS(instance=lambda: qapp), raising=False
    )
    seen = []

    def service(name):
        return lambda owner: seen.append((name, owner)) or NS(owner=owner)

    monkeypatch.setattr(module, "ApplicationPaths", service("paths"))
    monkeypatch.setattr(module, "Versions", service("versions"))
    preflib = importlib.import_module("fontlabapp.core.application.preflib")
    ui = importlib.import_module("fontlabapp.core.application.ui")
    host = importlib.import_module("fontlabapp.core.host")
    monkeypatch.setattr(preflib, "PrefLib", service("preferences"))
    monkeypatch.setattr(ui, "ApplicationUI", service("ui"))
    expected_host = NS(
        menu="menu", actions="actions", panels="panels", glyph_actions="glyph_actions"
    )
    monkeypatch.setattr(host, "Host", lambda window: expected_host)
    result = module.Application(with_ui=optional, with_preflib=optional)
    assert (
        result.ws,
        result.main,
        result.qmenus,
        result.item,
        result.qapp,
        result.pref,
    ) == (workspace, main, "menus", "items", qapp, pref)
    assert [name for name, _ in seen] == ["paths", "versions"] + (
        ["preferences", "ui"] if optional else []
    )
    assert all(owner is result for _, owner in seen)
    assert result.host is result.host is expected_host
    assert (result.menu, result.actions, result.panels, result.glyph_actions) == (
        "menu",
        "actions",
        "panels",
        "glyph_actions",
    )
    assert result.control is result.control and result.control.application is result
    application.print("<A>")
    application.print_md("**A**")
    application.print_html("<b>A</b>", styled=True)
    assert "&lt;A&gt;" in output[0][1] and "<strong>A</strong>" in output[1][1]
    assert "<html>" in output[2][1]


def test_preferences_when_entrypoint_runs_then_defaults_and_edited_values_survive_save(
    monkeypatch, tmp_path, capsys
):
    import fontlabapp

    module = importlib.import_module("fontlabapp.core.application.preflib")
    preferences = module.PrefLib(NS(paths=NS(appPrefLibPath=tmp_path / "prefs.json")))
    for name in fontlabapp.__all__:
        monkeypatch.setitem(vars(fontlabapp), name, NS())
    monkeypatch.setitem(
        vars(fontlabapp), "Application", lambda: NS(preflib=preferences)
    )
    runpy.run_path(module.__file__, run_name="__main__")
    assert preferences.lib.com.fontlab.demo.key1 == "val3"
    assert '"key1": "val3"' in (tmp_path / "prefs.json").read_text()
    assert "preflib.lib:" in capsys.readouterr().out
