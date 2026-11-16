# this_file: tests/test_context_proofs.py
"""Own exact original proof rows, repeated selections and empty-domain behavior."""

from types import SimpleNamespace as NS

import pytest

import fontlabapp.proof.context as api


@pytest.mark.parametrize(
    "mode,context",
    [
        ("lowercase", tuple("abcdefghijklmnopqrstuvwxyz")),
        ("uppercase", tuple("ABCDEFGHIJKLMNOPQRSTUVWXYZ")),
        (
            "lining",
            (
                "zero",
                "one",
                "two",
                "three",
                "four",
                "five",
                "six",
                "seven",
                "eight",
                "nine",
            ),
        ),
        (
            "oldstyle",
            tuple(
                n + ".osf"
                for n in (
                    "zero",
                    "one",
                    "two",
                    "three",
                    "four",
                    "five",
                    "six",
                    "seven",
                    "eight",
                    "nine",
                )
            ),
        ),
    ],
)
def test_between_contexts_preserve_every_name_and_two_final_newlines(mode, context):
    rows = api.proof_lines(mode, ("unencoded.alt", "B", "unencoded.alt"))
    assert len(rows) == 7 and rows[1] == rows[3] == rows[5] == rows[6] == ()
    assert rows[0][::2] == ("unencoded.alt",) * (len(context) + 1)
    assert rows[0][1::2] == context and rows[2][0] == "B" and rows[4] == rows[0]
    assert api.proof_lines(mode, ()) == ((),)


@pytest.mark.parametrize(
    "mode,context",
    [
        ("H", ("H",)),
        ("I", ("I",)),
        ("HHOHH", tuple("HHOHH")),
        ("nnonn", tuple("nnonn")),
    ],
)
def test_surround_contexts_preserve_repeated_occurrences_and_empty_selection(
    mode, context
):
    assert api.proof_lines(mode, ("A", "A")) == (
        context + ("A",) + context + ("A",) + context,
    )
    assert api.proof_lines(mode, ()) == (context,)


def test_golden_original_slash_text_keeps_unencoded_name_order_and_blank_lines():
    rows = api.proof_lines("lining", ("A.alt",))
    text = "\n".join("".join("/" + n for n in row) for row in rows)
    assert (
        text
        == "/A.alt/zero/A.alt/one/A.alt/two/A.alt/three/A.alt/four/A.alt/five/A.alt/six/A.alt/seven/A.alt/eight/A.alt/nine/A.alt\n\n"
    )


def test_invalid_mode_and_expired_deadline_do_not_make_a_valid_prefix(monkeypatch):
    with pytest.raises(ValueError, match="Unknown"):
        api.proof_lines("invalid", ("A",))
    monkeypatch.setattr(api, "monotonic", lambda: 3.0)
    with pytest.raises(TimeoutError):
        api.proof_lines("H", ("A", "B"), deadline=2.0)


@pytest.fixture
def selection(monkeypatch):
    import fontlabapp.masters.layers.selection as layers
    import fontlabapp.proof.tabs.named as tabs

    first = NS(
        context=(7, "Regular", "editor"),
        occurrences=(NS(glyph_name="A"), NS(glyph_name="A")),
    )
    state = NS(captures=[], opens=[], value=first)

    def capture(deadline):
        state.captures.append(deadline)
        return state.value

    monkeypatch.setattr(layers, "capture", capture)
    monkeypatch.setattr(
        tabs,
        "open_named_tab",
        lambda rows, **kwargs: state.opens.append((rows, kwargs)),
    )
    return state


def test_run_uses_complete_repeated_selection_one_deadline_and_captured_font(selection):
    api.run("H")
    assert (
        len(selection.captures) == 2 and selection.captures[0] == selection.captures[1]
    )
    assert selection.opens == [
        (
            (("H", "A", "H", "A", "H"),),
            {"expected_id": 7, "master": "Regular", "deadline": selection.captures[0]},
        )
    ]


def test_run_refuses_changed_selection_before_new_tab(selection, monkeypatch):
    import fontlabapp.masters.layers.selection as layers

    values = iter((selection.value, NS(context=(8, "Other", "font"), occurrences=())))
    monkeypatch.setattr(layers, "capture", lambda deadline: next(values))
    with pytest.raises(ValueError, match="changed"):
        api.run("H")
    assert selection.opens == []


@pytest.mark.parametrize("mode", api.MODES)
def test_run_keeps_original_empty_selection_result_without_false_refusal(
    selection, mode
):
    selection.value.occurrences = ()
    api.run(mode)
    assert selection.opens[0][0] == api.proof_lines(mode, ())


def test_provider_failure_never_reaches_new_tab(selection, monkeypatch):
    import fontlabapp.masters.layers.selection as layers

    monkeypatch.setattr(
        layers,
        "capture",
        lambda deadline: (_ for _ in ()).throw(ValueError("owned selection failure")),
    )
    with pytest.raises(ValueError, match="owned selection"):
        api.run("H")
    assert selection.opens == []
