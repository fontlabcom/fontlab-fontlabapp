# this_file: tests/test_random_proof.py
"""Owned deterministic controls for the complete seven-mode proof workflow."""

from random import Random

import pytest

from fontlabapp.proof.random import MODES, generate, word_dictionary


def test_dictionary_has_all_26_ordered_original_buckets_and_4991_entries():
    data = word_dictionary()
    assert list(data) == list("abcdefghijklmnopqrstuvwxyz")
    assert sum(map(len, data.values())) == 4991
    assert data["a"][:3] == ["Aaren", "Aarika", "Abagael"]
    assert data["z"][-3:] == ["Zsazsa", "Zulema", "Zuzana"]


class First(Random):
    def __init__(self):
        self.calls = []

    def choice(self, items):
        self.calls.append(tuple(items))
        return items[0]


def test_numbers_keep_200_digits_and_divisor_choice_for_every_index_including_zero():
    rng = First()
    text = generate("numbers", rng=rng)
    assert text == "0 " + "00 " * 99 + "0"
    assert len(rng.calls) == 400
    assert (
        rng.calls[:4]
        == [("0", "1", "2", "3", "4", "5", "6", "7", "8", "9"), (2, 3)] * 2
    )


@pytest.mark.parametrize(
    "mode,expected",
    [
        ("lowercase-nontext", "a aaa"),
        ("title-nontext", "A Aaa"),
        ("uppercase-nontext", "A AAA"),
    ],
)
def test_nontext_keeps_700_letters_and_random_3_5_7_divisor_calls(mode, expected):
    rng = First()
    text = generate(mode, rng=rng)
    assert len(text.replace(" ", "")) == 700 and text.count(" ") == 234
    assert text.startswith(expected) and text.endswith(" ")
    assert len(rng.calls) == 1400 and rng.calls[1::2] == [(3, 5, 7)] * 700


@pytest.mark.parametrize(
    "mode,method",
    [
        ("lowercase-words", "lower"),
        ("title-words", "title"),
        ("uppercase-words", "upper"),
    ],
)
def test_words_choose_once_per_ordered_letter_and_keep_source_trailing_space(
    mode, method
):
    rng = First()
    text = generate(mode, rng=rng)
    expected = "Aaren Bab Cacilia Dacey Eachelle Fae Gabbey Hadria Ianthe Jacenta Kacey La Verne Mab Nada Octavia Page Queenie Rachael Saba Tabatha Ula Val Wallie Xylia Yalonda Zacata "
    assert text == getattr(expected, method)()
    assert len(rng.calls) == 26
    assert all(
        list(call) == bucket
        for call, bucket in zip(rng.calls, word_dictionary().values())
    )


@pytest.mark.parametrize("mode", MODES)
def test_seeded_invocation_is_repeatable_and_does_not_mutate_dictionary(mode):
    before = word_dictionary()
    a = generate(mode, rng=Random(1234))
    b = generate(mode, rng=Random(1234))
    assert a == b and a and word_dictionary() == before


def test_invalid_mode_fails_before_any_random_draw():
    rng = First()
    with pytest.raises(ValueError, match="Unknown"):
        generate("invalid", rng=rng)
    assert not rng.calls


def test_default_random_source_is_the_existing_module_generator(monkeypatch):
    import fontlabapp.proof.random as api

    calls = []
    monkeypatch.setattr(
        api.random, "choice", lambda values: calls.append(values) or values[0]
    )
    assert generate("numbers") and len(calls) == 400
