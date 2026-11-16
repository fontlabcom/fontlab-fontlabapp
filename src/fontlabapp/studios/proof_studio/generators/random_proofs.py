# this_file: src/fontlabapp/studios/proof_studio/generators/random_proofs.py
# SPDX-License-Identifier: Apache-2.0
"""Random proofs: the seven Scriptmix "Random …" scripts as one seeded generator.

What: ``make`` runs ``fontlabapp.proof.random.generate(mode)`` (Pedro Arilla's
Apache-2.0 random proofs; see NOTICE), with ``random.Random(seed)`` when a
seed is given and the module RNG (unseeded, as the scripts) otherwise.
``open`` repeats the script: refuse with no font, draw, open one new tab.
``open_current`` opens the previewed draw in one new tab instead.
Pure apart from the lazy backend import; no Qt, no host, no writes.
"""

import random

from fontlabapp.core.scripting import current_package, proof_studio_backends

from . import Context, Generator, Options, Proof

NO_FONT = "Open a font before generating a random proof."


def make(mode: str, options: Options) -> Proof:
    """One part: the complete random proof for ``mode`` (seeded when ``options.seed`` is set)."""
    rng = None if options.seed is None else random.Random(options.seed)
    return Proof((proof_studio_backends().random.generate(mode, rng=rng),))


def open_current(mode: str, context: Context) -> None:
    """Open the previewed draw in one new tab bound to the current font."""
    package = current_package()
    if package is None:
        raise ValueError(NO_FONT)
    proof_studio_backends().text_tab.open_text_tab(context.text(), expected_id=package.id)


def open_tab(mode: str) -> None:
    """The absorbed script: refuse with no font before drawing, then one fresh draw in a new tab."""
    package = current_package()
    if package is None:
        raise ValueError(NO_FONT)
    backends = proof_studio_backends()
    backends.text_tab.open_text_tab(backends.random.generate(mode), expected_id=package.id)


GENERATOR = Generator(
    key="random",
    title="Random proof",
    tab="Random",
    tab_order=30,
    order=10,
    choices=(
        ("Numbers", "numbers"),
        ("Lowercase nontext", "lowercase-nontext"),
        ("Title nontext", "title-nontext"),
        ("Uppercase nontext", "uppercase-nontext"),
        ("Lowercase words", "lowercase-words"),
        ("Title words", "title-words"),
        ("Uppercase words", "uppercase-words"),
    ),
    scripts={
        "numbers": "Random Numbers",
        "lowercase-nontext": "Random Lowercase Nontext",
        "title-nontext": "Random Title Nontext",
        "uppercase-nontext": "Random Uppercase Nontext",
        "lowercase-words": "Random Lowercase Words",
        "title-words": "Random Title Words",
        "uppercase-words": "Random Uppercase Words",
    },
    make=make,
    open=open_tab,
    seeded=True,
    open_current=open_current,
    choice_label="Kind",
)
