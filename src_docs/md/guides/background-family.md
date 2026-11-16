---
this_file: src_docs/md/guides/background-family.md
---

# Pedro background tools

Scale takes a finite percentage (including fractions and negatives), multiplies
background own path nodes about the origin, and leaves components untouched.
Shift takes a finite x offset, moves every background own path node and
component position, and preserves y and the component linear transform.
Both process selected layers in order; a repeated layer receives the operation
again. The dialog captures selection when Apply is pressed and closes on success.
Invalid input leaves the field and dialog open for correction.

Selection to All the Backgrounds runs immediately. It uses only the first
selected layer, copies each whole path whose every node is selected (including
an empty contour), and excludes components. It replaces that layer background
and the selected-master background of **every glyph in font order**. The first
layer may be auxiliary, so its background is an additional destination. No
selected whole paths means clear all those backgrounds. Later selected layers
are not read. Existing mask custom metadata, identity, width and inherited mark
state remain attached while old shapes, anchors and nonhint guides are replaced.

FontLab mapping uses native mask layers. Foreign, automatic or hint-bearing
replacement masks and missing selected-master foregrounds diagnose the whole
operation before history; no subset is reported as success. Existing background
metadata remains in place. Copies preserve notes, raw node states, open/closed
and cubic/quadratic topology. Originals are never executed or packaged.

A changed selection, document, master, complete destination inventory or
background content refuses before mutation. Copies are staged before history.
Attachment failures attempt scoped geometry recovery, retain all errors and
poison the adapter; late history/cache failures may retain changes. Reopen only
after reviewing native history. No global Undo, UpdateAll, preference writer,
Output clearing or event pump is used. Paint updates restore their prior state.

This is a source and installed-artifact candidate. Native acceptance is pending:
owned full-font/cache/dependency preservation, successive different-glyph edits,
Apply/Undo/Redo/save/reopen and actual Qt lifecycle. No native calls were made.

N86 HOLD — independent N92 source review found a core rich-copy blocker.
FontLab ShapeImpl::assignStyle calls the source-mutating getPenParameters and
copies effective content lock into the raw destination lock. cloneCustom uses
that route. Current Python bindings cannot observe/restore those private fields.
All three workflows remain INCOMPLETE and unqualified for integration despite
passing ordinary offline artifacts. No native calls, canonical apply or push.
Exact source pins, unapplied native fix direction and before-history source
counterexamples are retained in background-family-z33 and independent N92.
