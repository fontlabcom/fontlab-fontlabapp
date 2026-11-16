# this_file: tests/test_kerning_proofs.py
"""Exact original resource and public-run oracles; never execute corpus scripts."""

import hashlib
from types import SimpleNamespace as NS

import pytest
import fontlabapp.kerning.proofs as api
import fontlabapp.core.scripting as scripting
import fontlabapp.proof.tabs.text as tabs

EXPECTED = {
    "hoefler-lowercase": (
        "20aa5f420ae61a4ab18c4a6cba81871db6a53f0c7786cc04e3de699c172eda0c",
    ),
    "hoefler-uppercase": (
        "54d4c7c3ec6d0700af6ae265de9a181fd01b03ffdb10bec2cc65603fb8455ff8",
    ),
    "kernking": (
        "383c5749dfa776f773b6e8c62b33bac68adf2beec623d5dd92e48d69350a4853",
        "80257cceb710af86ee65adceb26b516f77fccb61f9f7446bac1786c920ffd047",
    ),
    "kernsym": ("2727482ae2f352ce86c25ddd205781d6baced3e69345a6e752a1e5505c93033c",),
}


@pytest.mark.parametrize("mode", EXPECTED)
def test_complete_original_text_hashes_and_tab_order(mode):
    texts = api.proof_texts(mode)
    assert isinstance(texts, tuple)
    assert (
        tuple(hashlib.sha256(t.encode()).hexdigest() for t in texts) == EXPECTED[mode]
    )
    assert all(t.startswith("\n") and t.endswith("\n") for t in texts)
    assert max(map(len, texts)) < 32767


@pytest.mark.parametrize("mode", EXPECTED)
def test_public_run_keeps_exact_source_font_master_order_and_text(monkeypatch, mode):
    package = NS(id=47, master="Regular")
    monkeypatch.setattr(scripting, "current_package", lambda: package)
    calls = []
    monkeypatch.setattr(tabs, "_open_tab", lambda text, **kw: calls.append((text, kw)))
    monkeypatch.setattr(api, "monotonic", lambda: 10.0)
    api.run(mode)
    assert [t for t, _ in calls] == list(api.proof_texts(mode))
    assert all(
        kw == dict(expected_id=47, expected_master="Regular", deadline=12.0)
        for _, kw in calls
    )


@pytest.mark.parametrize("mode", ["", "unknown", None])
def test_invalid_mode_fails_without_resource_or_host_work(monkeypatch, mode):
    monkeypatch.setattr(
        api, "files", lambda *a: pytest.fail("resource read for invalid mode")
    )
    monkeypatch.setattr(
        scripting, "current_package", lambda: pytest.fail("host read for invalid mode")
    )
    with pytest.raises(ValueError, match="Unknown kerning proof"):
        api.run(mode)


def test_no_font_refuses_without_tab_creation(monkeypatch):
    monkeypatch.setattr(scripting, "current_package", lambda: None)
    monkeypatch.setattr(
        tabs, "_open_tab", lambda *a, **k: pytest.fail("unexpected new tab")
    )
    with pytest.raises(ValueError, match="Open a font"):
        api.run("kernking")


def test_resource_failure_precedes_any_host_or_tab_action(monkeypatch):
    def broken(*args):
        raise OSError("owned unreadable resource")

    monkeypatch.setattr(api, "files", broken)
    monkeypatch.setattr(
        scripting, "current_package", lambda: pytest.fail("resource failed before host")
    )
    with pytest.raises(OSError, match="owned unreadable"):
        api.run("kernking")


def test_kernking_second_failure_retains_first_success_and_does_not_retry(monkeypatch):
    monkeypatch.setattr(
        scripting, "current_package", lambda: NS(id=47, master="Regular")
    )
    calls = []

    def open_tab(text, **kw):
        calls.append(text)
        if len(calls) == 2:
            raise RuntimeError("owned second tab failure")

    monkeypatch.setattr(tabs, "_open_tab", open_tab)
    with pytest.raises(RuntimeError, match="second tab failure"):
        api.run("kernking")
    assert calls == list(api.proof_texts("kernking"))


def test_distinct_runs_get_fresh_immutable_resource_values():
    first = api.proof_texts("kernking")
    assert api.proof_texts("kernking") == first
    assert "/quoteright " in first[0] and "/germandbls " in first[1]
    assert first[0].endswith("\n\n") and first[1].endswith("\n\n")
    assert "//a//b//" in api.proof_texts("kernsym")[0]
