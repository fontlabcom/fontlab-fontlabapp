---
this_file: examples/find_files.md
---
# Find font source files

Open the decoded-text panel with `fly.ap.qt.find_files.model.show()` or the UTF-8-byte
panel with `fly.ap.qt.find_files.model.show_bytes()`. Both search one directory using a
filename pattern and literal content query. Browse selects a directory; Find
starts the search; Cancel and closing the window release the active stream.

The decoded panel follows file symlinks, uses the live filename pattern and
shows matches progressively. The byte panel excludes symlinks, captures its
pattern at Find, keeps ordered query histories and publishes completed results.
The original line-editor maximum remains 32,767 UTF-16 units.

Embedded NUL remains part of the content query. Editable fields use the shared
literal Qt setter, while history stores genuine native model strings and recalls
them through Qt. A history append leaves an edited draft, cursor, selection and
Undo state alone. There is no sentinel substitution or parallel text store.
A NUL in a directory remains an invalid filesystem path and reports the error;
it does not silently search the path prefix.

The ordinary search engine and both original workflow schedules remain unchanged.
Standalone Qt tests do not qualify PythonQt. Native history transfer, complete
installed FontLab workflows and full-font preservation require separate evidence.
