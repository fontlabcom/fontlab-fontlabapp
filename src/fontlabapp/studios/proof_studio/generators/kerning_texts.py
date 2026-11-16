# this_file: src/fontlabapp/studios/proof_studio/generators/kerning_texts.py
# SPDX-License-Identifier: Apache-2.0
"""Kerning proof texts: the four bundled texts, byte for byte, one part per tab.

Absorbs the Scriptmix Hoefler Lowercase, Hoefler Uppercase, KernKing and
KernSym scripts (adapted from Pedro Arilla's Apache-2.0 Kerning scripts).
Texts come from ``fontlabapp.kerning.proofs.proof_texts`` through
``core.scripting.kerning_proof_api``; KernKing has two parts (lowercase,
then mixed case), the others one. ``open`` calls the same ``run(mode)``.
"""

from fontlabapp.core.scripting import kerning_proof_api

from . import Generator, Options, Proof


def make(mode: str, options: Options) -> Proof:
    """The bundled texts of ``mode``; the selection is not used."""
    return Proof(tuple(kerning_proof_api().proof_texts(mode)))


def open_tabs(mode: str) -> None:
    """Open one new text tab per part on the current font and master, in order."""
    kerning_proof_api().run(mode)


GENERATOR = Generator(
    key="kerning-texts",
    title="Kerning proof texts",
    tab="Kerning proofs",
    tab_order=20,
    order=10,
    choices=(
        ("Hoefler lowercase", "hoefler-lowercase"),
        ("Hoefler uppercase", "hoefler-uppercase"),
        ("KernKing", "kernking"),
        ("KernSym", "kernsym"),
    ),
    scripts={
        "hoefler-lowercase": "Hoefler Lowercase",
        "hoefler-uppercase": "Hoefler Uppercase",
        "kernking": "KernKing",
        "kernsym": "KernSym",
    },
    make=make,
    open=open_tabs,
)
