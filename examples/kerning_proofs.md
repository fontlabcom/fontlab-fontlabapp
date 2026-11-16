---
this_file: examples/kerning_proofs.md
---

# Complete kerning proof tabs

Open a font, then choose Proof > Hoefler Lowercase, Hoefler Uppercase, KernKing
or KernSym. The native Glyph editor remains available for spacing and kerning.
KernKing opens lowercase followed by mixed case in two separate tabs. Each
other command opens one tab. Repeated invocations create fresh tabs.

```python
from fly.ap.kerning.proofs import run
run("kernking")
```

`proof_texts(mode)` returns immutable strings from all five exact source text
values. It preserves leading/trailing newlines, spaces, punctuation and glyph
escapes. FontLab's advanced text parser handles `/quoteright`, `/germandbls` and
`//` literal slash. Nothing is filtered based on the font's character coverage.
KernSym's original missing x in its lowercase slash row is intentionally kept.

All resources load before native work. The current font and master are captured
once; both are checked before each new tab. Native failure may leave a new tab,
and a failure on KernKing's second tab retains its first tab. Shared App tab
ownership restores source shape activation and disconnects/deletes its sender.
No font geometry, kerning, history or Output writer is used. The original clearLog
and console messages are deliberately omitted to preserve user Output.

The source's undefined `Font` global is replaced by explicit current-font lookup.
A missing/switched font, changed master, resource failure or expired two-second
preflight raises a useful error. Native calls are not preemptible. Source/artifact
controls do not establish native rendering, missing-glyph resolution, full-font
history/dirty state or workspace preservation; these remain root-owned gates.

Original scripts and complete proof-text credits: Pedro Arilla, Hoefler&Co.,
KernKing and the cited KernSym source, recorded with hashes in Scriptmix
`additional-tools.json` and `original-provenance.json`. Apache-2.0 terms and
modification notice are retained in NOTICE and LICENSE.
