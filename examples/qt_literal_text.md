---
this_file: examples/qt_literal_text.md
---
# Literal Qt values

`fontlabapp.qt.literal_text` supports owned Qt text without routing embedded NUL through PythonQt's no-length Python-string conversion. It imports no Qt binding and receives the existing binding namespace. It creates no application and accesses no clipboard, settings or fonts.

- `read_text(qt, raw)` reads an explicit known QString property or const-reference. Python strings pass through; native references use the documented QStringMatcher value getter.
- `set_mime_text(qt, mime, text)` fills an existing MIME allocation. NUL-bearing text uses full UTF-8 bytes in QByteArray/text/plain. The caller retains MIME ownership. It does not clear unrelated formats.
- `text_fragment(qt, text)` stages one paragraph run through native MIME decoding and returns its detached native cursor selection. CR, LF and PS are rejected because paragraph provenance belongs to the editor. NBSP, LS, NUL and non-BMP characters remain literal. Staging widgets/MIME are unshown and destroyed before return. Call it before changing live selection/history.
- `line_edit_type(qt)` creates a normal QLineEdit subclass. Its programmatic setter uses a native QObject sender/receiver connection for NUL-bearing values, retaining the target's maxLength and ordinary setter cursor/history semantics. Standard Qt bindings use their ordinary length-aware native setter. No persistent signal is connected.

Text Holder uses these values for file content, Find/Replace fields, cursor insertion and native-factory selection MIME. Paragraph identity stays in the existing undo-aware block character format. NUL-bearing IME commit restoration copies the native event before clearing its commit, then restores its copied QString const-reference, offsets and length. Preedit text and attributes stay on the original event. Read-only insertion, paste, IME and replacement return before changing selection/history.

The ordinary PythonQt string conversion and QByteArray QVariant text-property conversion remain lossy; neither is used for NUL text. There is no sentinel, replacement character or shadow document/history. This helper does not yet adapt Character Map or Find Files. Complete final-artifact native workflow acceptance remains a separate gate.

Relaunch builds a complete hidden candidate from one checked content/geometry snapshot before asking the current window to close. Failed construction or refused Close retains the unsaved draft; abandoned candidates disconnect/delete without writing content or window size. Successful same-path reopening retains the current frame size.
